param(
    [Parameter(Mandatory = $true)]
    [string] $SourceRepository,

    [string] $ManifestPath = (Join-Path $PSScriptRoot '..\migration\source-page-acceptance.json')
)

$ErrorActionPreference = 'Stop'
$manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
$remote = @(git -C $SourceRepository ls-remote origin refs/heads/main)
if ($LASTEXITCODE -ne 0 -or $remote.Count -ne 1 -or $remote[0] -notmatch '^([0-9a-f]{40})\s+refs/heads/main$') {
    throw 'source_remote_main_unavailable'
}
$sourceSha = $Matches[1]

git -C $SourceRepository cat-file -e "${sourceSha}^{commit}" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw 'source_main_object_not_available_locally'
}

foreach ($tree in $manifest.sourcePageTrees.PSObject.Properties) {
    $actual = @(git -C $SourceRepository rev-parse "${sourceSha}:$($tree.Name)")
    if ($LASTEXITCODE -ne 0 -or $actual.Count -ne 1 -or $actual[0] -ne $tree.Value) {
        throw "source_page_tree_changed:$($tree.Name)"
    }
}

$expected = @($manifest.pages | ForEach-Object { $_.sourcePath } | Sort-Object)
$actual = @(git -C $SourceRepository grep -l '@page' $sourceSha -- Maliev.Web/Pages Maliev.Intranet/Pages |
    ForEach-Object { $_.Substring($sourceSha.Length + 1) } | Sort-Object)
if ($LASTEXITCODE -ne 0 -or $actual.Count -ne $expected.Count) {
    throw 'source_page_inventory_changed'
}
for ($index = 0; $index -lt $expected.Count; $index++) {
    if ($actual[$index] -cne $expected[$index]) {
        throw 'source_page_inventory_changed'
    }
}

Write-Output "source_page_inventory_verified:$($actual.Count):$sourceSha"
