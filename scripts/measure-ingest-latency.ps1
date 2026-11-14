<#
.SYNOPSIS
    Measures upload ack, time to READY and suggestion latency per document (V2-25).
.DESCRIPTION
    Logs in as a fresh dev user (new personal workspace, so nothing is deduplicated), uploads the tracked
    corpus files one at a time and waits for each version to become READY and for its suggestion job to
    finish. Documents are uploaded sequentially so t_ready is not inflated by queueing behind other uploads.

    t_upload_ack_ms : client-side time of POST /api/v1/documents until the response.
    t_ready_ms      : core.document_versions.processed_at - created_at.
    t_suggest_ms    : rag.suggestion_jobs.timings (suggest job run time), plus llm_ms, method.
    t_suggest_wait_ms: suggestion_jobs.updated_at - core processed_at (queue wait + run time after READY).

    Needs the V2 stack running (docker-compose.v2.yml) and a core-api with the dev-login profile.
    Reads only the local database through `docker exec sopilot-v2-postgres psql`.
    Files named nb-*.md are gitignored and never used. The result is a small sample: report n with it.
.PARAMETER CoreApiUrl
    Base URL of core-api. Defaults to http://localhost:8080.
.PARAMETER TimeoutSeconds
    Per-document wait for READY and for the suggestion job. Defaults to 300.
#>
param(
    [string]$CoreApiUrl = "http://localhost:8080",
    [int]$TimeoutSeconds = 300
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$files = @("eval/datasets/sop-pilot/corpus", "eval/datasets/smoke/corpus") |
    ForEach-Object { Get-ChildItem -Path (Join-Path $root $_) -Filter *.md -File } |
    Where-Object { $_.Name -notlike "nb-*" }
if (-not $files) { Write-Error "No corpus files found."; exit 1 }

function Invoke-Psql([string]$sql) {
    $out = docker exec sopilot-v2-postgres psql -U postgres -d sopilot -At -F "|" -c $sql
    if ($LASTEXITCODE -ne 0) { throw "psql failed" }
    return $out
}

$stamp = Get-Date -Format "yyyyMMddHHmmss"
$email = "latency-$stamp@sopilot.local"
$login = Invoke-RestMethod -Uri "$CoreApiUrl/api/v1/auth/dev-login" -Method Post -ContentType "application/json" `
    -Body (@{ email = $email; displayName = "Latency Test $stamp" } | ConvertTo-Json)
$token = $login.data.accessToken
$userId = $login.data.user.id
Add-Type -AssemblyName System.Net.Http
$client = [System.Net.Http.HttpClient]::new()
$client.Timeout = [TimeSpan]::FromSeconds(60)
$client.DefaultRequestHeaders.Authorization = [System.Net.Http.Headers.AuthenticationHeaderValue]::new("Bearer", $token)

$ack = @()
foreach ($f in $files) {
    $content = [System.Net.Http.MultipartFormDataContent]::new()
    $bytes = [System.IO.File]::ReadAllBytes($f.FullName)
    $part = [System.Net.Http.ByteArrayContent]::new($bytes)
    $part.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse("text/markdown")
    $content.Add($part, "file", $f.Name)
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $resp = $client.PostAsync("$CoreApiUrl/api/v1/documents", $content).Result
    $sw.Stop()
    if (-not $resp.IsSuccessStatusCode) { Write-Warning "$($f.Name): upload failed $($resp.StatusCode)"; continue }
    $versionId = ($resp.Content.ReadAsStringAsync().Result | ConvertFrom-Json).data.latestVersion.id
    $ack += [int]$sw.ElapsedMilliseconds
    Write-Host ("[UP]   {0,-28} ack={1} ms" -f $f.Name, $sw.ElapsedMilliseconds)

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $status = ""
    $job = ""
    while ((Get-Date) -lt $deadline) {
        $status = Invoke-Psql "SELECT status FROM core.document_versions WHERE id = '$versionId'"
        $job = Invoke-Psql "SELECT status FROM rag.suggestion_jobs WHERE version_id = '$versionId'"
        if ($status -eq "FAILED") { break }
        if ($status -eq "READY" -and $job -in @("DONE", "FAILED")) { break }
        Start-Sleep -Seconds 2
    }
    Write-Host ("[DONE] {0,-28} version={1} suggestion={2}" -f $f.Name, $status, $job)
}

function Get-Stats($values) {
    $s = @($values | Sort-Object)
    if ($s.Count -eq 0) { return "n=0" }
    $p = { param($q) $i = [math]::Min($s.Count - 1, [math]::Ceiling($q * $s.Count) - 1); $s[[math]::Max(0, $i)] }
    return ("n={0} p50={1} p95={2} max={3}" -f $s.Count, (& $p 0.5), (& $p 0.95), $s[-1])
}

Write-Host ""
$rows = Invoke-Psql @"
SELECT v.original_name,
       round(extract(epoch FROM (v.processed_at - v.created_at)) * 1000)::int,
       coalesce((j.timings->>'t_suggest_ms')::int, -1),
       coalesce((j.timings->>'llm_ms')::int, -1),
       coalesce(j.method, ''),
       round(extract(epoch FROM (j.updated_at - v.processed_at)) * 1000)::int
  FROM core.document_versions v
  LEFT JOIN rag.suggestion_jobs j ON j.version_id = v.id
 WHERE v.uploaded_by = '$userId' AND v.status = 'READY'
 ORDER BY v.created_at
"@
$ready = @(); $suggest = @(); $llm = @(); $wait = @()
"{0,-28} {1,10} {2,10} {3,8} {4,-15} {5,12}" -f "document", "t_ready_ms", "t_suggest", "llm_ms", "method", "suggest_wait"
foreach ($line in $rows) {
    $c = $line -split "\|"
    "{0,-28} {1,10} {2,10} {3,8} {4,-15} {5,12}" -f $c[0], $c[1], $c[2], $c[3], $c[4], $c[5]
    $ready += [int]$c[1]; $wait += [int]$c[5]
    if ([int]$c[2] -ge 0) { $suggest += [int]$c[2] }
    if ([int]$c[3] -ge 0) { $llm += [int]$c[3] }
}
Write-Host ""
Write-Host "t_upload_ack_ms   $(Get-Stats $ack)"
Write-Host "t_ready_ms        $(Get-Stats $ready)"
Write-Host "t_suggest_ms      $(Get-Stats $suggest)"
Write-Host "llm_ms            $(Get-Stats $llm)"
Write-Host "suggest_wait_ms   $(Get-Stats $wait)"
$fallbacks = @($rows | Where-Object { $_ -match "RULES_FALLBACK" }).Count
Write-Host "fallback          $fallbacks of $($rows.Count)"
Write-Host "Sample is small: report n with any percentile. User: $email"
Write-Host "t_ready includes embedding cache hits (the cache is keyed by chunk text, not by workspace). Check"
Write-Host "'docker logs sopilot-v2-ai-worker | grep ingest_done' for embed_cached/embed_ms before quoting t_ready."
