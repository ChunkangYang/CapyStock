"""自動模擬交易 API — 帳戶總覽 / 資金曲線 / 每日 log / 手動觸發。"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.services import auto_trade_service

router = APIRouter()


class AutoTradeRunRequest(BaseModel):
    dry_run: bool = False
    as_of: Optional[date] = None


@router.get("/auto-trade/summary")
def get_summary():
    """帳戶總覽：現金、持倉（含暫定收益）、已實現損益、勝率。"""
    return auto_trade_service.summary()


@router.get("/auto-trade/equity")
def get_equity_curve():
    """資金曲線（日曆軸）：equity / cash / market_value / realized。"""
    return auto_trade_service.build_equity_curve()


@router.get("/auto-trade/logs")
def get_logs(days: int = 30):
    """最近 N 天每日 log 摘要（新到舊）。"""
    return auto_trade_service.list_daily_logs(days=days)


@router.get("/auto-trade/logs/{log_date}")
def get_log(log_date: str):
    """單日完整 log（含被跳過的候選與原因）。"""
    log = auto_trade_service.read_daily_log(log_date)
    if log is None:
        raise HTTPException(404, f"{log_date} 無交易 log")
    return log


@router.get("/auto-trade/logs/{log_date}/report")
def get_log_report(log_date: str):
    """單日 Telegram 日報文字（純文字，方便前端預覽/重送）。"""
    log = auto_trade_service.read_daily_log(log_date)
    if log is None:
        raise HTTPException(404, f"{log_date} 無交易 log")
    return {"date": log_date, "text": auto_trade_service.format_report(log)}


@router.post("/auto-trade/run")
def run_now(req: AutoTradeRunRequest):
    """手動跑一次（正式跑在 GitHub Actions；本地補跑或 dry-run 驗證用）。"""
    log = auto_trade_service.run_daily(as_of=req.as_of, dry_run=req.dry_run)
    return {"log": log, "report": auto_trade_service.format_report(log)}
