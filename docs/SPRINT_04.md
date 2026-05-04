# Sprint 4 — SvelteKit 前端骨架

依賴：[MILESTONE_03.md](MILESTONE_03.md)

## 目的
建立可運行的前端基底，所有後續 Sprint 在此之上加頁面。

## 安裝
```
cd frontend
npm create svelte@latest .  # SvelteKit + TypeScript + ESLint + Prettier + Vitest + Playwright
npm i lightweight-charts echarts
npm i -D @sveltejs/adapter-static @testing-library/svelte @playwright/test
```

## 共用設施
- `src/lib/api.ts`：
  ```ts
  const BASE = import.meta.env.VITE_API_BASE || '/api/v1';
  export async function api<T>(path: string, init?: RequestInit): Promise<T> {
    const r = await fetch(`${BASE}${path}`, init);
    if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`);
    return r.json();
  }
  ```
- `src/lib/types.ts`：對應後端 schema 的 TS 型別
- `src/lib/stores/favorites.ts`：載入後端後寫入 store，所有 `FavoriteToggle` 共用
- `vite.config.ts`：proxy `/api → http://localhost:8000`

## Layout
- `+layout.svelte`：左側欄導覽 `Dashboard / 投機訊號 / 金雞 / 我的最愛 / 模擬交易`
- 配色：暗色為主，主色 #4ade80（漲）/ #f87171（跌）
- 不引入 UI lib，CSS 自寫

## Dashboard `/`
- 三張卡片：
  1. **持倉狀態**：watchlist 全部、最近 alert 數
  2. **今日訊號**：`scan/signals` 最新快照前 5 名 `score`
  3. **金雞 Top**：`scan/dividend` 排序前 5 名（est_yield desc）
- 一個「最近 EDINET 事件」列表（watchlist 內）

## 驗收（自動化）
- `npm run test:unit` 通過：
  - `api.test.ts`：成功路徑 / 4xx / 5xx
  - `stores/favorites.test.ts`：load / add / remove / 多 tag 行為
- `npm run test:e2e` 通過 `e2e/dashboard.spec.ts`：
  - 後端用 fixture data dir 啟動於 `:8000`
  - 訪問 `/`，斷言三張卡片 DOM + 內容文字符合 mock API 回傳
  - 點側欄四個連結，URL 路徑變化正確
  - 截圖 baseline 比對（`dashboard-default.png`）
