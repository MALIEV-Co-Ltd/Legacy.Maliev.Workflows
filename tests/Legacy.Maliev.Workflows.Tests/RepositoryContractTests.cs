using System.Diagnostics;
using System.Text.RegularExpressions;
using YamlDotNet.RepresentationModel;
using Xunit;

namespace Legacy.Maliev.Workflows.Tests;

public sealed class RepositoryContractTests
{
    private const string Node24CheckoutReference =
        "actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0 # v7.0.0";

    private const string Node24SetupDotnetReference =
        "actions/setup-dotnet@a98b56852c35b8e3190ac28c8c2271da59106c68 # v6.0.0";

    private const string Node24CacheReference =
        "actions/cache@55cc8345863c7cc4c66a329aec7e433d2d1c52a9 # v6.1.0";

    private static readonly object BashEnvironmentLock = new();

    private static readonly string[] RequiredFiles =
    [
        "README.md",
        "SECURITY.md",
        ".github/dependabot.yml",
        "actions/dotnet-validate/action.yml",
        "actions/gitops-handoff/action.yml",
        ".github/workflows/validate.yml",
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
    public void DependabotConfiguration_WhenContractIsEvaluated_GroupsOnlyCompatibleUpdatesWithinQueueLimits()
    {
        YamlMappingNode root = Assert.IsType<YamlMappingNode>(ReadYaml(ReadRequiredSource(".github/dependabot.yml")).Documents.Single().RootNode);
        YamlSequenceNode updates = Assert.IsType<YamlSequenceNode>(ReadNode(root, "updates"));
        Dictionary<string, string> expectedLimits = new(StringComparer.Ordinal)
        {
            ["nuget"] = "10",
            ["docker"] = "5",
            ["github-actions"] = "5",
        };

        Assert.Equal(expectedLimits.Count, updates.Children.Count);
        foreach (YamlNode updateNode in updates.Children)
        {
            YamlMappingNode update = Assert.IsType<YamlMappingNode>(updateNode);
            string ecosystem = ReadScalar(update, "package-ecosystem");
            Assert.Equal(expectedLimits[ecosystem], ReadScalar(update, "open-pull-requests-limit"));

            YamlMappingNode groups = Assert.IsType<YamlMappingNode>(ReadNode(update, "groups"));
            YamlMappingNode compatible = Assert.IsType<YamlMappingNode>(Assert.Single(groups.Children).Value);
            YamlSequenceNode patterns = Assert.IsType<YamlSequenceNode>(ReadNode(compatible, "patterns"));
            Assert.Equal(["*"], patterns.Children.Select(Assert.IsType<YamlScalarNode>).Select(node => node.Value));

            YamlSequenceNode updateTypes = Assert.IsType<YamlSequenceNode>(ReadNode(compatible, "update-types"));
            Assert.Equal(
                ["minor", "patch"],
                updateTypes.Children.Select(Assert.IsType<YamlScalarNode>).Select(node => node.Value));
            Assert.DoesNotContain(updateTypes.Children, node => Assert.IsType<YamlScalarNode>(node).Value == "major");
        }
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

    [Theory]
    [InlineData("actions/dotnet-validate/action.yml")]
    [InlineData(".github/workflows/dotnet-validate.yml")]
    public void DotnetValidationSources_WhenContractIsEvaluated_UseNode24Actions(string relativePath)
    {
        string source = ReadRequiredSource(relativePath);

        Assert.Contains(Node24SetupDotnetReference, source, StringComparison.Ordinal);
        Assert.Contains(Node24CacheReference, source, StringComparison.Ordinal);
    }

    [Fact]
    public void ForkSafeValidationWorkflow_WhenContractIsEvaluated_UsesNode24Checkout()
    {
        string source = ReadRequiredSource(".github/workflows/dotnet-validate.yml");

        Assert.Contains(Node24CheckoutReference, source, StringComparison.Ordinal);
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
    public void PullRequestBootstrap_WhenContractIsEvaluated_CallsLocalValidationReadOnlyAndSecretless()
    {
        string source = ReadRequiredSource(".github/workflows/validate.yml");
        string normalizedSource = NormalizeLineEndings(source);

        Assert.Contains("name: validate", source, StringComparison.Ordinal);
        Assert.Contains("on:\n  pull_request:", normalizedSource, StringComparison.Ordinal);
        AssertExclusivePullRequestTrigger(normalizedSource);
        Assert.Contains("permissions:\n  contents: read", normalizedSource, StringComparison.Ordinal);
        Assert.Contains("jobs:\n  validate:\n    name: validate", normalizedSource, StringComparison.Ordinal);
        Assert.Contains("uses: ./.github/workflows/dotnet-validate.yml", source, StringComparison.Ordinal);
        Assert.Contains("solution: Legacy.Maliev.Workflows.slnx", source, StringComparison.Ordinal);

        Assert.DoesNotContain("pull_request_target", source, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("secrets: inherit", source, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("${{ secrets.", source, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("id-token: write", source, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("packages: write", source, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("contents: write", source, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("environment:", source, StringComparison.OrdinalIgnoreCase);
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
    public void ForkSafeValidationAction_WhenLocalDependenciesAreConfigured_UsesAnExactSafeBooleanContract()
    {
        string source = ReadRequiredSource("actions/dotnet-validate/action.yml");

        AssertLocalDependencyContract(source);
    }

    [Theory]
    [InlineData("    default: 'false'", "    default: 'true'")]
    [InlineData("        true|false)", "        true|false|TRUE)")]
    [InlineData("          exit 1", "          exit 0")]
    [InlineData("          export GITHUB_ACTIONS=false", "          export GITHUB_ACTIONS=true")]
    [InlineData("dotnet restore", "echo restore")]
    [InlineData("dotnet build", "echo build")]
    [InlineData("dotnet test", "echo test")]
    [InlineData("dotnet format", "echo format")]
    [InlineData("dotnet list", "echo list")]
    public void ForkSafeValidationAction_WhenLocalDependencyContractIsMutated_FailsSourceContract(
        string original,
        string mutation)
    {
        string source = ReadRequiredSource("actions/dotnet-validate/action.yml");
        string mutatedSource = source.Replace(original, mutation, StringComparison.Ordinal);

        Assert.NotEqual(source, mutatedSource);
        Assert.ThrowsAny<Exception>(() => AssertLocalDependencyContract(mutatedSource));
    }

    [Fact]
    public void ForkSafeValidationAction_WhenValidatorIsMovedAfterRestore_FailsSourceContract()
    {
        string source = ReadRequiredSource("actions/dotnet-validate/action.yml");
        int validatorStart = source.IndexOf("    - name: Validate local MALIEV dependency mode", StringComparison.Ordinal);
        int validatorEnd = source.IndexOf("    - name: Install Gitleaks", validatorStart, StringComparison.Ordinal);
        string validatorBlock = source[validatorStart..validatorEnd];
        string withoutValidator = source.Remove(validatorStart, validatorEnd - validatorStart);
        int buildStart = withoutValidator.IndexOf("    - name: Build", StringComparison.Ordinal);
        string mutatedSource = withoutValidator.Insert(buildStart, validatorBlock);

        Assert.ThrowsAny<Exception>(() => AssertLocalDependencyContract(mutatedSource));
    }

    [Fact]
    public void ForkSafeValidationAction_WhenAnUnguardedRestoreIsAdded_FailsSourceContract()
    {
        string source = ReadRequiredSource("actions/dotnet-validate/action.yml");
        string mutatedSource = source + """

                - name: Unsafe extra restore
                  shell: bash
                  run: dotnet restore extra.slnx
            """;

        Assert.ThrowsAny<Exception>(() => AssertLocalDependencyContract(mutatedSource));
    }

    [Theory]
    [InlineData("true", "USE_LOCAL_MALIEV_DEPENDENCIES=true")]
    [InlineData("false", "USE_LOCAL_MALIEV_DEPENDENCIES=false")]
    public void ForkSafeValidationAction_WhenLocalDependencyInputIsExactLowercase_AcceptsIt(
        string input,
        string expectedEnvironmentEntry)
    {
        string source = ReadRequiredSource("actions/dotnet-validate/action.yml");

        ProcessResult result = RunValidatorFixture(source, input);

        Assert.True(result.ExitCode == 0, result.Output);
        Assert.Contains(expectedEnvironmentEntry, result.Output, StringComparison.Ordinal);
    }

    [Theory]
    [InlineData("TRUE")]
    [InlineData("1")]
    [InlineData("")]
    [InlineData("true; printf injected")]
    public void ForkSafeValidationAction_WhenLocalDependencyInputIsNotExactLowercase_RejectsIt(string input)
    {
        string source = ReadRequiredSource("actions/dotnet-validate/action.yml");

        ProcessResult result = RunValidatorFixture(source, input);

        Assert.NotEqual(0, result.ExitCode);
        Assert.Contains("must be exactly 'true' or 'false'", result.Output, StringComparison.Ordinal);
        Assert.DoesNotContain("injected", result.Output, StringComparison.Ordinal);
    }

    [Theory]
    [InlineData("true", "child=false")]
    [InlineData("false", "child=true")]
    public void ForkSafeValidationAction_WhenDotnetStepRuns_OverridesOnlyTheEnabledChild(
        string localDependencyMode,
        string expectedChildEnvironment)
    {
        string source = ReadRequiredSource("actions/dotnet-validate/action.yml");
        string? parentEnvironmentBefore = Environment.GetEnvironmentVariable("GITHUB_ACTIONS");

        foreach (YamlMappingNode step in ReadActionSteps(source).Where(ContainsDotnetCommand))
        {
            string runScript = ReadScalar(step, "run");
            string fixtureScript = Regex.Replace(
                runScript,
                @"(?m)^dotnet .+$",
                "printf 'child=%s\\n' \"$GITHUB_ACTIONS\"");

            ProcessResult result = RunBashFixture(
                fixtureScript,
                ("GITHUB_ACTIONS", "true"),
                ("USE_LOCAL_MALIEV_DEPENDENCIES", localDependencyMode));

            Assert.True(result.ExitCode == 0, result.Output);
            Assert.Contains(expectedChildEnvironment, result.Output, StringComparison.Ordinal);
        }

        Assert.Equal(parentEnvironmentBefore, Environment.GetEnvironmentVariable("GITHUB_ACTIONS"));
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

    private static void AssertLocalDependencyContract(string source)
    {
        YamlStream yaml = ReadYaml(source);
        YamlMappingNode root = Assert.IsType<YamlMappingNode>(yaml.Documents.Single().RootNode);
        YamlMappingNode inputs = ReadMapping(root, "inputs");
        YamlMappingNode localDependencyInput = ReadMapping(inputs, "use-local-maliev-dependencies");
        Assert.Equal("false", ReadScalar(localDependencyInput, "default"));

        YamlMappingNode[] steps = ReadActionSteps(source);
        YamlMappingNode validator = Assert.Single(
            steps,
            step => ReadOptionalScalar(step, "name") == "Validate local MALIEV dependency mode");
        int validatorIndex = Array.IndexOf(steps, validator);
        Assert.Equal("bash", ReadScalar(validator, "shell"));
        Assert.Equal(
            "${{ inputs.use-local-maliev-dependencies }}",
            ReadScalar(ReadMapping(validator, "env"), "USE_LOCAL_MALIEV_DEPENDENCIES_INPUT"));

        string validatorScript = NormalizeLineEndings(ReadScalar(validator, "run"));
        Assert.Contains("case \"$USE_LOCAL_MALIEV_DEPENDENCIES_INPUT\" in", validatorScript, StringComparison.Ordinal);
        string[] casePatterns = Regex.Matches(validatorScript, @"(?m)^ {2}(?<pattern>[^)\r\n]+)\)$")
            .Select(match => match.Groups["pattern"].Value)
            .ToArray();
        Assert.Equal(["true|false", "*"], casePatterns);
        Assert.Contains("USE_LOCAL_MALIEV_DEPENDENCIES=$USE_LOCAL_MALIEV_DEPENDENCIES_INPUT", validatorScript, StringComparison.Ordinal);
        Assert.Contains(">> \"$GITHUB_ENV\"", validatorScript, StringComparison.Ordinal);
        Assert.Contains("    exit 1", validatorScript, StringComparison.Ordinal);

        string[] expectedDotnetCommands =
        [
            "dotnet restore \"${{ inputs.solution }}\"",
            "dotnet build \"${{ inputs.solution }}\" --configuration Release --no-restore",
            "dotnet test \"${{ inputs.solution }}\" --configuration Release --no-build --no-restore",
            "dotnet format \"${{ inputs.solution }}\" --verify-no-changes --no-restore",
            "dotnet list \"${{ inputs.solution }}\" package --vulnerable --include-transitive --no-restore",
        ];

        List<(int StepIndex, string Command, string Script)> dotnetInvocations = [];
        for (int stepIndex = 0; stepIndex < steps.Length; stepIndex++)
        {
            string? runScript = ReadOptionalScalar(steps[stepIndex], "run");
            if (runScript is null)
            {
                continue;
            }

            MatchCollection commands = Regex.Matches(
                NormalizeLineEndings(runScript),
                @"(?m)^(?<command>dotnet (?:restore|build|test|format|list)\b[^\r\n]*)$");
            dotnetInvocations.AddRange(commands.Select(match => (stepIndex, match.Groups["command"].Value, runScript)));
        }

        Assert.Equal(expectedDotnetCommands.Length, dotnetInvocations.Count);
        foreach (string expectedCommand in expectedDotnetCommands)
        {
            (int stepIndex, string command, string runScript) = Assert.Single(
                dotnetInvocations,
                invocation => invocation.Command == expectedCommand);
            Assert.True(stepIndex > validatorIndex, $"Validator must run before {command}.");
            Assert.Equal(
                $"if [[ \"$USE_LOCAL_MALIEV_DEPENDENCIES\" == \"true\" ]]; then\n" +
                $"  export GITHUB_ACTIONS=false\n" +
                $"fi\n" +
                expectedCommand,
                NormalizeLineEndings(runScript).TrimEnd());
        }

        Assert.Equal(
            expectedDotnetCommands.Length,
            dotnetInvocations.Sum(invocation => Regex.Matches(invocation.Script, "export GITHUB_ACTIONS=false").Count));
        Assert.DoesNotContain("eval ", source, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("bash -c", source, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("${{ secrets.", source, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("contents: write", source, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("packages: write", source, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("id-token: write", source, StringComparison.OrdinalIgnoreCase);
    }

    private static YamlStream ReadYaml(string source)
    {
        YamlStream yaml = [];
        yaml.Load(new StringReader(source));
        Assert.Single(yaml.Documents);
        return yaml;
    }

    private static YamlMappingNode[] ReadActionSteps(string source)
    {
        YamlMappingNode root = Assert.IsType<YamlMappingNode>(ReadYaml(source).Documents.Single().RootNode);
        YamlSequenceNode steps = Assert.IsType<YamlSequenceNode>(ReadNode(ReadMapping(root, "runs"), "steps"));
        return steps.Children.Select(Assert.IsType<YamlMappingNode>).ToArray();
    }

    private static YamlMappingNode ReadMapping(YamlMappingNode mapping, string key) =>
        Assert.IsType<YamlMappingNode>(ReadNode(mapping, key));

    private static YamlNode ReadNode(YamlMappingNode mapping, string key) => mapping.Children
        .Single(pair => Assert.IsType<YamlScalarNode>(pair.Key).Value == key)
        .Value;

    private static string ReadScalar(YamlMappingNode mapping, string key) =>
        Assert.IsType<YamlScalarNode>(ReadNode(mapping, key)).Value ??
        throw new InvalidDataException($"Expected a non-null scalar value for '{key}'.");

    private static string? ReadOptionalScalar(YamlMappingNode mapping, string key)
    {
        foreach ((YamlNode nodeKey, YamlNode value) in mapping.Children)
        {
            if (Assert.IsType<YamlScalarNode>(nodeKey).Value == key)
            {
                return Assert.IsType<YamlScalarNode>(value).Value;
            }
        }

        return null;
    }

    private static bool ContainsDotnetCommand(YamlMappingNode step) =>
        ReadOptionalScalar(step, "run") is string runScript &&
        Regex.IsMatch(runScript, @"(?m)^dotnet (?:restore|build|test|format|list)\b");

    private static ProcessResult RunValidatorFixture(string source, string input)
    {
        YamlMappingNode validator = Assert.Single(
            ReadActionSteps(source),
            step => ReadOptionalScalar(step, "name") == "Validate local MALIEV dependency mode");
        string githubEnvironmentPath = $"/tmp/legacy-workflows-github-env-{Guid.NewGuid():N}";
        string fixtureScript =
            "(\n" + ReadScalar(validator, "run") + "\n)\n" +
            "status=$?\n" +
            "if [[ -f \"$GITHUB_ENV\" ]]; then cat \"$GITHUB_ENV\"; rm -f \"$GITHUB_ENV\"; fi\n" +
            "exit $status\n";
        return RunBashFixture(
            fixtureScript,
            ("GITHUB_ENV", githubEnvironmentPath),
            ("USE_LOCAL_MALIEV_DEPENDENCIES_INPUT", input));
    }

    private static ProcessResult RunBashFixture(string script, params (string Name, string Value)[] environment)
    {
        foreach ((string name, _) in environment)
        {
            Assert.Matches("^[A-Z][A-Z0-9_]*$", name);
        }

        lock (BashEnvironmentLock)
        {
            Dictionary<string, string?> originalEnvironment = environment
                .Select(variable => variable.Name)
                .Append("WSLENV")
                .Distinct(StringComparer.Ordinal)
                .ToDictionary(
                    name => name,
                    Environment.GetEnvironmentVariable,
                    StringComparer.Ordinal);
            try
            {
                foreach ((string name, string value) in environment)
                {
                    Environment.SetEnvironmentVariable(name, value);
                }

                Environment.SetEnvironmentVariable(
                    "WSLENV",
                    string.Join(':', environment.Select(variable => $"{variable.Name}/u")));

                ProcessStartInfo startInfo = new("bash")
                {
                    WorkingDirectory = FindRepositoryRoot(),
                    RedirectStandardInput = true,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    UseShellExecute = false,
                };

                using Process process = Process.Start(startInfo)!;
                process.StandardInput.Write(script);
                process.StandardInput.Close();
                string standardOutput = process.StandardOutput.ReadToEnd();
                string standardError = process.StandardError.ReadToEnd();
                process.WaitForExit();
                return new ProcessResult(process.ExitCode, standardOutput + standardError);
            }
            finally
            {
                foreach ((string name, string? value) in originalEnvironment)
                {
                    Environment.SetEnvironmentVariable(name, value);
                }
            }
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

    private static void AssertExclusivePullRequestTrigger(string source)
    {
        string[] lines = source.Split('\n');
        int onLineIndex = Array.IndexOf(lines, "on:");
        Assert.True(onLineIndex >= 0, "Expected a block-style on mapping.");

        List<string> triggers = [];
        for (int lineIndex = onLineIndex + 1; lineIndex < lines.Length; lineIndex++)
        {
            string line = lines[lineIndex];
            if (string.IsNullOrWhiteSpace(line))
            {
                continue;
            }

            if (!line.StartsWith(' '))
            {
                break;
            }

            Match trigger = Regex.Match(line, @"^ {2}(?<trigger>[A-Za-z0-9_-]+):");
            if (trigger.Success)
            {
                triggers.Add(trigger.Groups["trigger"].Value);
            }
        }

        Assert.Equal(["pull_request"], triggers);
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
