<#
.SYNOPSIS
    Seeds demo data for SOPilot V2 (Ticket V2-16).
.DESCRIPTION
    Creates a demo TEAM workspace with:
    - 2 Departments: "Kỹ thuật" and "Nhân sự"
    - 2 members, invited and accepted through dev login: engineer@sopilot.local ("Kỹ thuật") and
      hr@sopilot.local ("Nhân sự")
    - SOP documents from tracked corpus files (no gitignored files are needed):
      * 2 Workspace-wide SOPs (eval/datasets/sop-pilot/corpus, public to all members)
      * 1 Department-limited SOP (eval/datasets/smoke/corpus, restricted to "Kỹ thuật", for UC-10 demo)
    Idempotent: safe to run multiple times. Documents are matched by title; the summary reports what
    was uploaded, what already existed and what failed. Exits with code 1 if any upload failed.
.PARAMETER CoreApiUrl
    Base URL of core-api. Defaults to http://localhost:8080.
#>

param(
    [string]$CoreApiUrl = "http://localhost:8080"
)

$ErrorActionPreference = "Stop"

function Write-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Success($msg) { Write-Host "[OK]   $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }

# Windows PowerShell 5.1 sends a string body as ISO-8859-1 and decodes "application/json" without a
# charset the same way, which turns "Kỹ thuật" into "K? thu?t". Send and read UTF-8 bytes instead.
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

Write-Info "Checking core-api health at $CoreApiUrl/actuator/health..."
try {
    $health = Invoke-Api -Uri "$CoreApiUrl/actuator/health" -Method Get -TimeoutSec 10
    if ($health.status -ne "UP") {
        Write-Warn "core-api is not fully UP: $($health.status)"
    } else {
        Write-Success "core-api is UP and healthy."
    }
} catch {
    Write-Error "Cannot reach core-api at $CoreApiUrl. Make sure the service is running (e.g. docker compose -f docker-compose.v2.yml up -d)."
    exit 1
}

# 1. Dev Login as Demo Owner
Write-Info "Logging in as demo-owner@sopilot.local..."
$loginBody = @{
    email = "demo-owner@sopilot.local"
    displayName = "Demo Owner"
} | ConvertTo-Json

$loginResp = Invoke-Api -Uri "$CoreApiUrl/api/v1/auth/dev-login" -Method Post `
    -ContentType "application/json" -Body $loginBody

$token = $loginResp.data.accessToken
$headers = @{
    Authorization = "Bearer $token"
}

Write-Success "Logged in. User ID: $($loginResp.data.user.id)"

# 2. Setup TEAM Workspace
Write-Info "Checking or creating demo TEAM workspace..."
$workspaces = (Invoke-Api -Uri "$CoreApiUrl/api/v1/workspaces" -Method Get -Headers $headers).data
$demoWs = $workspaces | Where-Object { $_.name -eq "SOPilot Demo Workspace" }

if (-not $demoWs) {
    Write-Info "Creating workspace 'SOPilot Demo Workspace'..."
    $wsBody = @{ name = "SOPilot Demo Workspace" } | ConvertTo-Json
    $wsResp = Invoke-Api -Uri "$CoreApiUrl/api/v1/workspaces" -Method Post `
        -ContentType "application/json" -Headers $headers -Body $wsBody
    $token = $wsResp.data.accessToken
    $headers.Authorization = "Bearer $token"
    $workspaceId = $wsResp.data.workspace.id
    Write-Success "Created TEAM workspace: $workspaceId"
} else {
    Write-Info "Workspace exists: $($demoWs.id). Switching to it..."
    $switchBody = @{ workspaceId = $demoWs.id } | ConvertTo-Json
    $switchResp = Invoke-Api -Uri "$CoreApiUrl/api/v1/auth/switch-workspace" -Method Post `
        -ContentType "application/json" -Headers $headers -Body $switchBody
    $token = $switchResp.data.accessToken
    $headers.Authorization = "Bearer $token"
    $workspaceId = $demoWs.id
    Write-Success "Switched to workspace: $workspaceId"
}

# 3. Setup Departments
Write-Info "Setting up departments..."
$existingDepts = (Invoke-Api -Uri "$CoreApiUrl/api/v1/departments" -Method Get -Headers $headers).data

function Get-OrCreate-Dept($name) {
    $found = $existingDepts | Where-Object { $_.name -eq $name }
    if ($found) {
        Write-Success "Department '$name' already exists: $($found.id)"
        return $found.id
    }
    $body = @{ name = $name } | ConvertTo-Json
    $resp = Invoke-Api -Uri "$CoreApiUrl/api/v1/departments" -Method Post `
        -ContentType "application/json" -Headers $headers -Body $body
    Write-Success "Created department '$name': $($resp.data.id)"
    return $resp.data.id
}

