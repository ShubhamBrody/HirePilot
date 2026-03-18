##############################################
#  HirePilot - Stop Application
##############################################

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
Push-Location $root

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "       HirePilot - Shutting Down        " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# -- 1. Check Docker is available ------------------------------
Write-Host "[1/2] Stopping Docker Compose services..." -ForegroundColor Yellow
$dockerOk = $false
try {
    $null = docker info 2>&1
    if ($LASTEXITCODE -eq 0) { $dockerOk = $true }
} catch { }

if ($dockerOk) {
    $downOutput = docker compose down 2>&1
    foreach ($line in $downOutput) {
        $s = "$line"
        if ($s -match "Removed|Stopped|removed|stopped") {
            Write-Host "  $s" -ForegroundColor DarkGray
        } elseif ($s -match "error|Error" -and $s -notmatch "NativeCommandError") {
            Write-Host "  $s" -ForegroundColor Red
        }
    }
    Write-Host "  All containers stopped and removed." -ForegroundColor Green
} else {
    Write-Host "  Docker is not running - skipping container shutdown." -ForegroundColor DarkYellow
}

# -- 2. Kill any leftover processes on app ports ---------------
Write-Host ""
Write-Host "[2/2] Cleaning up leftover port bindings..." -ForegroundColor Yellow
$ports = @(3000, 8000, 5432, 6379, 9000, 9001, 5050, 4444, 7900)
$killed = 0
foreach ($port in $ports) {
    $conn = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
            Where-Object { $_.State -eq "Listen" }
    if ($conn) {
        $procId = $conn[0].OwningProcess
        $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
        if ($proc -and $proc.ProcessName -notmatch "ollama|com\.docker|Docker Desktop|vpnkit|dockerd") {
            Write-Host "  Killing $($proc.ProcessName) (PID $procId) on port $port" -ForegroundColor DarkYellow
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            $killed++
        }
    }
}
if ($killed -eq 0) {
    Write-Host "  No leftover processes found." -ForegroundColor Green
} else {
    Write-Host "  Cleaned up $killed process(es)." -ForegroundColor Green
}

# -- Done ------------------------------------------------------
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "       HirePilot is STOPPED             " -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Note: Ollama is still running (shared system service)." -ForegroundColor DarkGray
Write-Host "  To stop Ollama too:  taskkill /IM ollama.exe /F" -ForegroundColor DarkGray
Write-Host "  Data volumes are preserved. To wipe:  docker compose down -v" -ForegroundColor DarkGray
Write-Host ""

Pop-Location
