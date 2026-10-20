#!/usr/bin/env pwsh
# Description: Traces a request from gateway to backend service

param (
    [Parameter(Mandatory=$true)]
    [string]$Endpoint
)

Write-Host "Tracing Request for Endpoint: $Endpoint" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# Define mapping based on route prefixes used in API Gateway
$routes = @(
    @{ Prefix = "/api/v1/auth"; Service = "auth-service"; Port = 8081 },
    @{ Prefix = "/api/v1/users"; Service = "user-service"; Port = 8082 },
    @{ Prefix = "/api/v1/documents"; Service = "knowledge-service"; Port = 8083 },
    @{ Prefix = "/api/v1/metadata"; Service = "metadata-service"; Port = 8084 },
    @{ Prefix = "/api/v1/feedback"; Service = "feedback-service"; Port = 8085 },
    @{ Prefix = "/api/v1/analytics"; Service = "feedback-service"; Port = 8085 },
    @{ Prefix = "/api/v1/ai"; Service = "ai-qa-service"; Port = 8086 },
    @{ Prefix = "/api/v1/ingestion"; Service = "ingestion-service"; Port = 8088 }
)

$matchedRoute = $null
foreach ($route in $routes) {
    if ($Endpoint.StartsWith($route.Prefix)) {
        $matchedRoute = $route
        break
    }
}

if ($matchedRoute) {
    Write-Host "1. Frontend (Port 3000):"
    Write-Host "   -> Calls API Gateway (Port 3001)"

    Write-Host ""
    Write-Host "2. API Gateway (api-gateway, Port 3001):"
    Write-Host "   -> Matches prefix: $($matchedRoute.Prefix)"
    Write-Host "   -> Applies Global Guards (JWT, RBAC)"
    Write-Host "   -> Proxies to: $($matchedRoute.Service) (Port $($matchedRoute.Port))"

    Write-Host ""
    Write-Host "3. Backend Service ($($matchedRoute.Service), Port $($matchedRoute.Port)):"
    Write-Host "   -> Handles route: $Endpoint"
    Write-Host "   -> Check specific controller in $($matchedRoute.Service) for exact method mapping."
} else {
    Write-Host "Could not automatically determine backend service for endpoint: $Endpoint" -ForegroundColor Yellow
    Write-Host "Check api-gateway routing configuration." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host "1. Search gateway codebase for '$Endpoint' to find exact routing logic."
if ($matchedRoute) {
    Write-Host "2. Search $($matchedRoute.Service) codebase for controller mapping to find implementation."
    Write-Host "3. Check logs for $($matchedRoute.Service): docker logs -f $($matchedRoute.Service)"
}
