"""FastAPI 應用入口。"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import dividend, favorites, meta, scan, signals, simulation, watchlist

app = FastAPI(
    title="CapyStock API",
    description="日股籌碼分析工具 API",
    version="0.1.0",
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


@app.get("/")
def root():
    """根路由。"""
    return {
        "name": "CapyStock API",
        "docs": "/docs",
        "openapi": "/openapi.json",
    }
