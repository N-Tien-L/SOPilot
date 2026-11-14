<#
.SYNOPSIS
  Validates SOPilot documentation: frontmatter, ids, statuses, placement, PLAN/ticket integrity, links and anchors.
.DESCRIPTION
  Read-only. Run from anywhere inside the repo:
    ./scripts/docs/check-docs.ps1               # strict (default): errors fail (exit 1); pre-commit and CI
    ./scripts/docs/check-docs.ps1 -Mode audit   # every check on every file incl. docs/archive; all findings are warnings, exit 0
  Conventions: docs/README.md ("Conventions"). The kind of a document is decided by its location (see $Kinds).
  Strict mode checks docs/archive only for broken links and duplicate ids; archived files are history and are not
  required to follow the current conventions.
  Works on Windows PowerShell 5.1 and pwsh 7 (Linux CI): paths use '/', and link targets are checked case-sensitively
  against `git ls-files`, so a case mismatch that Windows tolerates still fails here.
#>
param(
    [ValidateSet('strict', 'audit')]
    [string]$Mode = 'strict'
)
$ErrorActionPreference = 'Stop'

$repoRoot = (git rev-parse --show-toplevel 2>$null)
if (-not $repoRoot) { $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).ProviderPath }
Set-Location $repoRoot

$audit = ($Mode -eq 'audit')
$errors = New-Object System.Collections.Generic.List[string]
$warnings = New-Object System.Collections.Generic.List[string]
function Add-Err([string]$file, [string]$msg) {
    if ($audit) { $warnings.Add("${file}: $msg") } else { $errors.Add("${file}: $msg") }
}
function Add-Warn([string]$file, [string]$msg) { $warnings.Add("${file}: $msg") }

# ---------------------------------------------------------------- statuses and kinds
$General = @('draft', 'approved', 'superseded', 'archived')
$Status = @{
    general     = $General
    ticket      = @('todo', 'in_progress', 'review', 'done', 'blocked')
    research    = @('draft', 'final', 'superseded')
    report      = @('draft', 'final')
}
$Base = @('title', 'status', 'created', 'updated', 'author')

# Ordered: first match wins. Fm = frontmatter required; Id = id regex ('' = no id check, $null = id not used).
$Kinds = @(
    @{ Name = 'index';       Re = '^docs/README\.md$';                                         Fm = $false }
    @{ Name = 'archive-index'; Re = '^docs/archive/README\.md$';                               Fm = $false }
    @{ Name = 'archive';     Re = '^docs/archive/';                                          Fm = $false; Archive = $true }
    @{ Name = 'template';    Re = '^docs/templates/[^/]+\.md$';                                Fm = $false; Template = $true }
    @{ Name = 'portfolio';   Re = '^docs/portfolio/[^/]+\.md$';                                Fm = $false }
    @{ Name = 'prd';         Re = '^docs/product/[^/]+\.md$';                                  Fm = $true; St = 'general'; Id = '^PRD-[A-Z0-9-]+$' }
    @{ Name = 'adr';         Re = '^docs/architecture/decisions/[^/]+\.md$';                   Fm = $true; St = 'general'; Id = '^ADR-\d{3}$' }
    @{ Name = 'design';      Re = '^docs/architecture/(system-overview\.md|(components|data|domain|api)/[^/]+\.md)$'; Fm = $true; St = 'general'; Id = '^TECH-[A-Za-z0-9-]+$'; IdOptional = $true }
    @{ Name = 'initiative';  Re = '^docs/execution/initiatives/[^/]+/README\.md$';             Fm = $true; St = 'general' }
    @{ Name = 'plan';        Re = '^docs/execution/initiatives/[^/]+/PLAN\.md$';               Fm = $true; St = 'general'; Id = '^PLAN-[A-Z0-9-]+$' }
    @{ Name = 'ticket';      Re = '^docs/execution/initiatives/[^/]+/tickets/[^/]+\.md$';      Fm = $true; St = 'ticket'; Id = '^(V2-\d{2}|TICKET-\d{3})$' }
    @{ Name = 'design';      Re = '^docs/execution/initiatives/[^/]+/designs/[^/]+\.md$';      Fm = $true; St = 'general'; Id = '^TECH-[A-Za-z0-9-]+$'; IdOptional = $true }
    @{ Name = 'guide';       Re = '^docs/quality/(testing-strategy|quality-gates)\.md$';      Fm = $true; St = 'general' }
    @{ Name = 'test-plan';   Re = '^docs/quality/test-plans/[^/]+\.md$';                       Fm = $true; St = 'general'; Id = '^TEST-PLAN-\d{3}$' }
    @{ Name = 'test-report'; Re = '^docs/quality/test-reports/[^/]+\.md$';                     Fm = $true; St = 'report'; Id = '^(TEST-REPORT-\d{3}|AUDIT-[A-Za-z0-9-]+)$'; Extra = @('verdict') }
    @{ Name = 'runbook';     Re = '^docs/operations/[^/]+\.md$';                               Fm = $true; St = 'general' }
    @{ Name = 'research';    Re = '^docs/research/[^/]+\.md$';                                 Fm = $true; St = 'research'; Id = '^(RESEARCH|AUDIT)-[A-Za-z0-9-]+$' }
    @{ Name = 'handoff';     Re = '^docs/handoffs/[^/]+\.md$';                                 Fm = $true; St = 'report'; Id = '^HANDOFF-[A-Za-z0-9-]+$'; IdOptional = $true }
)
# Template file name -> kind whose required fields the template must carry.
$TemplateKinds = @{
    'prd.md' = 'prd'; 'adr.md' = 'adr'; 'design.md' = 'design'; 'initiative-readme.md' = 'initiative'; 'plan.md' = 'plan'
    'ticket.md' = 'ticket'; 'research.md' = 'research'; 'test-plan.md' = 'test-plan'; 'test-report.md' = 'test-report'
    'runbook.md' = 'runbook'; 'handoff.md' = 'handoff'
}
$KindRequired = @{
    plan   = @('total_tickets', 'completed_tickets', 'review_tickets', 'implemented_tickets')
    ticket = @('parent_plan', 'depends_on', 'blocks')
}

