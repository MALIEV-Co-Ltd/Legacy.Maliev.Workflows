param([Parameter(Mandatory)][string]$RepositoryRoot)
$ErrorActionPreference = 'Stop'
. (Join-Path $RepositoryRoot 'scripts/New-OfflineImageOnlyDeploymentPlan.ps1')
$source = 'a' * 40
$repository = 'asia-southeast1-docker.pkg.dev/maliev-website/legacy/legacy-maliev-file-service'
$image = $repository + '@sha256:' + ('b' * 64)
$original = @{
    apiVersion = 'apps/v1'; kind = 'Deployment'
    metadata = @{ name = 'legacy-maliev-file'; namespace = 'maliev-legacy'; annotations = @{ private = 'canary-never-echo'; recorded = '2026-10-05T01:02:03.0000+07:00' } }
    spec = @{ replicas = 3; template = @{ metadata = @{ labels = @{ app = 'file' } }; spec = @{
        serviceAccountName = 'legacy-maliev-file'; automountServiceAccountToken = $false
        containers = @(
            @{ name = 'sidecar'; image = 'sidecar:existing'; env = @(@{ name = 'SIDE'; value = 'keep' }) },
            @{ name = 'legacy-maliev-file-service'; image = 'file:existing'; env = @(@{ name = 'PRIVATE'; value = 'canary-never-echo' }); resources = @{ limits = @{ cpu = '1' } } }
        )
    } } }
}
$json = ConvertTo-Json $original -Depth 30 -Compress
function Invoke-Plan($Document = $json, $Proof = @{ sourceCommit = $source; image = $image; approved = $true }, $Commit = $source, $Repo = $repository, $Version = 'legacy-file-image-only/v1') {
    New-OfflineImageOnlyDeploymentPlan -DeploymentJson $Document -SourceCommit $Commit -ApprovedImageRepository $Repo -ImageProof $Proof -ContractVersion $Version
}
$plan = Invoke-Plan
if ($plan.DeploymentAllowed -or $plan.LiveAccepted -or $plan.SourceCommit -cne $source -or $plan.SchemaVersion -cne 'legacy-file-image-only/v1') { throw 'Plan flags mismatch.' }
$restored = $plan.Deployment
$restored.spec.template.spec.containers[1].image = 'file:existing'
if ((ConvertTo-Json $restored -Depth 30 -Compress) -cne $json) { throw 'Non-image value changed.' }
if ((ConvertTo-Json $original -Depth 30 -Compress) -cne $json) { throw 'Input mutated.' }
$idempotent = Invoke-Plan
$again = Invoke-Plan -Document (ConvertTo-Json $idempotent.Deployment -Depth 30 -Compress)
if ((ConvertTo-Json $again.Deployment -Depth 30 -Compress) -cne (ConvertTo-Json $idempotent.Deployment -Depth 30 -Compress)) { throw 'Plan not idempotent.' }
$count = 2
function Assert-Rejected([scriptblock]$Action) {
    $failed = $false
    try { $null = & $Action } catch {
        $failed = $true
        if ($_.Exception.Message.Contains('canary-never-echo')) { throw 'Private content echoed.' }
    }
    if (-not $failed) { throw 'Invalid input was accepted.' }
    $script:count++
}
foreach ($path in @('namespace', 'name', 'ksa', 'container', 'duplicate', 'missing', 'object', 'emptyimage', 'kind')) {
    $bad = ConvertFrom-Json $json -AsHashtable
    switch ($path) {
        namespace { $bad.metadata.namespace = 'foreign' }
        name { $bad.metadata.name = 'foreign' }
        ksa { $bad.spec.template.spec.serviceAccountName = 'foreign' }
        container { $bad.spec.template.spec.containers[1].name = 'foreign' }
        duplicate { $bad.spec.template.spec.containers[0].name = 'legacy-maliev-file-service' }
        missing { $bad.spec.template.spec.Remove('containers') }
        object { $bad.spec.template.spec.containers = $bad.spec.template.spec.containers[1] }
        emptyimage { $bad.spec.template.spec.containers[0].image = '' }
        kind { $bad.kind = 'StatefulSet' }
    }
    Assert-Rejected { Invoke-Plan -Document (ConvertTo-Json $bad -Depth 30 -Compress) }
}
foreach ($badJson in @('null', '{}', '{invalid-canary-never-echo', $json.Replace('"kind":"Deployment"', '"kind":"Deployment","kind":"Deployment"'))) {
    Assert-Rejected { Invoke-Plan -Document $badJson }
}
foreach ($field in @('source', 'approved', 'extra', 'tag', 'foreign', 'upper', 'case')) {
    $proof = @{ sourceCommit = $source; image = $image; approved = $true }
    switch ($field) {
        source { $proof.sourceCommit = 'c' * 40 }
        approved { $proof.approved = 'true' }
        extra { $proof.extra = 'canary-never-echo' }
        tag { $proof.image = $repository + ':latest' }
        foreign { $proof.image = 'foreign@sha256:' + ('b' * 64) }
        upper { $proof.image = $repository + '@sha256:' + ('B' * 64) }
        case { $proof.Remove('sourceCommit'); $proof.SourceCommit = $source }
    }
    Assert-Rejected { Invoke-Plan -Proof $proof }
}
Assert-Rejected { Invoke-Plan -Commit ('A' * 40) }
Assert-Rejected { Invoke-Plan -Repo 'foreign' }
Assert-Rejected { Invoke-Plan -Version 'v2' }
Write-Output "offline-image-only-controls:$count passed"
