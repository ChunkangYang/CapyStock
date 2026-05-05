# CONFIRMATION_TEST — 人工驗收測試清單

> 記錄各項改善 / 修復的驗收步驟，供 QA 人員手動確認。

---

## IMP-001｜新增 /watchlist 前端管理頁面

**對應項目**：新增 `/watchlist` 獨立頁面，提供追蹤清單完整管理 UI（列表、新增、刪除）

**改善方式**：
- 新建 `frontend/src/routes/watchlist/+page.svelte`：呼叫 GET/POST/DELETE `/api/v1/watchlist`
- 修改 `frontend/src/routes/+layout.svelte`：sidebar 新增「追蹤清單」連結

**確認步驟：**
1. 啟動後端：`uvicorn api.main:app --reload`
2. 啟動前端：`npm run dev`（在 frontend 目錄）
3. 開啟瀏覽器，點擊 sidebar「追蹤清單」或導覽至 `http://localhost:5173/watchlist`
4. 確認頁面正常顯示，列出目前追蹤中的股票
5. 在「股票代號」欄輸入 `7203`，「起始價」輸入 `2800`，點擊「＋ 加入追蹤」
6. 確認頁面顯示成功訊息「✓ 已加入追蹤：7203」，且清單自動刷新出現 7203
7. 點擊 7203 列的「移除」按鈕，確認提示視窗後確認移除
8. 確認 7203 從清單消失
9. 點擊任一股票代號連結，確認跳轉至 `/signals/{code}` 頁面

**預期結果：**
- `/watchlist` 正常顯示追蹤清單（含代號、名稱、起始價、加入日期）
- 新增：輸入代號+起始價 → API POST → 清單自動更新
- 刪除：確認後 API DELETE → 清單自動更新
- 代號欄可點擊跳轉至個股信號頁

**❌ 失敗條件：** 頁面無法載入、新增/刪除後清單未刷新、代號連結跳轉失敗

**測試結果：**
- 測試日期：
- 測試者：
- 結果：⬜ Pass　⬜ Fail
- 備註：

---
