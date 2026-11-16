#!/usr/bin/env pwsh
# Description: Shows which V2 service handles a request path. The browser talks only to the web
# origin; frontend/web/proxy.ts forwards /api/v1/** to core-api and /ai/v1/** to ai-service
# (lib/server/proxy-target.ts, ADR-010).

param (
    [Parameter(Mandatory=$true)]
    [string]$Endpoint
)

function Port($name, [int]$default) {
    $value = [Environment]::GetEnvironmentVariable($name)
    if ($value) { return [int]$value } else { return $default }
}

$routes = @(
    @{ Prefix = "/api/v1/"; Service = "core-api"; Port = (Port "V2_CORE_API_PORT" 8080); Code = "services/core-api/src/main/java/com/sopilot/core" },
    @{ Prefix = "/ai/v1/"; Service = "ai-service"; Port = (Port "V2_AI_SERVICE_PORT" 8000); Code = "services/ai-service/src/sopilot_ai/api" },
    @{ Prefix = "/internal/"; Service = "ai-service (service-to-service, X-Internal-Token)"; Port = (Port "V2_AI_SERVICE_PORT" 8000); Code = "services/ai-service/src/sopilot_ai/api/internal.py" }
)
$webPort = Port "V2_WEB_PORT" 3000

Write-Host "Tracing request path: $Endpoint" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

$matched = $routes | Where-Object { $Endpoint.StartsWith($_.Prefix) } | Select-Object -First 1
if (-not $matched) {
    Write-Host "No V2 route prefix matches '$Endpoint' (expected /api/v1/, /ai/v1/ or /internal/)." -ForegroundColor Yellow
    exit 1
}

if ($matched.Prefix -eq "/internal/") {
    Write-Host "1. Not proxied by the web app: core-api's OutboxDispatcher calls ai-service directly."
} else {
    Write-Host "1. Browser -> web (Next.js, port $webPort), same origin"
    Write-Host "   -> proxy.ts matches '$($matched.Prefix)**' and forwards the request unchanged"
}
Write-Host ""
Write-Host "2. $($matched.Service), port $($matched.Port)"
Write-Host "   -> Handles: $Endpoint"
Write-Host "   -> Code: $($matched.Code)"
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
$path = ($Endpoint -split '\?')[0]
Write-Host "1. Find the handler: git grep -n `"$($path.TrimEnd('/'))`" -- $($matched.Code)"
Write-Host "2. Endpoint table: docs/architecture/api/http-conventions.md"
Write-Host "3. Logs (compose): docker logs -f sopilot-v2-$(($matched.Service -split ' ')[0])"
exit 0
