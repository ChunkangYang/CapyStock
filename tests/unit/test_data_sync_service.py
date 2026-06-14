"""Fix 3-3：data_sync_service.run_cloud_sync kinds 過濾 + rescan 開關測試。"""
import pandas as pd
import pytest

from api.services import data_sync_service as dss
from capystock import config


@pytest.fixture
def fake_dirs(tmp_path, monkeypatch):
    """把 cloud-cache / cache 指到 tmp，預放一檔 price + 一檔 margin。"""
    cloud = tmp_path / "data" / "cloud-cache"
    cache = tmp_path / "cache"
    cloud.mkdir(parents=True)
    cache.mkdir(parents=True)
    (cloud / "7203_price.csv").write_text("date,close\n2026-06-05,3000\n", encoding="utf-8")
    (cloud / "7203_margin.csv").write_text("week,margin_long\n2026-06-01,100\n", encoding="utf-8")

    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(config, "CACHE_DIR", cache)
    # 同步標記檔導到 tmp，避免測試污染真實 data/last_sync.json
    monkeypatch.setattr(dss, "SYNC_MARKER_PATH", tmp_path / "last_sync.json")
    return cloud, cache


def test_kinds_price_only_copies_price(fake_dirs):
    cloud, cache = fake_dirs
    r = dss.run_cloud_sync(pull=False, kinds=["price"], rescan=False)
    assert (cache / "7203_price.csv").exists()
    assert not (cache / "7203_margin.csv").exists()
    assert r["rescan"] is None


def test_kinds_none_copies_all(fake_dirs):
    cloud, cache = fake_dirs
    dss.run_cloud_sync(pull=False, kinds=None, rescan=False)
    assert (cache / "7203_price.csv").exists()
    assert (cache / "7203_margin.csv").exists()


def test_rescan_false_does_not_scan(fake_dirs, monkeypatch):
    called = {"n": 0}

    def boom(*a, **k):
        called["n"] += 1
        return ([], [])

    monkeypatch.setattr("api.services.scan_service.run_signals_scan", boom)
    dss.run_cloud_sync(pull=False, kinds=["price"], rescan=False)
    assert called["n"] == 0


def test_sync_marker_and_state(fake_dirs):
    """同步成功後寫 marker，get_sync_state 報 synced_today=True。"""
    # 同步前：marker 不存在 → synced_today=False
    st0 = dss.get_sync_state()
    assert st0["synced_today"] is False
    assert st0["last_date"] is None

    dss.run_cloud_sync(pull=False, kinds=["price"], rescan=False)

    st1 = dss.get_sync_state()
    assert st1["synced_today"] is True
    assert st1["last_date"] == st1["today"]


def test_progress_callback_emits_phases(fake_dirs):
    """progress_callback 應收到 copy 階段與最後 done=100%。"""
    events: list[dict] = []
    dss.run_cloud_sync(
        pull=False, kinds=["price"], rescan=False, progress_callback=events.append
    )
    phases = {e["phase"] for e in events}
    assert "copy" in phases
    assert events[-1]["phase"] == "done"
    assert events[-1]["percent"] == 100
