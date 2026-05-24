"""模擬交易服務測試。"""
from datetime import date, timedelta
from unittest.mock import MagicMock
from pathlib import Path

import pytest

from api.services.simulation_service import SimulationService
from api.schemas.simulation import (
    CandidateEntry,
    Simulation,
    SimulationConfig,
    SimulationState,
    EntryRule,
    ExitRule,
    PositionSizing,
    CostModel,
)


@pytest.fixture
def sim_service(tmp_data_dir, monkeypatch):
    """模擬交易服務實例（臨時目錄）。"""
    monkeypatch.setattr("api.deps.DATA_DIR", tmp_data_dir)
    return SimulationService(str(tmp_data_dir))


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
        entry_rule=EntryRule(),
        exit_rule=ExitRule(),
        position_sizing=PositionSizing(),
        cost_model=CostModel(),
    )


class TestManualOpenPosition:
    """手動進場（open_position）測試。"""

    def test_open_position_creates_position(self, sim_service, base_config):
        sim = sim_service.create("Ledger", base_config)
        result = sim_service.open_position(
            sim.id, "7203", "Toyota", shares=30, entry_price=2500.0
        )
        assert len(result.state.positions) == 1
        pos = result.state.positions[0]
        assert pos.code == "7203"
        assert pos.shares == 30
        assert pos.entry_price == 2500.0
        # cash should be reduced
        assert result.state.cash < 100000.0
        # draft → running
        assert result.status == "running"

    def test_open_position_insufficient_cash_raises(self, sim_service, base_config):
        sim = sim_service.create("Ledger", base_config)
        with pytest.raises(ValueError, match="Insufficient cash"):
            sim_service.open_position(
                sim.id, "7203", "Toyota", shares=10000, entry_price=2500.0
            )

    def test_open_position_zero_shares_raises(self, sim_service, base_config):
        sim = sim_service.create("Ledger", base_config)
        with pytest.raises(ValueError, match="shares must be > 0"):
            sim_service.open_position(
                sim.id, "7203", "Toyota", shares=0, entry_price=2500.0
            )


