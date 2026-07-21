"""自動模擬交易：選股規則 / 每日執行 / 資金曲線 / bot 帳本隔離。"""
from datetime import date

import pytest

from api.schemas.ledger import Ledger, Trade
from api.services import auto_trade_service as ats
from api.services import ledger_service as ls


def _row(code, drop=0.5, premium=0.0, name="X"):
    return {
        "code": code, "name": name, "in_pocket": True, "gates_passed": 3,
        "gate1": {"passed": True, "lead_filer": "某某", "filing_count": 2},
        "gate2": {"passed": True, "master_cost": 1000.0, "latest_price": 1000.0,
                  "premium_pct": premium},
        "gate3": {"passed": True, "weeks": 3, "drop_pct": drop},
    }


def _lookup(prices: dict, px_date=date(2026, 6, 12)):
    return lambda code: (px_date, prices[code]) if code in prices else None


CFG = ats.AutoTradeConfig(position_jpy=300_000, max_open=10, max_new_per_day=3,
                          stop_pct=0.1, lot_size=100, fee_bps=0.0, slippage_bps=0.0,
                          max_price_age_days=5, min_premium_pct=-0.5, min_price_jpy=50.0)
TODAY = date(2026, 6, 12)


class TestSelectNewTrades:
    def test_sorted_by_drop_pct_and_capped_per_day(self):
        rows = [_row("1111", drop=0.1), _row("2222", drop=0.9), _row("3333", drop=0.5),
                _row("4444", drop=0.3)]
        picks, skipped = ats.select_new_trades(
            rows, open_codes=set(), cash=10_000_000, open_count=0, today=TODAY,
            price_lookup=_lookup({"1111": 1000.0, "2222": 1000.0, "3333": 1000.0, "4444": 1000.0}),
            cfg=CFG)
        assert [p["code"] for p in picks] == ["2222", "3333", "4444"]  # drop 大→小，取 3 檔
        assert any(s["code"] == "1111" and "額度" in s["reason"] for s in skipped)

    def test_lot_rounding_and_position_size(self):
        picks, _ = ats.select_new_trades(
            [_row("7922")], open_codes=set(), cash=10_000_000, open_count=0, today=TODAY,
            price_lookup=_lookup({"7922": 718.0}), cfg=CFG)
        # floor(300000 / 718 / 100) * 100 = 400 股
        assert picks[0]["shares"] == 400
        assert picks[0]["cost_jpy"] == pytest.approx(718.0 * 400)

    def test_skip_already_held(self):
        picks, skipped = ats.select_new_trades(
            [_row("1111")], open_codes={"1111"}, cash=10_000_000, open_count=1, today=TODAY,
            price_lookup=_lookup({"1111": 1000.0}), cfg=CFG)
        assert picks == []
        assert skipped[0]["reason"] == "已持有同一檔"

    def test_skip_stale_price(self):
        picks, skipped = ats.select_new_trades(
            [_row("1111")], open_codes=set(), cash=10_000_000, open_count=0, today=TODAY,
            price_lookup=_lookup({"1111": 1000.0}, px_date=date(2026, 5, 1)), cfg=CFG)
        assert picks == []
        assert "過舊" in skipped[0]["reason"]

    def test_skip_penny_and_broken_premium(self):
        picks, skipped = ats.select_new_trades(
            [_row("1111"), _row("2222", premium=-0.89)],
            open_codes=set(), cash=10_000_000, open_count=0, today=TODAY,
            price_lookup=_lookup({"1111": 13.0, "2222": 1000.0}), cfg=CFG)
        assert picks == []
        reasons = {s["code"]: s["reason"] for s in skipped}
        assert "股價過低" in reasons["1111"]
        assert "折價異常" in reasons["2222"]

    def test_cash_and_max_open_limits(self):
        rows = [_row("1111", drop=0.9), _row("2222", drop=0.8)]
        picks, skipped = ats.select_new_trades(
            rows, open_codes=set(), cash=250_000, open_count=0, today=TODAY,
            price_lookup=_lookup({"1111": 1000.0, "2222": 1000.0}), cfg=CFG)
        # 剩餘現金 < 每筆金額 → 買得起多少買多少（250,000 → 200 股），第二檔沒錢了
        assert [p["code"] for p in picks] == ["1111"]
        assert picks[0]["shares"] == 200
        assert "現金不足" in skipped[0]["reason"]

        cfg_full = ats.AutoTradeConfig(max_open=1, max_new_per_day=3)
        picks2, skipped2 = ats.select_new_trades(
            rows, open_codes={"9999"}, cash=10_000_000, open_count=1, today=TODAY,
            price_lookup=_lookup({"1111": 1000.0, "2222": 1000.0}), cfg=cfg_full)
        assert picks2 == []
        assert all("額度" in s["reason"] for s in skipped2)

    def test_reentry_cooldown_after_stop_out(self):
        rows = [_row("1111")]
        args = dict(open_codes=set(), cash=10_000_000, open_count=0,
                    price_lookup=_lookup({"1111": 1000.0}), cfg=CFG)
        # 出場後 5 天 → 冷卻中（門檻 20 天）
        picks, skipped = ats.select_new_trades(
            rows, today=TODAY, last_exit={"1111": date(2026, 6, 7)}, **args)
        assert picks == []
        assert "冷卻" in skipped[0]["reason"]
        # 出場後 25 天 → 可再進場
        picks2, _ = ats.select_new_trades(
            rows, today=TODAY, last_exit={"1111": date(2026, 5, 15)}, **args)
        assert [p["code"] for p in picks2] == ["1111"]

    def test_no_price_data(self):
        picks, skipped = ats.select_new_trades(
            [_row("1111")], open_codes=set(), cash=10_000_000, open_count=0, today=TODAY,
            price_lookup=_lookup({}), cfg=CFG)
        assert picks == []
        assert skipped[0]["reason"] == "無收盤價資料"


