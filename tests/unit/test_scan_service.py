import csv
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from api.schemas.common import Alert, SignalConditions, SignalResult
from api.schemas.scan import DividendScanRow, SignalScanRow
from api.services import scan_service


@pytest.fixture
def mock_signal_result():
    """模擬 signal 分析結果"""
    return SignalResult(
        code="7203",
        name="トヨタ自動車",
        latest_price=2500.0,
        latest_date=date(2026, 4, 25),
        start_price=2400.0,
        price_vs_start_pct=0.04167,
        price_vs_recent_low_pct=0.05,
        conditions=SignalConditions(cond_inst_sell=False, cond_margin_surge=False, cond_price_rise=True, matched=1),
        stop_loss_triggered=False,
        accumulation_signal=True,
        flow_recent=[100, 150, 200],
        margin_trend_note="無資料",
        notes=["吃貨訊號成立"],
        alerts=[Alert(alert_type="accumulation", severity="info", message="test", details={})],
    )


@pytest.fixture
def mock_fundamental_report():
    """模擬基本面報告"""
    from api.schemas.common import FundamentalMetric, FundamentalReport

    return FundamentalReport(
        code="7203",
        name="トヨタ自動車",
        overall="HEALTHY",
        metrics=[
            FundamentalMetric(metric="Sales", score="PASS", note="Good"),
            FundamentalMetric(metric="EPS", score="PASS", note="Good"),
            FundamentalMetric(metric="OpMargin", score="WARN", note="Moderate"),
            FundamentalMetric(metric="Equity Ratio", score="PASS", note="Good"),
            FundamentalMetric(metric="OpCF", score="PASS", note="Good"),
            FundamentalMetric(metric="Cash", score="WARN", note="Fair"),
            FundamentalMetric(metric="DPS", score="PASS", note="Good"),
            FundamentalMetric(metric="Payout Ratio", score="WARN", note="Moderate"),
        ],
    )


def test_run_signals_scan_basic(mock_signal_result, mock_fundamental_report):
    """確定性測試：signals scan 產生正確數量的行數"""
    universe = [
        {"code": "7203", "name": "トヨタ", "market": "Prime"},
        {"code": "6758", "name": "ソニー", "market": "Prime"},
    ]

    with patch("api.services.scan_service.analyze_one") as mock_analyze, patch(
        "api.services.scan_service.get_edinet_events"
    ) as mock_edinet:
        mock_analyze.return_value = mock_signal_result
        mock_edinet.return_value = []

        rows, errors = scan_service.run_signals_scan(universe, clock=date(2026, 4, 25))

        assert len(rows) == 2
        assert len(errors) == 0
        assert rows[0].code == "7203"
        assert rows[0].has_accumulation is True
        assert isinstance(rows[0], SignalScanRow)


def test_run_signals_scan_with_edinet():
    """驗證 EDINET 事件計數"""
    universe = [{"code": "7203", "name": "トヨタ", "market": "Prime"}]

    mock_result = SignalResult(
        code="7203",
        name="トヨタ自動車",
        latest_price=2500.0,
        latest_date=date(2026, 4, 25),
        start_price=None,
        price_vs_start_pct=None,
        price_vs_recent_low_pct=None,
        conditions=SignalConditions(cond_inst_sell=False, cond_margin_surge=False, cond_price_rise=False, matched=0),
        stop_loss_triggered=False,
        accumulation_signal=False,
        flow_recent=[],
        margin_trend_note="無資料",
        notes=[],
        alerts=[],
    )

    with patch("api.services.scan_service.analyze_one") as mock_analyze, patch(
        "api.services.scan_service.get_edinet_events"
    ) as mock_edinet:
        mock_analyze.return_value = mock_result
        mock_edinet.return_value = [
            {"sec_code": "7203", "doc_type_code": "350"},
            {"sec_code": "7203", "doc_type_code": "350"},
        ]

        rows, errors = scan_service.run_signals_scan(universe)

        assert len(rows) == 1
        assert rows[0].edinet_recent_count == 2


