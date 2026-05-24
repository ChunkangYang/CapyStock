#!/usr/bin/env bash
# CapyStock 容器管理腳本
# 用法：
#   ./start.sh          — 啟動容器（已在跑則跳過）
#   ./start.sh update   — git pull + rebuild image + 重啟容器
#   ./start.sh restart  — 不 pull / 不 rebuild，只重啟容器
#   ./start.sh stop     — 停止容器
#   ./start.sh logs     — 追蹤 log（Ctrl-C 離開）

set -euo pipefail

SERVICE=capystock

case "${1:-start}" in

  start)
    echo "[capystock] 啟動容器..."
    docker compose up -d
    echo "[capystock] 容器已啟動，服務位於 http://localhost:8000"
    ;;

  update)
    echo "[capystock] 拉取最新程式碼..."
    git pull

    echo "[capystock] 重新建置 image..."
    docker compose build

    echo "[capystock] 重啟容器..."
    docker compose up -d

    echo "[capystock] 更新完成，服務位於 http://localhost:8000"
    ;;

  restart)
    echo "[capystock] 重啟容器..."
    docker compose restart "$SERVICE"
    echo "[capystock] 重啟完成"
    ;;

  stop)
    echo "[capystock] 停止容器..."
    docker compose stop
    echo "[capystock] 已停止"
    ;;

  logs)
    docker compose logs -f "$SERVICE"
    ;;

  *)
    echo "用法: $0 {start|update|restart|stop|logs}"
    exit 1
    ;;

esac
