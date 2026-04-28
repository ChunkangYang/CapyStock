# CapyStock — Install as a Windows Service via NSSM
# 用法（系統管理員 PowerShell）：
#   .\nssm_install.ps1
#
# 前置條件：
#   1. 已安裝 nssm（https://nssm.cc/）並在 PATH 中
#   2. 已 `pip install -r requirements.txt`
#   3. 已 `cd frontend && npm install && npm run build`

param(
    [string]$ServiceName = "CapyStock",
    [string]$ProjectDir  = (Resolve-Path "$PSScriptRoot\..\..").Path,
    [int]$Port           = 8000,
    [string]$PythonExe   = ""
)

if (-not $PythonExe) {
    $PythonExe = (Get-Command python).Source
}

$Uvicorn = "$PythonExe"
$Args    = "-m uvicorn api.main:app --host 0.0.0.0 --port $Port"

Write-Host "[CapyStock] Service Name : $ServiceName"
Write-Host "[CapyStock] Project Dir  : $ProjectDir"
Write-Host "[CapyStock] Python       : $PythonExe"
Write-Host "[CapyStock] Listen Port  : $Port"

# 若已存在先移除
nssm stop $ServiceName 2>$null | Out-Null
nssm remove $ServiceName confirm 2>$null | Out-Null

nssm install $ServiceName $Uvicorn $Args
nssm set $ServiceName AppDirectory $ProjectDir
nssm set $ServiceName AppStdout    "$ProjectDir\data\service_stdout.log"
nssm set $ServiceName AppStderr    "$ProjectDir\data\service_stderr.log"
nssm set $ServiceName AppEnvironmentExtra "TZ=Asia/Tokyo"
nssm set $ServiceName Start SERVICE_AUTO_START
nssm start $ServiceName

Write-Host "[CapyStock] Installed. Test: curl http://localhost:$Port/api/v1/health"
