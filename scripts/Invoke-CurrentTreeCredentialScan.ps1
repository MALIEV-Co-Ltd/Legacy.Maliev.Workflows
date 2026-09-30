[CmdletBinding()]
param([Parameter(Mandatory = $true)][string]$RepositoryPath)

$ErrorActionPreference = 'Stop'
try {
    $scanner = Join-Path $PSScriptRoot '../tools/security/current_tree_secrets.py'
    if (-not (Test-Path -LiteralPath $scanner -PathType Leaf)) { throw 'Scanner unavailable.' }
    $pythonName = if ($IsWindows) { 'python' } else { 'python3' }
    $python = Get-Command $pythonName -CommandType Application -ErrorAction Stop | Select-Object -First 1
    $resolvedRepository = (Resolve-Path -LiteralPath $RepositoryPath -ErrorAction Stop).Path
    & $python.Source -B $scanner $resolvedRepository
    if ($LASTEXITCODE -notin @(0, 1, 2)) { throw 'Unexpected scanner exit.' }
    exit $LASTEXITCODE
} catch {
    [Console]::Error.WriteLine('[current-tree-scan] FAILED: scanner/runtime unavailable; details redacted')
    exit 2
}
