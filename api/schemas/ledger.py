"""跟單帳本（Ledger）schema — IMP-002 模擬交易大改。

模型：
  - Ledger（帳本）＝資料夾，純分組，無特殊功能。可新增/刪除。
  - Trade（交易）＝主體單位。一個帳本可放多筆，同一股票可重複出現、各自獨立。

出場：
  - trailing_stop：棘輪式移動停損（只升不降，以進場後最高收盤為錨）。
      high_water = max(進場價, 進場後最高收盤)
      停損線     = high_water × (1 − stop_pct)
      出場       = 某日收盤 < 停損線 → 以該日收盤出場
  - time_stop：進場後 N 根 K 棒仍在成本帶 ±BAND 內盤整（自動交易帳本才啟用）。
  - off_list：持倉離開三盤口袋名單超過 N 個日曆日＝進場理由消失（自動交易帳本才啟用）。
  - manual：使用者手動平倉。
"""
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class _DateModel(BaseModel):
    model_config = ConfigDict(json_encoders={date: lambda v: v.isoformat()})


class Trade(_DateModel):
    """帳本內的一筆交易（獨立主體）。"""
    id: str
    code: str
    name: str = ""
    entry_date: date
    entry_price: float          # 購入時價（可由使用者修改）
    shares: int                 # 購入股數（必填）
    stop_pct: float             # 移動停損 N（小數，0.10 = 10%）
    status: Literal["open", "closed"] = "open"
    entry_reason: str = ""      # 自動交易記進場理由（三盤 drop_pct 等），手動加入為空
    # 棘輪移動停損即時狀態
    high_water: float = 0.0     # 進場後最高收盤（初始＝進場價）
    stop_line: float = 0.0      # 目前停損線
    last_advanced_date: Optional[date] = None  # 已推進到的最後交易日
    # entry_price 取自哪一天的收盤。排程在收盤後跑時 = entry_date；跨日跑（JST 00:xx）
    # 時會早於 entry_date，此時若把推進錨點設成 entry_date，進場後第一根 K 棒會被
    # `d <= last_advanced_date` 跳過而永遠不檢查（見 AUTO_TRADE_LOW_TURNOVER_AUDIT.md §7）。
    entry_bar_date: Optional[date] = None
    # 訊號失效出場：最後一次出現在口袋名單的日期（None = 尚未評估過）
    last_on_list_date: Optional[date] = None
    # 出場後欄位
    exit_date: Optional[date] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[Literal["trailing_stop", "time_stop", "off_list", "manual"]] = None
    pnl_jpy: Optional[float] = None
    pnl_pct: Optional[float] = None


class Ledger(_DateModel):
    """帳本（資料夾）。"""
    id: str
    name: str
    created_at: str
    owner: Literal["user", "bot"] = "user"   # bot＝自動模擬交易帳本，唯讀（只有排程/Actions 寫）
    initial_cash_jpy: float = 0.0            # bot 帳本起始資金（user 帳本 0＝不管現金）
    cash_jpy: float = 0.0                    # bot 帳本目前現金
    trades: list[Trade] = Field(default_factory=list)


class LedgerSummary(_DateModel):
    """帳本列表用摘要。"""
    id: str
    name: str
    created_at: str
    owner: Literal["user", "bot"] = "user"
    trade_count: int
    open_count: int
    closed_count: int
    realized_pnl_jpy: float       # 已出場累計損益
    unrealized_pnl_jpy: float     # 持有中帳面損益（以最新收盤估）


class LedgerCreateRequest(BaseModel):
    name: str


class TradeAddRequest(BaseModel):
    """從 /pocket popup 加入一筆交易。"""
    code: str
    name: Optional[str] = None
    entry_price: float          # 購入時價（popup 預設帶現價，可改）
    shares: int                 # 購入股數（必填）
    stop_pct: float             # 移動停損 N（小數）
    entry_date: Optional[date] = None  # 預設今天


class AdvanceResult(BaseModel):
    advanced_trades: int
    closed_trades: int
