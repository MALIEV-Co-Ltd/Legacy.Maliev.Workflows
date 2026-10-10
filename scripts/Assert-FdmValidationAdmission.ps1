#requires -Version 7.2
param(
    [Parameter(Mandatory)][string]$Phase,
    [Parameter(Mandatory)][int]$MinimumFreeMiB,
    [Parameter(Mandatory)][switch]$RequireNoForeignDotnet,
    [string]$ExpectedHead = $env:FDM_EXPECTED_HEAD,
    [string]$Root = (Get-Location).Path
)
$ErrorActionPreference = 'Stop'
if ($MinimumFreeMiB -ne 3072 -or -not $RequireNoForeignDotnet) { throw 'Unchanged resource admission is required.' }
$control = Join-Path $PSScriptRoot 'fdm_validation_guards.py'
& python3 -B $control admission --root $Root --expected-head $ExpectedHead --phase $Phase --full-workflow-sha $env:FDM_FULL_WORKFLOW_SHA
exit $LASTEXITCODE
