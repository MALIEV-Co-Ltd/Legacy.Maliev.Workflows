#requires -Version 7.2
param(
    [Parameter(Mandatory)][string]$Phase,
    [Parameter(Mandatory)][string]$Manifest,
    [Parameter(Mandatory)][string]$Trx,
    [Parameter(Mandatory)][string]$ExpectedHead,
    [string]$Root = (Get-Location).Path
)
$ErrorActionPreference = 'Stop'
if ($Manifest -cne 'tests/fdm-validation-phases.json') { throw 'Reviewed phase manifest location is required.' }
$control = Join-Path $PSScriptRoot 'fdm_validation_guards.py'
& python3 -B $control trx --root $Root --expected-head $ExpectedHead --phase $Phase --trx $Trx --full-workflow-sha $env:FDM_FULL_WORKFLOW_SHA
exit $LASTEXITCODE
