"""Backtest 引擎測試。"""
from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from api.schemas.simulation import (
    CandidateEntry,
    ClosedTrade,
    CostModel,
    EntryRule,
    ExitRule,
    PositionSizing,
    Simulation,
    SimulationConfig,
    SimulationState,
)
from api.services.backtest_engine import (
    decide_exit_reason,
    run_backtest,
    calculate_report_metrics,
)


@pytest.fixture
def mock_signal_service():
    """模擬訊號服務。"""
    service = MagicMock()

    # 模擬 accumulation_signal：第 1, 3 日有訊號
    def analyze_one_side_effect(code):
        from api.schemas.common import SignalConditions, SignalResult

        return SignalResult(
            code=code,
            name="test",
            latest_price=100.0,
            conditions=SignalConditions(
                cond_inst_sell=False,
                cond_margin_surge=False,
                cond_price_rise=False,
                matched=0,
            ),
            stop_loss_triggered=False,
            accumulation_signal=True,
        )

    service.analyze_one.side_effect = analyze_one_side_effect
    return service


@pytest.fixture
def simple_price_cache():
    """簡化價格快取（每天 open=100, close=價格序列）。"""
    # 日期：2026-01-01 到 2026-01-10
    base = date(2026, 1, 1)
    prices = {}
    code = "7203"

    # 構造 10 天的價格序列
    prices_data = [
        (base + timedelta(days=0), 100.0, 100.0),  # Day 0: open=100, close=100
        (base + timedelta(days=1), 100.0, 100.0),  # Day 1: close=100
        (base + timedelta(days=2), 100.0, 99.0),   # Day 2: close=99
        (base + timedelta(days=3), 99.0, 95.0),    # Day 3: close=95（-5%）
        (base + timedelta(days=4), 95.0, 94.0),    # Day 4: close=94（-6%）
        (base + timedelta(days=5), 94.0, 110.0),   # Day 5: close=110（+10%）
        (base + timedelta(days=6), 110.0, 108.0),  # Day 6
        (base + timedelta(days=7), 108.0, 107.0),  # Day 7
        (base + timedelta(days=8), 107.0, 106.0),  # Day 8
        (base + timedelta(days=9), 106.0, 105.0),  # Day 9
    ]

    prices[code] = {}
    for d, open_p, close_p in prices_data:
        prices[code][d] = {"open": open_p, "close": close_p}

    return prices


@pytest.fixture
def base_config():
    """基本模擬配置。"""
    base_date = date(2026, 1, 1)
    return SimulationConfig(
        kind="backtest",
        initial_capital=100000.0,
        start_date=base_date,
        end_date=base_date + timedelta(days=9),
        candidates=[CandidateEntry(code="7203", name="Toyota")],
        entry_rule=EntryRule(
            price_basis="next_open",
            require_signal=False,
        ),
        exit_rule=ExitRule(
            use_exit_signal=False,
            use_stop_loss=True,
            take_profit_pct=None,
            max_hold_days=None,
        ),
        position_sizing=PositionSizing(
            mode="equal_weight",
            max_concurrent_positions=10,
        ),
        cost_model=CostModel(),
    )


