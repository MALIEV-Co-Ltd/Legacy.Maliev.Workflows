[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RepositoryPath,

    [Parameter(Mandatory = $true)]
    [string]$GitHubRepository,

    [ValidateRange(1, 3600)]
    [int]$WaitTimeoutSeconds = 900,

    [ValidateRange(0, 60)]
    [int]$PollIntervalSeconds = 10
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Stop-Publication {
    param([string]$Message)
    throw [System.InvalidOperationException]::new($Message)
}

function Invoke-RedactedProcess {
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
    if ($process.ExitCode -ne 0) { Stop-Publication $FailureMessage }
    if ($ReturnOutput) { return $output.Trim() }
}

function Invoke-GhApiWrite {
    param([string]$Endpoint, [string]$Method, [hashtable]$Payload, [string]$FailureMessage)

    $payloadPath = Join-Path ([System.IO.Path]::GetTempPath()) ('legacy-publication-' + [guid]::NewGuid().ToString('N') + '.json')
    try {
        [System.IO.File]::WriteAllText($payloadPath, ($Payload | ConvertTo-Json -Depth 10 -Compress))
        Invoke-RedactedProcess 'gh' @('api', $Endpoint, '--method', $Method, '--input', $payloadPath) $FailureMessage
    } finally {
        Remove-Item -LiteralPath $payloadPath -Force -ErrorAction SilentlyContinue
    }
}

try {
    $resolvedRepositoryPath = (Resolve-Path -LiteralPath $RepositoryPath).Path
    $gateScript = Join-Path $PSScriptRoot 'Test-LegacyPublication.ps1'

    Push-Location $resolvedRepositoryPath
    try {
        Invoke-RedactedProcess $gateScript @('-RepositoryPath', $resolvedRepositoryPath, '-GitHubRepository', $GitHubRepository) 'Local publication gate failed; GitHub was not mutated.'
        $headSha = Invoke-RedactedProcess 'git' @('-C', $resolvedRepositoryPath, 'rev-parse', 'HEAD') 'Unable to resolve the candidate commit.' -ReturnOutput

        Invoke-RedactedProcess 'gh' @('repo', 'create', $GitHubRepository, '--public', '--source', $resolvedRepositoryPath, '--remote', 'origin', '--description', 'Migrated MALIEV legacy service with fresh public history') 'GitHub repository creation failed.'
        Invoke-RedactedProcess 'git' @('-C', $resolvedRepositoryPath, 'push', '--set-upstream', 'origin', 'main') 'Initial main push failed.'

        $deadline = [DateTimeOffset]::UtcNow.AddSeconds($WaitTimeoutSeconds)
        $workflowRun = $null
        while ([DateTimeOffset]::UtcNow -lt $deadline -and $null -eq $workflowRun) {
            $runJson = Invoke-RedactedProcess 'gh' @('run', 'list', '--repo', $GitHubRepository, '--workflow', 'dotnet-validate.yml', '--commit', $headSha, '--limit', '20', '--json', 'databaseId,status,conclusion,name') 'Unable to query validation runs.' -ReturnOutput
            $runs = @($runJson | ConvertFrom-Json)
            $workflowRun = $runs | Where-Object { $_.name -ceq 'validate' } | Select-Object -First 1
            if ($null -eq $workflowRun -and $PollIntervalSeconds -gt 0) { Start-Sleep -Seconds $PollIntervalSeconds }
        }
        if ($null -eq $workflowRun) { Stop-Publication 'Timed out waiting for required check validate / validate.' }

        Invoke-RedactedProcess 'gh' @('run', 'watch', [string]$workflowRun.databaseId, '--repo', $GitHubRepository, '--exit-status') 'Required validation workflow failed.'
        $runReadback = Invoke-RedactedProcess 'gh' @('run', 'view', [string]$workflowRun.databaseId, '--repo', $GitHubRepository, '--json', 'jobs') 'Unable to read validation job state.' -ReturnOutput | ConvertFrom-Json
        $validateJob = @($runReadback.jobs) | Where-Object { $_.name -ceq 'validate' } | Select-Object -First 1
        if ($null -eq $validateJob -or $validateJob.status -cne 'completed' -or $validateJob.conclusion -cne 'success') {
            Stop-Publication 'Required check validate / validate did not complete successfully.'
        }

        Invoke-RedactedProcess 'gh' @(
            'api', "repos/$GitHubRepository", '--method', 'PATCH',
            '--field', 'visibility=public', '--field', 'default_branch=main',
            '--field', 'allow_merge_commit=false', '--field', 'allow_squash_merge=true',
            '--field', 'allow_rebase_merge=true', '--field', 'delete_branch_on_merge=true',
            '--field', 'security_and_analysis[private_vulnerability_reporting][status]=enabled'
        ) 'Repository security configuration failed.'

        $protectionPayload = @{
            required_status_checks = @{ strict = $true; contexts = @('validate / validate') }
            enforce_admins = $true
            required_pull_request_reviews = @{ dismiss_stale_reviews = $true; required_approving_review_count = 1 }
            restrictions = $null
            required_linear_history = $true
            allow_force_pushes = $false
            allow_deletions = $false
            required_conversation_resolution = $true
        }
        Invoke-GhApiWrite "repos/$GitHubRepository/branches/main/protection" 'PUT' $protectionPayload 'Branch protection configuration failed.'

        $environmentPayload = @{
            wait_timer = 0
            prevent_self_review = $true
            reviewers = @()
            deployment_branch_policy = @{ protected_branches = $true; custom_branch_policies = $false }
        }
        Invoke-GhApiWrite "repos/$GitHubRepository/environments/production" 'PUT' $environmentPayload 'Protected deployment environment configuration failed.'

        $repositoryReadback = Invoke-RedactedProcess 'gh' @('api', "repos/$GitHubRepository") 'Repository settings readback failed.' -ReturnOutput | ConvertFrom-Json
        $protectionReadback = Invoke-RedactedProcess 'gh' @('api', "repos/$GitHubRepository/branches/main/protection") 'Branch protection readback failed.' -ReturnOutput | ConvertFrom-Json
        $environmentReadback = Invoke-RedactedProcess 'gh' @('api', "repos/$GitHubRepository/environments/production") 'Environment readback failed.' -ReturnOutput | ConvertFrom-Json

        $requiredContexts = @($protectionReadback.required_status_checks.contexts)
        $readbackMatches =
            $repositoryReadback.visibility -ceq 'public' -and
            $repositoryReadback.default_branch -ceq 'main' -and
            $repositoryReadback.security_and_analysis.private_vulnerability_reporting.status -ceq 'enabled' -and
            $protectionReadback.required_status_checks.strict -eq $true -and
            $requiredContexts.Count -eq 1 -and $requiredContexts[0] -ceq 'validate / validate' -and
            $protectionReadback.enforce_admins.enabled -eq $true -and
            $protectionReadback.required_pull_request_reviews.dismiss_stale_reviews -eq $true -and
            $protectionReadback.required_pull_request_reviews.required_approving_review_count -eq 1 -and
            $protectionReadback.required_linear_history.enabled -eq $true -and
            $protectionReadback.required_conversation_resolution.enabled -eq $true -and
            $protectionReadback.allow_force_pushes.enabled -eq $false -and
            $protectionReadback.allow_deletions.enabled -eq $false -and
            $environmentReadback.name -ceq 'production' -and
            $environmentReadback.deployment_branch_policy.protected_branches -eq $true -and
            $environmentReadback.deployment_branch_policy.custom_branch_policies -eq $false

        if (-not $readbackMatches) { Stop-Publication 'GitHub readback mismatch; publication is incomplete and must not be treated as protected.' }
    } finally {
        Pop-Location
    }

    Write-Output 'Publication and protection verified: public main requires validate / validate and production is protected.'
    exit 0
} catch {
    [Console]::Error.WriteLine('[legacy-publisher] FAILED: ' + $_.Exception.Message)
    exit 1
}
