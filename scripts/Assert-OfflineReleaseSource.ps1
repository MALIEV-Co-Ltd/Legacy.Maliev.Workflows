function Assert-OfflineReleaseSource {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$RepositoryRoot,
        [Parameter(Mandatory)][string]$ExpectedSourceCommit,
        [Parameter(Mandatory)][string]$ApprovedSourceRepository,
        [switch]$AllowFixtureOrigin,
        [string]$SourceGuardModulePath = (Join-Path $PSScriptRoot 'offline_release_source.py')
    )
    $request = @{
        repositoryRoot = $RepositoryRoot
        expectedCommit = $ExpectedSourceCommit
        expectedOrigin = $ApprovedSourceRepository
        allowFixtureOrigin = [bool]$AllowFixtureOrigin
    } | ConvertTo-Json -Compress
    if ([Text.Encoding]::UTF8.GetByteCount($request) -gt 8192) { throw 'Offline release source input is invalid.' }
    $start = [Diagnostics.ProcessStartInfo]::new()
    $start.FileName = if ([OperatingSystem]::IsWindows()) { 'python' } else { 'python3' }
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardInput = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $start.StandardInputEncoding = [Text.UTF8Encoding]::new($false)
    $start.ArgumentList.Add('-B')
    $start.ArgumentList.Add($SourceGuardModulePath)
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $start
    $started = $false
    try {
        $started = $process.Start()
        $output = $process.StandardOutput.ReadToEndAsync()
        $errorOutput = $process.StandardError.ReadToEndAsync()
        $process.StandardInput.Write($request)
        $process.StandardInput.Close()
        if (-not $process.WaitForExit(20000)) { throw 'Source observation timed out.' }
        $text = $output.GetAwaiter().GetResult()
        $errorText = $errorOutput.GetAwaiter().GetResult()
        if ($process.ExitCode -ne 0 -or $errorText.Length -ne 0 -or $text.Length -gt 2048) { throw 'Source observation rejected.' }
        $proof = ConvertFrom-Json -InputObject $text -AsHashtable -ErrorAction Stop
        if ($proof.Count -ne 7 -or $proof.schemaVersion -cne 'offline-release-source/v1' -or
            $proof.sourceCommit -cne $ExpectedSourceCommit -or
            $proof.repositoryIdentity -cne $(if ($AllowFixtureOrigin) { 'isolated-fixture-origin' } else { $ApprovedSourceRepository }) -or
            $proof.cleanObserved -isnot [bool] -or -not $proof.cleanObserved -or
            $proof.remoteMainObserved -isnot [bool] -or -not $proof.remoteMainObserved -or
            $proof.deploymentAllowed -isnot [bool] -or $proof.deploymentAllowed -or
            $proof.liveAccepted -isnot [bool] -or $proof.liveAccepted) { throw 'Invalid source receipt.' }
        return [pscustomobject]$proof
    } catch {
        $failure = [InvalidOperationException]::new('Offline release source validation failed; details withheld.')
        if ($started -and $process.HasExited) { $failure.Data['ExitCode'] = $process.ExitCode }
        throw $failure
    } finally {
        if ($started -and -not $process.HasExited) { $process.Kill($true) }
        $process.Dispose()
    }
}
