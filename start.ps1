# CapyStock 容器管理腳本（PowerShell）
# 用法：
#   .\start.ps1           — 啟動容器（已在跑則跳過）
#   .\start.ps1 update    — git pull + rebuild image + 重啟容器
#   .\start.ps1 restart   — 不 pull / 不 rebuild，只重啟容器
#   .\start.ps1 stop      — 停止容器
#   .\start.ps1 logs      — 追蹤 log（Ctrl-C 離開）

param(
    [string]$Command = "start"
)

$SERVICE = "capystock"

switch ($Command) {

    "start" {
        Write-Host "[capystock] 啟動容器..."
        docker compose up -d
        Write-Host "[capystock] 容器已啟動，服務位於 http://localhost:8000"
    }

    "update" {
        Write-Host "[capystock] 拉取最新程式碼..."
        git pull

        Write-Host "[capystock] 重新建置 image..."
        docker compose build

        Write-Host "[capystock] 重啟容器..."
        docker compose up -d

        Write-Host "[capystock] 更新完成，服務位於 http://localhost:8000"
    }

    "restart" {
        Write-Host "[capystock] 重啟容器..."
        docker compose restart $SERVICE
        Write-Host "[capystock] 重啟完成"
    }

    "stop" {
        Write-Host "[capystock] 停止容器..."
        docker compose stop
        Write-Host "[capystock] 已停止"
    }

    "logs" {
        docker compose logs -f $SERVICE
    }

    default {
        Write-Host "用法: .\start.ps1 {start|update|restart|stop|logs}"
        exit 1
    }
}
