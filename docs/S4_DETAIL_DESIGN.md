# S4 Detail Design — SvelteKit 前端骨架（實作紀錄）

依賴：[SPRINT_04.md](SPRINT_04.md)
完成日：2026-04-25

## 實裝產出
- ✅ `frontend/package.json`：SvelteKit + Vite + Vitest + Playwright
- ✅ `frontend/src/lib/api.ts`：fetch wrapper + ApiError 類別
- ✅ `frontend/src/lib/types.ts`：TypeScript 型別定義
- ✅ `frontend/src/lib/stores/favorites.ts`：最愛清單 store（load/add/remove/updateNote）
- ✅ `frontend/src/routes/+layout.svelte`：左側導覽（5 個主要頁面連結）
- ✅ `frontend/src/routes/+page.svelte`：Dashboard（三張卡片 + 資料載入）
- ✅ 骨架路由：
  - `/signals` 及 `[code]`
  - `/dividend` 及 `[code]`
  - `/favorites`
  - `/simulation`

## 自動化測試
- `tests/unit/api.test.ts` — 4 個單元測試（成功回應、4xx、5xx、RequestInit）
- `tests/unit/stores/favorites.test.ts` — 7 個單元測試（load/add/remove/update/tag merge）
- `tests/e2e/dashboard.spec.ts` — Playwright E2E 測試（導航、DOM 驗證、截圖回歸）
- 總計 11 個單元測試全綠
