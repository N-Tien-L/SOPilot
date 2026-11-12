<#
.SYNOPSIS
    Measures end-to-end time to first token (TTFT) of the V2 answer API (V2-16, PRD-V2 NFR: P95 < 3 s).
.DESCRIPTION
    Asks each question of the demo workspace (scripts/seed-demo.ps1) twice:
      - "new":      first message of a new conversation (no question rewrite);
      - "followup": a follow-up in that same conversation (history, so the rewrite LLM call runs first).
    TTFT is client-side: from sending POST /ai/v1/conversations/{id}/messages to the first `delta` or
    `refusal` event of the SSE stream. Total time to `done` and the outcome are recorded too.

    This calls the real answer provider (the Modal endpoint in .env). Warm it first (a cold start takes
    minutes; infrastructure/modal/README.md) and run -Warmup questions that are not counted.
    The script reads no secret; it signs in with the local dev login. Report the numbers with the hardware,
    provider, number of runs and spread that this script writes into the result file.
.PARAMETER CoreApiUrl
    Base URL of core-api. Defaults to http://localhost:8080.
.PARAMETER AiServiceUrl
    Base URL of ai-service. Defaults to http://localhost:8000.
.PARAMETER Runs
    How many times the whole question set is asked. Defaults to 1 (15 new + 15 follow-up = 30 asks).
.PARAMETER Warmup
    Questions asked first and not counted. Defaults to 2.
.PARAMETER OutDir
    Where the JSON result goes. Defaults to eval/results/ttft (gitignored).
