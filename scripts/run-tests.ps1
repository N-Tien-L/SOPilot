param (
    [Parameter(Mandatory=$true)]
    [ValidateSet("core-api", "auth-service", "user-service", "knowledge-service", "metadata-service", "feedback-service", "ai-qa-service", "ingestion-service", "ai-service", "api-gateway", "frontend")]
    [string]$Scope,

    [Parameter(Mandatory=$false)]
    [ValidateSet("unit", "integration", "all")]
    [string]$Type = "all"
)

$ErrorActionPreference = "Stop"

$repoRoot = git rev-parse --show-toplevel 2>$null
if (-not $repoRoot -or -not (Test-Path $repoRoot)) {
    $repoRoot = (Resolve-Path "$PSScriptRoot\..").ProviderPath
}
$BaseDir = $repoRoot

Write-Host "Running tests for scope: $Scope (Type: $Type)" -ForegroundColor Cyan

$ExitCode = 0

switch ($Scope) {
    # core-api: -Type unit = surefire unit tests; -Type all = mvnw verify, which also runs the
    # *IT Testcontainers suites (needs Docker).
    { $_ -in "core-api", "auth-service", "user-service", "knowledge-service", "metadata-service", "feedback-service" } {
        $ServiceDir = Join-Path $BaseDir "services\$Scope"
        Set-Location $ServiceDir
        Write-Host "Running Java tests in $ServiceDir..."
        if ($Type -eq "integration") {
            Write-Error "No separate integration test profile is configured for $Scope. Use -Type all for Maven verify; this does not prove platform E2E coverage."
        }
        $mvnCmd = if ($env:OS -eq "Windows_NT") { ".\mvnw.cmd" } else { "./mvnw" }
        $mvnPhase = if ($Type -eq "all") { "verify" } else { "test" }
        & $mvnCmd $mvnPhase
        $ExitCode = $LASTEXITCODE
        Set-Location $BaseDir
    }
    { $_ -in "ai-qa-service", "ingestion-service" } {
        $ServiceDir = Join-Path $BaseDir "services\$Scope"
        Set-Location $ServiceDir
        Write-Host "Running Python tests in $ServiceDir..."
        $pytestArgs = if ($Type -eq "unit") { "tests/unit" } elseif ($Type -eq "integration") { "tests/integration" } else { "tests/" }
        if (-not (Test-Path $pytestArgs)) {
            Write-Error "No $Type test directory exists for $Scope ($pytestArgs). Use -Type all for the current mixed suite."
        }
        $pytestTemp = Join-Path $ServiceDir ("scratch\pytest-" + [guid]::NewGuid().ToString("N"))
        uv run pytest $pytestArgs -v --basetemp $pytestTemp
        $ExitCode = $LASTEXITCODE
        Set-Location $BaseDir
    }
    "ai-service" {
        $ServiceDir = Join-Path $BaseDir "services\ai-service"
        Set-Location $ServiceDir
        Write-Host "Running Python tests in $ServiceDir..."
        $pytestArgs = if ($Type -eq "integration") { "tests/integration" } elseif ($Type -eq "unit") { "tests/unit" } else { "tests/" }
        if (-not (Test-Path $pytestArgs)) {
            Write-Error "No $Type test directory exists for $Scope ($pytestArgs)."
        }
        # Extras: dev tools plus the optional PDF adapter (Docling). PDF tests skip if absent.
        uv run --extra dev --extra pdf pytest $pytestArgs -v
        $ExitCode = $LASTEXITCODE
        Set-Location $BaseDir
    }
    "api-gateway" {
        $ServiceDir = Join-Path $BaseDir "services\api-gateway"
        Set-Location $ServiceDir
        Write-Host "Running NestJS tests in $ServiceDir..."
        if ($Type -eq "integration" -and -not (Test-Path "test/jest-e2e.json")) {
            Write-Error "No separate gateway E2E suite is configured. Use -Type all for the current Jest suite."
        }
        $pnpmCmd = if ($Type -eq "integration") { "pnpm test:e2e" } else { "pnpm test" }
        Invoke-Expression $pnpmCmd
        $ExitCode = $LASTEXITCODE
        Set-Location $BaseDir
    }
    "frontend" {
        $ServiceDir = Join-Path $BaseDir "frontend\web"
        Set-Location $ServiceDir
        Write-Host "Running Next.js tests in $ServiceDir..."
        $packageJson = Get-Content "package.json" -Raw | ConvertFrom-Json
        if (-not $packageJson.scripts.test) {
            Write-Error "Frontend has no test script. Build/typecheck/lint are separate gates; component/E2E tests still need implementation."
        }
        Invoke-Expression "pnpm test"
        $ExitCode = $LASTEXITCODE
        Set-Location $BaseDir
    }
}

if ($ExitCode -eq 0) {
    Write-Host "✅ All tests passed for $Scope" -ForegroundColor Green
} else {
    Write-Host "❌ Tests failed for $Scope with exit code $ExitCode" -ForegroundColor Red
}

exit $ExitCode
