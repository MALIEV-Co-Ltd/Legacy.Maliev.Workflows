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
    $stdout = [IO.MemoryStream]::new()
    try {
        $started = $process.Start()
        $clock = [Diagnostics.Stopwatch]::StartNew()
        $streams = @(
            @{ Pipe = $process.StandardOutput.BaseStream; Buffer = [byte[]]::new(4096); Limit = 2048; Bytes = 0; Done = $false; Read = $null; Keep = $true },
            @{ Pipe = $process.StandardError.BaseStream; Buffer = [byte[]]::new(4096); Limit = 16384; Bytes = 0; Done = $false; Read = $null; Keep = $false }
        )
        foreach ($stream in $streams) { $stream.Read = $stream.Pipe.ReadAsync($stream.Buffer, 0, $stream.Buffer.Length) }
        # An unresponsive child must not block stdin before output draining starts.
        $process.StandardInput.AutoFlush = $true
        $inputWrite = $process.StandardInput.WriteAsync($request)
        $inputClosed = $false
        while (-not $process.HasExited -or @($streams | Where-Object { -not $_.Done }).Count -ne 0 -or -not $inputClosed) {
            if ($clock.ElapsedMilliseconds -ge 20000) { throw 'Source observation timed out.' }
            if (-not $inputClosed -and $inputWrite.IsCompleted) {
                $null = $inputWrite.GetAwaiter().GetResult()
                $process.StandardInput.Close()
                $inputClosed = $true
            }
            foreach ($stream in $streams) {
                if ($stream.Done -or -not $stream.Read.IsCompleted) { continue }
                $count = $stream.Read.GetAwaiter().GetResult()
                if ($count -eq 0) { $stream.Done = $true; continue }
                $stream.Bytes += $count
                if ($stream.Bytes -gt $stream.Limit) { throw 'Source observation output exceeded its bound.' }
                if ($stream.Keep) { $stdout.Write($stream.Buffer, 0, $count) }
                # Stderr is bounded and discarded, never joined to stdout or decoded.
                $stream.Read = $stream.Pipe.ReadAsync($stream.Buffer, 0, $stream.Buffer.Length)
            }
            [Threading.Thread]::Sleep(5)
        }
        if ($process.ExitCode -ne 0) { throw 'Source observation rejected.' }
        $text = [Text.UTF8Encoding]::new($false, $true).GetString($stdout.ToArray())
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
        $stdout.Dispose()
    }
}
