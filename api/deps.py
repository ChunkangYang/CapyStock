"""依賴注入與全域設定。"""
from pathlib import Path

# FastAPI 會自動重新載入，需要保持穩定的路徑參考
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