class TestRunDaily:
    def _bot_ledger(self, trades=None):
        return Ledger(id="auto-pocket", name="bot", created_at="2026-06-01T00:00:00",
                      owner="bot", initial_cash_jpy=1_000_000, cash_jpy=1_000_000,
                      trades=trades or [])

    def test_entry_deducts_cash_and_writes_log(self, monkeypatch, tmp_path):
        ledger = self._bot_ledger()
        saved = {}
        monkeypatch.setattr(ls, "get_or_create_bot_ledger", lambda: ledger)
        monkeypatch.setattr(ls, "save_ledger", lambda lg: saved.update({"lg": lg}))
        monkeypatch.setattr(ls, "closes_for", lambda code, days=400: [(TODAY, 1000.0)])
        monkeypatch.setattr(ats, "DAILY_LOG_DIR", tmp_path)

        log = ats.run_daily(as_of=TODAY, pocket_result={"pocket": [_row("1111")]}, cfg=CFG)

        assert len(log["opened"]) == 1
        assert ledger.trades[0].code == "1111"
        assert ledger.trades[0].shares == 300          # 300000/1000 = 300 股
        assert ledger.cash_jpy == pytest.approx(1_000_000 - 300_000)
        assert saved["lg"] is ledger
        assert (tmp_path / f"{TODAY.isoformat()}.json").exists()
        assert log["equity_jpy"] == pytest.approx(1_000_000)   # 進場當下權益不變

    def test_stop_loss_exit_returns_cash(self, monkeypatch, tmp_path):
        t = Trade(id="t1", code="1111", name="X", entry_date=date(2026, 6, 1),
                  entry_price=1000.0, shares=300, stop_pct=0.1)
        ls.init_trade_stops(t)
        ledger = self._bot_ledger([t])
        ledger.cash_jpy = 700_000.0
        monkeypatch.setattr(ls, "get_or_create_bot_ledger", lambda: ledger)
        monkeypatch.setattr(ls, "save_ledger", lambda lg: None)
        monkeypatch.setattr(ls, "closes_for",
                            lambda code, days=400: [(date(2026, 6, 10), 850.0)])
        monkeypatch.setattr(ats, "DAILY_LOG_DIR", tmp_path)

        log = ats.run_daily(as_of=TODAY, pocket_result={"pocket": []}, cfg=CFG)

        assert len(log["closed"]) == 1
        assert log["closed"][0]["exit_reason"] == "trailing_stop"
        assert ledger.trades[0].status == "closed"
        assert ledger.cash_jpy == pytest.approx(700_000 + 850.0 * 300)
        assert log["realized_pnl_jpy"] == pytest.approx((850.0 - 1000.0) * 300)

    def test_dry_run_writes_nothing(self, monkeypatch, tmp_path):
        ledger = self._bot_ledger()
        calls = []
        monkeypatch.setattr(ls, "get_or_create_bot_ledger", lambda: ledger)
        monkeypatch.setattr(ls, "save_ledger", lambda lg: calls.append(lg))
        monkeypatch.setattr(ls, "closes_for", lambda code, days=400: [(TODAY, 1000.0)])
        monkeypatch.setattr(ats, "DAILY_LOG_DIR", tmp_path)

        log = ats.run_daily(as_of=TODAY, pocket_result={"pocket": [_row("1111")]},
                            dry_run=True, cfg=CFG)
        assert log["opened"]
        assert calls == []
        assert list(tmp_path.glob("*.json")) == []


