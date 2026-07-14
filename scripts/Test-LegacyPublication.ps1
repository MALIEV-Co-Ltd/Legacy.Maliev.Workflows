[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RepositoryPath,

    [Parameter(Mandatory = $true)]
    [string]$GitHubRepository
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$GitleaksModule = 'github.com/zricethezav/gitleaks/v8@6eaad039603a4de39fddd1cf5f727391efe9974e'

function Stop-PublicationGate {
    param([string]$Message)
    throw [System.InvalidOperationException]::new($Message)
}

function Invoke-RedactedCommand {
    param(
        [string]$Command,
        [string[]]$Arguments,
        [string]$FailureMessage,
        [switch]$ReturnOutput
    )

    $commandInfo = Get-Command $Command -ErrorAction Stop | Select-Object -First 1
    $processArguments = @($Arguments)
    if ($commandInfo.CommandType -eq [System.Management.Automation.CommandTypes]::ExternalScript) {
        $processArguments = @('-NoLogo', '-NoProfile', '-File', $commandInfo.Source) + $processArguments
        $commandInfo = Get-Command 'pwsh' -CommandType Application | Select-Object -First 1
    }

    $startInfo = [System.Diagnostics.ProcessStartInfo]::new($commandInfo.Source)
    $startInfo.WorkingDirectory = (Get-Location).Path
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    foreach ($argument in $processArguments) { [void]$startInfo.ArgumentList.Add($argument) }

    $process = [System.Diagnostics.Process]::Start($startInfo)
    $stdout = $process.StandardOutput.ReadToEndAsync()
    $stderr = $process.StandardError.ReadToEndAsync()
    $process.WaitForExit()
    $output = $stdout.GetAwaiter().GetResult() + $stderr.GetAwaiter().GetResult()
    if ($process.ExitCode -ne 0) {
        Stop-PublicationGate $FailureMessage
    }

    if ($ReturnOutput) { return $output.Trim() }
}

function Invoke-GitRead {
    param([string[]]$Arguments, [string]$FailureMessage = 'Git repository validation failed.')
    Invoke-RedactedCommand -Command 'git' -Arguments (@('-C', $script:ResolvedRepositoryPath) + $Arguments) -FailureMessage $FailureMessage -ReturnOutput
}

try {
    if ($GitHubRepository -cnotmatch '^MALIEV-Co-Ltd/Legacy\.Maliev\.[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?$') {
        Stop-PublicationGate 'Repository name must use the exact MALIEV legacy namespace MALIEV-Co-Ltd/Legacy.Maliev.*.'
    }

    $script:ResolvedRepositoryPath = (Resolve-Path -LiteralPath $RepositoryPath).Path
    if (-not (Test-Path -LiteralPath (Join-Path $script:ResolvedRepositoryPath '.git'))) {
        Stop-PublicationGate 'Candidate path must be a Git repository.'
    }

    $branch = Invoke-GitRead @('branch', '--show-current')
    if ($branch -cne 'main') {
        Stop-PublicationGate 'Publication branch must be main.'
    }

    if ((Invoke-GitRead @('status', '--porcelain=v1', '--untracked-files=all')).Length -ne 0) {
        Stop-PublicationGate 'Candidate working tree must be clean, including untracked files.'
    }

    if ((Invoke-GitRead @('rev-parse', '--is-shallow-repository')) -ne 'false') {
        Stop-PublicationGate 'Shallow repositories cannot prove complete fresh history.'
    }

    $roots = @((Invoke-GitRead @('rev-list', '--max-parents=0', '--all')) -split "`r?`n" | Where-Object { $_ })
    if ($roots.Count -ne 1) {
        Stop-PublicationGate 'Candidate history must contain exactly one fresh root.'
    }

    $provenanceEvidence = @(
        Invoke-GitRead @('remote', '-v')
        Invoke-GitRead @('config', '--local', '--list')
        Invoke-GitRead @('reflog', 'show', '--all')
        Invoke-GitRead @('log', '--all', '--format=%B')
    ) -join "`n"
    if ($provenanceEvidence -match '(?i)maliev-web') {
        Stop-PublicationGate 'Candidate contains evidence of private source history or a maliev-web remote.'
    }

    Invoke-RedactedCommand -Command 'git' -Arguments @('-C', $script:ResolvedRepositoryPath, 'fsck', '--full', '--no-dangling') -FailureMessage 'Git object integrity validation failed.'

    $trackedFiles = @((Invoke-GitRead @('ls-files')) -split "`r?`n" | Where-Object { $_ })
    $prohibitedFilePattern = '(?i)(^|/)(\.env(?:\..*)?|[^/]+\.(?:key|pem|p12|pfx|jks|keystore|crt|cer|der|bak|backup|dump|sql|sqlite|db|zip|7z|rar|tar|tgz|gz))$'
    if ($trackedFiles | Where-Object { $_ -match $prohibitedFilePattern }) {
        Stop-PublicationGate 'Candidate tracks prohibited secret material, certificate, backup, dump, archive, or local environment file.'
    }

    $automationPaths = $trackedFiles | Where-Object { $_ -match '^\.github/workflows/.*\.ya?ml$' -or $_ -match '(?i)(^|/)action\.ya?ml$' }
    foreach ($automationPath in $automationPaths) {
        $workflowSource = Get-Content -LiteralPath (Join-Path $script:ResolvedRepositoryPath $automationPath) -Raw
        $unsafe = $false

        if ($workflowSource -match '(?im)^\s*pull_request_target\s*:|^\s*on\s*:\s*pull_request_target\s*$|^\s*on\s*:\s*\[[^\]]*\bpull_request_target\b') { $unsafe = $true }
        if ($workflowSource -match '(?im)\b(?:kubectl|argocd)\b|\bhelm\s+(?:install|upgrade|template)\b') { $unsafe = $true }

        $actionLines = $workflowSource -split "`r?`n" | Where-Object { $_ -match '(?i)^\s*(?:-\s*)?uses\s*:' }
        foreach ($actionLine in $actionLines) {
            if ($actionLine -notmatch '(?i)uses\s*:\s*\./' -and
                $actionLine -notmatch '(?i)uses\s*:\s*[^\s@]+@[0-9a-f]{40}(?:\s*(?:#.*)?)$') {
                $unsafe = $true
            }
        }

        if ($workflowSource -match '(?im)^\s*pull_request\s*:|^\s*on\s*:\s*pull_request\s*$|^\s*on\s*:\s*\[[^\]]*\bpull_request\b') {
            if ($workflowSource -match '(?im)^\s*permissions\s*:\s*write-all\s*(?:#.*)?$' -or
                $workflowSource -match '(?im)^\s*[A-Za-z0-9_-]+\s*:\s*write\s*(?:#.*)?$' -or
                $workflowSource -match '(?i)\$\{\{\s*secrets\.' -or
                $workflowSource -match '(?im)^\s*(?:GH_TOKEN|GITHUB_TOKEN|GOOGLE_APPLICATION_CREDENTIALS)\s*:' -or
                $workflowSource -match '(?im)persist-credentials\s*:\s*true' -or
                $workflowSource -match '(?im)^\s*environment\s*:') {
                $unsafe = $true
            }
            if ($workflowSource -match '(?im)uses\s*:\s*actions/checkout@' -and
                $workflowSource -notmatch '(?im)persist-credentials\s*:\s*false') {
                $unsafe = $true
            }
        }

        if ($unsafe) {
            Stop-PublicationGate 'Candidate violates the workflow security contract for triggers, permissions, credentials, Action pins, or cluster access.'
        }
    }

    Push-Location $script:ResolvedRepositoryPath
    try {
        Invoke-RedactedCommand -Command 'go' -Arguments @('run', $GitleaksModule, 'dir', '.', '--redact', '--no-banner', '--exit-code', '1') -FailureMessage 'Current-tree secret scan failed; findings were redacted.'
        Invoke-RedactedCommand -Command 'go' -Arguments @('run', $GitleaksModule, 'git', '.', '--redact', '--no-banner', '--exit-code', '1') -FailureMessage 'Complete-history secret scan failed; findings were redacted.'

        $solutions = @(Get-ChildItem -LiteralPath . -File | Where-Object { $_.Extension -in '.sln', '.slnx' })
        if ($solutions.Count -eq 0) {
            Stop-PublicationGate 'Candidate must contain a root .sln or .slnx quality-gate entry point.'
        }

        foreach ($solution in $solutions) {
            $solutionPath = '.\' + $solution.Name
            Invoke-RedactedCommand 'dotnet' @('restore', $solutionPath) 'Dependency restore failed.'
            Invoke-RedactedCommand 'dotnet' @('build', $solutionPath, '--configuration', 'Release', '--no-restore') 'Release build failed.'
            Invoke-RedactedCommand 'dotnet' @('test', $solutionPath, '--configuration', 'Release', '--no-build', '--no-restore') 'Test suite failed.'
            Invoke-RedactedCommand 'dotnet' @('format', $solutionPath, '--verify-no-changes', '--no-restore') 'Formatting verification failed.'
            $auditOutput = Invoke-RedactedCommand 'dotnet' @('list', $solutionPath, 'package', '--vulnerable', '--include-transitive', '--no-restore') 'Dependency vulnerability audit failed.' -ReturnOutput
            if ($auditOutput -match '(?im)has the following vulnerable packages|^\s*>\s+\S+') {
                Stop-PublicationGate 'Dependency vulnerability audit found prohibited packages.'
            }
        }

        $dockerfiles = @(Get-ChildItem -LiteralPath . -File -Recurse -Filter 'Dockerfile')
        foreach ($dockerfile in $dockerfiles) {
            $tag = 'legacy-publication-scan:' + ([guid]::NewGuid().ToString('N'))
            try {
                Invoke-RedactedCommand 'docker' @('build', '--file', $dockerfile.FullName, '--tag', $tag, $dockerfile.DirectoryName) 'Container build failed.'
                Invoke-RedactedCommand 'trivy' @('image', '--exit-code', '1', '--severity', 'HIGH,CRITICAL', '--ignore-unfixed', '--no-progress', $tag) 'Container vulnerability scan failed.'
            } finally {
                & docker image rm --force $tag *> $null
            }
        }
    } finally {
        Pop-Location
    }

    Write-Output 'Publication gate passed: repository history, source, workflows, secrets, and quality checks are safe.'
    exit 0
} catch {
    [Console]::Error.WriteLine('[publication-gate] FAILED: ' + $_.Exception.Message)
    exit 1
}
