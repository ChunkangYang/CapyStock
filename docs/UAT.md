# CapyStock — User Acceptance Test (UAT)

**版本**：v1.0（重建版）
**最後更新**：2026-05-05
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
python -m uvicorn api.main:app --reload --port 8000

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

**結果**：✅ Pass（2026-05-04）｜證據：[UAT_GROUP_A_CLI.md](EVIDENCES/UAT_GROUP_A_CLI.md)

#### TC-CLI-02 check 主流程（kabutan）
**步驟**：`python -m capystock.main check`
**預期**：
- 對清單每檔輸出表格（股價、近日漲跌、信號）
- 若 kabutan 失敗自動 fallback 到 yfinance（觀察 log 訊息）
- 三選二警告 / 停損 / 吃貨訊號正確標示

**結果**：✅ Pass（2026-05-04）｜kabutan 失敗自動 fallback yfinance，表格欄位完整｜IMP-WIN-001：Windows cp950 console 輸出 UnicodeEncodeError（非阻斷）

#### TC-CLI-03 check 單一股票 + EDINET
**步驟**：`python -m capystock.main check --code 7203 --edinet-days 7`
**預期**：
- 僅檢查 7203
- 表格附帶近 7 日 EDINET 大量保有報告（350/360）摘要

**結果**：✅ Pass（2026-05-04）｜僅輸出 7203，EDINET API 正常呼叫，7203 近 7 日無申報（實際市場狀況，靜默略過屬預期）

#### TC-CLI-04 EDINET 獨立查詢
**步驟**：`python -m capystock.main edinet --days 30 --all`
**預期**：30 日內全部 5% rule 申報列表，可看到 docTypeCode、提出者、対象証券コード

**結果**：✅ Pass（2026-05-04）｜回傳數百筆，欄位含 Date / Code / Kind（新規/変更）/ Filer / URL

#### TC-CLI-05 fundamental 評分
**步驟**：`python -m capystock.main fundamental 3543`
**預期**：
- 顯示 8 指標分數
- 評等為 STRONG / HEALTHY / CAUTION / RISKY 之一
- 即使部分指標缺值，仍可輸出 Partial Data 評分（S24 驗證點）

**結果**：✅ Pass（2026-05-04）｜8 指標顯示（DPS=WARN，其餘 N/A），評等 CAUTION，Partial Data 正常

#### TC-CLI-06 log 警示歷史
**前置**：先執行 check 數次累積 log
**步驟**：`python -m capystock.main log --days 30`
**預期**：依日期排序輸出 30 日內所有警示

**結果**：✅ Pass（2026-05-04）｜依日期升序，涵蓋 stop_loss / exit / edinet_5pct / accumulation / fundamental 各類型

---

### 群組 B：Backend API（M3 / S1–S3）

#### TC-API-01 健康檢查
**步驟**：GET `http://localhost:8000/api/v1/health`（實際前綴 `/api/v1/`）
**預期**：200，回傳 `{"status":"ok",...}`

**結果**：✅ Pass（2026-05-04）｜`HTTP 200 {"status":"ok","version":"0.1.0"}`｜證據：[UAT_GROUP_B_API.md](EVIDENCES/UAT_GROUP_B_API.md)

#### TC-API-02 OpenAPI 文件
**步驟**：開啟 `/docs`
**預期**：Swagger UI 顯示所有 router（watchlist、signals、dividend、scan、favorites、simulation、notify、scheduler、health、indicators、compare、ingest、analytics、sweep、data）

**結果**：✅ Pass（2026-05-04）｜全部 15 個 router tags 存在

#### TC-API-03 Watchlist CRUD
**步驟**：
1. POST `/api/v1/watchlist` body `{"code":"7203","start_price":2500}`（注意：欄位為 `start_price`）
2. GET `/api/v1/watchlist`
3. DELETE `/api/v1/watchlist/7203`

**預期**：對應寫入 / 讀取 / 刪除 `data/watchlist.json`

**結果**：✅ Pass（2026-05-04）｜CRUD 全流程正常｜IMP-DOC-001：UAT 原記 `entry_price`，實際欄位為 `start_price`

#### TC-API-04 全市場掃描快照
**步驟**：
1. 執行掃描 worker 產生 snapshot
2. GET `/api/v1/scan/signals`、`/api/v1/scan/dividend?order_by=est_yield&desc=true`

