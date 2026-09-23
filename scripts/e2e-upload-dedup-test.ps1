# E2E Test for Upload Deduplication UX flow
# Tests:
# 1. Login as admin to get JWT
# 2. Upload a document -> create documentId
# 3. Compute SHA-256 -> call /check-duplicate (expect no duplicate initially)
# 4. Confirm metadata -> expect ConfirmResultResponse with status
# 5. Upload the same file again -> /check-duplicate (expect BLOCK action)
# 6. Re-attempt confirm -> expect 409 Conflict

$ErrorActionPreference = "Stop"
$GATEWAY = "http://localhost:3001"
$USER = "admin"
$PASS = "Admin@123"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "E2E Test: Upload Deduplication UX Flow" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

function Write-Step($step, $msg) {
    Write-Host "`n[$step] $msg" -ForegroundColor Yellow
}

function Write-Ok($msg) {
    Write-Host "  [OK] $msg" -ForegroundColor Green
}

function Write-Err($msg) {
    Write-Host "  [ERR] $msg" -ForegroundColor Red
}

# Step 1: Login
Write-Step 1 "Login as admin"
try {
    $loginBody = @{ username = $USER; password = $PASS } | ConvertTo-Json
    $loginResp = Invoke-WebRequest -Uri "$GATEWAY/api/v1/auth/login" `
        -Method POST `
        -ContentType "application/json" `
        -Body $loginBody `
        -UseBasicParsing -TimeoutSec 30
    $loginData = $loginResp.Content | ConvertFrom-Json
    $TOKEN = $loginData.accessToken
    if (-not $TOKEN) {
        Write-Err "No accessToken in login response"
        $loginData | ConvertTo-Json -Depth 5 | Write-Host
        exit 1
    }
    Write-Ok "Got JWT (len=$( $TOKEN.Length))"
} catch {
    Write-Err "Login failed: $_"
    exit 1
}

$authHeader = @{ Authorization = "Bearer $TOKEN" }

# Step 2: Create test file and compute SHA-256
Write-Step 2 "Create test file & compute SHA-256"
$tempDir = Join-Path $env:TEMP "poliwise-e2e-$(Get-Random)"
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

$filePath = Join-Path $tempDir "test-document-$(Get-Random).txt"
# Generate a long, unique payload to avoid false semantic-similarity matches against
# short boilerplate from previous test runs. A unique GUID per run + ~5KB of varied text
# ensures content_hash, file_checksum, and semantic fingerprint are all distinct.
$rand = Get-Random
$guid = [guid]::NewGuid().ToString()
$content = @"
Poliwise E2E test document (run=$rand, guid=$guid)
Timestamp: $(Get-Date -Format o)

=== Section A ===
Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor
incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud
exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure
dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur.

=== Section B ===
Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt
mollit anim id est laborum. Curabitur pretium tincidunt lacus. Nulla gravida orci a
odio. Nullam varius, turpis et commodo pharetra, est eros bibendum elit, nec luctus
magna felis sollicitudin mauris. Integer in mauris eu nibh euismod gravida. Duis ac
tellus et risus vulputate vehicula. Donec lobortis risus a elit.

=== Section C ===
$guid -- $rand -- $(Get-Random) -- $(Get-Random) -- $(Get-Random)
Praesent libero. Sed cursus ante dapibus diam. Sed nisi. Nulla quis sem at nibh
elementum imperdiet. Duis sagittis ipsum. Praesent mauris. Fusce nec tellus sed
augue semper porta. Mauris massa. Vestibulum lacinia arcu eget nulla.
"@
Set-Content -Path $filePath -Value $content -NoNewline

$bytes = [System.IO.File]::ReadAllBytes($filePath)
$sha256 = [System.Security.Cryptography.SHA256]::Create()
$hashBytes = $sha256.ComputeHash($bytes)
$CHECKSUM = -join ($hashBytes | ForEach-Object { $_.ToString("x2") })
Write-Ok "File: $filePath"
Write-Ok "SHA-256: $CHECKSUM"
Write-Ok "Size: $( $bytes.Length) bytes"

