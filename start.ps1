param(
    [string]$Command = "start"
)

$SERVICE = "capystock"

switch ($Command) {
    "start" {
        Write-Host "[capystock] Starting container..."
        docker compose up -d
        Write-Host "[capystock] Running at http://localhost:8000"
    }
    "update" {
        Write-Host "[capystock] Pulling latest code..."
        git pull
        Write-Host "[capystock] Rebuilding image..."
        docker compose build
        Write-Host "[capystock] Restarting container..."
        docker compose up -d
        Write-Host "[capystock] Done. Running at http://localhost:8000"
    }
    "sync" {
        Write-Host "[capystock] Pulling latest data from GitHub..."
        git pull
        Write-Host "[capystock] Done. Open http://localhost:8000 to see updated data."
    }
    "restart" {
        Write-Host "[capystock] Restarting..."
        docker compose restart $SERVICE
        Write-Host "[capystock] Restarted."
    }
    "stop" {
        Write-Host "[capystock] Stopping..."
        docker compose stop
        Write-Host "[capystock] Stopped."
    }
    "logs" {
        docker compose logs -f $SERVICE
    }
    default {
        Write-Host "Usage: .\start.ps1 {start|sync|update|restart|stop|logs}"
        exit 1
    }
}