**預期**：回傳當日 snapshot；無快照時 404 並含明確訊息

**結果**：✅ Pass（2026-05-04）｜signals / dividend 均 200，含 score / est_yield / overall 評等欄位，依 est_yield 降序正確

#### TC-API-05 Favorites
**步驟**：
1. POST `/api/v1/favorites` body `{"code":"7203","tag":"speculative"}`
2. GET `/api/v1/favorites` → 應為 array
3. DELETE `/api/v1/favorites/7203`

**預期**：array 形式正確（BUG-001 防回歸）

**結果**：✅ Pass（2026-05-04）｜GET 回傳 JSON array（BUG-001 防回歸 ✓）｜IMP-DOC-001：POST 路徑應為 `POST /favorites` + body，非路徑參數

---

### 群組 C：前端 SPA — 首頁與導航（S4）

#### TC-UI-01 首頁載入
**步驟**：開啟 `/`
**預期**：
- 載入無 console 錯誤
- 頁面 H1 顯示「Dashboard」
- 顯示四張卡片，標題逐字為：「持倉狀態」、「追蹤清單」、「今日訊號」、「金雞 Top」（卡片標題與側欄連結名稱「持倉管理」/「投機訊號」/「金雞高股息」**不同**，這是設計上的內外命名差異）
- 持倉空狀態文字逐字：「尚無持倉。請至 持倉管理 新增買入記錄。」
- 追蹤清單空狀態文字逐字：「追蹤清單為空。使用 CLI `add` 加入關注股票。」
- 今日訊號 / 金雞 Top 空狀態文字逐字：「暫無訊號」、「暫無資料」
- 無 snapshot 時頁面上方 info banner 文字逐字：「尚無快照，請至資料管理執行掃描或等待 daily_pipeline 排程。」

#### TC-UI-02 SPA 路由 fallback
**步驟**：直接於瀏覽器網址列輸入 `/signals/7203` 並重新整理
**預期**：FastAPI catch-all 回傳 SPA index，路由正常解析（不出現 FastAPI 404 JSON）

#### TC-UI-03 全域導航
**步驟**：點擊側欄所有連結
**預期**：側欄連結文字逐字依序為：Dashboard / 投機訊號 / 投機對比 / 金雞高股息 / 金雞對比 / 持倉管理 / 追蹤清單 / 我的最愛 / 模擬交易 / **資料管理** / 設定 — 全部可達且當前頁高亮（左邊綠色 border + 文字綠）

---

### 群組 D：投機訊號（S5 / S17）

#### TC-SIG-01 列表頁
**步驟**：前往「投機訊號」（`/signals`）
**預期**：
- 頁面 H1 文字逐字：「投機訊號」
- 表格依 score 排序
- 分頁按鈕文字逐字：「全市場訊號」、「我的持倉」、「我的最愛」
- 無 snapshot 時 empty-state 文字逐字：「尚無投機訊號掃描快照。請至 資料管理 或執行掃描排程後再回來。」

#### TC-SIG-02 個股頁
**步驟**：前往「投機訊號」 → 點入個股（`/signals/7203`）
**預期**：
- 上方 K 線（H3 文字逐字「K 線（120 日）」）
- 指標 toolbar 文字逐字：「SMA：」5 / 20 / 60 / 120｜「EMA：」12 / 26｜「布林通道」｜「RSI」｜「MACD」（**目前無 ATR、無 KD**）
- 勾選 RSI / MACD 對應子圖（RSI Panel / MACD Panel）顯示
- 右上角有「對比模式」按鈕與星號 ★ 收藏切換

#### TC-SIG-03 收藏切換
**步驟**：在投機訊號個股頁點 ★
**預期**：立即變色，重新整理仍保留（store 為 Record-based，不噴 `r.filter is not a function`）

---

### 群組 E：金雞高股息（S6）

#### TC-DIV-01 列表頁
**步驟**：前往「金雞高股息」（`/dividend`）
**預期**：
- 頁面 H1 文字逐字：「金雞高股息」
- 表格欄位文字逐字依序：★ / Code / Name / Overall / DPS / Yield / 連無減配 / Payout Avg / 自己資本比 / EPS Growth / 指標
- 篩選器標籤文字逐字：Overall / 殖利率最低值 / 無減配年數 / 自己資本比率 / 配當性向上限 / 只看我的最愛
- 表格可點擊欄位標題排序
- 無 snapshot 時 empty-state 文字逐字：「尚無金雞掃描快照。請至 資料管理 或執行掃描排程後再回來。」

