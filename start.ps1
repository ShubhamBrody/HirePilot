##############################################
#  HirePilot - Start Application
##############################################

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
Push-Location $root

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "       HirePilot - Starting Up          " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# -- 1. Check Docker is running --------------------------------
Write-Host "[1/5] Checking Docker..." -ForegroundColor Yellow
$dockerOk = $false
try {
    $null = docker info 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Docker is running." -ForegroundColor Green
        $dockerOk = $true
    } else {
        Write-Host "  ERROR: Docker daemon is not running. Please start Docker Desktop first." -ForegroundColor Red
        Pop-Location
        exit 1
    }
} catch {
    Write-Host "  ERROR: Docker is not installed or not in PATH." -ForegroundColor Red
    Pop-Location
    exit 1
}

# -- 2. Check GitHub Models API key ----------------------------
Write-Host ""
Write-Host "[2/5] Checking GitHub Models API..." -ForegroundColor Yellow
$envFile = Join-Path $root "backend\.env"
$hasApiKey = $false
if (Test-Path $envFile) {
    $envContent = Get-Content $envFile -Raw
    if ($envContent -match "GITHUB_TOKEN\s*=\s*\S+") {
        Write-Host "  GitHub Models API key configured." -ForegroundColor Green
        $hasApiKey = $true
    }
}
if (-not $hasApiKey) {
    Write-Host "  WARNING: GITHUB_TOKEN not found in backend/.env" -ForegroundColor DarkYellow
    Write-Host "  AI features require a GitHub Models API key." -ForegroundColor DarkYellow
    Write-Host "  Get one at https://github.com/marketplace/models" -ForegroundColor DarkYellow
}

# -- 3. Free ports if occupied ---------------------------------
Write-Host ""
Write-Host "[3/5] Checking ports..." -ForegroundColor Yellow
$ports = @(3000, 8000, 5432, 6379, 9000, 9001, 5050, 4444)
$freedAny = $false
foreach ($port in $ports) {
    $conn = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
            Where-Object { $_.State -eq "Listen" }
    if ($conn) {
        $procId = $conn[0].OwningProcess
        $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
        if ($proc -and $proc.ProcessName -notmatch "ollama|com\.docker|Docker Desktop|vpnkit|dockerd") {
            Write-Host "  Port $port in use by $($proc.ProcessName) (PID $procId) - stopping it" -ForegroundColor DarkYellow
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            $freedAny = $true
        }
    }
}
if (-not $freedAny) {
    Write-Host "  All ports are clear." -ForegroundColor Green
}

# -- 4. Build and start Docker Compose -------------------------
Write-Host ""
Write-Host "[4/5] Building and starting Docker services..." -ForegroundColor Yellow
Write-Host "  This may take a few minutes on first run..." -ForegroundColor DarkGray

$buildOutput = docker compose up --build -d 2>&1
$buildExitCode = $LASTEXITCODE

foreach ($line in $buildOutput) {
    $s = "$line"
    if ($s -match "error|Error|ERROR" -and $s -notmatch "NativeCommandError") {
        Write-Host "  $s" -ForegroundColor Red
    } elseif ($s -match "Started|Running|Healthy|Built|Created") {
        Write-Host "  $s" -ForegroundColor DarkGray
    }
}

if ($buildExitCode -ne 0) {
    Write-Host ""
    Write-Host "  WARNING: Docker Compose exited with code $buildExitCode" -ForegroundColor Red
    Write-Host "  Check 'docker compose logs' for details." -ForegroundColor Red
}

# -- 5. Wait for backend health check --------------------------
Write-Host ""
Write-Host "[5/5] Waiting for services to be ready..." -ForegroundColor Yellow
$maxWait = 90
$waited = 0
$ready = $false
while ($waited -lt $maxWait) {
    Start-Sleep -Seconds 3
    $waited += 3
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:8000/docs" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
        if ($r.StatusCode -eq 200) {
            $ready = $true
            break
        }
    } catch { }
    Write-Host "  Waiting... (${waited}s)" -ForegroundColor DarkGray
}

if ($ready) {
    Write-Host "  Backend is ready!" -ForegroundColor Green
} else {
    Write-Host "  WARNING: Backend did not become ready in ${maxWait}s. Check logs with: docker compose logs backend" -ForegroundColor DarkYellow
}

# -- Summary ---------------------------------------------------
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
Write-Host "  LLM Provider   GitHub Models (GPT-4o)" -ForegroundColor White
Write-Host ""
Write-Host "  To stop:  .\stop.ps1" -ForegroundColor DarkGray
Write-Host ""

Pop-Location
