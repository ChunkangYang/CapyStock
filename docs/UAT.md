# CapyStock — User Acceptance Test (UAT)

**版本**：v1.0（重建版）
**最後更新**：2026-05-04
**對應實裝範圍**：Pre-S1（CLI 核心）+ Milestone 3（S1–S8）+ Milestone 4（S9–S13）+ Milestone 5（S14–S18）+ Milestone 6（S19–S23）+ Milestone 7（S24）

---

## 一、UAT 目的與範圍

驗收 CapyStock 全部已實裝功能在「使用者操作層」是否符合預期，包含：
- CLI 核心命令（追蹤清單、check、edinet、fundamental、log）
- Backend API（FastAPI）
- 前端 Web UI（SvelteKit SPA）
- 排程 / 通知 / 部署
- 資料 ingest / 異常偵測 / 策略 sweep / 資料管理面板

不在範圍內：
- 內部單元測試（已由 `tests/` 涵蓋）
- 程式碼品質、效能基準

---

## 二、測試環境準備

### 2.1 環境需求
| 項目 | 要求 |
|---|---|
| OS | Windows 11 / macOS / Linux |
| Python | 3.10+ |
| Node | 18+ |
| 瀏覽器 | Chrome / Edge 最新版 |

### 2.2 啟動步驟
```bash
# Backend
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev
# 預設 http://localhost:5173
```

### 2.3 必要設定
- `data/.env` → `EDINET_API_KEY=<key>`（測 EDINET 用）
- `data/watchlist.json` 至少包含 1–2 檔股票（建議：7203、9432）
- 可選：`data/cache/{CODE}_margin.csv`、`{CODE}_flow.csv`

### 2.4 通過判定
- ✅ Pass：實際結果完全符合「預期結果」
- ⚠️ Partial：主要符合但有非阻斷瑕疵 → 開 IMP-XXX
- ❌ Fail：阻斷使用 → 開 BUG-XXX

---

## 三、UAT 測試案例

> 證據存放：`docs/EVIDENCES/UAT_<TC-ID>.md`
> 命名規則：`TC-<area>-<seq>`，area 對應功能群組

---

### 群組 A：CLI 核心（Pre-S1）

#### TC-CLI-01 追蹤清單管理
**前置**：清空 `data/watchlist.json`
**步驟**：
1. `python -m capystock.main add 7203 2500`
2. `python -m capystock.main add 9432 150`
3. `python -m capystock.main list`
4. `python -m capystock.main remove 7203`
5. `python -m capystock.main list`

**預期**：
- 步驟 3 列出兩檔，含追蹤起始價 2500 / 150
- 步驟 5 僅剩 9432

#### TC-CLI-02 check 主流程（kabutan）
**步驟**：`python -m capystock.main check`
**預期**：
- 對清單每檔輸出表格（股價、近日漲跌、信號）
- 若 kabutan 失敗自動 fallback 到 yfinance（觀察 log 訊息）
- 三選二警告 / 停損 / 吃貨訊號正確標示

#### TC-CLI-03 check 單一股票 + EDINET
**步驟**：`python -m capystock.main check --code 7203 --edinet-days 7`
**預期**：
- 僅檢查 7203
- 表格附帶近 7 日 EDINET 大量保有報告（350/360）摘要

#### TC-CLI-04 EDINET 獨立查詢
**步驟**：`python -m capystock.main edinet --days 30 --all`
**預期**：30 日內全部 5% rule 申報列表，可看到 docTypeCode、提出者、対象証券コード

#### TC-CLI-05 fundamental 評分
**步驟**：`python -m capystock.main fundamental 3543`
**預期**：
- 顯示 8 指標分數
- 評等為 STRONG / HEALTHY / CAUTION / RISKY 之一
- 即使部分指標缺值，仍可輸出 Partial Data 評分（S24 驗證點）

#### TC-CLI-06 log 警示歷史
**前置**：先執行 check 數次累積 log
**步驟**：`python -m capystock.main log --days 30`
**預期**：依日期排序輸出 30 日內所有警示

---

### 群組 B：Backend API（M3 / S1–S3）

#### TC-API-01 健康檢查
**步驟**：GET `http://localhost:8000/health`
**預期**：200，回傳 `{"status":"ok",...}`

#### TC-API-02 OpenAPI 文件
**步驟**：開啟 `/docs`
**預期**：Swagger UI 顯示所有 router（watchlist、signals、dividend、scan、favorites、simulation、notify、scheduler、health、indicators、compare、ingest、analytics、sweep、data）

#### TC-API-03 Watchlist CRUD
**步驟**：
1. POST `/watchlist` body `{"code":"7203","entry_price":2500}`
2. GET `/watchlist`
3. DELETE `/watchlist/7203`

