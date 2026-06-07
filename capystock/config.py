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

# --- 吃貨訊號（籌碼沉澱）---
# 原定義依賴「外資/法人連買」flow 資料，但該資料源是全市場數字蓋到每檔（非個股），
# 已棄用。改用「真實個股」三要素近似主力吸籌：信用残(融資餘額)下降 + 股價撐住 + 量能維持。
# 邏輯：融資餘額連續下降代表散戶浮額釋出/沉澱，同期股價不跌且量能未崩 → 籌碼被強手承接。
ACCUM_MARGIN_DECLINE_WEEKS = 3        # 融資餘額(margin_long)連續下降週數
ACCUM_PRICE_HOLD_LOOKBACK_DAYS = 15   # 股價撐住的回看交易日（約 3 週）
ACCUM_PRICE_HOLD_MIN_PCT = 0.0        # 最新價相對 lookback 前須 >= 此漲幅（0 = 未跌即可）
ACCUM_VOLUME_RATIO = 0.8             # 近 5 日均量 >= 過去 20 日均量 × 此比率（量能未崩）

# --- 風報比（第十一篇）---
RISK_REWARD_MIN_RATIO = 3.0  # < 1:3 進場前提示

# --- 每日三盤濾網選股（第二篇 / 第十四節「三盤濾網選股」日本對映）---
# 第一盤 連續性：同一 EDINET 申報人（5% rule）在窗口內重複申報（350/360）視為主力連續建倉。
#   日股無「券商分點」，以同一申報人重複出現在大量保有/変更報告書近似「同一分點連續買超」。
POCKET_GATE1_MIN_FILINGS = 2          # 同一申報人在窗口內最少申報次數
POCKET_GATE1_WINDOW_DAYS = 60         # EDINET 回看窗口（日曆日）
# 第二盤 成本：主力成本以「申報日當天/鄰近收盤均價」近似，現價不可高於主力成本 +5%。
POCKET_GATE2_COST_TOLERANCE_PCT = 0.05  # 現價 <= 主力成本 ×(1+此值) 才過關
# 第三盤 戶數/籌碼集中：信用残(融資 margin_long)連續下降代表浮額釋出、籌碼集中。
POCKET_GATE3_MARGIN_DECLINE_WEEKS = 3   # 融資餘額連續下降週數

# --- 三階段移動停損（Chandelier Exit）---
# Stage 1（profit < STAGE2）：max(進場×(1-STOP_LOSS_DROP_PCT), 進場 - INITIAL_STOP_ATR_MULT×ATR)
# Stage 2（STAGE2 ≤ profit < STAGE3）：停損移到進場價（保本）
# Stage 3（profit ≥ STAGE3）：Chandelier = max(近 CHANDELIER_HIGH_WINDOW 日 high) - CHANDELIER_ATR_MULT×ATR
ATR_PERIOD = 14
INITIAL_STOP_ATR_MULT = 3.0
CHANDELIER_ATR_MULT = 2.5
CHANDELIER_HIGH_WINDOW = 20
TRAILING_STAGE2_THRESHOLD = 0.10  # +10% 進入保本
TRAILING_STAGE3_THRESHOLD = 0.25  # +25% 啟動 Chandelier

# --- 技術破位減碼警示 ---
SMA_BREAK_PERIOD = 20  # 跌破 SMA20 且向下走平
VOLUME_DRY_DAYS = 5
VOLUME_DRY_RATIO = 0.5  # 連續 N 日量能 < 5 日均量 × 0.5

# --- 出場策略 override 檔（Phase 2 動態調參）---
EXIT_STRATEGY_OVERRIDE_PATH = DATA_DIR / "exit_strategy.json"


def load_exit_strategy_override() -> dict:
    """從 data/exit_strategy.json 讀使用者覆寫的出場參數。

    回傳 dict，若檔案不存在或解析失敗則回空 dict（使用 config 預設）。
    """
    import json
    if not EXIT_STRATEGY_OVERRIDE_PATH.exists():
        return {}
    try:
        return json.loads(EXIT_STRATEGY_OVERRIDE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def get_exit_param(key: str, default):
    """取出場參數：優先用 exit_strategy.json，否則用 config 預設。"""
    return load_exit_strategy_override().get(key, default)
