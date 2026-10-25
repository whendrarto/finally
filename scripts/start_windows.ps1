# Start FinAlly in Docker (Windows PowerShell). Safe to run repeatedly.
# Usage: .\scripts\start_windows.ps1 [-Build] [-NoOpen]
param(
    [switch]$Build,
    [switch]$NoOpen
)

# Native docker calls are checked via $LASTEXITCODE (Stop would turn their stderr into exceptions on PS 5.1)
$ErrorActionPreference = "Continue"

$Image = "finally"
$Container = "finally"
$Volume = "finally-data"
$Port = if ($env:FINALLY_PORT) { $env:FINALLY_PORT } else { "8000" }
$Url = "http://localhost:$Port"

$RootDir = Split-Path -Parent $PSScriptRoot
Set-Location $RootDir

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker is not running. Start Docker Desktop and try again."
    exit 1
}

docker image inspect $Image *> $null
if ($Build -or $LASTEXITCODE -ne 0) {
    Write-Host "Building Docker image '$Image'..."
    docker build -t $Image .
    if ($LASTEXITCODE -ne 0) { Write-Error "Docker build failed."; exit 1 }
}

# Replace any existing container (running or stopped) so the latest image/env are used
docker container inspect $Container *> $null
if ($LASTEXITCODE -eq 0) {
    Write-Host "Removing existing container '$Container'..."
    docker rm -f $Container *> $null
}

$EnvArgs = @()
if (Test-Path (Join-Path $RootDir ".env")) {
    $EnvArgs = @("--env-file", ".env")
} else {
    Write-Warning "No .env file found in $RootDir. AI chat needs OPENROUTER_API_KEY (see .env.example)."
    Write-Warning "Continuing with the market simulator and default settings."
}

Write-Host "Starting container '$Container'..."
docker run -d --name $Container -v "${Volume}:/app/db" -p "${Port}:8000" @EnvArgs $Image | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Error "Failed to start container."; exit 1 }

Write-Host ""
Write-Host "FinAlly is running at $Url"
Write-Host "Stop it with: .\scripts\stop_windows.ps1"

if (-not $NoOpen) {
    # Give the server a moment to come up before opening the browser
    for ($i = 0; $i -lt 20; $i++) {
        try {
            Invoke-WebRequest -Uri "$Url/api/health" -UseBasicParsing -TimeoutSec 2 | Out-Null
            break
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    Start-Process $Url
}
