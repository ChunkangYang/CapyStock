# Milestone 5 — 技術指標與分析增強

## 規劃決策（已確認）
- 技術指標核心：**RSI(14) / MACD(12,26,9) / 布林通道(20,2σ) / SMA(5,20,60,120) / EMA(12,26)**
- 計算引擎：**純 Python + NumPy**（不引入 ta-lib）
- 比較模式：**最多 5 檔同時對比**，金雞 + 投機兩面板皆支援
- 訊號融合：把「技術指標訊號」併入 Signal Score，但需可單獨關閉

## Sprint 範圍與大綱

| Sprint | 主題 | 詳細設計 |
|---|---|---|
| S14 | 技術指標計算引擎（核心） | [SPRINT_14.md](SPRINT_14.md) |
| S15 | 指標 API + 服務整合 | [SPRINT_15.md](SPRINT_15.md) |
| S16 | 比較模式 service + 對比頁 | [SPRINT_16.md](SPRINT_16.md) |
| S17 | 前端：技術指標 + 對比頁 UI | [SPRINT_17.md](SPRINT_17.md) |
| S18 | 訊號回測整合 | [SPRINT_18.md](SPRINT_18.md) |

## 整體架構新增

```
CapyStock/
├── capystock/indicators.py              # ★新增
├── api/
│   ├── services/indicator_service.py / compare_service.py
│   ├── routers/indicators.py / compare.py
│   └── schemas/indicator.py / compare.py
├── frontend/src/
│   ├── lib/components/
│   │   ├── IndicatorOverlay.svelte / RSIPanel.svelte / MACDPanel.svelte / ComparePanel.svelte
│   └── routes/
│       ├── signals/[code]/+page.svelte   # ★擴
│       ├── compare/+page.svelte
│       └── dividend/compare/+page.svelte
```

## 跨 Sprint 共通約定

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

## 順序建議
1. **S14 → S15**：純後端，可獨立驗證
2. **S16**：對比 service + API
3. **S17**：前端整合
4. **S18**：模擬整合

完成 M5 後：使用者可以在 K 線上看 SMA / 布林通道 / RSI / MACD，比較多檔走勢與相關性，並用技術指標跑回測驗證策略。