# Step 3: Check duplicate (initial) — should return not-duplicate
Write-Step 3 "GET /check-duplicate (initial, expect not-duplicate)"
try {
    $dupResp = Invoke-WebRequest -Uri "$GATEWAY/api/v1/documents/check-duplicate?checksum=$CHECKSUM" `
        -Method GET -Headers $authHeader -UseBasicParsing -TimeoutSec 30
    $dupData = $dupResp.Content | ConvertFrom-Json
    Write-Ok "isDuplicate=$($dupData.isDuplicate) action=$($dupData.action) method=$($dupData.detectionMethod)"
} catch {
    Write-Err "check-duplicate failed: $_"
    $_.Exception.Response.StatusCode.value__
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $reader.ReadToEnd() | Write-Host
    }
    exit 1
}

# Step 4: Upload file via gateway (multipart must be proxied)
Write-Step 4 "POST /documents/upload (via gateway)"
try {
    $uploadFile = Get-Item $filePath
    # Use HttpClient for proper multipart upload
    Add-Type -AssemblyName System.Net.Http
    $httpClient = New-Object System.Net.Http.HttpClient
    $httpClient.Timeout = [TimeSpan]::FromSeconds(60)

    $content = New-Object System.Net.Http.MultipartFormDataContent
    $fileStream = [System.IO.File]::OpenRead($filePath)
    $fileContent = New-Object System.Net.Http.StreamContent($fileStream)
    $fileContent.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse("text/plain")
    $content.Add($fileContent, "file", $uploadFile.Name)

    $stringContent1 = New-Object System.Net.Http.StringContent("Initial upload")
    $content.Add($stringContent1, "changelog")
    $stringContent2 = New-Object System.Net.Http.StringContent("vi")
    $content.Add($stringContent2, "language")

    $httpClient.DefaultRequestHeaders.Authorization = [System.Net.Http.Headers.AuthenticationHeaderValue]::new("Bearer", $TOKEN)
    $uploadTask = $httpClient.PostAsync("$GATEWAY/api/v1/documents/upload", $content)
    $uploadResp = $uploadTask.Result
    $uploadJson = $uploadResp.Content.ReadAsStringAsync().Result
    $fileStream.Close()

    if (-not $uploadResp.IsSuccessStatusCode) {
        Write-Err "Upload HTTP $($uploadResp.StatusCode): $uploadJson"
        exit 1
    }
    $uploadData = $uploadJson | ConvertFrom-Json
    $DOCUMENT_ID = $uploadData.id
    if (-not $DOCUMENT_ID) {
        Write-Err "No documentId in upload response"
        $uploadData | ConvertTo-Json -Depth 5 | Write-Host
        exit 1
    }
    Write-Ok "documentId=$DOCUMENT_ID, status=$($uploadData.status)"
} catch {
    Write-Err "Upload failed: $_"
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $reader.ReadToEnd() | Write-Host
    }
    exit 1
}

# Step 5: Confirm metadata (sync) — expect READY
# Polling may take up to 60s; gateway timeout was extended to 120s for /confirm.
Write-Step 5 "POST /confirm (via gateway, expect READY)"
try {
    $confirmBody = @{
        title = "E2E Test Document"
        description = "Created by e2e test"
        categorySlug = "general"
        tags = @("test", "e2e")
        language = "vi"
        fileChecksum = $CHECKSUM
    } | ConvertTo-Json -Depth 5

    $confirmResp = Invoke-WebRequest -Uri "$GATEWAY/api/v1/documents/$DOCUMENT_ID/confirm" `
        -Method POST -Headers $authHeader `
        -ContentType "application/json" `
        -Body $confirmBody -UseBasicParsing -TimeoutSec 180
    $confirmData = $confirmResp.Content | ConvertFrom-Json
    Write-Ok "Confirm result: status=$($confirmData.status) chunkCount=$($confirmData.chunkCount)"
    if ($confirmData.status -ne "READY") {
        Write-Err "Expected READY, got $($confirmData.status)"
        $confirmData | ConvertTo-Json -Depth 5 | Write-Host
    }
} catch {
    Write-Err "Confirm failed: $_"
    if ($_.Exception.Response) {
        $code = $_.Exception.Response.StatusCode.value__
        Write-Host "  HTTP $code"
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $reader.ReadToEnd() | Write-Host
    }
    exit 1
}

