param(
    [Parameter(Mandatory = $true)]
    [string] $SourceRepository,

    [string] $ManifestPath = (Join-Path $PSScriptRoot '..\migration\source-page-acceptance.json')
)

$ErrorActionPreference = 'Stop'
$manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
if ($manifest.schemaVersion -ne 2) {
    throw 'source_page_manifest_schema_unsupported'
}
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

foreach ($page in $manifest.pages) {
    $sourcePath = [string] $page.sourcePath
    $sourceLines = @(git -C $SourceRepository show "${sourceSha}:$sourcePath")
    if ($LASTEXITCODE -ne 0 -or $sourceLines.Count -eq 0) {
        throw "source_page_route_changed:$sourcePath"
    }

    $directive = $sourceLines[0].TrimStart([char] 0xFEFF).Trim()
    if ($directive -cnotmatch '^@page(?:\s+"([^"]+)")?$') {
        throw "source_page_route_changed:$sourcePath"
    }

    $declaredRoute = $Matches[1]
    $pageRelativePath = $sourcePath -creplace '^Maliev\.(Web|Intranet)/Pages/', '' -creplace '\.cshtml$', ''
    $conventionalPath = '/' + $pageRelativePath
    if ($conventionalPath -eq '/Index') {
        $conventionalPath = '/'
    } elseif ($conventionalPath.EndsWith('/Index', [StringComparison]::Ordinal)) {
        $conventionalPath = $conventionalPath.Substring(0, $conventionalPath.Length - '/Index'.Length)
    }

    $actualRoute = if ([string]::IsNullOrEmpty($declaredRoute)) {
        $conventionalPath
    } elseif ($declaredRoute.StartsWith('/', [StringComparison]::Ordinal)) {
        $declaredRoute
    } else {
        $conventionalPath.TrimEnd('/') + '/' + $declaredRoute
    }
    if ($actualRoute -cne $page.sourceRoutePattern) {
        throw "source_page_route_changed:$sourcePath"
    }
}

Write-Output "source_page_inventory_and_routes_verified:$($actual.Count):$sourceSha"
