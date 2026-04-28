# Milestone 5 — 技術指標與分析增強 詳細設計

> 本文件交付給 Sonnet / Haiku 作為實作藍本。每個 Sprint 含：目的、檔案產物、API/元件規格、驗收條件。
> 規劃決策（已確認）：
> - 技術指標核心：**RSI(14) / MACD(12,26,9) / 布林通道(20,2σ) / SMA(5,20,60,120) / EMA(12,26)**
> - 計算引擎：**純 Python + NumPy**（不引入 ta-lib，免裝 C 擴充）。
> - 比較模式：**最多 5 檔同時對比**，金雞 + 投機兩面板皆支援。
> - 訊號融合：把「技術指標訊號」併入 Signal Score，但需可單獨關閉。

---

## 0. 整體架構新增

```
CapyStock/
├── capystock/
│   └── indicators.py              # ★新增 純函式技術指標庫（RSI/MACD/BB/SMA/EMA）
├── api/
│   ├── services/
│   │   ├── indicator_service.py   # ★新增 包裝 indicators + 快取
│   │   └── compare_service.py     # ★新增 多檔對比資料聚合
│   ├── routers/
│   │   ├── indicators.py          # ★新增
│   │   └── compare.py             # ★新增
│   └── schemas/
│       ├── indicator.py
│       └── compare.py
├── frontend/src/
│   ├── lib/components/
│   │   ├── IndicatorOverlay.svelte  # ★新增 K線圖疊加（SMA / BB）
│   │   ├── RSIPanel.svelte          # ★新增 子圖
│   │   ├── MACDPanel.svelte         # ★新增 子圖
│   │   └── ComparePanel.svelte      # ★新增 多檔對比視覺
│   └── routes/
│       ├── signals/[code]/+page.svelte   # ★擴 加技術指標切換
│       ├── compare/+page.svelte           # ★新增
│       └── dividend/compare/+page.svelte  # ★新增
└── docs/
    └── MILESTONE_5_SPRINT_PLAN.md (本文件)
```

---

## Sprint 14 — 技術指標計算引擎（核心）

### 目的
- 純函式可單獨測試（無 IO、無時間依賴）
- 介面接收 numpy array 或 list[float]，回傳同長度 array（不足期間填 NaN）

### 檔案
- `capystock/indicators.py`
- `tests/unit/test_indicators.py`
- `tests/fixtures/indicators_known_values.csv`：人工算好的標準答案

### API 設計

```python
# capystock/indicators.py
import numpy as np

def sma(closes: np.ndarray, period: int) -> np.ndarray: ...
def ema(closes: np.ndarray, period: int) -> np.ndarray: ...
def rsi(closes: np.ndarray, period: int = 14) -> np.ndarray:
    """Wilder smoothing；前 period 個 NaN"""
def macd(closes: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    """{'macd': arr, 'signal': arr, 'hist': arr}"""
def bollinger(closes: np.ndarray, period: int = 20, num_std: float = 2.0) -> dict:
    """{'mid': arr, 'upper': arr, 'lower': arr, 'bandwidth': arr, 'percent_b': arr}"""
def atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> np.ndarray: ...
def stoch_kd(highs, lows, closes, k_period=9, d_period=3) -> dict: ...
```

### 訊號偵測層（基於指標）

```python
class IndicatorSignal(BaseModel):
    name: Literal["rsi_oversold", "rsi_overbought", "macd_golden_cross", "macd_dead_cross",
                  "bb_breakout_up", "bb_breakout_down", "sma_golden_cross_5_20",
                  "sma_dead_cross_5_20"]
    date: date
    value: float
    strength: float  # 0~1

def detect_signals(prices: list[PriceBar], today: date) -> list[IndicatorSignal]:
    """跑全部指標 → 偵測當日 / 前一日交叉與穿越"""
```

### 偵測規則（精確定義）

| Signal | 條件 |
|---|---|
| rsi_oversold | RSI(14) 從 ≥ 30 跌破 30（昨日 ≥30 今日 <30） |
| rsi_overbought | RSI(14) 從 ≤ 70 突破 70 |
| macd_golden_cross | MACD line 由下往上穿越 signal line 且 hist 由負轉正 |
| macd_dead_cross | MACD line 由上往下穿越 signal line |
| bb_breakout_up | close > upper band 且前一日 close ≤ upper |
| bb_breakout_down | close < lower band 且前一日 close ≥ lower |
| sma_golden_cross_5_20 | SMA5 由下穿 SMA20 |
| sma_dead_cross_5_20 | SMA5 由上穿 SMA20 |

