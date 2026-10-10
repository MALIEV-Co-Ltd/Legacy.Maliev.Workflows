param([string]$RepositoryRoot = (Split-Path $PSScriptRoot), [string]$PublisherPath)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if (-not $PublisherPath) { $PublisherPath = Join-Path $RepositoryRoot 'scripts/Publish-LegacyRepository.ps1' }
$tokens = $null; $errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($PublisherPath, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'Publisher syntax invalid.' }
foreach ($name in @('Complete-RedactedProcessCleanup','Invoke-RedactedProcess')) {
$function = $ast.Find({ param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name }, $true)
if ($null -eq $function -and $name -eq 'Complete-RedactedProcessCleanup') { continue } # Original causal baseline lacks cleanup helper.
if ($null -eq $function) { throw 'Actual publisher command boundary unavailable.' }
Invoke-Expression $function.Extent.Text # Never execute publisher orchestration or provider tools.
}
$script:NativeCommandOwnershipSource = Join-Path $RepositoryRoot 'scripts/OwnedNativeCommandProcess.cs'
$hostExecutable = (Get-Command pwsh -CommandType Application | Select-Object -First 1).Source
$privateWarning = 'SYNTHETIC_PROVIDER_PRIVATE_WARNING'
$digest = 'sha256:' + ('a' * 64)
$json = '{"image_summary":{"digest":"' + $digest + '","note":"ไทย"}}'
$passed = 0
function FixtureArguments([string]$Output, [int]$Code) {
    $encodedOutput = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Output))
    $codeText = '[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); [Console]::Error.WriteLine("' + $privateWarning + '" + ("x" * 512)); [Console]::Error.WriteLine("SYNTHETIC_SECOND_WARNING"); [Console]::Out.Write([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String("' + $encodedOutput + '"))); exit ' + $Code
    return @('-NoLogo','-NoProfile','-NonInteractive','-EncodedCommand',[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($codeText)))
}
function Check([bool]$Condition, [string]$Message) { if (-not $Condition) { throw $Message } }
$value = @(Invoke-RedactedProcess $hostExecutable (FixtureArguments $json 0) 'offline JSON' -ReturnOutput 2>&1)
Check ($value.Count -eq 1 -and $value[0] -is [string] -and $value[0] -ceq $json) 'Actual successful native warning contaminated exact JSON stdout.'
Check (($value[0] | ConvertFrom-Json).image_summary.digest -ceq $digest) 'Successful native JSON cannot be parsed.'
$passed++
$caught = $null
try { Invoke-RedactedProcess $hostExecutable (FixtureArguments $json 17) 'offline safe step' -ReturnOutput | Out-Null } catch { $caught = $_.Exception }
Check ($null -ne $caught -and $caught.Data['ExitCode'] -eq 17 -and $caught.Data['Step'] -ceq 'offline safe step') ('Actual nonzero native exit or safe step metadata lost: ' + ($caught.Data | ConvertTo-Json -Compress))
Check ($caught.Data.Count -eq 2) 'Failure metadata exposes fields beyond safe step and exit code.'
Check (($caught.ToString() + ($caught.Data | ConvertTo-Json -Compress)) -notmatch $privateWarning) 'Provider diagnostics leaked through failure metadata.'
$passed++
$value = @(Invoke-RedactedProcess $hostExecutable (FixtureArguments $json 19) 'offline optional failure' -ReturnOutput -AllowFailure 2>&1)
Check ($value.Count -eq 0 -or ($value.Count -eq 1 -and $null -eq $value[0])) 'Optional failure returned provider output.'
$passed++
foreach ($malformed in @('malformed stdout','')) {
    $stdout = Invoke-RedactedProcess $hostExecutable (FixtureArguments $malformed 0) 'offline malformed JSON' -ReturnOutput
    Check ([string]$stdout -ceq $malformed) 'Malformed or empty stdout was replaced with stderr.'
    $accepted = $false
    try { $parsed = $stdout | ConvertFrom-Json; $accepted = $null -ne $parsed -and $null -ne $parsed.image_summary.digest } catch { }
    Check (-not $accepted) 'Caller accepted malformed or empty stdout as registry JSON.'
    $passed++
}
$value = @(Invoke-RedactedProcess $hostExecutable (FixtureArguments $json 0) 'offline no output' 2>&1)
Check ($value.Count -eq 0) 'Command without ReturnOutput emitted private diagnostics or JSON.'
$passed++
$value = Invoke-RedactedProcess $hostExecutable (FixtureArguments ("`r`n  " + $json + "  `n") 0) 'offline whitespace' -ReturnOutput
Check ($value -ceq $json) 'Existing stdout trimming or Unicode semantics changed.'
$passed++
$caught = $null
try { Invoke-RedactedProcess $hostExecutable (FixtureArguments 'malformed stdout' 23) 'offline malformed nonzero' -ReturnOutput | Out-Null } catch { $caught = $_.Exception }
Check ($null -ne $caught -and $caught.Data['ExitCode'] -eq 23 -and $caught.Message -ceq 'offline malformed nonzero') 'Nonzero malformed command did not preserve exact safe failure.'
$passed++
$caught = $null
try { Invoke-RedactedProcess (Join-Path $RepositoryRoot 'synthetic-private-missing-executable') @('SYNTHETIC_PRIVATE_ARGV') 'offline start failure' -ReturnOutput | Out-Null } catch { $caught = $_.Exception }
Check ($null -ne $caught -and $caught.Message -ceq 'offline start failure' -and $caught.Data.Count -eq 1 -and $caught.Data['Step'] -ceq 'offline start failure') 'Startup failure exported command path or argv.'
$passed++
$caught = $null
try { Invoke-RedactedProcess $hostExecutable @('-NoProfile','-Command','Start-Sleep -Seconds 30') 'offline timeout' -TimeoutSeconds 1 | Out-Null } catch { $caught = $_.Exception }
Check ($null -ne $caught -and $caught.Message -ceq 'offline timeout') 'Actual native command deadline failed to reject.'
$passed++
$caught = $null
$overflowCode = '[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); [Console]::Out.Write("x" * 1048577); exit 0'
$overflowArguments = @('-NoLogo','-NoProfile','-NonInteractive','-EncodedCommand',[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($overflowCode)))
try { Invoke-RedactedProcess $hostExecutable $overflowArguments 'offline overflow' -ReturnOutput | Out-Null } catch { $caught = $_.Exception }
Check ($null -ne $caught -and $caught.Message -ceq 'offline overflow') 'Actual native output bound failed to reject.'
$passed++
Check ($null -eq (Get-Variable NativeCommandUnresolvedCustody -Scope Script -ErrorAction SilentlyContinue)) 'Owned actual fixture command remained unsettled.'

