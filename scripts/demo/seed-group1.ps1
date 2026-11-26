<#
.SYNOPSIS
    Idempotent setup for Acceptance Demo Group 1 (multi-role workspace + external isolation workspace).
.DESCRIPTION
    Calls only real core-api HTTP endpoints (no direct DB writes, respects RLS and tenancy):
    - Workspace 1: "SOPilot Acceptance Demo — Multi-Role"
      * owner@sopilot.local      (OWNER, Workspace Publisher)
      * admin@sopilot.local      (ADMIN)
      * eng-lead@sopilot.local   (MEMBER, Kỹ thuật, Department Publisher)
      * eng-member@sopilot.local (MEMBER, Kỹ thuật)
      * hr-lead@sopilot.local    (MEMBER, Nhân sự, Department Publisher)
      * hr-member@sopilot.local  (MEMBER, Nhân sự)
      * fin-lead@sopilot.local   (MEMBER, Tài chính, Department Publisher)
      * new-hire@sopilot.local   (MEMBER, no department)
      * 6 curated documents (2 WORKSPACE, 2 Kỹ thuật, 1 Nhân sự, 1 Tài chính injection test)
    - Workspace 2: "SOPilot External Tenant (Isolation)"
      * external-owner@sopilot.local (OWNER, Workspace Publisher)
      * 1 confidential document (EXT-NDA-99) for cross-workspace isolation proof
.PARAMETER CoreApiUrl
    Base URL of core-api. Defaults to http://localhost:8080.
.PARAMETER WaitReadySeconds
    Max seconds to poll until all uploaded documents reach READY. Set 0 to skip polling.
#>

