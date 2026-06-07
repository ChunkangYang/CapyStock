"""三盤濾網選股（pocket_filter）單元測試。

驗證三盤各自的純函式邏輯，以及單檔三盤整合：
  - 第一盤 連續性：同一申報人重複申報 >= 門檻
  - 第二盤 成本：現價 <= 主力成本 +5%
  - 第三盤 戶數/籌碼集中：信用残連續下降
重點：確認濾網吃的是「單一個股」真實資料，兩檔不同輸入會得到不同結果。
"""
import pandas as pd
import pytest

from capystock import pocket_filter as pf


def _filings(filer, dates, doc="350"):
    return [{"submit_date": d, "filer_name": filer, "doc_type_code": doc} for d in dates]


def _price_df(pairs):
    return pd.DataFrame([{"date": d, "close": c} for d, c in pairs])


def _margin_df(pairs):
    return pd.DataFrame([{"week": w, "margin_long": m} for w, m in pairs])


# ---------------- 第一盤 ----------------
def test_gate1_pass_same_filer_repeated():
    g = pf.gate1_continuity(_filings("野村證券", ["2026-04-06", "2026-04-21"]), min_filings=2)
    assert g["passed"] is True
    assert g["lead_filer"] == "野村證券"
    assert g["filing_count"] == 2


def test_gate1_fail_single_filing():
    g = pf.gate1_continuity(_filings("野村證券", ["2026-04-06"]), min_filings=2)
    assert g["passed"] is False
    assert g["filing_count"] == 1


def test_gate1_picks_most_frequent_filer():
    filings = _filings("A社", ["2026-04-06"]) + _filings("B社", ["2026-04-07", "2026-04-10", "2026-04-20"])
    g = pf.gate1_continuity(filings, min_filings=2)
    assert g["lead_filer"] == "B社"
    assert g["filing_count"] == 3


def test_gate1_window_excludes_old_filings():
    # 兩筆相距超過 window_days，僅最新一筆落在窗口 → 不過關
    g = pf.gate1_continuity(
        _filings("野村證券", ["2026-01-01", "2026-04-21"]),
        min_filings=2, window_days=30,
    )
    assert g["filing_count"] == 1
    assert g["passed"] is False


# ---------------- 第二盤 ----------------
def test_gate2_pass_price_below_cost():
    price = _price_df([("2026-04-06", 1000.0), ("2026-04-21", 1010.0), ("2026-06-01", 1020.0)])
    g = pf.gate2_cost(price, ["2026-04-06", "2026-04-21"], tolerance=0.05)
    # 主力成本=(1000+1010)/2=1005，現價1020，溢價約 +1.5% <= 5% → 過
    assert g["passed"] is True
    assert g["master_cost"] == pytest.approx(1005.0)
    assert g["latest_price"] == 1020.0


def test_gate2_fail_price_chasing_high():
    price = _price_df([("2026-04-06", 1000.0), ("2026-06-01", 1200.0)])
    g = pf.gate2_cost(price, ["2026-04-06"], tolerance=0.05)
    # 主力成本1000，現價1200，溢價+20% > 5% → 不過（追高）
    assert g["passed"] is False
    assert g["premium_pct"] == pytest.approx(0.20)


def test_gate2_no_filing_dates_returns_fail():
    price = _price_df([("2026-04-06", 1000.0)])
    g = pf.gate2_cost(price, [], tolerance=0.05)
    assert g["passed"] is False
    assert g["master_cost"] is None


# ---------------- 第三盤 ----------------
def test_gate3_pass_consecutive_decline():
    m = _margin_df([("w1", 100.0), ("w2", 90.0), ("w3", 80.0), ("w4", 70.0)])
    g = pf.gate3_margin(m, weeks=3)
    assert g["passed"] is True
    assert g["drop_pct"] == pytest.approx(0.30)


def test_gate3_fail_when_increasing():
    m = _margin_df([("w1", 70.0), ("w2", 80.0), ("w3", 90.0), ("w4", 100.0)])
    g = pf.gate3_margin(m, weeks=3)
    assert g["passed"] is False


def test_gate3_fail_insufficient_history():
    m = _margin_df([("w1", 100.0), ("w2", 90.0)])
    g = pf.gate3_margin(m, weeks=3)
    assert g["passed"] is False


# ---------------- 單檔整合 + 真實個股區隔 ----------------
def test_evaluate_stock_all_three_gates_pass():
    res = pf.evaluate_stock(
        "7922", _filings("バロン", ["2026-04-16", "2026-04-27"]),
        _price_df([("2026-04-16", 700.0), ("2026-04-27", 710.0), ("2026-06-01", 719.0)]),
        _margin_df([("w1", 95.0), ("w2", 52.0), ("w3", 10.0), ("w4", 7.0)]),
        min_filings=2, margin_weeks=3,
    )
    assert res.in_pocket is True
    assert res.gates_passed == 3


def test_two_stocks_distinct_inputs_distinct_results():
    """兩檔不同個股 → 不同真實輸入 → 不同濾網結果（非全市場攤平）。"""
    # A：三關全過
    a = pf.evaluate_stock(
        "AAA", _filings("主力甲", ["2026-04-06", "2026-04-21"]),
        _price_df([("2026-04-06", 1000.0), ("2026-04-21", 1010.0), ("2026-06-01", 1020.0)]),
        _margin_df([("w1", 100.0), ("w2", 90.0), ("w3", 80.0), ("w4", 70.0)]),
    )
    # B：第二盤追高失敗（現價遠高於主力成本）
    b = pf.evaluate_stock(
        "BBB", _filings("主力乙", ["2026-04-06", "2026-04-21"]),
        _price_df([("2026-04-06", 500.0), ("2026-04-21", 510.0), ("2026-06-01", 900.0)]),
        _margin_df([("w1", 100.0), ("w2", 90.0), ("w3", 80.0), ("w4", 70.0)]),
    )
    assert a.gate1["lead_filer"] != b.gate1["lead_filer"]
    assert a.gate2["master_cost"] != b.gate2["master_cost"]
    assert a.in_pocket is True
    assert b.in_pocket is False
    assert b.passed_gate2 is False


# ---------------- 快照 degraded 防呆 ----------------
def test_write_snapshot_guard_rejects_empty_overwrite(tmp_path, monkeypatch):
    """候選=0 的空掃描不可覆寫既有非空快照（避免一鍵清空畫面）。"""
    from api.services import pocket_service as ps
    monkeypatch.setattr(ps, "SCAN_SNAPSHOTS_DIR", tmp_path)

    good = {"funnel": {"candidates": 638, "gate3_margin": 24}, "pocket": [{"code": "7922"}], "near_miss": []}
    ps.write_snapshot(good, date_str="2026-06-07")
    assert ps.latest_snapshot()["funnel"]["candidates"] == 638

    empty = {"funnel": {"candidates": 0, "gate3_margin": 0}, "pocket": [], "near_miss": []}
    ps.write_snapshot(empty, date_str="2026-06-08")  # guard 應拒絕覆寫

    # 既有好快照仍在，且被擋的空結果存成 _rejected_
    assert ps.latest_snapshot()["funnel"]["candidates"] == 638
    assert (tmp_path / "_rejected_pocket_2026-06-08.json").exists()
