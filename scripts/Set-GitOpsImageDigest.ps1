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
    [string] $GitOpsPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Stop-InvalidInput {
    param([Parameter(Mandatory)][string] $Message)

    throw $Message
}

if ($Service -cnotmatch '^Legacy\.Maliev\.[A-Z][A-Za-z0-9]*$') {
    Stop-InvalidInput 'service must match Legacy.Maliev.*'
}

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

$serviceSuffix = $Service.Substring('Legacy.Maliev.'.Length)
$serviceSlug = [regex]::Replace($serviceSuffix, '(?<=[a-z0-9])(?=[A-Z])', '-').ToLowerInvariant()
$relativeTarget = "3-apps/_legacy-$serviceSlug/overlays/legacy/kustomization.yaml"
$expectedTarget = [IO.Path]::GetFullPath([IO.Path]::Combine($rootPath, $relativeTarget))
if (-not $targetPath.Equals($expectedTarget, $pathComparison)) {
    Stop-InvalidInput "gitops-path must equal the established legacy path $relativeTarget"
}

if (-not [IO.File]::Exists($targetPath)) {
    Stop-InvalidInput 'gitops-path must identify an existing legacy kustomization.yaml'
}

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

$expectedImageName = "legacy-maliev-$serviceSlug"
$nameMatch = [regex]::Match($imagesBlock, '(?m)^\s*-\s*name\s*:\s*(?<value>\S+)\s*$')
if (-not $nameMatch.Success -or $nameMatch.Groups['value'].Value -cne $expectedImageName) {
    Stop-InvalidInput "image entry name must equal $expectedImageName"
}

$newNameMatches = [regex]::Matches($imagesBlock, '(?m)^\s*newName\s*:\s*(?<value>\S+)\s*$')
if ($newNameMatches.Count -ne 1 -or $newNameMatches[0].Groups['value'].Value -cne $Image) {
    Stop-InvalidInput 'manifest must contain exactly one newName matching image'
}

$mutableReferenceMatches = [regex]::Matches($imagesBlock, '(?m)^(?<indent>\s*)(?:newTag|digest)\s*:\s*\S+\s*$')
if ($mutableReferenceMatches.Count -ne 1) {
    Stop-InvalidInput 'manifest must contain exactly one newTag or digest field'
}

$referenceMatch = $mutableReferenceMatches[0]
$replacement = "$($referenceMatch.Groups['indent'].Value)digest: $Digest"
$updatedBlock = $imagesBlock.Remove($referenceMatch.Index, $referenceMatch.Length).Insert($referenceMatch.Index, $replacement)
$updated = $original.Remove($imagesMatch.Groups['block'].Index, $imagesMatch.Groups['block'].Length).Insert($imagesMatch.Groups['block'].Index, $updatedBlock)

if ($updated -ceq $original) {
    Stop-InvalidInput 'image digest update produced no change'
}

[IO.File]::WriteAllText($targetPath, $updated, [Text.UTF8Encoding]::new($false))

$changedFiles = @(& git -C $rootPath diff --name-only --)
if ($LASTEXITCODE -ne 0 -or $changedFiles.Count -ne 1 -or $changedFiles[0] -cne $relativeTarget) {
    [IO.File]::WriteAllText($targetPath, $original, [Text.UTF8Encoding]::new($false))
    Stop-InvalidInput 'git diff may contain only the target manifest'
}

Write-Output "Updated $relativeTarget to $Digest"
