#!/usr/bin/env pwsh
# Description: Smoke check of the V2 stack; exits with the result of scripts/check-services.ps1.

$scriptPath = Join-Path $PSScriptRoot "..\..\scripts\check-services.ps1"
if (Test-Path $scriptPath) {
    & $scriptPath @args
    exit $LASTEXITCODE
} else {
    Write-Host "Could not find check-services.ps1 at $scriptPath" -ForegroundColor Red
    exit 1
}