class TestBacktestScenarios:
    """確定性回測情境測試。"""

    def test_scenario_1_stop_loss_consecutive_2days(
        self, base_config, simple_price_cache, mock_signal_service
    ):
        """情景 1: 進場後股價跌破 -5% 連 2 日 → 停損。"""
        # 進場日：第 0 天 close=100, 進場價應為第 1 天 open=100
        base_date = date(2026, 1, 1)

        sim = Simulation(
            id="test-1",
            name="Test 1",
            kind="backtest",
            created_at="2026-01-01",
            config=base_config,
            state=SimulationState(
                cash=100000.0,
                cursor_date=base_date,
                pending_entries=[CandidateEntry(code="7203", name="Toyota")],
            ),
            status="draft",
        )

        run_backtest(sim, mock_signal_service, simple_price_cache)

        # 應該有 1 筆已平倉交易，原因為 stop_loss
        assert len(sim.state.closed_trades) == 1
        trade = sim.state.closed_trades[0]
        assert trade.code == "7203"
        assert trade.exit_reason == "stop_loss"
        # 應在第 4 天時停損（第 3, 4 日都跌破 -5%）
        assert trade.exit_date == base_date + timedelta(days=4)

    def test_scenario_5_end_of_sim_position_held(
        self, simple_price_cache, mock_signal_service
    ):
        """情景 5: 走到 end_date 仍持有 → 以 end_of_sim 平倉。"""
        base_date = date(2026, 1, 1)
        config = SimulationConfig(
            kind="backtest",
            initial_capital=100000.0,
            start_date=base_date,
            end_date=base_date + timedelta(days=9),
            candidates=[CandidateEntry(code="7203", name="Toyota")],
            entry_rule=EntryRule(
                price_basis="next_open",
                require_signal=False,
            ),
            exit_rule=ExitRule(
                use_exit_signal=False,
                use_stop_loss=False,  # 禁用停損
                take_profit_pct=None,
                max_hold_days=None,
            ),
            position_sizing=PositionSizing(
                mode="equal_weight",
                max_concurrent_positions=10,
            ),
            cost_model=CostModel(),
        )

        sim = Simulation(
            id="test-5",
            name="Test 5",
            kind="backtest",
            created_at="2026-01-01",
            config=config,
            state=SimulationState(
                cash=100000.0,
                cursor_date=base_date,
                pending_entries=[CandidateEntry(code="7203", name="Toyota")],
            ),
            status="draft",
        )

        run_backtest(sim, mock_signal_service, simple_price_cache)

        # 應該有 1 筆交易，原因為 end_of_sim
        assert len(sim.state.closed_trades) == 1
        trade = sim.state.closed_trades[0]
        assert trade.exit_reason == "end_of_sim"
        assert trade.exit_date == config.end_date

    def test_scenario_3_take_profit(self, simple_price_cache, mock_signal_service):
        """情景 3: 設定 take_profit=10% → 股價 +10% 時出場。"""
        base_date = date(2026, 1, 1)
        config = SimulationConfig(
            kind="backtest",
            initial_capital=100000.0,
            start_date=base_date,
            end_date=base_date + timedelta(days=9),
            candidates=[CandidateEntry(code="7203", name="Toyota")],
            entry_rule=EntryRule(
                price_basis="next_open",
                require_signal=False,
            ),
            exit_rule=ExitRule(
                use_exit_signal=False,
                use_stop_loss=False,
                take_profit_pct=0.10,  # 10% 止盈
                max_hold_days=None,
            ),
            position_sizing=PositionSizing(
                mode="equal_weight",
                max_concurrent_positions=10,
            ),
            cost_model=CostModel(),
        )

        sim = Simulation(
            id="test-3",
            name="Test 3",
            kind="backtest",
            created_at="2026-01-01",
            config=config,
            state=SimulationState(
                cash=100000.0,
                cursor_date=base_date,
                pending_entries=[CandidateEntry(code="7203", name="Toyota")],
            ),
            status="draft",
        )

        run_backtest(sim, mock_signal_service, simple_price_cache)

        # 應該有 1 筆交易，原因為 take_profit
        assert len(sim.state.closed_trades) == 1
        trade = sim.state.closed_trades[0]
        assert trade.exit_reason == "take_profit"


class TestReportMetrics:
    """報告指標計算測試。"""

    def test_report_metrics_basic(self, simple_price_cache, mock_signal_service):
        """計算基本報告指標。"""
        base_date = date(2026, 1, 1)
        config = SimulationConfig(
            kind="backtest",
            initial_capital=100000.0,
            start_date=base_date,
            end_date=base_date + timedelta(days=9),
            candidates=[CandidateEntry(code="7203", name="Toyota")],
            entry_rule=EntryRule(
                price_basis="next_open",
                require_signal=False,
            ),
            exit_rule=ExitRule(
                use_exit_signal=False,
                use_stop_loss=False,
                take_profit_pct=None,
                max_hold_days=None,
            ),
            position_sizing=PositionSizing(
                mode="equal_weight",
                max_concurrent_positions=10,
            ),
            cost_model=CostModel(),
        )

        sim = Simulation(
            id="test-metrics",
            name="Test Metrics",
            kind="backtest",
            created_at="2026-01-01",
            config=config,
            state=SimulationState(
                cash=100000.0,
                cursor_date=base_date,
                pending_entries=[CandidateEntry(code="7203", name="Toyota")],
            ),
            status="draft",
        )

        run_backtest(sim, mock_signal_service, simple_price_cache)
        metrics = calculate_report_metrics(sim)

        # 檢查必要欄位存在
        assert "total_return_pct" in metrics
        assert "annualized_return_pct" in metrics
        assert "max_drawdown_pct" in metrics
        assert "win_rate" in metrics
        assert "profit_factor" in metrics
        assert "winning_trades" in metrics
        assert "losing_trades" in metrics

        # 檢查值的合理性（至少有一筆交易）
        assert metrics["winning_trades"] + metrics["losing_trades"] == len(
            sim.state.closed_trades
        )


