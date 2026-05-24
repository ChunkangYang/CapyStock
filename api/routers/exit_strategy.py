"""出場策略設定 API：讀寫 data/exit_strategy.json，動態調整 trailing stop 參數。"""
import json
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from capystock import config

router = APIRouter()


class ExitStrategyConfig(BaseModel):
    """出場策略參數（前端可調）。"""
    atr_period: int = Field(default=14, ge=5, le=60, description="ATR 週期")
    initial_stop_atr_mult: float = Field(default=3.0, ge=1.0, le=10.0, description="Stage 1 初始停損 ATR 倍數")
    chandelier_atr_mult: float = Field(default=2.5, ge=1.0, le=10.0, description="Stage 3 Chandelier ATR 倍數")
    chandelier_high_window: int = Field(default=20, ge=5, le=60, description="Chandelier 看回 N 日高點")
    stage2_threshold_pct: float = Field(default=0.10, ge=0.01, le=1.0, description="進入 Stage 2（保本）門檻")
    stage3_threshold_pct: float = Field(default=0.25, ge=0.05, le=2.0, description="進入 Stage 3（Chandelier）門檻")
    sma_break_period: int = Field(default=20, ge=5, le=200, description="SMA 跌破警示週期")
    volume_dry_days: int = Field(default=5, ge=2, le=20, description="量能萎縮連續日數")
    volume_dry_ratio: float = Field(default=0.5, ge=0.1, le=1.0, description="量能萎縮比率（vs 5 日均量）")


def _defaults() -> ExitStrategyConfig:
    return ExitStrategyConfig(
        atr_period=config.ATR_PERIOD,
        initial_stop_atr_mult=config.INITIAL_STOP_ATR_MULT,
        chandelier_atr_mult=config.CHANDELIER_ATR_MULT,
        chandelier_high_window=config.CHANDELIER_HIGH_WINDOW,
        stage2_threshold_pct=config.TRAILING_STAGE2_THRESHOLD,
        stage3_threshold_pct=config.TRAILING_STAGE3_THRESHOLD,
        sma_break_period=config.SMA_BREAK_PERIOD,
        volume_dry_days=config.VOLUME_DRY_DAYS,
        volume_dry_ratio=config.VOLUME_DRY_RATIO,
    )


@router.get("/config/exit-strategy")
def get_exit_strategy() -> ExitStrategyConfig:
    """讀取目前出場策略（override 優先，否則回 config 預設）。"""
    override = config.load_exit_strategy_override()
    defaults = _defaults().model_dump()
    defaults.update({k: v for k, v in override.items() if k in defaults})
    return ExitStrategyConfig(**defaults)


@router.put("/config/exit-strategy")
def update_exit_strategy(payload: ExitStrategyConfig) -> ExitStrategyConfig:
    """寫入新的出場策略到 data/exit_strategy.json。"""
    if payload.stage3_threshold_pct <= payload.stage2_threshold_pct:
        raise HTTPException(
            status_code=400,
            detail=f"stage3 ({payload.stage3_threshold_pct}) 必須大於 stage2 ({payload.stage2_threshold_pct})",
        )
    config.EXIT_STRATEGY_OVERRIDE_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.EXIT_STRATEGY_OVERRIDE_PATH.write_text(
        json.dumps(payload.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload


@router.delete("/config/exit-strategy")
def reset_exit_strategy() -> ExitStrategyConfig:
    """還原為 config 預設（刪除 override 檔）。"""
    if config.EXIT_STRATEGY_OVERRIDE_PATH.exists():
        # 改名加 DELETE_ prefix（遵循 CLAUDE.md 禁刪規則）
        backup = config.EXIT_STRATEGY_OVERRIDE_PATH.with_name(
            f"DELETE_{config.EXIT_STRATEGY_OVERRIDE_PATH.name}"
        )
        config.EXIT_STRATEGY_OVERRIDE_PATH.rename(backup)
    return _defaults()
