<#
.SYNOPSIS
  Validates the three local .env files (root, core-api, ai-service) without printing any value.

.DESCRIPTION
  Checks, per file: required keys present, no <placeholder> left, format of each value.
  Then checks that the values shared between files are identical.
  Output names keys and verdicts only, never values (secrets stay out of the terminal and logs).
  Exit code 1 when any check fails; warnings do not fail.

.PARAMETER Root
  Repository root. Defaults to the parent of this script's directory.

.EXAMPLE
  ./scripts/check-env.ps1
#>
param([string]$Root = (Split-Path -Parent $PSScriptRoot))

$ErrorActionPreference = 'Stop'
$script:fail = 0
$script:warn = 0

function Read-EnvFile([string]$path) {
    $map = @{}
    foreach ($line in Get-Content -LiteralPath $path) {
        if ($line -match '^\s*#' -or $line -notmatch '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$') { continue }
        $v = $Matches[2].Trim()
        if ($v.Length -ge 2 -and (($v[0] -eq '"' -and $v[-1] -eq '"') -or ($v[0] -eq "'" -and $v[-1] -eq "'"))) {
            $v = $v.Substring(1, $v.Length - 2)
        }
        $map[$Matches[1]] = $v
    }
    return $map
}

function Fail([string]$scope, [string]$key, [string]$msg) { $script:fail++; Write-Host "  FAIL  [$scope] $key - $msg" -ForegroundColor Red }
function Warn([string]$scope, [string]$key, [string]$msg) { $script:warn++; Write-Host "  WARN  [$scope] $key - $msg" -ForegroundColor Yellow }

# Rule: Kind = secret (>=32 chars), url, hostport, port, text, any
function Test-Key($scope, $env, [string]$key, [string]$kind, [bool]$required = $true) {
    if (-not $env.ContainsKey($key)) {
        if ($required) { Fail $scope $key 'missing' }
        return
    }
    $v = $env[$key]
    if ($v -eq '') {
        if ($required) { Fail $scope $key 'empty' }
        return
    }
    if ($v -match '<[^>]*>') { Fail $scope $key 'still contains a <placeholder>'; return }
    switch ($kind) {
        'secret'   { if ($v.Length -lt 32) { Fail $scope $key 'shorter than 32 characters' } }
        'url'      { if ($v -notmatch '^https?://[^\s/]+') { Fail $scope $key 'must be http(s)://host[:port]' } }
        'hostport' { if ($v -notmatch '^[^\s/:]+:\d{2,5}$') { Fail $scope $key 'must be host:port without a scheme' } }
        'port'     { if ($v -notmatch '^\d{2,5}$' -or [int]$v -gt 65535) { Fail $scope $key 'must be a port number' } }
        'int'      { if ($v -notmatch '^\d+$') { Fail $scope $key 'must be a non-negative integer' } }
    }
}

function Test-Same($a, $ka, $b, $kb, [string]$label) {
    if (-not $a.ContainsKey($ka) -or -not $b.ContainsKey($kb) -or $a[$ka] -eq '' -or $b[$kb] -eq '') { return }
    if ($a[$ka] -ceq $b[$kb]) { Write-Host "  ok    $label" -ForegroundColor DarkGreen }
    else { Fail 'shared' $label 'values differ' }
}

# --- load ---
$paths = [ordered]@{
    root = Join-Path $Root '.env'
    core = Join-Path $Root 'services/core-api/.env'
    ai   = Join-Path $Root 'services/ai-service/.env'
}
$envs = @{}
foreach ($name in $paths.Keys) {
    if (Test-Path -LiteralPath $paths[$name]) { $envs[$name] = Read-EnvFile $paths[$name] }
    else { Fail $name '.env' "file not found ($($paths[$name].Replace($Root, '.')))"; $envs[$name] = @{} }
}
$r = $envs['root']; $c = $envs['core']; $a = $envs['ai']

# --- root ---
Write-Host "`n[root] .env" -ForegroundColor Cyan
foreach ($k in 'V2_POSTGRES_SUPERUSER_PASSWORD', 'V2_DB_MIGRATOR_PASSWORD', 'V2_DB_CORE_APP_PASSWORD', 'V2_DB_AI_APP_PASSWORD',
               'V2_MINIO_ROOT_PASSWORD', 'SOPILOT_S3_SECRET_KEY', 'SOPILOT_S3_AI_SECRET_KEY') { Test-Key 'root' $r $k 'secret' }
