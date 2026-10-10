#requires -Version 7.2
param(
    [Parameter(Mandatory)][string]$ExpectedHead,
    [Parameter(Mandatory)][switch]$ReadOnly,
    [string]$Root = (Get-Location).Path,
    [string]$FullWorkflowSha = $env:FDM_FULL_WORKFLOW_SHA
)
$ErrorActionPreference = 'Stop'
if (-not $ReadOnly) { throw 'Read-only source custody is required.' }
$control = Join-Path $PSScriptRoot 'fdm_validation_guards.py'
& python3 -B $control source --root $Root --expected-head $ExpectedHead --full-workflow-sha $FullWorkflowSha
exit $LASTEXITCODE
