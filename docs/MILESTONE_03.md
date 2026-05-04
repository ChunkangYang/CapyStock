# Milestone 3 — Web UI（FastAPI + SvelteKit）

## 規劃決策（已確認）
- 技術棧：**FastAPI（後端）+ SvelteKit（前端）**
- 模擬模式：**回測（backtest）+ 前進模擬（paper trading）兩者皆做**
- 進場價規則：**使用者可選**（訊號當日收盤 / 隔日開盤 / 自訂價）

## Sprint 範圍與大綱

| Sprint | 主題 | 詳細設計 |
|---|---|---|
| S1 | Backend API 骨架 + 既有功能 service 化 | [SPRINT_01.md](SPRINT_01.md) |
| S2 | 全市場掃描 worker + 每日快照 | [SPRINT_02.md](SPRINT_02.md) |
| S3 | Favorites API + watchlist 整合 | [SPRINT_03.md](SPRINT_03.md) |
| S4 | SvelteKit 前端骨架 | [SPRINT_04.md](SPRINT_04.md) |
| S5 | 進出場信號儀表板（投機） | [SPRINT_05.md](SPRINT_05.md) |
| S6 | 金雞高股息儀表板 | [SPRINT_06.md](SPRINT_06.md) |
| S7 | 模擬交易引擎（後端） | [SPRINT_07.md](SPRINT_07.md) |
| S8 | 模擬交易 UI | [SPRINT_08.md](SPRINT_08.md) |

## 整體架構

```
CapyStock/
├── capystock/                    # (現有) CLI / 業務邏輯核心
├── api/                          # ★新增 FastAPI 服務
│   ├── main.py / deps.py
│   ├── schemas/                  # Pydantic models
│   ├── routers/                  # watchlist / signals / dividend / favorites / scan / simulation / meta
│   ├── services/                 # signal / dividend / scan / favorite / simulation / backtest_engine
│   └── workers/                  # scan_worker / paper_worker
├── frontend/                     # ★新增 SvelteKit
│   ├── src/lib/                  # api.ts / types.ts / stores / components
│   └── src/routes/               # +layout / signals / dividend / favorites / simulation
├── data/
│   ├── favorites.json            # ★新增
│   ├── scan_snapshots/*.parquet  # ★新增
│   ├── simulations/{sim_id}.json # ★新增
│   └── universe.csv              # ★新增
```

### API base URL
- 開發：`http://localhost:8000`，前端 dev `http://localhost:5173`，Vite proxy `/api → :8000`
- CORS：dev 階段允許 `localhost:5173`，prod 同源
- 命名前綴：所有 API 路由 `/api/v1/`

## 跨 Sprint 共通約定

### 錯誤處理
- 後端 service 失敗 → raise `HTTPException(status_code=4xx/5xx, detail="...")`
- 前端 `api()` throw → 上層用 `try/catch`，畫面顯示 toast

### 日期格式
- 所有 API 出入皆 ISO 8601 字串（`2026-04-25`）
- 前端用原生 Date + `Intl.DateTimeFormat('ja-JP')`

### 後端測試規則
1. **隔離 data 目錄**：`conftest.py` 提供 `tmp_data_dir` fixture，monkeypatch `config.DATA_DIR` 等到 tmp
2. **禁止外部網路**：`autouse=True` fixture 將 `requests.get` 設為丟錯，所有測試必須用 fixture CSV 餵 mock 資料
3. **FastAPI**：用 `from fastapi.testclient import TestClient`
4. **覆蓋率門檻**：`pytest --cov=api --cov-fail-under=80`
5. **判斷邏輯**：`backtest_engine` 必須有確定性測試
6. backtest_engine 不應呼叫 `datetime.now()` / `date.today()` — 一律從參數注入 `as_of`

### 前端測試規則
1. **單元測試（vitest）**：`lib/api.ts` mock fetch；stores 驗 add/remove；元件用 `@testing-library/svelte`
2. **E2E 測試（Playwright）**：後端 fixture data dir 跑 `:8000`、前端 `npm run preview` 跑 `:4173`；`playwright.config.ts` 用 `webServer` 自動拉起
3. **截圖回歸**：視覺差 > 0.1% 失敗

### 開發指令
```
uvicorn api.main:app --reload --port 8000
cd frontend && npm run dev
python -m api.workers.scan_worker --kind signals
python -m api.workers.paper_worker
```

### 測試指令
```
pytest tests/ -v --cov=api --cov-fail-under=80
cd frontend && npm run test:unit -- --run
cd frontend && npm run test:e2e
```

### 部署
- 前端 `npm run build` → adapter-static 輸出 `frontend/build`
- 後端 mount static：`app.mount("/", StaticFiles(directory="frontend/build", html=True))`
- 單一 uvicorn 起整個服務

## 給實作者的順序建議
1. **S1 → S2 → S3**：純後端可獨立驗證（curl）
2. **S4**：前端骨架，後續每個 sprint 邊加頁
3. **S5、S6**：可平行
4. **S7 → S8**：模擬交易最後做（依賴前面所有 service）
