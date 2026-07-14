using System.Diagnostics;
using System.Text.RegularExpressions;
using Xunit;

namespace Legacy.Maliev.Workflows.Tests;

public sealed class RepositoryContractTests
{
    private static readonly string[] RequiredFiles =
    [
        "README.md",
        "SECURITY.md",
        ".github/dependabot.yml",
        "actions/dotnet-validate/action.yml",
        "actions/gitops-handoff/action.yml",
        ".github/workflows/dotnet-validate.yml",
        ".github/workflows/publish-image.yml",
        "scripts/Set-GitOpsImageDigest.ps1",
        "scripts/Test-LegacyPublication.ps1",
        "scripts/Publish-LegacyRepository.ps1",
    ];

    private static readonly string[] RequiredActionSources =
    [
        "actions/dotnet-validate/action.yml",
        "actions/gitops-handoff/action.yml",
        ".github/workflows/dotnet-validate.yml",
        ".github/workflows/publish-image.yml",
    ];

    [Fact]
    public void RequiredRepositoryFiles_WhenContractIsEvaluated_AllExist()
    {
        string repositoryRoot = FindRepositoryRoot();
        string[] missingFiles = RequiredFiles
            .Where(relativePath => !File.Exists(Path.Combine(repositoryRoot, relativePath)))
            .ToArray();

        Assert.True(
            missingFiles.Length == 0,
            $"Missing required repository files:{Environment.NewLine}{string.Join(Environment.NewLine, missingFiles)}");
    }

    [Fact]
    public void ActionSources_WhenContractIsEvaluated_AreSafeAndShaPinned()
    {
        string repositoryRoot = FindRepositoryRoot();

        foreach (string relativePath in RequiredActionSources)
        {
            string sourcePath = Path.Combine(repositoryRoot, relativePath);
            Assert.True(File.Exists(sourcePath), $"Missing required action source: {relativePath}");

            string source = File.ReadAllText(sourcePath);
            Assert.DoesNotContain("pull_request_target", source, StringComparison.OrdinalIgnoreCase);
            Assert.DoesNotContain("kubectl", source, StringComparison.OrdinalIgnoreCase);
            Assert.DoesNotContain("argocd", source, StringComparison.OrdinalIgnoreCase);

            AssertActionUsesAreShaPinned(source);
        }
    }