def test_run_signals_scan_error_tolerance():
    """失敗容忍測試：一檔失敗，其他仍寫入"""
    universe = [
        {"code": "7203", "name": "トヨタ", "market": "Prime"},
        {"code": "ERR", "name": "Bad", "market": "Prime"},
        {"code": "6758", "name": "ソニー", "market": "Prime"},
    ]

    mock_result = SignalResult(
        code="7203",
        name="トヨタ自動車",
        latest_price=2500.0,
        latest_date=date(2026, 4, 25),
        start_price=None,
        price_vs_start_pct=None,
        price_vs_recent_low_pct=None,
        conditions=SignalConditions(cond_inst_sell=False, cond_margin_surge=False, cond_price_rise=False, matched=0),
        stop_loss_triggered=False,
        accumulation_signal=False,
        flow_recent=[],
        margin_trend_note="無資料",
        notes=[],
        alerts=[],
    )

    def side_effect(code, *args, **kwargs):
        if code == "ERR":
            raise ValueError("Test error")
        return mock_result

    with patch("api.services.scan_service.analyze_one") as mock_analyze, patch(
        "api.services.scan_service.get_edinet_events"
    ) as mock_edinet:
        mock_analyze.side_effect = side_effect
        mock_edinet.return_value = []

        rows, errors = scan_service.run_signals_scan(universe)

        assert len(rows) == 2
        assert len(errors) == 1
        assert errors[0]["code"] == "ERR"


def test_write_and_load_snapshot(tmp_path):
    """確定性測試：寫入與讀取 parquet"""
    with patch("api.services.scan_service.SCAN_SNAPSHOTS_DIR", tmp_path):
        rows = [
            SignalScanRow(
                code="7203",
                name="トヨタ",
                latest_price=2500.0,
                has_accumulation=True,
                has_exit=False,
                has_stop_loss=False,
                edinet_recent_count=0,
                score=3,
                generated_at=date(2026, 4, 25).isoformat(),
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
                generated_at=date(2026, 4, 25).isoformat(),
            ),
        ]

        path = scan_service.write_snapshot("signals", rows, "2026-04-25")
        assert path.exists()

        df = scan_service.load_latest_snapshot("signals", "2026-04-25")
        assert len(df) == 2
        assert df.iloc[0]["score"] == 3
        assert df.iloc[1]["score"] == -2


def test_overwrite_snapshot(tmp_path):
    """覆寫測試：同日兩次，parquet 不重複"""
    with patch("api.services.scan_service.SCAN_SNAPSHOTS_DIR", tmp_path):
        rows1 = [
            SignalScanRow(
                code="7203",
                name="トヨタ",
                latest_price=2500.0,
                has_accumulation=True,
                has_exit=False,
                has_stop_loss=False,
                edinet_recent_count=0,
                score=3,
                generated_at=date(2026, 4, 25).isoformat(),
            )
        ]

        rows2 = [
            SignalScanRow(
                code="7203",
                name="トヨタ",
                latest_price=2600.0,
                has_accumulation=True,
                has_exit=False,
                has_stop_loss=False,
                edinet_recent_count=0,
                score=3,
                generated_at=date(2026, 4, 25).isoformat(),
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
                generated_at=date(2026, 4, 25).isoformat(),
            ),
        ]

        scan_service.write_snapshot("signals", rows1, "2026-04-25")
        scan_service.write_snapshot("signals", rows2, "2026-04-25")

        df = scan_service.load_latest_snapshot("signals", "2026-04-25")
        assert len(df) == 2  # 第二次覆寫為 2 筆