### 驗收（自動化）

`pytest tests/unit/test_indicators.py -v`：

- RSI / MACD / BB 與 `pandas-ta` 結果（在 dev 用 pandas-ta 算 baseline → 寫入 fixture csv，prod 不依賴 pandas-ta）容忍誤差 1e-6
- 邊界：input length < period → 全 NaN 不 raise
- 持平 input（全 100）→ RSI = 50（以 50 為中性慣例）；BB upper=lower=mid=100；MACD ≈ 0
- detect_signals：人工構造 22 日序列觸發每種訊號各一次，斷言 name + date 完全相符
- 性能：1000 點 RSI/MACD < 5ms

### 給實作者
- RSI 用 Wilder smoothing：`avg_gain = (prev_avg_gain*(p-1) + gain) / p`，不是簡單 SMA
- MACD signal line 是 EMA(MACD, signal_period)，不是 SMA

---

## Sprint 15 — 指標 API + 服務整合

### 目的
- 對外暴露指標時序（給前端畫圖）
- 把 indicator_signals 注入 `signal_service.analyze_one`

### 檔案
- `api/services/indicator_service.py`
- `api/services/signal_service.py`：擴 — 將 indicator_signals 加入 SignalResult
- `api/routers/indicators.py`
- `api/schemas/indicator.py`

### Service

```python
class IndicatorSeries(BaseModel):
    name: str          # "rsi" | "macd" | "macd_signal" | "macd_hist" | "bb_upper" ...
    dates: list[date]
    values: list[float | None]   # NaN → None

class IndicatorBundle(BaseModel):
    code: str
    period_days: int
    series: dict[str, IndicatorSeries]
    signals: list[IndicatorSignal]

class IndicatorService:
    def get_bundle(self, code: str, days: int = 120, include: list[str] = None) -> IndicatorBundle: ...
        # include 預設 ["sma_5","sma_20","sma_60","ema_12","ema_26","rsi_14","macd","bollinger_20"]
```

### SignalResult 擴充

```python
class SignalResult(BaseModel):
    # ... 原本欄位
    indicator_signals: list[IndicatorSignal] = []   # ★新增
    technical_score: float = 0.0                    # ★新增 -3~+3
```

### technical_score 計算
- 各 indicator_signal 加權：金叉 +1、死叉 -1；oversold +0.5；overbought -0.5；BB breakout up +0.5；down -0.5
- 截斷到 [-3, +3]

### scan signals score 融合
- 在 `scan_service.run_signals_scan` 中：`score_total = score_existing + technical_score`
- query param `?include_technical=true|false`（預設 true，false 時退回原 score）

### Endpoints

| Method | Path | 說明 |
|---|---|---|
| GET | `/api/v1/indicators/{code}?days=120&include=rsi,macd,bollinger` | 取 bundle |
| GET | `/api/v1/indicators/{code}/signals?days=30` | 只取訊號清單 |

### 驗收（自動化）

`pytest tests/unit/test_indicator_service.py tests/api/test_indicators_router.py -v`：

- get_bundle 預設 include 全帶；指定 `include=rsi_14,macd` → series dict 只含這兩組
- 對 fixture price_7203.csv 跑 → series length = price length；NaN → None 序列化正確
- SignalResult 內 indicator_signals 至少包含一筆；technical_score 與算出值一致
- include_technical=false 時 scan score 與舊版相同（不引入新增量）

---

## Sprint 16 — 比較模式 service + 對比頁

### 目的
- 投機面板：兩到五檔同期 K 線疊加 + 指標對比
- 金雞面板：3 檔基本面雷達圖疊加 + DPS 趨勢並排

### 檔案
- `api/services/compare_service.py`
- `api/routers/compare.py`
- `api/schemas/compare.py`
- `frontend/src/routes/compare/+page.svelte`（投機）
- `frontend/src/routes/dividend/compare/+page.svelte`（金雞）
- `frontend/src/lib/components/ComparePanel.svelte`

### Service

```python
class CompareSignalsBundle(BaseModel):
    codes: list[str]
    period_days: int
    series_by_code: dict[str, dict]   # {code: {price, rsi, macd, signals, ...}}
    correlation_matrix: dict[str, dict[str, float]]  # close return 對相關係數

class CompareDividendBundle(BaseModel):
    codes: list[str]
    fundamentals: dict[str, FundamentalReport]
    dividend_history: dict[str, list[DpsRow]]
    radar_normalized: dict[str, dict[str, float]]    # {code: {Sales: 0~100, ...}}

class CompareService:
    def signals_bundle(self, codes: list[str], days: int=120) -> CompareSignalsBundle: ...
    def dividend_bundle(self, codes: list[str]) -> CompareDividendBundle: ...
```

