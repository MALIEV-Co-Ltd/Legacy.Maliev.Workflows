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

$legacyTargets = [ordered]@{}
$ownerNames = @(
    @($mapping.rules.owners | ForEach-Object { $_ }) + @($mapping.architecturalTargets) |
        Sort-Object -Unique
)
foreach ($owner in $ownerNames) {
    $repositoryPath = Join-Path $LegacyRoot $owner
    if (-not (Test-Path -LiteralPath (Join-Path $repositoryPath '.git'))) { throw "Canonical Legacy repository was not found: $repositoryPath" }
    $targetSha = ([string](& git -C $repositoryPath rev-parse origin/main 2>&1 | Select-Object -First 1)).Trim()
    if ($LASTEXITCODE -ne 0 -or $targetSha -notmatch '^[0-9a-f]{40}$') { throw "Could not resolve $owner origin/main to a full commit SHA." }
    $legacyTargets[$owner] = [ordered]@{
        mainSha = $targetSha
        evidence = "https://github.com/MALIEV-Co-Ltd/$owner/commit/$targetSha"
    }
}

$commits = Invoke-SourceGit rev-list --reverse --no-merges $checkpoint
$ordinal = 0
$records = foreach ($commitValue in $commits) {
    $ordinal++
    $commit = $commitValue.Trim()
    $metadata = ([string](Invoke-SourceGit show -s '--format=%aI%x09%s' $commit | Select-Object -First 1)) -split "`t", 2
    $paths = @(Invoke-SourceGit diff-tree --root --no-commit-id --name-only -r $commit | Where-Object { $_ })
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
        subject = $metadata[1]
        sourceEvidence = "https://github.com/$($mapping.sourceRepository)/commit/$commit"
        classifications = @($classifications)
    }
}

$ledger = [ordered]@{
    schemaVersion = 1
    generatedAt = [DateTimeOffset]::UtcNow.ToString('O')
    sourceRepository = $mapping.sourceRepository
    sourceCheckpoint = $checkpoint
    legacyTargets = $legacyTargets
    nonMergeCommitCount = @($records).Count
    records = @($records)
}

$parent = Split-Path -Parent $OutputPath
New-Item -ItemType Directory -Force -Path $parent | Out-Null
$ledger | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $OutputPath -Encoding utf8NoBOM
Write-Host "Wrote $($ledger.nonMergeCommitCount) source commits through $checkpoint to $OutputPath"
