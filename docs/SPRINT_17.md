# Sprint 17 — 前端：技術指標 + 對比頁 UI

依賴：[MILESTONE_05.md](MILESTONE_05.md)

## 目的
- `/signals/[code]` 加技術指標切換 / 子圖
- 新增 `/compare`（投機）與 `/dividend/compare`（金雞）

## `/signals/[code]` 擴充

### 主視覺新增
- K 線圖右上加 toolbar：
  - SMA 多選：5 / 20 / 60 / 120
  - 布林通道 toggle
  - EMA 12/26 toggle
- K 線圖下方新增可摺疊區塊：
  - **RSI(14) 子圖**：水平線 30 / 70；最近一筆超買 / 超賣高亮
  - **MACD 子圖**：MACD line + signal line + histogram
- 右欄「指標訊號」卡片：列出最近 30 日 indicator_signals（icon + 日期 + 名稱 + 強度）

### 元件
- `IndicatorOverlay.svelte`：lightweight-charts 的 line series 包裝（接 SMA / EMA / BB 上下軌）
- `RSIPanel.svelte`：lightweight-charts 子圖（共用 time scale）
- `MACDPanel.svelte`：line + line + histogram

## `/compare` 投機對比頁

### 路由參數
- `?codes=7203,8058,9984&days=120`

### 區塊
1. **頂部 chip bar**：已選 codes，可加（autocomplete by name/code）/ 移除
2. **Normalized K 線圖**：以期初為 100 對齊；多色 line series
3. **指標切換**：與 `/signals/[code]` 同 toolbar
4. **相關性矩陣表**：色階 heatmap（紅綠）
5. **訊號時間軸**：每檔一行，並排顯示
6. **最近指標訊號清單**：彙總

## `/dividend/compare`

### 區塊
1. chip bar
2. **疊加雷達圖**：3–5 條色 series
3. **DPS 並排 bar**：x = year，每檔不同色
4. **指標明細表**：列 = metric，欄 = code，cell = score（PASS/WARN/FAIL color）
5. **配當性向比較線圖**

## 驗收（自動化）

`npm run test:unit` 通過：
- `IndicatorOverlay.test.ts`：給 SMA series + BB series 渲染後 series count 正確
- `RSIPanel.test.ts`：給 RSI array 含 NaN，line 不斷裂；30/70 水平線存在
- `MACDPanel.test.ts`：histogram 正負兩色 bar count 正確
- `ComparePanel.test.ts`：給 3 codes correlation matrix 渲染 3x3 cell

`npm run test:e2e` 通過 `e2e/indicators_compare.spec.ts`：
1. `/signals/7203`：toolbar 點 SMA 20 → K 線多一條 line series；點 BB → 多兩條；展開 RSI 子圖 → DOM 出現
2. 訊號清單：列數 = `/indicators/{code}/signals` 回傳長度
3. `/compare?codes=7203,8058,9984`：normalized 線 3 條；correlation heatmap 3x3；移除一檔 → 變 2x2
4. `/dividend/compare?codes=7203,8058`：雷達圖 2 series；DPS bar 兩色
5. 截圖回歸：3 張
