<#
.SYNOPSIS
    Idempotent setup for Acceptance Demo Group 2 (83 documents from eval/datasets/sop-main-v3/corpus).
.DESCRIPTION
    Calls only real core-api HTTP endpoints (no direct DB writes).
    Requires core-api document quota >= 83 (e.g., SOPILOT_QUOTA_DOCS_PER_WORKSPACE=200 or 0).
    Default quota (50) will fail at document #51 with HTTP 429/409 QUOTA_EXCEEDED.
.PARAMETER CoreApiUrl
    Base URL of core-api. Defaults to http://localhost:8080.
.PARAMETER Limit
    Optional cap on number of documents to upload (for smoke testing). 0 = all 83.
.PARAMETER WaitReadySeconds
    Max seconds to poll until all uploaded documents reach READY. Defaults to 900s.
#>

param(
    [string]$CoreApiUrl = "http://localhost:8080",
    [int]$Limit = 0,
    [int]$WaitReadySeconds = 900
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Net.Http

function Write-Info($msg)    { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Success($msg) { Write-Host "[OK]   $msg" -ForegroundColor Green }
function Write-Warn($msg)    { Write-Host "[WARN] $msg" -ForegroundColor Yellow }

function Invoke-Api {
    param([string]$Uri, [string]$Method = "Get", [hashtable]$Headers = @{}, $Body = $null,
          [string]$ContentType = "application/json", [int]$TimeoutSec = 30)
    $params = @{ Uri = $Uri; Method = $Method; Headers = $Headers; UseBasicParsing = $true; TimeoutSec = $TimeoutSec }
    if ($null -ne $Body) {
        $params.Body = [System.Text.Encoding]::UTF8.GetBytes([string]$Body)
        $params.ContentType = "$ContentType; charset=utf-8"
    }
    $resp = Invoke-WebRequest @params
    $text = [System.Text.Encoding]::UTF8.GetString($resp.RawContentStream.ToArray())
    if ([string]::IsNullOrWhiteSpace($text)) { return $null }
    return $text | ConvertFrom-Json
}

function List-AllDocs($headers) {
    $all = @()
    $cursor = $null
    do {
        $url = "$CoreApiUrl/api/v1/documents?limit=100"
        if ($cursor) { $url += "&cursor=$([System.Uri]::EscapeDataString($cursor))" }
        $page = Invoke-Api -Uri $url -Method Get -Headers $headers
        if ($page.data) { $all += $page.data }
        $cursor = if ($page.page.hasMore) { $page.page.nextCursor } else { $null }
    } while ($cursor)
    return $all
}

$swTotal = [System.Diagnostics.Stopwatch]::StartNew()

Write-Info "Checking core-api health at $CoreApiUrl/actuator/health..."
$health = Invoke-Api -Uri "$CoreApiUrl/actuator/health" -Method Get -TimeoutSec 10
if ($health.status -ne "UP") { throw "core-api is not UP: $($health.status)" }

$loginResp = Invoke-Api -Uri "$CoreApiUrl/api/v1/auth/dev-login" -Method Post `
    -Body (@{ email = "corpus-owner@sopilot.local"; displayName = "Corpus Reviewer" } | ConvertTo-Json -Compress)
$token = $loginResp.data.accessToken
$headers = @{ Authorization = "Bearer $token" }

$wsName = "SOPilot Acceptance Demo — Corpus 83 (sop-main-v3)"
$workspaces = (Invoke-Api -Uri "$CoreApiUrl/api/v1/workspaces" -Method Get -Headers $headers).data
$found = $workspaces | Where-Object { $_.name -eq $wsName } | Select-Object -First 1
if ($found) {
    $sw = Invoke-Api -Uri "$CoreApiUrl/api/v1/auth/switch-workspace" -Method Post -Headers $headers `
        -Body (@{ workspaceId = $found.id } | ConvertTo-Json -Compress)
    $token = $sw.data.accessToken
    $workspaceId = $found.id
    Write-Success "Using existing workspace '$wsName' ($workspaceId)."
} else {
    $created = Invoke-Api -Uri "$CoreApiUrl/api/v1/workspaces" -Method Post -Headers $headers `
        -Body (@{ name = $wsName } | ConvertTo-Json -Compress)
    $token = $created.data.accessToken
    $workspaceId = $created.data.workspace.id
    Write-Success "Created workspace '$wsName' ($workspaceId)."
}
$headers = @{ Authorization = "Bearer $token" }

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$corpusDir = Join-Path $repoRoot "eval\datasets\sop-main-v3\corpus"
if (-not (Test-Path $corpusDir)) { throw "Corpus directory not found: $corpusDir" }

$files = Get-ChildItem $corpusDir -File | Sort-Object Name
if ($Limit -gt 0) { $files = $files | Select-Object -First $Limit }
Write-Info "Target corpus files: $($files.Count) from $corpusDir"

$existingDocs = List-AllDocs $headers
$existingByTitle = @{}
foreach ($d in $existingDocs) { $existingByTitle[$d.title] = $d }

$uploaded = 0; $skipped = 0; $failed = 0
$client = [System.Net.Http.HttpClient]::new()
$client.DefaultRequestHeaders.Authorization = [System.Net.Http.Headers.AuthenticationHeaderValue]::new("Bearer", $token)

try {
    foreach ($f in $files) {
        $title = [System.IO.Path]::GetFileNameWithoutExtension($f.Name)
        if ($existingByTitle.ContainsKey($title)) {
            $skipped++
            continue
        }
        $content = [System.Net.Http.MultipartFormDataContent]::new()
        $bytes = [System.IO.File]::ReadAllBytes($f.FullName)
        $fc = [System.Net.Http.ByteArrayContent]::new($bytes)
        $mime = switch ($f.Extension.ToLowerInvariant()) {
            ".pdf"  { "application/pdf" }
            ".docx" { "application/vnd.openxmlformats-officedocument.wordprocessingml.document" }
            ".txt"  { "text/plain" }
            default { "text/markdown" }
        }
        $fc.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse($mime)
        $content.Add($fc, "file", $f.Name)
        $content.Add([System.Net.Http.StringContent]::new($title), "title")
        $content.Add([System.Net.Http.StringContent]::new("WORKSPACE"), "visibility")

        $resp = $client.PostAsync("$CoreApiUrl/api/v1/documents", $content).Result
        if ($resp.IsSuccessStatusCode) {
            $uploaded++
            if (($uploaded % 10) -eq 0 -or $uploaded -eq 1) {
                Write-Info "  Uploaded $uploaded / $($files.Count - $skipped) new documents..."
            }
        } else {
            $err = $resp.Content.ReadAsStringAsync().Result
            Write-Warn "Failed uploading '$($f.Name)' (HTTP $([int]$resp.StatusCode)): $err"
            $failed++
            if ($err -match "QUOTA") {
                Write-Warn "Quota exceeded! Restart core-api with SOPILOT_QUOTA_DOCS_PER_WORKSPACE=200 (or 0) and re-run."
                break
            }
        }
    }
} finally {
    $client.Dispose()
}

Write-Info "Upload phase complete: $uploaded uploaded, $skipped already existed, $failed failed."
if ($failed -gt 0) { exit 1 }

if ($WaitReadySeconds -gt 0) {
    $deadline = (Get-Date).AddSeconds($WaitReadySeconds)
    $tokenIssuedAt = Get-Date
    Write-Info "Polling until all $($files.Count) documents reach READY (timeout ${WaitReadySeconds}s)..."
    $allDone = $false
    while ((Get-Date) -lt $deadline) {
        # Access tokens expire in <= 15 min (SOPILOT_ACCESS_TTL); re-authenticate every 10 min.
        if (((Get-Date) - $tokenIssuedAt).TotalMinutes -ge 10) {
            $reLogin = Invoke-Api -Uri "$CoreApiUrl/api/v1/auth/dev-login" -Method Post `
                -Body (@{ email = "corpus-owner@sopilot.local"; displayName = "Corpus Reviewer" } | ConvertTo-Json -Compress)
            $reSw = Invoke-Api -Uri "$CoreApiUrl/api/v1/auth/switch-workspace" -Method Post `
                -Headers @{ Authorization = "Bearer $($reLogin.data.accessToken)" } `
                -Body (@{ workspaceId = $workspaceId } | ConvertTo-Json -Compress)
            $headers = @{ Authorization = "Bearer $($reSw.data.accessToken)" }
            $tokenIssuedAt = Get-Date
        }
        $docs = List-AllDocs $headers
        $ready  = @($docs | Where-Object { $_.status -eq "READY" }).Count
        $fail   = @($docs | Where-Object { $_.status -eq "FAILED" }).Count
        $total  = @($docs).Count
        Write-Info "  Status: $ready READY, $fail FAILED, $($total - $ready - $fail) processing (total $total)..."
        if ($ready + $fail -ge $files.Count) {
            if ($fail -gt 0) {
                $bad = ($docs | Where-Object { $_.status -eq "FAILED" } | ForEach-Object { $_.title }) -join ", "
                Write-Warn "FAILED documents ($fail): $bad"
                exit 1
            }
            Write-Success "All $ready/$total documents are READY!"
            $allDone = $true
            break
        }
        Start-Sleep -Seconds 5
    }
    if (-not $allDone) {
        Write-Warn "Timed out after ${WaitReadySeconds}s; ai-worker continues processing remaining documents in the background."
        exit 2
    }
}