foreach ($k in 'V2_POSTGRES_PORT', 'V2_MINIO_API_PORT', 'V2_MINIO_CONSOLE_PORT') { Test-Key 'root' $r $k 'port' }
foreach ($k in 'V2_MINIO_ROOT_USER', 'SOPILOT_S3_BUCKET', 'SOPILOT_S3_ACCESS_KEY', 'SOPILOT_S3_AI_ACCESS_KEY') { Test-Key 'root' $r $k 'text' }
# Answer-LLM block (V2-10): only needed once the pipeline runs, so warn instead of fail.
foreach ($k in 'SOPILOT_LLM_BASE_URL', 'SOPILOT_LLM_MODEL', 'SOPILOT_LLM_API_KEY') {
    if (-not $r.ContainsKey($k) -or $r[$k] -eq '') { Warn 'root' $k 'empty (needed for the V2-10 answer pipeline)' }
    elseif ($r[$k] -match '<[^>]*>') { Warn 'root' $k 'still a <placeholder> (needed for the V2-10 answer pipeline)' }
}
if ($r.ContainsKey('SOPILOT_LLM_BASE_URL') -and $r['SOPILOT_LLM_BASE_URL'] -notmatch '<' -and $r['SOPILOT_LLM_BASE_URL'] -ne '' -and
    $r['SOPILOT_LLM_BASE_URL'] -notmatch '^https?://') { Fail 'root' 'SOPILOT_LLM_BASE_URL' 'must be http(s)://...' }
foreach ($k in 'SOPILOT_LLM_RPM', 'SOPILOT_LLM_TPM') { if ($r.ContainsKey($k) -and $r[$k] -ne '') { Test-Key 'root' $r $k 'int' } }
# Distinct secrets: a reused password defeats role isolation.
$pw = 'V2_POSTGRES_SUPERUSER_PASSWORD', 'V2_DB_MIGRATOR_PASSWORD', 'V2_DB_CORE_APP_PASSWORD', 'V2_DB_AI_APP_PASSWORD', 'V2_MINIO_ROOT_PASSWORD'
$seen = @{}
foreach ($k in $pw) {
    if ($r.ContainsKey($k) -and $r[$k] -ne '') {
        if ($seen.ContainsKey($r[$k])) { Warn 'root' $k "same value as $($seen[$r[$k]]) (use distinct passwords)" } else { $seen[$r[$k]] = $k }
    }
}

# --- core-api ---
Write-Host "`n[core-api] services/core-api/.env" -ForegroundColor Cyan
Test-Key 'core' $c 'GOOGLE_CLIENT_ID' 'text'
if ($c.ContainsKey('GOOGLE_CLIENT_ID') -and $c['GOOGLE_CLIENT_ID'] -ne '' -and $c['GOOGLE_CLIENT_ID'] -notmatch '<' -and
    $c['GOOGLE_CLIENT_ID'] -notmatch '\.apps\.googleusercontent\.com$') { Fail 'core' 'GOOGLE_CLIENT_ID' 'must end with .apps.googleusercontent.com' }
Test-Key 'core' $c 'SOPILOT_DB_URL' 'text'
if ($c.ContainsKey('SOPILOT_DB_URL') -and $c['SOPILOT_DB_URL'] -notmatch '<' -and $c['SOPILOT_DB_URL'] -ne '' -and
    $c['SOPILOT_DB_URL'] -notmatch '^jdbc:postgresql://[^/\s:]+:\d+/\w+') { Fail 'core' 'SOPILOT_DB_URL' 'must look like jdbc:postgresql://host:port/db' }
Test-Key 'core' $c 'SOPILOT_DB_USER' 'text'
if ($c.ContainsKey('SOPILOT_DB_USER') -and $c['SOPILOT_DB_USER'] -ne '' -and $c['SOPILOT_DB_USER'] -ne 'sopilot_core_app') { Fail 'core' 'SOPILOT_DB_USER' 'must be sopilot_core_app' }
Test-Key 'core' $c 'SOPILOT_DB_PASSWORD' 'secret'
Test-Key 'core' $c 'SOPILOT_S3_ENDPOINT' 'url'
Test-Key 'core' $c 'SOPILOT_S3_BUCKET' 'text'
Test-Key 'core' $c 'SOPILOT_S3_ACCESS_KEY' 'text'
Test-Key 'core' $c 'SOPILOT_S3_SECRET_KEY' 'secret'
Test-Key 'core' $c 'SOPILOT_AI_BASE_URL' 'url'
Test-Key 'core' $c 'SOPILOT_INTERNAL_TOKEN' 'secret'

