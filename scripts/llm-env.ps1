<#
.SYNOPSIS
  Loads services/ai-service/.env into the current PowerShell session and checks the answer-LLM variables.

.DESCRIPTION
  Dot-source it so the variables stay in your shell (V2-10, for test_endpoint.py, eval answers and the API):
      . ./scripts/llm-env.ps1
  Prints variable names and problems only, never values. Does not change the file.
#>
$ErrorActionPreference = 'Stop'

$envFile = Join-Path (Split-Path -Parent $PSScriptRoot) 'services/ai-service/.env'
if (-not (Test-Path -LiteralPath $envFile)) {
    Write-Host "services/ai-service/.env not found. Copy services/ai-service/.env.example and fill it in." -ForegroundColor Red
    return
}

$loaded = 0
foreach ($line in Get-Content -LiteralPath $envFile) {
    if ($line -notmatch '^\s*[^#\s][^=]*=') { continue }
    $k, $v = $line -split '=', 2
    $v = $v.Trim()
    if ($v.Length -ge 2 -and (($v[0] -eq '"' -and $v[-1] -eq '"') -or ($v[0] -eq "'" -and $v[-1] -eq "'"))) {
        $v = $v.Substring(1, $v.Length - 2)
    }
    Set-Item "env:$($k.Trim())" $v
    $loaded++
}
Write-Host "Loaded $loaded variable(s) from services/ai-service/.env" -ForegroundColor DarkGreen

$problems = 0
foreach ($k in 'SOPILOT_LLM_BASE_URL', 'SOPILOT_LLM_MODEL', 'SOPILOT_LLM_API_KEY') {
    $val = [Environment]::GetEnvironmentVariable($k)
    if ([string]::IsNullOrWhiteSpace($val)) { Write-Host "  MISSING  $k is empty" -ForegroundColor Yellow; $problems++ }
    elseif ($val -match '<[^>]*>') { Write-Host "  MISSING  $k is still a <placeholder>" -ForegroundColor Yellow; $problems++ }
}

$base = $env:SOPILOT_LLM_BASE_URL
if ($base -and $base -notmatch '<') {
    if ($base -notmatch '^https?://') {
        Write-Host "  ERROR    SOPILOT_LLM_BASE_URL must start with http(s)://" -ForegroundColor Red; $problems++
    } elseif ($base.TrimEnd('/') -notmatch '/v1$') {
        # The OpenAI-compatible routes live under /v1; without it every call is a 404.
        $env:SOPILOT_LLM_BASE_URL = $base.TrimEnd('/') + '/v1'
        Write-Host "  FIXED    SOPILOT_LLM_BASE_URL had no /v1 suffix; added it for this session only. Fix the file too." -ForegroundColor Yellow
    }
}

if ($problems -eq 0) { Write-Host "LLM variables are set. No values were printed." -ForegroundColor Green }
else { Write-Host "$problems problem(s) above. No values were printed." -ForegroundColor Red }
