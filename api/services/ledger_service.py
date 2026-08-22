"""跟單帳本服務 — IMP-002。

儲存：每個帳本一個 JSON 檔 `data/ledgers/{id}.json`（帳本＝資料夾，trades 內含）。
刪除：依專案絕對規則不真刪，改名加 `DELETE_` prefix（軟刪除，列表排除）。

出場：棘輪式移動停損（pure function `advance_trade`，方便測試）＋選配時間停損。
「訊號失效出場」（掉出口袋名單）是自動交易帳本專屬，實作在 auto_trade_service。
"""
from __future__ import annotations

import glob
import json
import os
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from api.deps import DATA_DIR
from api.schemas.ledger import (
    AdvanceResult, Ledger, LedgerSummary, Trade, TradeAddRequest,
)

LEDGERS_DIR = DATA_DIR / "ledgers"


def _ensure_dir() -> None:
    LEDGERS_DIR.mkdir(parents=True, exist_ok=True)


def _ledger_path(ledger_id: str) -> Path:
    return LEDGERS_DIR / f"{ledger_id}.json"


# ── 棘輪式移動停損（純函式核心，便於 pytest）────────────────────────────

def init_trade_stops(trade: Trade, entry_bar_date: Optional[date] = None) -> Trade:
    """初始化棘輪狀態：high_water=進場價、停損線=進場價×(1-N)。

    `entry_bar_date`＝entry_price 取自哪一天的收盤（預設＝entry_date）。推進的錨點用它
    而不是 entry_date：排程若在 JST 00:xx 跑，entry_price 是前一交易日收盤但 entry_date
    記成當天，用 entry_date 當錨點會讓進場後第一根 K 棒被永久跳過。
    """
    trade.high_water = float(trade.entry_price)
    trade.stop_line = float(trade.entry_price) * (1.0 - trade.stop_pct)
    trade.entry_bar_date = entry_bar_date or trade.entry_date
    trade.last_advanced_date = trade.entry_bar_date
    return trade


def close_trade(trade: Trade, d: date, close: float, reason: str) -> Trade:
    """把一筆 open 交易結算掉（統一寫 exit_* 與損益欄位）。"""
    trade.status = "closed"
    trade.exit_date = d
    trade.exit_price = float(close)
    trade.exit_reason = reason
    trade.pnl_jpy = (close - trade.entry_price) * trade.shares
    trade.pnl_pct = (close - trade.entry_price) / trade.entry_price if trade.entry_price else 0.0
    return trade


def advance_trade(
    trade: Trade,
    closes: list[tuple[date, float]],
    *,
    time_stop_days: int = 0,
    time_stop_band_pct: Optional[float] = None,
) -> Trade:
    """以「(日期, 收盤)」序列推進一筆 open 交易（棘輪移動停損 + 選配時間停損）。

    規則（只處理晚於 last_advanced_date 的收盤）：
      - 收盤 < 停損線 → 出場（exit_price=該日收盤、reason=trailing_stop）
      - time_stop_days>0 且進場後已滿 N 根 K 棒，且（未指定帶寬 或 損益在 ±帶寬內）
        → 出場（reason=time_stop）。帶寬條件避免把正在跑的贏家砍掉。
      - 收盤創新高 → high_water=收盤、停損線=high_water×(1-N)（只升不降）

    time_stop_* 預設關閉 → user 帳本行為與過去完全一致，只有自動交易帳本會傳。
    """
    if trade.status != "open":
        return trade
    if trade.high_water <= 0:
        init_trade_stops(trade)

    anchor = trade.entry_bar_date or trade.entry_date
    start = trade.last_advanced_date or anchor
    ordered = sorted(closes, key=lambda x: x[0])
    # 已推進過的 K 棒根數（跨 run 續算，不需另存欄位）
    held = sum(1 for d, _ in ordered if anchor < d <= start)

    for d, close in ordered:
        if d <= start:
            continue
        trade.last_advanced_date = d
        held += 1
        # 先判出場（用「進入該日前」的停損線），再更新新高
        if close < trade.stop_line:
            return close_trade(trade, d, close, "trailing_stop")
        if time_stop_days and held >= time_stop_days:
            pnl_pct = ((close - trade.entry_price) / trade.entry_price) if trade.entry_price else 0.0
            if time_stop_band_pct is None or abs(pnl_pct) <= time_stop_band_pct:
                return close_trade(trade, d, close, "time_stop")
        if close > trade.high_water:
            trade.high_water = float(close)
            trade.stop_line = float(close) * (1.0 - trade.stop_pct)
    return trade


