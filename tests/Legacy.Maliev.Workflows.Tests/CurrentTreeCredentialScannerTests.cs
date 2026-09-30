using System.Diagnostics;
using System.Text.Json;
using YamlDotNet.RepresentationModel;
using Xunit;

namespace Legacy.Maliev.Workflows.Tests;

public sealed class CurrentTreeCredentialScannerTests
{
    [Fact]
    public void ReusableValidation_WhenBothActualCallersRun_UsesDistinctConcurrencyGroups()
    {
        YamlMappingNode Read(string path)
        {
            YamlStream yaml = new();
            yaml.Load(new StringReader(File.ReadAllText(Path.Combine(RepositoryContractTests.FindRepositoryRoot(), path))));
            return (YamlMappingNode)yaml.Documents.Single().RootNode;
        }

        YamlMappingNode reusable = Read(".github/workflows/dotnet-validate.yml");
        YamlMappingNode concurrency = (YamlMappingNode)reusable.Children[new YamlScalarNode("concurrency")];
        string expression = Scalar(concurrency, "group");
        Assert.Equal("true", Scalar(concurrency, "cancel-in-progress"));
        YamlMappingNode callers = (YamlMappingNode)Read(".github/workflows/validate.yml").Children[new YamlScalarNode("jobs")];
        List<string> groups = [];
        foreach (YamlMappingNode caller in callers.Children.Values.Cast<YamlMappingNode>())
        {
            YamlMappingNode inputs = (YamlMappingNode)caller.Children[new YamlScalarNode("with")];
            string directory = Scalar(inputs, "working-directory");
            if (directory.Length == 0) { directory = "."; }
            string group = expression.Replace("${{ github.workflow }}", "validate", StringComparison.Ordinal)
                .Replace("${{ github.ref }}", "refs/pull/246/merge", StringComparison.Ordinal)
                .Replace("${{ inputs.solution }}", Scalar(inputs, "solution"), StringComparison.Ordinal)
                .Replace("${{ inputs.working-directory }}", directory, StringComparison.Ordinal);
            Assert.DoesNotContain("${{", group, StringComparison.Ordinal);
            groups.Add(group);
        }
        Assert.Equal(2, groups.Count);
        Assert.Equal(groups.Count, groups.Distinct(StringComparer.OrdinalIgnoreCase).Count());
    }

    [Fact]
    public void BothValidationSurfaces_WhenParsed_GateCurrentTreeBeforeRestoreWithoutReplacingExistingChecks()
    {
        foreach (string path in new[] { "actions/dotnet-validate/action.yml", ".github/workflows/dotnet-validate.yml" })
        {
            YamlMappingNode[] steps = Steps(path);
            int scanner = Array.FindIndex(steps, step => Scalar(step, "name") == "Scan tracked current-tree credentials");
            int restore = Array.FindIndex(steps, step => Scalar(step, "name") == "Restore");
            int history = Array.FindIndex(steps, step => Scalar(step, "name") == "Scan repository for leaked secrets");
            int resource = Array.FindIndex(steps, step => Scalar(step, "name") == "Scan JWT signing resources");
            Assert.True(scanner >= 0 && scanner < restore, $"Current-tree scan missing before restore in {path}");
            Assert.True(history >= 0 && history < restore);
            Assert.True(resource >= 0 && resource < restore);
            Assert.False(steps[scanner].Children.ContainsKey(new YamlScalarNode("continue-on-error")));
        }
    }