#### TC-DIV-02 個股頁
**步驟**：前往「金雞高股息」 → 點入個股（`/dividend/7203`）
**預期**：頁面區塊 H3 文字逐字：「8 指標雷達圖」、「配當歷史」、「指標評分」、「統計摘要」（**目前無「殖利率走勢」獨立區塊**）；右上角有 Overall 評等與星號 ★ 收藏切換

---

### 群組 F：比較模式（S16）

#### TC-CMP-01 投機對比
**步驟**：前往「投機對比」（`/compare?codes=7203,9432,6758`）
**預期**：
- 頁面 H2 文字逐字：「投機對比」
- 卡片 H3 文字逐字依序：「正規化走勢（期初 = 100）」、相關性矩陣熱圖、「最近指標訊號」
- 上方有 chip 形式股票代碼，下拉選單文字「期間」+ 60 / 120 / 250 日選項

#### TC-CMP-02 金雞對比
**步驟**：前往「金雞對比」（`/dividend/compare?codes=7203,9432`）
**預期**：
- 側欄連結文字為「金雞對比」，但頁面 H2 文字逐字為「**金雞高股息對比**」（內外命名不一致是現況）
- 顯示 DPS（配當）對比表 + 雷達圖對比

---

### 群組 G：模擬交易（S7 / S8 / S18）

#### TC-SIM-01 建立模擬（基本）
**步驟**：前往「模擬交易」（`/simulation`）→ 點右上角「+ 新建模擬」按鈕 → Step1 基本設定（名稱 / kind / 期間 / 資金）→ Step2 候選標的 → Step3 規則與條件 → 送出
**預期**：
- 列表頁 H1 文字逐字：「模擬交易」；建立按鈕文字逐字：「+ 新建模擬」
- 列表表頭文字逐字：名稱 / 類型 / 狀態 / 期間 / 初始資金 / 當前權益 / 報酬 / 操作
- 送出後跳轉 `/simulation/[id]` 顯示權益曲線、交易明細、績效指標

#### TC-SIM-02 技術指標條件
**步驟**：Step3「技術指標條件」區，進場勾選下拉項目「RSI 超賣（< 30）」、出場勾選「RSI 超買（> 70）」
**預期**：
- 下拉選項文字逐字含：「RSI 超賣（< 30）」、「RSI 超買（> 70）」、「MACD 金叉」、「MACD 死叉」、「SMA 交叉」、「布林通道上突破」、「布林通道下突破」
- 報告中 strategy_type 標示為「技術指標」，出場原因分布含 indicator_exit

#### TC-SIM-03 模擬列表
**步驟**：前往「模擬交易」（`/simulation`）
**預期**：列出 `data/simulations/*.json` 全部結果，可點入

---

### 群組 H：策略參數 Sweep（S22）

#### TC-SWP-01 啟動 sweep
**步驟**：前往「模擬交易」→「策略參數 Sweep（網格回測）」（`/simulation/sweep`）→ 設定參數網格（如停損 5/8/10 × 獲利了結 15/20/25）→ 點「執行 Sweep」
**預期**：
- SSE 即時更新進度
- 完成後顯示熱圖（stop_loss × take_profit → 總報酬%）
- 排行榜 Top N

#### TC-SWP-02 取消 sweep
**步驟**：執行中按取消
**預期**：後端（`DELETE /api/v1/sweep/{job_id}`）成功，UI 回到 idle

---

### 群組 I：通知與排程（S9–S12）

#### TC-NTF-01 通道設定
**步驟**：點側欄「設定」→ 子導航「通知」（`/settings/notifications`）→ 在「Channels」區塊啟用 Email、填寫 SMTP；啟用 LINE Notify token
**預期**：
- 設定頁子導航文字逐字依序：通知 / 排程 / 健康
- 通知頁 H2 文字逐字：「通知設定」
- Section H3 文字逐字依序：「Channels」、「Rules」、「最近 7 日推送 log」
- 每張 Channel 卡片下方按鈕文字逐字：「測試發送」；點擊後顯示 toast：成功為「{name} 測試送出」、失敗為「{name} 失敗（{status}）」

