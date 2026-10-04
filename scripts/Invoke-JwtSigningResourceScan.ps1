[CmdletBinding()]
param([Parameter(Mandatory = $true)][string]$RepositoryPath)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'JwtSigningResourceScanner.ps1')

try {
    $resolvedRepositoryPath = (Resolve-Path -LiteralPath $RepositoryPath).Path
    $repositoryRoot = @(& git -C $resolvedRepositoryPath rev-parse --show-toplevel 2>$null)
    if ($LASTEXITCODE -ne 0 -or $repositoryRoot.Count -ne 1 -or
        [string]::IsNullOrWhiteSpace($repositoryRoot[0])) {
        throw [System.InvalidOperationException]::new('Unable to enumerate tracked candidate files.')
    }
    $resolvedRepositoryPath = (Resolve-Path -LiteralPath $repositoryRoot[0]).Path
    $trackedOutput = & git -C $resolvedRepositoryPath ls-files --full-name -z 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw [System.InvalidOperationException]::new('Unable to enumerate tracked candidate files.')
    }
    $trackedFiles = @($trackedOutput -split "`0" | Where-Object { $_ })
    if (Test-JwtSigningResourceMaterial -RepositoryPath $resolvedRepositoryPath -TrackedFiles $trackedFiles) {
        throw [System.InvalidOperationException]::new('Candidate contains credential material in a resource; value redacted.')
    }
} catch {
    $message = $_.Exception.Message
    if ($message -notin @(
        'Unable to enumerate tracked candidate files.',
        'Candidate contains credential material in a resource; value redacted.',
        'Candidate resource XML cannot be safely inspected; details redacted.',
        'Candidate generated resource XML cannot be safely inspected; details redacted.',
        'Candidate generated resource cannot be safely inspected; details redacted.')) {
        $message = 'Unable to safely inspect tracked resource files; details redacted.'
    }
    [Console]::Error.WriteLine('[jwt-resource-scan] FAILED: ' + $message)
    exit 1
}