**預期**：對應寫入 / 讀取 / 刪除 `data/watchlist.json`

#### TC-API-04 全市場掃描快照
**步驟**：
1. 執行掃描 worker 產生 snapshot
2. GET `/scan/signals`、`/scan/dividend?order_by=est_yield&desc=true`

**預期**：回傳當日 snapshot；無快照時 404 並含明確訊息

#### TC-API-05 Favorites
**步驟**：
1. POST `/favorites/7203`
2. GET `/favorites` → 應為 array
3. DELETE `/favorites/7203`

**預期**：array 形式正確（BUG-001 防回歸）

---

### 群組 C：前端 SPA — 首頁與導航（S4）

#### TC-UI-01 首頁載入
**步驟**：開啟 `/`
**預期**：
- 載入無 console 錯誤
- 顯示「追蹤清單」、「Top Signals」、「Top Dividend」三區塊
- 無 snapshot 時顯示「尚無快照，請至資料管理」提示而非整頁錯誤

#### TC-UI-02 SPA 路由 fallback
**步驟**：直接於瀏覽器網址列輸入 `/signals/7203` 並重新整理
**預期**：FastAPI catch-all 回傳 SPA index，路由正常解析（不出現 FastAPI 404 JSON）

#### TC-UI-03 全域導航
**步驟**：點擊側欄 / 上方所有連結
**預期**：投機（Signals）/ 金雞（Dividend）/ 比較 / 模擬 / Sweep / 資料 / 設定 全部可達且高亮目前頁

---

### 群組 D：投機儀表板（S5 / S17）

#### TC-SIG-01 列表頁
**步驟**：`/signals`
**預期**：
- 表格依 score 排序
- 可篩選 / 翻頁
- 無 snapshot 時顯示空狀態指引

#### TC-SIG-02 個股頁
**步驟**：`/signals/7203`
**預期**：
- 上方 K 線 / 收盤折線
- 指標 toolbar：RSI / MACD / BB / SMA / EMA / ATR / KD 可勾選
- 勾選後對應子圖（RSI / MACD Panel）顯示
- 指標訊號卡片（買賣建議）顯示

#### TC-SIG-03 收藏切換
**步驟**：點 ★
**預期**：立即變色，重新整理仍保留（store 為 Record-based，FavoriteToggle 不噴 `r.filter is not a function`）

---

### 群組 E：金雞儀表板（S6）

#### TC-DIV-01 列表頁
**步驟**：`/dividend`
**預期**：欄位含 est_yield、payout_ratio、健康評等；可排序

#### TC-DIV-02 個股頁
**步驟**：`/dividend/7203`
**預期**：歷史配息、殖利率走勢、基本面 8 指標雷達 / 表格

---

### 群組 F：比較模式（S16）

#### TC-CMP-01 投機對比
**步驟**：`/compare?codes=7203,9432,6758`
**預期**：相關性矩陣熱圖 + 對齊後價格走勢

#### TC-CMP-02 金雞對比
**步驟**：`/dividend/compare?codes=7203,9432`
**預期**：殖利率 / 配息歷史對比表

---

### 群組 G：模擬交易（S7 / S8 / S18）

#### TC-SIM-01 建立模擬（基本）
**步驟**：`/simulation/new` → Step1 標的 → Step2 區間/資金 → Step3 條件 → 送出
**預期**：跳轉 `/simulation/[id]` 顯示權益曲線、交易明細、績效指標

#### TC-SIM-02 技術指標條件
**步驟**：Step3 加入 `RSI < 30 進場`、`RSI > 70 出場`
**預期**：報告中 strategy_type 標示為「技術指標」，出場原因分布含 indicator_exit

#### TC-SIM-03 模擬列表
**步驟**：`/simulation`
**預期**：列出 `data/simulations/*.json` 全部結果，可點入

---

### 群組 H：策略 Sweep（S22）

#### TC-SWP-01 啟動 sweep
**步驟**：`/simulation/sweep` 設定 ParamGrid（如 RSI 進場 25/30/35 × 出場 65/70/75）→ Run
**預期**：
- SSE 即時更新進度
- 完成後顯示熱圖（兩參數網格 × Sharpe / 報酬）
- 排行榜 Top N

#### TC-SWP-02 取消 sweep
**步驟**：執行中按取消
**預期**：DELETE `/sweep/{job_id}` 成功，UI 回到 idle

---

### 群組 I：通知與排程（S9–S12）

#### TC-NTF-01 通道設定
**步驟**：`/settings/notifications` → 啟用 Email、填寫 SMTP；啟用 LINE Notify token
**預期**：寫入設定檔；連線測試按鈕顯示成功 / 失敗

#### TC-NTF-02 規則
**步驟**：建立規則「投機 score≥80 即時 push」、「每日 18:00 digest」
**預期**：保存後可見列表；可啟停

