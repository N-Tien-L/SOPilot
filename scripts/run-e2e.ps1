<#
.SYNOPSIS
    Runs the end-to-end suite (tests/e2e, Playwright) against the stack that is already running.
.DESCRIPTION
    Checks that core-api, the web app and ai-service answer, then runs the suite. The suite builds a
    throwaway TEAM workspace through the API (people in every role, departments, publishers, two
    documents) and deletes it when it ends, so the owner's own data is never touched.
    Never starts or stops containers and never deletes volumes.
.PARAMETER Keep
    Keep the throwaway workspace after the run (for exploring it by hand or with a browser agent).
    Remove it later with: pnpm --dir tests/e2e cleanup
.PARAMETER Spec
    Optional spec file or title filter passed to Playwright, for example "03-documents".
.EXAMPLE
    ./scripts/run-e2e.ps1
    ./scripts/run-e2e.ps1 -Keep
    ./scripts/run-e2e.ps1 -Spec 03-documents
#>
param(
    [switch]$Keep,
    [string]$Spec = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$e2e = Join-Path $root "tests/e2e"

$web = if ($env:E2E_BASE_URL) { $env:E2E_BASE_URL } else { "http://localhost:3000" }
$core = if ($env:E2E_API_URL) { $env:E2E_API_URL } else { "http://localhost:8080" }
$ai = if ($env:E2E_AI_URL) { $env:E2E_AI_URL } else { "http://localhost:8000" }

function Test-Url($name, $url) {
    try {
        $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 10
        Write-Host "[OK]   $name $url ($($r.StatusCode))" -ForegroundColor Green
        return $true
    } catch {
        Write-Host "[FAIL] $name $url : $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

$up = $true
$up = (Test-Url "core-api" "$core/actuator/health") -and $up
$up = (Test-Url "web" "$web/login") -and $up
# ai-service is needed only for the READY check and chat; the other specs still run without it.
$aiUp = Test-Url "ai-service" "$ai/health"
if (-not $up) {
    Write-Host "The stack is not up. See docs/operations/local-development.md (never use 'docker compose down -v')." -ForegroundColor Red
    exit 2
}
if (-not $aiUp) { Write-Host "[WARN] ai-service is down: 05-ingest-ready will fail." -ForegroundColor Yellow }

if (-not (Test-Path (Join-Path $e2e "node_modules"))) {
    pnpm --dir $e2e install --frozen-lockfile
    pnpm --dir $e2e exec playwright install chromium
}

if ($Keep) { $env:E2E_KEEP = "1" }
$pw = @("--dir", $e2e, "run", "test")
if ($Spec) { $pw += $Spec }
# Windows PowerShell 5.1 turns anything a native program writes to stderr into an error; pnpm and Node
# write warnings there, so do not let that stop the script. The exit code is what counts.
Remove-Item Env:FORCE_COLOR -ErrorAction SilentlyContinue
$ErrorActionPreference = "Continue"
& pnpm @pw
$code = $LASTEXITCODE
$ErrorActionPreference = "Stop"

$results = Join-Path $e2e "results.json"
if (Test-Path $results) {
    $json = Get-Content $results -Raw | ConvertFrom-Json
    $s = $json.stats
    Write-Host ""
    Write-Host "Expected: $($s.expected)  Unexpected (failed): $($s.unexpected)  Flaky: $($s.flaky)  Skipped: $($s.skipped)"
    Write-Host "HTML report: pnpm --dir tests/e2e report   (tests/e2e/report)"
}
if ($Keep) { Write-Host "Workspace kept. Personas are in tests/e2e/.world.json. Remove it with: pnpm --dir tests/e2e cleanup" }
exit $code
