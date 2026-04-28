"""模擬交易 API 路由。"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException

from api.schemas.simulation import (
    CandidateEntry,
    Simulation,
    SimulationConfig,
    SimulationReport,
)
from api.services import simulation_service, signal_service
from api.services.indicator_service import get_indicator_service

router = APIRouter()


@router.post("/simulation", response_model=Simulation)
def create_simulation(
    name: str,
    config: SimulationConfig,
):
    """建立新模擬。"""
    try:
        sim = simulation_service.create(name, config)
        return sim
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/simulation", response_model=list[Simulation])
def list_simulations():
    """列出所有模擬。"""
    return simulation_service.list_all()


@router.get("/simulation/{sim_id}", response_model=Simulation)
def get_simulation(sim_id: str):
    """取得模擬詳情。"""
    sim = simulation_service.get(sim_id)
    if sim is None:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return sim


@router.patch("/simulation/{sim_id}", response_model=Simulation)
def update_simulation(
    sim_id: str,
    config: SimulationConfig,
):
    """更新模擬設定（draft 狀態）。"""
    try:
        sim = simulation_service.update_config(sim_id, config)
        return sim
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/simulation/{sim_id}/add-candidate", response_model=Simulation)
def add_candidate(
    sim_id: str,
    code: str,
    name: str,
    forced_entry_date: Optional[date] = None,
):
    """新增候選股票。"""
    try:
        sim = simulation_service.add_candidate(sim_id, code, name, forced_entry_date)
        return sim
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/simulation/{sim_id}/run", response_model=Simulation)
def run_simulation(sim_id: str):
    """執行模擬（backtest 同步、paper 改狀態）。"""
    try:
        sim = simulation_service.get(sim_id)
        if sim is None:
            raise HTTPException(status_code=404, detail="Simulation not found")

        if sim.config.kind == "backtest":
            # 收集所有需要的價格資料到 price_cache
            price_cache = {}
            for cand in sim.config.candidates:
                try:
                    prices = signal_service.get_price_history(cand.code, days=365)
                    price_cache[cand.code] = {
                        p.date: {"open": p.open, "close": p.close} for p in prices
                    }
                except Exception:
                    pass

            sim = simulation_service.run_backtest(sim_id, signal_service, price_cache, indicator_service=get_indicator_service())
            return sim
        elif sim.config.kind == "paper":
            sim.status = "running"
            simulation_service._save(sim)
            return sim
        else:
            raise HTTPException(status_code=400, detail="Unknown simulation kind")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/simulation/{sim_id}/advance", response_model=Simulation)
def advance_paper(
    sim_id: str,
    to_date: Optional[date] = None,
):
    """推進前進模擬。"""
    from datetime import date as date_cls

    if to_date is None:
        to_date = date_cls.today()

    try:
        sim = simulation_service.get(sim_id)
        if sim is None:
            raise HTTPException(status_code=404, detail="Simulation not found")

        if sim.config.kind != "paper":
            raise HTTPException(status_code=400, detail="Not a paper trading simulation")

        # 收集所有需要的價格資料
        price_cache = {}
        for cand in sim.config.candidates:
            try:
                prices = signal_service.get_price_history(cand.code, days=365)
                price_cache[cand.code] = {
                    p.date: {"open": p.open, "close": p.close} for p in prices
                }
            except Exception:
                pass

        sim = simulation_service.advance_paper(sim_id, to_date, signal_service, price_cache)
        return sim

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/simulation/{sim_id}/close-position", response_model=Simulation)
def close_position(
    sim_id: str,
    code: str,
    exit_price: float,
    exit_date: Optional[date] = None,
):
    """手動平倉。"""
    try:
        sim = simulation_service.close_position(sim_id, code, exit_price, exit_date)
        return sim
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/simulation/{sim_id}/report", response_model=SimulationReport)
def get_report(sim_id: str):
    """取得模擬報告。"""
    try:
        report = simulation_service.get_report(sim_id)
        return report
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/simulation/{sim_id}")
def delete_simulation(sim_id: str):
    """刪除模擬。"""
    try:
        simulation_service.delete(sim_id)
        return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
