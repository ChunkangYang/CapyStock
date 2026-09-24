"""海龜投資法每日模擬交易服務：進場選股/加碼觸發/出場優先序/回撤節流。"""
from datetime import date, timedelta

import pytest

from api.schemas.ledger import Ledger, Trade
from api.services import ledger_service as ls
from api.services import turtle_trade_service as tts

TODAY = date(2026, 6, 12)


def _sig(close, n=20.0, dhigh=None, dlow=None, d=TODAY):
    return tts.TurtleSignal(code="", date=d, close=close, n=n,
                            dhigh_entry=dhigh, dlow_exit=dlow)


CFG = tts.TurtleConfig(unit_risk_pct=0.01, stop_n_mult=2.0, pyramid_add_n_mult=0.5,
                       max_units_per_market=4, max_total_units=20,
                       max_new_units_per_day=4, min_price_jpy=50.0,
                       max_price_age_days=5, lot_size=100,
                       reentry_cooldown_days=10)


class TestSelectNewEntries:
    def test_breakout_triggers_and_scores_sorted(self):
        signals = {
            "1111": _sig(1000.0, n=20.0, dhigh=990.0),   # score = 10/20 = 0.5
            "2222": _sig(1000.0, n=10.0, dhigh=950.0),   # score = 50/10 = 5.0 最強
            "3333": _sig(1000.0, n=20.0, dhigh=1000.0),  # 未突破（close<=dhigh）
        }
        candidates, skipped = tts.select_new_entries(
            list(signals), signals, held_codes=set(), cooldown_until={}, today=TODAY, cfg=CFG)
        assert [c["code"] for c in candidates] == ["2222", "1111"]

    def test_held_codes_excluded(self):
        signals = {"1111": _sig(1000.0, n=20.0, dhigh=900.0)}
        candidates, _ = tts.select_new_entries(
            list(signals), signals, held_codes={"1111"}, cooldown_until={}, today=TODAY, cfg=CFG)
        assert candidates == []

    def test_cooldown_blocks_new_entry(self):
        signals = {"1111": _sig(1000.0, n=20.0, dhigh=900.0)}
        candidates, skipped = tts.select_new_entries(
            list(signals), signals, held_codes=set(),
            cooldown_until={"1111": TODAY + timedelta(days=1)}, today=TODAY, cfg=CFG)
        assert candidates == []
        assert "冷卻" in skipped[0]["reason"]

    def test_cooldown_expired_allows_entry(self):
        signals = {"1111": _sig(1000.0, n=20.0, dhigh=900.0)}
        candidates, _ = tts.select_new_entries(
            list(signals), signals, held_codes=set(),
            cooldown_until={"1111": TODAY - timedelta(days=1)}, today=TODAY, cfg=CFG)
        assert [c["code"] for c in candidates] == ["1111"]

    def test_penny_stock_skipped(self):
        signals = {"1111": _sig(30.0, n=1.0, dhigh=20.0)}
        candidates, skipped = tts.select_new_entries(
            list(signals), signals, held_codes=set(), cooldown_until={}, today=TODAY, cfg=CFG)
        assert candidates == []
        assert "股價過低" in skipped[0]["reason"]

    def test_stale_price_skipped(self):
        signals = {"1111": _sig(1000.0, n=20.0, dhigh=900.0, d=TODAY - timedelta(days=30))}
        candidates, skipped = tts.select_new_entries(
            list(signals), signals, held_codes=set(), cooldown_until={}, today=TODAY, cfg=CFG)
        assert candidates == []
        assert "過舊" in skipped[0]["reason"]

    def test_no_signal_is_silently_skipped(self):
        candidates, skipped = tts.select_new_entries(
            ["1111"], {}, held_codes=set(), cooldown_until={}, today=TODAY, cfg=CFG)
        assert candidates == [] and skipped == []


