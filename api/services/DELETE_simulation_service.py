"""模擬交易服務層。"""
import json
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from api.schemas.simulation import (
    CandidateEntry,
    ClosedTrade,
    EquityPoint,
    Simulation,
    SimulationConfig,
    SimulationReport,
    SimulationState,
)
from api.services.backtest_engine import run_backtest as _engine_run_backtest, calculate_report_metrics


class SimulationService:
    """模擬交易服務。"""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.sim_dir = self.data_dir / "simulations"
        self.sim_dir.mkdir(parents=True, exist_ok=True)

    def _sim_path(self, sim_id: str) -> Path:
        """返回模擬檔案路徑。"""
        return self.sim_dir / f"{sim_id}.json"

    def _trades_path(self, sim_id: str) -> Path:
        """返回交易紀錄檔案路徑。"""
        return self.sim_dir / f"{sim_id}_trades.csv"

    def create(
        self,
        name: str,
        config: SimulationConfig,
    ) -> Simulation:
        """建立新模擬（draft 狀態）。"""
        sim_id = str(uuid4())
        now = datetime.utcnow().isoformat()

        sim = Simulation(
            id=sim_id,
            name=name,
            kind=config.kind,
            created_at=now,
            config=config,
            state=SimulationState(
                cash=config.initial_capital,
                cursor_date=config.start_date,
                pending_entries=config.candidates.copy(),
            ),
            status="draft",
        )

        self._save(sim)
        return sim

    def get(self, sim_id: str) -> Optional[Simulation]:
        """取得模擬。"""
        path = self._sim_path(sim_id)
        if not path.exists():
            return None

        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return Simulation(**data)

    def list_all(self) -> list[Simulation]:
        """列出所有模擬。"""
        sims = []
        for path in self.sim_dir.glob("*.json"):
            if "_trades" not in path.stem:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                    sims.append(Simulation(**data))
        return sims

    def update_config(self, sim_id: str, config: SimulationConfig) -> Simulation:
        """更新模擬設定（只能在 draft 狀態）。"""
        sim = self.get(sim_id)
        if sim is None:
            raise ValueError(f"Simulation {sim_id} not found")
        if sim.status != "draft":
            raise ValueError(f"Cannot update non-draft simulation (status={sim.status})")

        sim.config = config
        sim.state.pending_entries = config.candidates.copy()
        self._save(sim)
        return sim

    def add_candidate(
        self, sim_id: str, code: str, name: str, forced_entry_date: Optional[date] = None
    ) -> Simulation:
        """新增候選股票（只能在 draft）。"""
        sim = self.get(sim_id)
        if sim is None:
            raise ValueError(f"Simulation {sim_id} not found")
        if sim.status != "draft":
            raise ValueError(f"Cannot modify non-draft simulation")

        cand = CandidateEntry(
            code=code,
            name=name,
            forced_entry_date=forced_entry_date,
        )
        sim.config.candidates.append(cand)
        sim.state.pending_entries.append(cand)
        self._save(sim)
        return sim

    def prepare_rerun(self, sim_id: str) -> None:
        """重置 state 並設為 running，供背景執行前呼叫。"""
        sim = self.get(sim_id)
        if sim is None:
            raise ValueError(f"Simulation {sim_id} not found")
        sim.state = SimulationState(
            cash=sim.config.initial_capital,
            cursor_date=sim.config.start_date,
            pending_entries=sim.config.candidates.copy(),
        )
        sim.status = "running"
        self._save(sim)

    def run_backtest(self, sim_id: str, signal_service, price_cache: dict) -> Simulation:
        """執行回測。"""
        sim = self.get(sim_id)
        if sim is None:
            raise ValueError(f"Simulation {sim_id} not found")
        if sim.config.kind != "backtest":
            raise ValueError(f"Simulation is not backtest type")

        if sim.status != "running":
            self.prepare_rerun(sim_id)
            sim = self.get(sim_id)

        try:
            _engine_run_backtest(sim, signal_service, price_cache)
            sim.status = "completed"
        except Exception as e:
            sim.status = "failed"
            raise e
        finally:
            self._save(sim)
            self._save_trades_csv(sim)

        return sim

    def advance_paper(
        self,
        sim_id: str,
        to_date: date,
        signal_service,
        price_cache: dict,
    ) -> Simulation:
        """推進前進模擬到指定日期。"""
        from api.services.backtest_engine import run_one_day

        sim = self.get(sim_id)
        if sim is None:
            raise ValueError(f"Simulation {sim_id} not found")
        if sim.config.kind != "paper":
            raise ValueError(f"Simulation is not paper type")

        sim.status = "running"

        current = sim.state.cursor_date + __import__("datetime").timedelta(days=1)
        while current <= to_date:
            run_one_day(sim, current, signal_service, price_cache)
            current += __import__("datetime").timedelta(days=1)

        sim.status = "completed"
        self._save(sim)
        self._save_trades_csv(sim)

        return sim

    def open_position(
        self,
        sim_id: str,
        code: str,
        name: str,
        shares: int,
        entry_price: float,
        entry_date: Optional[date] = None,
    ) -> Simulation:
        """手動進場（跳過 candidate / entry_rule）。

        直接建立 Position、扣現金，並把 sim 標為 running（讓每日 advance 接手）。
        """
        from api.schemas.simulation import Position

        sim = self.get(sim_id)
        if sim is None:
            raise ValueError(f"Simulation {sim_id} not found")

        if shares <= 0:
            raise ValueError("shares must be > 0")
        if entry_price <= 0:
            raise ValueError("entry_price must be > 0")

        if entry_date is None:
            entry_date = date.today()

        cost = shares * entry_price * (
            1 + sim.config.cost_model.commission_pct + sim.config.cost_model.slippage_pct
        )
        if cost > sim.state.cash:
            raise ValueError(
                f"Insufficient cash: need ¥{cost:,.0f}, available ¥{sim.state.cash:,.0f}"
            )

        sim.state.cash -= cost
        sim.state.positions.append(
            Position(
                code=code,
                name=name,
                entry_date=entry_date,
                entry_price=entry_price,
                shares=shares,
                cost_basis=cost,
            )
        )

        if sim.state.cursor_date < entry_date:
            sim.state.cursor_date = entry_date

        if sim.status == "draft":
            sim.status = "running"

        self._save(sim)
        return sim

    def close_position(
        self,
        sim_id: str,
        code: str,
        exit_price: float,
        exit_date: Optional[date] = None,
    ) -> Simulation:
        """手動平倉。"""
        from api.services.backtest_engine import close_position

        sim = self.get(sim_id)
        if sim is None:
            raise ValueError(f"Simulation {sim_id} not found")

        if exit_date is None:
            exit_date = date.today()

        pos = None
        for p in sim.state.positions:
            if p.code == code:
                pos = p
                break

        if pos is None:
            raise ValueError(f"Position {code} not found")

        close_position(sim.state, pos, exit_price, exit_date, "manual", sim.config.cost_model)
        self._save(sim)
        self._save_trades_csv(sim)

        return sim

    def get_report(self, sim_id: str) -> SimulationReport:
        """生成報告。"""
        sim = self.get(sim_id)
        if sim is None:
            raise ValueError(f"Simulation {sim_id} not found")

        metrics = calculate_report_metrics(sim)

        period_start = sim.config.start_date
        period_end = sim.state.cursor_date

        return SimulationReport(
            id=sim.id,
            name=sim.name,
            kind=sim.kind,
            status=sim.status,
            period_start=period_start,
            period_end=period_end,
            initial_capital=sim.config.initial_capital,
            final_equity=sim.state.equity_curve[-1].equity
            if sim.state.equity_curve
            else sim.config.initial_capital,
            total_return_pct=metrics["total_return_pct"],
            annualized_return_pct=metrics["annualized_return_pct"],
            max_drawdown_pct=metrics["max_drawdown_pct"],
            win_rate=metrics["win_rate"],
            avg_pnl_pct=metrics["avg_pnl_pct"],
            avg_hold_days=metrics["avg_hold_days"],
            profit_factor=metrics["profit_factor"],
            total_trades=len(sim.state.closed_trades),
            winning_trades=metrics["winning_trades"],
            losing_trades=metrics["losing_trades"],
            closed_trades=sim.state.closed_trades,
            equity_curve=sim.state.equity_curve,
            exit_reason_breakdown=metrics.get("exit_reason_breakdown", {}),
            strategy_type=metrics.get("strategy_type", "pure_signal"),
        )

    def delete(self, sim_id: str) -> None:
        """刪除模擬。"""
        path = self._sim_path(sim_id)
        trades_path = self._trades_path(sim_id)

        if path.exists():
            path.unlink()
        if trades_path.exists():
            trades_path.unlink()

    def _save(self, sim: Simulation) -> None:
        """保存模擬到 JSON（原子寫入）。"""
        path = self._sim_path(sim.id)
        data = sim.model_dump()

        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False, suffix=".json"
        ) as f:
            json.dump(data, f, indent=2, default=str, ensure_ascii=False)
            tmp_path = f.name

        Path(tmp_path).replace(path)

    def _save_trades_csv(self, sim: Simulation) -> None:
        """保存交易紀錄 CSV（append-only）。"""
        path = self._trades_path(sim.id)

        # 先刪除重寫（簡化版，實際應為 append）
        if path.exists():
            path.unlink()

        with open(path, "w", encoding="utf-8") as f:
            f.write("code,name,entry_date,entry_price,exit_date,exit_price,shares,pnl_jpy,pnl_pct,hold_days,exit_reason\n")
            for trade in sim.state.closed_trades:
                f.write(
                    f"{trade.code},{trade.name},{trade.entry_date},{trade.entry_price},"
                    f"{trade.exit_date},{trade.exit_price},{trade.shares},{trade.pnl_jpy},"
                    f"{trade.pnl_pct},{trade.hold_days},{trade.exit_reason}\n"
                )