class TestEquityCurve:
    def test_curve_reflects_entry_and_exit(self, monkeypatch):
        t = Trade(id="t1", code="1111", name="X", entry_date=date(2026, 6, 1),
                  entry_price=1000.0, shares=100, stop_pct=0.1, status="closed",
                  exit_date=date(2026, 6, 3), exit_price=1200.0, pnl_jpy=20_000.0)
        ledger = Ledger(id="auto-pocket", name="bot", created_at="2026-06-01T00:00:00",
                        owner="bot", initial_cash_jpy=1_000_000, cash_jpy=1_020_000, trades=[t])
        monkeypatch.setattr(ats, "_closes_map", lambda code, days=420: {
            date(2026, 6, 1): 1000.0, date(2026, 6, 2): 1100.0, date(2026, 6, 3): 1200.0})

        c = ats.build_equity_curve(ledger, end=date(2026, 6, 4))
        assert c["dates"] == ["2026-06-01", "2026-06-02", "2026-06-03", "2026-06-04"]
        assert c["equity"] == [1_000_000, 1_010_000, 1_020_000, 1_020_000]
        assert c["cash"][0] == 900_000            # 進場後現金 -10 萬
        assert c["cash"][-1] == 1_020_000         # 出場後回到現金

    def test_empty_ledger(self, monkeypatch):
        ledger = Ledger(id="auto-pocket", name="bot", created_at="x", owner="bot",
                        initial_cash_jpy=1_000_000, cash_jpy=1_000_000, trades=[])
        c = ats.build_equity_curve(ledger, end=date(2026, 6, 4))
        assert c["dates"] == [] and c["equity"] == []


class TestBotLedgerIsolation:
    def test_advance_all_skips_bot_ledger(self, monkeypatch):
        from api.schemas.ledger import LedgerSummary
        summaries = [
            LedgerSummary(id="u1", name="user", created_at="x", owner="user", trade_count=0,
                          open_count=0, closed_count=0, realized_pnl_jpy=0, unrealized_pnl_jpy=0),
            LedgerSummary(id="auto-pocket", name="bot", created_at="x", owner="bot", trade_count=0,
                          open_count=0, closed_count=0, realized_pnl_jpy=0, unrealized_pnl_jpy=0),
        ]
        loaded = []
        monkeypatch.setattr(ls, "list_ledgers", lambda: summaries)
        monkeypatch.setattr(ls, "_load_ledger", lambda lid: loaded.append(lid))

        ls.advance_all()
        assert loaded == ["u1"]

        loaded.clear()
        ls.advance_all(include_bot=True)
        assert loaded == ["u1", "auto-pocket"]
