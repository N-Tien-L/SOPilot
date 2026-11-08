<#
.SYNOPSIS
  Validates docs/ frontmatter, status vocabulary, PLAN counters, ticket dependencies and links.
.DESCRIPTION
  Read-only. Run from the repo root: ./scripts/check-docs.ps1
  Rules live in docs/README.md ("Quy uoc frontmatter"). Exit code 1 if any error is found.
  Archived docs (docs/_archive) are checked for frontmatter and links only, never for counters.
#>
$ErrorActionPreference = "Stop"

$repoRoot = git rev-parse --show-toplevel 2>$null
if (-not $repoRoot -or -not (Test-Path $repoRoot)) {
    $repoRoot = (Resolve-Path "$PSScriptRoot\..").ProviderPath
}
Set-Location $repoRoot

$errors = New-Object System.Collections.Generic.List[string]
function Add-Err([string]$file, [string]$msg) { $errors.Add("${file}: $msg") }

function Read-Frontmatter([string]$path) {
    $text = [System.IO.File]::ReadAllText($path, [System.Text.Encoding]::UTF8)
    if ($text -notmatch '(?s)\A---\r?\n(.*?)\r?\n---') { return $null }
    $fm = @{}
    $lines = $Matches[1] -split '\r?\n'
    $key = $null
    foreach ($line in $lines) {
        if ($line -match '^([A-Za-z_]+):\s*(.*)$') {
            $key = $Matches[1]
            $val = $Matches[2].Trim()
            $fm[$key] = $val
        } elseif ($key -and $line -match '^\s+-\s+(.*)$') {
            $fm[$key] = ($fm[$key] + ' ' + $Matches[1].Trim()).Trim()
        }
    }
    return $fm
}

function Get-List([string]$value) {
    if (-not $value) { return @() }
    return @([regex]::Matches($value, '[A-Za-z0-9]+(?:-[A-Za-z0-9]+)+') | ForEach-Object { $_.Value })
}

$allowedStatus = @{
    PRD    = @('draft', 'approved', 'superseded')
    ADR    = @('draft', 'approved', 'superseded')
    TECH   = @('draft', 'approved', 'superseded')
    PLAN   = @('draft', 'approved', 'superseded')
    TICKET = @('todo', 'in-progress', 'review', 'done', 'superseded')
    REPORT = @('draft', 'final')
}