# Deterministic partial Start uncertainty: no child process is created.
foreach ($knownExited in @($false,$true)) {
$uncertain = [pscustomobject]@{ Disposed = $false; KnownExited = $knownExited }
$uncertain | Add-Member ScriptProperty HasExited { if (-not $this.KnownExited) { throw 'Synthetic allocation state unavailable' }; return $true }
$uncertain | Add-Member ScriptMethod Dispose { $this.Disposed = $true }
$cancel = [Threading.CancellationTokenSource]::new()
$capture = [IO.MemoryStream]::new()
$custody = $null
try {
    $state = Complete-RedactedProcessCleanup $uncertain $null $true $null ([Threading.Tasks.Task[]]::new(2)) $cancel ([object[]]::new(2)) ([object[]]::new(2)) @([byte[]]::new(8),[byte[]]::new(8)) $capture
    Check ($state.Exited -eq $knownExited -and -not $state.ProcessClosed -and -not $uncertain.Disposed) 'Unknown partial Start discarded its original owner.'
    $custody = $script:NativeCommandUnresolvedCustody[$script:NativeCommandUnresolvedCustody.Count-1]
    Check ([object]::ReferenceEquals($custody.Process,$uncertain) -and $custody.StartAttempted -and $null -eq $custody.StartResult -and -not $custody.ExpiryMeansSettled) 'Unknown partial Start lost actual custody.'
    $passed++
} finally {
    $uncertain.KnownExited = $true; $uncertain.Dispose(); $cancel.Dispose(); $capture.Dispose()
    if ($null -ne $custody) { [void]$script:NativeCommandUnresolvedCustody.Remove($custody) }
}

}

Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
public sealed class CancellationIgnoringFixtureStream : Stream {
    private readonly TaskCompletionSource<int> pending = new(TaskCreationOptions.RunContinuationsAsynchronously);
    public int Disposals { get; private set; }
    public void Complete() => pending.TrySetResult(0);
    public override Task<int> ReadAsync(byte[] buffer, int offset, int count, CancellationToken cancellationToken) => pending.Task;
    protected override void Dispose(bool disposing) { if (disposing) Disposals++; base.Dispose(disposing); }
    public override bool CanRead => true;
    public override bool CanSeek => false;
    public override bool CanWrite => false;
    public override long Length => throw new NotSupportedException();
    public override long Position { get => throw new NotSupportedException(); set => throw new NotSupportedException(); }
    public override void Flush() { }
    public override int Read(byte[] buffer, int offset, int count) => throw new NotSupportedException();
    public override long Seek(long offset, SeekOrigin origin) => throw new NotSupportedException();
    public override void SetLength(long value) => throw new NotSupportedException();
    public override void Write(byte[] buffer, int offset, int count) => throw new NotSupportedException();
}
'@
foreach ($oneCompleted in @($false,$true)) {
    $cancel = [Threading.CancellationTokenSource]::new()
    $streams = @([CancellationIgnoringFixtureStream]::new(),[CancellationIgnoringFixtureStream]::new())
    $readers = @([IO.StreamReader]::new($streams[0]),[IO.StreamReader]::new($streams[1]))
    $buffers = @([byte[]]::new(8),[byte[]]::new(8))
    $reads = @($streams[0].ReadAsync($buffers[0],0,8,$cancel.Token),$streams[1].ReadAsync($buffers[1],0,8,$cancel.Token))
    $process = [pscustomobject]@{ HasExited = $true; Disposed = $false }
    $process | Add-Member ScriptMethod Dispose { $this.Disposed = $true }
    $capture = [IO.MemoryStream]::new(); $custody = $null
    if ($oneCompleted) { $streams[0].Complete() }
    try {
        $state = Complete-RedactedProcessCleanup $process $null $true $true $reads $cancel $readers $streams $buffers $capture
        Check (-not $state.ReadsSettled -and -not $state.ProcessClosed -and -not $state.CtsClosed -and $streams[0].Disposals -eq 0 -and $streams[1].Disposals -eq 0) 'Pending actual read was disposed before settlement.'
        $custody = $script:NativeCommandUnresolvedCustody[$script:NativeCommandUnresolvedCustody.Count-1]
        Check ([object]::ReferenceEquals($custody.ReaderTasks[1],$reads[1]) -and [object]::ReferenceEquals($custody.Readers[0],$readers[0]) -and [object]::ReferenceEquals($custody.Buffers[1],$buffers[1]) -and [object]::ReferenceEquals($custody.Cancellation,$cancel)) 'Pending actual read/task/buffer/reader/CTS references lost.'
        $passed++
    } finally {
        $streams[0].Complete(); $streams[1].Complete()
        [Threading.Tasks.Task]::WhenAll([Threading.Tasks.Task[]]$reads).WaitAsync([TimeSpan]::FromSeconds(1)).GetAwaiter().GetResult()
        $readers[0].Dispose(); $readers[1].Dispose(); $cancel.Dispose(); $process.Dispose(); $capture.Dispose()
        if ($null -ne $custody) { [void]$script:NativeCommandUnresolvedCustody.Remove($custody) }
    }
}
Check ($script:NativeCommandUnresolvedCustody.Count -eq 0) 'Synthetic pending reader control custody remained live.'
Write-Output ('redacted-native-output-controls:' + $passed + ' passed')
