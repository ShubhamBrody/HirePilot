##############################################
#  HirePilot — Stop Application
##############################################

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
Push-Location $root

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "       HirePilot  —  Shutting Down       " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ── 1. Stop all Docker Compose services ─────────────────────
Write-Host "[1/2] Stopping Docker Compose services..." -ForegroundColor Yellow
docker compose down 2>&1 | ForEach-Object {
    if ($_ -match "Removed|Stopped|removed|stopped") {
        Write-Host "  $_" -ForegroundColor DarkGray
    } elseif ($_ -match "error|Error") {
        Write-Host "  $_" -ForegroundColor Red
    }
}
Write-Host "  All containers stopped and removed." -ForegroundColor Green

# ── 2. Kill any leftover processes on app ports ──────────────
Write-Host ""
Write-Host "[2/2] Cleaning up leftover port bindings..." -ForegroundColor Yellow
$ports = @(3000, 8000, 5432, 6379, 9000, 9001, 5050, 4444, 7900)
$killed = 0
foreach ($port in $ports) {
    $conn = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
            Where-Object { $_.State -eq "Listen" }
    if ($conn) {
        $pid = $conn[0].OwningProcess
        $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
        # Don't kill Ollama or Docker Desktop itself
        if ($proc -and $proc.ProcessName -notmatch "ollama|com\.docker|Docker Desktop|vpnkit") {
            Write-Host "  Killing $($proc.ProcessName) (PID $pid) on port $port" -ForegroundColor DarkYellow
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            $killed++
        }
    }
}
if ($killed -eq 0) {
    Write-Host "  No leftover processes found." -ForegroundColor Green
} else {
    Write-Host "  Cleaned up $killed process(es)." -ForegroundColor Green
}

# ── Done ─────────────────────────────────────────────────────
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "       HirePilot is STOPPED              " -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Note: Ollama is still running (shared system service)." -ForegroundColor DarkGray
Write-Host "  To stop Ollama too:  taskkill /IM ollama.exe /F" -ForegroundColor DarkGray
Write-Host "  Data volumes are preserved. To wipe:  docker compose down -v" -ForegroundColor DarkGray
Write-Host ""

Pop-Location