    [Fact]
    public async Task CompositeScanner_WhenActualStepRunsFromNestedCaller_ScansCallerNotActionCheckout()
    {
        string root = RepositoryContractTests.FindRepositoryRoot();
        string script = Scalar(Steps("actions/dotnet-validate/action.yml")
            .Single(step => Scalar(step, "name") == "Scan tracked current-tree credentials"), "run");
        string temporary = Path.Combine(Path.GetTempPath(), "maliev-current-tree-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(temporary);
        try
        {
            await Run("git", temporary, ["init", "--quiet"]);
            string candidate = Path.Combine(temporary, "candidate.txt");
            await File.WriteAllTextAsync(candidate, "safe", TestContext.Current.CancellationToken);
            await Run("git", temporary, ["add", "candidate.txt"]);
            string nested = Directory.CreateDirectory(Path.Combine(temporary, "nested")).FullName;
            Dictionary<string, string> environment = new() { ["GITHUB_ACTION_PATH"] = Path.Combine(root, "actions/dotnet-validate") };
            Assert.Equal(0, (await Run("pwsh", nested, ["-NoProfile", "-Command", script], environment)).ExitCode);
            await File.WriteAllTextAsync(candidate, "Pass" + "word=synthetic-value", TestContext.Current.CancellationToken);
            var failed = await Run("pwsh", nested, ["-NoProfile", "-Command", script], environment);
            Assert.Equal(1, failed.ExitCode);
            Assert.DoesNotContain("synthetic-value", failed.Output, StringComparison.Ordinal);
            environment["GITHUB_ACTION_PATH"] = temporary;
            Assert.Equal(2, (await Run("pwsh", nested, ["-NoProfile", "-Command", script], environment)).ExitCode);
        }
        finally { DeleteFixture(temporary); }
    }

    [Theory]
    [InlineData("", "MALIEV-Co-Ltd/Legacy.Maliev.Workflows", false)]
    [InlineData("main", "MALIEV-Co-Ltd/Legacy.Maliev.Workflows", false)]
    [InlineData("1111111111111111111111111111111111111111", "untrusted/caller", false)]
    [InlineData("1111111111111111111111111111111111111111", "MALIEV-Co-Ltd/Legacy.Maliev.Workflows", true)]
    public async Task ReusableAcquisition_WhenIdentityIsValidated_OnlyExactCalledRepositoryAndShaAreAdmitted(
        string sha, string repository, bool admitted)
    {
        string script = Scalar(Steps(".github/workflows/dotnet-validate.yml")
            .Single(step => Scalar(step, "name") == "Validate shared scanner identity"), "run");
        string output = Path.GetTempFileName();
        try
        {
            var result = await Run("pwsh", RepositoryContractTests.FindRepositoryRoot(), ["-NoProfile", "-Command", script],
                new()
                {
                    ["SHARED_JOB_IDENTITY"] = JsonSerializer.Serialize(new { workflow_repository = repository, workflow_sha = sha }),
                    ["GITHUB_OUTPUT"] = output,
                    ["GITHUB_WORKSPACE"] = Path.GetDirectoryName(output)!,
                });
            Assert.Equal(admitted ? 0 : 2, result.ExitCode);
            Assert.DoesNotContain(sha.Length == 0 ? "Traceback" : sha, result.Output, StringComparison.Ordinal);
            Assert.Equal(admitted ? $"workflow_sha={sha}\n" : "", await File.ReadAllTextAsync(output, TestContext.Current.CancellationToken));
        }
        finally { File.Delete(output); }
    }

    [Theory]
    [InlineData("")]
    [InlineData("not-json")]
    [InlineData("null")]
    [InlineData("[]")]
    [InlineData("{\"status\":\"success\"}")]
    [InlineData("{\"workflow_repository\":123,\"workflow_sha\":null}")]
    [InlineData("{\"workflow_repository\":\"MALIEV-Co-Ltd/Legacy.Maliev.Workflows\",\"github_sha\":\"1111111111111111111111111111111111111111\"}")]
    public async Task ReusableAcquisition_WhenCalledIdentityIsMissingOrMalformed_NoCallerFallbackOrOutput(string identity)
    {
        string script = Scalar(Steps(".github/workflows/dotnet-validate.yml")
            .Single(step => Scalar(step, "name") == "Validate shared scanner identity"), "run");
        string output = Path.GetTempFileName();
        try
        {
            var result = await Run("pwsh", RepositoryContractTests.FindRepositoryRoot(), ["-NoProfile", "-Command", script],
                new() { ["SHARED_JOB_IDENTITY"] = identity, ["GITHUB_OUTPUT"] = output });
            Assert.Equal(2, result.ExitCode);
            Assert.Equal("", await File.ReadAllTextAsync(output, TestContext.Current.CancellationToken));
            Assert.DoesNotContain(identity.Length == 0 ? "Traceback" : identity, result.Output, StringComparison.Ordinal);
        }
        finally { File.Delete(output); }
    }

    [Fact]
    public async Task ReusableAcquisition_WhenCheckoutHeadDiffers_FailsBeforeCallerScan()
    {
        string script = Scalar(Steps(".github/workflows/dotnet-validate.yml")
            .Single(step => Scalar(step, "name") == "Verify shared scanner checkout"), "run");
        var result = await Run("pwsh", RepositoryContractTests.FindRepositoryRoot(), ["-NoProfile", "-Command", script],
            new()
            {
                ["SHARED_WORKFLOW_SHA"] = "1111111111111111111111111111111111111111",
                ["SHARED_TOOLS_PATH"] = RepositoryContractTests.FindRepositoryRoot(),
            });
        Assert.Equal(2, result.ExitCode);
    }

    [Fact]
    public async Task ReusableAcquisition_WhenReservedToolsPathAlreadyExists_FailsWithoutOverwritingCaller()
    {
        string script = Scalar(Steps(".github/workflows/dotnet-validate.yml")
            .Single(step => Scalar(step, "name") == "Validate shared scanner identity"), "run");
        string temporary = Path.Combine(Path.GetTempPath(), "maliev-current-tree-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(Path.Combine(temporary, ".maliev-validation-tools"));
        string output = Path.Combine(temporary, "output.txt");
        await File.WriteAllTextAsync(output, "", TestContext.Current.CancellationToken);
        try
        {
            var result = await Run("pwsh", temporary, ["-NoProfile", "-Command", script], new()
            {
                ["GITHUB_WORKSPACE"] = temporary,
                ["GITHUB_OUTPUT"] = output,
                ["SHARED_JOB_IDENTITY"] = JsonSerializer.Serialize(new
                {
                    workflow_repository = "MALIEV-Co-Ltd/Legacy.Maliev.Workflows",
                    workflow_sha = "1111111111111111111111111111111111111111",
                }),
            });
            Assert.Equal(2, result.ExitCode);
            Assert.Equal("", await File.ReadAllTextAsync(output, TestContext.Current.CancellationToken));
        }
        finally { DeleteFixture(temporary); }
    }

    [Fact]
    public async Task ReusableScanner_WhenActualVerifiedSharedCheckoutRuns_InspectsSeparateNestedCaller()
    {
        string root = RepositoryContractTests.FindRepositoryRoot();
        string temporary = Path.Combine(Path.GetTempPath(), "maliev-current-tree-" + Guid.NewGuid().ToString("N"));
        string tools = Directory.CreateDirectory(Path.Combine(temporary, "tools")).FullName;
        string caller = Directory.CreateDirectory(Path.Combine(temporary, "caller")).FullName;
        try
        {
            foreach (string path in new[] { "scripts/Invoke-CurrentTreeCredentialScan.ps1", "tools/security/current_tree_secrets.py",
                "scripts/Invoke-JwtSigningResourceScan.ps1", "scripts/JwtSigningResourceScanner.ps1" })
            {
                string target = Path.Combine(tools, path);
                Directory.CreateDirectory(Path.GetDirectoryName(target)!);
                File.Copy(Path.Combine(root, path), target);
            }
            Assert.Equal(0, (await Run("git", tools, ["init", "--quiet"])).ExitCode);
            Assert.Equal(0, (await Run("git", tools, ["add", "."])).ExitCode);
            Assert.Equal(0, (await Run("git", tools,
                ["-c", "user.name=Scanner fixture", "-c", "user.email=fixture@example.invalid", "commit", "--quiet", "-m", "safe tools fixture"])).ExitCode);
            string head = (await Run("git", tools, ["rev-parse", "HEAD"])).Output.Trim();
            Dictionary<string, string> environment = new() { ["SHARED_TOOLS_PATH"] = tools, ["SHARED_WORKFLOW_SHA"] = head };
            string verify = Scalar(Steps(".github/workflows/dotnet-validate.yml")
                .Single(step => Scalar(step, "name") == "Verify shared scanner checkout"), "run");
            Assert.Equal(0, (await Run("pwsh", caller, ["-NoProfile", "-Command", verify], environment)).ExitCode);
            Assert.Equal(0, (await Run("git", caller, ["init", "--quiet"])).ExitCode);
            string candidate = Path.Combine(caller, "candidate.txt");
            await File.WriteAllTextAsync(candidate, "safe", TestContext.Current.CancellationToken);
            Assert.Equal(0, (await Run("git", caller, ["add", "candidate.txt"])).ExitCode);
            string nested = Directory.CreateDirectory(Path.Combine(caller, "nested")).FullName;
            string scan = Scalar(Steps(".github/workflows/dotnet-validate.yml")
                .Single(step => Scalar(step, "name") == "Scan tracked current-tree credentials"), "run");
            Assert.Equal(0, (await Run("pwsh", nested, ["-NoProfile", "-Command", scan], environment)).ExitCode);
            await File.WriteAllTextAsync(candidate, "Pass" + "word=synthetic-value", TestContext.Current.CancellationToken);
            var result = await Run("pwsh", nested, ["-NoProfile", "-Command", scan], environment);
            Assert.Equal(1, result.ExitCode);
            Assert.DoesNotContain("synthetic-value", result.Output, StringComparison.Ordinal);
            File.Delete(Path.Combine(tools, "scripts/Invoke-JwtSigningResourceScan.ps1"));
            Assert.Equal(2, (await Run("pwsh", caller, ["-NoProfile", "-Command", verify], environment)).ExitCode);
        }
        finally { DeleteFixture(temporary); }
    }

    [Fact]
    public async Task GeneralScanner_WhenSyntheticBehaviorSuiteRuns_ProtectsTrackedCurrentTreeAndRedactsFailures()
    {
        string root = RepositoryContractTests.FindRepositoryRoot();
        Assert.True(File.Exists(Path.Combine(root, "tools/security/current_tree_secrets.py")),
            "General current-tree credential scanner is missing.");
        ProcessStartInfo start = new(OperatingSystem.IsWindows() ? "python" : "python3")
        {
            WorkingDirectory = root,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
        };
        start.ArgumentList.Add("-B");
        start.ArgumentList.Add("-m");
        start.ArgumentList.Add("unittest");
        start.ArgumentList.Add("discover");
        start.ArgumentList.Add("-s");
        start.ArgumentList.Add("tools/security/tests");
        start.ArgumentList.Add("-v");
        start.Environment["PYTHONDONTWRITEBYTECODE"] = "1";
        using Process process = Process.Start(start)!;
        CancellationToken cancellation = TestContext.Current.CancellationToken;
        Task<string> stdout = process.StandardOutput.ReadToEndAsync(cancellation);
        Task<string> stderr = process.StandardError.ReadToEndAsync(cancellation);
        await process.WaitForExitAsync(cancellation).WaitAsync(TimeSpan.FromMinutes(3), cancellation);
        Assert.True(process.ExitCode == 0, await stdout + await stderr);
    }

    private static YamlMappingNode[] Steps(string path)
    {
        YamlStream stream = new();
        stream.Load(new StringReader(File.ReadAllText(Path.Combine(RepositoryContractTests.FindRepositoryRoot(), path))));
        YamlMappingNode root = (YamlMappingNode)stream.Documents.Single().RootNode;
        YamlMappingNode container = path.StartsWith("actions/", StringComparison.Ordinal)
            ? (YamlMappingNode)root.Children[new YamlScalarNode("runs")]
            : (YamlMappingNode)((YamlMappingNode)root.Children[new YamlScalarNode("jobs")]).Children[new YamlScalarNode("validate")];
        return ((YamlSequenceNode)container.Children[new YamlScalarNode("steps")]).Children.Cast<YamlMappingNode>().ToArray();
    }

    private static string Scalar(YamlMappingNode node, string key) =>
        node.Children.TryGetValue(new YamlScalarNode(key), out YamlNode? value) ? ((YamlScalarNode)value).Value ?? "" : "";

    private static async Task<(int ExitCode, string Output)> Run(string command, string directory,
        string[] arguments, Dictionary<string, string>? environment = null)
    {
        ProcessStartInfo start = new(command)
        {
            WorkingDirectory = directory,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
        };
        foreach (string argument in arguments) { start.ArgumentList.Add(argument); }
        foreach (var item in environment ?? []) { start.Environment[item.Key] = item.Value; }
        using Process process = Process.Start(start)!;
        CancellationToken cancellation = TestContext.Current.CancellationToken;
        Task<string> stdout = process.StandardOutput.ReadToEndAsync(cancellation);
        Task<string> stderr = process.StandardError.ReadToEndAsync(cancellation);
        try
        {
            await process.WaitForExitAsync(cancellation).WaitAsync(TimeSpan.FromMinutes(1), cancellation);
            return (process.ExitCode, await stdout + await stderr);
        }
        finally
        {
            if (!process.HasExited) { process.Kill(entireProcessTree: true); }
        }
    }

    private static void DeleteFixture(string path)
    {
        string fullPath = Path.GetFullPath(path);
        Assert.StartsWith(Path.GetFullPath(Path.GetTempPath()), fullPath, StringComparison.OrdinalIgnoreCase);
        Assert.StartsWith("maliev-current-tree-", Path.GetFileName(fullPath), StringComparison.Ordinal);
        foreach (string file in Directory.EnumerateFiles(fullPath, "*", SearchOption.AllDirectories))
        {
            File.SetAttributes(file, FileAttributes.Normal);
        }
        Directory.Delete(fullPath, recursive: true);
    }
}
