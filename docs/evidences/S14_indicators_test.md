# S14 — 技術指標計算引擎 測試結果

## 執行日期
2026-04-28

## 測試指令
```
py -3.13 -m pytest tests/unit/test_indicators.py -v --tb=no
```

## 結果
```
platform win32 -- Python 3.13.7, pytest-9.0.2
collected 21 items

TestRSI::test_matches_pandas_ta              PASSED
TestRSI::test_short_input_returns_all_nan    PASSED
TestRSI::test_flat_input_rsi50               PASSED
TestRSI::test_period_boundary_nan            PASSED
TestRSI::test_performance_1000pts            PASSED
TestMACD::test_matches_pandas_ta             PASSED
TestMACD::test_short_input_returns_all_nan   PASSED
TestMACD::test_flat_input_macd_near_zero     PASSED
TestMACD::test_performance_1000pts           PASSED
TestBollinger::test_matches_pandas_ta        PASSED
TestBollinger::test_flat_input_all_bands_equal PASSED
TestBollinger::test_short_input_returns_nan  PASSED
TestSmaEma::test_sma_basic                   PASSED
TestSmaEma::test_ema_seed_equals_sma         PASSED
TestSmaEma::test_period_gt_length_all_nan    PASSED
TestAtrStoch::test_atr_not_nan_after_warmup  PASSED
TestAtrStoch::test_stoch_kd_not_nan_after_warmup PASSED
TestDetectSignals::test_returns_empty_on_short_input PASSED
TestDetectSignals::test_rsi_oversold_triggered PASSED
TestDetectSignals::test_detect_signals_returns_valid_types PASSED
TestDetectSignals::test_all_signal_names_are_valid PASSED

21 passed in 0.04s
```

## 備注
- RSI fixture 使用 SMA-seeded Wilder smoothing（Wilder 原始論文算法）作為標準答案
- MACD / BB fixture 與 pandas-ta 0.4.71b0 對齊，容忍誤差 < 1e-6
- BB 使用 `ddof=1`（樣本標準差）對齊 pandas-ta
- 性能：1000 點 RSI/MACD < 5ms ✅
