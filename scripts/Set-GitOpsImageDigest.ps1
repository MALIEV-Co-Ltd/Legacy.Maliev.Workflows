[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string] $GitOpsRoot,

    [Parameter(Mandatory)]
    [string] $Service,

    [Parameter(Mandatory)]
    [string] $Image,

    [Parameter(Mandatory)]
    [string] $Digest,

    [Parameter(Mandatory)]
    [string] $GitOpsPath,

    [Parameter()]
    [string] $ContractVersion = 'v1',

    [Parameter(Mandatory)]
    [string] $GitHubOutput
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$contracts = @{
    v1 = @{
        'Legacy.Maliev.CountryService' = @{
            Path      = '3-apps/_legacy-country-service/overlays/legacy/kustomization.yaml'
            ImageName = 'legacy-maliev-country-service'
            Branch    = 'gitops/legacy-country-service'
        }
    }
}

function Stop-InvalidInput {
    param([Parameter(Mandatory)][string] $Message)

    throw $Message
}

function Assert-NoOutputControlCharacters {
    param([Parameter(Mandatory)][string[]] $Values)

    foreach ($value in $Values) {
        if ($value.IndexOfAny([char[]]@("`r", "`n", "`0")) -ge 0) {
            Stop-InvalidInput 'inputs must not contain CR, LF, or NUL characters'
        }
    }
}

function Assert-NoReparseComponents {
    param(
        [Parameter(Mandatory)][string] $RootPath,
        [Parameter(Mandatory)][string] $TargetPath
    )

    $relativePath = [IO.Path]::GetRelativePath($RootPath, $TargetPath)
    $components = @($RootPath)
    $currentPath = $RootPath
    foreach ($segment in $relativePath.Split([char[]]@([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar), [StringSplitOptions]::RemoveEmptyEntries)) {
        $currentPath = [IO.Path]::Combine($currentPath, $segment)
        $components += $currentPath
    }

    foreach ($component in $components) {
        $item = Get-Item -LiteralPath $component -Force
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
            ($item.PSObject.Properties.Name -contains 'LinkType' -and $null -ne $item.LinkType)) {
            Stop-InvalidInput 'reparse points and symbolic links are prohibited in gitops-root and gitops-path'
        }
    }
}

function Write-ActionOutputs {
    param(
        [Parameter(Mandatory)][bool] $Changed,
        [Parameter(Mandatory)][ValidateSet('updated', 'no-op')][string] $Status,
        [Parameter(Mandatory)][string] $Branch
    )

    $lines = @(
        "changed=$($Changed.ToString().ToLowerInvariant())",
        "status=$Status",
        "branch=$Branch"
    )
    $payload = ($lines -join [Environment]::NewLine) + [Environment]::NewLine
    [IO.File]::AppendAllText($GitHubOutput, $payload, [Text.UTF8Encoding]::new($false))
}

Assert-NoOutputControlCharacters @(
    $GitOpsRoot,
    $Service,
    $Image,
    $Digest,
    $GitOpsPath,
    $ContractVersion,
    $GitHubOutput
)

if ($Service -cnotmatch '^Legacy\.Maliev\.[A-Z][A-Za-z0-9]*$') {
    Stop-InvalidInput 'service must match Legacy.Maliev.*'
}

if (-not $contracts.ContainsKey($ContractVersion)) {
    Stop-InvalidInput "unknown GitOps contract version $ContractVersion"
}

$versionedContracts = $contracts[$ContractVersion]
if (-not $versionedContracts.ContainsKey($Service)) {
    Stop-InvalidInput "service is not present in GitOps contract $ContractVersion"
}
$contract = $versionedContracts[$Service]

if ($Digest -cnotmatch '^sha256:[0-9a-f]{64}$') {
    Stop-InvalidInput 'digest must be sha256 followed by 64 lowercase hexadecimal characters'
}

if ($Image -notmatch '^[^\s:@]+(?:/[^\s:@]+)+$') {
    Stop-InvalidInput 'image must be a full image name without a tag or digest'
}

$rootPath = [IO.Path]::GetFullPath($GitOpsRoot)
if (-not [IO.Directory]::Exists($rootPath)) {
    Stop-InvalidInput 'gitops-root must be an existing directory'
}

$targetPath = if ([IO.Path]::IsPathRooted($GitOpsPath)) {
    [IO.Path]::GetFullPath($GitOpsPath)
}
else {
    [IO.Path]::GetFullPath([IO.Path]::Combine($rootPath, $GitOpsPath))
}

$rootPrefix = $rootPath.TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
$pathComparison = if ($IsWindows) { [StringComparison]::OrdinalIgnoreCase } else { [StringComparison]::Ordinal }
if (-not $targetPath.StartsWith($rootPrefix, $pathComparison)) {
    Stop-InvalidInput 'gitops-path must stay within gitops-root'
}