    [Fact]
    public void ForkSafeValidationWorkflow_WhenContractIsEvaluated_IsReadOnlyAndSecretless()
    {
        string source = ReadRequiredSource(".github/workflows/dotnet-validate.yml");

        Assert.Contains("permissions:\n  contents: read", NormalizeLineEndings(source), StringComparison.Ordinal);
        Assert.DoesNotContain("secrets: inherit", source, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("id-token: write", source, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("packages: write", source, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("pull_request_target", source, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("${{ secrets.", source, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("gcloud", source, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("kubectl", source, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("argocd", source, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void ForkSafeValidationAction_WhenContractIsEvaluated_ExposesInputsAndRunsValidationInOrder()
    {
        string source = ReadRequiredSource("actions/dotnet-validate/action.yml");

        Assert.Contains("solution:", source, StringComparison.Ordinal);
        Assert.Contains("working-directory:", source, StringComparison.Ordinal);
        Assert.Contains("dotnet-version:", source, StringComparison.Ordinal);
        Assert.Contains("actions/setup-dotnet@", source, StringComparison.Ordinal);
        Assert.Contains("actions/cache@", source, StringComparison.Ordinal);
        AssertUsesSecretlessGitleaksCli(source);
        AssertValidationCommandsRunInOrder(source);
    }

    [Fact]
    public void ForkSafeValidationWorkflow_WhenContractIsEvaluated_ExposesCallerContractAndMatchesAction()
    {
        string source = ReadRequiredSource(".github/workflows/dotnet-validate.yml");

        Assert.Contains("name: validate", source, StringComparison.Ordinal);
        Assert.Contains("workflow_call:", source, StringComparison.Ordinal);
        Assert.Contains("solution:", source, StringComparison.Ordinal);
        Assert.Contains("working-directory:", source, StringComparison.Ordinal);
        Assert.Contains("dotnet-version:", source, StringComparison.Ordinal);
        Assert.Contains("timeout-minutes: 20", source, StringComparison.Ordinal);
        Assert.Contains("cancel-in-progress: true", source, StringComparison.Ordinal);
        Assert.Contains("persist-credentials: false", source, StringComparison.Ordinal);
        AssertUsesSecretlessGitleaksCli(source);
        AssertValidationCommandsRunInOrder(source);
    }

    [Fact]
    public void TrustedImagePublicationWorkflow_WhenContractIsEvaluated_RequiresTrustedCallerAndOidcPermissions()
    {
        string source = ReadRequiredSource(".github/workflows/publish-image.yml");
        string normalizedSource = NormalizeLineEndings(source);

        Assert.Contains("name: publish-image", source, StringComparison.Ordinal);
        Assert.Contains("workflow_call:", source, StringComparison.Ordinal);
        Assert.Contains("image:", source, StringComparison.Ordinal);
        Assert.Contains("dockerfile:", source, StringComparison.Ordinal);
        Assert.Contains("context:", source, StringComparison.Ordinal);
        Assert.Contains("environment:", source, StringComparison.Ordinal);
        Assert.Contains("workload-identity-provider:", source, StringComparison.Ordinal);
        Assert.Contains("service-account:", source, StringComparison.Ordinal);
        Assert.Contains("outputs:\n      digest:", normalizedSource, StringComparison.Ordinal);
        Assert.Contains("permissions:\n  contents: read\n  id-token: write", normalizedSource, StringComparison.Ordinal);
        Assert.Contains("environment: ${{ inputs.environment }}", source, StringComparison.Ordinal);
        Assert.Contains("github.ref == 'refs/heads/main'", source, StringComparison.Ordinal);
        Assert.Contains("github.ref_protected == true", source, StringComparison.Ordinal);
        Assert.Contains("github.event_name == 'push'", source, StringComparison.Ordinal);
        Assert.Contains("github.event_name == 'workflow_dispatch'", source, StringComparison.Ordinal);

        Assert.DoesNotContain("pull_request:", source, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("pull_request_target", source, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("${{ secrets.", source, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("credentials_json", source, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("service_account_key", source, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("private_key", source, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("client_email", source, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("kubectl", source, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("helm ", source, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("argocd", source, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain(":latest", source, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void TrustedImagePublicationWorkflow_WhenContractIsEvaluated_BuildsOnceScansBeforePushAndReturnsDigest()
    {
        string source = ReadRequiredSource(".github/workflows/publish-image.yml");

        AssertActionUsesAreShaPinned(source);
        Assert.Single(Regex.Matches(source, @"docker/build-push-action@[0-9a-f]{40}"));
        Assert.Contains("google-github-actions/auth@", source, StringComparison.Ordinal);
        Assert.Contains("workload_identity_provider: ${{ inputs.workload-identity-provider }}", source, StringComparison.Ordinal);
        Assert.Contains("service_account: ${{ inputs.service-account }}", source, StringComparison.Ordinal);
        Assert.Contains("token_format: access_token", source, StringComparison.Ordinal);
        Assert.Contains("docker/login-action@", source, StringComparison.Ordinal);
        Assert.Contains("docker/setup-buildx-action@", source, StringComparison.Ordinal);
        Assert.Contains("aquasecurity/trivy-action@", source, StringComparison.Ordinal);
        Assert.Contains("push: false", source, StringComparison.Ordinal);
        Assert.Contains("load: true", source, StringComparison.Ordinal);
        Assert.Contains("${{ inputs.image }}:${{ github.sha }}", source, StringComparison.Ordinal);
        Assert.Contains("^sha256:[0-9a-f]{64}$", source, StringComparison.Ordinal);
        Assert.Contains("echo \"digest=$DIGEST\" >> \"$GITHUB_OUTPUT\"", source, StringComparison.Ordinal);

        int buildIndex = source.IndexOf("docker/build-push-action@", StringComparison.Ordinal);
        int scanIndex = source.IndexOf("aquasecurity/trivy-action@", StringComparison.Ordinal);
        int pushIndex = source.IndexOf("docker push", StringComparison.Ordinal);
        int digestIndex = source.IndexOf("docker buildx imagetools inspect", StringComparison.Ordinal);

        Assert.True(buildIndex >= 0 && scanIndex > buildIndex, "Expected Trivy to scan the locally built image.");
        Assert.True(pushIndex > scanIndex, "Expected the vulnerability scan to pass before image publication.");
        Assert.True(digestIndex > pushIndex, "Expected immutable digest resolution after image publication.");
        Assert.Single(Regex.Matches(source, @"GITHUB_OUTPUT"));
    }

    [Fact]
    public void GitOpsDigestUpdater_WhenFixtureIsValid_ChangesOnlyTheLegacyImageToTheDigest()
    {
        using GitOpsFixture fixture = GitOpsFixture.Create();

        ProcessResult result = fixture.RunUpdater();

        Assert.True(result.ExitCode == 0, result.Output);
        string manifest = File.ReadAllText(fixture.ManifestPath);
        Assert.Contains($"    digest: {GitOpsFixture.ValidDigest}", manifest, StringComparison.Ordinal);
        Assert.DoesNotContain("newTag:", manifest, StringComparison.Ordinal);
        Assert.Equal(fixture.RelativeManifestPath, fixture.RunGit("diff", "--name-only").Trim());
        Assert.Contains("changed=true", fixture.ReadOutputs(), StringComparison.Ordinal);
        Assert.Contains("status=updated", fixture.ReadOutputs(), StringComparison.Ordinal);
        Assert.Contains("branch=gitops/legacy-country-service", fixture.ReadOutputs(), StringComparison.Ordinal);
    }

    [Fact]
    public void GitOpsDigestUpdater_WhenDigestAlreadyMatches_ReturnsSuccessfulNoOp()
    {
        string manifest = GitOpsFixture.ValidManifest.Replace(
            "newTag: latest",
            $"digest: {GitOpsFixture.ValidDigest}",
            StringComparison.Ordinal);
        using GitOpsFixture fixture = GitOpsFixture.Create(manifest);

        ProcessResult result = fixture.RunUpdater();

        Assert.True(result.ExitCode == 0, result.Output);
        Assert.Empty(fixture.RunGit("diff", "--name-only"));
        Assert.Contains("changed=false", fixture.ReadOutputs(), StringComparison.Ordinal);
        Assert.Contains("status=no-op", fixture.ReadOutputs(), StringComparison.Ordinal);
    }

    [Theory]
    [InlineData(false)]
    [InlineData(true)]
    public void GitOpsDigestUpdater_WhenManifestHasDuplicateTopLevelImagesBlocks_FailsBeforeUpdateOrNoOp(
        bool firstBlockAlreadyHasDigest)
    {
        string firstBlock = firstBlockAlreadyHasDigest
            ? GitOpsFixture.ValidManifest.Replace("newTag: latest", $"digest: {GitOpsFixture.ValidDigest}", StringComparison.Ordinal)
            : GitOpsFixture.ValidManifest;
        string manifest = $"""
            {firstBlock.TrimEnd()}
            images:
              - name: duplicate-image
                newName: registry.example/duplicate-image
                newTag: latest
            """;
        using GitOpsFixture fixture = GitOpsFixture.Create(manifest);

        ProcessResult result = fixture.RunUpdater();

        Assert.NotEqual(0, result.ExitCode);
        Assert.Contains("manifest must contain exactly one top-level images block", result.Output, StringComparison.OrdinalIgnoreCase);
        Assert.False(File.Exists(fixture.OutputPath));
        Assert.Empty(fixture.RunGit("diff", "--name-only"));
    }

    [Theory]
    [InlineData("NotLegacy.CountryService", GitOpsFixture.ValidDigest, "service must match Legacy.Maliev.*")]
    [InlineData("Legacy.Maliev.CountryService", "sha256:not-a-digest", "digest must be sha256 followed by 64 lowercase hexadecimal characters")]
    public void GitOpsDigestUpdater_WhenIdentityInputIsInvalid_FailsClosed(
        string service,
        string digest,
        string expectedError)
    {
        using GitOpsFixture fixture = GitOpsFixture.Create();

        ProcessResult result = fixture.RunUpdater(service: service, digest: digest);

        Assert.NotEqual(0, result.ExitCode);
        Assert.Contains(expectedError, result.Output, StringComparison.OrdinalIgnoreCase);
        Assert.Empty(fixture.RunGit("diff", "--name-only"));
    }

    [Fact]
    public void GitOpsDigestUpdater_WhenWellFormedServiceIsNotAllowlisted_FailsClosed()
    {
        using GitOpsFixture fixture = GitOpsFixture.Create();

        ProcessResult result = fixture.RunUpdater(service: "Legacy.Maliev.QuoteEngine");

        Assert.NotEqual(0, result.ExitCode);
        Assert.Contains("service is not present in GitOps contract v1", result.Output, StringComparison.OrdinalIgnoreCase);
        Assert.False(File.Exists(fixture.OutputPath));
        Assert.Empty(fixture.RunGit("diff", "--name-only"));
    }

    [Theory]
    [InlineData("Legacy.Maliev.CountryService\nforged=true", "registry.example/legacy-maliev-country-service", GitOpsFixture.ValidDigest, "3-apps/_legacy-country-service/overlays/legacy/kustomization.yaml")]
    [InlineData("Legacy.Maliev.CountryService", "registry.example/legacy-maliev-country-service\rforged=true", GitOpsFixture.ValidDigest, "3-apps/_legacy-country-service/overlays/legacy/kustomization.yaml")]
    [InlineData("Legacy.Maliev.CountryService", "registry.example/legacy-maliev-country-service", GitOpsFixture.ValidDigest + "\nforged=true", "3-apps/_legacy-country-service/overlays/legacy/kustomization.yaml")]
    [InlineData("Legacy.Maliev.CountryService", "registry.example/legacy-maliev-country-service", GitOpsFixture.ValidDigest, "3-apps/_legacy-country-service/overlays/legacy/kustomization.yaml\nforged=true")]
    public void GitOpsDigestUpdater_WhenInputContainsOutputControlCharacters_FailsBeforeWritingOutputs(
        string service,
        string image,
        string digest,
        string gitOpsPath)
    {
        using GitOpsFixture fixture = GitOpsFixture.Create();

        ProcessResult result = fixture.RunUpdater(service, digest, gitOpsPath, image);

        Assert.NotEqual(0, result.ExitCode);
        Assert.Contains("inputs must not contain CR, LF, or NUL", result.Output, StringComparison.OrdinalIgnoreCase);
        Assert.False(File.Exists(fixture.OutputPath));
        Assert.Empty(fixture.RunGit("diff", "--name-only"));
    }

    [Fact]
    public void GitOpsDigestUpdater_WhenPathEscapesCheckout_FailsClosed()
    {
        using GitOpsFixture fixture = GitOpsFixture.Create();
        string outsidePath = Path.Combine(fixture.ContainerPath, "outside.yaml");
        File.WriteAllText(outsidePath, GitOpsFixture.ValidManifest);

        ProcessResult result = fixture.RunUpdater(gitOpsPath: outsidePath);

        Assert.NotEqual(0, result.ExitCode);
        Assert.Contains("gitops-path must stay within gitops-root", result.Output, StringComparison.OrdinalIgnoreCase);
        Assert.Empty(fixture.RunGit("diff", "--name-only"));
    }

    [Fact]
    public void GitOpsDigestUpdater_WhenTargetTraversesReparsePoint_FailsBeforeWrite()
    {
        using GitOpsFixture fixture = GitOpsFixture.Create();
        if (!fixture.TryReplaceLegacyDirectoryWithSymbolicLink())
        {
            Assert.Skip("Symbolic-link or junction creation is unavailable on this platform.");
        }

        ProcessResult result = fixture.RunUpdater();

        Assert.NotEqual(0, result.ExitCode);
        Assert.Contains("reparse points and symbolic links are prohibited", result.Output, StringComparison.OrdinalIgnoreCase);
        Assert.False(File.Exists(fixture.OutputPath));
    }

    [Theory]
    [InlineData("namespace: maliev-prod", "namespace must remain maliev-legacy")]
    [InlineData("nodeSelector:\n  cloud.google.com/gke-nodepool: paid-pool", "node selectors are prohibited")]
    [InlineData("  - name: another-image\n    newName: registry.example/another-image\n    newTag: latest", "manifest must contain exactly one image entry")]
    public void GitOpsDigestUpdater_WhenManifestContractIsUnsafe_FailsClosed(
        string replacement,
        string expectedError)
    {
        string manifest = replacement.StartsWith("namespace:", StringComparison.Ordinal)
            ? GitOpsFixture.ValidManifest.Replace("namespace: maliev-legacy", replacement, StringComparison.Ordinal)
            : $"{GitOpsFixture.ValidManifest.TrimEnd()}\n{replacement}\n";
        using GitOpsFixture fixture = GitOpsFixture.Create(manifest);

        ProcessResult result = fixture.RunUpdater();

        Assert.NotEqual(0, result.ExitCode);
        Assert.Contains(expectedError, result.Output, StringComparison.OrdinalIgnoreCase);
        Assert.Empty(fixture.RunGit("diff", "--name-only"));
    }

    [Fact]
    public void GitOpsDigestUpdater_WhenAnotherFileIsChanged_FailsClosed()
    {
        using GitOpsFixture fixture = GitOpsFixture.Create();
        File.AppendAllText(Path.Combine(fixture.RepositoryPath, "README.md"), "unexpected\n");

        ProcessResult result = fixture.RunUpdater();

        Assert.NotEqual(0, result.ExitCode);
        Assert.Contains("git diff may contain only the target manifest", result.Output, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("digest:", File.ReadAllText(fixture.ManifestPath), StringComparison.Ordinal);
    }

    [Fact]
    public void GitOpsHandoffAction_WhenContractIsEvaluated_IsSecretlessTrustedAndPrOnly()
    {
        string repositoryRoot = FindRepositoryRoot();
        string source = ReadRequiredSource("actions/gitops-handoff/action.yml");
        string normalizedSource = NormalizeLineEndings(source);

        Assert.False(File.Exists(Path.Combine(repositoryRoot, ".github/workflows/gitops-handoff.yml")));
        Assert.Contains("name: GitOps handoff", source, StringComparison.Ordinal);
        Assert.Contains("runs:\n  using: composite", normalizedSource, StringComparison.Ordinal);
        Assert.Contains("service:", source, StringComparison.Ordinal);
        Assert.Contains("image:", source, StringComparison.Ordinal);
        Assert.Contains("digest:", source, StringComparison.Ordinal);
        Assert.Contains("gitops-path:", source, StringComparison.Ordinal);
        Assert.Contains("contract-version:", source, StringComparison.Ordinal);
        Assert.Contains("default: v1", source, StringComparison.Ordinal);
        Assert.Contains("token:", source, StringComparison.Ordinal);
        Assert.Contains("outputs:\n  changed:", normalizedSource, StringComparison.Ordinal);
        Assert.Contains("status:", source, StringComparison.Ordinal);
        Assert.Contains("branch:", source, StringComparison.Ordinal);
        Assert.Contains("GITHUB_REF_PROTECTED", source, StringComparison.Ordinal);
        Assert.Contains("refs/heads/main", source, StringComparison.Ordinal);
        Assert.Contains("GITHUB_EVENT_NAME", source, StringComparison.Ordinal);
        Assert.Contains("repository: MALIEV-Co-Ltd/maliev-gitops", source, StringComparison.Ordinal);
        Assert.Contains("token: ${{ inputs.token }}", source, StringComparison.Ordinal);
        Assert.Contains("persist-credentials: false", source, StringComparison.Ordinal);
        Assert.Contains("Set-GitOpsImageDigest.ps1", source, StringComparison.Ordinal);
        Assert.Contains("SERVICE: ${{ inputs.service }}", source, StringComparison.Ordinal);
        Assert.Contains("IMAGE: ${{ inputs.image }}", source, StringComparison.Ordinal);
        Assert.Contains("DIGEST: ${{ inputs.digest }}", source, StringComparison.Ordinal);
        Assert.Contains("GITOPS_PATH: ${{ inputs.gitops-path }}", source, StringComparison.Ordinal);
        Assert.Contains("CONTRACT_VERSION: ${{ inputs.contract-version }}", source, StringComparison.Ordinal);
        Assert.Contains("GITHUB_ACTION_PATH", source, StringComparison.Ordinal);
        Assert.Contains("kustomize build", source, StringComparison.Ordinal);
        Assert.Contains("if: steps.update.outputs.changed == 'true'", source, StringComparison.Ordinal);
        Assert.Contains("git -c http.https://github.com/.extraheader=", source, StringComparison.Ordinal);
        Assert.Contains("TOKEN: ${{ inputs.token }}", source, StringComparison.Ordinal);
        Assert.Contains("GH_TOKEN: ${{ inputs.token }}", source, StringComparison.Ordinal);
        Assert.Contains("if: always()", source, StringComparison.Ordinal);
        Assert.Contains("git config --local --get-regexp", source, StringComparison.Ordinal);
        Assert.Contains("git remote get-url origin", source, StringComparison.Ordinal);
        Assert.DoesNotContain("\n        git push", normalizedSource, StringComparison.Ordinal);
        Assert.Contains("gh pr create", source, StringComparison.Ordinal);
        Assert.Contains("gh pr edit", source, StringComparison.Ordinal);

        Assert.DoesNotContain("pull_request_target", source, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("${{ secrets.", source, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("gitops-token", source, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("kubectl", source, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("helm ", source, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("argocd", source, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("gh pr merge", source, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("sync", source, StringComparison.OrdinalIgnoreCase);
        AssertActionUsesAreShaPinned(source);

        foreach (string relativePath in RequiredActionSources)
        {
            Assert.DoesNotContain("gitops-token", ReadRequiredSource(relativePath), StringComparison.OrdinalIgnoreCase);
        }
    }

    [Fact]
    public void GitOpsHandoffDocumentation_WhenContractIsEvaluated_LeavesEnvironmentOwnershipWithService()
    {
        string source = ReadRequiredSource("README.md");

        Assert.Contains("actions/gitops-handoff/action.yml", source, StringComparison.Ordinal);
        Assert.Contains("environment:", source, StringComparison.Ordinal);
        Assert.Contains("token: ${{ secrets.GITOPS_TOKEN }}", source, StringComparison.Ordinal);
        Assert.Contains("Legacy.Maliev.CountryService", source, StringComparison.Ordinal);
        Assert.Contains("3-apps/_legacy-country-service/overlays/legacy/kustomization.yaml", source, StringComparison.Ordinal);
        Assert.Contains("not yet present on `maliev-gitops` main", source, StringComparison.OrdinalIgnoreCase);
        Assert.Contains("Contents: read and write", source, StringComparison.Ordinal);
        Assert.Contains("Pull requests: read and write", source, StringComparison.Ordinal);
        Assert.Contains("limited to `MALIEV-Co-Ltd/maliev-gitops`", source, StringComparison.Ordinal);
        Assert.DoesNotContain(".github/workflows/gitops-handoff.yml", source, StringComparison.Ordinal);
    }

    [Fact]
    public void FindRepositoryRoot_WhenGitMarkerIsFileOrDirectory_ReturnsRepositoryRoot()
    {
        DirectoryInfo? expectedRoot = new(AppContext.BaseDirectory);

        while (expectedRoot is not null)
        {
            string gitMarker = Path.Combine(expectedRoot.FullName, ".git");
            if (Directory.Exists(gitMarker) || File.Exists(gitMarker))
            {
                break;
            }

            expectedRoot = expectedRoot.Parent;
        }

        Assert.NotNull(expectedRoot);
        Assert.Equal(expectedRoot.FullName, FindRepositoryRoot());
    }

    public static string FindRepositoryRoot()
    {
        DirectoryInfo? currentDirectory = new(AppContext.BaseDirectory);

        while (currentDirectory is not null)
        {
            string gitMarker = Path.Combine(currentDirectory.FullName, ".git");
            if (Directory.Exists(gitMarker) || File.Exists(gitMarker))
            {
                return currentDirectory.FullName;
            }

            currentDirectory = currentDirectory.Parent;
        }

        throw new DirectoryNotFoundException("Could not find the repository root containing .git.");
    }

    private static string ReadRequiredSource(string relativePath)
    {
        string sourcePath = Path.Combine(FindRepositoryRoot(), relativePath);
        Assert.True(File.Exists(sourcePath), $"Missing required action source: {relativePath}");
        return File.ReadAllText(sourcePath);
    }

    private static void AssertValidationCommandsRunInOrder(string source)
    {
        string[] commands =
        [
            "dotnet restore \"${{ inputs.solution }}\"",
            "dotnet build \"${{ inputs.solution }}\" --configuration Release --no-restore",
            "dotnet test \"${{ inputs.solution }}\" --configuration Release --no-build --no-restore",
            "dotnet format \"${{ inputs.solution }}\" --verify-no-changes --no-restore",
            "dotnet list \"${{ inputs.solution }}\" package --vulnerable --include-transitive --no-restore",
        ];

        int previousIndex = -1;
        foreach (string command in commands)
        {
            int commandIndex = source.IndexOf(command, StringComparison.Ordinal);
            Assert.True(commandIndex > previousIndex, $"Expected validation command in order: {command}");
            previousIndex = commandIndex;
        }
    }

    private static void AssertActionUsesAreShaPinned(string source)
    {
        string[] actionLines = source
            .Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries)
            .Where(line => Regex.IsMatch(line, @"^\s*(?:-\s*)?uses:\s*", RegexOptions.IgnoreCase))
            .ToArray();

        Assert.NotEmpty(actionLines);
        foreach (string actionLine in actionLines)
        {
            Assert.Matches(@"uses:\s+[^\s@]+@[0-9a-f]{40}(?:\s|$)", actionLine);
        }
    }

    private static void AssertUsesSecretlessGitleaksCli(string source)
    {
        Assert.DoesNotContain("gitleaks/gitleaks-action", source, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("${{ secrets.", source, StringComparison.OrdinalIgnoreCase);
        Assert.Contains(
            "go install github.com/zricethezav/gitleaks/v8@6eaad039603a4de39fddd1cf5f727391efe9974e",
            source,
            StringComparison.Ordinal);
        Assert.Contains("echo \"$(go env GOPATH)/bin\" >> \"$GITHUB_PATH\"", source, StringComparison.Ordinal);
        Assert.Contains("gitleaks git --redact --exit-code 1", source, StringComparison.Ordinal);
    }

    private static string NormalizeLineEndings(string source) => source.Replace("\r\n", "\n", StringComparison.Ordinal);

    private sealed record ProcessResult(int ExitCode, string Output);

    private sealed class GitOpsFixture : IDisposable
    {
        public const string ValidDigest = "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
        public const string ValidManifest = """
            apiVersion: kustomize.config.k8s.io/v1beta1
            kind: Kustomization
            namespace: maliev-legacy
            resources:
              - ../../base
            images:
              - name: legacy-maliev-country-service
                newName: registry.example/legacy-maliev-country-service
                newTag: latest
            """;

        private GitOpsFixture(string containerPath, string repositoryPath, string relativeManifestPath)
        {
            ContainerPath = containerPath;
            RepositoryPath = repositoryPath;
            RelativeManifestPath = relativeManifestPath;
        }

        public string ContainerPath { get; }
        public string RepositoryPath { get; }
        public string RelativeManifestPath { get; }
        public string ManifestPath => Path.Combine(RepositoryPath, RelativeManifestPath);
        public string OutputPath => Path.Combine(ContainerPath, "github-output.txt");

        public static GitOpsFixture Create(string? manifest = null)
        {
            string containerPath = Path.Combine(Path.GetTempPath(), $"legacy-gitops-{Guid.NewGuid():N}");
            string repositoryPath = Path.Combine(containerPath, "maliev-gitops");
            const string relativeManifestPath = "3-apps/_legacy-country-service/overlays/legacy/kustomization.yaml";
            Directory.CreateDirectory(Path.GetDirectoryName(Path.Combine(repositoryPath, relativeManifestPath))!);
            File.WriteAllText(Path.Combine(repositoryPath, relativeManifestPath), manifest ?? ValidManifest);
            File.WriteAllText(Path.Combine(repositoryPath, "README.md"), "fixture\n");

            GitOpsFixture fixture = new(containerPath, repositoryPath, relativeManifestPath);
            fixture.RunGit("init");
            fixture.RunGit("config", "user.name", "Fixture");
            fixture.RunGit("config", "user.email", "fixture@example.invalid");
            fixture.RunGit("config", "core.autocrlf", "false");
            fixture.RunGit("add", ".");
            fixture.RunGit("commit", "-m", "fixture");
            return fixture;
        }

        public ProcessResult RunUpdater(
            string service = "Legacy.Maliev.CountryService",
            string digest = ValidDigest,
            string? gitOpsPath = null,
            string image = "registry.example/legacy-maliev-country-service")
        {
            File.Delete(OutputPath);
            string scriptPath = Path.Combine(FindRepositoryRoot(), "scripts", "Set-GitOpsImageDigest.ps1");
            return RunProcess(
                RepositoryPath,
                "pwsh",
                "-NoLogo",
                "-NoProfile",
                "-File",
                scriptPath,
                "-GitOpsRoot",
                RepositoryPath,
                "-Service",
                service,
                "-Image",
                image,
                "-Digest",
                digest,
                "-GitOpsPath",
                gitOpsPath ?? RelativeManifestPath,
                "-ContractVersion",
                "v1",
                "-GitHubOutput",
                OutputPath);
        }

        public string ReadOutputs() => File.ReadAllText(OutputPath);

        public bool TryReplaceLegacyDirectoryWithSymbolicLink()
        {
            string linkPath = Path.Combine(RepositoryPath, "3-apps", "_legacy-country-service");
            string targetPath = Path.Combine(ContainerPath, "linked-legacy-country-service");
            CopyDirectory(linkPath, targetPath);
            Directory.Delete(linkPath, recursive: true);

            try
            {
                Directory.CreateSymbolicLink(linkPath, targetPath);
                return true;
            }
            catch (Exception exception) when (exception is UnauthorizedAccessException or IOException or PlatformNotSupportedException)
            {
                if (!OperatingSystem.IsWindows())
                {
                    return false;
                }

                ProcessResult result = RunProcess(
                    RepositoryPath,
                    "cmd.exe",
                    "/d",
                    "/c",
                    $"mklink /J \"{linkPath}\" \"{targetPath}\"");
                return result.ExitCode == 0;
            }
        }

        public string RunGit(params string[] arguments)
        {
            ProcessResult result = RunProcess(RepositoryPath, "git", arguments);
            Assert.True(result.ExitCode == 0, result.Output);
            return result.Output;
        }

        public void Dispose()
        {
            foreach (string path in Directory.EnumerateFiles(ContainerPath, "*", SearchOption.AllDirectories))
            {
                File.SetAttributes(path, FileAttributes.Normal);
            }

            Directory.Delete(ContainerPath, recursive: true);
        }

        private static void CopyDirectory(string sourcePath, string destinationPath)
        {
            Directory.CreateDirectory(destinationPath);
            foreach (string filePath in Directory.EnumerateFiles(sourcePath))
            {
                File.Copy(filePath, Path.Combine(destinationPath, Path.GetFileName(filePath)));
            }
            foreach (string directoryPath in Directory.EnumerateDirectories(sourcePath))
            {
                CopyDirectory(directoryPath, Path.Combine(destinationPath, Path.GetFileName(directoryPath)));
            }
        }

        private static ProcessResult RunProcess(string workingDirectory, string fileName, params string[] arguments)
        {
            ProcessStartInfo startInfo = new(fileName)
            {
                WorkingDirectory = workingDirectory,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
            };
            foreach (string argument in arguments)
            {
                startInfo.ArgumentList.Add(argument);
            }

            using Process process = Process.Start(startInfo)!;
            string standardOutput = process.StandardOutput.ReadToEnd();
            string standardError = process.StandardError.ReadToEnd();
            process.WaitForExit();
            return new ProcessResult(process.ExitCode, standardOutput + standardError);
        }
    }
}
