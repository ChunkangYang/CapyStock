"""FastAPI 應用入口。"""
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routers import (
    analytics, compare, dividend, favorites, health, indicators, ingest, meta, notify, scan, scheduler, signals, simulation, sweep, watchlist,
)
from api.services import scheduler_service as scheduler_service_module


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.environ.get("CAPYSTOCK_SCHEDULER_DISABLED") != "1":
        try:
            scheduler_service_module.get_scheduler_service().start()
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


_FRONTEND_DIR = Path(
    os.environ.get("CAPYSTOCK_FRONTEND_DIR")
    or Path(__file__).resolve().parent.parent / "frontend" / "dist"
)

if _FRONTEND_DIR.exists() and (_FRONTEND_DIR / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="frontend")
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
