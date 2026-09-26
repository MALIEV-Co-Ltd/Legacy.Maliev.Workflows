[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string] $SourceRepository,
    [string] $SourceRef = 'origin/main',
    [string] $LegacyRoot = (Split-Path -Parent $PSScriptRoot | Split-Path -Parent),
    [string] $MappingPath = (Join-Path $PSScriptRoot '..\migration\source-path-owners.json'),
    [string] $OutputPath = (Join-Path $PSScriptRoot '..\migration\source-commit-ledger.json')
)

$ErrorActionPreference = 'Stop'

function Invoke-SourceGit {
    param([Parameter(ValueFromRemainingArguments)] [string[]] $Arguments)
    $result = & git -C $SourceRepository @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Read-only source Git command failed: git $($Arguments -join ' ')`n$result" }
    return @($result)
}

$mapping = Get-Content -LiteralPath $MappingPath -Raw | ConvertFrom-Json -Depth 20
$checkpoint = ([string](Invoke-SourceGit rev-parse $SourceRef | Select-Object -First 1)).Trim()
if ($checkpoint -notmatch '^[0-9a-f]{40}$') { throw "Source ref did not resolve to a full commit SHA: $checkpoint" }
$liveMain = ([string](Invoke-SourceGit ls-remote origin refs/heads/main | Select-Object -First 1)).Trim()
$liveMatch = [regex]::Match($liveMain, '^([0-9a-f]{40})\s+refs/heads/main$')
if (-not $liveMatch.Success -or $liveMatch.Groups[1].Value -cne $checkpoint) {
    throw 'The local source ref does not match live origin/main; do not publish a stale ledger.'
}

$legacyTargets = [ordered]@{}
$ownerNames = @(
    @($mapping.rules.owners | ForEach-Object { $_ }) + @($mapping.architecturalTargets) |
        Sort-Object -Unique
)
foreach ($owner in $ownerNames) {
    $repositoryPath = Join-Path $LegacyRoot $owner
    if (-not (Test-Path -LiteralPath (Join-Path $repositoryPath '.git'))) { throw "Canonical Legacy repository was not found: $repositoryPath" }
    $remoteMainResult = & git -C $repositoryPath ls-remote origin refs/heads/main 2>&1
    $remoteGitExit = $LASTEXITCODE
    $remoteMain = ([string]($remoteMainResult | Select-Object -First 1)).Trim()
    if ($remoteGitExit -ne 0 -or $remoteMain -notmatch '^([0-9a-f]{40})\s+refs/heads/main$') {
        throw "Could not resolve $owner live origin/main to a full commit SHA."
    }
    $targetSha = $Matches[1]
    $legacyTargets[$owner] = [ordered]@{
        mainSha = $targetSha
        evidence = "https://github.com/MALIEV-Co-Ltd/$owner/commit/$targetSha"
    }
}

$commits = Invoke-SourceGit rev-list --reverse $checkpoint
$ordinal = 0
$mergeCount = 0
$nonMergeCount = 0
$records = foreach ($commitValue in $commits) {
    $ordinal++
    $commit = $commitValue.Trim()
    $metadata = ([string](Invoke-SourceGit show -s '--format=%aI%x09%P%x09%s' $commit | Select-Object -First 1)) -split "`t", 3
    $parents = @($metadata[1] -split ' ' | Where-Object { $_ })
    $isMerge = $parents.Count -gt 1
    if ($isMerge) { $mergeCount++ } else { $nonMergeCount++ }
    # A merge's first-parent tree delta includes both merged work and conflict resolution.
    # Classifying only its individual parents would miss changes made in the merge itself.
    $paths = if ($isMerge) {
        @(Invoke-SourceGit diff --name-only $parents[0] $commit | Where-Object { $_ })
    } else {
        @(Invoke-SourceGit diff-tree --root --no-commit-id --name-only -r $commit | Where-Object { $_ })
    }
    $classifications = foreach ($path in $paths) {
        $matches = @($mapping.rules | Where-Object { $path -match $_.pattern })
        if ($matches.Count -ne 1) { throw "Path '$path' in $commit matched $($matches.Count) ownership rules; expected exactly one." }
        $rule = $matches[0]
        [ordered]@{
            path = $path
            owners = @($rule.owners)
            disposition = if ($rule.disposition) { $rule.disposition } else { 'migration-required' }
            decision = if ($rule.decision) { $rule.decision } else { $null }
        }
    }

    [ordered]@{
        ordinal = $ordinal
        commit = $commit
        authoredAt = $metadata[0]
        parents = $parents
        isMerge = $isMerge
        subject = $metadata[2]
        sourceEvidence = "https://github.com/$($mapping.sourceRepository)/commit/$commit"
        classifications = @($classifications)
    }
}

$ledger = [ordered]@{
    schemaVersion = 2
    generatedAt = [DateTimeOffset]::UtcNow.ToString('O')
    sourceRepository = $mapping.sourceRepository
    sourceCheckpoint = $checkpoint
    legacyTargets = $legacyTargets
    commitCount = @($records).Count
    nonMergeCommitCount = $nonMergeCount
    mergeCommitCount = $mergeCount
    records = @($records)
}

$finalMain = ([string](Invoke-SourceGit ls-remote origin refs/heads/main | Select-Object -First 1)).Trim()
$finalMatch = [regex]::Match($finalMain, '^([0-9a-f]{40})\s+refs/heads/main$')
if (-not $finalMatch.Success -or $finalMatch.Groups[1].Value -cne $checkpoint) {
    throw 'The live source main changed during ledger generation; regenerate from a fresh checkpoint.'
}

$parent = Split-Path -Parent $OutputPath
New-Item -ItemType Directory -Force -Path $parent | Out-Null
$ledger | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $OutputPath -Encoding utf8NoBOM
Write-Host "Wrote $($ledger.commitCount) source commits, including $mergeCount merges, through $checkpoint to $OutputPath"