# 預設實例（供 router 使用）
_default_service: Optional[SimulationService] = None


def _get_service() -> SimulationService:
    """取得預設服務實例。"""
    global _default_service
    if _default_service is None:
        from api.deps import DATA_DIR
        _default_service = SimulationService(str(DATA_DIR))
    return _default_service


def create(name: str, config: SimulationConfig) -> Simulation:
    """建立新模擬。"""
    return _get_service().create(name, config)


def get(sim_id: str) -> Optional[Simulation]:
    """取得模擬。"""
    return _get_service().get(sim_id)


def list_all() -> list[Simulation]:
    """列出所有模擬。"""
    return _get_service().list_all()


def update_config(sim_id: str, config: SimulationConfig) -> Simulation:
    """更新模擬設定。"""
    return _get_service().update_config(sim_id, config)


def add_candidate(
    sim_id: str, code: str, name: str, forced_entry_date: Optional[date] = None
) -> Simulation:
    """新增候選股票。"""
    return _get_service().add_candidate(sim_id, code, name, forced_entry_date)


def prepare_rerun(sim_id: str) -> None:
    """重置 state 並設為 running。"""
    return _get_service().prepare_rerun(sim_id)


def run_backtest(
    sim_id: str, signal_service, price_cache: dict
) -> Simulation:
    """執行回測。"""
    return _get_service().run_backtest(sim_id, signal_service, price_cache)


def advance_paper(
    sim_id: str, to_date: date, signal_service, price_cache: dict
) -> Simulation:
    """推進前進模擬。"""
    return _get_service().advance_paper(sim_id, to_date, signal_service, price_cache)


def close_position(
    sim_id: str,
    code: str,
    exit_price: float,
    exit_date: Optional[date] = None,
) -> Simulation:
    """手動平倉。"""
    return _get_service().close_position(sim_id, code, exit_price, exit_date)


def open_position(
    sim_id: str,
    code: str,
    name: str,
    shares: int,
    entry_price: float,
    entry_date: Optional[date] = None,
) -> Simulation:
    """手動進場。"""
    return _get_service().open_position(sim_id, code, name, shares, entry_price, entry_date)


def get_report(sim_id: str) -> SimulationReport:
    """生成報告。"""
    return _get_service().get_report(sim_id)


def delete(sim_id: str) -> None:
    """刪除模擬。"""
    return _get_service().delete(sim_id)


def _save(sim: Simulation) -> None:
    """內部保存（給 router 使用）。"""
    return _get_service()._save(sim)