#### TC-NTF-02 規則
**步驟**：在「通知設定」頁「Rules」區塊，點按鈕「+ 新規則」，建立「投機 score≥80 即時 push」、「每日 18:00 digest」
**預期**：
- Rules 表頭文字逐字依序：啟用 / Name / Mode / Summary / Channels / 操作
- 列操作按鈕文字逐字依序：編輯 / 立即執行 / Preview / 刪除
- 保存後在 Rules 清單可見；可勾選 checkbox 啟停（toast 文字「{name} 啟用」/「{name} 停用」）

#### TC-NTF-03 排程
**步驟**：前往「設定」→「排程」（`/settings/scheduler`）啟用 daily_pipeline，設 09:30 / 18:00
**預期**：APScheduler 註冊；下次執行時間正確顯示

#### TC-NTF-04 健康監控
**步驟**：點側欄「設定」→ 子導航「健康」（`/settings/health`）
**預期**：
- 子導航 tab 文字為「健康」，但頁面 H2 文字逐字為「**系統健康**」（tab 與 H2 命名不同是現況）
- 顯示 heartbeat、freshness、deliverability 折線圖、disk 使用量分區

---

### 群組 J：資料管理（S19 / S20 / S23）

#### TC-ING-01 信用残自動抓取
**步驟**：點側欄「資料管理」進入 `/data` → 點頁面右上角藍色按鈕「批量抓取」→ 選 7203 → margin → Run（API: `POST /api/v1/ingest/margin`）
**預期**：
- 頁面 H1 文字逐字：「資料管理」
- 右上角按鈕文字逐字：「批量抓取」（藍）、「上傳資料」（綠）
- fallback chain（yahoo → minkabu）任一成功即寫入 `data/cache/7203_margin.csv`；UI 顯示來源與筆數

#### TC-ING-02 投資部門別（個股估算）
**步驟**：同頁，選 flow → Run
**預期**：寫入 `{code}_flow.csv`

#### TC-ING-03 JPX 週報
**步驟**：在「資料管理」觸發 JPX 週報（API: `POST /api/v1/ingest/jpx-weekly`）
**預期**：下載解析 Excel；API `GET /api/v1/ingest/market-flow` 可讀取

#### TC-ING-04 手動上傳
**步驟**：在「資料管理」點「上傳資料」（`/data`）→ 拖入 CSV（含 alias 欄名如 `週,信用買残,信用売残`）
**預期**：預覽欄位 normalize 後正確；確認後寫入 cache

#### TC-ING-05 資料總覽
**步驟**：點側欄「資料管理」進入 `/data`
**預期**：
- 表頭文字逐字依序：代碼 / 名稱 / 股價 / 信用残 / 投資部門別 / 基本面 / 操作（共 4 種快取欄位，**非 3 種**）
- 圖例文字逐字：「最新（≤7日）」綠、「偏舊（7-30日）」黃、「過舊（>30日）」紅
- 每列「操作」欄含「重抓」「上傳」連結
- 過舊以紅（>30日）/ 黃（7–30日）顏色警示

#### TC-ING-06 批量 ingest（SSE）
**步驟**：在「資料管理」點「批量抓取」→ 全選 → Run All
**預期**：SSE 即時逐檔回報成功 / 失敗

---

### 群組 K：分析增強（S15 / S21）

#### TC-ANL-01 指標 API
**步驟**：`GET /api/v1/indicators/7203?series=rsi,macd,bb`
**預期**：JSON 含時序，數值與 capystock 計算一致

#### TC-ANL-02 異常偵測
**步驟**：`GET /api/v1/analytics/anomaly/7203?days=60`
**預期**：列出 volume_spike / price_jump / gap_up / gap_down 事件，附 z-score

#### TC-ANL-03 事件研究
**步驟**：`POST /api/v1/analytics/event-study/7203` body 含事件日期清單
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
**步驟**：點側欄「設定」→ 子導航「通知」（`/settings/notifications`）→ 在「Channels」區塊切換通道狀態
**預期**：每張 Channel 卡片左上角圓點顏色即時變化（綠=ok、黃=warn、灰=off），無需重新整理

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
