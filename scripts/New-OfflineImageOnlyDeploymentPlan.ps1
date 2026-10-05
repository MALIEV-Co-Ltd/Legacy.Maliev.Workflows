# Pure offline JSON transformation. No process, network, file, or resource adapter.
function New-OfflineImageOnlyDeploymentPlan {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$DeploymentJson,
        [Parameter(Mandatory)][string]$SourceCommit,
        [Parameter(Mandatory)][string]$ApprovedImageRepository,
        [Parameter(Mandatory)][hashtable]$ImageProof,
        [string]$ContractVersion = 'legacy-file-image-only/v1'
    )
    if ($ContractVersion -cne 'legacy-file-image-only/v1' -or
        $SourceCommit -cnotmatch '^[a-f0-9]{40}$' -or
        $ApprovedImageRepository -cnotmatch '^[a-z0-9-]+-docker\.pkg\.dev/maliev-website/[a-z0-9._-]+/legacy-maliev-file-service$') {
        throw 'Offline image plan contract or provenance scope is invalid.'
    }
    if ($ImageProof.Count -ne 3 -or @($ImageProof.Keys) -cnotcontains 'sourceCommit' -or
        @($ImageProof.Keys) -cnotcontains 'approved' -or @($ImageProof.Keys) -cnotcontains 'image' -or
        $ImageProof.sourceCommit -isnot [string] -or $ImageProof.sourceCommit -cne $SourceCommit -or
        $ImageProof.approved -isnot [bool] -or -not $ImageProof.approved -or
        $ImageProof.image -isnot [string] -or
        -not $ImageProof.image.StartsWith($ApprovedImageRepository + '@sha256:', [StringComparison]::Ordinal) -or
        $ImageProof.image.Substring($ApprovedImageRepository.Length) -cnotmatch '^@sha256:[a-f0-9]{64}$') {
        throw 'Offline image plan immutable image proof is invalid.'
    }
    # Reject duplicate JSON names rather than accepting the parser's last value.
    function Assert-UniqueJsonNames([System.Text.Json.JsonElement]$Element) {
        if ($Element.ValueKind -eq [System.Text.Json.JsonValueKind]::Object) {
            $names = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
            foreach ($property in $Element.EnumerateObject()) {
                if (-not $names.Add($property.Name)) { throw 'Duplicate JSON name.' }
                Assert-UniqueJsonNames $property.Value
            }
        } elseif ($Element.ValueKind -eq [System.Text.Json.JsonValueKind]::Array) {
            foreach ($item in $Element.EnumerateArray()) { Assert-UniqueJsonNames $item }
        }
    }
    $document = $null
    try {
        if ($DeploymentJson.Length -gt 1048576) { throw 'Document too large.' }
        $document = [System.Text.Json.JsonDocument]::Parse($DeploymentJson)
        Assert-UniqueJsonNames $document.RootElement
        $deployment = ConvertFrom-Json -InputObject $DeploymentJson -AsHashtable -DateKind String -ErrorAction Stop
        if ($deployment -isnot [hashtable] -or $deployment.apiVersion -cne 'apps/v1' -or
            $deployment.kind -cne 'Deployment' -or $deployment.metadata.name -cne 'legacy-maliev-file' -or
            $deployment.metadata.namespace -cne 'maliev-legacy' -or
            $deployment.spec.template.spec.serviceAccountName -cne 'legacy-maliev-file') { throw 'Foreign Deployment.' }
        $containers = $deployment.spec.template.spec.containers
        if ($containers -isnot [array] -or $containers.Count -eq 0) { throw 'Invalid containers.' }
        $names = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
        foreach ($container in $containers) {
            if ($container -isnot [hashtable] -or $container.name -isnot [string] -or
                [string]::IsNullOrWhiteSpace($container.name) -or -not $names.Add($container.name) -or
                $container.image -isnot [string] -or [string]::IsNullOrWhiteSpace($container.image)) { throw 'Invalid container.' }
        }
        $selected = @($containers | Where-Object { $_.name -ceq 'legacy-maliev-file-service' })
        if ($selected.Count -ne 1) { throw 'Missing target container.' }
    } catch { throw 'Offline image plan existing Deployment is invalid.' }
    finally { if ($null -ne $document) { $document.Dispose() } }
    $selected[0].image = $ImageProof.image
    return [pscustomobject]@{
        SchemaVersion = $ContractVersion
        SourceCommit = $SourceCommit
        Deployment = $deployment
        DeploymentAllowed = $false
        LiveAccepted = $false
    }
}
