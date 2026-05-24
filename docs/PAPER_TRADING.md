# 模擬交易帳本（Paper Trading）使用說明

> 本文件針對 2026-05 重設後的「跟單帳本」工作流程。

## 核心工作流

```
1. 建立帳本（一次）
   → /simulation/ledger/new
   → 設定：名稱 / 初始資金 / 停損% / 停利% / 最長持有天數

2. 看訊號決定進場（每次）
   → /signals → 點開個股 → 「📥 進場到帳本」
   → 選帳本、輸入股數、確認價格 → 送出

3. 每日自動推進（背景）
   → Windows 工作排程器每日 16:00 跑 paper_advance_daily.ps1
   → 系統用當日 close 判斷：
     - 跌破 entry × (1 - 停損%) → 自動賣出（stop_loss）
     - 漲過 entry × (1 + 停利%) → 自動賣出（take_profit）
     - 持有超過 max_hold_days → 自動賣出（max_hold）
     - 系統出場訊號（matched ≥ 2）→ 自動賣出（exit_signal）

4. Review 結果
   → /simulation/{id} → 看 equity curve、closed trades、報告指標
   → /simulation/{id}/report：win_rate、profit_factor、最大回撤、平均持有天數
```

## 排程設定（Windows）

開啟 PowerShell（**以系統管理員執行**），切到專案根目錄後：

```powershell
$projectRoot = Get-Location
$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$projectRoot\scripts\paper_advance_daily.ps1`""
$trigger = New-ScheduledTaskTrigger -Daily -At 16:00
Register-ScheduledTask `
    -TaskName "CapyStock-PaperAdvance" `
    -Action $action `
    -Trigger $trigger `
    -Description "每日推進 CapyStock 模擬帳本"
```

驗證：

```powershell
Get-ScheduledTask -TaskName "CapyStock-PaperAdvance"
# 手動立即跑一次測試
Start-ScheduledTask -TaskName "CapyStock-PaperAdvance"
# 看 log
Get-Content data\logs\paper_advance_*.log -Tail 50
```

刪除（若要重設）：

```powershell
Unregister-ScheduledTask -TaskName "CapyStock-PaperAdvance" -Confirm:$false
```

## API 補充

| Endpoint | 用途 |
|---|---|
| `POST /simulation` | 建帳本 |
| `POST /simulation/{id}/open-position?code=&name=&shares=&entry_price=&entry_date=` | **手動進場（核心）** |
| `POST /simulation/{id}/close-position?code=&exit_price=` | 手動平倉 |
| `POST /simulation/{id}/advance?to_date=YYYY-MM-DD` | 手動推進到某日（排程在做的事） |
| `GET /simulation/{id}/report` | 取得績效指標 |

## 規則細節

### 停損
單日 close ≤ `entry_price × (1 - stop_loss_pct)` 即觸發。例：5% 停損 + entry ¥1000 → close ≤ ¥950 即賣。

### 停利
單日 close ≥ `entry_price × (1 + take_profit_pct)` 即觸發。

### 出場訊號
系統呼叫 `signal_service.analyze_one(code)`，若 `matched ≥ 2`（外資連賣 / 融資暴增 / 股價離低點任 2 條成立）即視為訊號出場。

### 成本與稅
- 進場：`shares × price × (1 + commission_pct + slippage_pct)` 扣現金
- 出場：`shares × price × (1 - commission_pct - slippage_pct)`，若 PnL > 0 再扣 `gross_pnl × tax_pct`（日股 20.315%）

## 與舊系統的差異（給已建過 backtest 的用戶）

- `/simulation/new`（4 步驟精靈）仍可用，適合「給規則跑回測」場景
- `/simulation/ledger/new`（新）：適合「我自己決定進場 + 系統自動出場」場景
- 兩者使用同一個資料結構與後端引擎，只是建立流程不同

## 注意事項

- 排程依賴 `python` 在 PATH 中可呼叫，且專案 venv 已啟用相關依賴
- 排程跑失敗時看 `data/logs/paper_advance_YYYYMMDD.log`
- 重大假日當天跑也無妨：當日無新價格 → equity_curve 不變、不會誤觸發