$swTotal.Stop()
Write-Host ""
Write-Info "Ensuring categories and assigning them to all Group 2 documents..."

function Ensure-Category($headers, $name) {
    $existing = (Invoke-Api -Uri "$CoreApiUrl/api/v1/categories" -Method Get -Headers $headers).data
    $found = $existing | Where-Object { $_.name -eq $name } | Select-Object -First 1
    if ($found) { return $found.id }
    $resp = Invoke-Api -Uri "$CoreApiUrl/api/v1/categories" -Method Post -Headers $headers `
        -Body (@{ name = $name } | ConvertTo-Json -Compress)
    Write-Success "Created category '$name'."
    return $resp.data.id
}

$cats = @{
    "People & Culture"             = Ensure-Category $headers "People & Culture"
    "Engineering & Product"        = Ensure-Category $headers "Engineering & Product"
    "Finance, Legal & GTM"         = Ensure-Category $headers "Finance, Legal & GTM"
    "Regulatory & Compliance (EN)" = Ensure-Category $headers "Regulatory & Compliance (EN)"
    "Quy trình ISO & Hành chính"   = Ensure-Category $headers "Quy trình ISO & Hành chính"
    "General Handbook"             = Ensure-Category $headers "General Handbook"
}

$allDocs = List-AllDocs $headers
$assigned = 0
foreach ($d in $allDocs) {
    $t = $d.title.ToLowerInvariant()
    $catName = if ($t -match "^gl-(people|total-rewards|hiring|benefits|diversity|values|communication|leadership|company|paid-time|time-off|working-group|inclusion)") {
        "People & Culture"
    } elseif ($t -match "^gl-(engineering|security|support|product|customer-success|it|infrastructure|quality|development)") {
        "Engineering & Product"
    } elseif ($t -match "^gl-(finance|legal|sales|marketing|procurement|tax|payroll|accounting|business-technology|alliances)") {
        "Finance, Legal & GTM"
    } elseif ($t -match "^(fda|epa|osha|nist|cdc|us-)") {
        "Regulatory & Compliance (EN)"
    } elseif ($t -match "(tb-|nb-|qt|cv|vbhn|qd|nd|cang-vu|so-xay-dung|nghi-dinh|thong-tu|quyet-dinh|cong-van)") {
        "Quy trình ISO & Hành chính"
    } elseif ($t -match "^gl-") {
        "General Handbook"
    } else {
        "Quy trình ISO & Hành chính"
    }
    $targetCatId = $cats[$catName]
    if ($d.categoryId -ne $targetCatId) {
        $patch = @{ categoryId = $targetCatId } | ConvertTo-Json -Compress
        Invoke-Api -Uri "$CoreApiUrl/api/v1/documents/$($d.id)" -Method Patch -Headers $headers -Body $patch | Out-Null
        $assigned++
    }
}
Write-Success "Categorized $assigned documents across $($cats.Count) categories."

Write-Success "=== GROUP 2 CORPUS SEED COMPLETE in $([math]::Round($swTotal.Elapsed.TotalSeconds, 1))s ==="
Write-Host "Workspace: $wsName ($workspaceId)"
