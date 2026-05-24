"""FastAPI 應用入口。"""
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.routers import (
    analytics, compare, data, dividend, exit_strategy, favorites, health, indicators, ingest, meta, notify, portfolio, scan, scheduler, signals, simulation, sweep, watchlist,
)
from api.services import scheduler_service as scheduler_service_module


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.environ.get("CAPYSTOCK_SCHEDULER_DISABLED") != "1":
        try:
            scheduler_service_module.get_scheduler_service().start()
            print("[scheduler] started")
        except Exception as e:
            print(f"[scheduler] startup failed: {e}")
    yield
    try:
        scheduler_service_module.get_scheduler_service().stop()
    except Exception:
        pass


app = FastAPI(
    title="CapyStock API",
    description="日股籌碼分析工具 API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS（開發階段允許 localhost:5173 前端）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 註冊路由
app.include_router(meta.router, prefix="/api/v1", tags=["meta"])
app.include_router(watchlist.router, prefix="/api/v1", tags=["watchlist"])
app.include_router(signals.router, prefix="/api/v1", tags=["signals"])
app.include_router(dividend.router, prefix="/api/v1", tags=["dividend"])
app.include_router(scan.router, prefix="/api/v1", tags=["scan"])
app.include_router(favorites.router, prefix="/api/v1", tags=["favorites"])
app.include_router(simulation.router, prefix="/api/v1", tags=["simulation"])
app.include_router(notify.router, prefix="/api/v1", tags=["notify"])
app.include_router(scheduler.router, prefix="/api/v1", tags=["scheduler"])
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(indicators.router, prefix="/api/v1", tags=["indicators"])
app.include_router(compare.router, prefix="/api/v1", tags=["compare"])
app.include_router(ingest.router, prefix="/api/v1", tags=["ingest"])
app.include_router(analytics.router, prefix="/api/v1", tags=["analytics"])
app.include_router(sweep.router, prefix="/api/v1", tags=["sweep"])
app.include_router(data.router, prefix="/api/v1", tags=["data"])
app.include_router(portfolio.router, prefix="/api/v1", tags=["portfolio"])
app.include_router(exit_strategy.router, prefix="/api/v1", tags=["exit_strategy"])


_FRONTEND_DIR = Path(
    os.environ.get("CAPYSTOCK_FRONTEND_DIR")
    or Path(__file__).resolve().parent.parent / "frontend" / "dist"
)
_FRONTEND_INDEX = _FRONTEND_DIR / "index.html"

# SvelteKit adapter-static (fallback mode) 只產生一份 index.html 作為 SPA 殼，
# 其餘 client-side route（/dividend、/signals/{code} …）需後端把未知 path 都回傳 index.html，
# 由 SvelteKit runtime 在瀏覽器端解析路由。FastAPI StaticFiles(html=True) 不支援這種 fallback，
# 所以這裡顯式：靜態資產目錄各自 mount，其餘走 catch-all → index.html。
if _FRONTEND_INDEX.exists():
    # 直接掛 SvelteKit build 出的資產目錄（hash 化檔名，可長期快取）
    app.mount(
        "/_app",
        StaticFiles(directory=str(_FRONTEND_DIR / "_app")),
        name="sveltekit-app",
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        # /api/* 已由上方 router 處理；走到這裡代表 router 沒匹配到，回 404 而非 SPA 殼，
        # 避免前端誤把 JSON 404 當成 HTML 頁面。
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")

        # docs 相關路徑由 FastAPI 自身處理，不會走到這裡；保險起見也排除。
        if full_path in {"docs", "redoc", "openapi.json"}:
            raise HTTPException(status_code=404, detail="Not Found")

        # 1. 嘗試對應 build 目錄下的實體檔案（favicon、prerender 過的 .html、其他 asset）
        candidate = (_FRONTEND_DIR / full_path).resolve()
        try:
            candidate.relative_to(_FRONTEND_DIR.resolve())  # 防 path traversal
        except ValueError:
            raise HTTPException(status_code=404, detail="Not Found")
        if candidate.is_file():
            return FileResponse(candidate)

        # 2. 否則回 SPA 殼，由 SvelteKit client router 處理
        return FileResponse(_FRONTEND_INDEX)
else:
    @app.get("/")
    def root():
        """根路由（frontend 尚未 build）。"""
        return {
            "name": "CapyStock API",
            "docs": "/docs",
            "openapi": "/openapi.json",
            "frontend": "not built — run `make build` or `cd frontend && npm run build`",
        }
