param(
    [string]$SourceGuardScriptPath,
    [string]$RepositoryRoot,
    [string]$ExpectedSourceCommit,
    [string]$ApprovedSourceRepository,
    [string]$SourceGuardModulePath,
    [switch]$CaptureFailure
)
$ErrorActionPreference = 'Stop'
. $SourceGuardScriptPath
$arguments = @{ RepositoryRoot = $RepositoryRoot; ExpectedSourceCommit = $ExpectedSourceCommit; ApprovedSourceRepository = $ApprovedSourceRepository; AllowFixtureOrigin = $true }
if ($SourceGuardModulePath) { $arguments.SourceGuardModulePath = $SourceGuardModulePath }
try {
    Assert-OfflineReleaseSource @arguments | ConvertTo-Json -Compress
} catch {
    if (-not $CaptureFailure) { throw }
    @{ rejected = $true; exitCode = $_.Exception.Data['ExitCode']; message = $_.Exception.Message } | ConvertTo-Json -Compress
}
