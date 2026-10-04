using System.Diagnostics;
using YamlDotNet.RepresentationModel;
using Xunit;

namespace Legacy.Maliev.Workflows.Tests;

public sealed class JwtScannerCallerScopeTests
{
    private const string Reusable = ".github/workflows/dotnet-validate.yml";
    private const string Composite = "actions/dotnet-validate/action.yml";

    public static TheoryData<string, string, string> RootResourceCases
    {
        get
        {
            TheoryData<string, string, string> cases = [];
            foreach (string caller in new[] { Reusable, Composite })
            {
                foreach (string name in new[] { "JwtSigningKey", "BrevoApiKey" })
                {
                    foreach (string extension in new[] { ".resx", ".Designer.cs", ".xml" })
                    {
                        cases.Add(caller, extension, name);
                    }
                }
            }

            return cases;
        }
    }

    [Theory]
    [MemberData(nameof(RootResourceCases))]
    public async Task NestedCaller_RejectsTrackedResourceOutsideItsWorkingDirectory(
        string caller, string extension, string resourceName)
    {
        await WithCaller(async root =>
        {
            string relative = "Properties/Resources" + extension;
            Directory.CreateDirectory(Path.Combine(root, "Properties"));
            await File.WriteAllTextAsync(Path.Combine(root, relative), Resource(extension, resourceName), TestContext.Current.CancellationToken);
            Assert.Equal(0, (await Run("git", root, ["add", "--", relative])).ExitCode);
            string nested = Directory.CreateDirectory(Path.Combine(root, "nested", "deeper")).FullName;

            // Execute the real caller step and real trusted scanner; no CLI replacements.
            ProcessResult result = await Scan(caller, nested);
            Assert.Equal(1, result.ExitCode);
            Assert.DoesNotContain("synthetic-resource-value", result.Output, StringComparison.Ordinal);
        });
    }

    [Theory]
    [InlineData(Reusable)]
    [InlineData(Composite)]
    public async Task NestedCaller_AcceptsTrackedEmptyResource(string caller)
    {
        await WithCaller(async root =>
        {
            await File.WriteAllTextAsync(Path.Combine(root, "empty.resx"),
                "<root><data name=\"JwtSigningKey\"><value> </value></data></root>", TestContext.Current.CancellationToken);
            Assert.Equal(0, (await Run("git", root, ["add", "--", "empty.resx"])).ExitCode);
            string nested = Directory.CreateDirectory(Path.Combine(root, "nested", "deeper")).FullName;
            Assert.Equal(0, (await Scan(caller, nested)).ExitCode);
        });
    }

    [Theory]
    [InlineData(Reusable)]
    [InlineData(Composite)]
    public async Task NestedCaller_DoesNotInspectUntrackedResource(string caller)
    {
        await WithCaller(async root =>
        {
            await File.WriteAllTextAsync(Path.Combine(root, "untracked.resx"), Resource(".resx", "JwtSigningKey"), TestContext.Current.CancellationToken);
            string nested = Directory.CreateDirectory(Path.Combine(root, "nested", "deeper")).FullName;
            Assert.Equal(0, (await Scan(caller, nested)).ExitCode);
        });
    }

    [Theory]
    [InlineData(Reusable)]
    [InlineData(Composite)]
    public async Task NestedCaller_RejectsMalformedTrackedRootResourceWithoutRawXml(string caller)
    {
        await WithCaller(async root =>
        {
            await File.WriteAllTextAsync(Path.Combine(root, "malformed.resx"), "<root><synthetic-private-document", TestContext.Current.CancellationToken);
            Assert.Equal(0, (await Run("git", root, ["add", "--", "malformed.resx"])).ExitCode);
            string nested = Directory.CreateDirectory(Path.Combine(root, "nested", "deeper")).FullName;
            ProcessResult result = await Scan(caller, nested);
            Assert.Equal(1, result.ExitCode);
            Assert.DoesNotContain("synthetic-private-document", result.Output, StringComparison.Ordinal);
        });
    }

    [Theory]
    [InlineData(Reusable)]
    [InlineData(Composite)]
    public async Task NestedCaller_RejectsDeletedTrackedRootResourceAsIncompleteInspection(string caller)
    {
        await WithCaller(async root =>
        {
            string resource = Path.Combine(root, "deleted.resx");
            await File.WriteAllTextAsync(resource, Resource(".resx", "JwtSigningKey"), TestContext.Current.CancellationToken);
            Assert.Equal(0, (await Run("git", root, ["add", "--", "deleted.resx"])).ExitCode);
            File.Delete(resource);
            string nested = Directory.CreateDirectory(Path.Combine(root, "nested", "deeper")).FullName;
            ProcessResult result = await Scan(caller, nested);
            Assert.Equal(1, result.ExitCode);
            Assert.DoesNotContain("synthetic-resource-value", result.Output, StringComparison.Ordinal);
        });
    }

