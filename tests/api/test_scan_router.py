from datetime import date, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.schemas.scan import DividendScanRow, SignalScanRow

client = TestClient(app)


@pytest.fixture
def mock_signals_snapshot():
    """模擬訊號快照"""
    return [
        SignalScanRow(
            code="7203",
            name="トヨタ",
            latest_price=2500.0,
            has_accumulation=True,
            has_exit=False,
            has_stop_loss=False,
            edinet_recent_count=0,
            score=3,
            generated_at=datetime(2026, 4, 25, 12, 0),
        ),
        SignalScanRow(
            code="6758",
            name="ソニー",
            latest_price=1500.0,
            has_accumulation=False,
            has_exit=True,
            has_stop_loss=False,
            edinet_recent_count=1,
            score=-2,
            generated_at=datetime(2026, 4, 25, 12, 0),
        ),
    ]


@pytest.fixture
def mock_dividend_snapshot():
    """模擬配息快照"""
    return [
        DividendScanRow(
            code="7203",
            name="トヨタ",
            overall="HEALTHY",
            pass_count=6,
            warn_count=2,
            fail_count=0,
            latest_dps=75.0,
            dps_streak_no_cut=10,
            est_yield=0.03,
            payout_avg=0.35,
            equity_ratio_latest=0.45,
            eps_growth=0.05,
            generated_at=datetime(2026, 4, 25, 12, 0),
        ),
        DividendScanRow(
            code="6758",
            name="ソニー",
            overall="STRONG",
            pass_count=7,
            warn_count=1,
            fail_count=0,
            latest_dps=100.0,
            dps_streak_no_cut=12,
            est_yield=0.05,
            payout_avg=0.40,
            equity_ratio_latest=0.50,
            eps_growth=0.10,
            generated_at=datetime(2026, 4, 25, 12, 0),
        ),
    ]


def test_get_signals_snapshot_historical_not_found():
    """指定歷史日期但無對應 parquet 時回 404"""
    with patch("api.routers.scan.scan_service.load_latest_snapshot") as mock_load:
        mock_load.return_value = None

        response = client.get("/api/v1/scan/signals?date=2020-01-01")
        assert response.status_code == 404
        assert "No snapshot found" in response.json()["detail"]


def test_get_signals_snapshot_historical_success(mock_signals_snapshot):
    """指定歷史日期且有對應 parquet 時，從 parquet 讀資料"""
    import pandas as pd

    df = pd.DataFrame([r.model_dump() for r in mock_signals_snapshot])

    with patch("api.routers.scan.scan_service.load_latest_snapshot") as mock_load:
        mock_load.return_value = df

        response = client.get("/api/v1/scan/signals?date=2026-04-25")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        assert len(body["data"]) == 2
        assert body["data"][0]["code"] == "7203"
        assert body["data"][0]["has_accumulation"] is True
        assert body["data"][1]["score"] == -2


def test_get_signals_snapshot_live_uses_in_memory(mock_signals_snapshot):
    """預設（不指定 date）走即時計算路徑，不讀 parquet。"""
    with patch("api.routers.scan.scan_service.load_latest_snapshot") as mock_load, patch(
        "api.routers.scan._get_or_compute_live_signals"
    ) as mock_live:
        from datetime import datetime

        mock_live.return_value = (mock_signals_snapshot, [], datetime.now())

        response = client.get("/api/v1/scan/signals")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        assert len(body["data"]) == 2
        # 預設路徑不應該讀 parquet
        mock_load.assert_not_called()
        mock_live.assert_called_once()


def test_get_dividend_snapshot_with_filter(mock_dividend_snapshot):
    """篩選 min_yield"""
    import pandas as pd

    df = pd.DataFrame([r.model_dump() for r in mock_dividend_snapshot])

    with patch("api.routers.scan.scan_service.load_latest_snapshot") as mock_load:
        mock_load.return_value = df

        response = client.get("/api/v1/scan/dividend?min_yield=0.04")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["code"] == "6758"


def test_get_dividend_snapshot_with_overall_filter(mock_dividend_snapshot):
    """篩選 overall"""
    import pandas as pd

    df = pd.DataFrame([r.model_dump() for r in mock_dividend_snapshot])

    with patch("api.routers.scan.scan_service.load_latest_snapshot") as mock_load:
        mock_load.return_value = df

        response = client.get("/api/v1/scan/dividend?overall=STRONG")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["overall"] == "STRONG"


def test_get_dividend_snapshot_with_sort(mock_dividend_snapshot):
    """排序 est_yield desc"""
    import pandas as pd

    df = pd.DataFrame([r.model_dump() for r in mock_dividend_snapshot])

    with patch("api.routers.scan.scan_service.load_latest_snapshot") as mock_load:
        mock_load.return_value = df

        response = client.get("/api/v1/scan/dividend?order_by=est_yield&desc=true")
        assert response.status_code == 200
        data = response.json()
        assert data[0]["code"] == "6758"  # 0.05 > 0.03
        assert data[1]["code"] == "7203"


def test_get_snapshots_list():
    """列出所有快照"""
    with patch("api.routers.scan.scan_service.list_snapshots") as mock_list:
        mock_list.return_value = [
            {"date": "2026-04-25", "kind": "signals", "rows": 10, "path": "/data/scan_snapshots/signals_2026-04-25.parquet"},
            {"date": "2026-04-24", "kind": "signals", "rows": 8, "path": "/data/scan_snapshots/signals_2026-04-24.parquet"},
        ]

        response = client.get("/api/v1/scan/snapshots")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2


def test_run_scan_sync():
    """同步掃描"""
    with patch("api.routers.scan.scan_service.load_universe") as mock_universe, patch(
        "api.routers.scan.scan_service.run_signals_scan"
    ) as mock_run, patch("api.routers.scan.scan_service.write_snapshot") as mock_write:
        mock_universe.return_value = [{"code": "7203", "name": "トヨタ", "market": "Prime"}]
        mock_run.return_value = ([], [])
        mock_write.return_value = "/fake/path"

        response = client.post("/api/v1/scan/run", json={"kind": "signals"}, params={"async_mode": False})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["kind"] == "signals"


def test_run_scan_invalid_kind():
    """無效的 kind"""
    with patch("api.routers.scan.scan_service.load_universe") as mock_universe:
        mock_universe.return_value = []

        response = client.post("/api/v1/scan/run", json={"kind": "invalid"}, params={"async_mode": False})
        assert response.status_code == 500


def test_get_job_status():
    """查 job 狀態"""
    response = client.get("/api/v1/scan/jobs/nonexistent")
    assert response.status_code == 404
    assert "Job not found" in response.json()["detail"]