# ── 儲存 ────────────────────────────────────────────────────────────────

def _load_ledger(ledger_id: str) -> Optional[Ledger]:
    path = _ledger_path(ledger_id)
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return Ledger(**json.load(f))
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def _save_ledger(ledger: Ledger) -> None:
    _ensure_dir()
    with open(_ledger_path(ledger.id), "w", encoding="utf-8") as f:
        json.dump(ledger.model_dump(mode="json"), f, ensure_ascii=False, indent=1)


# 公開別名（auto_trade_service 等同套件內服務使用，避免各自實作讀寫）
load_ledger = _load_ledger
save_ledger = _save_ledger


def closes_for(code: str, days: int = 400) -> list[tuple[date, float]]:
    """(日期, 收盤) 序列 — 讀 data/cache 的 price CSV（cache-first，不打外網）。"""
    return _closes_for(code, days=days)


# ── 帳本 CRUD ────────────────────────────────────────────────────────────

def create_ledger(name: str) -> Ledger:
    _ensure_dir()
    ledger = Ledger(
        id=str(uuid.uuid4()),
        name=name.strip() or "未命名帳本",
        created_at=datetime.now().isoformat(timespec="seconds"),
        trades=[],
    )
    _save_ledger(ledger)
    return ledger


def list_ledgers() -> list[LedgerSummary]:
    _ensure_dir()
    out: list[LedgerSummary] = []
    for fp in sorted(glob.glob(str(LEDGERS_DIR / "*.json"))):
        if os.path.basename(fp).startswith("DELETE_"):
            continue
        try:
            with open(fp, encoding="utf-8") as f:
                lg = Ledger(**json.load(f))
        except (OSError, json.JSONDecodeError, ValueError):
            continue
        realized = sum((t.pnl_jpy or 0.0) for t in lg.trades if t.status == "closed")
        out.append(LedgerSummary(
            id=lg.id, name=lg.name, created_at=lg.created_at, owner=lg.owner,
            trade_count=len(lg.trades),
            open_count=sum(1 for t in lg.trades if t.status == "open"),
            closed_count=sum(1 for t in lg.trades if t.status == "closed"),
            realized_pnl_jpy=realized,
            unrealized_pnl_jpy=0.0,  # 由 advance/詳情即時估，列表先 0
        ))
    out.sort(key=lambda s: s.created_at, reverse=True)
    return out


def get_ledger(ledger_id: str) -> Optional[Ledger]:
    return _load_ledger(ledger_id)


def get_or_create_bot_ledger() -> Ledger:
    """取得（或初始化）自動模擬交易帳本 — 固定 id，owner="bot"，只由排程/Actions 寫。"""
    from capystock import config
    ledger = _load_ledger(config.AUTO_TRADE_LEDGER_ID)
    if ledger is not None:
        return ledger
    _ensure_dir()
    ledger = Ledger(
        id=config.AUTO_TRADE_LEDGER_ID,
        name=config.AUTO_TRADE_LEDGER_NAME,
        created_at=datetime.now().isoformat(timespec="seconds"),
        owner="bot",
        initial_cash_jpy=float(config.AUTO_TRADE_INITIAL_CASH_JPY),
        cash_jpy=float(config.AUTO_TRADE_INITIAL_CASH_JPY),
        trades=[],
    )
    _save_ledger(ledger)
    return ledger


def is_bot_ledger(ledger_id: str) -> bool:
    lg = _load_ledger(ledger_id)
    return lg is not None and lg.owner == "bot"


def delete_ledger(ledger_id: str) -> bool:
    """軟刪除：改名加 DELETE_ prefix（不真刪，符合絕對規則）。"""
    path = _ledger_path(ledger_id)
    if not path.exists():
        return False
    target = path.with_name(f"DELETE_{path.name}")
    os.rename(path, target)
    return True


# ── 交易 ─────────────────────────────────────────────────────────────────

def add_trade(ledger_id: str, req: TradeAddRequest) -> Optional[Trade]:
    ledger = _load_ledger(ledger_id)
    if ledger is None:
        return None
    trade = Trade(
        id=str(uuid.uuid4()),
        code=req.code.strip(),
        name=(req.name or "").strip(),
        entry_date=req.entry_date or date.today(),
        entry_price=float(req.entry_price),
        shares=int(req.shares),
        stop_pct=float(req.stop_pct),
        status="open",
    )
    init_trade_stops(trade)
    ledger.trades.append(trade)
    _save_ledger(ledger)
    return trade


