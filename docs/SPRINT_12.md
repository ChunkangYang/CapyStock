# Sprint 12 — 通知 / 排程設定 UI + 健康監控頁

依賴：[MILESTONE_04.md](MILESTONE_04.md)

## 目的
讓使用者不必開 JSON / CSV 也能：
- 切換 rule 開關 / 改 cron / 改 recipient
- 查 run 歷史與失敗詳情
- 看到「最近一次 scan 何時跑、結果」

## 路由
- `/settings/notifications`
- `/settings/scheduler`
- `/settings/health`

## `/settings/notifications`

### 區塊
1. **Channels 狀態卡**：Email / LINE 各一張（綠燈 = configured + healthy）
   - 「測試發送」按鈕 → `/notify/test` → toast
2. **Rules 表格**：
   - 欄位：啟用 toggle / Name / Mode / Trigger / Filters 摘要 / Channels / 最近送出 / 操作（編輯 / 刪除 / 立即執行 / Preview）
   - 「+ 新規則」開 modal 表單
3. **Log table**：最近 7 日推送，可篩 channel / severity

### 規則編輯 modal
- mode radio
- digest：cron picker（用 `cron-parser` 顯示「每日 08:00」人話）
- realtime：alert_types multi-select、min_severity radio
- scope radio (watchlist / favorites / all)
- channels multi-check + per-channel recipients 輸入
- 「Preview」按鈕 → 顯示 digest body_html（iframe srcdoc）

## `/settings/scheduler`

- Jobs 表格：Name / cron（inline 編輯）/ Enabled toggle / Last run / Next run / Status badge / 操作（Run Now / 看 Runs）
- 點 row 展開最近 10 次 runs（mini timeline，色塊代表 status）
- Run 詳情 modal：起訖時間 / output_summary / error stack

## `/settings/health`

- 「Worker 心跳」：healthcheck_ping job 最近一次成功時間，超過 1 小時亮紅
- 「資料新鮮度」：`scan/snapshots` 最新日期、`paper sim cursor_date` 最舊
- 「Notification deliverability」：過去 7 日成功率（折線）
- 「Disk usage」：`data/` 目錄大小 + 各子目錄 breakdown

## API 新增
| Method | Path | 說明 |
|---|---|---|
| GET | `/api/v1/health/system` | aggregate：scheduler last run / scan freshness / notify success rate / disk |

## 驗收（自動化）

`npm run test:e2e` 通過 `e2e/settings.spec.ts`：

1. `/settings/notifications`：channels 卡片亮燈；點測試 → toast；建立 rule → 表格新增；toggle disable → PATCH
2. Preview：modal 內 iframe srcdoc 含 `<h2>` 等預期內容
3. `/settings/scheduler`：jobs row count = mock；inline 改 cron → PATCH；Run Now → status=running → success；展開 runs mini timeline 5 個色塊
4. `/settings/health`：四張卡 DOM 存在；scan freshness 顯示「N 日前」；折線圖 series count = 7
5. 截圖回歸：三張

`npm run test:unit`：
- `CronEditor.test.ts`：輸入 `0 8 * * *` → 顯示「每日 08:00」；無效 → 錯誤
- `RuleForm.test.ts`：mode 切換顯示對應欄位；submit emit 完整 payload
