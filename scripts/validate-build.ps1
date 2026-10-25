param (
    [Parameter(Mandatory=$true)]
    [string]$Scope
)

$ErrorActionPreference = "Stop"

$repoRoot = git rev-parse --show-toplevel 2>$null
if (-not $repoRoot -or -not (Test-Path $repoRoot)) {
    $repoRoot = (Resolve-Path "$PSScriptRoot\..").ProviderPath
}
Set-Location $repoRoot

$springBootScopes = @("auth", "user", "knowledge", "metadata", "feedback")
$pythonScopes = @("ai-qa", "ingestion", "ai")

if ($springBootScopes -contains $Scope) {
    Write-Host "Validating Spring Boot service: $Scope"
    $serviceDir = "services\$Scope-service"
    if (Test-Path $serviceDir) {
        Set-Location $serviceDir
        .\mvnw compile -q
        if ($LASTEXITCODE -ne 0) { throw "Maven compilation failed." }
    } else { throw "Directory $serviceDir not found." }
}
elseif ($pythonScopes -contains $Scope) {
    Write-Host "Validating Python service: $Scope"
    $serviceDir = "services\$Scope-service"
    if (Test-Path $serviceDir) {
        Set-Location $serviceDir
        python -m compileall src
        if ($LASTEXITCODE -ne 0) { throw "Python compilation failed." }
        uv run ruff check
        if ($LASTEXITCODE -ne 0) { throw "Ruff linting failed." }
    } else { throw "Directory $serviceDir not found." }
}
elseif ($Scope -eq "gateway") {
    Write-Host "Validating NestJS API Gateway"
    $serviceDir = "services\api-gateway"
    if (Test-Path $serviceDir) {
        Set-Location $serviceDir
        pnpm build
        if ($LASTEXITCODE -ne 0) { throw "NestJS build failed." }
        pnpm exec eslint "{src,apps,libs,test}/**/*.ts"
        if ($LASTEXITCODE -ne 0) { throw "NestJS linting failed." }
    } else { throw "Directory $serviceDir not found." }
}
elseif ($Scope -eq "web") {
    Write-Host "Validating Next.js Frontend"
    $serviceDir = "frontend\web"
    if (Test-Path $serviceDir) {
        Set-Location $serviceDir
        pnpm build
        if ($LASTEXITCODE -ne 0) { throw "Next.js build failed." }
        pnpm lint
        if ($LASTEXITCODE -ne 0) { throw "Next.js linting failed." }
    } else { throw "Directory $serviceDir not found." }
}
else {
    Write-Host "Unknown scope: $Scope"
    exit 1
}

Write-Host "Validation successful for scope $Scope."
exit 0
