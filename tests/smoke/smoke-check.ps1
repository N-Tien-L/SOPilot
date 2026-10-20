#!/usr/bin/env pwsh
# Description: Smoke check for platform services and infrastructure

$scriptPath = Join-Path $PSScriptRoot "..\..\scripts\check-services.ps1"
if (Test-Path $scriptPath) {
    & $scriptPath
} else {
    Write-Host "Could not find check-services.ps1 at $scriptPath" -ForegroundColor Red
    exit 1
}
