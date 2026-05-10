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
- 頁面標題顯示「Dashboard」
- 顯示四張卡片，標題依序為「持倉狀態」、「追蹤清單」、「今日訊號」、「金雞 Top」
- 持倉卡片空狀態：「尚無持倉。請至 持倉管理 新增買入記錄。」
- 追蹤清單卡片空狀態：「追蹤清單為空。請至 追蹤清單 新增關注股票。」
- 今日訊號 / 金雞 Top 空狀態：「暫無訊號」、「暫無資料」
- 頁面上方橫幅提示：「尚無快照，請至資料管理執行掃描或等待 daily_pipeline 排程。」

**結果**：✅ Pass（2026-05-06）

#### TC-UI-02 SPA 路由 fallback
**步驟**：直接於瀏覽器網址列輸入 `/signals/7203` 並重新整理
**預期**：直接顯示頁面內容，不出現 404 錯誤訊息

**結果**：✅ Pass（2026-05-06）｜頁面正常顯示，無 404｜IMP-LOAD-001：加載無動畫（已修復：新增 LoadingSpinner 元件）

#### TC-UI-03 全域導航
**步驟**：點擊側欄所有連結
**預期**：側欄依序顯示：Dashboard / 投機訊號 / 投機對比 / 金雞高股息 / 金雞對比 / 持倉管理 / 追蹤清單 / 我的最愛 / 模擬交易 / 資料管理 / 設定 — 全部可達且當前頁以左邊綠色 border + 綠色文字高亮

**結果**：✅ Pass（2026-05-06）

---

### 群組 D：投機訊號（S5 / S17）

#### TC-SIG-01 列表頁
**步驟**：前往「投機訊號」（`/signals`）
**預期**：
- 頁面標題：「投機訊號」
- 表格依 score 排序
- 分頁按鈕：「全市場訊號」、「我的持倉」、「我的最愛」
- 空資料時顯示：「尚無投機訊號掃描快照。請至 資料管理 或執行掃描排程後再回來。」

**結果**：✅ Pass（2026-05-06）｜表格依 score 降序排列正確，分頁按鈕齊全

#### TC-SIG-02 個股頁
**步驟**：前往「投機訊號」 → 點入個股（`/signals/7203`）
**預期**：
- 上方圖表標題：「K 線（120 日）」
- 指標 toolbar：「SMA：」5 / 20 / 60 / 120｜「EMA：」12 / 26｜「布林通道」｜「RSI」｜「MACD」
- 勾選 RSI / MACD 顯示對應子圖
- 右上角有「對比模式」按鈕與星號 ★ 收藏切換

**結果**：✅ Pass（2026-05-06）

#### TC-SIG-03 收藏切換
**步驟**：在投機訊號個股頁點 ★
**預期**：立即變色，重新整理仍保留（store 為 Record-based，不噴 `r.filter is not a function`）

**結果**：✅ Pass（2026-05-06）

---

### 群組 E：金雞高股息（S6）

#### TC-DIV-01 列表頁
**步驟**：前往「金雞高股息」（`/dividend`）
**預期**：
- 頁面標題：「金雞高股息」
- 表格欄位依序：★ / Code / Name / Overall / DPS / Yield / 連無減配 / Payout Avg / 自己資本比 / EPS Growth / 指標
- 篩選器標籤：Overall / 殖利率最低值 / 無減配年數 / 自己資本比率 / 配當性向上限 / 只看我的最愛
- 表格可點擊欄位標題排序
- 空資料時顯示：「尚無金雞掃描快照。請至 資料管理 或執行掃描排程後再回來。」

**結果**：✅ Pass（2026-05-06）

#### TC-DIV-02 個股頁
**步驟**：前往「金雞高股息」 → 點入個股（`/dividend/7203`）
**預期**：頁面區塊標題依序為「8 指標雷達圖」、「配當歷史」、「指標評分」、「統計摘要」；右上角有 Overall 評等與星號 ★ 收藏切換

**結果**：✅ Pass（2026-05-06）

---

### 群組 F：比較模式（S16）

#### TC-CMP-01 投機對比
**步驟**：前往「投機對比」（`/compare?codes=7203,9432,6758`）
**預期**：
- 頁面標題：「投機對比」
- 卡片區塊依序：「正規化走勢（期初 = 100）」、相關性矩陣熱圖、「最近指標訊號」
- 上方有 chip 形式股票代碼，下拉選單「期間」含 60 / 120 / 250 日選項

**結果**：✅ Pass（2026-05-06）

#### TC-CMP-02 金雞對比
**步驟**：點側欄「金雞對比」（`/dividend/compare?codes=7203,9432`）
**預期**：
- 頁面標題：「金雞高股息對比」
- 顯示 DPS（配當）對比表 + 雷達圖對比

