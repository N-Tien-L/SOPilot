param (
    [Parameter(Mandatory=$true)]
    [ValidateSet("core", "ai", "web")]
    [string]$Scope
)

$ErrorActionPreference = "Stop"

$repoRoot = git rev-parse --show-toplevel 2>$null
if (-not $repoRoot -or -not (Test-Path $repoRoot)) {
    $repoRoot = (Resolve-Path "$PSScriptRoot\..").ProviderPath
}
Set-Location $repoRoot

switch ($Scope) {
    "core" {
        Write-Host "Validating Spring Boot service: core-api"
        $serviceDir = "services\core-api"
        if (-not (Test-Path $serviceDir)) { throw "Directory $serviceDir not found." }
        Set-Location $serviceDir
        .\mvnw compile -q
        if ($LASTEXITCODE -ne 0) { throw "Maven compilation failed." }
    }
    "ai" {
        Write-Host "Validating Python service: ai-service"
        $serviceDir = "services\ai-service"
        if (-not (Test-Path $serviceDir)) { throw "Directory $serviceDir not found." }
        Set-Location $serviceDir
        python -m compileall -q src
        if ($LASTEXITCODE -ne 0) { throw "Python compilation failed." }
        uv run ruff check
        if ($LASTEXITCODE -ne 0) { throw "Ruff linting failed." }
    }
    "web" {
        Write-Host "Validating Next.js frontend"
        $serviceDir = "frontend\web"
        if (-not (Test-Path $serviceDir)) { throw "Directory $serviceDir not found." }
        Set-Location $serviceDir
        pnpm build
        if ($LASTEXITCODE -ne 0) { throw "Next.js build failed." }
        pnpm lint
        if ($LASTEXITCODE -ne 0) { throw "Next.js linting failed." }
        pnpm test
        if ($LASTEXITCODE -ne 0) { throw "Next.js tests failed." }
    }
}

Write-Host "Validation successful for scope $Scope."
exit 0