class TestSimulationServiceBasics:
    """基本 CRUD 操作測試。"""

    def test_create_simulation(self, sim_service, base_config):
        """建立新模擬。"""
        sim = sim_service.create("My Test Sim", base_config)

        assert sim.id is not None
        assert sim.name == "My Test Sim"
        assert sim.kind == "backtest"
        assert sim.status == "draft"
        assert sim.config == base_config
        assert sim.state.cash == 100000.0
        assert sim.state.cursor_date == base_config.start_date

    def test_get_simulation(self, sim_service, base_config):
        """取得模擬。"""
        created = sim_service.create("Test Get", base_config)
        retrieved = sim_service.get(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == "Test Get"

    def test_get_nonexistent(self, sim_service):
        """取得不存在的模擬。"""
        result = sim_service.get("nonexistent-id")
        assert result is None

    def test_list_all_simulations(self, sim_service, base_config):
        """列出所有模擬。"""
        sim1 = sim_service.create("Sim 1", base_config)
        sim2 = sim_service.create("Sim 2", base_config)

        all_sims = sim_service.list_all()
        assert len(all_sims) >= 2
        ids = [s.id for s in all_sims]
        assert sim1.id in ids
        assert sim2.id in ids

    def test_delete_simulation(self, sim_service, base_config):
        """刪除模擬。"""
        sim = sim_service.create("To Delete", base_config)
        sim_id = sim.id

        sim_service.delete(sim_id)
        retrieved = sim_service.get(sim_id)

        assert retrieved is None

    def test_update_config_draft_only(self, sim_service, base_config):
        """更新設定（只能在 draft）。"""
        sim = sim_service.create("Test Update", base_config)
        assert sim.status == "draft"

        # 修改配置
        new_config = SimulationConfig(
            kind="backtest",
            initial_capital=200000.0,  # 改大一倍
            start_date=base_config.start_date,
            end_date=base_config.end_date,
            candidates=base_config.candidates,
            entry_rule=base_config.entry_rule,
            exit_rule=base_config.exit_rule,
            position_sizing=base_config.position_sizing,
            cost_model=base_config.cost_model,
        )

        updated = sim_service.update_config(sim.id, new_config)
        assert updated.config.initial_capital == 200000.0

    def test_update_config_non_draft_fails(self, sim_service, base_config):
        """更新非 draft 狀態的模擬應失敗。"""
        sim = sim_service.create("Test Non Draft", base_config)
        sim.status = "running"
        sim_service._save(sim)

        new_config = SimulationConfig(
            kind="backtest",
            initial_capital=200000.0,
            start_date=base_config.start_date,
            end_date=base_config.end_date,
            candidates=base_config.candidates,
            entry_rule=base_config.entry_rule,
            exit_rule=base_config.exit_rule,
            position_sizing=base_config.position_sizing,
            cost_model=base_config.cost_model,
        )

        with pytest.raises(ValueError, match="Cannot update non-draft"):
            sim_service.update_config(sim.id, new_config)


class TestCandidateManagement:
    """候選股票管理測試。"""

    def test_add_candidate_draft_only(self, sim_service, base_config):
        """加入候選（只能在 draft）。"""
        sim = sim_service.create("Test Add Candidate", base_config)

        result = sim_service.add_candidate(sim.id, "9984", "SoftBank")
        assert len(result.config.candidates) == 2
        assert result.config.candidates[1].code == "9984"
        assert result.state.pending_entries[1].code == "9984"

    def test_add_candidate_non_draft_fails(self, sim_service, base_config):
        """加入候選到非 draft 模擬應失敗。"""
        sim = sim_service.create("Test Add Non Draft", base_config)
        sim.status = "running"
        sim_service._save(sim)

        with pytest.raises(ValueError, match="Cannot modify non-draft"):
            sim_service.add_candidate(sim.id, "9984", "SoftBank")


class TestPersistence:
    """持久化測試。"""

    def test_save_and_load_roundtrip(self, sim_service, base_config):
        """保存和載入往返測試。"""
        original = sim_service.create("Test Persistence", base_config)
        original.status = "completed"
        sim_service._save(original)

        loaded = sim_service.get(original.id)
        assert loaded.id == original.id
        assert loaded.status == "completed"
        assert loaded.config.initial_capital == original.config.initial_capital

    def test_trades_csv_written(self, sim_service, base_config):
        """交易 CSV 被正確寫入。"""
        sim = sim_service.create("Test CSV", base_config)

        # 手動新增一筆交易（以便測試 CSV 寫入）
        from api.schemas.simulation import ClosedTrade

        sim.state.closed_trades.append(
            ClosedTrade(
                code="7203",
                name="Toyota",
                entry_date=base_config.start_date,
                entry_price=100.0,
                exit_date=base_config.start_date + timedelta(days=1),
                exit_price=105.0,
                shares=10,
                pnl_jpy=50.0,
                pnl_pct=0.05,
                hold_days=1,
                exit_reason="take_profit",
            )
        )

        sim_service._save_trades_csv(sim)

        # 驗證 CSV 檔案存在並包含資料
        csv_path = sim_service._trades_path(sim.id)
        assert csv_path.exists()

        with open(csv_path) as f:
            lines = f.readlines()
            assert len(lines) == 2  # header + 1 trade
            assert "7203" in lines[1]
            assert "take_profit" in lines[1]


class TestReportGeneration:
    """報告生成測試。"""

    def test_get_report_basic(self, sim_service, base_config):
        """生成基本報告。"""
        sim = sim_service.create("Test Report", base_config)

        # 手動新增權益曲線點以便測試
        from api.schemas.simulation import EquityPoint

        sim.state.equity_curve.append(
            EquityPoint(
                date=base_config.start_date,
                cash=100000.0,
                market_value=0.0,
                equity=100000.0,
            )
        )
        sim.state.equity_curve.append(
            EquityPoint(
                date=base_config.start_date + timedelta(days=1),
                cash=99000.0,
                market_value=1500.0,
                equity=100500.0,
            )
        )

        sim_service._save(sim)
        report = sim_service.get_report(sim.id)

        assert report.id == sim.id
        assert report.kind == "backtest"
        assert report.initial_capital == 100000.0
        assert report.final_equity == 100500.0
        assert "total_return_pct" in report.model_dump()
        assert "max_drawdown_pct" in report.model_dump()


class TestClosePosition:
    """手動平倉測試。"""

    def test_close_position_success(self, sim_service, base_config):
        """手動平倉成功。"""
        from api.schemas.simulation import Position

        sim = sim_service.create("Test Close", base_config)

        # 手動新增持倉
        pos = Position(
            code="7203",
            name="Toyota",
            entry_date=base_config.start_date,
            entry_price=100.0,
            shares=10,
            cost_basis=1000.0,
        )
        sim.state.positions.append(pos)
        sim_service._save(sim)

        # 平倉
        result = sim_service.close_position(sim.id, "7203", 105.0, base_config.start_date + timedelta(days=1))

        assert len(result.state.positions) == 0
        assert len(result.state.closed_trades) == 1
        trade = result.state.closed_trades[0]
        assert trade.exit_reason == "manual"
        assert trade.exit_price == 105.0

    def test_close_nonexistent_position_fails(self, sim_service, base_config):
        """平倉不存在的持倉應失敗。"""
        sim = sim_service.create("Test Close Fail", base_config)
        sim_service._save(sim)

        with pytest.raises(ValueError, match="Position .* not found"):
            sim_service.close_position(sim.id, "9999", 100.0)