**結果**：✅ Pass（2026-05-06）

---

### 群組 G：模擬交易（S7 / S8 / S18）

#### TC-SIM-01 建立模擬（基本）
**步驟**：前往「模擬交易」（`/simulation`）→ 點右上角「+ 新建模擬」按鈕 → Step1 基本設定（名稱 / kind / 期間 / 資金）→ Step2 候選標的 → Step3 規則與條件 → 送出
**預期**：
- 頁面標題：「模擬交易」；右上角按鈕：「+ 新建模擬」
- 列表表頭依序：名稱 / 類型 / 狀態 / 期間 / 初始資金 / 當前權益 / 報酬 / 操作
- 送出後跳轉 `/simulation/[id]` 顯示權益曲線、交易明細、績效指標

**結果**：✅ Pass（2026-05-06）

#### TC-SIM-02 技術指標條件
**步驟**：Step3「技術指標條件」區，進場勾選「RSI 超賣（< 30）」、出場勾選「RSI 超買（> 70）」
**預期**：
- 下拉選項含：「RSI 超賣（< 30）」、「RSI 超買（> 70）」、「MACD 金叉」、「MACD 死叉」、「SMA 交叉」、「布林通道上突破」、「布林通道下突破」
- 報告中 strategy_type 標示為「技術指標」，出場原因分布含 indicator_exit

**結果**：✅ Pass（2026-05-06）

#### TC-SIM-03 模擬列表
**步驟**：前往「模擬交易」（`/simulation`）
**預期**：列出 `data/simulations/*.json` 全部結果，可點入

**結果**：✅ Pass（2026-05-06）

---

### 群組 H：策略參數 Sweep（S22）

#### TC-SWP-01 啟動 sweep
**步驟**：前往「模擬交易」→ 點「⚡ 網格回測 Sweep」→ 預設值（停損 5/8/10%、獲利了結 15/20/25%、股票 7203、2026-02-01 ~ 2026-04-30）→ 點「執行 Sweep」
**預期**：
- 完成後顯示熱圖（stop_loss × take_profit → 總報酬%）
- 排行榜 Top N，各組合有交易數與報酬

**結果**：✅ Pass（2026-05-07）｜9 組合跑出，熱圖有色，交易數 1，stop_loss=8% 組合損失最小（-0.01%）｜修復：price cache 2024 資料不足、stop_loss_pct 未套入引擎、require_signal 阻止進場

#### TC-SWP-02 取消 sweep
**步驟**：執行中按取消
**預期**：後端（`DELETE /api/v1/sweep/{job_id}`）成功，UI 回到 idle

**結果**：✅ Pass（2026-05-08）

---

### 群組 I：通知與排程（S9–S12）

#### TC-NTF-01 通道設定
**步驟**：點側欄「設定」→ 子導航「通知」（`/settings/notifications`）→ 在「Channels」區塊啟用 Email、填寫 SMTP；啟用 LINE Notify token
**預期**：
- 設定頁子導航依序：通知 / 排程 / 健康
- 頁面標題：「通知設定」
- 區塊標題依序：「Channels」、「Rules」、「最近 7 日推送 log」
- 每張 Channel 卡片下方按鈕：「測試發送」；點擊後顯示 toast「{name} 測試送出」（成功）或「{name} 失敗（{status}）」（失敗）

**結果**：✅ Pass（2026-05-08）

#### TC-NTF-02 規則
**步驟**：在「通知設定」頁「Rules」區塊，點「+ 新規則」按鈕，建立「投機 score≥80 即時 push」、「每日 18:00 digest」
**預期**：
- Rules 表頭依序：啟用 / Name / Mode / Summary / Channels / 操作
- 列操作按鈕依序：編輯 / 立即執行 / Preview / 刪除
- 保存後在 Rules 清單可見；勾選 checkbox 啟停顯示 toast「{name} 啟用」/「{name} 停用」

**結果**：✅ Pass（2026-05-08）

#### TC-NTF-03 排程
**步驟**：前往「設定」→「排程」（`/settings/scheduler`）啟用 daily_pipeline，設 09:30 / 18:00
**預期**：APScheduler 註冊；下次執行時間正確顯示

**結果**：✅ Pass（2026-05-08）

#### TC-NTF-04 健康監控
**步驟**：點側欄「設定」→ 子導航「健康」（`/settings/health`）
**預期**：
- 頁面標題：「系統健康」
- 顯示 heartbeat、freshness、deliverability 折線圖、disk 使用量分區

**結果**：✅ Pass（2026-05-08）

---

### 群組 J：資料管理（S19 / S20 / S23）

