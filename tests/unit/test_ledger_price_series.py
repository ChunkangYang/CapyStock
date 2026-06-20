"""帳本單筆交易：進場日 → 今天的日曆軸收盤序列（缺資料留 None）測試。"""
from datetime import date

from api.schemas.ledger import Trade
from api.services import ledger_service as ls


def _open_trade(entry_date=date(2026, 6, 1)) -> Trade:
    t = Trade(id="t1", code="7203", name="トヨタ", entry_date=entry_date,
              entry_price=100.0, shares=100, stop_pct=0.1)
    return ls.init_trade_stops(t)


def test_calendar_axis_blanks_missing_days(monkeypatch):
    """只有 6/1、6/3 有收盤 → 6/2（未同步/週末）留 None，前端折線留白。"""
    t = _open_trade()
    monkeypatch.setattr(
        ls, "_closes_for",
        lambda code, days=400: [(date(2026, 6, 1), 100.0), (date(2026, 6, 3), 110.0)],
    )
    s = ls.build_trade_price_series(t, today=date(2026, 6, 3))
    assert s["dates"] == ["2026-06-01", "2026-06-02", "2026-06-03"]
    assert s["closes"] == [100.0, None, 110.0]
    assert s["entry_date"] == "2026-06-01"
    assert s["end_date"] == "2026-06-03"
    assert s["entry_price"] == 100.0
    assert s["stop_line"] == 90.0


def test_series_ends_at_exit_date_not_today(monkeypatch):
    """已出場的交易：軸到出場日為止，不延伸到今天。"""
    t = _open_trade()
    t.status = "closed"
    t.exit_date = date(2026, 6, 2)
    t.exit_price = 90.0
    monkeypatch.setattr(
        ls, "_closes_for",
        lambda code, days=400: [
            (date(2026, 6, 1), 100.0), (date(2026, 6, 2), 90.0), (date(2026, 6, 5), 95.0),
        ],
    )
    s = ls.build_trade_price_series(t, today=date(2026, 6, 10))
    assert s["dates"][-1] == "2026-06-02"
    assert s["exit_date"] == "2026-06-02"
    assert s["exit_price"] == 90.0


def test_trade_price_series_missing_returns_none(monkeypatch, tmp_path):
    """帳本/交易不存在 → None（router 轉 404）。"""
    monkeypatch.setattr(ls, "LEDGERS_DIR", tmp_path / "ledgers")
    assert ls.trade_price_series("nope", "nope") is None
