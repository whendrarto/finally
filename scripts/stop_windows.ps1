# Stop FinAlly (Windows PowerShell). Removes the container but keeps the data volume. Safe to run repeatedly.
# Native docker calls are checked via $LASTEXITCODE (Stop would turn their stderr into exceptions on PS 5.1)
$ErrorActionPreference = "Continue"

$Container = "finally"

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker is not running."
    exit 1
}

docker container inspect $Container *> $null
if ($LASTEXITCODE -eq 0) {
    Write-Host "Stopping and removing container '$Container'..."
    docker rm -f $Container *> $null
    Write-Host "Stopped. Your data is preserved in the 'finally-data' volume."
} else {
    Write-Host "Container '$Container' is not running. Nothing to do."
}
