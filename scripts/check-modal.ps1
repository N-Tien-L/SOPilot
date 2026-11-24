<#
.SYNOPSIS
  Checks the Modal LLM/reranker configuration inside the running containers and against the live endpoints.

.DESCRIPTION
  1. Per container: prints each variable; secrets print only "configured" / "NOT configured".
  2. Probes Modal with the key taken from the ai-service container: GET /models and an unauthenticated
     rerank call (expects 401). Prints HTTP codes only, never the key.
  Cold starts can take minutes, so probes wait up to -TimeoutS seconds.
  Run after: docker compose up -d. Exit code 1 when a check fails.

.EXAMPLE
  ./scripts/check-modal.ps1
#>
param([int]$TimeoutS = 900)

$ErrorActionPreference = 'Stop'
$script:fail = 0

function Get-ContainerVar([string]$svc, [string]$name) {
    $out = docker compose exec -T $svc sh -c "printenv $name" 2>$null
    if ($LASTEXITCODE -ne 0) { return $null }
    return ($out | Out-String).Trim()
}

$secretNames = @('SOPILOT_LLM_API_KEY')
$vars = @{
    'ai-service' = @('SOPILOT_LLM_BASE_URL', 'SOPILOT_LLM_API_KEY', 'SOPILOT_RERANK_BASE_URL', 'RERANK_ENABLED', 'RERANK_PROVIDER', 'RERANK_TIMEOUT_S', 'SOPILOT_ROUTER_CLASSIFIER_MODE', 'SOPILOT_ROUTER_CLASSIFIER_DIR', 'SOPILOT_LLM_THINKING')
    'ai-worker'  = @('SOPILOT_LLM_BASE_URL', 'SOPILOT_LLM_API_KEY')
}

Write-Host '== Container variables =='
foreach ($svc in 'ai-service', 'ai-worker') {
    foreach ($v in $vars[$svc]) {
        $val = Get-ContainerVar $svc $v
        if ($secretNames -contains $v) {
            $shown = if ([string]::IsNullOrWhiteSpace($val)) { 'NOT configured' } else { 'configured' }
        } else {
            $shown = if ($null -eq $val) { '(container not running)' } elseif ($val -eq '') { '(empty)' } else { $val }
        }
        $bad = ($shown -in 'NOT configured', '(empty)', '(container not running)') -and $v -ne 'SOPILOT_RERANK_BASE_URL'
        if ($bad) { $script:fail++ }
        Write-Host ("  {0,-10} {1,-26} {2}" -f $svc, $v, $shown) -ForegroundColor $(if ($bad) { 'Red' } else { 'Gray' })
    }
}

Write-Host '== SetFit router artifact =='
$mode = Get-ContainerVar 'ai-service' 'SOPILOT_ROUTER_CLASSIFIER_MODE'
$rdir = Get-ContainerVar 'ai-service' 'SOPILOT_ROUTER_CLASSIFIER_DIR'
if ($mode -in 'shadow', 'on') {
    $files = docker compose exec -T ai-service sh -c "ls '$rdir' 2>/dev/null | wc -l"
    $n = [int](($files | Out-String).Trim())
    $ok = $n -gt 0
    if (-not $ok) { $script:fail++ }
    Write-Host "  mode=$mode, $rdir has $n file(s) $(if ($ok) { 'OK' } else { 'artifact missing (mount services/ai-service/models/setfit-router)' })" -ForegroundColor $(if ($ok) { 'Green' } else { 'Red' })
}
else { Write-Host "  mode=${mode}: classifier not used, artifact not checked" -ForegroundColor Yellow }

$base = Get-ContainerVar 'ai-service' 'SOPILOT_LLM_BASE_URL'
$key = Get-ContainerVar 'ai-service' 'SOPILOT_LLM_API_KEY'
$rerank = Get-ContainerVar 'ai-service' 'SOPILOT_RERANK_BASE_URL'
$rerankOn = (Get-ContainerVar 'ai-service' 'RERANK_ENABLED') -eq 'true' -and (Get-ContainerVar 'ai-service' 'RERANK_PROVIDER') -eq 'modal'

function Get-Code([string[]]$curlArgs) {
    $code = & curl.exe -s -o NUL -w '%{http_code}' -L --max-time $TimeoutS @curlArgs
    return $code
}

Write-Host '== Modal endpoints (cold start may take minutes) =='
if ($base -and $key) {
    $code = Get-Code @('-H', "Authorization: Bearer $key", "$base/models")
    $ok = $code -eq '200'
    if (-not $ok) { $script:fail++ }
    Write-Host "  LLM GET /models (real key)        HTTP $code  $(if ($ok) { 'OK' } else { 'expected 200 (401 = key mismatch, 404/000 = wrong URL)' })" -ForegroundColor $(if ($ok) { 'Green' } else { 'Red' })
}
else { Write-Host '  skipped LLM probe: base URL or key missing' -ForegroundColor Yellow }

if ($rerankOn -and $rerank) {
    $code = Get-Code @('-H', 'Authorization: Bearer wrong','-H', 'Content-Type: application/json', '-d', '{}', "$rerank/rerank")
    $ok = $code -eq '401'
    if (-not $ok) { $script:fail++ }
    Write-Host "  rerank POST (wrong key)           HTTP $code  $(if ($ok) { 'OK (authenticated)' } else { 'expected 401' })" -ForegroundColor $(if ($ok) { 'Green' } else { 'Red' })

    $code = Get-Code @('-H', "Authorization: Bearer $key",'-H', 'Content-Type: application/json', '-d', '{"model":"x","query":"q","documents":["d"]}', "$rerank/rerank")
    $ok = $code -match '^(2\d\d|400|422)$'
    if (-not $ok) { $script:fail++ }
    Write-Host "  rerank POST (real key)            HTTP $code  $(if ($ok) { 'OK (key accepted)' } else { 'key rejected or URL wrong' })" -ForegroundColor $(if ($ok) { 'Green' } else { 'Red' })
}
else { Write-Host '  rerank probe skipped (RERANK_ENABLED/RERANK_PROVIDER not modal, or URL empty)' -ForegroundColor Yellow }

Write-Host ''
if ($script:fail -gt 0) { Write-Host "$($script:fail) check(s) failed." -ForegroundColor Red; exit 1 }
Write-Host 'All checks passed.' -ForegroundColor Green
