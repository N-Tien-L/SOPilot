$ErrorActionPreference = "Continue"

Write-Host "========================================="
Write-Host " SOPilot Pre-Commit Verification"
Write-Host "========================================="

$FailedChecks = 0

$repoRoot = git rev-parse --show-toplevel 2>$null
if (-not $repoRoot -or -not (Test-Path $repoRoot)) {
    $repoRoot = (Resolve-Path "$PSScriptRoot\..").ProviderPath
}
Set-Location $repoRoot

# 1. Identify Changed Files
Write-Host "`n[1/7] Identifying changed files..." -ForegroundColor Cyan
$ChangedFiles = git diff --cached --name-only
if (-not $ChangedFiles) {
    $ChangedFiles = git diff --name-only HEAD
}

if (-not $ChangedFiles) {
    Write-Host "No changed files detected." -ForegroundColor Yellow
} else {
    Write-Host "Changed files:"
    $ChangedFiles | ForEach-Object { Write-Host "  - $_" }
}

# 2. Check for Debug Statements & Secrets in Diff
Write-Host "`n[2/7] Checking for debug statements and secrets..." -ForegroundColor Cyan
$DiffContent = git diff --cached -- ':!scripts/*' ':!docs/*' ':!*.md'
if (-not $DiffContent) {
    $DiffContent = git diff HEAD -- ':!scripts/*' ':!docs/*' ':!*.md'
}

$AddedLines = $DiffContent | Where-Object { $_ -match '^\+(?!\+)' }
$DebugPattern = "(console\.log|System\.out\.println|\bprint\()"
$SecretPattern = "(?i)(password|api_key|secret|token)\s*=\s*['`"][^'`"]+['`"]"
$HasDebug = [bool]($AddedLines | Where-Object { $_ -match $DebugPattern })
$HasSecrets = [bool]($AddedLines | Where-Object { $_ -match $SecretPattern })
$EnvFiles = $ChangedFiles | Where-Object { ($_ -match '(^|/)\.env($|\.)') -and ($_ -notmatch '\.env\.example$') }
if ($EnvFiles) {
    Write-Host "Environment files must not be committed: $($EnvFiles -join ', ')" -ForegroundColor Red
    $FailedChecks++
}
$TodoLines = $AddedLines | Where-Object {
    ($_ -match "(?i)\b(TODO|FIXME)\b") -and ($_ -notmatch "[A-Z0-9]+-\d+")
}
$HasInvalidTodo = [bool]$TodoLines

if ($HasDebug) {
    Write-Host "❌ Found debug statements (console.log, print, etc.)" -ForegroundColor Red
    $FailedChecks++
} else { Write-Host "✅ No debug statements found" -ForegroundColor Green }

if ($HasSecrets) {
    Write-Host "❌ Found potential secrets/hardcoded credentials" -ForegroundColor Red
    $FailedChecks++
} else { Write-Host "✅ No secrets found" -ForegroundColor Green }

if ($HasInvalidTodo) {
    Write-Host "❌ Found TODO/FIXME without a ticket reference" -ForegroundColor Red
    $FailedChecks++
} else { Write-Host "✅ All TODOs have ticket references" -ForegroundColor Green }

# 3. Determine Affected Services & Build/Test
Write-Host "`n[3/7] Determining affected services and running tests..." -ForegroundColor Cyan
$AffectedServices = @()

foreach ($File in $ChangedFiles) {
    if ($File -match "^services/([^/]+)/") {
        $Service = $Matches[1]
        if ($AffectedServices -notcontains $Service) { $AffectedServices += $Service }
    } elseif ($File -match "^frontend/web/") {
        if ($AffectedServices -notcontains "frontend") { $AffectedServices += "frontend" }
    }
}

if ($AffectedServices.Count -eq 0) {
    Write-Host "No specific services affected by changes." -ForegroundColor Yellow
} else {
    foreach ($Service in $AffectedServices) {
        Write-Host "-> Testing $Service..."

        # Call run-tests.ps1 for the service
        $ScriptPath = Join-Path $PSScriptRoot "run-tests.ps1"
        if (-not (Test-Path $ScriptPath)) {
            $ScriptPath = Join-Path $repoRoot "scripts\run-tests.ps1"
        }

        if ($Service -eq "frontend") {
            & $ScriptPath -Scope "frontend"
        } else {
            & $ScriptPath -Scope $Service
        }

        if ($LASTEXITCODE -ne 0) {
            Write-Host "❌ Build/Test failed for $Service" -ForegroundColor Red
            $FailedChecks++
        } else {
            Write-Host "✅ Build/Test passed for $Service" -ForegroundColor Green
        }
    }
}

# 4. Validate Docker Compose Config (V2 first; V1 kept until V2-17)
Write-Host "`n[4/7] Validating Docker Compose config..." -ForegroundColor Cyan
foreach ($ComposeFile in @("docker-compose.v2.yml", "docker-compose.yml")) {
    if (Test-Path $ComposeFile) {
        # V2 requires its secrets (${VAR:?}); validate structure with the placeholder values, never with .env.
        if ($ComposeFile -eq "docker-compose.v2.yml") {
            docker compose -f $ComposeFile --env-file .env.example config --quiet
        } else {
            docker compose -f $ComposeFile config --quiet
        }
        if ($LASTEXITCODE -ne 0) {
            Write-Host "❌ $ComposeFile is invalid" -ForegroundColor Red
            $FailedChecks++
        } else {
            Write-Host "✅ $ComposeFile is valid" -ForegroundColor Green
        }
    } else {
        Write-Host "⚠️ $ComposeFile not found, skipping." -ForegroundColor Yellow
    }
}

# 5. V2 Flyway migrations: naming, numbering, immutability, no destructive DDL
Write-Host "`n[5/7] Checking V2 migrations..." -ForegroundColor Cyan
& (Join-Path $PSScriptRoot "check-migrations.ps1")
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Migration check failed" -ForegroundColor Red
    $FailedChecks++
} else {
    Write-Host "✅ Migration check passed" -ForegroundColor Green
}

# 6. Docs: frontmatter, status vocabulary, PLAN counters, ticket relations, links
Write-Host "`n[6/7] Checking docs..." -ForegroundColor Cyan
& (Join-Path $PSScriptRoot "check-docs.ps1")
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Docs check failed" -ForegroundColor Red
    $FailedChecks++
} else {
    Write-Host "✅ Docs check passed" -ForegroundColor Green
}

# 7. Summary
Write-Host "`n========================================="
if ($FailedChecks -gt 0) {
    Write-Host "❌ Pre-commit verification FAILED ($FailedChecks errors)" -ForegroundColor Red
    exit 1
} else {
    Write-Host "✅ Pre-commit verification PASSED!" -ForegroundColor Green
    exit 0
}