# --- ai-service ---
Write-Host "`n[ai-service] services/ai-service/.env" -ForegroundColor Cyan
Test-Key 'ai' $a 'SOPILOT_DB_URL' 'text'
$aiDb = $null
if ($a.ContainsKey('SOPILOT_DB_URL') -and $a['SOPILOT_DB_URL'] -ne '' -and $a['SOPILOT_DB_URL'] -notmatch '<') {
    if ($a['SOPILOT_DB_URL'] -match '^postgres(?:ql)?(?:\+\w+)?://([^:/@\s]+):([^@\s]+)@([^/:\s]+):(\d+)/(\w+)') {
        $aiDb = @{ user = $Matches[1]; pass = $Matches[2]; port = $Matches[4] }
        if ($aiDb.user -ne 'sopilot_ai_app') { Fail 'ai' 'SOPILOT_DB_URL' 'user must be sopilot_ai_app' }
    } else { Fail 'ai' 'SOPILOT_DB_URL' 'must look like postgresql://user:password@host:port/db (not the JDBC form)' }
}
Test-Key 'ai' $a 'SOPILOT_INTERNAL_TOKEN' 'secret'
Test-Key 'ai' $a 'SOPILOT_CORE_BASE_URL' 'url'
Test-Key 'ai' $a 'SOPILOT_CORE_JWKS_URL' 'url'
if ($a.ContainsKey('SOPILOT_CORE_JWKS_URL') -and $a['SOPILOT_CORE_JWKS_URL'] -match '^https?://' -and
    $a['SOPILOT_CORE_JWKS_URL'] -notmatch '/\.well-known/jwks\.json$') { Fail 'ai' 'SOPILOT_CORE_JWKS_URL' 'must end with /.well-known/jwks.json' }
Test-Key 'ai' $a 'SOPILOT_S3_ENDPOINT' 'hostport'
Test-Key 'ai' $a 'SOPILOT_S3_BUCKET' 'text'
Test-Key 'ai' $a 'SOPILOT_S3_AI_ACCESS_KEY' 'text'
Test-Key 'ai' $a 'SOPILOT_S3_AI_SECRET_KEY' 'secret'
# EMBEDDING_REVISION: 40 hex chars. Empty is allowed in profile local, an error in profile eval.
$profile = if ($a.ContainsKey('SOPILOT_PROFILE') -and $a['SOPILOT_PROFILE'] -ne '') { $a['SOPILOT_PROFILE'] } else { 'local' }
if (-not $a.ContainsKey('EMBEDDING_REVISION') -or $a['EMBEDDING_REVISION'] -eq '') {
    if ($profile -eq 'eval') { Fail 'ai' 'EMBEDDING_REVISION' 'empty, but profile eval requires a pinned revision' }
    else { Warn 'ai' 'EMBEDDING_REVISION' 'empty (unpinned; startup fails in profile eval)' }
} elseif ($a['EMBEDDING_REVISION'] -notmatch '^[0-9a-f]{40}$') { Fail 'ai' 'EMBEDDING_REVISION' 'must be a 40-character lowercase hex commit hash' }
if ($a.ContainsKey('SOPILOT_PROFILE') -and $a['SOPILOT_PROFILE'] -notin @('', 'local', 'eval')) { Fail 'ai' 'SOPILOT_PROFILE' 'must be local or eval' }

