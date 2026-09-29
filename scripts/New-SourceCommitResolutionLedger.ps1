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
$previous = $null
if (Test-Path -LiteralPath $OutputPath) {
    $previous = Get-Content -LiteralPath $OutputPath -Raw | ConvertFrom-Json -AsHashtable -DateKind String
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

# Workflows #138 reviewed six path mappings. Only three commits lose the
# CompatibilityContracts owner entirely; mixed commits retain that valid owner.
$reviewedOwnerTransitions = @{}
$reviewedTransitionPatterns = @{}
# Workflows #193 pins the MessageService-only ownership correction. This is
# independent of earlier LoggerService transitions on the same source commits.
$reviewedMessageShas = @(
    '5fac706a7983a6d359b39acbd670e6800afe020e',
    '3a393215d883fa35e1461f69c876bf2ead7ce36e',
    '0822636e5e2d46e4db20a79d27037aab426d85aa',
    '3a104503328cc3c0d57ff9ae2deafba06d1e46d5',
    '72eb9f1949176392141951d35e6e06f7c30af4c2',
    '5458b7ddc81a15d72087fa69fb4cfcc27ae75747',
    '53f4baf373ef04a3ed5ab5c1ef39bd61404c5258',
    '93f9f99522fbe6c128acb5d049f2b448e07dba95',
    '90f34b389c298d1ce85abe2ae7ac92877dbbf7af',
    '00ec830615c15b5e4e227046712247b11df0100f',
    '2aab25eb07894fc0267b03b85bad96490219d2fa',
    '7d6f46f53cbab853ca9c25e385af067cfff6238a',
    'cbac7d7155da2208c77d56103b6a2cb19196fc83',
    'eb8ed86672bd9afccc6560b547b734d0fcd7363b',
    'a649db99a27bda65274fe1b18866ae226d3c69cf',
    '03eaff1194c3ae2a54ceefeae31deffaff90436f',
    '72163e9ae11f39f6579423841a2e20529b986fab',
    'f8921b1b1d5846eeaff999af10b640011655d1d4',
    '143f53ba0a1c81c78d252864ca131d42ed79dc1b',
    '9e51e6c5da29de8e617b65b59d46882cde6d3b64',
    'c660de68b633618cb0c857a287020f5ed9c42683',
    'a7d0a4517ef1cfef638763cb1092088a5932fa2f',
    '03dc9a1271c16e6535934445e9dd6e3f30e8fffe',
    '5ac7d045c51194edd9e64d8564f1b726b001be34'
)
$reviewedMessageSet = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
foreach ($sha in $reviewedMessageShas) {
    if (-not $reviewedMessageSet.Add($sha)) { throw "Duplicate reviewed MessageService SHA $sha." }
}
@(
    '3d6506285a58671651d046e97a35fbb8885cea4f',
    '7b311e4e7f0dd80be0441abc2625dab295179f1a',
    '5ac7d045c51194edd9e64d8564f1b726b001be34'
) | ForEach-Object {
    $reviewedTransitionPatterns[$_] = '^Maliev\.(?:NativeLogging|Service\.WebApi)/'
    $reviewedOwnerTransitions[$_] = [ordered]@{
        removedOwner = 'Legacy.Maliev.CompatibilityContracts'
        retainedOwner = 'Legacy.Maliev.ServiceDefaults'
        issueUrl = 'https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Workflows/issues/138'
        priorIssueUrls = @()
        reason = 'Native logging and WebApi diagnostics are not CompatibilityContracts APIs; the retained ServiceDefaults owner still requires independent migration evidence.'
    }
    if ($_ -ceq '7b311e4e7f0dd80be0441abc2625dab295179f1a') {
        $reviewedOwnerTransitions[$_].priorIssueUrls = @(
            'https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Workflows/issues/138')
    }
}
@(
    '3a393215d883fa35e1461f69c876bf2ead7ce36e',
    '5458b7ddc81a15d72087fa69fb4cfcc27ae75747',
    '53f4baf373ef04a3ed5ab5c1ef39bd61404c5258',
    '93f9f99522fbe6c128acb5d049f2b448e07dba95',
    '00ec830615c15b5e4e227046712247b11df0100f',
    '2aab25eb07894fc0267b03b85bad96490219d2fa',
    '7d6f46f53cbab853ca9c25e385af067cfff6238a',
    'cbac7d7155da2208c77d56103b6a2cb19196fc83',
    'eb8ed86672bd9afccc6560b547b734d0fcd7363b',
    'a649db99a27bda65274fe1b18866ae226d3c69cf',
    '03eaff1194c3ae2a54ceefeae31deffaff90436f',
    '72163e9ae11f39f6579423841a2e20529b986fab',
    'f8921b1b1d5846eeaff999af10b640011655d1d4',
    'ee2bb593830c0b8aa30874d162ba2edee1596fea',
    '143f53ba0a1c81c78d252864ca131d42ed79dc1b',
    'abc057c985053c983ff3a23a78dcfe3ba1d0b2be',
    'f0640fe0719b2eb6becda378bff08153d955be07',
    '9e51e6c5da29de8e617b65b59d46882cde6d3b64'
) | ForEach-Object {
    $reviewedTransitionPatterns[$_] = '^Maliev\.LoggerService\.'
    $reviewedOwnerTransitions[$_] = [ordered]@{
        removedOwner = 'Legacy.Maliev.CompatibilityContracts'
        retainedOwner = 'Legacy.Maliev.ServiceDefaults'
        issueUrl = 'https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Workflows/issues/173'
        priorIssueUrls = @()
        reason = 'Retired LoggerService HTTP logging and NLog are not retained message-wire contracts; ServiceDefaults owns the replacement failure-tracing behavior.'
    }
}

# Workflows #220 reviews the sole Web.Tests file that tests UploadService
# deployment artifacts, not Web behavior. It changed in exactly two source
# commits; FileService retains their open workload identity release gate.
@(
    '4533669fa5231368f17c4b59b17c3e2f52e24a89',
    '25418c95b5ac79400029ce274541f0e51728da3e'
) | ForEach-Object {
    $reviewedTransitionPatterns[$_] =
        '^Maliev\.Web\.Tests/UploadServiceWorkloadIdentityDeploymentTests\.cs$'
    $reviewedOwnerTransitions[$_] = [ordered]@{
        removedOwner = 'Legacy.Maliev.Web'
        retainedOwner = 'Legacy.Maliev.FileService'
        issueUrl = 'https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Workflows/issues/220'
        priorIssueUrls = @()
        reason = 'The source test reads only UploadService deployment artifacts; FileService owns the pending workload identity release gate, with target-native manifest verification in GitOps.'
    }
}

$resolvedCount = 0
$reviewedTransitionCount = 0
$reviewedMessageCount = 0
$intranetTestSolutionSha = '5e2030b7339d4d9bd699fd8c3f406b71706b377d'
$intranetTestSolutionCount = 0
$formatOnlySha = '61df92fb171a5c1c65a46a07cd70777d87e1a46e'
$formatOnlyPaths = @(
    'Maliev.QuotationRequestService.Common/Models/QualificationOutcomeReadback.cs',
    'Maliev.QuotationRequestService.Tests/QuotationRequests/QualificationOutcomeReadbackTests.cs',
    'Maliev.Web.Tests/MeasurementRuntimeBrowserTests.cs'
)
$formatOnlyOwners = @('Legacy.Maliev.QuotationService', 'Legacy.Maliev.Web')
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
        if ($item.status -cnotin @('pending', 'partial', 'migrated', 'blocked', 'approved-no-op')) {
            throw "Invalid owner resolution status for $($source.commit)."
        }
        if ($item.status -cin @('partial', 'migrated')) {
            if (@($item.issueUrls).Count -eq 0 -or @($item.prUrls).Count -eq 0 -or
                @($item.validationEvidenceUrls).Count -eq 0 -or
                $item.mergedTargetSha -cnotmatch '^[0-9a-f]{40}$') {
                throw "Resolved slice for $owner lacks issue, PR, main SHA, or validation evidence."
            }
            Assert-EvidenceUrls @($item.issueUrls) 'issues/[0-9]+'
            foreach ($prUrl in @($item.prUrls)) {
                if ($prUrl -cnotmatch ('^https://github\.com/MALIEV-Co-Ltd/' +
                    [regex]::Escape($owner) + '/pull/[0-9]+$')) {
                    throw "A resolved $owner slice points to a PR in a different repository."
                }
            }
            foreach ($evidenceUrl in @($item.validationEvidenceUrls)) {
                if ($evidenceUrl -cnotmatch '^https://') {
                    throw "A resolved $owner slice has a non-URL validation reference."
                }
            }
            $targetPath = Join-Path $LegacyRoot $owner
            & git -C $targetPath merge-base --is-ancestor $item.mergedTargetSha $ledger.legacyTargets[$owner].mainSha
            if ($LASTEXITCODE -ne 0) {
                throw "The merged target SHA is not an ancestor of protected main for $owner."
            }
        }
        if ($item.status -ceq 'approved-no-op') {
            if ($source.commit -cne $formatOnlySha -or $source.isMerge -or
                (@($owners | Sort-Object -CaseSensitive) -join '|') -cne
                    (@($formatOnlyOwners | Sort-Object -CaseSensitive) -join '|') -or
                (@($source.classifications | ForEach-Object { $_.path } | Sort-Object -CaseSensitive) -join '|') -cne
                    (@($formatOnlyPaths | Sort-Object -CaseSensitive) -join '|') -or
                (@($item.issueUrls) -join '|') -cne
                    'https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Workflows/issues/175' -or
                [string]::IsNullOrWhiteSpace([string]$item.reason) -or
                $item.reviewedTargetSha -cnotmatch '^[0-9a-f]{40}$' -or
                @($item.prUrls | Where-Object { $_ }).Count -ne 0 -or
                @($item.validationEvidenceUrls | Where-Object { $_ }).Count -ne 0 -or
                -not [string]::IsNullOrEmpty([string]$item.mergedTargetSha)) {
                throw "The exact owner no-op disposition is invalid for $($source.commit)."
            }
            $changedPaths = @(git -C $SourceRepository diff --name-only $source.parents[0] $source.commit)
            if ($LASTEXITCODE -ne 0 -or
                (@($changedPaths | Sort-Object -CaseSensitive) -join '|') -cne
                    (@($formatOnlyPaths | Sort-Object -CaseSensitive) -join '|')) {
                throw 'The reviewed source commit no longer has the exact three formatting-only paths.'
            }
            & git -C $SourceRepository diff --ignore-space-at-eol --quiet $source.parents[0] $source.commit
            if ($LASTEXITCODE -ne 0) {
                throw 'The reviewed source commit contains a non-formatting content change.'
            }
            $targetPath = Join-Path $LegacyRoot $owner
            & git -C $targetPath merge-base --is-ancestor $item.reviewedTargetSha $ledger.legacyTargets[$owner].mainSha
            if ($LASTEXITCODE -ne 0) {
                throw "The reviewed no-op target SHA is not an ancestor of protected main for $owner."
            }
        }
        $ownerResolutions[$owner] = $item
    }
    $solutionGraphTransition = $null
    if ($source.commit -ceq $intranetTestSolutionSha) {
        $intranetTestSolutionCount++
        $solutionPaths = @($source.classifications | Where-Object { $_.path -ceq 'Maliev.sln' })
        if ($source.isMerge -or $solutionPaths.Count -ne 1 -or
            (@($solutionPaths[0].owners) -join '|') -cne 'Legacy.Maliev.Intranet' -or
            $owners -ccontains 'Legacy.Maliev.AppHost' -or $owners -ccontains 'Legacy.Maliev.Workflows') {
            throw 'The reviewed Intranet test-solution owner transition no longer matches its source classification.'
        }
        $removedOwners = @('Legacy.Maliev.AppHost', 'Legacy.Maliev.Workflows')
        $previousOwners = @($old.ownerResolutions.Keys | Sort-Object -CaseSensitive)
        $expectedPreviousOwners = if ($old.solutionGraphOwnerTransition) {
            @($owners | Sort-Object -CaseSensitive)
        } else {
            @(($owners + $removedOwners) | Sort-Object -Unique -CaseSensitive)
        }
        $solutionGraphTransition = [ordered]@{
            removedOwners = $removedOwners
            retainedOwner = 'Legacy.Maliev.Intranet'
            issueUrl = 'https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Workflows/issues/233'
            reason = 'The source solution adds only Intranet.Tests; the split Intranet solution and CI own that test graph, not AppHost or Workflows.'
        }
        if (-not $old -or $previousOwners.Count -ne $expectedPreviousOwners.Count -or
            ($previousOwners -join '|') -cne ($expectedPreviousOwners -join '|')) {
            throw 'The reviewed Intranet test-solution transition has an unexpected prior owner set.'
        }
        if (-not $old.solutionGraphOwnerTransition) {
            foreach ($removedOwner in $removedOwners) {
                $removed = $old.ownerResolutions[$removedOwner]
                if ($removed.status -cne 'pending' -or @($removed.issueUrls | Where-Object { $_ }).Count -ne 0 -or
                    @($removed.prUrls | Where-Object { $_ }).Count -ne 0 -or
                    @($removed.validationEvidenceUrls | Where-Object { $_ }).Count -ne 0 -or
                    -not [string]::IsNullOrEmpty([string]$removed.mergedTargetSha)) {
                    throw "Removed solution-graph owner $removedOwner has evidence or non-pending work."
                }
            }
        }
        if ($old.solutionGraphOwnerTransition -and
            ($old.solutionGraphOwnerTransition | ConvertTo-Json -Compress) -cne
                ($solutionGraphTransition | ConvertTo-Json -Compress)) {
            throw 'The reviewed Intranet test-solution transition provenance changed.'
        }
    }
    elseif ($old -and $old.solutionGraphOwnerTransition) {
        throw "Unexpected Intranet test-solution transition for $($source.commit)."
    }
    $transition = $reviewedOwnerTransitions[$source.commit]
    if ($transition) {
        $reviewedTransitionCount++
        if (-not $old -or -not @($source.classifications | Where-Object {
            $_.path -match $reviewedTransitionPatterns[$source.commit]
        }).Count -or $owners -cnotcontains $transition.retainedOwner -or
            $owners -ccontains $transition.removedOwner) {
            throw "The reviewed owner transition does not match the source classification for $($source.commit)."
        }
        $oldOwners = @($old.ownerResolutions.Keys | Sort-Object -CaseSensitive)
        $newOwners = @($owners | Sort-Object -CaseSensitive)
        if ($old.ownerResolutions.ContainsKey($transition.removedOwner)) {
            $expectedOldOwners = @(($newOwners + $transition.removedOwner) | Sort-Object -Unique -CaseSensitive)
            $removed = $old.ownerResolutions[$transition.removedOwner]
            if (($oldOwners -join '|') -cne ($expectedOldOwners -join '|') -or
                $removed.status -cne 'pending' -or
                (@($removed.issueUrls) -join '|') -cne (@($transition.priorIssueUrls) -join '|') -or
                @($removed.prUrls | Where-Object { $_ }).Count -ne 0 -or
                @($removed.validationEvidenceUrls | Where-Object { $_ }).Count -ne 0 -or
                -not [string]::IsNullOrEmpty([string]$removed.mergedTargetSha) -or
                $old.ownerSetTransition) {
                throw "Removed owner has evidence or unexpected history for $($source.commit)."
            }
        }
        else {
            $expectedPriorOwners = $newOwners
            if ($reviewedMessageSet.Contains($source.commit) -and -not $old.messageOwnerTransition) {
                $expectedPriorOwners = @($newOwners | Where-Object { $_ -cne 'Legacy.Maliev.ContactService' })
                if (-not @($source.classifications | Where-Object {
                    $_.path -notmatch '^Maliev\.MessageService\.' -and
                    $_.owners -ccontains 'Legacy.Maliev.NotificationService'
                }).Count) {
                    $expectedPriorOwners = @($expectedPriorOwners + 'Legacy.Maliev.NotificationService' |
                        Sort-Object -Unique -CaseSensitive)
                }
            }
            if (($oldOwners -join '|') -cne ($expectedPriorOwners -join '|') -or
                $old.ownerSetTransition.removedOwner -cne $transition.removedOwner -or
                $old.ownerSetTransition.retainedOwner -cne $transition.retainedOwner -or
                $old.ownerSetTransition.issueUrl -cne $transition.issueUrl -or
                (@($old.ownerSetTransition.priorIssueUrls) -join '|') -cne
                    (@($transition.priorIssueUrls) -join '|') -or
                $old.ownerSetTransition.reason -cne $transition.reason) {
                throw "The reviewed owner transition provenance changed for $($source.commit)."
            }
        }
    }
    $messageTransition = $null
    if ($reviewedMessageSet.Contains($source.commit)) {
        $reviewedMessageCount++
        $messagePaths = @($source.classifications | Where-Object { $_.path -match '^Maliev\.MessageService\.' })
        $otherNotificationPaths = @($source.classifications | Where-Object {
            $_.path -notmatch '^Maliev\.MessageService\.' -and
            $_.owners -ccontains 'Legacy.Maliev.NotificationService'
        })
        $removedNotification = $otherNotificationPaths.Count -eq 0
        $oldOwners = @($old.ownerResolutions.Keys | Sort-Object -CaseSensitive)
        $newOwners = @($owners | Sort-Object -CaseSensitive)
        $expectedOldOwners = @($newOwners | Where-Object { $_ -cne 'Legacy.Maliev.ContactService' })
        if ($removedNotification) {
            $expectedOldOwners = @($expectedOldOwners + 'Legacy.Maliev.NotificationService' |
                Sort-Object -Unique -CaseSensitive)
        }
        if (-not $old -or $messagePaths.Count -eq 0 -or
            @($messagePaths | Where-Object { $_.owners -cne 'Legacy.Maliev.ContactService' }).Count -ne 0 -or
            $owners -cnotcontains 'Legacy.Maliev.ContactService') {
            throw "The reviewed MessageService classification changed for $($source.commit)."
        }
        $messageTransition = [ordered]@{
            addedOwner = 'Legacy.Maliev.ContactService'
            removedOwner = if ($removedNotification) { 'Legacy.Maliev.NotificationService' } else { $null }
            issueUrl = 'https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Workflows/issues/193'
            reason = 'MessageService belongs to ContactService; NotificationService remains an owner only where this commit also changes EmailService.'
        }
        if ($old.messageOwnerTransition) {
            if (($oldOwners -join '|') -cne ($newOwners -join '|') -or
                ($old.messageOwnerTransition | ConvertTo-Json -Compress) -cne
                    ($messageTransition | ConvertTo-Json -Compress)) {
                throw "The reviewed MessageService transition provenance changed for $($source.commit)."
            }
        }
        else {
            if (($oldOwners -join '|') -cne ($expectedOldOwners -join '|') -or
                ($removedNotification -and ($old.ownerResolutions['Legacy.Maliev.NotificationService'].status -cne 'pending' -or
                    @($old.ownerResolutions['Legacy.Maliev.NotificationService'].issueUrls | Where-Object { $_ }).Count -ne 0 -or
                    @($old.ownerResolutions['Legacy.Maliev.NotificationService'].prUrls | Where-Object { $_ }).Count -ne 0 -or
                    @($old.ownerResolutions['Legacy.Maliev.NotificationService'].validationEvidenceUrls | Where-Object { $_ }).Count -ne 0 -or
                    $old.ownerResolutions['Legacy.Maliev.NotificationService'].mergedTargetSha))) {
                throw "Removed MessageService owner has evidence or unexpected history for $($source.commit)."
            }
        }
    }
    elseif ($old -and $old.messageOwnerTransition) {
        throw "Unexpected MessageService transition for $($source.commit)."
    }
    elseif (-not $transition -and -not $solutionGraphTransition -and $old -and
        (@($old.ownerResolutions.Keys | Sort-Object -CaseSensitive) -join '|') -cne ($owners -join '|')) {
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

    $allOwnersMigrated = $owners.Count -gt 0 -and
        @($ownerResolutions.Values | Where-Object { $_.status -cne 'migrated' }).Count -eq 0
    $allOwnersNoOp = $owners.Count -gt 0 -and
        @($ownerResolutions.Values | Where-Object { $_.status -cne 'approved-no-op' }).Count -eq 0
    $retirementApproved = -not $retirement -or $retirement.status -ceq 'approved'
    # A validated subset is visible as partial, but cannot increment the fully
    # resolved count until every owner and retirement decision is complete.
    $anyResolved = @($ownerResolutions.Values | Where-Object {
        $_.status -cin @('partial', 'migrated', 'approved-no-op') }).Count -gt 0 -or
        ($retirement -and $retirement.status -ceq 'approved')
    $anyBlocked = @($ownerResolutions.Values | Where-Object { $_.status -ceq 'blocked' }).Count -gt 0 -or
        ($retirement -and $retirement.status -ceq 'blocked')
    $status = if ($allOwnersMigrated -and $retirementApproved) { 'migrated' }
        elseif ($allOwnersNoOp -and $retirementApproved) { 'approved-no-op' }
        elseif ($owners.Count -eq 0 -and $retirementApproved) { 'approved-retirement' }
        elseif ($anyResolved) { 'partial' } elseif ($anyBlocked) { 'blocked' } else { 'pending' }
    if ($status -in @('migrated', 'approved-no-op', 'approved-retirement')) { $resolvedCount++ }
    $record = [ordered]@{
        sourceSha = $source.commit
        isMerge = [bool]$source.isMerge
        status = $status
        ownerResolutions = $ownerResolutions
        retirementApproval = $retirement
    }
    if ($transition) { $record.ownerSetTransition = $transition }
    if ($messageTransition) { $record.messageOwnerTransition = $messageTransition }
    if ($solutionGraphTransition) { $record.solutionGraphOwnerTransition = $solutionGraphTransition }
    $record
}
if ($intranetTestSolutionCount -ne 1) {
    throw 'The exact reviewed Intranet test-solution transition was not present once in the complete source ledger.'
}
if ($reviewedTransitionCount -ne $reviewedOwnerTransitions.Count) {
    throw 'The exact reviewed owner-set transitions were not present in the complete source ledger.'
}
if ($reviewedMessageCount -ne $reviewedMessageSet.Count) {
    throw 'The exact reviewed MessageService commits were not present in the complete source ledger.'
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
if ($previous -and $previous.schemaVersion -eq $result.schemaVersion -and
    $previous.sourceRepository -ceq $result.sourceRepository -and
    $previous.sourceCheckpoint -ceq $result.sourceCheckpoint -and
    $previous.sourceCommitCount -eq $result.sourceCommitCount -and
    $previous.fullyResolvedCommitCount -eq $result.fullyResolvedCommitCount -and
    $previous.unresolvedCommitCount -eq $result.unresolvedCommitCount -and
    $previous.complete -eq $result.complete -and
    ($previous.records | ConvertTo-Json -Depth 30 -Compress) -ceq
        ($result.records | ConvertTo-Json -Depth 30 -Compress)) {
    $result.generatedAt = $previous.generatedAt
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