#>
param(
    [string]$CoreApiUrl = "http://localhost:8080",
    [string]$AiServiceUrl = "http://localhost:8000",
    [int]$Runs = 1,
    [int]$Warmup = 2,
    [string]$OutDir = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
if (-not $OutDir) { $OutDir = Join-Path $root "eval/results/ttft" }
Add-Type -AssemblyName System.Net.Http

# (question, follow-up) pairs over the three seeded demo SOPs. Written for latency only: no gold answers.
$pairs = @(
    @("Chương trình buddy ở GitLab kéo dài bao lâu?", "Vậy buddy cần làm gì trong tuần đầu?"),
    @("Ai được chọn làm buddy cho nhân viên mới?", "Người đó có cần kinh nghiệm gì không?"),
    @("Buddy và quản lý trực tiếp khác nhau thế nào?", "Còn onboarding issue thì ai phụ trách?"),
    @("Nhân viên mới nên hỏi buddy những gì?", "Nếu buddy bận thì sao?"),
    @("Có cần gặp buddy hàng tuần không?", "Mỗi lần gặp khoảng bao lâu?"),
    @("Cuộc họp ở GitLab có cần agenda không?", "Agenda nên được chia sẻ khi nào?"),
    @("Ai ghi biên bản cuộc họp?", "Biên bản lưu ở đâu?"),
    @("Cuộc họp có bắt buộc bật camera không?", "Còn ghi hình cuộc họp thì sao?"),
    @("Khi nào nên hủy một cuộc họp?", "Cần báo trước bao lâu?"),
    @("Họp đúng giờ được quy định thế nào?", "Nếu người chủ trì đến muộn thì sao?"),
    @("Quy trình an toàn lao động yêu cầu trang bị bảo hộ gì?", "Ai kiểm tra việc đó?"),
    @("Khi xảy ra tai nạn lao động phải làm gì đầu tiên?", "Sau đó báo cáo cho ai?"),
    @("What is the GitLab buddy program for?", "How long does it last?"),
    @("Should every meeting have an agenda?", "Who writes the notes?"),
    @("Do meetings start on time at GitLab?", "What if the host is late?")
)
$warmupQuestions = @("Chương trình buddy là gì?", "Cuộc họp có cần agenda không?")

function Invoke-Api([string]$Uri, [string]$Method = "Get", [hashtable]$Headers = @{}, $Body = $null) {
    $params = @{ Uri = $Uri; Method = $Method; Headers = $Headers; UseBasicParsing = $true }
    if ($null -ne $Body) {
        $params.Body = [System.Text.Encoding]::UTF8.GetBytes([string]$Body)
        $params.ContentType = "application/json; charset=utf-8"
    }
    $resp = Invoke-WebRequest @params
    return [System.Text.Encoding]::UTF8.GetString($resp.RawContentStream.ToArray()) | ConvertFrom-Json
}

# Sign in as the demo owner, in the demo workspace.
$login = Invoke-Api "$CoreApiUrl/api/v1/auth/dev-login" "Post" @{} (@{ email = "demo-owner@sopilot.local"; displayName = "Demo Owner" } | ConvertTo-Json)
$auth = @{ Authorization = "Bearer $($login.data.accessToken)" }
$ws = (Invoke-Api "$CoreApiUrl/api/v1/workspaces" "Get" $auth).data | Where-Object { $_.name -eq "SOPilot Demo Workspace" }
if (-not $ws) { Write-Error "Demo workspace not found; run scripts/seed-demo.ps1 first."; exit 1 }
$switch = Invoke-Api "$CoreApiUrl/api/v1/auth/switch-workspace" "Post" $auth (@{ workspaceId = $ws.id } | ConvertTo-Json)
$token = $switch.data.accessToken  # valid for at most 15 min; long runs sign in again below
$tokenAt = Get-Date

function Get-Token {
    if (((Get-Date) - $script:tokenAt).TotalMinutes -gt 10) {
        $l = Invoke-Api "$CoreApiUrl/api/v1/auth/dev-login" "Post" @{} (@{ email = "demo-owner@sopilot.local"; displayName = "Demo Owner" } | ConvertTo-Json)
        $s = Invoke-Api "$CoreApiUrl/api/v1/auth/switch-workspace" "Post" @{ Authorization = "Bearer $($l.data.accessToken)" } (@{ workspaceId = $ws.id } | ConvertTo-Json)
        $script:token = $s.data.accessToken
        $script:tokenAt = Get-Date
    }
    return $script:token
}

$client = [System.Net.Http.HttpClient]::new()
$client.Timeout = [TimeSpan]::FromSeconds(180)

# One question; returns ttft_ms, total_ms, outcome, conversation id.
function Ask([string]$conversation, [string]$question) {
    $req = [System.Net.Http.HttpRequestMessage]::new([System.Net.Http.HttpMethod]::Post,
        "$AiServiceUrl/ai/v1/conversations/$conversation/messages")
    $req.Headers.Authorization = [System.Net.Http.Headers.AuthenticationHeaderValue]::new("Bearer", (Get-Token))
    $json = @{ content = $question } | ConvertTo-Json
    $req.Content = [System.Net.Http.StringContent]::new($json, [System.Text.Encoding]::UTF8, "application/json")
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $resp = $client.SendAsync($req, [System.Net.Http.HttpCompletionOption]::ResponseHeadersRead).Result
    if (-not $resp.IsSuccessStatusCode) { throw "HTTP $([int]$resp.StatusCode)" }
    $reader = [System.IO.StreamReader]::new($resp.Content.ReadAsStreamAsync().Result, [System.Text.Encoding]::UTF8)
    $ttft = $null; $event = $null; $conv = $conversation; $outcome = $null
    try {
        while ($null -ne ($line = $reader.ReadLine())) {
            if ($line.StartsWith("event: ")) { $event = $line.Substring(7); continue }
            if (-not $line.StartsWith("data: ")) { continue }
            $data = $line.Substring(6) | ConvertFrom-Json
            if ($null -eq $ttft -and ($event -eq "delta" -or $event -eq "refusal")) { $ttft = $sw.ElapsedMilliseconds }
            if ($event -eq "meta") { $conv = $data.conversationId }
            if ($event -eq "error") { $outcome = "ERROR:$($data.code)"; break }
            if ($event -eq "done") { $outcome = $data.outcome; break }
        }
    } finally { $reader.Dispose(); $resp.Dispose() }
    return [pscustomobject]@{ ttft_ms = $ttft; total_ms = $sw.ElapsedMilliseconds; outcome = $outcome; conversation = $conv }
}

function Pct($values, [double]$p) {
    $v = @($values | Where-Object { $null -ne $_ } | Sort-Object)
    if ($v.Count -eq 0) { return $null }
    $rank = [Math]::Ceiling($p * $v.Count) - 1   # nearest rank
    return $v[[Math]::Max(0, [int]$rank)]
}

function Stats($rows) {
    $t = @($rows | ForEach-Object { $_.ttft_ms } | Where-Object { $null -ne $_ })
    if ($t.Count -eq 0) { return @{ n = 0 } }
    $mean = ($t | Measure-Object -Average).Average
    $sd = [Math]::Sqrt((($t | ForEach-Object { ($_ - $mean) * ($_ - $mean) }) | Measure-Object -Sum).Sum / [Math]::Max(1, $t.Count - 1))
    return [ordered]@{ n = $t.Count; p50_ms = (Pct $t 0.50); p95_ms = (Pct $t 0.95); mean_ms = [Math]::Round($mean, 1);
        stdev_ms = [Math]::Round($sd, 1); min_ms = ($t | Measure-Object -Minimum).Minimum; max_ms = ($t | Measure-Object -Maximum).Maximum;
        p95_under_3s = ((Pct $t 0.95) -lt 3000) }
}

for ($i = 0; $i -lt [Math]::Min($Warmup, $warmupQuestions.Count); $i++) {
    $w = Ask "new" $warmupQuestions[$i]
    Write-Host "[warmup] ttft=$($w.ttft_ms) ms outcome=$($w.outcome)"
}

$rows = @()
for ($run = 1; $run -le $Runs; $run++) {
    foreach ($pair in $pairs) {
        $first = Ask "new" $pair[0]
        $rows += [pscustomobject]@{ run = $run; kind = "new"; question = $pair[0]; ttft_ms = $first.ttft_ms; total_ms = $first.total_ms; outcome = $first.outcome }
        $second = Ask $first.conversation $pair[1]
        $rows += [pscustomobject]@{ run = $run; kind = "followup"; question = $pair[1]; ttft_ms = $second.ttft_ms; total_ms = $second.total_ms; outcome = $second.outcome }
        Write-Host "[run $run] new ttft=$($first.ttft_ms) ($($first.outcome)) | followup ttft=$($second.ttft_ms) ($($second.outcome))"
    }
}
$client.Dispose()

$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$ram = [Math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)
$result = [ordered]@{
    measured_at = (Get-Date).ToString("o")
    conditions = [ordered]@{
        hardware = "$($cpu.Name.Trim()), $($cpu.NumberOfLogicalProcessors) logical CPUs, $ram GB RAM"
        stack = "docker-compose.v2.yml (core-api, ai-service, ai-worker local); answer LLM = SOPILOT_LLM_* endpoint"
        runs = $Runs; warmup = $Warmup; questions_per_run = $pairs.Count * 2
        ttft = "client-side, POST until the first delta or refusal event"
    }
    new_conversation = Stats ($rows | Where-Object { $_.kind -eq "new" })
    with_history_rewrite = Stats ($rows | Where-Object { $_.kind -eq "followup" })
    all = Stats $rows
    outcomes = $rows | Group-Object outcome | ForEach-Object { [ordered]@{ outcome = $_.Name; count = $_.Count } }
    rows = $rows | Select-Object run, kind, ttft_ms, total_ms, outcome
}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$file = Join-Path $OutDir ("ttft-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".json")
[System.IO.File]::WriteAllText($file, ($result | ConvertTo-Json -Depth 6), [System.Text.UTF8Encoding]::new($false))
Write-Host ""
Write-Host "new conversation (no rewrite): $($result.new_conversation | ConvertTo-Json -Compress)"
Write-Host "with history (rewrite):        $($result.with_history_rewrite | ConvertTo-Json -Compress)"
Write-Host "Result: $file"
