[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RepositoryPath,

    [Parameter(Mandatory = $true)]
    [string]$GitHubRepository,

    [string]$PrivateSourceRepositoryPath,

    [switch]$IndependentRepository,

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
        [switch]$ReturnOutput,
        [switch]$AllowFailure
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
        if ($AllowFailure) { return $null }
        Stop-Publication $FailureMessage
    }
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

    if ($IndependentRepository) {
        if ($GitHubRepository -cne 'MALIEV-Co-Ltd/Legacy.Maliev.Workflows') {
            Stop-Publication 'Only MALIEV-Co-Ltd/Legacy.Maliev.Workflows may use independent mode.'
        }
        if (-not [string]::IsNullOrWhiteSpace($PrivateSourceRepositoryPath)) {
            Stop-Publication 'Independent mode cannot be combined with a private source repository path.'
        }
        $provenanceAudit = 'Publication provenance: independent shared Workflows repository; private-source ODB comparison is not applicable.'
    } elseif ([string]::IsNullOrWhiteSpace($PrivateSourceRepositoryPath)) {
        Stop-Publication 'A private source repository path is required for extracted service publication.'
    } else {
        $provenanceAudit = 'Publication provenance: candidate commit OIDs were compared with the supplied private-source ODB; unavailable object databases cannot be proven.'
    }

    Push-Location $resolvedRepositoryPath
    try {
        $gateArguments = @('-RepositoryPath', $resolvedRepositoryPath, '-GitHubRepository', $GitHubRepository)
        if ($IndependentRepository) { $gateArguments += '-IndependentRepository' }
        else { $gateArguments += @('-PrivateSourceRepositoryPath', $PrivateSourceRepositoryPath) }
        Invoke-RedactedProcess $gateScript $gateArguments 'Local publication gate failed; GitHub was not mutated.'
        $headSha = Invoke-RedactedProcess 'git' @('-C', $resolvedRepositoryPath, 'rev-parse', 'HEAD') 'Unable to resolve the candidate commit.' -ReturnOutput
        $rootSha = Invoke-RedactedProcess 'git' @('-C', $resolvedRepositoryPath, 'rev-list', '--max-parents=0', 'HEAD') 'Unable to resolve the fresh root commit.' -ReturnOutput
        $publicationBranch = "publication/$headSha"

        $repositoryStateJson = Invoke-RedactedProcess 'gh' @('repo', 'view', $GitHubRepository, '--json', 'isEmpty,visibility,defaultBranchRef') 'Unable to inspect the target GitHub repository.' -ReturnOutput -AllowFailure
        if ([string]::IsNullOrWhiteSpace($repositoryStateJson)) {
            Invoke-RedactedProcess 'gh' @('repo', 'create', $GitHubRepository, '--public', '--source', $resolvedRepositoryPath, '--remote', 'origin', '--description', 'Migrated MALIEV legacy service with fresh public history') 'GitHub repository creation failed.'
        } else {
            $repositoryState = $repositoryStateJson | ConvertFrom-Json
            if ($repositoryState.isEmpty -ne $true) {
                Stop-Publication 'Target GitHub repository is unexpectedly non-empty; refusing to alter existing history.'
            }
            if ([string]$repositoryState.visibility -cne 'PUBLIC') {
                Stop-Publication 'Pre-created target GitHub repository must already be public.'
            }
        }

        $originUrl = Invoke-RedactedProcess 'git' @('-C', $resolvedRepositoryPath, 'config', '--get', 'remote.origin.url') 'Unable to inspect the origin remote.' -ReturnOutput -AllowFailure
        $expectedOriginUrls = @(
            "https://github.com/$GitHubRepository",
            "https://github.com/$GitHubRepository.git",
            "git@github.com:$GitHubRepository.git"
        )
        if ([string]::IsNullOrWhiteSpace($originUrl)) {
            Invoke-RedactedProcess 'git' @('-C', $resolvedRepositoryPath, 'remote', 'add', 'origin', "https://github.com/$GitHubRepository.git") 'Unable to configure the target origin remote.'
        } elseif ($originUrl -cnotin $expectedOriginUrls) {
            Stop-Publication 'Existing origin does not point to the requested GitHub repository.'
        }

        Invoke-RedactedProcess 'git' @('-C', $resolvedRepositoryPath, 'push', 'origin', "${rootSha}:refs/heads/main") 'Initial root-only main push failed.'
        Invoke-RedactedProcess 'git' @('-C', $resolvedRepositoryPath, 'push', 'origin', "${headSha}:refs/heads/$publicationBranch") 'Candidate publication branch push failed.'

        $prListArguments = @('pr', 'list', '--repo', $GitHubRepository, '--base', 'main', '--head', $publicationBranch, '--state', 'open', '--json', 'number,headRefOid,baseRefName,headRefName,state')
        $pullRequests = @(Invoke-RedactedProcess 'gh' $prListArguments 'Unable to identify the publication pull request.' -ReturnOutput | ConvertFrom-Json)
        if ($pullRequests.Count -eq 0) {
            $repositoryName = $GitHubRepository.Split('/')[-1]
            Invoke-RedactedProcess 'gh' @(
                'pr', 'create', '--repo', $GitHubRepository, '--base', 'main', '--head', $publicationBranch,
                '--title', "Publish $repositoryName at $headSha",
                '--body', 'Bootstrap publication through the required pull-request validation boundary.'
            ) 'Unable to create the publication pull request.'
            $pullRequests = @(Invoke-RedactedProcess 'gh' $prListArguments 'Unable to read back the publication pull request.' -ReturnOutput | ConvertFrom-Json)
        }
        if ($pullRequests.Count -ne 1) { Stop-Publication 'Expected exactly one open publication pull request for the candidate branch.' }
        $pullRequest = $pullRequests[0]
        if ($pullRequest.baseRefName -cne 'main' -or
            $pullRequest.headRefName -cne $publicationBranch -or
            $pullRequest.headRefOid -cne $headSha -or
            $pullRequest.state -cne 'OPEN') {
            Stop-Publication 'Publication pull request identity or exact head SHA did not match the candidate.'
        }

        $deadline = [DateTimeOffset]::UtcNow.AddSeconds($WaitTimeoutSeconds)
        $workflowRun = $null
        while ([DateTimeOffset]::UtcNow -lt $deadline -and $null -eq $workflowRun) {
            $runJson = Invoke-RedactedProcess 'gh' @('run', 'list', '--repo', $GitHubRepository, '--workflow', 'validate.yml', '--commit', $headSha, '--event', 'pull_request', '--limit', '20', '--json', 'databaseId,status,conclusion,name,headSha,event') 'Unable to query validation runs.' -ReturnOutput
            $runs = @($runJson | ConvertFrom-Json)
            $workflowRun = $runs | Where-Object {
                $_.name -ceq 'validate' -and $_.headSha -ceq $headSha -and $_.event -ceq 'pull_request'
            } | Select-Object -First 1
            if ($null -eq $workflowRun -and $PollIntervalSeconds -gt 0) { Start-Sleep -Seconds $PollIntervalSeconds }
        }
        if ($null -eq $workflowRun) { Stop-Publication 'Timed out waiting for required check validate / validate.' }

        Invoke-RedactedProcess 'gh' @('run', 'watch', [string]$workflowRun.databaseId, '--repo', $GitHubRepository, '--exit-status') 'Required validation workflow failed.'
        $runReadback = Invoke-RedactedProcess 'gh' @('run', 'view', [string]$workflowRun.databaseId, '--repo', $GitHubRepository, '--json', 'jobs') 'Unable to read validation job state.' -ReturnOutput | ConvertFrom-Json
        $validateJob = @($runReadback.jobs) | Where-Object { $_.name -ceq 'validate / validate' } | Select-Object -First 1
        if ($null -eq $validateJob -or $validateJob.status -cne 'completed' -or $validateJob.conclusion -cne 'success') {
            Stop-Publication 'Required check validate / validate did not complete successfully.'
        }

        Invoke-RedactedProcess 'gh' @('pr', 'merge', [string]$pullRequest.number, '--repo', $GitHubRepository, '--squash', '--delete-branch', '--match-head-commit', $headSha) 'Unable to squash-merge the validated publication pull request.'
        $mergedMainSha = Invoke-RedactedProcess 'gh' @('api', "repos/$GitHubRepository/commits/main", '--jq', '.sha') 'Unable to read back merged main SHA.' -ReturnOutput
        if ($mergedMainSha -notmatch '^[0-9a-f]{40}$') { Stop-Publication 'Merged main readback did not return a complete commit SHA.' }

        Invoke-RedactedProcess 'gh' @('api', "repos/$GitHubRepository/private-vulnerability-reporting", '--method', 'PUT') 'Private vulnerability reporting configuration failed.'

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
        $vulnerabilityReadback = Invoke-RedactedProcess 'gh' @('api', "repos/$GitHubRepository/private-vulnerability-reporting") 'Private vulnerability reporting readback failed.' -ReturnOutput | ConvertFrom-Json
        $protectionReadback = Invoke-RedactedProcess 'gh' @('api', "repos/$GitHubRepository/branches/main/protection") 'Branch protection readback failed.' -ReturnOutput | ConvertFrom-Json
        $environmentReadback = Invoke-RedactedProcess 'gh' @('api', "repos/$GitHubRepository/environments/production") 'Environment readback failed.' -ReturnOutput | ConvertFrom-Json

        $requiredContexts = @($protectionReadback.required_status_checks.contexts)
        $environmentRules = @($environmentReadback.protection_rules)
        $waitTimerRules = @($environmentRules | Where-Object { $_.type -ceq 'wait_timer' })
        $reviewerRules = @($environmentRules | Where-Object { $_.type -ceq 'required_reviewers' })
        $branchPolicyRules = @($environmentRules | Where-Object { $_.type -ceq 'branch_policy' })
        $readbackMatches =
            $repositoryReadback.visibility -ceq 'public' -and
            $repositoryReadback.default_branch -ceq 'main' -and
            $vulnerabilityReadback.enabled -eq $true -and
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
            $environmentRules.Count -eq 3 -and
            $waitTimerRules.Count -eq 1 -and $waitTimerRules[0].wait_timer -eq 0 -and
            $reviewerRules.Count -eq 1 -and $reviewerRules[0].prevent_self_review -eq $true -and
            @($reviewerRules[0].reviewers).Count -eq 0 -and
            $branchPolicyRules.Count -eq 1 -and
            $environmentReadback.deployment_branch_policy.protected_branches -eq $true -and
            $environmentReadback.deployment_branch_policy.custom_branch_policies -eq $false

        if (-not $readbackMatches) { Stop-Publication 'GitHub readback mismatch; publication is incomplete and must not be treated as protected.' }
    } finally {
        Pop-Location
    }

    Write-Output $provenanceAudit
    Write-Output "Publication and protection verified at merged main $mergedMainSha`: public main requires validate / validate and production is protected."
    exit 0
} catch {
    [Console]::Error.WriteLine('[legacy-publisher] FAILED: ' + $_.Exception.Message)
    exit 1
}