$deptEngId = Get-OrCreate-Dept "Kỹ thuật"
$deptHrId = Get-OrCreate-Dept "Nhân sự"

# 4. Demo members: invite, then accept as that user (dev login), so they are real members.
#    engineer@sopilot.local -> "Kỹ thuật" (sees the department-limited SOP, UC-10)
#    hr@sopilot.local       -> "Nhân sự"  (does not see it)
function Ensure-Member($email, $displayName, $deptId, $jobTitle) {
    $result = [pscustomobject]@{ Status = "failed"; UserId = $null; Token = $null }
    $members = (Invoke-Api -Uri "$CoreApiUrl/api/v1/members" -Method Get -Headers $headers).data
    if ($members | Where-Object { $_.email -eq $email }) {
        try {
            $memberLogin = Invoke-Api -Uri "$CoreApiUrl/api/v1/auth/dev-login" -Method Post `
                -ContentType "application/json" -Body (@{ email = $email; displayName = $displayName } | ConvertTo-Json)
            $memberSwitch = Invoke-Api -Uri "$CoreApiUrl/api/v1/auth/switch-workspace" -Method Post `
                -ContentType "application/json" -Body (@{ workspaceId = $workspaceId } | ConvertTo-Json) `
                -Headers @{ Authorization = "Bearer $($memberLogin.data.accessToken)" }
            $result.Status = "member"; $result.UserId = $memberLogin.data.user.id
            $result.Token = $memberSwitch.data.accessToken
            Write-Success "$email is already a member."
        } catch {
            Write-Warn "$email is a member but could not sign in: $($_.Exception.Message)"
        }
        return $result
    }
    $pending = (Invoke-Api -Uri "$CoreApiUrl/api/v1/invitations" -Method Get -Headers $headers).data
    $invite = $pending | Where-Object { $_.email -eq $email }
    $inviteId = $null
    if ($invite) {
        $inviteId = $invite.id
        Write-Info "$email has a pending invitation: $inviteId"
    } else {
        $inviteBody = @{
            email = $email
            role = "MEMBER"
            displayName = $displayName
            departmentId = $deptId
            jobTitle = $jobTitle
        } | ConvertTo-Json
        try {
            $invResp = Invoke-Api -Uri "$CoreApiUrl/api/v1/invitations" -Method Post `
                -ContentType "application/json" -Headers $headers -Body $inviteBody
            $inviteId = $invResp.data.id
            Write-Success "Invited $email`: $inviteId"
        } catch {
            Write-Warn "Invitation for $email not created: $($_.Exception.Message)"
            return $result
        }
    }
    try {
        $memberLogin = Invoke-Api -Uri "$CoreApiUrl/api/v1/auth/dev-login" -Method Post `
            -ContentType "application/json" -Body (@{ email = $email; displayName = $displayName } | ConvertTo-Json)
        $memberHeaders = @{ Authorization = "Bearer $($memberLogin.data.accessToken)" }
        $accepted = Invoke-Api -Uri "$CoreApiUrl/api/v1/invitations/accept" -Method Post `
            -ContentType "application/json" -Headers $memberHeaders `
            -Body (@{ invitationId = $inviteId } | ConvertTo-Json)
        $result.Status = "member"; $result.UserId = $memberLogin.data.user.id
        $result.Token = $accepted.data.accessToken  # signed into the demo workspace
        Write-Success "$email accepted the invitation."
    } catch {
        Write-Warn "$email could not accept the invitation: $($_.Exception.Message)"
    }
    return $result
}

Write-Info "Setting up demo members..."
$engineer = Ensure-Member "engineer@sopilot.local" "Nguyễn Kỹ Thuật" $deptEngId "Kỹ sư vận hành"
$hr = Ensure-Member "hr@sopilot.local" "Trần Nhân Sự" $deptHrId "Chuyên viên nhân sự"
$engStatus = $engineer.Status
$hrStatus = $hr.Status

# Document writes belong to publishers (V2-36, ADR-009): the department-limited SOP is uploaded by the
# publisher of "Kỹ thuật", who must be a member of it. The owner (workspace publisher) uploads the rest.
$engPublisher = "failed"
if ($engineer.UserId) {
    try {
        Invoke-Api -Uri "$CoreApiUrl/api/v1/departments/$deptEngId/publisher" -Method Put -Headers $headers `
            -Body (@{ userId = $engineer.UserId } | ConvertTo-Json) | Out-Null
        $engPublisher = "publisher"
        Write-Success "engineer@sopilot.local is the publisher of 'Kỹ thuật'."
    } catch {
        Write-Warn "Could not make engineer@sopilot.local the publisher of 'Kỹ thuật': $($_.Exception.Message)"
    }
}