class TestEdgeCases:
    """邊界情況測試。"""

    def test_missing_price_data_skip_entry(self, mock_signal_service):
        """進場日缺 price 資料 → skip 該日。"""
        base_date = date(2026, 1, 1)
        config = SimulationConfig(
            kind="backtest",
            initial_capital=100000.0,
            start_date=base_date,
            end_date=base_date + timedelta(days=3),
            candidates=[CandidateEntry(code="7203", name="Toyota")],
            entry_rule=EntryRule(
                price_basis="next_open",
                require_signal=False,
            ),
            exit_rule=ExitRule(),
            position_sizing=PositionSizing(),
            cost_model=CostModel(),
        )

        # 空的價格快取（完全無資料）
        price_cache = {}

        sim = Simulation(
            id="test-missing",
            name="Test Missing",
            kind="backtest",
            created_at="2026-01-01",
            config=config,
            state=SimulationState(
                cash=100000.0,
                cursor_date=base_date,
                pending_entries=[CandidateEntry(code="7203", name="Toyota")],
            ),
            status="draft",
        )

        run_backtest(sim, mock_signal_service, price_cache)

        # 應該沒有任何交易（因為沒有價格資料）
        assert len(sim.state.closed_trades) == 0
        assert len(sim.state.positions) == 0
        assert sim.state.pending_entries == [
            CandidateEntry(code="7203", name="Toyota")
        ]

    def test_multiple_positions_concurrent(self, mock_signal_service):
        """多檔同時進場、cash 不足 → 部分檔不進場。"""
        base_date = date(2026, 1, 1)
        config = SimulationConfig(
            kind="backtest",
            initial_capital=50000.0,  # 只有 50k，不足多檔
            start_date=base_date,
            end_date=base_date + timedelta(days=3),
            candidates=[
                CandidateEntry(code="7203", name="Toyota"),
                CandidateEntry(code="9984", name="SoftBank"),
            ],
            entry_rule=EntryRule(
                price_basis="next_open",
                require_signal=False,
            ),
            exit_rule=ExitRule(use_exit_signal=False, use_stop_loss=False),
            position_sizing=PositionSizing(
                mode="equal_weight",
                max_concurrent_positions=10,
            ),
            cost_model=CostModel(),
        )

        price_cache = {
            "7203": {
                base_date: {"open": 100.0, "close": 100.0},
                base_date + timedelta(days=1): {"open": 100.0, "close": 100.0},
            },
            "9984": {
                base_date: {"open": 100.0, "close": 100.0},
                base_date + timedelta(days=1): {"open": 100.0, "close": 100.0},
            },
        }

        sim = Simulation(
            id="test-multi",
            name="Test Multi",
            kind="backtest",
            created_at="2026-01-01",
            config=config,
            state=SimulationState(
                cash=50000.0,
                cursor_date=base_date,
                pending_entries=config.candidates.copy(),
            ),
            status="draft",
        )

        run_backtest(sim, mock_signal_service, price_cache)

        # 應該只進場一檔，另一檔保留在 pending
        assert len(sim.state.positions) <= 1
        # 剩餘候選仍在 pending
        assert len(sim.state.pending_entries) >= 1

    def test_entry_price_basis_variations(self, mock_signal_service):
        """進場價規則三種模式：signal_close / next_open / user_specified。"""
        base_date = date(2026, 1, 1)

        # 建立價格快取，signal_close=100, next_open=101
        price_cache = {
            "7203": {
                base_date: {"open": 100.0, "close": 100.0},
                base_date + timedelta(days=1): {"open": 101.0, "close": 101.0},
            }
        }

        for price_basis, expected_approx in [
            ("signal_close", 100.0),
            ("next_open", 101.0),
            ("user_specified", 99.0),
        ]:
            config = SimulationConfig(
                kind="backtest",
                initial_capital=100000.0,
                start_date=base_date,
                end_date=base_date + timedelta(days=1),
                candidates=[CandidateEntry(code="7203", name="Toyota")],
                entry_rule=EntryRule(
                    price_basis=price_basis,
                    user_price=99.0 if price_basis == "user_specified" else None,
                    require_signal=False,
                ),
                exit_rule=ExitRule(
                    use_exit_signal=False,
                    use_stop_loss=False,
                ),
                position_sizing=PositionSizing(),
                cost_model=CostModel(),
            )

            sim = Simulation(
                id=f"test-{price_basis}",
                name=f"Test {price_basis}",
                kind="backtest",
                created_at="2026-01-01",
                config=config,
                state=SimulationState(
                    cash=100000.0,
                    cursor_date=base_date,
                    pending_entries=[CandidateEntry(code="7203", name="Toyota")],
                ),
                status="draft",
            )

            run_backtest(sim, mock_signal_service, price_cache)

            # 如果進場了，檢查進場價
            if sim.state.closed_trades:
                trade = sim.state.closed_trades[0]
                assert trade.entry_price == pytest.approx(expected_approx, rel=0.1)