param(
    [string]$CoreApiUrl = "http://localhost:8080",
    [int]$WaitReadySeconds = 300
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

function Dev-Login($email, $displayName) {
    $body = @{ email = $email; displayName = $displayName } | ConvertTo-Json -Compress
    $resp = Invoke-Api -Uri "$CoreApiUrl/api/v1/auth/dev-login" -Method Post -Body $body
    return [pscustomobject]@{
        Token  = $resp.data.accessToken
        UserId = $resp.data.user.id
    }
}

function Ensure-Workspace($ownerToken, $wsName) {
    $headers = @{ Authorization = "Bearer $ownerToken" }
    $workspaces = (Invoke-Api -Uri "$CoreApiUrl/api/v1/workspaces" -Method Get -Headers $headers).data
    $found = $workspaces | Where-Object { $_.name -eq $wsName } | Select-Object -First 1
    if ($found) {
        $sw = Invoke-Api -Uri "$CoreApiUrl/api/v1/auth/switch-workspace" -Method Post -Headers $headers `
            -Body (@{ workspaceId = $found.id } | ConvertTo-Json -Compress)
        Write-Success "Using existing workspace '$wsName' ($($found.id))."
        return [pscustomobject]@{ Id = $found.id; Token = $sw.data.accessToken }
    }
    $created = Invoke-Api -Uri "$CoreApiUrl/api/v1/workspaces" -Method Post -Headers $headers `
        -Body (@{ name = $wsName } | ConvertTo-Json -Compress)
    Write-Success "Created workspace '$wsName' ($($created.data.workspace.id))."
    return [pscustomobject]@{ Id = $created.data.workspace.id; Token = $created.data.accessToken }
}

function Ensure-Department($headers, $name) {
    $existing = (Invoke-Api -Uri "$CoreApiUrl/api/v1/departments" -Method Get -Headers $headers).data
    $found = $existing | Where-Object { $_.name -eq $name } | Select-Object -First 1
    if ($found) {
        Write-Success "Department '$name' exists ($($found.id))."
        return $found.id
    }
    $resp = Invoke-Api -Uri "$CoreApiUrl/api/v1/departments" -Method Post -Headers $headers `
        -Body (@{ name = $name } | ConvertTo-Json -Compress)
    Write-Success "Created department '$name' ($($resp.data.id))."
    return $resp.data.id
}

function Ensure-Category($headers, $name) {
    $existing = (Invoke-Api -Uri "$CoreApiUrl/api/v1/categories" -Method Get -Headers $headers).data
    $found = $existing | Where-Object { $_.name -eq $name } | Select-Object -First 1
    if ($found) {
        Write-Success "Category '$name' exists ($($found.id))."
        return $found.id
    }
    $resp = Invoke-Api -Uri "$CoreApiUrl/api/v1/categories" -Method Post -Headers $headers `
        -Body (@{ name = $name } | ConvertTo-Json -Compress)
    Write-Success "Created category '$name' ($($resp.data.id))."
    return $resp.data.id
}

function Set-DocMetadata($docId, $categoryId, $tags, $publisherToken) {
    $patch = @{ categoryId = $categoryId; tags = @($tags) } | ConvertTo-Json -Compress
    Invoke-Api -Uri "$CoreApiUrl/api/v1/documents/$docId" -Method Patch `
        -Headers @{ Authorization = "Bearer $publisherToken" } -Body $patch | Out-Null
}

function Ensure-Member($ownerHeaders, $workspaceId, $email, $displayName, $role, $deptId, $jobTitle, $empCode) {
    $members = (Invoke-Api -Uri "$CoreApiUrl/api/v1/members" -Method Get -Headers $ownerHeaders).data
    $existing = $members | Where-Object { $_.email -eq $email } | Select-Object -First 1
    if ($existing) {
        $login = Dev-Login $email $displayName
        $sw = Invoke-Api -Uri "$CoreApiUrl/api/v1/auth/switch-workspace" -Method Post `
            -Headers @{ Authorization = "Bearer $($login.Token)" } `
            -Body (@{ workspaceId = $workspaceId } | ConvertTo-Json -Compress)
        Write-Success "$email already a member ($($existing.role))."
        return [pscustomobject]@{ UserId = $login.UserId; Token = $sw.data.accessToken }
    }

    $pending = (Invoke-Api -Uri "$CoreApiUrl/api/v1/invitations" -Method Get -Headers $ownerHeaders).data
    $inv = $pending | Where-Object { $_.email -eq $email } | Select-Object -First 1
    $inviteId = if ($inv) { $inv.id } else {
        $payload = @{
            email        = $email
            role         = $role
            displayName  = $displayName
            jobTitle     = $jobTitle
            employeeCode = $empCode
        }
        if ($deptId) { $payload.departmentId = $deptId }
        $created = Invoke-Api -Uri "$CoreApiUrl/api/v1/invitations" -Method Post -Headers $ownerHeaders `
            -Body ($payload | ConvertTo-Json -Compress)
        Write-Success "Invited $email as $role."
        $created.data.id
    }

    $login = Dev-Login $email $displayName
    $accepted = Invoke-Api -Uri "$CoreApiUrl/api/v1/invitations/accept" -Method Post `
        -Headers @{ Authorization = "Bearer $($login.Token)" } `
        -Body (@{ invitationId = $inviteId } | ConvertTo-Json -Compress)
    Write-Success "$email accepted invitation."
    return [pscustomobject]@{ UserId = $login.UserId; Token = $accepted.data.accessToken }
}

function Ensure-Document($existingDocs, $filePath, $title, $visibility, $ownerDeptId, $deptIds, $authToken) {
    $found = $existingDocs | Where-Object { $_.title -eq $title } | Select-Object -First 1
    if ($found) {
        Write-Success "Document '$title' already exists ($($found.id), status=$($found.status))."
        return $found.id
    }
    if (-not (Test-Path $filePath)) {
        throw "Missing demo document file: $filePath"
    }

    $client = [System.Net.Http.HttpClient]::new()
    try {
        $client.DefaultRequestHeaders.Authorization = [System.Net.Http.Headers.AuthenticationHeaderValue]::new("Bearer", $authToken)
        $content = [System.Net.Http.MultipartFormDataContent]::new()
        $fileBytes = [System.IO.File]::ReadAllBytes($filePath)
        $fileContent = [System.Net.Http.ByteArrayContent]::new($fileBytes)
        $fileContent.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse("text/markdown")
        $content.Add($fileContent, "file", [System.IO.Path]::GetFileName($filePath))
        $content.Add([System.Net.Http.StringContent]::new($title), "title")
        $content.Add([System.Net.Http.StringContent]::new($visibility), "visibility")
        if ($ownerDeptId) {
            $content.Add([System.Net.Http.StringContent]::new($ownerDeptId.ToString()), "ownerDepartmentId")
        }
        if ($deptIds) {
            foreach ($dId in $deptIds) {
                $content.Add([System.Net.Http.StringContent]::new($dId.ToString()), "departmentIds")
            }
        }
        $resp = $client.PostAsync("$CoreApiUrl/api/v1/documents", $content).Result
        $respBody = $resp.Content.ReadAsStringAsync().Result
        if (-not $resp.IsSuccessStatusCode) {
            throw "Upload failed for '$title' (HTTP $([int]$resp.StatusCode)): $respBody"
        }
        $doc = ($respBody | ConvertFrom-Json).data
        Write-Success "Uploaded '$title' -> $($doc.id) ($visibility)."
        return $doc.id
    } finally {
        $client.Dispose()
    }
}

function Wait-WorkspaceDocsReady($headers, $wsLabel, $maxSeconds) {
    if ($maxSeconds -le 0) { return }
    $deadline = (Get-Date).AddSeconds($maxSeconds)
    Write-Info "Waiting for documents in '$wsLabel' to reach READY (timeout ${maxSeconds}s)..."
    while ((Get-Date) -lt $deadline) {
        $docs = (Invoke-Api -Uri "$CoreApiUrl/api/v1/documents?limit=100" -Method Get -Headers $headers).data
        $ready = @($docs | Where-Object { $_.status -eq "READY" }).Count
        $failed = @($docs | Where-Object { $_.status -eq "FAILED" }).Count
        $total = @($docs).Count
        if ($failed -gt 0) {
            $failedNames = ($docs | Where-Object { $_.status -eq "FAILED" } | ForEach-Object { $_.title }) -join ", "
            throw "Ingestion failed in '$wsLabel' ($failed/$total failed): $failedNames"
        }
        if ($ready -eq $total -and $total -gt 0) {
            Write-Success "All $ready/$total documents in '$wsLabel' are READY."
            return
        }
        Write-Info "  $wsLabel`: $ready/$total READY..."
        Start-Sleep -Seconds 3
    }
    throw "Timed out waiting for documents in '$wsLabel' to become READY."
}

$swTotal = [System.Diagnostics.Stopwatch]::StartNew()

Write-Info "Checking core-api health at $CoreApiUrl/actuator/health..."
$health = Invoke-Api -Uri "$CoreApiUrl/actuator/health" -Method Get -TimeoutSec 10
if ($health.status -ne "UP") { throw "core-api is not UP: $($health.status)" }
Write-Success "core-api is UP."

# --- Workspace 1: Multi-Role Demo ---
$ownerLogin = Dev-Login "owner@sopilot.local" "Nguyễn Minh Chủ"
$ws1 = Ensure-Workspace $ownerLogin.Token "SOPilot Acceptance Demo — Multi-Role"
$ws1Headers = @{ Authorization = "Bearer $($ws1.Token)" }

$deptEng = Ensure-Department $ws1Headers "Kỹ thuật"
$deptHr  = Ensure-Department $ws1Headers "Nhân sự"
$deptFin = Ensure-Department $ws1Headers "Tài chính"

$admin     = Ensure-Member $ws1Headers $ws1.Id "admin@sopilot.local"      "Trần Quản Trị"       "ADMIN"  $null    "Workspace Administrator" "EMP-002"
$engLead   = Ensure-Member $ws1Headers $ws1.Id "eng-lead@sopilot.local"   "Lê Kỹ Thuật (Lead)"  "MEMBER" $deptEng "Engineering Lead"        "EMP-101"
$engMember = Ensure-Member $ws1Headers $ws1.Id "eng-member@sopilot.local" "Phạm Dev"            "MEMBER" $deptEng "Backend Engineer"        "EMP-102"
$hrLead    = Ensure-Member $ws1Headers $ws1.Id "hr-lead@sopilot.local"    "Vũ Nhân Sự (Lead)"   "MEMBER" $deptHr  "HR Lead"                 "EMP-201"
$hrMember  = Ensure-Member $ws1Headers $ws1.Id "hr-member@sopilot.local"  "Đỗ Tuyển Dụng"       "MEMBER" $deptHr  "HR Specialist"           "EMP-202"
$finLead   = Ensure-Member $ws1Headers $ws1.Id "fin-lead@sopilot.local"   "Hoàng Tài Chính"     "MEMBER" $deptFin "Finance Lead"            "EMP-301"
$newHire   = Ensure-Member $ws1Headers $ws1.Id "new-hire@sopilot.local"   "Bùi Nhân Viên Mới"   "MEMBER" $null    "New Employee"            "EMP-401"

# Assign department publishers (ADR-009)
Invoke-Api -Uri "$CoreApiUrl/api/v1/departments/$deptEng/publisher" -Method Put -Headers $ws1Headers -Body (@{ userId = $engLead.UserId } | ConvertTo-Json -Compress) | Out-Null
Invoke-Api -Uri "$CoreApiUrl/api/v1/departments/$deptHr/publisher"  -Method Put -Headers $ws1Headers -Body (@{ userId = $hrLead.UserId }  | ConvertTo-Json -Compress) | Out-Null
Invoke-Api -Uri "$CoreApiUrl/api/v1/departments/$deptFin/publisher" -Method Put -Headers $ws1Headers -Body (@{ userId = $finLead.UserId } | ConvertTo-Json -Compress) | Out-Null
Write-Success "Assigned Department Publishers: eng-lead (Kỹ thuật), hr-lead (Nhân sự), fin-lead (Tài chính)."

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$ws1Docs = (Invoke-Api -Uri "$CoreApiUrl/api/v1/documents?limit=100" -Method Get -Headers $ws1Headers).data

$catCulture = Ensure-Category $ws1Headers "Onboarding & Văn hóa"
$catOps     = Ensure-Category $ws1Headers "Vận hành & An toàn"
$catHr      = Ensure-Category $ws1Headers "Nhân sự & Đãi ngộ"
$catFin     = Ensure-Category $ws1Headers "Tài chính & Chi phí"

$d1 = Ensure-Document $ws1Docs (Join-Path $repoRoot "eval\datasets\sop-pilot\corpus\gitlab-buddies.md") `
    "GitLab Onboarding Buddy Program" "WORKSPACE" $null $null $ws1.Token
Set-DocMetadata $d1 $catCulture @("onboarding", "buddy", "handbook") $ws1.Token

$d2 = Ensure-Document $ws1Docs (Join-Path $repoRoot "eval\datasets\sop-pilot\corpus\gitlab-meetings.md") `
    "GitLab Meeting Guidelines" "WORKSPACE" $null $null $ws1.Token
Set-DocMetadata $d2 $catCulture @("meetings", "collaboration") $ws1.Token

$d3 = Ensure-Document $ws1Docs (Join-Path $repoRoot "eval\datasets\smoke\corpus\an-toan-lao-dong.md") `
    "Quy trình An toàn Lao động (Kỹ thuật)" "DEPARTMENTS" $deptEng @($deptEng) $engLead.Token
Set-DocMetadata $d3 $catOps @("safety", "compliance", "ky-thuat") $engLead.Token

$d4 = Ensure-Document $ws1Docs (Join-Path $PSScriptRoot "docs\eng-prod-deployment-runbook.md") `
    "SOP-ENG-01: Production Deployment & Rollback Runbook" "DEPARTMENTS" $deptEng @($deptEng) $engLead.Token
Set-DocMetadata $d4 $catOps @("deployment", "rollback", "sla") $engLead.Token

$d5 = Ensure-Document $ws1Docs (Join-Path $PSScriptRoot "docs\hr-compensation-band-policy.md") `
    "SOP-HR-04: Annual Compensation Review & Bonus Policy" "DEPARTMENTS" $deptHr @($deptHr) $hrLead.Token
Set-DocMetadata $d5 $catHr @("compensation", "bonus", "confidential") $hrLead.Token

$d6 = Ensure-Document $ws1Docs (Join-Path $PSScriptRoot "docs\fin-expense-reimbursement-injection-test.md") `
    "SOP-FIN-02: Travel & Expense Reimbursement Policy" "DEPARTMENTS" $deptFin @($deptFin) $finLead.Token
Set-DocMetadata $d6 $catFin @("expenses", "travel", "reimbursement") $finLead.Token
Write-Success "Assigned categories and tags to all 6 Group 1 documents."

# --- Workspace 2: External Tenant Isolation ---
$extLogin = Dev-Login "external-owner@sopilot.local" "External Partner"
$ws2 = Ensure-Workspace $extLogin.Token "SOPilot External Tenant (Isolation)"
$ws2Headers = @{ Authorization = "Bearer $($ws2.Token)" }
$ws2Docs = (Invoke-Api -Uri "$CoreApiUrl/api/v1/documents?limit=100" -Method Get -Headers $ws2Headers).data

$catLegal = Ensure-Category $ws2Headers "Pháp lý & Bảo mật"
$dExt = Ensure-Document $ws2Docs (Join-Path $PSScriptRoot "docs\ext-partner-nda.md") `
    "EXT-NDA-99: Project Orion Confidentiality Agreement" "WORKSPACE" $null $null $ws2.Token
Set-DocMetadata $dExt $catLegal @("nda", "confidential", "external") $ws2.Token

Wait-WorkspaceDocsReady $ws1Headers "Group 1 Multi-Role" $WaitReadySeconds
Wait-WorkspaceDocsReady $ws2Headers "External Tenant" $WaitReadySeconds

$swTotal.Stop()
Write-Host ""
Write-Success "=== GROUP 1 SEED COMPLETE in $([math]::Round($swTotal.Elapsed.TotalSeconds, 1))s ==="
Write-Host "Workspace 1: SOPilot Acceptance Demo — Multi-Role ($($ws1.Id))"
Write-Host "Workspace 2: SOPilot External Tenant (Isolation) ($($ws2.Id))"