def delete_trade(ledger_id: str, trade_id: str) -> bool:
    ledger = _load_ledger(ledger_id)
    if ledger is None:
        return False
    before = len(ledger.trades)
    ledger.trades = [t for t in ledger.trades if t.id != trade_id]
    if len(ledger.trades) == before:
        return False
    _save_ledger(ledger)
    return True


# ── 每日推進（棘輪移動停損出場）─────────────────────────────────────────

def _closes_for(code: str, days: int = 400) -> list[tuple[date, float]]:
    from api.services import signal_service
    bars = signal_service.get_price_history(code, days=days)
    return [(b.date, float(b.close)) for b in bars]


# ── 單筆交易：進場日 → 今天的價格折線序列 ────────────────────────────────

def build_trade_price_series(trade: Trade, today: Optional[date] = None) -> dict:
    """從進場日到今天（已出場則到出場日）的「日曆軸」收盤序列。

    回傳 dates / closes 兩條等長陣列：當日 cache 沒有收盤（週末、未同步那天）→
    close=None，前端折線留白（不連線）。另附進場價 / 停損線 / 出場點供標記。
    """
    today = today or date.today()
    end = trade.exit_date or today
    if end < trade.entry_date:
        end = trade.entry_date
    span = (end - trade.entry_date).days + 5
    closes = dict(_closes_for(trade.code, days=max(span, 30)))

    dates: list[str] = []
    values: list[Optional[float]] = []
    d = trade.entry_date
    one = timedelta(days=1)
    while d <= end:
        dates.append(d.isoformat())
        c = closes.get(d)
        values.append(round(float(c), 2) if c is not None else None)
        d += one

    return {
        "code": trade.code,
        "name": trade.name,
        "entry_date": trade.entry_date.isoformat(),
        "end_date": end.isoformat(),
        "entry_price": trade.entry_price,
        "stop_line": trade.stop_line,
        "high_water": trade.high_water,
        "status": trade.status,
        "exit_date": trade.exit_date.isoformat() if trade.exit_date else None,
        "exit_price": trade.exit_price,
        "dates": dates,
        "closes": values,
    }


def trade_price_series(ledger_id: str, trade_id: str) -> Optional[dict]:
    """讀某帳本某筆交易的價格折線序列。帳本/交易不存在回 None。"""
    ledger = _load_ledger(ledger_id)
    if ledger is None:
        return None
    trade = next((t for t in ledger.trades if t.id == trade_id), None)
    if trade is None:
        return None
    return build_trade_price_series(trade)


def advance_ledger(ledger_id: str) -> Optional[AdvanceResult]:
    ledger = _load_ledger(ledger_id)
    if ledger is None:
        return None
    return _advance_and_save(ledger)


def advance_all(include_bot: bool = False) -> AdvanceResult:
    """推進所有帳本所有 open 交易（排程/手動用）。

    include_bot=False（預設）：**跳過 owner="bot" 的自動模擬交易帳本** —
    該帳本唯一寫入者是 GitHub Actions（paper-trade.yml），本地若也推進會造成
    重複推進與 git 衝突（單一寫入者原則）。
    """
    total_adv = 0
    total_closed = 0
    for s in list_ledgers():
        if not include_bot and s.owner == "bot":
            continue
        ledger = _load_ledger(s.id)
        if ledger is None:
            continue
        r = _advance_and_save(ledger)
        total_adv += r.advanced_trades
        total_closed += r.closed_trades
    return AdvanceResult(advanced_trades=total_adv, closed_trades=total_closed)


def _advance_and_save(ledger: Ledger) -> AdvanceResult:
    closes_cache: dict[str, list[tuple[date, float]]] = {}
    advanced = 0
    closed = 0
    for t in ledger.trades:
        if t.status != "open":
            continue
        if t.code not in closes_cache:
            closes_cache[t.code] = _closes_for(t.code)
        before_status = t.status
        advance_trade(t, closes_cache[t.code])
        advanced += 1
        if before_status == "open" and t.status == "closed":
            closed += 1
    if advanced:
        _save_ledger(ledger)
    return AdvanceResult(advanced_trades=advanced, closed_trades=closed)
