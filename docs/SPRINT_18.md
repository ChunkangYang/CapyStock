# Sprint 18 — 訊號回測整合（驗證技術指標的實戰價值）

依賴：[MILESTONE_05.md](MILESTONE_05.md)

## 目的
- 把 indicator_signals 接入 `simulation` 引擎，使用者可建「以 MACD 金叉進場 + RSI 超買出場」的策略
- 量化技術指標對 backtest 報酬的貢獻

## 檔案
- `api/schemas/simulation.py`：擴 EntryRule / ExitRule
- `api/services/backtest_engine.py`：擴 entry/exit 條件支援 indicator
- `frontend/src/routes/simulation/new/+page.svelte`：Step 3 表單擴

## Schema 擴充

```python
class IndicatorCondition(BaseModel):
    type: Literal["rsi_oversold", "rsi_overbought", "macd_golden_cross", "macd_dead_cross",
                  "sma_cross", "bb_breakout_up", "bb_breakout_down"]
    params: dict = {}

class EntryRule(BaseModel):
    # ... 原欄位
    indicator_entry: list[IndicatorCondition] = []
    indicator_entry_logic: Literal["and", "or"] = "or"

class ExitRule(BaseModel):
    # ... 原欄位
    indicator_exit: list[IndicatorCondition] = []
    indicator_exit_logic: Literal["and", "or"] = "or"
```

## 引擎邏輯

```python
def check_indicator_entry(code: str, today: date, conds: list[IndicatorCondition], logic: str) -> bool:
    bundle = indicator_service.get_bundle(code, days=120)
    today_signals = {s.name for s in bundle.signals if s.date == today}
    matches = [c.type in today_signals for c in conds]
    return all(matches) if logic == "and" else any(matches)
```

- 進場時除原本 `require_signal` 外，若 `indicator_entry` 非空，必須再通過此 check
- 出場時若 `indicator_exit` 命中，reason = `indicator_exit`

## 報告增強
- `report.exit_reason_breakdown`：dict count by reason，**新增 indicator_exit 類別**
- `report.attribution`：用「移除指標條件後重跑」結果對比，計算技術指標貢獻 %
  - 簡化：先在 UI 顯示「策略類型 = pure signal / signal+indicator / pure indicator」標籤即可

## UI Step 3 擴充
- 「技術指標條件（可選）」區塊
- 進場條件：multi-select indicator type + and/or radio
- 出場條件：同上
- 預覽：顯示「最近 30 日命中此條件的日期」

## 驗收（自動化）

`pytest tests/unit/test_backtest_engine_indicators.py -v`：

- 構造 30 日 price 序列，已知 MACD 金叉在 D10、死叉在 D20
- 設 entry: macd_golden_cross；exit: macd_dead_cross
- 預期 closed_trade 進出場日 = D10 / D20，reason = `indicator_exit`
- and 邏輯：require macd_golden_cross AND rsi_oversold；構造序列只滿足前者 → 不進場
- or 邏輯：滿足任一即進場
- 報告 exit_reason_breakdown 含 `indicator_exit: 1`

`npm run test:e2e` 通過 `e2e/simulation_indicator.spec.ts`：
- 建立模擬時 Step 3 勾選 macd_golden_cross 進場 → 預覽顯示日期清單 → 完成 backtest → 報告顯示 indicator_exit 標籤
