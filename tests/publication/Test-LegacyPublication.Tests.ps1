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
    $tools = Join-Path $container 'tools'
    $bare = Join-Path $container 'published.git'
    New-Item -ItemType Directory -Path $repository, $tools | Out-Null

    Invoke-Git $repository init -b main | Out-Null
    Invoke-Git $repository config user.name Fixture | Out-Null
    Invoke-Git $repository config user.email fixture@example.invalid | Out-Null
    Invoke-Git $repository config core.autocrlf false | Out-Null

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
if ($Arguments[0] -eq 'repo' -and $Arguments[1] -eq 'create') {
    & $env:REAL_GIT -C $env:FIXTURE_REPOSITORY remote add origin $env:BARE_REPOSITORY
    exit $LASTEXITCODE
}
if ($Arguments[0] -eq 'run' -and $Arguments[1] -eq 'list') {
    '[{"databaseId":42,"status":"completed","conclusion":"success","name":"validate"}]'
    exit 0
}
if ($Arguments[0] -eq 'run' -and $Arguments[1] -eq 'view') {
    '{"jobs":[{"name":"validate","status":"completed","conclusion":"success"}]}'
    exit 0
}
if ($Arguments[0] -eq 'api' -and $joined -notmatch '--method') {
    if ($joined -match '/branches/main/protection') {
        $conversationResolution = if ($env:GH_PROTECTION_MISMATCH) { 'false' } else { 'true' }
        '{"required_status_checks":{"strict":true,"contexts":["validate / validate"]},"enforce_admins":{"enabled":true},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"required_approving_review_count":1},"required_linear_history":{"enabled":true},"required_conversation_resolution":{"enabled":' + $conversationResolution + '},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false}}'
    } elseif ($joined -match '/environments/production') {
        '{"name":"production","deployment_branch_policy":{"protected_branches":true,"custom_branch_policies":false}}'
    } else {
        $visibility = if ($env:GH_VISIBILITY) { $env:GH_VISIBILITY } else { 'public' }
        '{"visibility":"' + $visibility + '","default_branch":"main","security_and_analysis":{"private_vulnerability_reporting":{"status":"enabled"}}}'
    }
    exit 0
}
$null = @($input)
exit 0
'@ | Set-Content (Join-Path $tools 'gh.ps1')

    Invoke-Git $repository add . | Out-Null
    Invoke-Git $repository commit -m 'fresh public root' | Out-Null
    Invoke-Process $container $RealGit @('init', '--bare', $bare) | Out-Null

    [pscustomobject]@{
        Container = $container
        Repository = $repository
        Tools = $tools
        Bare = $bare
        DotnetLog = Join-Path $container 'dotnet.log'
        GhLog = Join-Path $container 'gh.log'
    }
}

function Invoke-GateFixture {
    param($Fixture, [string]$Name = 'MALIEV-Co-Ltd/Legacy.Maliev.Fixture')
    $path = $Fixture.Tools + [IO.Path]::PathSeparator + $env:PATH
    Invoke-Process $Fixture.Repository 'pwsh' @('-NoLogo', '-NoProfile', '-File', $GateScript, '-RepositoryPath', $Fixture.Repository, '-GitHubRepository', $Name) @{
        PATH = $path
        REAL_GIT = $RealGit
        FIXTURE_REPOSITORY = $Fixture.Repository
        DOTNET_LOG = $Fixture.DotnetLog
    }
}

function Invoke-PublisherFixture {
    param($Fixture, [string]$Visibility = '', [switch]$ProtectionMismatch)
    $path = $Fixture.Tools + [IO.Path]::PathSeparator + $env:PATH
    Invoke-Process $Fixture.Repository 'pwsh' @('-NoLogo', '-NoProfile', '-File', $PublishScript, '-RepositoryPath', $Fixture.Repository, '-GitHubRepository', 'MALIEV-Co-Ltd/Legacy.Maliev.Fixture', '-WaitTimeoutSeconds', '5', '-PollIntervalSeconds', '0') @{
        PATH = $path
        REAL_GIT = $RealGit
        FIXTURE_REPOSITORY = $Fixture.Repository
        BARE_REPOSITORY = $Fixture.Bare
        DOTNET_LOG = $Fixture.DotnetLog
        GH_LOG = $Fixture.GhLog
        GH_VISIBILITY = $Visibility
        GH_PROTECTION_MISMATCH = if ($ProtectionMismatch) { 'true' } else { '' }
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
            $log | Should Match 'run list.*--commit'
            $log | Should Match 'branches/main/protection.*--method PUT'
            $log | Should Match 'private_vulnerability_reporting'
            $log | Should Match 'environments/production.*--method PUT'
            $log | Should Match '(?m)branches/main/protection\r?$'
            $log | Should Match '(?m)environments/production\r?$'
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
