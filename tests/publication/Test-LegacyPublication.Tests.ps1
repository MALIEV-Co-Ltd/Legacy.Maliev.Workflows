$ErrorActionPreference = 'Stop'

$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$GateScript = Join-Path $RepositoryRoot 'scripts\Test-LegacyPublication.ps1'
$PublishScript = Join-Path $RepositoryRoot 'scripts\Publish-LegacyRepository.ps1'
$RealGit = (Get-Command git -CommandType Application | Select-Object -First 1).Source

function Invoke-Process {
    param([string]$WorkingDirectory, [string]$FilePath, [string[]]$ArgumentList, [hashtable]$Environment = @{})

    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $FilePath
    $startInfo.WorkingDirectory = $WorkingDirectory
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    foreach ($argument in $ArgumentList) { [void]$startInfo.ArgumentList.Add($argument) }
    foreach ($entry in $Environment.GetEnumerator()) { $startInfo.Environment[$entry.Key] = [string]$entry.Value }

    $process = [System.Diagnostics.Process]::Start($startInfo)
    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd()
    $process.WaitForExit()
    [pscustomobject]@{ ExitCode = $process.ExitCode; Output = $stdout + $stderr }
}

function Invoke-Git {
    param([string]$RepositoryPath, [Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    $result = Invoke-Process $RepositoryPath $RealGit $Arguments
    if ($result.ExitCode -ne 0) { throw $result.Output }
    $result.Output.Trim()
}

function New-PublicationFixture {
    $container = Join-Path ([System.IO.Path]::GetTempPath()) ('legacy-publication-' + [guid]::NewGuid().ToString('N'))
    $repository = Join-Path $container 'candidate'
    $privateSource = Join-Path $container 'private-source'
    $tools = Join-Path $container 'tools'
    $bare = Join-Path $container 'published.git'
    New-Item -ItemType Directory -Path $repository, $privateSource, $tools | Out-Null

    Invoke-Git $repository init -b main | Out-Null
    Invoke-Git $repository config user.name Fixture | Out-Null
    Invoke-Git $repository config user.email fixture@example.invalid | Out-Null
    Invoke-Git $repository config core.autocrlf false | Out-Null

    Invoke-Git $privateSource init -b main | Out-Null
    Invoke-Git $privateSource config user.name Fixture | Out-Null
    Invoke-Git $privateSource config user.email fixture@example.invalid | Out-Null
    Set-Content (Join-Path $privateSource 'private-source.txt') 'private source fixture with unrelated objects'
    Invoke-Git $privateSource add . | Out-Null
    Invoke-Git $privateSource commit -m 'private source root' | Out-Null

    Set-Content (Join-Path $repository 'Legacy.Maliev.Fixture.slnx') '<Solution />'
    New-Item -ItemType Directory -Path (Join-Path $repository '.github\workflows') | Out-Null
    @'
name: validate
on:
  pull_request:
permissions:
  contents: read
jobs:
  validate:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@ac593985615ec2ede58e132d2e21d2b1cbd6127c
        with:
          persist-credentials: false
      - run: dotnet test
'@ | Set-Content (Join-Path $repository '.github\workflows\validate.yml')
    Set-Content (Join-Path $repository 'README.md') 'fresh public fixture'

    @'
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
$tree = Get-ChildItem -LiteralPath $env:FIXTURE_REPOSITORY -File -Recurse -Force |
    Where-Object { $_.FullName -notmatch '[\\/]\.git[\\/]' } |
    ForEach-Object { Get-Content -LiteralPath $_.FullName -Raw -ErrorAction SilentlyContinue } | Out-String
$source = if ($Arguments -contains 'git') {
    & $env:REAL_GIT -C $env:FIXTURE_REPOSITORY log -p --all 2>$null | Out-String
} else {
    $tree
}
if ($source -match 'github_pat_[A-Za-z0-9_]+') {
    [Console]::Error.WriteLine('leak: ' + $Matches[0])
    exit 1
}
exit 0
'@ | Set-Content (Join-Path $tools 'go.ps1')

    @'
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
Add-Content -LiteralPath $env:DOTNET_LOG -Value ($Arguments -join ' ')
if (($Arguments -join ' ') -match 'package --vulnerable') { 'The following sources were used: fixture'; }
exit 0
'@ | Set-Content (Join-Path $tools 'dotnet.ps1')

    @'
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
$joined = $Arguments -join ' '
Add-Content -LiteralPath $env:GH_LOG -Value $joined

function Stop-StrictMock([string]$Message) {
    [Console]::Error.WriteLine('strict gh mock rejected call: ' + $Message)
    exit 97
}

if ($joined -ceq 'repo view MALIEV-Co-Ltd/Legacy.Maliev.Fixture --json isEmpty,visibility,defaultBranchRef') {
    if ($env:GH_REMOTE_STATE -ceq 'missing') { exit 1 }
    if ($env:GH_REMOTE_STATE -ceq 'empty') { '{"isEmpty":true,"visibility":"PUBLIC","defaultBranchRef":null}'; exit 0 }
    if ($env:GH_REMOTE_STATE -ceq 'non-empty') { '{"isEmpty":false,"visibility":"PUBLIC","defaultBranchRef":{"name":"main"}}'; exit 0 }
    Stop-StrictMock 'unknown remote state'
}
if ($Arguments.Count -eq 10 -and $Arguments[0] -eq 'repo' -and $Arguments[1] -eq 'create' -and
    $Arguments[2] -ceq 'MALIEV-Co-Ltd/Legacy.Maliev.Fixture' -and $Arguments[3] -ceq '--public' -and
    $Arguments[4] -ceq '--source' -and $Arguments[5] -ceq $env:FIXTURE_REPOSITORY -and
    $Arguments[6] -ceq '--remote' -and $Arguments[7] -ceq 'origin' -and
    $Arguments[8] -ceq '--description' -and $Arguments[9] -ceq 'Migrated MALIEV legacy service with fresh public history') {
    $remoteUrl = 'https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Fixture.git'
    & $env:REAL_GIT -C $env:FIXTURE_REPOSITORY remote add origin $remoteUrl
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $env:REAL_GIT -C $env:FIXTURE_REPOSITORY config "url.$env:BARE_REPOSITORY.insteadOf" $remoteUrl
    exit $LASTEXITCODE
}
if ($Arguments.Count -eq 12 -and $Arguments[0] -ceq 'pr' -and $Arguments[1] -ceq 'list' -and
    $Arguments[2] -ceq '--repo' -and $Arguments[3] -ceq 'MALIEV-Co-Ltd/Legacy.Maliev.Fixture' -and
    $Arguments[4] -ceq '--base' -and $Arguments[5] -ceq 'main' -and
    $Arguments[6] -ceq '--head' -and $Arguments[7] -ceq "publication/$env:CANDIDATE_SHA" -and
    $Arguments[8] -ceq '--state' -and $Arguments[9] -ceq 'open' -and
    $Arguments[10] -ceq '--json' -and $Arguments[11] -ceq 'number,headRefOid,baseRefName,headRefName,state') {
    $remoteMain = & $env:REAL_GIT --git-dir $env:BARE_REPOSITORY rev-parse refs/heads/main
    $remoteCandidate = & $env:REAL_GIT --git-dir $env:BARE_REPOSITORY rev-parse "refs/heads/publication/$env:CANDIDATE_SHA"
    if ($remoteMain -cne $env:ROOT_SHA -or $remoteCandidate -cne $env:CANDIDATE_SHA) {
        Stop-StrictMock 'candidate history reached the wrong remote ref before PR validation'
    }
    Set-Content -LiteralPath $env:PRE_MERGE_STATE_FILE -Value 'root-only-main-and-exact-candidate-branch'
    if (Test-Path -LiteralPath $env:PR_STATE_FILE) {
        '[{"number":17,"headRefOid":"' + $env:CANDIDATE_SHA + '","baseRefName":"main","headRefName":"publication/' + $env:CANDIDATE_SHA + '","state":"OPEN"}]'
    } else { '[]' }
    exit 0
}
if ($Arguments.Count -eq 12 -and $Arguments[0] -ceq 'pr' -and $Arguments[1] -ceq 'create' -and
    $Arguments[2] -ceq '--repo' -and $Arguments[3] -ceq 'MALIEV-Co-Ltd/Legacy.Maliev.Fixture' -and
    $Arguments[4] -ceq '--base' -and $Arguments[5] -ceq 'main' -and
    $Arguments[6] -ceq '--head' -and $Arguments[7] -ceq "publication/$env:CANDIDATE_SHA" -and
    $Arguments[8] -ceq '--title' -and $Arguments[9] -ceq "Publish Legacy.Maliev.Fixture at $env:CANDIDATE_SHA" -and
    $Arguments[10] -ceq '--body' -and $Arguments[11] -ceq 'Bootstrap publication through the required pull-request validation boundary.') {
    Set-Content -LiteralPath $env:PR_STATE_FILE -Value 'created'
    'https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Fixture/pull/17'
    exit 0
}
if ($Arguments.Count -eq 14 -and $Arguments[0] -eq 'run' -and $Arguments[1] -eq 'list' -and
    $Arguments[2] -ceq '--repo' -and $Arguments[3] -ceq 'MALIEV-Co-Ltd/Legacy.Maliev.Fixture' -and
    $Arguments[4] -ceq '--workflow' -and $Arguments[5] -ceq 'validate.yml' -and
    $Arguments[6] -ceq '--commit' -and $Arguments[7] -match '^[0-9a-f]{40}$' -and
    $Arguments[7] -ceq $env:CANDIDATE_SHA -and $Arguments[8] -ceq '--event' -and
    $Arguments[9] -ceq 'pull_request' -and $Arguments[10] -ceq '--limit' -and
    $Arguments[11] -ceq '20' -and $Arguments[12] -ceq '--json' -and
    $Arguments[13] -ceq 'databaseId,status,conclusion,name,headSha,event') {
    '[{"databaseId":42,"status":"completed","conclusion":"success","name":"validate","headSha":"' + $env:CANDIDATE_SHA + '","event":"pull_request"}]'
    exit 0
}
if ($joined -ceq 'run watch 42 --repo MALIEV-Co-Ltd/Legacy.Maliev.Fixture --exit-status') { exit 0 }
if ($joined -ceq 'run view 42 --repo MALIEV-Co-Ltd/Legacy.Maliev.Fixture --json jobs') {
    '{"jobs":[{"name":"validate / validate","status":"completed","conclusion":"success"}]}'
    exit 0
}
if ($joined -ceq "pr merge 17 --repo MALIEV-Co-Ltd/Legacy.Maliev.Fixture --squash --delete-branch --match-head-commit $env:CANDIDATE_SHA") {
    $tree = & $env:REAL_GIT --git-dir $env:BARE_REPOSITORY rev-parse "$env:CANDIDATE_SHA`^{tree}"
    $env:GIT_AUTHOR_NAME = 'Fixture'
    $env:GIT_AUTHOR_EMAIL = 'fixture@example.invalid'
    $env:GIT_COMMITTER_NAME = 'Fixture'
    $env:GIT_COMMITTER_EMAIL = 'fixture@example.invalid'
    $mergedSha = 'bootstrap publication' | & $env:REAL_GIT --git-dir $env:BARE_REPOSITORY commit-tree $tree -p $env:ROOT_SHA
    if ($LASTEXITCODE -ne 0 -or $mergedSha -notmatch '^[0-9a-f]{40}$') { Stop-StrictMock 'unable to simulate squash merge' }
    & $env:REAL_GIT --git-dir $env:BARE_REPOSITORY update-ref refs/heads/main $mergedSha $env:ROOT_SHA
    if ($LASTEXITCODE -ne 0) { Stop-StrictMock 'unable to update simulated merged main' }
    & $env:REAL_GIT --git-dir $env:BARE_REPOSITORY update-ref -d "refs/heads/publication/$env:CANDIDATE_SHA"
    Set-Content -LiteralPath $env:MERGED_SHA_FILE -Value $mergedSha
    exit 0
}
if ($joined -ceq 'api repos/MALIEV-Co-Ltd/Legacy.Maliev.Fixture/commits/main --jq .sha') {
    if (-not (Test-Path -LiteralPath $env:MERGED_SHA_FILE)) { Stop-StrictMock 'main SHA read before squash merge' }
    Get-Content -LiteralPath $env:MERGED_SHA_FILE -Raw
    exit 0
}

$repositoryEndpoint = 'repos/MALIEV-Co-Ltd/Legacy.Maliev.Fixture'
$protectionEndpoint = $repositoryEndpoint + '/branches/main/protection'
$environmentEndpoint = $repositoryEndpoint + '/environments/production'
$vulnerabilityEndpoint = $repositoryEndpoint + '/private-vulnerability-reporting'

if ($joined -ceq "api $vulnerabilityEndpoint --method PUT") { exit 0 }
if ($joined -ceq "api $vulnerabilityEndpoint") { '{"enabled":true}'; exit 0 }
if ($joined -ceq "api $repositoryEndpoint") {
    $visibility = if ($env:GH_VISIBILITY) { $env:GH_VISIBILITY } else { 'public' }
    '{"visibility":"' + $visibility + '","default_branch":"main"}'
    exit 0
}
if ($joined -ceq "api $protectionEndpoint") {
    $conversationResolution = if ($env:GH_PROTECTION_MISMATCH) { 'false' } else { 'true' }
    '{"required_status_checks":{"strict":true,"contexts":["validate / validate"]},"enforce_admins":{"enabled":true},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"required_approving_review_count":1},"required_linear_history":{"enabled":true},"required_conversation_resolution":{"enabled":' + $conversationResolution + '},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false}}'
    exit 0
}
if ($joined -ceq "api $environmentEndpoint") {
    $waitTimer = if ($env:GH_ENVIRONMENT_MISMATCH) { 5 } else { 0 }
    '{"name":"production","protection_rules":[{"type":"wait_timer","wait_timer":' + $waitTimer + '},{"type":"required_reviewers","prevent_self_review":true,"reviewers":[]},{"type":"branch_policy"}],"deployment_branch_policy":{"protected_branches":true,"custom_branch_policies":false}}'
    exit 0
}
if ($Arguments.Count -eq 6 -and $Arguments[0] -ceq 'api' -and $Arguments[2] -ceq '--method' -and
    $Arguments[3] -ceq 'PUT' -and $Arguments[4] -ceq '--input' -and (Test-Path -LiteralPath $Arguments[5])) {
    $payload = Get-Content -LiteralPath $Arguments[5] -Raw | ConvertFrom-Json
    if ($Arguments[1] -ceq $protectionEndpoint) {
        if (@($payload.psobject.Properties).Count -ne 8 -or
            $payload.required_status_checks.strict -ne $true -or @($payload.required_status_checks.contexts).Count -ne 1 -or
            $payload.required_status_checks.contexts[0] -cne 'validate / validate' -or $payload.enforce_admins -ne $true -or
            $payload.required_pull_request_reviews.dismiss_stale_reviews -ne $true -or
            $payload.required_pull_request_reviews.required_approving_review_count -ne 1 -or
            $payload.required_linear_history -ne $true -or $payload.allow_force_pushes -ne $false -or
            $payload.allow_deletions -ne $false -or $payload.required_conversation_resolution -ne $true) {
            Stop-StrictMock 'branch protection payload mismatch'
        }
        exit 0
    }
    if ($Arguments[1] -ceq $environmentEndpoint) {
        if (@($payload.psobject.Properties).Count -ne 4 -or $payload.wait_timer -ne 0 -or
            $payload.prevent_self_review -ne $true -or @($payload.reviewers).Count -ne 0 -or
            $payload.deployment_branch_policy.protected_branches -ne $true -or
            $payload.deployment_branch_policy.custom_branch_policies -ne $false) {
            Stop-StrictMock 'environment payload mismatch'
        }
        exit 0
    }
}
Stop-StrictMock $joined
'@ | Set-Content (Join-Path $tools 'gh.ps1')

    Invoke-Git $repository add . | Out-Null
    Invoke-Git $repository commit -m 'fresh public root' | Out-Null
    $rootSha = Invoke-Git $repository rev-parse HEAD
    Add-Content (Join-Path $repository 'README.md') 'candidate publication change'
    Invoke-Git $repository add README.md | Out-Null
    Invoke-Git $repository commit -m 'candidate publication change' | Out-Null
    $headSha = Invoke-Git $repository rev-parse HEAD
    Invoke-Process $container $RealGit @('init', '--bare', $bare) | Out-Null

    [pscustomobject]@{
        Container = $container
        Repository = $repository
        PrivateSource = $privateSource
        Tools = $tools
        Bare = $bare
        RootSha = $rootSha
        HeadSha = $headSha
        DotnetLog = Join-Path $container 'dotnet.log'
        GhLog = Join-Path $container 'gh.log'
        PrState = Join-Path $container 'pr-state.txt'
        MergedSha = Join-Path $container 'merged-sha.txt'
        PreMergeState = Join-Path $container 'pre-merge-state.txt'
    }
}

function Invoke-GateFixture {
    param($Fixture, [string]$Name = 'MALIEV-Co-Ltd/Legacy.Maliev.Fixture', [string]$PrivateSourceRepositoryPath = $Fixture.PrivateSource, [switch]$IndependentRepository)
    $path = $Fixture.Tools + [IO.Path]::PathSeparator + $env:PATH
    $arguments = @('-NoLogo', '-NoProfile', '-File', $GateScript, '-RepositoryPath', $Fixture.Repository, '-GitHubRepository', $Name)
    if ($PrivateSourceRepositoryPath) { $arguments += @('-PrivateSourceRepositoryPath', $PrivateSourceRepositoryPath) }
    if ($IndependentRepository) { $arguments += '-IndependentRepository' }
    Invoke-Process $Fixture.Repository 'pwsh' $arguments @{
        PATH = $path
        REAL_GIT = $RealGit
        FIXTURE_REPOSITORY = $Fixture.Repository
        DOTNET_LOG = $Fixture.DotnetLog
    }
}

function Invoke-PublisherFixture {
    param(
        $Fixture,
        [string]$Visibility = '',
        [switch]$ProtectionMismatch,
        [switch]$EnvironmentMismatch,
        [switch]$OmitPrivateSource,
        [ValidateSet('missing', 'empty', 'non-empty')][string]$RemoteState = 'missing',
        [switch]$ExistingPr)
    $path = $Fixture.Tools + [IO.Path]::PathSeparator + $env:PATH
    if ($RemoteState -cne 'missing') {
        $remoteUrl = 'https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Fixture.git'
        Invoke-Git $Fixture.Repository remote add origin $remoteUrl | Out-Null
        Invoke-Git $Fixture.Repository config "url.$($Fixture.Bare).insteadOf" $remoteUrl | Out-Null
    }
    if ($RemoteState -ceq 'non-empty') {
        Invoke-Git $Fixture.Repository push origin "$($Fixture.RootSha):refs/heads/main" | Out-Null
    }
    if ($ExistingPr) { Set-Content -LiteralPath $Fixture.PrState -Value 'existing' }
    $arguments = @('-NoLogo', '-NoProfile', '-File', $PublishScript, '-RepositoryPath', $Fixture.Repository, '-GitHubRepository', 'MALIEV-Co-Ltd/Legacy.Maliev.Fixture', '-WaitTimeoutSeconds', '5', '-PollIntervalSeconds', '0')
    if (-not $OmitPrivateSource) { $arguments += @('-PrivateSourceRepositoryPath', $Fixture.PrivateSource) }
    Invoke-Process $Fixture.Repository 'pwsh' $arguments @{
        PATH = $path
        REAL_GIT = $RealGit
        FIXTURE_REPOSITORY = $Fixture.Repository
        BARE_REPOSITORY = $Fixture.Bare
        DOTNET_LOG = $Fixture.DotnetLog
        GH_LOG = $Fixture.GhLog
        GH_REMOTE_STATE = $RemoteState
        ROOT_SHA = $Fixture.RootSha
        CANDIDATE_SHA = $Fixture.HeadSha
        PR_STATE_FILE = $Fixture.PrState
        MERGED_SHA_FILE = $Fixture.MergedSha
        PRE_MERGE_STATE_FILE = $Fixture.PreMergeState
        GH_VISIBILITY = $Visibility
        GH_PROTECTION_MISMATCH = if ($ProtectionMismatch) { 'true' } else { '' }
        GH_ENVIRONMENT_MISMATCH = if ($EnvironmentMismatch) { 'true' } else { '' }
    }
}

Describe 'Test-LegacyPublication' {
    It 'passes a clean fresh-history repository and runs every mandatory quality gate' {
        $fixture = New-PublicationFixture
        try {
            $result = Invoke-GateFixture $fixture
            $result.ExitCode | Should Be 0
            $result.Output | Should Match 'Publication gate passed'
            $log = Get-Content $fixture.DotnetLog -Raw
            $log | Should Match 'restore'
            $log | Should Match 'build.*--no-restore'
            $log | Should Match 'test.*--no-build.*--no-restore'
            $log | Should Match 'format.*--verify-no-changes.*--no-restore'
            $log | Should Match 'package --vulnerable.*--include-transitive.*--no-restore'
        } finally { Remove-Item $fixture.Container -Recurse -Force }
    }

    It 'rejects any repository name outside the exact MALIEV legacy namespace' {
        $fixture = New-PublicationFixture
        try {
            $result = Invoke-GateFixture $fixture 'someone/Legacy.Maliev.Fixture'
            $result.ExitCode | Should Not Be 0
            $result.Output | Should Match 'exact MALIEV legacy namespace'
        }
        finally { Remove-Item $fixture.Container -Recurse -Force }
    }

    It 'rejects a maliev-web remote' {
        $fixture = New-PublicationFixture
        try {
            Invoke-Git $fixture.Repository remote add source https://github.com/MALIEV-Co-Ltd/maliev-web.git | Out-Null
            $result = Invoke-GateFixture $fixture
            $result.ExitCode | Should Not Be 0
            $result.Output | Should Match 'private source history'
        } finally { Remove-Item $fixture.Container -Recurse -Force }
    }

    It 'rejects multiple root histories merged into the candidate' {
        $fixture = New-PublicationFixture
        try {
            $orphan = Join-Path $fixture.Container 'orphan'
            New-Item -ItemType Directory $orphan | Out-Null
            Invoke-Git $orphan init -b source | Out-Null
            Invoke-Git $orphan config user.name Fixture | Out-Null
            Invoke-Git $orphan config user.email fixture@example.invalid | Out-Null
            Set-Content (Join-Path $orphan 'source.txt') 'source'
            Invoke-Git $orphan add . | Out-Null
            Invoke-Git $orphan commit -m 'source root' | Out-Null
            Invoke-Git $fixture.Repository remote add source $orphan | Out-Null
            Invoke-Git $fixture.Repository fetch source source | Out-Null
            Invoke-Git $fixture.Repository merge --allow-unrelated-histories --no-edit source/source | Out-Null
            Invoke-Git $fixture.Repository remote remove source | Out-Null
            $result = Invoke-GateFixture $fixture
            $result.ExitCode | Should Not Be 0
            $result.Output | Should Match 'exactly one fresh root'
        } finally { Remove-Item $fixture.Container -Recurse -Force }
    }

    It 'rejects tracked local environment and key material' {
        $fixture = New-PublicationFixture
        try {
            Set-Content (Join-Path $fixture.Repository '.env') 'SAFE_FIXTURE=value'
            Invoke-Git $fixture.Repository add .env | Out-Null
            Invoke-Git $fixture.Repository commit -m 'unsafe env' | Out-Null
            $result = Invoke-GateFixture $fixture
            $result.ExitCode | Should Not Be 0
            $result.Output | Should Match 'prohibited secret material'
        } finally { Remove-Item $fixture.Container -Recurse -Force }
    }

    It 'rejects a prohibited environment filename deleted from the current tree' {
        $fixture = New-PublicationFixture
        try {
            Set-Content (Join-Path $fixture.Repository '.env') 'NON_SECRET_FIXTURE=value'
            Invoke-Git $fixture.Repository add .env | Out-Null
            Invoke-Git $fixture.Repository commit -m 'historical environment file' | Out-Null
            Remove-Item (Join-Path $fixture.Repository '.env')
            Invoke-Git $fixture.Repository add -u | Out-Null
            Invoke-Git $fixture.Repository commit -m 'remove environment file' | Out-Null
            $result = Invoke-GateFixture $fixture
            $result.ExitCode | Should Not Be 0
            $result.Output | Should Match 'prohibited filename in complete history'
        } finally { Remove-Item $fixture.Container -Recurse -Force }
    }

    It 'rejects a secret removed from the current tree and never prints the secret' {
        $fixture = New-PublicationFixture
        try {
            $token = 'github_pat_' + ('A' * 90)
            Set-Content (Join-Path $fixture.Repository 'temporary.txt') $token
            Invoke-Git $fixture.Repository add temporary.txt | Out-Null
            Invoke-Git $fixture.Repository commit -m 'temporary credential' | Out-Null
            Remove-Item (Join-Path $fixture.Repository 'temporary.txt')
            Invoke-Git $fixture.Repository add -u | Out-Null
            Invoke-Git $fixture.Repository commit -m 'remove credential' | Out-Null
            $result = Invoke-GateFixture $fixture
            $result.ExitCode | Should Not Be 0
            $result.Output | Should Match 'secret scan failed'
            $result.Output | Should Not Match ([regex]::Escape($token))
        } finally { Remove-Item $fixture.Container -Recurse -Force }
    }

    It 'rejects unpinned Actions, unsafe PR permissions, secret access, and direct cluster commands' {
        $fixture = New-PublicationFixture
        try {
            @'
name: unsafe
on: pull_request_target
permissions:
  contents: write
jobs:
  unsafe:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@main
      - run: kubectl apply -f manifest.yml
        env:
          TOKEN: ${{ secrets.DEPLOY_TOKEN }}
'@ | Set-Content (Join-Path $fixture.Repository '.github\workflows\validate.yml')
            Invoke-Git $fixture.Repository add . | Out-Null
            Invoke-Git $fixture.Repository commit -m 'unsafe workflow' | Out-Null
            $result = Invoke-GateFixture $fixture
            $result.ExitCode | Should Not Be 0
            $result.Output | Should Match 'workflow security contract'
        } finally { Remove-Item $fixture.Container -Recurse -Force }
    }

    It 'rejects a pull-request validation workflow with any additional trigger' {
        $fixture = New-PublicationFixture
        try {
            $workflowPath = Join-Path $fixture.Repository '.github\workflows\validate.yml'
            $source = (Get-Content $workflowPath -Raw) -replace '  pull_request:', "  pull_request:`n  push:"
            Set-Content $workflowPath $source
            Invoke-Git $fixture.Repository add $workflowPath | Out-Null
            Invoke-Git $fixture.Repository commit -m 'unsafe additional trigger' | Out-Null
            $result = Invoke-GateFixture $fixture
            $result.ExitCode | Should Not Be 0
            $result.Output | Should Match 'workflow security contract'
        } finally { Remove-Item $fixture.Container -Recurse -Force }
    }

    It 'rejects a valid malicious flow-style workflow before policy inspection' {
        $fixture = New-PublicationFixture
        try {
            @'
name: unsafe-flow
on: { pull_request: {} }
permissions: { contents: write }
jobs: { validate: { runs-on: ubuntu-24.04, steps: [{ uses: actions/checkout@ac593985615ec2ede58e132d2e21d2b1cbd6127c, with: { persist-credentials: true } }] } }
'@ | Set-Content (Join-Path $fixture.Repository '.github\workflows\validate.yml')
            Invoke-Git $fixture.Repository add . | Out-Null
            Invoke-Git $fixture.Repository commit -m 'obfuscated unsafe workflow' | Out-Null
            $result = Invoke-GateFixture $fixture
            $result.ExitCode | Should Not Be 0
            $result.Output | Should Match 'safe block-style YAML subset'
        } finally { Remove-Item $fixture.Container -Recurse -Force }
    }

    It 'rejects multi-document anchors aliases and quoted policy keys' {
        $cases = @(
            "name: first`non:`n  pull_request:`n---`nname: second`n",
            "name: anchored`non:`n  pull_request:`npermissions: &policy`n  contents: read`njobs: *policy`n",
            "name: quoted`n`"on`":`n  `"pull_request`":`n`"permissions`":`n  `"contents`": write`n"
        )
        foreach ($source in $cases) {
            $fixture = New-PublicationFixture
            try {
                Set-Content (Join-Path $fixture.Repository '.github\workflows\validate.yml') $source
                Invoke-Git $fixture.Repository add . | Out-Null
                Invoke-Git $fixture.Repository commit -m 'unsupported yaml policy syntax' | Out-Null
                $result = Invoke-GateFixture $fixture
                $result.ExitCode | Should Not Be 0
                $result.Output | Should Match 'safe block-style YAML subset'
            } finally { Remove-Item $fixture.Container -Recurse -Force }
        }
    }

    It 'rejects candidate commits that intersect the supplied private source object database' {
        $fixture = New-PublicationFixture
        try {
            $result = Invoke-GateFixture $fixture -PrivateSourceRepositoryPath $fixture.Repository
            $result.ExitCode | Should Not Be 0
            $result.Output | Should Match 'commit object also exists in the private source'
        } finally { Remove-Item $fixture.Container -Recurse -Force }
    }

    It 'rejects an intersecting commit that is unreachable but remains in the private source object database' {
        $fixture = New-PublicationFixture
        try {
            Invoke-Git $fixture.PrivateSource fetch $fixture.Repository main | Out-Null
            Remove-Item (Join-Path $fixture.PrivateSource '.git\FETCH_HEAD') -Force
            $result = Invoke-GateFixture $fixture
            $result.ExitCode | Should Not Be 0
            $result.Output | Should Match 'commit object also exists in the private source'
        } finally { Remove-Item $fixture.Container -Recurse -Force }
    }

    It 'requires a private source path for an extracted service repository' {
        $fixture = New-PublicationFixture
        try {
            $result = Invoke-GateFixture $fixture -PrivateSourceRepositoryPath ''
            $result.ExitCode | Should Not Be 0
            $result.Output | Should Match 'private source repository path is required'
        } finally { Remove-Item $fixture.Container -Recurse -Force }
    }

    It 'allows independent mode only for the exact shared Workflows repository' {
        $fixture = New-PublicationFixture
        try {
            $result = Invoke-GateFixture $fixture -PrivateSourceRepositoryPath '' -IndependentRepository
            $result.ExitCode | Should Not Be 0
            $result.Output | Should Match 'only MALIEV-Co-Ltd/Legacy.Maliev.Workflows may use independent mode'
        } finally { Remove-Item $fixture.Container -Recurse -Force }
    }

    It 'rejects a dirty working tree' {
        $fixture = New-PublicationFixture
        try {
            Add-Content (Join-Path $fixture.Repository 'README.md') 'dirty'
            $result = Invoke-GateFixture $fixture
            $result.ExitCode | Should Not Be 0
            $result.Output | Should Match 'working tree must be clean'
        } finally { Remove-Item $fixture.Container -Recurse -Force }
    }

    It 'rejects PR checkout credential persistence by omission' {
        $fixture = New-PublicationFixture
        try {
            $workflowPath = Join-Path $fixture.Repository '.github\workflows\validate.yml'
            $source = (Get-Content $workflowPath -Raw) -replace '(?ms)\s+with:\s+persist-credentials:\s+false', ''
            Set-Content $workflowPath $source
            Invoke-Git $fixture.Repository add . | Out-Null
            Invoke-Git $fixture.Repository commit -m 'persist checkout credential' | Out-Null
            $result = Invoke-GateFixture $fixture
            $result.ExitCode | Should Not Be 0
            $result.Output | Should Match 'workflow security contract'
        } finally { Remove-Item $fixture.Container -Recurse -Force }
    }

    It 'rejects write-all permission on a PR workflow' {
        $fixture = New-PublicationFixture
        try {
            $workflowPath = Join-Path $fixture.Repository '.github\workflows\validate.yml'
            $source = (Get-Content $workflowPath -Raw) -replace 'permissions:\s+contents: read', 'permissions: write-all'
            Set-Content $workflowPath $source
            Invoke-Git $fixture.Repository add . | Out-Null
            Invoke-Git $fixture.Repository commit -m 'unsafe broad permission' | Out-Null
            $result = Invoke-GateFixture $fixture
            $result.ExitCode | Should Not Be 0
            $result.Output | Should Match 'workflow security contract'
        } finally { Remove-Item $fixture.Container -Recurse -Force }
    }
}

Describe 'Publish-LegacyRepository' {
    It 'publishes only after the gate, waits for validate, configures protections, and verifies readback' {
        $fixture = New-PublicationFixture
        try {
            $result = Invoke-PublisherFixture $fixture
            $result.ExitCode | Should Be 0
            $result.Output | Should Match 'Publication and protection verified'
            $log = Get-Content $fixture.GhLog -Raw
            $log | Should Match 'repo create MALIEV-Co-Ltd/Legacy.Maliev.Fixture --public'
            (Get-Content $fixture.PreMergeState -Raw).Trim() | Should Be 'root-only-main-and-exact-candidate-branch'
            $mergedSha = (Get-Content $fixture.MergedSha -Raw).Trim()
            (Invoke-Git $fixture.Bare rev-parse refs/heads/main) | Should Be $mergedSha
            $mergedSha | Should Not Be $fixture.HeadSha
            $log | Should Match "pr create.*--base main.*--head publication/$($fixture.HeadSha)"
            $log | Should Match "run list.*--workflow validate.yml.*--commit $($fixture.HeadSha)"
            $log | Should Match "pr merge.*--squash.*--match-head-commit $($fixture.HeadSha)"
            $log | Should Match 'api repos/MALIEV-Co-Ltd/Legacy.Maliev.Fixture/commits/main --jq \.sha'
            $log | Should Match 'branches/main/protection.*--method PUT'
            $log | Should Match '(?m)^api repos/MALIEV-Co-Ltd/Legacy.Maliev.Fixture/private-vulnerability-reporting --method PUT\r?$'
            $log | Should Match '(?m)^api repos/MALIEV-Co-Ltd/Legacy.Maliev.Fixture/private-vulnerability-reporting\r?$'
            $log | Should Match 'environments/production.*--method PUT'
            $log | Should Match '(?m)branches/main/protection\r?$'
            $log | Should Match '(?m)environments/production\r?$'
            $log.IndexOf('run list', [StringComparison]::Ordinal) | Should BeLessThan $log.IndexOf('pr merge', [StringComparison]::Ordinal)
            $log.IndexOf('pr merge', [StringComparison]::Ordinal) | Should BeLessThan $log.IndexOf('branches/main/protection', [StringComparison]::Ordinal)
        } finally { Remove-Item $fixture.Container -Recurse -Force }
    }

    It 'does not call GitHub when the local publication gate fails' {
        $fixture = New-PublicationFixture
        try {
            Add-Content (Join-Path $fixture.Repository 'README.md') 'dirty'
            $result = Invoke-PublisherFixture $fixture
            $result.ExitCode | Should Not Be 0
            Test-Path $fixture.GhLog | Should Be $false
        } finally { Remove-Item $fixture.Container -Recurse -Force }
    }

    It 'reuses a pre-created empty repository without attempting to create it again' {
        $fixture = New-PublicationFixture
        try {
            $result = Invoke-PublisherFixture $fixture -RemoteState empty
            $result.ExitCode | Should Be 0
            $log = Get-Content $fixture.GhLog -Raw
            $log | Should Match '^repo view '
            $log | Should Not Match '(?m)^repo create '
        } finally { Remove-Item $fixture.Container -Recurse -Force }
    }

    It 'reuses the exact open candidate pull request when publication resumes' {
        $fixture = New-PublicationFixture
        try {
            $result = Invoke-PublisherFixture $fixture -ExistingPr
            $result.ExitCode | Should Be 0
            $log = Get-Content $fixture.GhLog -Raw
            $log | Should Not Match '(?m)^pr create '
            ([regex]::Matches($log, '(?m)^pr list ')).Count | Should Be 1
        } finally { Remove-Item $fixture.Container -Recurse -Force }
    }

    It 'fails before any publication push when the remote repository is unexpectedly non-empty' {
        $fixture = New-PublicationFixture
        try {
            $result = Invoke-PublisherFixture $fixture -RemoteState non-empty
            $result.ExitCode | Should Not Be 0
            $result.Output | Should Match 'non-empty'
            $log = Get-Content $fixture.GhLog -Raw
            $log | Should Not Match '(?m)^pr (?:list|create|merge) '
        } finally { Remove-Item $fixture.Container -Recurse -Force }
    }

    It 'fails closed when GitHub readback does not match the required public contract' {
        $fixture = New-PublicationFixture
        try {
            $result = Invoke-PublisherFixture $fixture 'private'
            $result.ExitCode | Should Not Be 0
            $result.Output | Should Match 'readback mismatch'
        } finally { Remove-Item $fixture.Container -Recurse -Force }
    }

    It 'fails closed when any configured branch protection readback differs' {
        $fixture = New-PublicationFixture
        try {
            $result = Invoke-PublisherFixture $fixture -ProtectionMismatch
            $result.ExitCode | Should Not Be 0
            $result.Output | Should Match 'readback mismatch'
        } finally { Remove-Item $fixture.Container -Recurse -Force }
    }

    It 'fails closed when exact environment protection readback differs' {
        $fixture = New-PublicationFixture
        try {
            $result = Invoke-PublisherFixture $fixture -EnvironmentMismatch
            $result.ExitCode | Should Not Be 0
            $result.Output | Should Match 'readback mismatch'
        } finally { Remove-Item $fixture.Container -Recurse -Force }
    }

    It 'requires private source comparison before publishing an extracted service' {
        $fixture = New-PublicationFixture
        try {
            $result = Invoke-PublisherFixture $fixture -OmitPrivateSource
            $result.ExitCode | Should Not Be 0
            Test-Path $fixture.GhLog | Should Be $false
        } finally { Remove-Item $fixture.Container -Recurse -Force }
    }
}

Describe 'Dependabot publication contract' {
    It 'configures grouped weekly NuGet Docker and GitHub Actions updates' {
        $source = Get-Content (Join-Path $RepositoryRoot '.github\dependabot.yml') -Raw
        $source | Should Match 'version:\s*2'
        $source | Should Match 'package-ecosystem:\s*"nuget"'
        $source | Should Match 'package-ecosystem:\s*"docker"'
        $source | Should Match 'package-ecosystem:\s*"github-actions"'
        ([regex]::Matches($source, 'interval:\s*"weekly"')).Count | Should Be 3
        ([regex]::Matches($source, '(?m)^\s+groups:\s*$')).Count | Should Be 3
        ([regex]::Matches($source, 'patterns:\s*\["\*"\]')).Count | Should Be 3
    }
}
