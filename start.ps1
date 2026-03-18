##############################################
#  HirePilot — Start Application
##############################################

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
Push-Location $root

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "       HirePilot  —  Starting Up        " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ── 1. Ensure Ollama is running on the host ─────────────────
Write-Host "[1/4] Checking Ollama..." -ForegroundColor Yellow
$ollamaRunning = $false
try {
    $r = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -Method Get -TimeoutSec 3 -ErrorAction Stop
    $models = ($r.models | ForEach-Object { $_.name }) -join ", "
    Write-Host "  Ollama is running  —  models: $models" -ForegroundColor Green
    $ollamaRunning = $true
} catch {
    Write-Host "  Ollama is NOT running." -ForegroundColor Red
    Write-Host "  Attempting to start Ollama..." -ForegroundColor Yellow
    $ollamaExe = Get-Command ollama -ErrorAction SilentlyContinue
    if ($ollamaExe) {
        Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
        Start-Sleep -Seconds 3
        try {
            Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -Method Get -TimeoutSec 5 -ErrorAction Stop | Out-Null
            Write-Host "  Ollama started successfully." -ForegroundColor Green
            $ollamaRunning = $true
        } catch {
            Write-Host "  WARNING: Could not start Ollama. AI features will use fallback mode." -ForegroundColor DarkYellow
        }
    } else {
        Write-Host "  WARNING: Ollama not installed. AI features will use fallback mode." -ForegroundColor DarkYellow
    }
}

# ── 2. Free ports if occupied ────────────────────────────────
Write-Host ""
Write-Host "[2/4] Checking ports..." -ForegroundColor Yellow
$ports = @(3000, 8000, 5432, 6379, 9000, 9001, 5050, 4444)
foreach ($port in $ports) {
    $conn = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
            Where-Object { $_.State -eq "Listen" }
    if ($conn) {
        $pid = $conn[0].OwningProcess
        $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
        # Don't kill Ollama or Docker
        if ($proc -and $proc.ProcessName -notmatch "ollama|com\.docker|Docker Desktop|vpnkit") {
            Write-Host "  Port $port in use by $($proc.ProcessName) (PID $pid) — stopping it" -ForegroundColor DarkYellow
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        }
    }
}
Write-Host "  Ports clear." -ForegroundColor Green

# ── 3. Build and start Docker Compose ────────────────────────
Write-Host ""
Write-Host "[3/4] Building and starting Docker services..." -ForegroundColor Yellow
docker compose up --build -d 2>&1 | ForEach-Object {
    if ($_ -match "error|Error|ERROR") {
        Write-Host "  $_" -ForegroundColor Red
    } elseif ($_ -match "Started|Running|Healthy|Built|Created") {
        Write-Host "  $_" -ForegroundColor DarkGray
    }
}

# ── 4. Wait for health checks ───────────────────────────────
Write-Host ""
Write-Host "[4/4] Waiting for services to be ready..." -ForegroundColor Yellow
$maxWait = 60
$waited = 0
while ($waited -lt $maxWait) {
    Start-Sleep -Seconds 3
    $waited += 3
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:8000/docs" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
        if ($r.StatusCode -eq 200) {
            break
        }
    } catch { }
    Write-Host "  Waiting... ($waited`s)" -ForegroundColor DarkGray
}

# ── Summary ──────────────────────────────────────────────────
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "       HirePilot is RUNNING             " -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Frontend       http://localhost:3000" -ForegroundColor White
Write-Host "  Backend API    http://localhost:8000" -ForegroundColor White
Write-Host "  API Docs       http://localhost:8000/docs" -ForegroundColor White
Write-Host "  pgAdmin        http://localhost:5050" -ForegroundColor White
Write-Host "  MinIO Console  http://localhost:9001" -ForegroundColor White
Write-Host "  Selenium VNC   http://localhost:7900" -ForegroundColor White
if ($ollamaRunning) {
    Write-Host "  Ollama LLM     http://localhost:11434" -ForegroundColor White
}
Write-Host ""

Pop-Location