class TestSelectPyramidAdds:
    def _trade(self, unit_index, entry_price, code="1111"):
        t = Trade(id=f"t{unit_index}", code=code, entry_date=TODAY - timedelta(days=5),
                  entry_price=entry_price, shares=100, stop_pct=0.0, status="open",
                  unit_index=unit_index, n_at_fill=20.0)
        return t

    def test_triggers_when_price_up_half_n(self):
        trades = [self._trade(1, 1000.0)]
        positions = {"1111": trades}
        signals = {"1111": _sig(1010.0, n=20.0)}  # +10 = 0.5*20 剛好觸發
        out = tts.select_pyramid_adds(positions, signals, cfg=CFG)
        assert len(out) == 1 and out[0]["unit_index"] == 2

    def test_below_threshold_no_trigger(self):
        trades = [self._trade(1, 1000.0)]
        positions = {"1111": trades}
        signals = {"1111": _sig(1005.0, n=20.0)}
        out = tts.select_pyramid_adds(positions, signals, cfg=CFG)
        assert out == []

    def test_max_units_per_market_blocks_further_adds(self):
        trades = [self._trade(i, 1000.0 + i * 10) for i in range(1, 5)]  # 已 4 unit
        positions = {"1111": trades}
        signals = {"1111": _sig(2000.0, n=20.0)}
        out = tts.select_pyramid_adds(positions, signals, cfg=CFG)
        assert out == []

    def test_uses_latest_unit_as_anchor(self):
        trades = [self._trade(1, 1000.0), self._trade(2, 1010.0)]
        positions = {"1111": trades}
        # 從 unit1(1000) 算已觸發，但錨點應是 unit2(1010)：1010+10=1020 才觸發
        signals = {"1111": _sig(1015.0, n=20.0)}
        out = tts.select_pyramid_adds(positions, signals, cfg=CFG)
        assert out == []
        signals2 = {"1111": _sig(1020.0, n=20.0)}
        out2 = tts.select_pyramid_adds(positions, signals2, cfg=CFG)
        assert len(out2) == 1 and out2[0]["unit_index"] == 3


class TestEvaluateExit:
    def _trades(self, stop_line=900.0):
        return [Trade(id="t1", code="1111", entry_date=TODAY, entry_price=1000.0,
                      shares=100, stop_pct=0.0, status="open", stop_line=stop_line,
                      unit_index=1)]

    def test_stop_takes_priority_over_donchian(self):
        trades = self._trades(stop_line=950.0)
        sig = _sig(900.0, dlow=920.0)  # 兩者都觸發，優先回停損
        assert tts.evaluate_exit(trades, sig) == "turtle_stop"

    def test_donchian_exit_when_stop_not_hit(self):
        trades = self._trades(stop_line=800.0)
        sig = _sig(900.0, dlow=920.0)  # 未破停損，但破 20 日低
        assert tts.evaluate_exit(trades, sig) == "turtle_donchian_exit"

    def test_no_exit_when_above_both(self):
        trades = self._trades(stop_line=800.0)
        sig = _sig(1000.0, dlow=900.0)
        assert tts.evaluate_exit(trades, sig) is None

    def test_no_data_means_no_exit(self):
        trades = self._trades(stop_line=800.0)
        assert tts.evaluate_exit(trades, None) is None


class TestDrawdownThrottle:
    def test_halves_risk_when_drawdown_exceeds_threshold(self):
        throttled, risk = tts.next_risk_pct(
            throttled=False, equity=780_000, peak_equity=1_000_000, cfg=CFG)
        assert throttled is True
        assert risk == pytest.approx(CFG.unit_risk_pct / 2.0)

    def test_stays_normal_within_threshold(self):
        throttled, risk = tts.next_risk_pct(
            throttled=False, equity=850_000, peak_equity=1_000_000, cfg=CFG)
        assert throttled is False
        assert risk == pytest.approx(CFG.unit_risk_pct)

    def test_recovers_only_after_crossing_recover_line(self):
        # 仍在節流中，權益回到 -15%（未到 -10% 門檻）→ 維持節流
        throttled, risk = tts.next_risk_pct(
            throttled=True, equity=850_000, peak_equity=1_000_000, cfg=CFG)
        assert throttled is True
        assert risk == pytest.approx(CFG.unit_risk_pct / 2.0)

    def test_recovers_when_crossing_recover_line(self):
        throttled, risk = tts.next_risk_pct(
            throttled=True, equity=905_000, peak_equity=1_000_000, cfg=CFG)
        assert throttled is False
        assert risk == pytest.approx(CFG.unit_risk_pct)