# ---------------------------------------------------------------- repository file index (case-sensitive)
$tracked = @(git -c core.quotepath=off ls-files -co --exclude-standard) | Where-Object { $_ }
$fileSet = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::Ordinal)
$fileSetCI = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
foreach ($t in $tracked) {
    [void]$fileSet.Add($t); [void]$fileSetCI.Add($t)
    $parts = $t.Split('/')
    for ($i = 1; $i -lt $parts.Length; $i++) {
        $d = ($parts[0..($i - 1)] -join '/')
        [void]$fileSet.Add($d); [void]$fileSetCI.Add($d)
    }
}

function Resolve-RelPath([string]$baseDir, [string]$link) {
    $joined = if ($baseDir) { "$baseDir/$link" } else { $link }
    $out = New-Object System.Collections.Generic.List[string]
    foreach ($seg in $joined.Split('/')) {
        if ($seg -eq '' -or $seg -eq '.') { continue }
        if ($seg -eq '..') { if ($out.Count -gt 0) { $out.RemoveAt($out.Count - 1) } else { return $null }; continue }
        $out.Add($seg)
    }
    return ($out -join '/')
}

# Returns $null when the path exists with exactly this case, otherwise an error message. A target that is
# gitignored ('untracked-ignored', a warning) is told apart by .gitignore, not by presence on disk: a fresh CI
# checkout does not have datasets/ or eval/datasets/, and those links must stay warnings there too.
function Test-RepoPath([string]$p) {
    if ($fileSet.Contains($p)) { return $null }
    if ($fileSetCI.Contains($p)) { return 'case mismatch' }
    if (Test-Path -LiteralPath (Join-Path $repoRoot $p)) { return 'untracked-ignored' }
    git check-ignore -q --no-index -- $p 2>$null
    if ($LASTEXITCODE -eq 0) { return 'untracked-ignored' }
    return 'missing'
}

# ---------------------------------------------------------------- markdown helpers
function Read-Text([string]$rel) { return [System.IO.File]::ReadAllText((Join-Path $repoRoot $rel), [System.Text.Encoding]::UTF8) }