def test_write_errors(tmp_path):
    """測試寫入失敗紀錄"""
    with patch("api.services.scan_service.SCAN_SNAPSHOTS_DIR", tmp_path):
        errors = [
            {"code": "ERR1", "name": "Bad1", "error": "Network error"},
            {"code": "ERR2", "name": "Bad2", "error": "Timeout"},
        ]

        scan_service.write_errors("signals", errors, "2026-04-25")

        error_file = tmp_path / "_errors_signals_2026-04-25.csv"
        assert error_file.exists()

        with open(error_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 2
            assert rows[0]["code"] == "ERR1"


def test_list_snapshots(tmp_path):
    """測試列出所有快照"""
    with patch("api.services.scan_service.SCAN_SNAPSHOTS_DIR", tmp_path):
        rows = [
            SignalScanRow(
                code="7203",
                name="トヨタ",
                latest_price=2500.0,
                has_accumulation=True,
                has_exit=False,
                has_stop_loss=False,
                edinet_recent_count=0,
                score=3,
                generated_at=date(2026, 4, 25).isoformat(),
            )
        ]

        scan_service.write_snapshot("signals", rows, "2026-04-25")
        scan_service.write_snapshot("signals", rows, "2026-04-24")

        snapshots = scan_service.list_snapshots("signals")
        assert len(snapshots) == 2
        assert snapshots[0]["date"] == "2026-04-25"  # 最新的優先


def test_run_dividend_scan_basic(mock_signal_result, mock_fundamental_report):
    """確定性測試：dividend scan 產生正確數量的行數"""
    universe = [
        {"code": "7203", "name": "トヨタ", "market": "Prime"},
        {"code": "6758", "name": "ソニー", "market": "Prime"},
    ]

    with patch("api.services.scan_service.analyze_one") as mock_analyze, patch(
        "api.services.scan_service.get_fundamental_report"
    ) as mock_report:
        mock_analyze.return_value = mock_signal_result
        mock_report.return_value = mock_fundamental_report

        rows, errors = scan_service.run_dividend_scan(universe, clock=date(2026, 4, 25))

        assert len(rows) == 2
        assert len(errors) == 0
        assert rows[0].code == "7203"
        assert rows[0].overall == "HEALTHY"
        assert isinstance(rows[0], DividendScanRow)


def test_run_dividend_scan_no_report():
    """基本面報告不存在時的容忍"""
    universe = [{"code": "7203", "name": "トヨタ", "market": "Prime"}]

    mock_result = SignalResult(
        code="7203",
        name="トヨタ自動車",
        latest_price=2500.0,
        latest_date=date(2026, 4, 25),
        start_price=None,
        price_vs_start_pct=None,
        price_vs_recent_low_pct=None,
        conditions=SignalConditions(cond_inst_sell=False, cond_margin_surge=False, cond_price_rise=False, matched=0),
        stop_loss_triggered=False,
        accumulation_signal=False,
        flow_recent=[],
        margin_trend_note="無資料",
        notes=[],
        alerts=[],
    )

    with patch("api.services.scan_service.analyze_one") as mock_analyze, patch(
        "api.services.scan_service.get_fundamental_report"
    ) as mock_report:
        mock_analyze.return_value = mock_result
        mock_report.return_value = None  # 無基本面報告

        rows, errors = scan_service.run_dividend_scan(universe)

        assert len(rows) == 0
        assert len(errors) == 1
        assert "No fundamental report" in errors[0]["error"]


def test_run_dividend_scan_yield_calculation():
    """驗證殖利率計算"""
    from api.schemas.common import FundamentalMetric, FundamentalReport

    universe = [{"code": "7203", "name": "トヨタ", "market": "Prime"}]

    mock_result = SignalResult(
        code="7203",
        name="トヨタ自動車",
        latest_price=1000.0,  # 1000 JPY
        latest_date=date(2026, 4, 25),
        start_price=None,
        price_vs_start_pct=None,
        price_vs_recent_low_pct=None,
        conditions=SignalConditions(cond_inst_sell=False, cond_margin_surge=False, cond_price_rise=False, matched=0),
        stop_loss_triggered=False,
        accumulation_signal=False,
        flow_recent=[],
        margin_trend_note="無資料",
        notes=[],
        alerts=[],
    )

    report = FundamentalReport(
        code="7203",
        name="トヨタ自動車",
        overall="HEALTHY",
        metrics=[
            FundamentalMetric(metric="DPS", score="PASS", note="Good dividend"),
            FundamentalMetric(metric="Sales", score="PASS", note="Good"),
        ],
    )

    with patch("api.services.scan_service.analyze_one") as mock_analyze, patch(
        "api.services.scan_service.get_fundamental_report"
    ) as mock_report:
        mock_analyze.return_value = mock_result
        mock_report.return_value = report

        rows, errors = scan_service.run_dividend_scan(universe)

        assert len(rows) == 1
        assert rows[0].code == "7203"
        assert rows[0].pass_count == 2
