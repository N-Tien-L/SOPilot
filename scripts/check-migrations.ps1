<#
.SYNOPSIS
    Checks the V2 Flyway chains in infrastructure/db/migrations/<chain>/ (core, rag).

.DESCRIPTION
    Read-only. Fails (exit 1) when:
      - a file name is not V<NNN>__<snake_case>.sql;
      - versions in a chain are duplicated or not 1..n without gaps;
      - a migration that exists in HEAD or at the merge-base with -BaseRef was modified, deleted or
        renamed (Flyway checksums: an applied migration must never change; add a new one instead);
      - a migration contains DROP SCHEMA, DROP DATABASE, DROP TABLE or TRUNCATE.
    Each violation is printed as "MIGRATION <file>: <reason>".

.PARAMETER BaseRef
    Branch or commit whose migrations are immutable. Default "main". In CI pass the PR base,
    e.g. -BaseRef origin/main. If the ref does not exist, only HEAD is used and a warning is printed.

.EXAMPLE
    ./scripts/check-migrations.ps1
    ./scripts/check-migrations.ps1 -BaseRef origin/develop
#>
param (
    [string]$BaseRef = "main"
)

$ErrorActionPreference = "Stop"

$repoRoot = git rev-parse --show-toplevel 2>$null
if (-not $repoRoot -or -not (Test-Path $repoRoot)) {
    $repoRoot = (Resolve-Path "$PSScriptRoot\..").ProviderPath
}
Set-Location $repoRoot

$migrationsRel = "infrastructure/db/migrations"
$violations = New-Object System.Collections.Generic.List[string]

if (-not (Test-Path $migrationsRel)) {
    Write-Host "No $migrationsRel directory; nothing to check."
    exit 0
}

# 1. Naming and numbering per chain.
foreach ($chain in Get-ChildItem -Path $migrationsRel -Directory) {
    $versions = @{}
    foreach ($file in Get-ChildItem -Path $chain.FullName -File) {
        $rel = "$migrationsRel/$($chain.Name)/$($file.Name)"
        if ($file.Name -notmatch '^V(\d{3})__[a-z0-9]+(_[a-z0-9]+)*\.sql$') {
            $violations.Add("MIGRATION ${rel}: name must be V<NNN>__<snake_case>.sql")
            continue
        }
        $v = [int]$Matches[1]
        if ($versions.ContainsKey($v)) {
            $violations.Add("MIGRATION ${rel}: duplicate version V$($Matches[1]) (also $($versions[$v]))")
        } else {
            $versions[$v] = $file.Name
        }

        $sql = Get-Content -Path $file.FullName -Raw
        if ($sql -match '(?i)\b(DROP\s+(SCHEMA|DATABASE|TABLE)|TRUNCATE)\b') {
            $violations.Add("MIGRATION ${rel}: destructive DDL '$($Matches[1])' is not allowed; migrations are additive")
        }
    }
    $sorted = @($versions.Keys | Sort-Object)
    for ($i = 0; $i -lt $sorted.Count; $i++) {
        if ($sorted[$i] -ne ($i + 1)) {
            $violations.Add("MIGRATION $migrationsRel/$($chain.Name): versions must run 1..n without gaps; expected V$('{0:D3}' -f ($i + 1)), found V$('{0:D3}' -f $sorted[$i])")
            break
        }
    }
}

# 2. Immutability: compare the working tree with HEAD, and with the merge-base of BaseRef.
$bases = @("HEAD")
git rev-parse --verify --quiet "$BaseRef^{commit}" *> $null
if ($LASTEXITCODE -eq 0) {
    $mergeBase = git merge-base HEAD $BaseRef
    if ($LASTEXITCODE -eq 0 -and $mergeBase) { $bases += $mergeBase.Trim() }
} else {
    Write-Host "WARNING: ref '$BaseRef' not found; checking immutability against HEAD only." -ForegroundColor Yellow
}

foreach ($base in $bases) {
    $changes = git diff --name-status --no-renames $base -- $migrationsRel
    foreach ($line in $changes) {
        if (-not $line) { continue }
        $parts = $line -split "`t"
        $status = $parts[0]
        $path = $parts[1]
        if ($status -ne "A") {
            $label = if ($base -eq "HEAD") { "HEAD" } else { "$BaseRef (merge-base $($base.Substring(0, 8)))" }
            $what = switch -Regex ($status) { '^D' { "deleted" } default { "modified" } }
            $violations.Add("MIGRATION ${path}: $what, but it already exists in $label; never edit an applied migration, add the next V<NNN> instead")
        }
    }
}

$unique = @($violations | Select-Object -Unique)
if ($unique.Count -gt 0) {
    foreach ($v in $unique) { Write-Host $v -ForegroundColor Red }
    Write-Host "Migration check FAILED ($($unique.Count) violation(s))." -ForegroundColor Red
    exit 1
}

Write-Host "Migration check passed ($migrationsRel; immutable against: $($bases -join ', '))." -ForegroundColor Green
exit 0
