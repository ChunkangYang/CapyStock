"""棘輪式移動停損（ledger_service.advance_trade）測試 — IMP-002。

驗收使用者定義（進場 100、N=10%）：
  - 停損線初始 90
  - 收 105 → 停損線升到 94.5（只升不降）
  - 收 95/91（未破過進場高點時）→ 停損線維持 90，不出場
  - 收 89 → 出場（收盤 < 停損線）
"""
from datetime import date

from api.schemas.ledger import Trade
from api.services import ledger_service as ls


def _trade(entry=100.0, n=0.10, entry_date=date(2026, 1, 1)) -> Trade:
    t = Trade(id="t1", code="7203", name="トヨタ", entry_date=entry_date,
              entry_price=entry, shares=100, stop_pct=n)
    return ls.init_trade_stops(t)


def _closes(start_day, prices):
    return [(date(2026, 1, start_day + i), float(p)) for i, p in enumerate(prices)]


def test_init_stops():
    t = _trade()
    assert t.high_water == 100.0
    assert t.stop_line == 90.0


def test_ratchet_moves_up_on_new_high():
    t = _trade()
    ls.advance_trade(t, _closes(2, [105]))
    assert t.high_water == 105.0
    assert t.stop_line == 94.5
    assert t.status == "open"


def test_stop_does_not_move_down_when_below_entry():
    t = _trade()
    # 收 95、91 都未超過進場價 100 → high_water 維持 100、停損維持 90、不出場
    ls.advance_trade(t, _closes(2, [95, 91]))
    assert t.high_water == 100.0
    assert t.stop_line == 90.0
    assert t.status == "open"


def test_exit_when_close_below_stop():
    t = _trade()
    ls.advance_trade(t, _closes(2, [95, 91, 89]))
    assert t.status == "closed"
    assert t.exit_price == 89.0
    assert t.exit_reason == "trailing_stop"
    assert t.pnl_jpy == (89.0 - 100.0) * 100


def test_locked_profit_after_ratchet():
    """漲到 120（停損升到 108，已過進場價＝鎖利），回落到 107 → 出場且獲利。"""
    t = _trade()
    ls.advance_trade(t, _closes(2, [120, 107]))
    assert t.status == "closed"
    assert t.exit_price == 107.0
    assert t.pnl_jpy == (107.0 - 100.0) * 100  # 正獲利
    assert t.pnl_pct == (107.0 - 100.0) / 100.0


def test_no_exit_when_holding_above_stop():
    t = _trade()
    ls.advance_trade(t, _closes(2, [101, 102, 103]))
    assert t.status == "open"
    assert t.high_water == 103.0
    assert t.stop_line == 103.0 * 0.9


def test_advance_is_idempotent_on_same_data():
    t = _trade()
    closes = _closes(2, [105, 103])
    ls.advance_trade(t, closes)
    hw, sl, lad = t.high_water, t.stop_line, t.last_advanced_date
    ls.advance_trade(t, closes)  # 重跑同資料不應再變動
    assert (t.high_water, t.stop_line, t.last_advanced_date) == (hw, sl, lad)
