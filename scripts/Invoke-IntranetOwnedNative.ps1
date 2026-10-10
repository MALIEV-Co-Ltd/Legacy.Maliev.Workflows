# Producer-owned adapter for the existing reviewed Invoke-RedactedProcess API.
# Import that exact-pinned producer definition separately; never replay credentials.
function Invoke-IntranetOwnedNativeCore {
    param([string]$Command,[string[]]$Arguments,[string]$Step)
    if($Command -cne 'kubectl' -or $Arguments.Count -lt 3 -or $Arguments[0] -cne '-n' -or $Arguments[1] -cne 'maliev-legacy' -or $Step -cnotmatch '^[A-Z_]{1,40}$'){throw 'Intranet native request rejected.'}
    try {
        $stdout=Invoke-RedactedProcess $Command $Arguments 'Intranet native boundary failed; output withheld.' -ReturnOutput -TimeoutSeconds 120
        if($null -eq $stdout){$stdout=''}
        return @{exitCode=0;stdout=[string]$stdout}
    } catch {
        $code=$_.Exception.Data['ExitCode']
        if($code -isnot [int] -or $code -lt 1){throw [InvalidOperationException]::new('Intranet native ownership or receipt failed.')}
        return @{exitCode=$code;stdout=''}
    }
}
function Invoke-IntranetOwnedNative {
    param([string]$Command,[string[]]$Arguments,[string]$Step)
    throw 'Intranet native source is not approved for execution.'
}
