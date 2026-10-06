param([Parameter(Mandatory)][string]$RepositoryRoot)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
. (Join-Path $RepositoryRoot 'scripts/New-OfflineImageOnlyDeploymentPlan.ps1')
$source = 'a' * 40
$repository = 'asia-southeast1-docker.pkg.dev/maliev-website/legacy/legacy-maliev-file-service'
$image = $repository + '@sha256:' + ('b' * 64)
$privateMarker = 'fixture-private-never-echo'
$original = @{
    apiVersion = 'apps/v1'; kind = 'Deployment'
    metadata = @{ name = 'legacy-maliev-file'; namespace = 'maliev-legacy' }
    spec = @{ replicas = 3; template = @{ spec = @{
        serviceAccountName = 'legacy-maliev-file'
        containers = @(@{
            name = 'legacy-maliev-file-service'; image = 'file:existing'
            env = @(@{ name = 'RECORDING_SETTING'; value = $privateMarker })
            envFrom = @(@{ configMapRef = @{ name = 'fixture-config' } })
            ports = @(@{ containerPort = 8080 })
            volumeMounts = @(@{ name = 'fixture-volume'; mountPath = '/fixture' })
        })
        imagePullSecrets = @(@{ name = 'fixture-pull' })
        volumes = @(@{ name = 'fixture-volume'; emptyDir = @{} })
    } } }
}
$json = ConvertTo-Json $original -Depth 40 -Compress
$passed = 0
function Invoke-Plan([string]$Document) {
    New-OfflineImageOnlyDeploymentPlan -DeploymentJson $Document -SourceCommit $source -ApprovedImageRepository $repository -ImageProof @{ sourceCommit = $source; approved = $true; image = $image }
}
function Assert-Preserved([Collections.IDictionary]$InputDocument) {
    $before = ConvertTo-Json $InputDocument -Depth 40 -Compress
    $plan = Invoke-Plan $before
    if ($plan.DeploymentAllowed -or $plan.LiveAccepted) { throw 'Resource authority changed.' }
    $container = $plan.Deployment.spec.template.spec.containers[0]
    if ($container.image -cne $image) { throw 'Selected image was not replaced.' }
    foreach ($array in @($plan.Deployment.spec.template.spec.containers, $container.env, $container.envFrom, $container.ports, $container.volumeMounts, $plan.Deployment.spec.template.spec.imagePullSecrets, $plan.Deployment.spec.template.spec.volumes)) {
        if ($array -isnot [array] -or $array.Count -ne 1) { throw 'Singleton array shape changed.' }
    }
    $container.image = 'file:existing'
    if ((ConvertTo-Json $plan.Deployment -Depth 40 -Compress) -cne $before) { throw 'Non-image metadata changed.' }
    if ((ConvertTo-Json $InputDocument -Depth 40 -Compress) -cne $before) { throw 'Input was mutated.' }
    $script:passed++
}
Assert-Preserved (ConvertFrom-Json $json -AsHashtable)
foreach ($mode in @('http', 'startup', 'tcp', 'grpc', 'null-optional')) {
    $fixture = ConvertFrom-Json $json -AsHashtable
    $container = $fixture.spec.template.spec.containers[0]
    $probe = switch ($mode) {
        'tcp' { @{ tcpSocket = @{ port = 'http'; host = '127.0.0.1' }; timeoutSeconds = 2 } }
        'grpc' { @{ grpc = @{ port = 8080; service = 'health' }; failureThreshold = 3 } }
        default { @{ httpGet = @{ port = 8080; path = '/health'; scheme = 'HTTP' }; periodSeconds = 10 } }
    }
    $container.readinessProbe = $probe
    $container.livenessProbe = $probe
    if ($mode -ceq 'startup') { $container.startupProbe = $probe }
    if ($mode -ceq 'null-optional') { $container.startupProbe = $null }
    Assert-Preserved $fixture
}
foreach ($reference in @('secretKeyRef', 'configMapKeyRef', 'fieldRef', 'resourceFieldRef')) {
    $fixture = ConvertFrom-Json $json -AsHashtable
    $value = switch ($reference) {
        'fieldRef' { @{ fieldPath = 'metadata.namespace' } }
        'resourceFieldRef' { @{ resource = 'limits.cpu'; divisor = '1' } }
        default { @{ name = 'fixture-config'; key = 'fixture-key'; optional = $false } }
    }
    $fixture.spec.template.spec.containers[0].env = @(@{ name = 'REFERENCE'; valueFrom = @{ $reference = $value } })
    Assert-Preserved $fixture
}
foreach ($mode in @('exec', 'headers', 'readiness-headers', 'liveness-exec', 'scalar', 'array', 'missing-action', 'unknown-probe', 'malformed-http', 'unknown-http', 'two-actions', 'missing-port', 'unknown-tcp', 'unknown-grpc', 'action-case', 'field-case', 'reference-null', 'reference-scalar', 'reference-array', 'reference-empty', 'reference-multiple', 'reference-unknown', 'reference-case', 'env-scalar', 'env-entry-scalar')) {
    $fixture = ConvertFrom-Json $json -AsHashtable
    $container = $fixture.spec.template.spec.containers[0]
    $container.startupProbe = @{ httpGet = @{ port = 8080 } }
    switch ($mode) {
        'exec' { $container.startupProbe = @{ exec = @{ command = @($privateMarker) } } }
        'headers' { $container.startupProbe.httpGet.httpHeaders = @(@{ name = $privateMarker; value = $privateMarker }) }
        'readiness-headers' { $container.readinessProbe = @{ httpGet = @{ port = 8080; httpHeaders = @(@{ name = $privateMarker; value = $privateMarker }) } } }
        'liveness-exec' { $container.livenessProbe = @{ exec = @{ command = @($privateMarker) } } }
        'scalar' { $container.startupProbe = $privateMarker }
        'array' { $container.startupProbe = @(@{ httpGet = @{ port = 8080 } }) }
        'missing-action' { $container.startupProbe = @{ periodSeconds = 10 } }
        'unknown-probe' { $container.startupProbe.private = $privateMarker }
        'malformed-http' { $container.startupProbe.httpGet = $privateMarker }
        'unknown-http' { $container.startupProbe.httpGet.private = $privateMarker }
        'two-actions' { $container.startupProbe.tcpSocket = @{ port = 8080 } }
        'missing-port' { $container.startupProbe.httpGet = @{ path = '/health' } }
        'unknown-tcp' { $container.startupProbe = @{ tcpSocket = @{ port = 8080; private = $privateMarker } } }
        'unknown-grpc' { $container.startupProbe = @{ grpc = @{ port = 8080; private = $privateMarker } } }
        'action-case' { $container.startupProbe = @{ HttpGet = @{ port = 8080 } } }
        'field-case' { $container.startupProbe = @{ httpGet = @{ Port = 8080 } } }
        'reference-null' { $container.env = @(@{ name = 'REFERENCE'; valueFrom = $null }) }
        'reference-scalar' { $container.env = @(@{ name = 'REFERENCE'; valueFrom = $privateMarker }) }
        'reference-array' { $container.env = @(@{ name = 'REFERENCE'; valueFrom = @(@{ fieldRef = @{ fieldPath = 'metadata.namespace' } }) }) }
        'reference-empty' { $container.env = @(@{ name = 'REFERENCE'; valueFrom = @{} }) }
        'reference-multiple' { $container.env = @(@{ name = 'REFERENCE'; valueFrom = @{ fieldRef = @{}; secretKeyRef = @{} } }) }
        'reference-unknown' { $container.env = @(@{ name = 'REFERENCE'; valueFrom = @{ private = $privateMarker } }) }
        'reference-case' { $container.env = @(@{ name = 'REFERENCE'; valueFrom = @{ FieldRef = @{} } }) }
        'env-scalar' { $container.env = $privateMarker }
        'env-entry-scalar' { $container.env = @($privateMarker) }
    }
    $caught = $null
    try { $null = Invoke-Plan (ConvertTo-Json $fixture -Depth 40 -Compress) } catch { $caught = $_.Exception }
    if ($null -eq $caught -or $caught.Message -cne 'Offline image plan existing Deployment is invalid.' -or $caught.ToString().Contains($privateMarker)) { throw "Unsafe metadata was not opaquely rejected: $mode" }
    $script:passed++
}
Write-Output "offline-image-metadata-controls:$passed passed"