$files = Get-ChildItem -Path docs -Recurse -Filter *.md -File | Where-Object {
    $rel = $_.FullName.Substring($repoRoot.Length + 1).Replace('\', '/')
    $rel -notmatch '/templates/' -and $rel -notmatch '^docs/portfolio/' -and $rel -ne 'docs/README.md'
}

$docs = @()
foreach ($f in $files) {
    $rel = $f.FullName.Substring($repoRoot.Length + 1).Replace('\', '/')
    $fm = Read-Frontmatter $f.FullName
    if ($null -eq $fm) { Add-Err $rel 'missing frontmatter'; continue }

    foreach ($k in 'id', 'title', 'status', 'created', 'updated', 'author') {
        if (-not $fm.ContainsKey($k) -or [string]::IsNullOrWhiteSpace($fm[$k])) { Add-Err $rel "missing field '$k'" }
    }
    foreach ($k in 'created', 'updated') {
        if ($fm.ContainsKey($k) -and $fm[$k] -notmatch '^\d{4}-\d{2}-\d{2}$') { Add-Err $rel "'$k' must be YYYY-MM-DD (got '$($fm[$k])')" }
    }
    if ($fm.ContainsKey('author') -and $fm['author'].Trim('"') -ne 'Owner') {
        Add-Err $rel ('author must be "Owner" (got ' + $fm['author'] + ')')
    }

    $name = $f.Name
    $kind = $null
    if ($name -match '^PRD-') { $kind = 'PRD' }
    elseif ($name -match '^ADR-') { $kind = 'ADR' }
    elseif ($name -match '^TECH-') { $kind = 'TECH' }
    elseif ($name -match '^PLAN-') { $kind = 'PLAN' }
    elseif ($rel -match '/tickets/') { $kind = 'TICKET' }
    elseif ($name -match '^(AUDIT|RESEARCH|HANDOFF)-') { $kind = 'REPORT' }
    if (-not $kind) { Add-Err $rel 'unknown document kind (file name prefix not PRD/ADR/TECH/PLAN/AUDIT/RESEARCH/HANDOFF)'; continue }

    if ($fm.ContainsKey('status') -and $allowedStatus[$kind] -notcontains $fm['status']) {
        Add-Err $rel "status '$($fm['status'])' not allowed for $kind (allowed: $($allowedStatus[$kind] -join ', '))"
    }

    if ($kind -eq 'REPORT') {
        $prefix = ($name -split '-')[0]
        $expectType = $prefix.ToLower()
        if ($fm.ContainsKey('id') -and -not $fm['id'].StartsWith($prefix + '-')) { Add-Err $rel "id must start with '$prefix-'" }
        if (-not $fm.ContainsKey('type') -or $fm['type'] -ne $expectType) { Add-Err $rel "type must be '$expectType' to match the file name prefix (got '$($fm['type'])')" }
    }

    # refs must resolve (root-relative paths in frontmatter)
    $raw = [System.IO.File]::ReadAllText($f.FullName, [System.Text.Encoding]::UTF8)
    if ($raw -match '(?s)\A---\r?\n(.*?)\r?\n---') {
        foreach ($m in [regex]::Matches($Matches[1], '(?<![\w/])((?:docs|\.agent|temp)/[\w\-./]+\.md)')) {
            $p = $m.Groups[1].Value
            if ($p -like 'temp/*') { continue }
            if (-not (Test-Path $p)) { Add-Err $rel "frontmatter ref does not exist: $p" }
        }
    }

    # markdown links must resolve
    $body = $raw
    foreach ($m in [regex]::Matches($body, '\]\(([^)\s#]+)(?:#[^)]*)?\)')) {
        $l = $m.Groups[1].Value
        if ($l -match '^[a-zA-Z][a-zA-Z0-9+.-]*:') { continue }
        $target = Join-Path (Split-Path $f.FullName -Parent) ($l -replace '/', '\')
        if (-not (Test-Path $target)) { Add-Err $rel "broken link: $l" }
    }

    $docs += [pscustomobject]@{ Rel = $rel; Kind = $kind; Fm = $fm; Archived = ($rel -like 'docs/_archive/*') }
}

# ---- PLAN counters and ticket relations (live docs only) ----
$tickets = $docs | Where-Object { $_.Kind -eq 'TICKET' }
$plans = $docs | Where-Object { $_.Kind -eq 'PLAN' }
$ticketById = @{}
foreach ($t in $tickets) { if ($t.Fm.ContainsKey('id')) { $ticketById[$t.Fm['id']] = $t } }

foreach ($plan in ($plans | Where-Object { -not $_.Archived })) {
    $planId = $plan.Fm['id']
    $mine = @($tickets | Where-Object { $_.Fm['parent_plan'] -eq $planId })
    if ($plan.Fm['status'] -eq 'superseded') { continue }
    $done = @($mine | Where-Object { $_.Fm['status'] -eq 'done' }).Count
    $review = @($mine | Where-Object { $_.Fm['status'] -eq 'review' }).Count
    $exp = @{ total_tickets = $mine.Count; completed_tickets = $done; review_tickets = $review; implemented_tickets = ($done + $review) }
    foreach ($k in $exp.Keys) {
        if (-not $plan.Fm.ContainsKey($k)) { Add-Err $plan.Rel "missing counter '$k'"; continue }
        if ([int]$plan.Fm[$k] -ne $exp[$k]) { Add-Err $plan.Rel "$k is $($plan.Fm[$k]) but tickets give $($exp[$k])" }
    }
}

# open tickets under a superseded plan
$supersededPlans = @($plans | ForEach-Object { if ($_.Fm['status'] -eq 'superseded') { $_.Fm['id'] } })
foreach ($t in $tickets) {
    if ($supersededPlans -contains $t.Fm['parent_plan'] -and @('done', 'superseded') -notcontains $t.Fm['status']) {
        Add-Err $t.Rel "status '$($t.Fm['status'])' under superseded plan $($t.Fm['parent_plan']) (must be done or superseded)"
    }
}

# depends_on <-> blocks symmetry among live tickets
foreach ($t in ($tickets | Where-Object { -not $_.Archived })) {
    $id = $t.Fm['id']
    foreach ($dep in (Get-List $t.Fm['depends_on'])) {
        if (-not $ticketById.ContainsKey($dep)) { Add-Err $t.Rel "depends_on unknown ticket $dep"; continue }
        if ((Get-List $ticketById[$dep].Fm['blocks']) -notcontains $id) { Add-Err $t.Rel "depends_on $dep but $dep.blocks does not list $id" }
    }
    foreach ($blk in (Get-List $t.Fm['blocks'])) {
        if (-not $ticketById.ContainsKey($blk)) { Add-Err $t.Rel "blocks unknown ticket $blk"; continue }
        if ((Get-List $ticketById[$blk].Fm['depends_on']) -notcontains $id) { Add-Err $t.Rel "blocks $blk but $blk.depends_on does not list $id" }
    }
}

Write-Host "Checked $($docs.Count) documents."
if ($errors.Count -gt 0) {
    $errors | Sort-Object | ForEach-Object { Write-Host "ERROR $_" -ForegroundColor Red }
    Write-Host "docs check FAILED ($($errors.Count) errors)" -ForegroundColor Red
    exit 1
}
Write-Host "docs check passed" -ForegroundColor Green
exit 0