    [Theory]
    [InlineData(Reusable)]
    [InlineData(Composite)]
    public async Task NestedCaller_DoesNotInspectOtherSiblingRepository(string caller)
    {
        await WithCaller(async root =>
        {
            string sibling = Directory.CreateDirectory(Path.Combine(root, "untracked-sibling")).FullName;
            Assert.Equal(0, (await Run("git", sibling, ["init", "--quiet"])).ExitCode);
            await File.WriteAllTextAsync(Path.Combine(sibling, "credential.resx"), Resource(".resx", "JwtSigningKey"), TestContext.Current.CancellationToken);
            Assert.Equal(0, (await Run("git", sibling, ["add", "--", "credential.resx"])).ExitCode);
            string nested = Directory.CreateDirectory(Path.Combine(root, "nested", "deeper")).FullName;
            Assert.Equal(0, (await Scan(caller, nested)).ExitCode);
        });
    }

    private static string Resource(string extension, string name) => extension switch
    {
        ".resx" => $"<root><data name=\"{name}\"><value>synthetic-resource-value</value></data></root>",
        ".Designer.cs" => "/// Looks up a localized string similar to synthetic-resource-value.\n" +
            $"internal static string {name} {{ get {{ return null; }} }}\n",
        ".xml" => $"<doc><members><member name=\"P:Fixture.Resources.{name}\"><summary>" +
            "Looks up a localized string similar to synthetic-resource-value.</summary></member></members></doc>",
        _ => throw new ArgumentOutOfRangeException(nameof(extension)),
    };

    private static async Task WithCaller(Func<string, Task> assertion)
    {
        string root = Path.Combine(Path.GetTempPath(), "jwt-caller-scope-" + Guid.NewGuid().ToString("N") + " workspace");
        Directory.CreateDirectory(root);
        try
        {
            Assert.Equal(0, (await Run("git", root, ["init", "--quiet"])).ExitCode);
            await File.WriteAllTextAsync(Path.Combine(root, "tracked.txt"), "safe", TestContext.Current.CancellationToken);
            Assert.Equal(0, (await Run("git", root, ["add", "--", "tracked.txt"])).ExitCode);
            await assertion(root);
        }
        finally
        {
            string full = Path.GetFullPath(root);
            Assert.StartsWith(Path.GetFullPath(Path.GetTempPath()), full, StringComparison.OrdinalIgnoreCase);
            Assert.StartsWith("jwt-caller-scope-", Path.GetFileName(full), StringComparison.Ordinal);
            foreach (string file in Directory.EnumerateFiles(full, "*", SearchOption.AllDirectories))
            {
                File.SetAttributes(file, FileAttributes.Normal);
            }

            Directory.Delete(full, recursive: true);
        }
    }

    private static Task<ProcessResult> Scan(string caller, string directory)
    {
        string root = RepositoryContractTests.FindRepositoryRoot();
        YamlStream yaml = [];
        yaml.Load(new StringReader(File.ReadAllText(Path.Combine(root, caller))));
        YamlMappingNode workflow = Assert.IsType<YamlMappingNode>(yaml.Documents.Single().RootNode);
        YamlMappingNode job = caller == Composite
            ? Assert.IsType<YamlMappingNode>(workflow.Children[new YamlScalarNode("runs")])
            : Assert.IsType<YamlMappingNode>(Assert.IsType<YamlMappingNode>(workflow.Children[new YamlScalarNode("jobs")]).Children[new YamlScalarNode("validate")]);
        YamlMappingNode step = Assert.Single(Assert.IsType<YamlSequenceNode>(job.Children[new YamlScalarNode("steps")]).Children.Cast<YamlMappingNode>(),
            value => Scalar(value, "name") == "Scan JWT signing resources");
        return Run("pwsh", directory, ["-NoProfile", "-Command", Scalar(step, "run")], new()
        {
            ["SHARED_TOOLS_PATH"] = root,
            ["GITHUB_ACTION_PATH"] = Path.Combine(root, "actions", "dotnet-validate"),
        });
    }

    private static string Scalar(YamlMappingNode node, string key) =>
        node.Children.TryGetValue(new YamlScalarNode(key), out YamlNode? value) ? ((YamlScalarNode)value).Value ?? "" : "";

    private static async Task<ProcessResult> Run(string command, string directory, string[] arguments,
        Dictionary<string, string>? environment = null)
    {
        ProcessStartInfo start = new(command)
        {
            WorkingDirectory = directory,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        foreach (string argument in arguments)
        {
            start.ArgumentList.Add(argument);
        }

        foreach ((string key, string value) in environment ?? [])
        {
            start.Environment[key] = value;
        }

        using Process process = Process.Start(start) ?? throw new InvalidOperationException("Fixture process did not start.");
        Task<string> output = process.StandardOutput.ReadToEndAsync(TestContext.Current.CancellationToken);
        Task<string> error = process.StandardError.ReadToEndAsync(TestContext.Current.CancellationToken);
        try
        {
            await process.WaitForExitAsync(TestContext.Current.CancellationToken).WaitAsync(TimeSpan.FromMinutes(1), TestContext.Current.CancellationToken);
            return new ProcessResult(process.ExitCode, await output + await error);
        }
        finally
        {
            if (!process.HasExited)
            {
                process.Kill(entireProcessTree: true);
                await process.WaitForExitAsync(CancellationToken.None).WaitAsync(TimeSpan.FromSeconds(10));
            }
        }
    }

    private sealed record ProcessResult(int ExitCode, string Output);
}
