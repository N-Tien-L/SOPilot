# Moved to scripts/docs/check-docs.ps1 (docs restructure). This wrapper only keeps the old path working for
# commands recorded in older tickets and handoffs; it is removed in Phase 5 of the docs migration.
param([string]$Mode = 'strict', [switch]$LegacyRefsAsErrors)
& (Join-Path $PSScriptRoot 'docs/check-docs.ps1') -Mode $Mode -LegacyRefsAsErrors:$LegacyRefsAsErrors
exit $LASTEXITCODE