# --- shared values ---
Write-Host "`n[shared] values that must match" -ForegroundColor Cyan
Test-Same $r 'V2_DB_CORE_APP_PASSWORD' $c 'SOPILOT_DB_PASSWORD' 'root V2_DB_CORE_APP_PASSWORD = core SOPILOT_DB_PASSWORD'
if ($aiDb) {
    if ($r.ContainsKey('V2_DB_AI_APP_PASSWORD') -and $r['V2_DB_AI_APP_PASSWORD'] -ne '') {
        # The password sits in a URL: accept it raw or percent-encoded.
        if ($aiDb.pass -ceq $r['V2_DB_AI_APP_PASSWORD'] -or [uri]::UnescapeDataString($aiDb.pass) -ceq $r['V2_DB_AI_APP_PASSWORD']) {
            Write-Host '  ok    root V2_DB_AI_APP_PASSWORD = password inside ai SOPILOT_DB_URL' -ForegroundColor DarkGreen
        } else { Fail 'shared' 'root V2_DB_AI_APP_PASSWORD = password inside ai SOPILOT_DB_URL' 'values differ' }
    }
}
Test-Same $r 'SOPILOT_S3_BUCKET' $c 'SOPILOT_S3_BUCKET' 'root = core SOPILOT_S3_BUCKET'
Test-Same $r 'SOPILOT_S3_BUCKET' $a 'SOPILOT_S3_BUCKET' 'root = ai SOPILOT_S3_BUCKET'
Test-Same $r 'SOPILOT_S3_ACCESS_KEY' $c 'SOPILOT_S3_ACCESS_KEY' 'root = core SOPILOT_S3_ACCESS_KEY'
Test-Same $r 'SOPILOT_S3_SECRET_KEY' $c 'SOPILOT_S3_SECRET_KEY' 'root = core SOPILOT_S3_SECRET_KEY'
Test-Same $r 'SOPILOT_S3_AI_ACCESS_KEY' $a 'SOPILOT_S3_AI_ACCESS_KEY' 'root = ai SOPILOT_S3_AI_ACCESS_KEY'
Test-Same $r 'SOPILOT_S3_AI_SECRET_KEY' $a 'SOPILOT_S3_AI_SECRET_KEY' 'root = ai SOPILOT_S3_AI_SECRET_KEY'
Test-Same $c 'SOPILOT_INTERNAL_TOKEN' $a 'SOPILOT_INTERNAL_TOKEN' 'core = ai SOPILOT_INTERNAL_TOKEN'

# --- ports must agree with the root file ---
Write-Host "`n[ports] URLs point at the ports in the root file" -ForegroundColor Cyan
function Test-Port([string]$label, $actual, $expected) {
    if ($null -eq $actual -or $null -eq $expected -or $expected -eq '') { return }
    if ("$actual" -eq "$expected") { Write-Host "  ok    $label" -ForegroundColor DarkGreen }
    else { Fail 'ports' $label "port differs from the root file ($expected)" }
}
if ($c.ContainsKey('SOPILOT_DB_URL') -and $c['SOPILOT_DB_URL'] -match '^jdbc:postgresql://[^/\s:]+:(\d+)/') {
    Test-Port 'core SOPILOT_DB_URL port = root V2_POSTGRES_PORT' $Matches[1] $r['V2_POSTGRES_PORT'] }
if ($aiDb) { Test-Port 'ai SOPILOT_DB_URL port = root V2_POSTGRES_PORT' $aiDb.port $r['V2_POSTGRES_PORT'] }
if ($c.ContainsKey('SOPILOT_S3_ENDPOINT') -and $c['SOPILOT_S3_ENDPOINT'] -match ':(\d+)/?$') {
    Test-Port 'core SOPILOT_S3_ENDPOINT port = root V2_MINIO_API_PORT' $Matches[1] $r['V2_MINIO_API_PORT'] }
if ($a.ContainsKey('SOPILOT_S3_ENDPOINT') -and $a['SOPILOT_S3_ENDPOINT'] -match ':(\d+)$') {
    Test-Port 'ai SOPILOT_S3_ENDPOINT port = root V2_MINIO_API_PORT' $Matches[1] $r['V2_MINIO_API_PORT'] }
if ($c.ContainsKey('SOPILOT_AI_BASE_URL') -and $c['SOPILOT_AI_BASE_URL'] -match ':(\d+)/?$' -and
    $a.ContainsKey('SOPILOT_CORE_BASE_URL') -and $a['SOPILOT_CORE_BASE_URL'] -match ':(\d+)/?$') {
    Write-Host '  info  core SOPILOT_AI_BASE_URL and ai SOPILOT_CORE_BASE_URL set (expected :8000 and :8080 when run from source)'
}

# --- summary ---
Write-Host ''
if ($script:fail -gt 0) { Write-Host "env check FAILED: $($script:fail) problem(s), $($script:warn) warning(s). No values were printed." -ForegroundColor Red; exit 1 }
Write-Host "env check passed ($($script:warn) warning(s)). No values were printed." -ForegroundColor Green
exit 0