# 5. Upload SOP Documents from tracked corpus files (gitignored nb-*.md are never used)
$sopCorpusPath = Join-Path $PSScriptRoot "..\eval\datasets\sop-pilot\corpus"
$smokeCorpusPath = Join-Path $PSScriptRoot "..\eval\datasets\smoke\corpus"
foreach ($dir in @($sopCorpusPath, $smokeCorpusPath)) {
    if (-not (Test-Path $dir)) {
        Write-Error "Cannot locate corpus directory: $dir"
        exit 1
    }
}

Write-Info "Loading existing documents (first page, up to 100)..."
$existingPage = Invoke-Api -Uri "$CoreApiUrl/api/v1/documents?limit=100" -Method Get -Headers $headers
$existingDocs = $existingPage.data
if ($existingPage.page.hasMore) {
    Write-Warn "More than 100 documents exist; duplicate check only covers the first 100."
}

# Returns 'uploaded', 'exists' or 'failed'. Never throws, so one bad file does not stop the others.
function Upload-Document($filePath, $title, $visibility, $ownerDeptId, $deptIds, $authToken) {
    $existing = $existingDocs | Where-Object { $_.title -eq $title }
    if ($existing) {
        Write-Success "Document '$title' already uploaded: $($existing.id)"
        return "exists"
    }

    Write-Info "Uploading: $title (Visibility: $visibility)..."

    # Use HttpClient for multipart/form-data upload
    Add-Type -AssemblyName System.Net.Http
    $client = [System.Net.Http.HttpClient]::new()
    try {
        $client.DefaultRequestHeaders.Authorization = [System.Net.Http.Headers.AuthenticationHeaderValue]::new("Bearer", $authToken)

        $content = [System.Net.Http.MultipartFormDataContent]::new()

        $fileBytes = [System.IO.File]::ReadAllBytes($filePath)
        $fileContent = [System.Net.Http.ByteArrayContent]::new($fileBytes)
        $fileContent.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse("text/markdown")
        $fileName = [System.IO.Path]::GetFileName($filePath)
        $content.Add($fileContent, "file", $fileName)

        if ($title) {
            $content.Add([System.Net.Http.StringContent]::new($title), "title")
        }
        if ($visibility) {
            $content.Add([System.Net.Http.StringContent]::new($visibility), "visibility")
        }
        if ($ownerDeptId) {
            $content.Add([System.Net.Http.StringContent]::new($ownerDeptId.ToString()), "ownerDepartmentId")
        }
        if ($deptIds) {
            foreach ($dId in $deptIds) {
                $content.Add([System.Net.Http.StringContent]::new($dId.ToString()), "departmentIds")
            }
        }

        $response = $client.PostAsync("$CoreApiUrl/api/v1/documents", $content).Result
        if ($response.IsSuccessStatusCode) {
            $respStr = $response.Content.ReadAsStringAsync().Result
            $docData = $respStr | ConvertFrom-Json
            Write-Success "Uploaded '$title' -> ID: $($docData.data.id)"
            return "uploaded"
        }
        $err = $response.Content.ReadAsStringAsync().Result
        Write-Warn "Upload failed for '$title': $err"
        return "failed"
    } catch {
        Write-Warn "Upload failed for '$title': $($_.Exception.Message)"
        return "failed"
    } finally {
        $client.Dispose()
    }
}

