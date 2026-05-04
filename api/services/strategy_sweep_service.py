"""策略參數 Sweep 服務：網格展開 + 並行 backtest。"""
from __future__ import annotations

import copy
import itertools
import logging
import os
import uuid
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from typing import Callable, Optional

from api.schemas.simulation import SimulationConfig, SimulationState
from api.schemas.sweep import ParamGrid, SweepRequest, SweepResult, SweepRow

logger = logging.getLogger(__name__)

_MAX_COMBINATIONS = 200
_MAX_WORKERS = min(8, os.cpu_count() or 2)

# 進行中的 job 狀態儲存（in-memory，重啟會清空）
_jobs: dict[str, SweepResult] = {}


def _expand_grid(grid: ParamGrid) -> list[dict]:
    """展開笛卡兒積，回傳每組參數 dict。"""
    axes: dict[str, list] = {}
    if grid.stop_loss_pct:
        axes["stop_loss_pct"] = grid.stop_loss_pct
    if grid.take_profit_pct:
        axes["take_profit_pct"] = grid.take_profit_pct
    if grid.max_hold_days:
        axes["max_hold_days"] = grid.max_hold_days
    if grid.indicator_entry_combos:
        axes["indicator_entry_combos"] = grid.indicator_entry_combos

    if not axes:
        return [{}]

    keys = list(axes.keys())
    values = [axes[k] for k in keys]
    return [dict(zip(keys, combo)) for combo in itertools.product(*values)]


def _apply_params(base_config: SimulationConfig, params: dict) -> SimulationConfig:
    """複製 base_config 並覆蓋指定欄位。"""
    cfg = copy.deepcopy(base_config)
    if "stop_loss_pct" in params:
        cfg.exit_rule.use_stop_loss = True
    if "take_profit_pct" in params:
        cfg.exit_rule.take_profit_pct = params["take_profit_pct"]
    if "max_hold_days" in params:
        cfg.exit_rule.max_hold_days = params["max_hold_days"]
    return cfg


def _run_single_backtest(args: tuple) -> tuple[dict, dict]:
    """子程序：跑一組 backtest，回傳 (params, metrics)。"""
    params, base_config_dict, sim_config_dict = args
    try:
        from api.schemas.simulation import SimulationConfig, Simulation, SimulationState
        from api.services.backtest_engine import run_backtest, calculate_report_metrics
        from capystock import scraper
        import pandas as pd

        base_cfg = SimulationConfig.model_validate(base_config_dict)
        cfg = _apply_params(base_cfg, params)

        # 建立最小 simulation
        from uuid import uuid4
        from datetime import datetime as dt
        sim = Simulation(
            id=str(uuid4()),
            name="sweep",
            kind=cfg.kind,
            created_at=dt.utcnow().isoformat(),
            config=cfg,
            state=SimulationState(
                cash=cfg.initial_capital,
                cursor_date=cfg.start_date,
                pending_entries=cfg.candidates.copy(),
            ),
        )

        # 建立 price cache
        codes = [c.code for c in cfg.candidates]
        price_cache: dict = {}
        for code in codes:
            try:
                df, _ = scraper.fetch_price(code)
                if df is not None and not df.empty:
                    price_cache[code] = {}
                    for _, row in df.iterrows():
                        d = pd.Timestamp(row["date"]).date()
                        price_cache[code][d] = {
                            "close": float(row["close"]),
                            "open": float(row.get("open", row["close"])),
                        }
            except Exception:
                pass

        class _DummySignalService:
            def analyze_one(self, code):
                from types import SimpleNamespace
                conds = SimpleNamespace(matched=0)
                return SimpleNamespace(accumulation_signal=False, conditions=conds)

        run_backtest(sim, _DummySignalService(), price_cache)
        metrics = calculate_report_metrics(sim)
        return params, metrics
    except Exception as e:
        return params, {"error": str(e)}


class StrategySweepService:
    def run(
        self,
        req: SweepRequest,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> SweepResult:
        combos = _expand_grid(req.grid)
        n = len(combos)

        if n > _MAX_COMBINATIONS:
            raise ValueError(f"組合數 {n} 超過上限 {_MAX_COMBINATIONS}")

        job_id = str(uuid.uuid4())
        started_at = datetime.utcnow()

        base_dict = req.base_config.model_dump(mode="json")
        args = [(params, base_dict, base_dict) for params in combos]

        rows: list[SweepRow] = []
        done = 0

        with ProcessPoolExecutor(max_workers=min(_MAX_WORKERS, n or 1)) as executor:
            futures = {executor.submit(_run_single_backtest, a): a[0] for a in args}
            for fut in as_completed(futures):
                done += 1
                if on_progress:
                    on_progress(done, n)
                try:
                    params, metrics = fut.result()
                    if "error" in metrics:
                        logger.warning(f"sweep row error: {metrics['error']}")
                        continue
                    total_trades = metrics.get("winning_trades", 0) + metrics.get("losing_trades", 0)
                    pf = metrics.get("profit_factor") or 0.0
                    rows.append(SweepRow(
                        params=params,
                        total_return=round(float(metrics.get("total_return_pct", 0)), 4),
                        annualized=round(float(metrics.get("annualized_return_pct", 0)), 4),
                        max_drawdown=round(float(metrics.get("max_drawdown_pct", 0)), 4),
                        win_rate=round(float(metrics.get("win_rate") or 0), 4),
                        profit_factor=round(float(pf), 4),
                        n_trades=total_trades,
                    ))
                except Exception as e:
                    logger.warning(f"sweep future error: {e}")

        # 排序
        reverse = req.metric != "max_drawdown"
        metric_key = req.metric
        rows.sort(key=lambda r: getattr(r, metric_key, 0) or 0, reverse=reverse)
        rows = rows[: req.top_n]

        result = SweepResult(
            job_id=job_id,
            request=req,
            rows=rows,
            started_at=started_at,
            finished_at=datetime.utcnow(),
            n_combinations=n,
            status="completed",
        )
        _jobs[job_id] = result
        return result

    def get_job(self, job_id: str) -> Optional[SweepResult]:
        return _jobs.get(job_id)

    def cancel_job(self, job_id: str) -> bool:
        if job_id in _jobs:
            job = _jobs[job_id]
            job.status = "cancelled"
            return True
        return False