#### TC-ING-01 信用残自動抓取
**步驟**：點側欄「資料管理」進入 `/data` → 點頁面右上角「批量抓取」按鈕 → 選 7203 → 信用残 → 執行
**預期**：
- 頁面標題：「資料管理」
- 右上角按鈕：「批量抓取」（綠底黑字）、「上傳資料」（黑底綠字外框）
- 成功後 UI 顯示來源與筆數；資料寫入 `data/cache/7203_margin.csv`

**結果**：✅ Pass（2026-05-08）

#### TC-ING-02 投資部門別（個股估算）
**步驟**：在「批量抓取」頁勾選「投資部門別」→ 輸入代碼 → 執行
**預期**：狀態顯示 ✓；來源欄顯示 `jpx_flow`；寫入 `data/cache/{code}_flow.csv`

**結果**：✅ Pass（2026-05-08）

#### TC-ING-03 JPX 週報（市場整體）
**步驟**：在「資料管理」頁面（`/data`）點右上角「↻ 市場 Flow」按鈕
**預期**：按鈕變灰並顯示「更新中…」；完成後顯示「✓ 已更新市場 Flow（N 週）」；`data/cache/_market_flow.csv` 寫入最新週資料

**結果**：✅ Pass（2026-05-08）

#### TC-ING-04 手動上傳
**步驟**：
1. 在「資料管理」（`/data`）點「上傳資料」
2. 拖入 `docs/test_data/7203_margin_sample.csv`
3. 股票代碼填 `7203`，資料種類選「信用残 (margin)」
4. 確認預覽後點「確認上傳」
**預期**：
- 預覽表格顯示欄位 `週 / 買残 / 売残 / 信用倍率`（10 列）
- 確認後顯示「✓ 上傳成功，來源：manual_csv，寫入 10 筆」
- `data/cache/7203_margin.csv` 存在

> 另有 `docs/test_data/7203_flow_sample.csv` 可用同樣步驟測試 flow（種類選「投資部門別 (flow)」）

**結果**：✅ Pass（2026-05-08）

#### TC-ING-05 資料總覽
**步驟**：點側欄「資料管理」進入 `/data`
**預期**：
- 表頭依序：代碼 / 名稱 / 股價 / 信用残 / 投資部門別 / 基本面 / 操作
- 圖例：「最新（≤7日）」綠、「偏舊（7-30日）」黃、「過舊（>30日）」紅
- 每列「操作」欄含「重抓」、「上傳」連結
- 過舊以紅（>30日）/ 黃（7–30日）顏色警示

**結果**：✅ Pass（2026-05-08）

#### TC-ING-06 批量 ingest（SSE）
**步驟**：在「資料管理」點「批量抓取」→ 全選 → Run All
**預期**：SSE 即時逐檔回報成功 / 失敗

**結果**：✅ Pass（2026-05-08）

---

### 群組 K：分析增強（S15 / S21）

#### TC-ANL-01 指標 API
**步驟**：`GET /api/v1/indicators/7203?series=rsi,macd,bb`
**預期**：JSON 含時序，數值與 capystock 計算一致

**結果**：✅ Pass（2026-05-10）｜series 含 rsi_14/macd/macd_signal/macd_hist/bb_upper/bb_mid/bb_lower，58 points，NaN→null 正確，signals 4 筆（含 rsi_oversold）｜證據：[UAT_GROUP_K_ANL.md](EVIDENCES/UAT_GROUP_K_ANL.md)

#### TC-ANL-02 異常偵測
**步驟**：`GET /api/v1/analytics/anomaly/7203?days=60`
**預期**：列出 volume_spike / price_jump / gap_up / gap_down 事件，附 z-score

**結果**：✅ Pass（2026-05-10）｜5 筆事件（gap_up×1、gap_down×2、price_jump×1、volume_spike×1），含 value/threshold/severity｜證據：[UAT_GROUP_K_ANL.md](EVIDENCES/UAT_GROUP_K_ANL.md)

#### TC-ANL-03 事件研究
**步驟**：`POST /api/v1/analytics/event-study/7203` body 含事件日期清單
**預期**：回傳 AR / AAR / CAR 序列（事件窗口 ±N 日）

**結果**：✅ Pass（2026-05-10）｜n_events=2，window=[-5,20]，aar/car 各 26 筆，benchmark=self_mean，CAR 累計=0.0804｜證據：[UAT_GROUP_K_ANL.md](EVIDENCES/UAT_GROUP_K_ANL.md)

---

### 群組 L：基本面（S24）

#### TC-FUN-01 IR Bank 橫向表格解析
**步驟**：`python -m capystock.main fundamental 3543`（コメダHD）
**預期**：顯示完整 8 指標與評等

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
