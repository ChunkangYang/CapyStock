"""海龜投資法核心計算函式單測：TR / N / Donchian / unit sizing / pyramid / stop。"""
import pytest

from capystock import turtle as tt


class TestTrueRange:
    def test_no_gap_uses_high_low_range(self):
        assert tt.true_range(110, 100, 105) == 10

    def test_gap_up_uses_high_minus_prev_close(self):
        # 前收 90，今高 110、今低 105 → |110-90|=20 最大
        assert tt.true_range(110, 105, 90) == 20

    def test_gap_down_uses_prev_close_minus_low(self):
        # 前收 130，今高 115、今低 110 → |110-130|=20 最大
        assert tt.true_range(115, 110, 130) == 20

    def test_first_bar_has_no_prev_close(self):
        assert tt.true_range(110, 100, None) == 10


class TestNValue:
    def test_simple_average_of_last_period(self):
        trs = [10.0] * 19 + [30.0]  # 20 筆，最後一筆特別大
        n = tt.n_value(trs, period=20)
        assert n == pytest.approx((10.0 * 19 + 30.0) / 20)

    def test_insufficient_data_returns_none(self):
        assert tt.n_value([1.0, 2.0, 3.0], period=20) is None

    def test_uses_only_last_period_window(self):
        trs = [100.0] * 5 + [10.0] * 20  # 前面的大值超出窗口不應影響
        assert tt.n_value(trs, period=20) == pytest.approx(10.0)


class TestDonchian:
    def test_high_excludes_current_day_by_construction(self):
        # 呼叫端只傳「不含當日」的收盤，函式單純取最大值
        closes_before_today = [100, 105, 110, 108, 103]
        assert tt.donchian_high(closes_before_today, window=5) == 110

    def test_low(self):
        closes_before_today = [100, 105, 110, 108, 103]
        assert tt.donchian_low(closes_before_today, window=5) == 100

    def test_insufficient_data_returns_none(self):
        assert tt.donchian_high([100, 105], window=55) is None
        assert tt.donchian_low([100, 105], window=20) is None

    def test_uses_only_last_window(self):
        closes = [1000] + [100, 105, 110, 108, 103]  # 5 日窗口，最舊的 1000 應被排除
        assert tt.donchian_high(closes, window=5) == 110


class TestUnitSize:
    def test_lot_rounding(self):
        # equity=3,000,000 × 1% / N=50 = 600 股理論值，lot=100 → 600（剛好整除）
        shares = tt.unit_size(3_000_000, 50, unit_risk_pct=0.01, lot_size=100)
        assert shares == 600

    def test_rounds_down_to_lot(self):
        # 3,000,000*0.01/70 = 428.57 → floor to 400
        shares = tt.unit_size(3_000_000, 70, unit_risk_pct=0.01, lot_size=100)
        assert shares == 400

    def test_zero_when_less_than_one_lot(self):
        shares = tt.unit_size(100_000, 1000, unit_risk_pct=0.01, lot_size=100)
        assert shares == 0

    def test_zero_n_or_equity_is_safe(self):
        assert tt.unit_size(3_000_000, 0, unit_risk_pct=0.01, lot_size=100) == 0
        assert tt.unit_size(0, 50, unit_risk_pct=0.01, lot_size=100) == 0

    def test_cash_constraint_caps_shares(self):
        # 理論 600 股 @ price=1000 需要 60 萬現金，但只剩 20 萬現金 → 上限 200 股
        shares = tt.unit_size(3_000_000, 50, unit_risk_pct=0.01, lot_size=100,
                              price=1000.0, cash=200_000.0)
        assert shares == 200

    def test_cash_not_binding_when_sufficient(self):
        shares = tt.unit_size(3_000_000, 50, unit_risk_pct=0.01, lot_size=100,
                              price=1000.0, cash=10_000_000.0)
        assert shares == 600


class TestPyramidTrigger:
    def test_triggers_at_exact_threshold(self):
        # 最近進場價 1000，N=20，0.5N=10 → 1010 觸發
        assert tt.pyramid_trigger(1010.0, 1000.0, 20.0, add_n_mult=0.5) is True

    def test_just_below_threshold_does_not_trigger(self):
        assert tt.pyramid_trigger(1009.99, 1000.0, 20.0, add_n_mult=0.5) is False

    def test_far_above_still_only_one_trigger_flag(self):
        # 函式本身只回布林值；「當天只加一次」的節流邏輯在呼叫端（service/backtest）
        assert tt.pyramid_trigger(1200.0, 1000.0, 20.0, add_n_mult=0.5) is True

    def test_zero_n_never_triggers(self):
        assert tt.pyramid_trigger(2000.0, 1000.0, 0, add_n_mult=0.5) is False


class TestStopLine:
    def test_stop_is_price_minus_two_n(self):
        assert tt.stop_line_for_unit(1000.0, 50.0, stop_n_mult=2.0) == 900.0

    def test_default_mult_is_two(self):
        assert tt.stop_line_for_unit(1000.0, 50.0) == 900.0


class TestTightenStop:
    def test_first_entry_has_no_prior_stop(self):
        assert tt.tighten_stop(None, 900.0) == 900.0

    def test_only_moves_up_never_down(self):
        # 加碼後新算出來的停損線比舊的低 → 維持舊的（只升不降）
        assert tt.tighten_stop(950.0, 900.0) == 950.0

    def test_moves_up_when_candidate_higher(self):
        assert tt.tighten_stop(900.0, 980.0) == 980.0