function Read-Frontmatter([string]$text) {
    if ($text -notmatch '(?s)\A\uFEFF?---\r?\n(.*?)\r?\n---') { return $null }
    $fm = @{}
    $key = $null
    foreach ($line in ($Matches[1] -split '\r?\n')) {
        if ($line -match '^([A-Za-z_]+):\s*(.*)$') {
            $key = $Matches[1]
            $val = $Matches[2].Trim()
            if ($val -notmatch '^["'']') { $val = ($val -replace '\s+#.*$', '').Trim() }  # strip trailing YAML comments
            $fm[$key] = $val.Trim('"')
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

# Text outside fenced code blocks (links and headings inside code are not real).
function Get-Prose([string]$text) {
    $sb = New-Object System.Text.StringBuilder
    $inFence = $false
    foreach ($line in ($text -split '\r?\n')) {
        if ($line -match '^\s*(```|~~~)') { $inFence = -not $inFence; continue }
        if (-not $inFence) { [void]$sb.AppendLine($line) }
    }
    return $sb.ToString()
}

$anchorCache = @{}
# GitHub-style heading slugs: lowercase, drop punctuation except '-' and '_', spaces to '-', duplicates get -1, -2 ...
function Get-Anchors([string]$rel) {
    if ($anchorCache.ContainsKey($rel)) { return $anchorCache[$rel] }
    $set = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::Ordinal)
    $seen = @{}
    $prose = Get-Prose (Read-Text $rel)
    foreach ($m in [regex]::Matches($prose, '(?m)^#{1,6}[ \t]+(.+?)[ \t#]*$')) {
        $h = $m.Groups[1].Value
        $h = [regex]::Replace($h, '\[([^\]]*)\]\([^)]*\)', '$1')        # [text](url) -> text
        $h = [regex]::Replace($h, '<[^>]+>', '')                       # inline html
        $s = $h.Trim().ToLowerInvariant()
        $s = [regex]::Replace($s, '[^\p{L}\p{Mn}\p{Nd}\p{Pc} -]', '')
        $s = $s.Replace(' ', '-')
        if ($seen.ContainsKey($s)) { $seen[$s]++; $s = "$s-$($seen[$s])" } else { $seen[$s] = 0 }
        [void]$set.Add($s)
    }
    # explicit html anchors
    foreach ($m in [regex]::Matches($prose, '<a\s+(?:name|id)="([^"]+)"')) { [void]$set.Add($m.Groups[1].Value) }
    $anchorCache[$rel] = $set
    return $set
}

function Test-Links([string]$rel, [string]$text, [bool]$checkAnchors) {
    $dir = if ($rel.Contains('/')) { $rel.Substring(0, $rel.LastIndexOf('/')) } else { '' }
    $prose = Get-Prose $text
    foreach ($m in [regex]::Matches($prose, '\]\(<?([^)\s>]*)>?(?:\s+"[^"]*")?\)')) {
        $link = $m.Groups[1].Value
        if (-not $link -or $link -match '^[a-zA-Z][a-zA-Z0-9+.-]*:' -or $link.StartsWith('//')) { continue }
        $anchor = $null
        if ($link.Contains('#')) { $anchor = $link.Substring($link.IndexOf('#') + 1); $link = $link.Substring(0, $link.IndexOf('#')) }
        $link = [uri]::UnescapeDataString($link)
        if ($link -eq '') { $target = $rel } else {
            if ($link.StartsWith('/')) { Add-Err $rel "absolute link not portable: $link"; continue }
            $target = Resolve-RelPath $dir $link.TrimEnd('/')
            if ($null -eq $target) { Add-Err $rel "link escapes the repository: $link"; continue }
            $res = Test-RepoPath $target
            if ($res -eq 'untracked-ignored') { Add-Warn $rel "link to a gitignored path: $link"; continue }
            if ($res) { Add-Err $rel "broken link ($res): $link"; continue }
        }
        if ($checkAnchors -and $anchor -and $target -match '\.md$' -and $fileSet.Contains($target)) {
            $a = [uri]::UnescapeDataString($anchor).ToLowerInvariant()
            if (-not (Get-Anchors $target).Contains($a)) { Add-Err $rel "broken anchor: #$anchor in $target" }
        }
    }
}

# ---------------------------------------------------------------- per-document checks
$docs = @()
$idOwners = @{}
$docFiles = $tracked | Where-Object { $_ -like 'docs/*' -and $_ -like '*.md' }

foreach ($rel in $docFiles) {
    $kind = $null
    foreach ($k in $Kinds) { if ($rel -match $k.Re) { $kind = $k; break } }
    if (-not $kind) { Add-Err $rel 'unknown location: no document kind is defined for this path (docs/README.md, "Conventions")'; continue }
    $text = Read-Text $rel
    $fm = Read-Frontmatter $text
    $isArchive = [bool]$kind.Archive

    # links: everywhere except templates (placeholders); anchors: active docs always, archive only in audit mode
    if (-not $kind.Template) { Test-Links $rel $text ((-not $isArchive) -or $audit) }

    # ids are unique across the whole tree, archive included
    if ($fm -and $fm.ContainsKey('id') -and $fm['id'] -and -not $kind.Template) {
        $id = $fm['id']
        if ($idOwners.ContainsKey($id)) { Add-Err $rel "duplicate id $id (also in $($idOwners[$id]))" } else { $idOwners[$id] = $rel }
    }

    if ($kind.Template) {
        $tk = $TemplateKinds[[System.IO.Path]::GetFileName($rel)]
        if (-not $tk) { Add-Err $rel 'template has no kind mapping in check-docs.ps1 ($TemplateKinds)'; continue }
        if ($null -eq $fm) { Add-Err $rel 'template missing frontmatter'; continue }
        $need = @($Base)
        $kd = $Kinds | Where-Object { $_.Name -eq $tk } | Select-Object -First 1
        if ($kd.Id -and -not $kd.IdOptional) { $need += 'id' }
        if ($kd.Extra) { $need += $kd.Extra }
        if ($KindRequired.ContainsKey($tk)) { $need += $KindRequired[$tk] }
        foreach ($f in $need) { if (-not $fm.ContainsKey($f)) { Add-Err $rel "template lacks required field '$f' of kind $tk" } }
        continue
    }
    if ($isArchive -and -not $audit) { continue }

    # file names: lowercase kebab-case; README.md, PLAN.md and V2-NN-<slug>.md tickets are the exceptions
    if (-not $isArchive) {
        $fname = [System.IO.Path]::GetFileName($rel)
        $nameOk = ($fname -cmatch '^[a-z0-9]+(?:-[a-z0-9]+)*\.md$') -or ($fname -ceq 'README.md') -or
                  ($kind.Name -eq 'plan') -or ($kind.Name -eq 'ticket' -and $fname -cmatch '^V2-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*\.md$')
        if (-not $nameOk) { Add-Err $rel "file name must be lowercase kebab-case (docs/README.md, ""Filenames"")" }
    }
    if (-not $kind.Fm -and -not $isArchive) { continue }
    if ($null -eq $fm) { Add-Err $rel 'missing frontmatter'; continue }

    foreach ($f in $Base) {
        if (-not $fm.ContainsKey($f) -or [string]::IsNullOrWhiteSpace($fm[$f])) { Add-Err $rel "missing field '$f'" }
    }
    foreach ($f in 'created', 'updated') {
        if ($fm.ContainsKey($f) -and $fm[$f] -notmatch '^\d{4}-\d{2}-\d{2}$') { Add-Err $rel "'$f' must be YYYY-MM-DD (got '$($fm[$f])')" }
    }
    if ($fm.ContainsKey('author') -and $fm['author'] -ne 'Owner') { Add-Err $rel "author must be ""Owner"" (got $($fm['author']))" }
    if ($isArchive) { continue }   # audit mode: archive gets the base checks only

    if ($kind.St -and $fm.ContainsKey('status') -and $Status[$kind.St] -notcontains $fm['status']) {
        Add-Err $rel "status '$($fm['status'])' not allowed for $($kind.Name) (allowed: $($Status[$kind.St] -join ', '))"
    }
    if ($kind.Id) {
        if (-not $fm.ContainsKey('id') -or -not $fm['id']) { if (-not $kind.IdOptional) { Add-Err $rel "missing field 'id'" } }
        elseif ($fm['id'] -cnotmatch $kind.Id) { Add-Err $rel "id '$($fm['id'])' does not match $($kind.Name) format $($kind.Id)" }
    }
    if ($kind.Extra) { foreach ($f in $kind.Extra) { if (-not $fm[$f]) { Add-Err $rel "missing field '$f'" } } }
    if ($KindRequired.ContainsKey($kind.Name)) { foreach ($f in $KindRequired[$kind.Name]) { if (-not $fm.ContainsKey($f)) { Add-Err $rel "missing field '$f'" } } }
    if ($kind.PrefixType) {
        $prefix = ([System.IO.Path]::GetFileName($rel) -split '-')[0]
        if ($fm['id'] -and -not $fm['id'].StartsWith($prefix + '-')) { Add-Err $rel "id must start with '$prefix-'" }
        if ($fm['type'] -ne $prefix.ToLower()) { Add-Err $rel "type must be '$($prefix.ToLower())' to match the file name prefix (got '$($fm['type'])')" }
    }
    if ($kind.Name -eq 'ticket' -and $fm['status'] -eq 'blocked' -and -not $fm['blocked_reason']) { Add-Err $rel "status blocked requires 'blocked_reason'" }
    if ($kind.Name -eq 'ticket' -and $fm['id'] -and -not [System.IO.Path]::GetFileName($rel).ToLowerInvariant().StartsWith($fm['id'].ToLowerInvariant() + '-')) {
        Add-Err $rel "file name must start with the ticket id '$($fm['id'])-'"
    }

    # root-relative paths in frontmatter must exist: every `refs` item, plus repo paths with an extension in other fields
    if ($text -match '(?s)\A\uFEFF?---\r?\n(.*?)\r?\n---') {
        $paths = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::Ordinal)
        foreach ($m in [regex]::Matches($Matches[1], '(?<![\w/.])((?:docs|\.claude|services|infrastructure|eval|scripts|tests|frontend)/[\w\-./]+\.[A-Za-z]+)')) {
            [void]$paths.Add($m.Groups[1].Value)
        }
        if ($fm.ContainsKey('refs') -and $fm['refs']) {
            foreach ($r in ($fm['refs'].Trim('[', ']') -split '[\s,]+')) {
                $r = $r.Trim('"', "'").TrimEnd('/')
                if ($r -and $r -notmatch '^[a-zA-Z][a-zA-Z0-9+.-]*:') { [void]$paths.Add($r) }
            }
        }
        foreach ($p in $paths) {
            $res = Test-RepoPath $p
            if ($res -and $res -ne 'untracked-ignored') { Add-Err $rel "frontmatter ref ($res): $p" }
        }
    }

    $initiative = $null
    if ($rel -match '^docs/execution/initiatives/([^/]+)/') { $initiative = $Matches[1] }
    $docs += [pscustomobject]@{ Rel = $rel; Kind = $kind.Name; Fm = $fm; Initiative = $initiative }
}

# ---------------------------------------------------------------- PLAN counters and ticket relations
$tickets = @($docs | Where-Object { $_.Kind -eq 'ticket' })
$plans = @($docs | Where-Object { $_.Kind -eq 'plan' })
$ticketById = @{}
foreach ($t in $tickets) { if ($t.Fm['id']) { $ticketById[$t.Fm['id']] = $t } }

foreach ($plan in $plans) {
    $planId = $plan.Fm['id']
    $mine = @($tickets | Where-Object { $_.Fm['parent_plan'] -eq $planId })
    if (@('superseded', 'archived') -contains $plan.Fm['status']) { continue }
    $done = @($mine | Where-Object { $_.Fm['status'] -eq 'done' }).Count
    $review = @($mine | Where-Object { $_.Fm['status'] -eq 'review' }).Count
    $exp = [ordered]@{ total_tickets = $mine.Count; completed_tickets = $done; review_tickets = $review; implemented_tickets = ($done + $review) }
    foreach ($k in $exp.Keys) {
        if ($plan.Fm.ContainsKey($k) -and [int]$plan.Fm[$k] -ne $exp[$k]) { Add-Err $plan.Rel "$k is $($plan.Fm[$k]) but tickets give $($exp[$k])" }
    }
}
foreach ($t in $tickets) {
    $pid_ = $t.Fm['parent_plan']
    $parent = $plans | Where-Object { $_.Fm['id'] -eq $pid_ } | Select-Object -First 1
    if (-not $parent) { Add-Err $t.Rel "parent_plan $pid_ not found"; continue }
    if ($t.Initiative -and $parent.Initiative -ne $t.Initiative) { Add-Err $t.Rel "parent_plan $pid_ is not the PLAN.md of initiative '$($t.Initiative)'" }
    if (@('superseded', 'archived') -contains $parent.Fm['status'] -and @('done') -notcontains $t.Fm['status']) {
        Add-Err $t.Rel "status '$($t.Fm['status'])' under closed plan $pid_ (must be done, or move it to the archive)"
    }
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

# ---------------------------------------------------------------- agent-facing files: links + legacy references
$agentFiles = @($tracked | Where-Object {
        $_ -eq 'CLAUDE.md' -or $_ -eq 'README.md' -or
        ($_ -match '^\.claude/(rules|agents|skills)/.+\.md$' -and $_ -notmatch '^\.claude/(skills/impeccable|agents/impeccable)') -or
        $_ -match '^(services/(core-api|ai-service)|infrastructure/(db|modal)|eval|eval/review_ui|tests|tests/tenant-isolation|frontend/web)/README\.md$'
    })
foreach ($rel in $agentFiles) { Test-Links $rel (Read-Text $rel) $true }

$legacyRe = '(?<![\w])(\.agent/|docs/0[1-4]-|docs/_archive|AGENTS\.md|GEMINI\.md)'
$activeDocs = @($docFiles | Where-Object { $_ -notmatch '^docs/archive/' })
foreach ($rel in ($activeDocs + $agentFiles)) {
    $hits = [regex]::Matches((Read-Text $rel), $legacyRe)
    if ($hits.Count -gt 0) {
        $what = (($hits | ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique) -join ', ')
        $msg = "legacy path reference x$($hits.Count) ($what)"
        Add-Err $rel $msg
    }
}

# ---------------------------------------------------------------- gitignore probes
$mustIgnore = @('artifacts/testing/probe-run/screenshots/probe.png', 'artifacts/testing/probe-run/logs/probe.log')
$mustTrack = @('docs/quality/test-reports/test-report-001-probe.md', 'docs/quality/test-plans/test-plan-001-probe.md', 'docs/architecture/data/probe.md')
foreach ($p in $mustIgnore) { git check-ignore -q --no-index $p 2>$null; if ($LASTEXITCODE -ne 0) { Add-Err '.gitignore' "generated evidence is not ignored: $p" } }
foreach ($p in $mustTrack) { git check-ignore -q --no-index $p 2>$null; if ($LASTEXITCODE -eq 0) { Add-Err '.gitignore' "documentation path would be ignored: $p" } }

# ---------------------------------------------------------------- audit-only: translation progress
if ($audit) {
    # Vietnamese-only letters: A/a breve, D/d stroke, O/U horn, and the U+1EA0..U+1EF9 block (escaped: PS 5.1 reads BOM-less files as ANSI)
    $vi = '[\u0102\u0103\u0110\u0111\u01A0\u01A1\u01AF\u01B0\u1EA0-\u1EF9]'
    foreach ($rel in $activeDocs) {
        $t = Read-Text $rel
        $words = ([regex]::Matches($t, '\S+')).Count
        if ($words -gt 0 -and ([regex]::Matches($t, $vi, 'IgnoreCase')).Count / $words -gt 0.08) { Add-Warn $rel 'mostly Vietnamese (active docs are English)' }
    }
    $docs | Group-Object Kind | Sort-Object Name | ForEach-Object {
        $byStatus = ($_.Group | Group-Object { $_.Fm['status'] } | ForEach-Object { "$($_.Name)=$($_.Count)" }) -join ' '
        Write-Host ("  {0,-12} {1,3}  {2}" -f $_.Name, $_.Count, $byStatus)
    }
}

# ---------------------------------------------------------------- report
Write-Host "Checked $($docFiles.Count) docs and $($agentFiles.Count) agent/README files (mode: $Mode)."
$warnings | Sort-Object | ForEach-Object { Write-Host "WARN  $_" -ForegroundColor Yellow }
if ($errors.Count -gt 0) {
    $errors | Sort-Object | ForEach-Object { Write-Host "ERROR $_" -ForegroundColor Red }
    Write-Host "docs check FAILED ($($errors.Count) errors, $($warnings.Count) warnings)" -ForegroundColor Red
    exit 1
}
Write-Host "docs check passed ($($warnings.Count) warnings)" -ForegroundColor Green
exit 0