### correlation_matrix
- 各 code 計算 daily log return 序列，對齊交易日 → Pearson correlation
- 缺資料對齊：取所有 code 都有的日期交集

### Endpoints

| Method | Path | 說明 |
|---|---|---|
| GET | `/api/v1/compare/signals?codes=7203,8058,9984&days=120` | 投機對比 |
| GET | `/api/v1/compare/dividend?codes=7203,8058,9984` | 金雞對比 |

### 限制
- codes 最多 5 檔；超過 422
- codes 重複自動去重

### 驗收（自動化）

`pytest tests/unit/test_compare_service.py tests/api/test_compare_router.py -v`：

- 對 3 檔 fixture，correlation_matrix 對角線 = 1.0、對稱、值在 [-1,1]
- 缺一檔資料的日期 → 該日不納入 correlation 計算
- codes=[] → 422；codes=6 檔 → 422
- 重複 codes=[7203,7203,8058] → 回 [7203, 8058]
- radar_normalized 每檔 8 軸 0–100

---

## Sprint 17 — 前端：技術指標 + 對比頁 UI

### 目的
- `/signals/[code]` 加技術指標切換 / 子圖
- 新增 `/compare`（投機）與 `/dividend/compare`（金雞）

### `/signals/[code]` 擴充

#### 主視覺新增
- K 線圖右上加 toolbar：
  - SMA 多選：5 / 20 / 60 / 120
  - 布林通道 toggle
  - EMA 12/26 toggle
- K 線圖下方新增可摺疊區塊：
  - **RSI(14) 子圖**：水平線 30 / 70；最近一筆超買 / 超賣高亮
  - **MACD 子圖**：MACD line + signal line + histogram
- 右欄「指標訊號」卡片：列出最近 30 日 indicator_signals（icon + 日期 + 名稱 + 強度）

#### 元件
- `IndicatorOverlay.svelte`：lightweight-charts 的 line series 包裝（接 SMA / EMA / BB 上下軌）
- `RSIPanel.svelte`：lightweight-charts 子圖（共用 time scale）
- `MACDPanel.svelte`：line + line + histogram

### `/compare` 投機對比頁

#### 路由參數
- `?codes=7203,8058,9984&days=120`

#### 區塊
1. **頂部 chip bar**：已選 codes，可加（autocomplete by name/code）/ 移除
2. **Normalized K 線圖**：以期初為 100 對齊；多色 line series
3. **指標切換**：與 `/signals/[code]` 同 toolbar
4. **相關性矩陣表**：色階 heatmap（紅綠）
5. **訊號時間軸**：每檔一行，並排顯示
6. **最近指標訊號清單**：彙總

### `/dividend/compare`

#### 區塊
1. chip bar
2. **疊加雷達圖**：3–5 條色 series
3. **DPS 並排 bar**：x = year，每檔不同色
4. **指標明細表**：列 = metric，欄 = code，cell = score（PASS/WARN/FAIL color）
5. **配當性向比較線圖**

### 驗收（自動化）

`npm run test:unit` 通過：
- `IndicatorOverlay.test.ts`：給 SMA series + BB series 渲染後 series count 正確
- `RSIPanel.test.ts`：給 RSI array 含 NaN，line 不斷裂報錯；30/70 水平線存在
- `MACDPanel.test.ts`：histogram 正負兩色 bar count 正確
- `ComparePanel.test.ts`：給 3 codes correlation matrix 渲染 3x3 cell

`npm run test:e2e` 通過 `e2e/indicators_compare.spec.ts`：
1. `/signals/7203`：toolbar 點 SMA 20 → K 線多一條 line series；點 BB → 多兩條（upper/lower）；展開 RSI 子圖 → DOM 出現
2. 訊號清單：列數 = `/indicators/{code}/signals` 回傳長度
3. `/compare?codes=7203,8058,9984`：normalized 線 3 條；correlation heatmap 3x3；移除一檔 → 變 2x2
4. `/dividend/compare?codes=7203,8058`：雷達圖 2 series；DPS bar 兩色
5. 截圖回歸：`/signals/7203?indicators=on`、`/compare`、`/dividend/compare` 三張

---