$relativeTarget = [string]$contract.Path
$expectedTarget = [IO.Path]::GetFullPath([IO.Path]::Combine($rootPath, $relativeTarget))
if (-not $targetPath.Equals($expectedTarget, $pathComparison)) {
    Stop-InvalidInput "gitops-path must equal the allowlisted $ContractVersion path $relativeTarget"
}

if (-not [IO.File]::Exists($targetPath)) {
    Stop-InvalidInput 'gitops-path must identify an existing allowlisted legacy kustomization.yaml'
}

Assert-NoReparseComponents -RootPath $rootPath -TargetPath $targetPath

$existingChanges = @(& git -C $rootPath status --porcelain=v1 --untracked-files=all)
if ($LASTEXITCODE -ne 0) {
    throw 'could not inspect the GitOps checkout'
}
if ($existingChanges.Count -ne 0) {
    Stop-InvalidInput 'git diff may contain only the target manifest; the checkout must start clean'
}

$original = [IO.File]::ReadAllText($targetPath)
if ([regex]::Matches($original, '(?m)^\s*namespace:\s*maliev-legacy\s*$').Count -ne 1 -or
    [regex]::Matches($original, '(?m)^\s*namespace:\s*\S+\s*$').Count -ne 1) {
    Stop-InvalidInput 'namespace must remain maliev-legacy'
}

if ($original -match '(?im)^\s*(?:nodeSelector|node-selector)\s*:') {
    Stop-InvalidInput 'node selectors are prohibited in the legacy image manifest'
}

$imagesMatch = [regex]::Match($original, '(?ms)^images:\s*\r?\n(?<block>(?:^[ \t]+.*(?:\r?\n|$))+)')
if (-not $imagesMatch.Success) {
    Stop-InvalidInput 'manifest must contain one images block'
}

$imagesBlock = $imagesMatch.Groups['block'].Value
if ([regex]::Matches($imagesBlock, '(?m)^\s*-\s*name\s*:').Count -ne 1) {
    Stop-InvalidInput 'manifest must contain exactly one image entry'
}

$expectedImageName = [string]$contract.ImageName
$nameMatch = [regex]::Match($imagesBlock, '(?m)^\s*-\s*name\s*:\s*(?<value>\S+)\s*$')
if (-not $nameMatch.Success -or $nameMatch.Groups['value'].Value -cne $expectedImageName) {
    Stop-InvalidInput "image entry name must equal allowlisted image $expectedImageName"
}

$newNameMatches = [regex]::Matches($imagesBlock, '(?m)^\s*newName\s*:\s*(?<value>\S+)\s*$')
if ($newNameMatches.Count -ne 1 -or $newNameMatches[0].Groups['value'].Value -cne $Image) {
    Stop-InvalidInput 'manifest must contain exactly one newName matching image'
}

$mutableReferenceMatches = [regex]::Matches($imagesBlock, '(?m)^(?<indent>\s*)(?<field>newTag|digest)\s*:\s*(?<value>\S+)\s*$')
if ($mutableReferenceMatches.Count -ne 1) {
    Stop-InvalidInput 'manifest must contain exactly one newTag or digest field'
}

$referenceMatch = $mutableReferenceMatches[0]
if ($referenceMatch.Groups['field'].Value -ceq 'digest' -and
    $referenceMatch.Groups['value'].Value -ceq $Digest) {
    Write-ActionOutputs -Changed $false -Status 'no-op' -Branch ([string]$contract.Branch)
    Write-Output "No change required for $relativeTarget at $Digest"
    exit 0
}

$replacement = "$($referenceMatch.Groups['indent'].Value)digest: $Digest"
$updatedBlock = $imagesBlock.Remove($referenceMatch.Index, $referenceMatch.Length).Insert($referenceMatch.Index, $replacement)
$updated = $original.Remove($imagesMatch.Groups['block'].Index, $imagesMatch.Groups['block'].Length).Insert($imagesMatch.Groups['block'].Index, $updatedBlock)

[IO.File]::WriteAllText($targetPath, $updated, [Text.UTF8Encoding]::new($false))

$changedFiles = @(& git -C $rootPath diff --name-only --)
if ($LASTEXITCODE -ne 0 -or $changedFiles.Count -ne 1 -or $changedFiles[0] -cne $relativeTarget) {
    [IO.File]::WriteAllText($targetPath, $original, [Text.UTF8Encoding]::new($false))
    Stop-InvalidInput 'git diff may contain only the target manifest'
}

Write-ActionOutputs -Changed $true -Status 'updated' -Branch ([string]$contract.Branch)
Write-Output "Updated $relativeTarget to $Digest"
