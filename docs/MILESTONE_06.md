# Milestone 6 — 資料源擴展 + 進階分析

## 規劃決策（已確認）
- 信用残資料：**半自動 import**（Yahoo Finance Japan / Minkabu 爬蟲嘗試 + 手動 CSV 上傳兜底）
- 投資部門別：同上策略，使用 JPX 公開週報 PDF / Excel 解析
- 進階分析：**事件研究（event study）**、**異常成交量偵測**、**選股回測 sweep**
- 多帳戶：本 Milestone 不做（單使用者）

## Sprint 範圍與大綱

| Sprint | 主題 | 詳細設計 |
|---|---|---|
| S19 | 信用残自動抓取（多來源 ingest 層） | [SPRINT_19.md](SPRINT_19.md) |
| S20 | 投資部門別 ingest（JPX 週報） | [SPRINT_20.md](SPRINT_20.md) |
| S21 | 異常偵測 + 事件研究 | [SPRINT_21.md](SPRINT_21.md) |
| S22 | 策略參數 Sweep（網格回測） | [SPRINT_22.md](SPRINT_22.md) |
| S23 | 資料管理面板 + 上傳介面 | [SPRINT_23.md](SPRINT_23.md) |

## 整體架構新增

```
CapyStock/
├── capystock/ingest/                    # ★新增 資料引入層
│   ├── base.py                          # IngestionSource ABC
│   ├── yahoo_jp_margin.py / minkabu_margin.py
│   ├── jpx_flow.py / manual_csv.py
├── api/
│   ├── services/
│   │   ├── ingest_service.py / event_study_service.py
│   │   ├── anomaly_service.py / strategy_sweep_service.py
│   ├── routers/ingest.py / analytics.py / sweep.py
│   └── schemas/ingest.py / analytics.py / sweep.py
├── frontend/src/routes/
│   ├── data/ +page / ingest / upload
│   ├── analytics/ event-study / anomaly
│   └── simulation/sweep/+page.svelte
```

## 跨 Sprint 共通約定

### 爬蟲倫理
- 任何新 source 都需 `time.sleep(REQUEST_DELAY_SECONDS)`
- USER_AGENT 一律 `config.USER_AGENT`（聲明用途 + 聯絡方式）
- robots.txt 違反者直接不實作

### 估算資料標記
- 任何「估算」資料（如部門別 flow 估算）必須在 schema 上有 `estimated: bool` 欄位
- UI 上虛線 / 角標 / tooltip 三重提示

### 並行
- 一律 `concurrent.futures.ProcessPoolExecutor`，避免 GIL 限制
- 子程序內不能讀全域 `Settings`，需透過 pickle-able 參數傳

## 順序建議
1. **S19 → S20**：ingest 層獨立可驗證
2. **S21**：分析服務（依賴 ingest 的資料完整性）
3. **S22**：sweep（依賴 simulation engine M3、indicator M5）
4. **S23**：資料 UI（最後做）

## Milestone 全圖

| Milestone | 主題 | Sprint | 狀態 |
|---|---|---|---|
| M1 | CLI + 核心爬蟲 + EDINET | （pre-S1）| ✅ |
| M2 | 基本面分析 fundamental | （pre-S1）| ✅ |
| M3 | Web UI（FastAPI + SvelteKit）| S1–S8 | ✅ |
| M4 | 自動化、排程、通知 | S9–S13 | 🟡 進行中 |
| M5 | 技術指標 + 比較模式 | S14–S18 | 規劃中 |
| M6 | 資料源擴展 + 進階分析 | S19–S23 | 規劃中 |

往後若要再擴：
- **M7（候選）**：多帳戶 / 雲端部署 / 行動 App
- **M8（候選）**：機器學習選股
- **M9（候選）**：選擇權 / 信用交易模擬
