# CapyStock — Product Requirements Document (PRD)

**版本**：v1.0  
**建立日期**：2026-05-10  
**對應實裝版本**：v1.0（Pre-S1 + M3–M8 / S1–S25）

---

## 一、產品定位

CapyStock 是一款日本股票籌碼分析輔助工具，幫助個人投資者用「籌碼分析」方法（參見 [KNOWLEDGE_舅舅心法.md](KNOWLEDGE_舅舅心法.md)）追蹤主力動向、判斷進出場時機，並管理自己的追蹤清單與持倉記錄。

---

## 二、目標使用者

### 主要使用者：個人投資者（非工程師）

| 屬性 | 描述 |
|---|---|
| 技術能力 | 不具備 Command Line 操作能力，不會寫程式 |
| 裝置 | Windows 11 個人電腦，使用瀏覽器（Chrome / Edge）操作 |
| 股市經驗 | 有基本股票交易經驗，理解「主力」、「停損」、「籌碼集中」等概念 |
| 市場 | 日本股市（東京證券交易所上市個股，使用 4 位數股票代碼） |
| 操作習慣 | 每日收盤後花 10–15 分鐘查看訊號，不做盤中即時操作 |
| 語言 | 中文（繁體）使用者 |

### 次要使用者：開發者 / 系統管理員

| 屬性 | 描述 |
|---|---|
| 技術能力 | 具備 Python / CLI 能力，負責部署與維運 |
| 操作方式 | CLI（`python -m capystock.main`）、Docker、NSSM 等系統級工具 |
| 範疇說明 | CLI 功能屬維運工具層，**不在 UAT 驗收範圍**；UAT 僅涵蓋 Web UI |

---

## 三、問題陳述

個人投資者跟蹤日本股票時面臨：

1. **資訊散亂**：主力動向（EDINET 大量保有報告）、信用残、投資部門別分別在不同來源，需人工彙整
2. **訊號難判讀**：「三選二警告」、吃貨訊號、停損觸發需要同時比對多維度資料，容易遺漏
3. **缺乏量化輔助**：沒有工具幫助計算風報比、追蹤主力成本（master cost）
4. **歷史難回溯**：缺乏結構化的警示記錄和持倉損益追蹤

---

## 四、產品目標

| 目標 | 衡量方式 |
|---|---|
| 使用者每日 10 分鐘內看完自己的追蹤清單訊號 | Dashboard 一屏顯示關鍵資訊 |
| 訊號觸發後無需額外操作即能收到通知 | Email / LINE 通知自動推送 |
| 任何功能的主路徑不超過 3 次點擊 | Web UI 設計規則 |
| 非工程師使用者無需接觸 CLI | 所有使用者功能均可由 Web UI 完成 |

---

## 五、功能範圍

### 5.1 核心功能（已實裝，M3–M8）

#### 5.1.1 Dashboard（首頁）
- 持倉狀態卡片：顯示已持有股票的未實現損益
- 追蹤清單卡片：顯示監控中但未買入的股票
- 今日訊號卡片：今日觸發的出場/警示訊號
- 金雞 Top 卡片：殖利率最高的股票速覽
- 無掃描快照時顯示提示，引導至資料管理執行掃描

#### 5.1.2 投機訊號（/signals）
- 全市場訊號列表：依 score 降序排列，含三選二警告、吃貨、停損等訊號
- 分頁切換：全市場訊號 / 我的持倉 / 我的最愛
- 個股頁（/signals/{code}）：
  - K 線圖（120 日）含技術指標覆蓋（SMA 5/20/60/120、EMA 12/26、布林通道、RSI、MACD）
  - 對比模式入口、收藏切換（★）

#### 5.1.3 金雞高股息（/dividend）
- 列表頁：欄位含 Overall 評等 / DPS / 殖利率 / 連無減配年數 / 自己資本比 / EPS Growth
- 篩選器：Overall / 殖利率最低值 / 無減配年數 / 自己資本比率 / 配當性向上限 / 只看我的最愛
- 個股頁（/dividend/{code}）：8 指標雷達圖、配當歷史、指標評分、統計摘要

#### 5.1.4 比較模式
- 投機對比（/compare）：正規化走勢（期初=100）、相關性矩陣熱圖、最近指標訊號，最多 5 檔
- 金雞對比（/dividend/compare）：DPS 配當對比表、雷達圖對比

#### 5.1.5 持倉管理（/portfolio）
- 已買入股票記錄：進場價、數量、日期、停損價、目標價、主力成本
- 未實現損益計算（以即時股價為基準）
- 新增 / 平倉操作

#### 5.1.6 追蹤清單（/watchlist）
- 監控中但未買入的股票清單
- 新增 / 移除，設定追蹤起始價

#### 5.1.7 我的最愛（/favorites）
- 跨投機 / 金雞頁面的收藏清單
- 從個股頁 ★ 按鈕切換

#### 5.1.8 模擬交易（/simulation）
- 建立模擬：基本設定（名稱、類型、期間、資金）→ 候選標的 → 規則與條件
- 技術指標條件：RSI 超賣/超買、MACD 金叉/死叉、SMA 交叉、布林通道突破
- 查看結果：權益曲線、交易明細、績效指標
- 策略參數 Sweep（⚡ 網格回測）：stop_loss × take_profit 熱圖 + 排行榜

