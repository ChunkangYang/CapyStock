"""可調整的判斷參數與爬蟲設定。"""
import os
from pathlib import Path

# --- 檔案路徑 ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
WATCHLIST_PATH = DATA_DIR / "watchlist.json"
PORTFOLIO_PATH = DATA_DIR / "portfolio.json"
LOG_PATH = DATA_DIR / "log.csv"
ENV_PATH = DATA_DIR / ".env"
EDINET_CACHE_DIR = CACHE_DIR / "edinet"


def _load_env() -> None:
    """輕量 .env 讀取（避免額外相依 python-dotenv）。"""
    if not ENV_PATH.exists():
        return
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        os.environ.setdefault(k, v)


_load_env()
EDINET_API_KEY = os.environ.get("EDINET_API_KEY", "")

# --- 爬蟲 ---
REQUEST_DELAY_SECONDS = 2.0
REQUEST_TIMEOUT = 15
USER_AGENT = "CapyStock/0.1 (+personal portfolio tracker)"

# --- 持倉出場條件 ---
INSTITUTIONAL_SELL_CONSECUTIVE_DAYS = 3
INSTITUTIONAL_SELL_RATIO_OF_PRIOR_10D_BUY = 0.20

MARGIN_INCREASE_CONSECUTIVE_WEEKS = 3
MARGIN_INCREASE_VS_8W_MEAN = 2.0

PRICE_RISE_FROM_RECENT_LOW = 0.30
PRICE_RECENT_LOW_WINDOW_DAYS = 30

# --- 停損 ---
# 心法 v2 第七篇/第九篇：停損錨點優先順序為
#   1) 使用者指定 stop_price → 直接用
#   2) last_step_price（主力最後一階） → 跌破 LAST_STEP_BREAK_PCT 連 N 日
#   3) master_cost（主力成本）→ 跌破 STOP_LOSS_DROP_PCT 連 N 日
#   4) 都沒有 → fallback 用 start_price（舊行為）
STOP_LOSS_DROP_PCT = 0.05
STOP_LOSS_CONSECUTIVE_DAYS = 2
LAST_STEP_BREAK_PCT = 0.03  # 第七篇：跌破最後一階 3% 視為失守

# --- 時間停損（第九篇）---
# 進場後 N 日股價仍在成本帶內盤整、未突破 → 警告減碼
TIME_STOP_DAYS = 7
TIME_STOP_RANGE_PCT = 0.03  # 相對成本帶 ±3% 內視為盤整

# --- 量能停損（第九篇）---
# 爆量但股價不漲 → 主力可能在出貨
VOLUME_SPIKE_MULTIPLE = 3.0  # vs 近 5 日均量
VOLUME_SPIKE_PRICE_FLAT_PCT = 0.01  # 漲幅 < +1% 視為不漲

# --- 風報比（第十一篇）---
RISK_REWARD_MIN_RATIO = 3.0  # < 1:3 進場前提示

# --- 吃貨訊號 ---
ACCUMULATION_INSTITUTIONAL_BUY_DAYS = 5