## Sprint 18 — 訊號回測整合（驗證技術指標的實戰價值）

### 目的
- 把 indicator_signals 接入 `simulation` 引擎，使用者可以建「以 MACD 金叉進場 + RSI 超買出場」的策略
- 量化技術指標對 backtest 報酬的貢獻

### 檔案
- `api/schemas/simulation.py`：擴 EntryRule / ExitRule
- `api/services/backtest_engine.py`：擴 entry/exit 條件支援 indicator
- `frontend/src/routes/simulation/new/+page.svelte`：Step 3 表單擴

### Schema 擴充

```python
class IndicatorCondition(BaseModel):
    type: Literal["rsi_oversold", "rsi_overbought", "macd_golden_cross", "macd_dead_cross",
                  "sma_cross", "bb_breakout_up", "bb_breakout_down"]
    params: dict = {}    # 例如 {"fast":5,"slow":20} for sma_cross

class EntryRule(BaseModel):
    # ... 原欄位
    indicator_entry: list[IndicatorCondition] = []     # 新增
    indicator_entry_logic: Literal["and", "or"] = "or"

class ExitRule(BaseModel):
    # ... 原欄位
    indicator_exit: list[IndicatorCondition] = []      # 新增
    indicator_exit_logic: Literal["and", "or"] = "or"
```

### 引擎邏輯

```python
def check_indicator_entry(code: str, today: date, conds: list[IndicatorCondition], logic: str) -> bool:
    bundle = indicator_service.get_bundle(code, days=120)
    today_signals = {s.name for s in bundle.signals if s.date == today}
    matches = [c.type in today_signals for c in conds]
    return all(matches) if logic == "and" else any(matches)
```

- 進場時除原本 `require_signal` 外，若 `indicator_entry` 非空，必須再通過此 check
- 出場時若 `indicator_exit` 命中，reason = `indicator_exit`

### 報告增強
- `report.exit_reason_breakdown`：dict count by reason，**新增 indicator_exit 類別**
- `report.attribution`：用「移除指標條件後重跑」結果對比，計算技術指標貢獻 %
  - 簡化：先在 UI 顯示「策略類型 = pure signal / signal+indicator / pure indicator」標籤即可，attribution 列為 v2

### UI Step 3 擴充
- 「技術指標條件（可選）」區塊
- 進場條件：multi-select indicator type + and/or radio
- 出場條件：同上
- 預覽：顯示「最近 30 日命中此條件的日期」（呼叫 indicator_service 預檢）

### 驗收（自動化）

`pytest tests/unit/test_backtest_engine_indicators.py -v`：

- 構造 30 日 price 序列，已知 MACD 金叉在 D10、死叉在 D20
- 設 entry: macd_golden_cross；exit: macd_dead_cross
- 預期 closed_trade 進出場日 = D10 / D20，reason = `indicator_exit`
- and 邏輯：require macd_golden_cross AND rsi_oversold；構造序列只滿足前者 → 不進場
- or 邏輯：滿足任一即進場
- 報告 exit_reason_breakdown 含 `indicator_exit: 1`

`npm run test:e2e` 通過 `e2e/simulation_indicator.spec.ts`：
- 建立模擬時 Step 3 勾選 macd_golden_cross 進場 → 預覽顯示日期清單 → 完成 backtest → 報告顯示 indicator_exit 標籤

---

## 跨 Sprint 共通約定（沿用 M3 / M4，補充以下）

### NumPy / NaN 處理
- 序列化到 JSON：`float('nan')` → `None`
- 反序列化進 numpy：`None` → `np.nan`
- 比較 NaN：禁止 `==`，一律 `np.isnan()`

### 指標快取
- `IndicatorService` 不另存檔，每次從 price.csv 重算（< 5ms 可接受）
- 若日後改全市場 batch 計算 → 加 LRU `@lru_cache`，cache key 含 price.csv mtime

### 性能
- compare_service 對 5 檔 + 120 天，計算 + 序列化 < 200ms（不含 IO）
- 加 `@pytest.mark.performance` 標記 budget 測試

---

## 順序建議
1. **S14 → S15**：純後端，可獨立驗證
2. **S16**：對比 service + API（依賴 S14/S15 的 indicator）
3. **S17**：前端整合（依賴 S15/S16 API）
4. **S18**：模擬整合（依賴 S15）

完成 M5 後：使用者可以在 K 線上看 SMA / 布林通道 / RSI / MACD，比較多檔走勢與相關性，並用技術指標跑回測驗證策略。
