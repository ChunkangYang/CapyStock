# Human TODO — 需要人工介入的任務

## Sprint 6：金雞高股息儀表板

### E2E 測試 Playwright 瀏覽器安裝
- **狀態**：待執行
- **理由**：Playwright 瀏覽器未安裝，需要運行 `npx playwright install`
- **命令**：
  ```bash
  cd frontend && npx playwright install
  npm run test:e2e
  ```
- **預期結果**：20 個 E2E 測試全綠
  - dashboard.spec.ts：7 個測試
  - dividend.spec.ts：10 個測試
  - signals.spec.ts：11 個測試
- **優先級**：High（完整驗收必須）

### 後端測試
- **狀態**：待確認
- **預期**：Sprint 1-3 的後端 API 應已完成，dividend 相關 endpoints 應存在
- **測試命令**：
  ```bash
  pytest tests/api/test_dividend_router.py -v
  ```