$results = @()

function Add-Upload($filePath, $title, $visibility, $ownerDeptId, $deptIds, $authToken = $token) {
    if (-not (Test-Path $filePath)) {
        Write-Warn "Missing corpus file, not uploaded: $filePath"
        $script:results += [pscustomobject]@{ Title = $title; Visibility = $visibility; Status = "failed" }
        return
    }
    if (-not $authToken) {
        Write-Warn "No publisher token for '$title'; not uploaded."
        $script:results += [pscustomobject]@{ Title = $title; Visibility = $visibility; Status = "failed" }
        return
    }
    $status = Upload-Document $filePath $title $visibility $ownerDeptId $deptIds $authToken
    $script:results += [pscustomobject]@{ Title = $title; Visibility = $visibility; Status = $status }
}

# 2 WORKSPACE-wide SOPs (tracked in eval/datasets/sop-pilot)
Add-Upload (Join-Path $sopCorpusPath "gitlab-buddies.md") `
    "Quy trình Hướng dẫn Đồng đội (GitLab Buddy Program)" "WORKSPACE" $null $null
Add-Upload (Join-Path $sopCorpusPath "gitlab-meetings.md") `
    "Quy định Họp và Thảo luận (GitLab Meetings)" "WORKSPACE" $null $null

# 1 DEPARTMENTS-limited SOP (tracked sample in eval/datasets/smoke, visible to "Kỹ thuật" only; UC-10)
Add-Upload (Join-Path $smokeCorpusPath "an-toan-lao-dong.md") `
    "Quy trình An toàn Lao động (Giới hạn Kỹ thuật)" "DEPARTMENTS" $deptEngId @($deptEngId) $engineer.Token

$uploaded = @($results | Where-Object { $_.Status -eq "uploaded" }).Count
$already = @($results | Where-Object { $_.Status -eq "exists" }).Count
$failed = @($results | Where-Object { $_.Status -eq "failed" }).Count
$workspaceDocs = @($results | Where-Object { $_.Visibility -eq "WORKSPACE" -and $_.Status -ne "failed" }).Count
$deptDocs = @($results | Where-Object { $_.Visibility -eq "DEPARTMENTS" -and $_.Status -ne "failed" }).Count

Write-Host ""
if ($failed -gt 0 -or $engStatus -ne "member" -or $hrStatus -ne "member") {
    Write-Warn "=== DEMO SEEDING FINISHED WITH FAILURES ($failed failed upload(s)) ==="
} else {
    Write-Success "=== DEMO SEEDING COMPLETED SUCCESSFULLY ==="
}
Write-Host "Workspace:   SOPilot Demo Workspace ($workspaceId)"
Write-Host "Owner:       demo-owner@sopilot.local"
Write-Host "Departments: Kỹ thuật ($deptEngId), Nhân sự ($deptHrId)"
Write-Host "Members:     engineer@sopilot.local (Kỹ thuật, $engPublisher): $engStatus; hr@sopilot.local (Nhân sự): $hrStatus"
Write-Host "Documents:   $uploaded uploaded, $already already present, $failed failed"
Write-Host "             in place: $workspaceDocs WORKSPACE + $deptDocs DEPARTMENTS (Kỹ thuật only)"

if ($failed -gt 0 -or $engStatus -ne "member" -or $hrStatus -ne "member") {
    exit 1
}