#### 5.1.9 資料管理（/data）
- 資料總覽：每支追蹤股票的信用残 / 投資部門別 / 基本面資料新鮮度（顏色警示）
- 批量抓取：從多來源（Yahoo JP、Minkabu、JPX）自動抓取資料，SSE 即時回報進度
- 手動上傳：拖拉 CSV 上傳信用残（margin）或投資部門別（flow）資料
- 市場 Flow 更新：JPX 週報一鍵更新

#### 5.1.10 設定（/settings）
- 通知（/settings/notifications）：
  - Channels：Email SMTP、LINE Notify 設定與測試發送
  - Rules：通知規則建立（即時 push / 每日 digest），含啟停、立即執行、Preview
  - 最近 7 日推送 log
- 排程（/settings/scheduler）：daily_pipeline 啟停與執行時間設定
- 健康（/settings/health）：heartbeat / freshness / deliverability 折線圖、磁碟使用量

### 5.2 不在使用者操作範圍的功能（維運層）

以下功能存在於系統中但不面向一般使用者，**不納入 UAT 驗收**：

| 功能 | 說明 |
|---|---|
| CLI（`python -m capystock.main`） | 開發者 / 維運工具，不要求一般使用者能操作 |
| Backend API 直接呼叫（curl / Swagger UI） | 開發者測試工具 |
| Docker 部署、NSSM 服務註冊 | 維運人員操作 |

---

## 六、不在範圍（Out of Scope）

| 項目 | 說明 |
|---|---|
| 台灣 / 美國股市 | 目前只支援日本東證上市股票 |
| 多使用者 / 帳號系統 | 單使用者本地部署，無登入認證 |
| 即時盤中數據 | 使用每日收盤後更新的資料，不做分鐘級即時行情 |
| 自動下單 | 只提供分析與警示，不對接券商 API 下單 |
| 行動 App（iOS / Android） | 僅支援桌面瀏覽器 |

---

## 七、資料來源限制

| 來源 | 限制 |
|---|---|
| kabutan.jp | 個股信用残歷史 / 投資部門別為 Premium 專屬，免費層無法自動抓取 |
| EDINET | 需有效 API Key（`EDINET_API_KEY`），申報週期為事件驅動，不每日更新 |
| LINE Notify | 2025 年中已停止服務，目前以 SMTP Email 為主要通知通道 |
| yfinance | 當 kabutan 爬取失敗時的備援股價來源，無信用残資料 |

---

## 八、籌碼分析核心邏輯（業務規則）

以下參數位於 `capystock/config.py`，使用者可透過設定調整：

### 出場警告（三選二制）
| 條件 | 參數 |
|---|---|
| 法人連續賣超 ≥ 3 日，且累計 ≥ 前 10 日買超量的 20% | `INSTITUTIONAL_SELL_CONSECUTIVE_DAYS`, `INSTITUTIONAL_SELL_RATIO_OF_PRIOR_10D_BUY` |
| 信用買残連升 ≥ 3 週，且 ≥ 8 週均值的 2 倍 | `MARGIN_INCREASE_CONSECUTIVE_WEEKS`, `MARGIN_INCREASE_VS_8W_MEAN` |
| 股價較近 30 日最低點上漲 ≥ 30% | `PRICE_RISE_FROM_RECENT_LOW` |

### 停損觸發
| 條件 | 參數 |
|---|---|
| 股價跌破追蹤起始價（或主力成本）5%，連續 2 日 | `STOP_LOSS_DROP_PCT`, `STOP_LOSS_CONSECUTIVE_DAYS` |

### 吃貨訊號
| 條件 | 參數 |
|---|---|
| 外資或法人連續 5 日買超，同期信用買残下降 | `ACCUMULATION_INSTITUTIONAL_BUY_DAYS` |

---

## 九、技術架構摘要（僅供參考）

| 層次 | 技術 |
|---|---|
| 使用者介面 | SvelteKit SPA（http://localhost:5173 開發 / 同源 prod） |
| Backend API | FastAPI（http://localhost:8000，路由前綴 `/api/v1/`） |
| 資料儲存 | JSON（watchlist / portfolio / favorites / 排程設定）、CSV（log / 快取 / 快照） |
| 部署 | Docker Compose（API + 前端 static build）或 Windows NSSM |

---

## 十、術語對照

| 術語 | 定義 |
|---|---|
| 追蹤清單（Watchlist） | 使用者關注但尚未買入的股票，作為訊號監控對象 |
| 持倉（Portfolio） | 使用者已實際買入、持有中的股票 |
| 主力成本（master_cost） | 使用者估算的主力買入均價，作為停損錨點 |
| 三選二警告 | 出場條件三項中任兩項觸發即發出警告 |
| 金雞 | 高股息、財務健全、殖利率穩定的股票 |
| 快照（Snapshot） | 全市場掃描結果的 Parquet 快取，由 daily_pipeline 排程生成 |
| score | 投機訊號的綜合得分，越高表示訊號越強 |
| Overall | 金雞評等（STRONG / HEALTHY / CAUTION / RISKY） |