class TestRunDaily:
    def _ledger(self, trades=None):
        return Ledger(id=config_id(), name="turtle-test", created_at="2026-06-01T00:00:00",
                      owner="bot", initial_cash_jpy=3_000_000, cash_jpy=3_000_000,
                      trades=trades or [])

    def test_new_entry_deducts_cash_and_logs(self, monkeypatch, tmp_path):
        ledger = self._ledger()
        monkeypatch.setattr(ls, "get_or_create_bot_ledger", lambda *a, **k: ledger)
        monkeypatch.setattr(ls, "save_ledger", lambda lg: None)
        monkeypatch.setattr(tts, "DAILY_LOG_DIR", tmp_path)
        monkeypatch.setattr(tts, "make_price_lookup",
                            lambda as_of=None: (lambda code: (TODAY, 1000.0)))

        def provider(code):
            return _sig(1000.0, n=20.0, dhigh=900.0) if code == "1111" else None

        log = tts.run_daily(as_of=TODAY, universe=["1111"], signal_provider=provider, cfg=CFG)

        assert len(log["opened"]) == 1
        assert log["opened"][0]["action"] == "entry"
        assert ledger.trades[0].code == "1111"
        assert ledger.cash_jpy == pytest.approx(3_000_000 - log["opened"][0]["cost_jpy"])
        assert (tmp_path / f"{TODAY.isoformat()}.json").exists()

    def test_stop_exit_priority_over_donchian(self, monkeypatch, tmp_path):
        t = Trade(id="t1", code="1111", entry_date=TODAY - timedelta(days=10),
                  entry_price=1000.0, shares=100, stop_pct=0.0, status="open",
                  stop_line=950.0, unit_index=1, n_at_fill=20.0)
        ledger = self._ledger([t])
        monkeypatch.setattr(ls, "get_or_create_bot_ledger", lambda *a, **k: ledger)
        monkeypatch.setattr(ls, "save_ledger", lambda lg: None)
        monkeypatch.setattr(tts, "DAILY_LOG_DIR", tmp_path)
        monkeypatch.setattr(tts, "make_price_lookup",
                            lambda as_of=None: (lambda code: (TODAY, 900.0)))

        def provider(code):
            return _sig(900.0, n=20.0, dlow=920.0) if code == "1111" else None

        log = tts.run_daily(as_of=TODAY, universe=[], signal_provider=provider, cfg=CFG)
        assert len(log["closed"]) == 1
        assert log["closed"][0]["exit_reason"] == "turtle_stop"
        assert ledger.trades[0].status == "closed"

    def test_drawdown_throttle_halves_new_unit_size(self, monkeypatch, tmp_path):
        # 起始資金 3,000,000，權益已跌到 2,000,000（<=80% 觸發節流）
        ledger = self._ledger()
        ledger.cash_jpy = 2_000_000
        monkeypatch.setattr(ls, "get_or_create_bot_ledger", lambda *a, **k: ledger)
        monkeypatch.setattr(ls, "save_ledger", lambda lg: None)
        monkeypatch.setattr(tts, "DAILY_LOG_DIR", tmp_path)
        monkeypatch.setattr(tts, "make_price_lookup",
                            lambda as_of=None: (lambda code: (TODAY, 1000.0)))

        def provider(code):
            return _sig(1000.0, n=20.0, dhigh=900.0) if code == "1111" else None

        log = tts.run_daily(as_of=TODAY, universe=["1111"], signal_provider=provider, cfg=CFG)
        assert log["throttled"] is True
        # 節流：risk 減半 → floor(2,000,000*0.005/20)=500 股（未節流時應為 1000 股）
        assert log["opened"][0]["shares"] == 500


def config_id():
    from capystock import config
    return config.TURTLE_LEDGER_ID
