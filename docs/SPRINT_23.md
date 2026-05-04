# Sprint 23 — 資料管理面板 + 上傳介面

依賴：[MILESTONE_06.md](MILESTONE_06.md)

## 目的
- 集中管理：使用者可以一頁看到「每檔股票 cache 何時更新、缺什麼」
- 補資料：批量觸發 ingest / 上傳

## 路由
- `/data`（總覽）
- `/data/ingest`（批量抓取）
- `/data/upload`（拖拉上傳）

## `/data` 總覽
- 表格：Code / Name / price 最新日期 / margin 最新週 / flow 最新日期 / fundamental 上次更新 / 操作（重抓 / 上傳）
- 顏色：> 7 日未更新 = 黃；> 30 日 = 紅
- 篩選：watchlist / favorites / 全部

## `/data/ingest`
- 多選 codes + 多選 kinds（margin / flow / fundamental / price）
- 「執行」→ SSE 進度
- 完成後表格：每 (code, kind) 一行，source / rows / ok / error

## `/data/upload`
- 拖拉區：接受 csv / xlsx
- 自動偵測 code（從檔名 `{CODE}_margin.csv` 或讓使用者選）
- 預覽前 10 列 + 欄位 mapping UI
- 確認後 `POST /ingest/upload`

## Endpoints
| Method | Path | 說明 |
|---|---|---|
| GET | `/api/v1/data/overview?scope=watchlist` | 各 code 各 kind 的 cache 狀態 |
| POST | `/api/v1/data/batch-ingest` | body `{codes, kinds}`：批量觸發；回 job_id |
| GET | `/api/v1/data/batch-ingest/{job_id}/stream` | SSE |

## 驗收

`pytest tests/api/test_data_router.py -v`：
- overview 回每 code 4 個 kind，age_days 欄位
- batch-ingest 5 codes × 2 kinds = 10 task，全部成功；其中 1 個失敗仍繼續、result 標 ok=false

`npm run test:e2e` 通過 `e2e/data.spec.ts`：
1. `/data`：表格 row 數 = watchlist size；顏色驗證（mock 一檔 35 日舊 → 紅 cell）
2. `/data/ingest`：選 3 codes 1 kind → 執行 → SSE 進度 → 完成
3. `/data/upload`：拖拉 CSV → 預覽 10 列 → mapping → 上傳 → toast 成功
4. 截圖：2 張
