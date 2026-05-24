# 每日推進所有 paper trading 模擬帳本到今日。
# 設定 Windows 工作排程器：每個交易日 16:00（日股收盤後 1 小時）執行。
#
# 註冊範例（PowerShell 管理員）：
#   $action = New-ScheduledTaskAction -Execute "powershell.exe" `
#       -Argument "-NoProfile -File `"$PWD\scripts\paper_advance_daily.ps1`""
#   $trigger = New-ScheduledTaskTrigger -Daily -At 16:00
#   Register-ScheduledTask -TaskName "CapyStock-PaperAdvance" `
#       -Action $action -Trigger $trigger -Description "推進模擬帳本"

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$logDir = Join-Path $projectRoot "data\logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$logFile = Join-Path $logDir ("paper_advance_" + (Get-Date -Format "yyyyMMdd") + ".log")

"=== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') paper_advance start ===" | Out-File -Append -Encoding utf8 $logFile

try {
    python -m api.workers.paper_worker 2>&1 | Out-File -Append -Encoding utf8 $logFile
    "=== exit code: $LASTEXITCODE ===" | Out-File -Append -Encoding utf8 $logFile
} catch {
    "ERROR: $_" | Out-File -Append -Encoding utf8 $logFile
    exit 1
}
