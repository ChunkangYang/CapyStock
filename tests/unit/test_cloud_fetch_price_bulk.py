"""Fix 3-1：cloud_fetch 價格 bulk 模式單元測試（mock yf.download / Ticker）。

驗證：
  (a) 輸出 header 與既有 cloud-cache 檔逐字一致（9 欄）
  (b) 增量合併 dedupe by date
  (c) trim 只留最後 260 列
  (d) 檔案不存在 → 走 6mo 單檔初始化
  (e) 批次失敗不中斷其他批
"""
import importlib.util
import sys
import types
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
EXPECTED_HEADER = ["date", "open", "high", "low", "close", "adj close", "volume", "dividends", "stock splits"]


def _load_cloud_fetch():
    spec = importlib.util.spec_from_file_location("cloud_fetch", ROOT / "scripts" / "cloud_fetch.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _yf_single_df(dates, base=100.0):
    """模擬 yfinance 單檔回傳（index=Date，欄位 Open/High/Low/Close/Adj Close/Volume）。"""
    idx = pd.to_datetime(dates)
    idx.name = "Date"  # 真實 yfinance 的 index 名為 Date（reset_index 後成 date 欄）
    n = len(dates)
    return pd.DataFrame(
        {
            "Open": [base + i for i in range(n)],
            "High": [base + 5 + i for i in range(n)],
            "Low": [base - 5 + i for i in range(n)],
            "Close": [base + 2 + i for i in range(n)],
            "Adj Close": [base + 1 + i for i in range(n)],
            "Volume": [1000 + i for i in range(n)],
        },
        index=idx,
    )


def _install_fake_yf(monkeypatch, download_impl=None, history_impl=None):
    fake = types.ModuleType("yfinance")

    def default_download(tickers, **kwargs):
        # 多 ticker → MultiIndex；單 ticker → flat
        if isinstance(tickers, (list, tuple)) and len(tickers) > 1:
            frames = {}
            for t in tickers:
                frames[t] = _yf_single_df(["2026-06-04", "2026-06-05"])
            return pd.concat(frames, axis=1)
        return _yf_single_df(["2026-06-04", "2026-06-05"])

    fake.download = download_impl or default_download

    class FakeTicker:
        def __init__(self, symbol):
            self.symbol = symbol

        def history(self, **kwargs):
            if history_impl:
                return history_impl(self.symbol, **kwargs)
            return _yf_single_df(["2026-06-04", "2026-06-05"])

    fake.Ticker = FakeTicker
    monkeypatch.setitem(sys.modules, "yfinance", fake)


def test_output_header_matches_existing(tmp_path, monkeypatch):
    mod = _load_cloud_fetch()
    monkeypatch.setattr(mod, "CLOUD_CACHE_DIR", tmp_path)
    _install_fake_yf(monkeypatch)

    # 檔案不存在 → 走 6mo 初始化（Ticker.history）
    results = mod.fetch_price_bulk_cloud(["7203"])
    assert results[0]["ok"] is True
    out = tmp_path / "7203_price.csv"
    assert out.exists()
    header = out.read_text(encoding="utf-8").splitlines()[0].split(",")
    assert header == EXPECTED_HEADER


def test_incremental_merge_dedupe_by_date(tmp_path, monkeypatch):
    mod = _load_cloud_fetch()
    monkeypatch.setattr(mod, "CLOUD_CACHE_DIR", tmp_path)
    # 預先放既有檔（含 2026-06-04 舊值）
    existing = pd.DataFrame(
        [["2026-06-03", 1, 2, 0, 1, 1, 10, 0.0, 0.0],
         ["2026-06-04", 9, 9, 9, 999, 9, 10, 0.0, 0.0]],
        columns=EXPECTED_HEADER,
    )
    existing.to_csv(tmp_path / "7203_price.csv", index=False)

    _install_fake_yf(monkeypatch)  # download 回 06-04 / 06-05
    mod.fetch_price_bulk_cloud(["7203"])

    df = pd.read_csv(tmp_path / "7203_price.csv")
    df["date"] = df["date"].astype(str)
    # 三個不同日期，06-04 被新值覆蓋（keep=last）
    assert sorted(df["date"]) == ["2026-06-03", "2026-06-04", "2026-06-05"]
    row0604 = df[df["date"] == "2026-06-04"].iloc[0]
    assert row0604["close"] != 999  # 舊值已被新下載覆蓋


def test_trim_to_260_rows(tmp_path, monkeypatch):
    mod = _load_cloud_fetch()
    monkeypatch.setattr(mod, "CLOUD_CACHE_DIR", tmp_path)
    # 既有 400 列
    dates = pd.date_range("2024-01-01", periods=400).strftime("%Y-%m-%d")
    existing = pd.DataFrame(
        [[d, 1, 2, 0, 1, 1, 10, 0.0, 0.0] for d in dates], columns=EXPECTED_HEADER
    )
    existing.to_csv(tmp_path / "7203_price.csv", index=False)

    _install_fake_yf(monkeypatch)
    mod.fetch_price_bulk_cloud(["7203"])

    df = pd.read_csv(tmp_path / "7203_price.csv")
    assert len(df) == mod._PRICE_TRIM_ROWS == 260


def test_missing_file_uses_6mo_init(tmp_path, monkeypatch):
    mod = _load_cloud_fetch()
    monkeypatch.setattr(mod, "CLOUD_CACHE_DIR", tmp_path)
    called = {"period": None}

    def history_impl(symbol, **kwargs):
        called["period"] = kwargs.get("period")
        return _yf_single_df(["2026-06-04", "2026-06-05"])

    _install_fake_yf(monkeypatch, history_impl=history_impl)
    mod.fetch_price_bulk_cloud(["7203"])
    assert called["period"] == "6mo"


def test_batch_failure_does_not_abort_others(tmp_path, monkeypatch):
    mod = _load_cloud_fetch()
    monkeypatch.setattr(mod, "CLOUD_CACHE_DIR", tmp_path)

    def boom_download(tickers, **kwargs):
        raise RuntimeError("yahoo down")

    # 兩檔都先有既有檔（避免走 6mo 單檔 init path）
    for c in ["7203", "6758"]:
        pd.DataFrame([["2026-06-03", 1, 2, 0, 1, 1, 10, 0.0, 0.0]], columns=EXPECTED_HEADER).to_csv(
            tmp_path / f"{c}_price.csv", index=False
        )
    _install_fake_yf(monkeypatch, download_impl=boom_download)

    results = mod.fetch_price_bulk_cloud(["7203", "6758"], batch_size=2)
    assert len(results) == 2
    assert all(r["ok"] is False for r in results)
    assert all("yahoo down" in r["error"] for r in results)