#### TC-NTF-03 排程
**步驟**：`/settings/scheduler` 啟用 daily_pipeline，設 09:30 / 18:00
**預期**：APScheduler 註冊；下次執行時間正確顯示

#### TC-NTF-04 健康監控
**步驟**：`/settings/health`
**預期**：顯示最近 N 次 job 執行紀錄、成功 / 失敗、耗時、錯誤訊息

---

### 群組 J：資料 Ingest（S19 / S20 / S23）

#### TC-ING-01 信用残自動抓取
**步驟**：`/data/ingest` 選 7203 → margin → Run
**預期**：fallback chain（yahoo → minkabu）任一成功即寫入 `data/cache/7203_margin.csv`；UI 顯示來源與筆數

#### TC-ING-02 投資部門別（個股估算）
**步驟**：同頁，選 flow → Run
**預期**：寫入 `{code}_flow.csv`

#### TC-ING-03 JPX 週報
**步驟**：POST `/ingest/jpx-weekly`（或 UI 觸發）
**預期**：下載解析 Excel；GET `/ingest/market-flow` 可讀取

#### TC-ING-04 手動上傳
**步驟**：`/data/upload` 拖入 CSV（含 alias 欄名如 `週,信用買残,信用売残`）
**預期**：預覽欄位 normalize 後正確；確認後寫入 cache

#### TC-ING-05 資料總覽
**步驟**：`/data`
**預期**：每檔股票顯示 price / margin / flow cache 狀態與最新日期；過舊以紅 / 黃顏色警示

#### TC-ING-06 批量 ingest（SSE）
**步驟**：`/data/ingest` 全選 → Run All
**預期**：SSE 即時逐檔回報成功 / 失敗

---

### 群組 K：分析增強（S15 / S21）

#### TC-ANL-01 指標 API
**步驟**：GET `/indicators/7203?series=rsi,macd,bb`
**預期**：JSON 含時序，數值與 capystock 計算一致

#### TC-ANL-02 異常偵測
**步驟**：GET `/analytics/anomaly/7203?days=60`
**預期**：列出 volume_spike / price_jump / gap_up / gap_down 事件，附 z-score

#### TC-ANL-03 事件研究
**步驟**：POST `/analytics/event-study/7203` body 含事件日期清單
**預期**：回傳 AR / AAR / CAR 序列（事件窗口 ±N 日）

---

### 群組 L：基本面（S24）

#### TC-FUN-01 IR Bank 橫向表格解析
**步驟**：`python -m capystock.main fundamental 3543`（コメダHD）
**預期**：成功評分（先前舊解析會失敗，S24 修復點）；顯示完整 8 指標

#### TC-FUN-02 Partial Data
**步驟**：對僅有 5–6 項可解析的個股執行 fundamental
**預期**：缺項標 N/A，仍輸出加權評等而非整體失敗

---

### 群組 M：部署（S13）

#### TC-DEP-01 Docker
**步驟**：`docker compose up`（依 SPRINT_13.md）
**預期**：API + 前端容器啟動，`http://localhost` 可達

#### TC-DEP-02 Windows NSSM
**步驟**：依文件以 NSSM 註冊 `CapyStockAPI` service
**預期**：開機自動啟動，service 狀態 RUNNING

---

### 群組 N：跨功能 / 回歸（BUG-001 防呆）

#### TC-REG-01 Toast 動畫
**步驟**：觸發任一通知 toast
**預期**：fade-in / fade-out 平滑，無閃爍

#### TC-REG-02 Channel dot 即時更新
**步驟**：`/settings/notifications` 切換通道狀態
**預期**：頁首通道狀態小點即時換色，無需重新整理

#### TC-REG-03 SPA 直連深層路由
**步驟**：直接於網址列輸入 `/dividend`、`/signals`、`/signals/7203` 重新整理
**預期**：均 200，空狀態正確顯示「尚無快照」（2026-05-04 已驗證）

---

## 四、UAT 簽核

| 角色 | 姓名 | 日期 | 結果 |
|---|---|---|---|
| 開發 | | | |
| QA | | | |
| Owner | | | |

---

## 五、附錄

### 5.1 已知限制（HUMAN_TODO）
- kabutan 個股信用残歷史 / 投資部門別為 Premium → 改由 ingest 層或本地 CSV
- LINE Notify 已於 2025 中止 → 測試需以替代 webhook 驗證
- 完整測試 EDINET 需有效 API key

### 5.2 證據檔規範
- 路徑：`docs/EVIDENCES/UAT_<TC-ID>.md`
- 內容：操作步驟截圖 / log / curl 回應 / 結論（Pass / Partial / Fail）
- Fail 時連結至開出的 BUG-XXX.md
