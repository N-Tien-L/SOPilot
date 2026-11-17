#!/usr/bin/env pwsh
# Description: Checks the health of the SOPilot V2 stack (core-api, ai-service, ai-worker, web,
# Postgres, MinIO). Ports follow the V2_*_PORT variables when set, as in the compose file.
# Exits 1 if any check is red.

param(
    # Compose project of the stack to check (the compose file sets name: sopilot-v2).
    [string]$Project = "sopilot-v2"
)

function Port($name, [int]$default) {
    $value = [Environment]::GetEnvironmentVariable($name)
    if ($value) { return [int]$value } else { return $default }
}

$services = @(
    @{ Name = "core-api"; Port = (Port "V2_CORE_API_PORT" 8080); Path = "/actuator/health" },
    @{ Name = "ai-service"; Port = (Port "V2_AI_SERVICE_PORT" 8000); Path = "/health" },
    @{ Name = "web"; Port = (Port "V2_WEB_PORT" 3000); Path = "/" }
)

$infrastructure = @(
    @{ Name = "PostgreSQL"; Port = (Port "V2_POSTGRES_PORT" 55432) },
    @{ Name = "MinIO"; Port = (Port "V2_MINIO_API_PORT" 59000) }
)

$red = 0

function Test-TcpConnection {
    param([int]$Port)
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $tcp.Connect("127.0.0.1", $Port)
        $tcp.Close()
        return $true
    } catch {
        return $false
    }
}

Write-Host "Checking SOPilot V2 services..." -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan

foreach ($svc in $services) {
    $url = "http://localhost:$($svc.Port)$($svc.Path)"
    try {
        $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) {
            Write-Host "[GREEN] $($svc.Name) is healthy on port $($svc.Port)" -ForegroundColor Green
        } else {
            Write-Host "[RED] $($svc.Name) returned status $($response.StatusCode) on port $($svc.Port)" -ForegroundColor Red
            $red++
        }
    } catch {
        Write-Host "[RED] $($svc.Name) is UNREACHABLE on port $($svc.Port)" -ForegroundColor Red
        $red++
    }
}

# ai-worker has no HTTP port: check its container when the stack runs in compose.
$worker = $null
try {
    # -a: an exited (e.g. OOM-killed) worker must show up as RED, not as "not checked".
    $worker = docker ps -a --filter "label=com.docker.compose.project=$Project" `
        --filter "label=com.docker.compose.service=ai-worker" --format "{{.Status}}" 2>$null
} catch {
    $worker = $null
}
if ($worker -match "^Up") {
    Write-Host "[GREEN] ai-worker container is running ($worker)" -ForegroundColor Green
} elseif ($worker) {
    Write-Host "[RED] ai-worker container is not up ($worker)" -ForegroundColor Red
    $red++
} else {
    Write-Host "[YELLOW] ai-worker not checked: no '$Project' ai-worker container (run from source, or another project name)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Checking infrastructure..." -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan

foreach ($infra in $infrastructure) {
    if (Test-TcpConnection -Port $infra.Port) {
        Write-Host "[GREEN] $($infra.Name) is accessible on port $($infra.Port)" -ForegroundColor Green
    } else {
        Write-Host "[RED] $($infra.Name) is UNREACHABLE on port $($infra.Port)" -ForegroundColor Red
        $red++
    }
}

Write-Host ""
if ($red -gt 0) {
    Write-Host "$red check(s) red." -ForegroundColor Red
    exit 1
}
Write-Host "All checks green." -ForegroundColor Green
exit 0
