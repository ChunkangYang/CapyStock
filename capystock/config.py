"""可調整的判斷參數與爬蟲設定。"""
import os
from pathlib import Path

# --- 檔案路徑 ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
WATCHLIST_PATH = DATA_DIR / "watchlist.json"
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
STOP_LOSS_DROP_PCT = 0.05
STOP_LOSS_CONSECUTIVE_DAYS = 2

# --- 吃貨訊號 ---
ACCUMULATION_INSTITUTIONAL_BUY_DAYS = 5
