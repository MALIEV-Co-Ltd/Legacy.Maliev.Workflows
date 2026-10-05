param(
    [string]$SourceGuardScriptPath,
    [string]$RepositoryRoot,
    [string]$ExpectedSourceCommit,
    [string]$ApprovedSourceRepository
)
$ErrorActionPreference = 'Stop'
. $SourceGuardScriptPath
Assert-OfflineReleaseSource -RepositoryRoot $RepositoryRoot -ExpectedSourceCommit $ExpectedSourceCommit -ApprovedSourceRepository $ApprovedSourceRepository -AllowFixtureOrigin | ConvertTo-Json -Compress