# Step 6: Upload the same file again -> check-duplicate should return isDuplicate=true action=BLOCK
Write-Step 6 "GET /check-duplicate (after first upload, expect BLOCK)"
try {
    $dupResp2 = Invoke-WebRequest -Uri "$GATEWAY/api/v1/documents/check-duplicate?checksum=$CHECKSUM" `
        -Method GET -Headers $authHeader -UseBasicParsing -TimeoutSec 30
    $dupData2 = $dupResp2.Content | ConvertFrom-Json
    if ($dupData2.isDuplicate -eq $true -and $dupData2.action -eq "BLOCK") {
        Write-Ok "Duplicate detected as expected (BLOCK). Existing doc id: $($dupData2.existingDocument.documentId)"
    } else {
        Write-Err "Expected isDuplicate=true, action=BLOCK; got isDuplicate=$($dupData2.isDuplicate), action=$($dupData2.action)"
        $dupData2 | ConvertTo-Json -Depth 5 | Write-Host
    }
} catch {
    Write-Err "check-duplicate (2nd) failed: $_"
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $reader.ReadToEnd() | Write-Host
    }
}

# Step 7: Upload same file again -> upload should succeed (STAGING) -> confirm should return 409 with duplicate info
Write-Step 7 "Upload same file again -> confirm expects 409 Conflict"
try {
    $uploadFile2 = Get-Item $filePath
    Add-Type -AssemblyName System.Net.Http
    $httpClient2 = New-Object System.Net.Http.HttpClient
    $httpClient2.Timeout = [TimeSpan]::FromSeconds(60)

    $content2 = New-Object System.Net.Http.MultipartFormDataContent
    $fileStream2 = [System.IO.File]::OpenRead($filePath)
    $fileContent2 = New-Object System.Net.Http.StreamContent($fileStream2)
    $fileContent2.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse("text/plain")
    $content2.Add($fileContent2, "file", $uploadFile2.Name)
    $stringContent3 = New-Object System.Net.Http.StringContent("Duplicate upload attempt")
    $content2.Add($stringContent3, "changelog")
    $stringContent4 = New-Object System.Net.Http.StringContent("vi")
    $content2.Add($stringContent4, "language")

    $httpClient2.DefaultRequestHeaders.Authorization = [System.Net.Http.Headers.AuthenticationHeaderValue]::new("Bearer", $TOKEN)
    $uploadTask2 = $httpClient2.PostAsync("$GATEWAY/api/v1/documents/upload", $content2)
    $uploadResp2 = $uploadTask2.Result
    $uploadJson2 = $uploadResp2.Content.ReadAsStringAsync().Result
    $fileStream2.Close()

    if (-not $uploadResp2.IsSuccessStatusCode) {
        Write-Err "Re-upload HTTP $($uploadResp2.StatusCode): $uploadJson2"
        return
    }
    $uploadData2 = $uploadJson2 | ConvertFrom-Json
    $DOCUMENT_ID_2 = $uploadData2.id
    Write-Ok "Re-upload returned documentId=$DOCUMENT_ID_2 (status=$($uploadData2.status))"

    $confirmBody2 = @{
        title = "E2E Test Document (duplicate)"
        description = "Should be blocked"
        categorySlug = "general"
        tags = @("test", "e2e")
        language = "vi"
        fileChecksum = $CHECKSUM
    } | ConvertTo-Json -Depth 5

    # Use HttpClient for the second confirm because Invoke-WebRequest
    # does not surface 4xx as exceptions in PowerShell; we need to inspect
    # the response status code to detect 409 Conflict.
    Add-Type -AssemblyName System.Net.Http
    $httpClient3 = New-Object System.Net.Http.HttpClient
    $httpClient3.Timeout = [TimeSpan]::FromSeconds(120)
    $httpClient3.DefaultRequestHeaders.Authorization = [System.Net.Http.Headers.AuthenticationHeaderValue]::new("Bearer", $TOKEN)
    $content3 = New-Object System.Net.Http.StringContent($confirmBody2, [System.Text.Encoding]::UTF8, "application/json")
    $confirmTask3 = $httpClient3.PostAsync("$GATEWAY/api/v1/documents/$DOCUMENT_ID_2/confirm", $content3)
    $confirmResp2 = $confirmTask3.Result
    $confirmJson2 = $confirmResp2.Content.ReadAsStringAsync().Result
    $confirmStatus2 = [int]$confirmResp2.StatusCode

    if ($confirmStatus2 -eq 409) {
        $confirmData2 = $confirmJson2 | ConvertFrom-Json
        Write-Ok "Confirm correctly returned 409 Conflict"
        Write-Host "    detectionMethod=$($confirmData2.detectionMethod) existingDoc=$($confirmData2.existingDocument.documentId)"
    } elseif ($confirmStatus2 -eq 200) {
        $confirmData2 = $confirmJson2 | ConvertFrom-Json
        if ($confirmData2.status -eq "DUPLICATE" -or $confirmData2.status -eq "NEAR_DUPLICATE") {
            Write-Ok "Confirm returned $($confirmData2.status) status as expected"
        } else {
            Write-Err "Expected DUPLICATE/NEAR_DUPLICATE/409, got status=$($confirmData2.status) http=$confirmStatus2 body=$confirmJson2"
        }
    } else {
        Write-Err "Confirm failed with HTTP $confirmStatus2 body=$confirmJson2"
    }
} catch {
    Write-Err "Re-upload failed: $_"
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $reader.ReadToEnd() | Write-Host
    }
}

# Step 8: Test ingestion-service endpoints directly
Write-Step 8 "GET ingestion-service /check-duplicate (direct)"
try {
    $ingResp = Invoke-WebRequest -Uri "http://localhost:8088/check-duplicate?checksum=$CHECKSUM" `
        -Method GET -UseBasicParsing -TimeoutSec 30
    $ingData = $ingResp.Content | ConvertFrom-Json
    Write-Ok "Ingestion /check-duplicate: isDuplicate=$($ingData.isDuplicate)"
} catch {
    Write-Err "Ingestion check-duplicate failed: $_"
}

# Step 9: Cleanup
Write-Step 9 "Cleanup"
Remove-Item -Recurse -Force $tempDir -ErrorAction SilentlyContinue
Write-Ok "Removed temp dir"

Write-Host "`n=========================================" -ForegroundColor Cyan
Write-Host "E2E Test completed." -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan