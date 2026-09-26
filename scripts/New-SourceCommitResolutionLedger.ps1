[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string] $SourceRepository,
    [string] $LegacyRoot = (Split-Path -Parent $PSScriptRoot | Split-Path -Parent),
    [string] $LedgerPath = (Join-Path $PSScriptRoot '..\migration\source-commit-ledger.json'),
    [string] $OutputPath = (Join-Path $PSScriptRoot '..\migration\source-commit-resolutions.json')
)

$ErrorActionPreference = 'Stop'
$ledger = Get-Content -LiteralPath $LedgerPath -Raw | ConvertFrom-Json -AsHashtable
if ($ledger.schemaVersion -ne 2 -or $ledger.sourceCheckpoint -cnotmatch '^[0-9a-f]{40}$') {
    throw 'The complete schema-2 source ownership ledger is required.'
}
$liveMainResult = & git -C $SourceRepository ls-remote origin refs/heads/main
$liveGitExit = $LASTEXITCODE
$liveMain = @($liveMainResult | Select-Object -First 1)[0]
$liveMatch = [regex]::Match($liveMain, '^([0-9a-f]{40})\s+refs/heads/main$')
if ($liveGitExit -ne 0 -or -not $liveMatch.Success -or
    $liveMatch.Groups[1].Value -cne $ledger.sourceCheckpoint) {
    throw 'The source ledger checkpoint does not match live origin/main.'
}
$reachable = @(git -C $SourceRepository rev-list --reverse $ledger.sourceCheckpoint)
if ($LASTEXITCODE -ne 0 -or $reachable.Count -ne $ledger.commitCount -or
    $reachable.Count -ne @($ledger.records).Count) {
    throw 'The source commit inventory is not reachable or complete.'
}
for ($i = 0; $i -lt $reachable.Count; $i++) {
    if ($reachable[$i] -cne $ledger.records[$i].commit) {
        throw "The source commit order diverges at ordinal $($i + 1)."
    }
}

$previousBySha = @{}
if (Test-Path -LiteralPath $OutputPath) {
    $previous = Get-Content -LiteralPath $OutputPath -Raw | ConvertFrom-Json -AsHashtable
    if ($previous.schemaVersion -ne 1 -or $previous.sourceRepository -cne $ledger.sourceRepository) {
        throw 'The existing resolution ledger has an unsupported schema or source.'
    }
    foreach ($record in $previous.records) {
        if ($record.sourceSha -cnotmatch '^[0-9a-f]{40}$' -or $previousBySha.ContainsKey($record.sourceSha)) {
            throw 'The existing resolution ledger contains a duplicate or malformed source SHA.'
        }
        $previousBySha[$record.sourceSha] = $record
    }
}

function Assert-EvidenceUrls([object[]] $Urls, [string] $Suffix) {
    foreach ($url in $Urls) {
        if ($url -cnotmatch ('^https://github\.com/MALIEV-Co-Ltd/[^/]+/' + $Suffix + '$')) {
            throw "A resolution contains an invalid $Suffix evidence URL."
        }
    }
}

$resolvedCount = 0
$records = foreach ($source in $ledger.records) {
    $owners = @($source.classifications | Where-Object { $_.disposition -ceq 'migration-required' } |
        ForEach-Object { $_.owners } | Where-Object { $_ } | Sort-Object -Unique -CaseSensitive)
    $retirementPaths = @($source.classifications | Where-Object { $_.disposition -cne 'migration-required' } |
        ForEach-Object { $_.path } | Sort-Object -Unique -CaseSensitive)
    $old = $previousBySha[$source.commit]
    $ownerResolutions = [ordered]@{}
    foreach ($owner in $owners) {
        if (-not @($ledger.legacyTargets.Keys).Contains($owner)) {
            throw "Unknown Legacy owner $owner on $($source.commit)."
        }
        $prior = if ($old) { $old.ownerResolutions[$owner] } else { $null }
        $item = if ($prior) { $prior } else {
            [ordered]@{
                status = 'pending'
                issueUrls = @()
                prUrls = @()
                mergedTargetSha = $null
                validationEvidenceUrls = @()
            }
        }
        if ($item.status -cnotin @('pending', 'migrated', 'blocked')) {
            throw "Invalid owner resolution status for $($source.commit)."
        }
        if ($item.status -ceq 'migrated') {
            if (@($item.issueUrls).Count -eq 0 -or @($item.prUrls).Count -eq 0 -or
                @($item.validationEvidenceUrls).Count -eq 0 -or
                $item.mergedTargetSha -cnotmatch '^[0-9a-f]{40}$') {
                throw "Migrated owner $owner lacks issue, PR, main SHA, or validation evidence."
            }
            Assert-EvidenceUrls @($item.issueUrls) 'issues/[0-9]+'
            foreach ($prUrl in @($item.prUrls)) {
                if ($prUrl -cnotmatch ('^https://github\.com/MALIEV-Co-Ltd/' +
                    [regex]::Escape($owner) + '/pull/[0-9]+$')) {
                    throw "A migrated $owner resolution points to a PR in a different repository."
                }
            }
            foreach ($evidenceUrl in @($item.validationEvidenceUrls)) {
                if ($evidenceUrl -cnotmatch '^https://') {
                    throw "A migrated $owner resolution has a non-URL validation reference."
                }
            }
            $targetPath = Join-Path $LegacyRoot $owner
            & git -C $targetPath merge-base --is-ancestor $item.mergedTargetSha $ledger.legacyTargets[$owner].mainSha
            if ($LASTEXITCODE -ne 0) {
                throw "The merged target SHA is not an ancestor of protected main for $owner."
            }
        }
        $ownerResolutions[$owner] = $item
    }
    if ($old -and (@($old.ownerResolutions.Keys | Sort-Object -CaseSensitive) -join '|') -cne ($owners -join '|')) {
        throw "The owner set changed for $($source.commit); review its evidence manually."
    }

    $retirement = $null
    if ($retirementPaths.Count -gt 0) {
        $retirement = if ($old -and $old.retirementApproval) { $old.retirementApproval } else {
            [ordered]@{ status = 'pending'; paths = $retirementPaths; reason = $null; evidenceUrl = $null }
        }
        if ((@($retirement.paths | Sort-Object -CaseSensitive) -join '|') -cne ($retirementPaths -join '|') -or
            $retirement.status -cnotin @('pending', 'approved', 'blocked')) {
            throw "The retirement candidate set changed for $($source.commit)."
        }
        if ($retirement.status -ceq 'approved' -and
            ([string]::IsNullOrWhiteSpace($retirement.reason) -or
             $retirement.evidenceUrl -cnotmatch '^https://github\.com/MALIEV-Co-Ltd/')) {
            throw "An approved retirement lacks an owner reason or evidence URL for $($source.commit)."
        }
    }
    elseif ($old -and $old.retirementApproval) {
        throw "A prior retirement candidate disappeared for $($source.commit)."
    }

    $allOwnersMigrated = $owners.Count -eq 0 -or
        @($ownerResolutions.Values | Where-Object { $_.status -cne 'migrated' }).Count -eq 0
    $retirementApproved = -not $retirement -or $retirement.status -ceq 'approved'
    $anyResolved = @($ownerResolutions.Values | Where-Object { $_.status -ceq 'migrated' }).Count -gt 0 -or
        ($retirement -and $retirement.status -ceq 'approved')
    $anyBlocked = @($ownerResolutions.Values | Where-Object { $_.status -ceq 'blocked' }).Count -gt 0 -or
        ($retirement -and $retirement.status -ceq 'blocked')
    $status = if ($allOwnersMigrated -and $retirementApproved) {
        if ($owners.Count -gt 0) { 'migrated' } else { 'approved-retirement' }
    } elseif ($anyResolved) { 'partial' } elseif ($anyBlocked) { 'blocked' } else { 'pending' }
    if ($status -in @('migrated', 'approved-retirement')) { $resolvedCount++ }
    [ordered]@{
        sourceSha = $source.commit
        isMerge = [bool]$source.isMerge
        status = $status
        ownerResolutions = $ownerResolutions
        retirementApproval = $retirement
    }
}
$sourceShaSet = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
foreach ($record in $records) { $null = $sourceShaSet.Add($record.sourceSha) }
if (@($previousBySha.Keys | Where-Object { -not $sourceShaSet.Contains($_) }).Count -gt 0) {
    throw 'Previously tracked source commits disappeared from the current ledger.'
}

$result = [ordered]@{
    schemaVersion = 1
    generatedAt = [DateTimeOffset]::UtcNow.ToString('O')
    sourceRepository = $ledger.sourceRepository
    sourceCheckpoint = $ledger.sourceCheckpoint
    sourceCommitCount = @($records).Count
    fullyResolvedCommitCount = $resolvedCount
    unresolvedCommitCount = @($records).Count - $resolvedCount
    complete = ($resolvedCount -eq @($records).Count)
    records = @($records)
}
$finalMainResult = & git -C $SourceRepository ls-remote origin refs/heads/main
$finalGitExit = $LASTEXITCODE
$finalMatch = [regex]::Match(([string]($finalMainResult | Select-Object -First 1)),
    '^([0-9a-f]{40})\s+refs/heads/main$')
if ($finalGitExit -ne 0 -or -not $finalMatch.Success -or
    $finalMatch.Groups[1].Value -cne $ledger.sourceCheckpoint) {
    throw 'The live source main changed during resolution generation; regenerate both ledgers.'
}
$result | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $OutputPath -Encoding utf8NoBOM
Write-Host "Tracked $($result.sourceCommitCount) source commits; $($result.unresolvedCommitCount) remain unresolved."
