#!/usr/bin/env pwsh
# Description: Checks health of all SOPilot services and infrastructure

$services = @(
    @{ Name = "auth-service"; Port = 8081; Path = "/actuator/health"; Type = "Spring Boot" },
    @{ Name = "user-service"; Port = 8082; Path = "/actuator/health"; Type = "Spring Boot" },
    @{ Name = "knowledge-service"; Port = 8083; Path = "/actuator/health"; Type = "Spring Boot" },
    @{ Name = "metadata-service"; Port = 8084; Path = "/actuator/health"; Type = "Spring Boot" },
    @{ Name = "feedback-service"; Port = 8085; Path = "/actuator/health"; Type = "Spring Boot" },
    @{ Name = "ai-qa-service"; Port = 8086; Path = "/health"; Type = "Python FastAPI" },
    @{ Name = "ingestion-service"; Port = 8088; Path = "/health"; Type = "Python FastAPI" },
    @{ Name = "api-gateway"; Port = 3001; Path = "/health"; Type = "NestJS" },
    @{ Name = "frontend/web"; Port = 3000; Path = "/"; Type = "Next.js" }
)

$infrastructure = @(
    @{ Name = "PostgreSQL"; Port = 5432 },
    @{ Name = "RabbitMQ"; Port = 15672 },
    @{ Name = "Redis"; Port = 6379 },
    @{ Name = "MinIO"; Port = 9000 }
)

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

Write-Host "Checking SOPilot Services Health..." -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan

foreach ($svc in $services) {
    $url = "http://localhost:$($svc.Port)$($svc.Path)"
    try {
        $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
        if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) {
            Write-Host "[GREEN] $($svc.Name) ($($svc.Type)) is healthy on port $($svc.Port)" -ForegroundColor Green
        } else {
            Write-Host "[RED] $($svc.Name) ($($svc.Type)) returned status $($response.StatusCode) on port $($svc.Port)" -ForegroundColor Red
        }
    } catch {
        Write-Host "[RED] $($svc.Name) ($($svc.Type)) is UNREACHABLE on port $($svc.Port)" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Checking Infrastructure Health..." -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan

foreach ($infra in $infrastructure) {
    $isUp = Test-TcpConnection -Port $infra.Port
    if ($isUp) {
        Write-Host "[GREEN] $($infra.Name) is accessible on port $($infra.Port)" -ForegroundColor Green
    } else {
        Write-Host "[RED] $($infra.Name) is UNREACHABLE on port $($infra.Port)" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Docker Container Status (docker ps)..." -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan
try {
    docker ps --format "table {{.Names}}`t{{.Status}}`t{{.Ports}}"
} catch {
    Write-Host "[YELLOW] Docker daemon not running or not accessible." -ForegroundColor Yellow
}
