# Sprint 13 — 部署整合 + 文件

依賴：[MILESTONE_04.md](MILESTONE_04.md)

## 目的
把 M1–M4 所有元件打包成「一鍵啟動」服務（不為了上 cloud，為了使用者重灌時能 5 分鐘恢復）。

## 檔案
- `Dockerfile`（multi-stage：node build frontend → python runtime + adapter-static 輸出）
- `docker-compose.yml`（單 service + volume mount `data/`）
- `Makefile`：`make dev` / `make test` / `make build` / `make run`
- `docs/DEPLOY.md`：部署手冊
- `docs/USER_GUIDE.md`：使用者手冊（CLI + Web UI 並列）
- `docs/ARCHITECTURE.md`：模組關係圖（Mermaid）

## 部署模式

### 模式 A：本機 Python（首選）
```
pip install -r requirements.txt
cd frontend && npm install && npm run build
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

### 模式 B：Docker
```
docker compose up -d
# 預設 port 8000；data/ 掛載為 volume
```

### 模式 C：Windows 服務
- 用 `nssm` 把 `uvicorn` 註冊為服務
- 範本：`docs/DEPLOY/nssm_install.ps1`

## 驗收（半自動）

- `make test` 一次跑完 backend pytest + frontend unit + e2e
- `docker build .` 成功；`docker run -p 8000:8000 -v $(pwd)/data:/app/data capystock` 起來後 `curl /api/v1/health` 回 200
- `frontend/build` 內 `index.html` 存在且被 FastAPI mount 在 `/`
- 使用者手冊章節：安裝、`add` / `check` / web UI 走過、設定通知、設定排程、模擬交易
- 部署手冊章節：環境變數總表、port、log 位置、備份 `data/` 建議

## 自動化測試
- `tests/e2e/test_smoke_after_build.py`（pytest + httpx）：build docker image，subprocess 起 container，30 秒內 healthcheck 200，清理
- `tests/integration/test_full_pipeline.py`：起 in-process FastAPI + scheduler disabled，呼叫 `daily_pipeline.run(today, dry_run=True)`，斷言 summary 各欄位 > 0、notification log 有 dry-run 記錄
