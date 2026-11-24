param (
    [Parameter(Mandatory=$true)]
    [ValidateSet("core-api", "ai-service", "frontend")]
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
    "core-api" {
        $ServiceDir = Join-Path $BaseDir "services\core-api"
        Set-Location $ServiceDir
        Write-Host "Running Java tests in $ServiceDir..."
        if ($Type -eq "integration") {
            Write-Error "No separate integration test profile is configured for core-api. Use -Type all for Maven verify."
        }
        $mvnCmd = if ($env:OS -eq "Windows_NT") { ".\mvnw.cmd" } else { "./mvnw" }
        $mvnPhase = if ($Type -eq "all") { "verify" } else { "test" }
        # Maven writes JVM warnings (e.g. Mockito self-attach) to stderr; with "Stop" Windows
        # PowerShell would turn the first one into a terminating error. Judge by the exit code.
        $ErrorActionPreference = "Continue"
        & $mvnCmd -B $mvnPhase 2>&1 | ForEach-Object { "$_" }
        $ExitCode = $LASTEXITCODE
        $ErrorActionPreference = "Stop"
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
    "frontend" {
        $ServiceDir = Join-Path $BaseDir "frontend\web"
        Set-Location $ServiceDir
        Write-Host "Running Vitest in $ServiceDir..."
        if ($Type -eq "integration") {
            Write-Error "The frontend has only Vitest unit tests. Use -Type unit or -Type all."
        }
        pnpm test
        $ExitCode = $LASTEXITCODE
        Set-Location $BaseDir
    }
}

if ($ExitCode -eq 0) {
    Write-Host "All tests passed for $Scope" -ForegroundColor Green
} else {
    Write-Host "Tests failed for $Scope with exit code $ExitCode" -ForegroundColor Red
}

exit $ExitCode
