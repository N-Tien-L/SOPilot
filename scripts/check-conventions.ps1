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

$violations = @()

# Check branch name convention
$branchName = git rev-parse --abbrev-ref HEAD
if ($branchName -notmatch "^(feat|fix|chore|docs|refactor|test)/$Scope-.*$") {
    $violations += "Branch name '$branchName' does not follow convention: {type}/$Scope-{short-name}"
}

# Check changed files
$changedFiles = @(git diff --name-only HEAD) + @(git ls-files --others --exclude-standard)
foreach ($file in $changedFiles) {
    $file = $file.Replace('/', '\')
    # Check correct service directory
    if ($Scope -eq "web") {
        if (-not $file.StartsWith("frontend\web")) {
            $violations += "File changed outside frontend\web: $file"
        }
    }
    elseif ($Scope -eq "gateway") {
        if (-not $file.StartsWith("services\api-gateway")) {
            $violations += "File changed outside services\api-gateway: $file"
        }
    }
    elseif ($Scope -ne "infra") {
        $expectedDir = "services\$Scope-service"
        if (-not $file.StartsWith($expectedDir)) {
            $violations += "File changed outside ${expectedDir}: $file"
        }
    }

    # Check for .env files
    if (($file -match '(^|\\)\.env($|\.)') -and ($file -notmatch '\.env\.example$')) {
        $violations += ".env file included in diff: $file"
    }
}

# Check for debug statements
$diffOutput = git diff HEAD | Where-Object { $_ -match '^\+(?!\+)' }
if ($diffOutput -match "console\.log" -or $diffOutput -match "System\.out\.println" -or $diffOutput -match "print\(") {
    $violations += "Debug statements found in diff (console.log, System.out.println, or print)."
}

if ($violations.Count -gt 0) {
    Write-Host "Convention violations found:"
    foreach ($v in $violations) {
        Write-Host "- $v" -ForegroundColor Red
    }
    exit 1
}

Write-Host "All convention checks passed."
exit 0
