using System.Diagnostics;
using System.Text.Json;
using YamlDotNet.RepresentationModel;
using Xunit;

namespace Legacy.Maliev.Workflows.Tests;

[Collection("Packaged image acceptance")]
public sealed class PackagedIntranetAssetGateTests
{
    // Independent current compatibility corpus from Intranet b374ef520863404e9c53ef10b017a5bd77da45b8.
    // Removing any asset check must let a deliberately broken real image through.
    private static readonly string[] Assets =
    [
        "Legacy.Maliev.Intranet.dll", "Legacy.Maliev.Intranet.deps.json", "Legacy.Maliev.Intranet.runtimeconfig.json",
        "wwwroot/css/ibm-plex-sans-thai.css", "wwwroot/css/site.css", "wwwroot/js/compat-shell.js",
        "wwwroot/fonts/ibm-plex-sans-thai/IBMPlexSansThai-Regular.woff2",
        "wwwroot/fonts/ibm-plex-sans-thai/IBMPlexSansThai-SemiBold.woff2",
        "wwwroot/fonts/ibm-plex-sans-thai/LICENSE.txt",
    ];

    public static TheoryData<string, bool> BrokenAssets
    {
        get
        {
            TheoryData<string, bool> result = [];
            foreach (string asset in Assets)
            {
                result.Add(asset, false);
                result.Add(asset, true);
            }

            return result;
        }
    }

    [Fact]
    public async Task CompletePackagedImage_IsAcceptedWithoutApplicationStartup()
    {
        await WithImage(null, false, async image =>
        {
            ProcessResult result = await RunGate(image, "MALIEV-Co-Ltd/Legacy.Maliev.Intranet");
            Assert.Equal(0, result.ExitCode);
            using JsonDocument receipt = JsonDocument.Parse(result.Output);
            Assert.Equal("source-image-artifacts-verified", receipt.RootElement.GetProperty("status").GetString());
            Assert.Equal(9, receipt.RootElement.GetProperty("files").GetArrayLength());
            Assert.Equal("", (await Native("docker", ["ps", "--all", "--quiet", "--filter", $"ancestor={image}"])).Output.Trim());
        });
    }

    [Theory]
    [MemberData(nameof(BrokenAssets))]
    public async Task MissingOrEmptyPackagedAsset_RejectsTheActualImage(string asset, bool empty)
    {
        await WithImage(asset, empty, async image =>
        {
            ProcessResult result = await RunGate(image, "MALIEV-Co-Ltd/Legacy.Maliev.Intranet");
            Assert.NotEqual(0, result.ExitCode);
            Assert.DoesNotContain("accepted", result.Output, StringComparison.Ordinal);
            Assert.Equal("", (await Native("docker", ["ps", "--all", "--quiet", "--filter", $"ancestor={image}"])).Output.Trim());
        });
    }

    [Fact]
    public async Task UnavailableImage_FailsClosedWithRedactedDiagnostics()
    {
        ProcessResult result = await RunGate("sha256:" + new string('0', 64), "MALIEV-Co-Ltd/Legacy.Maliev.Intranet");
        Assert.NotEqual(0, result.ExitCode);
        Assert.DoesNotContain("accepted", result.Output, StringComparison.Ordinal);
        Assert.DoesNotContain("Traceback", result.Error, StringComparison.Ordinal);
    }

    [Fact]
    public async Task OtherService_DoesNotAcquireAnIntranetAssetRequirement()
    {
        ProcessResult result = await RunGate("sha256:" + new string('0', 64), "MALIEV-Co-Ltd/Legacy.Maliev.CountryService");
        Assert.Equal(0, result.ExitCode);
        using JsonDocument receipt = JsonDocument.Parse(result.Output);
        Assert.Equal("not-applicable", receipt.RootElement.GetProperty("status").GetString());
    }

    [Fact]
    public async Task IntranetBff_DoesNotAcquireTheCompatibilityApplicationAssetRequirement()
    {
        await WithImage(null, false, async image =>
        {
            ProcessResult result = await RunGate(image, "MALIEV-Co-Ltd/Legacy.Maliev.Intranet",
                "Legacy.Maliev.Intranet.Bff/Dockerfile");
            Assert.Equal(0, result.ExitCode);
            using JsonDocument receipt = JsonDocument.Parse(result.Output);
            Assert.Equal("bff", receipt.RootElement.GetProperty("role").GetString());
            Assert.Equal(3, receipt.RootElement.GetProperty("files").GetArrayLength());
        }, bff: true);
    }

    [Theory]
    [InlineData("Legacy.Maliev.Intranet.Bff.dll", false)]
    [InlineData("Legacy.Maliev.Intranet.Bff.dll", true)]
    [InlineData("Legacy.Maliev.Intranet.Bff.deps.json", false)]
    [InlineData("Legacy.Maliev.Intranet.Bff.deps.json", true)]
    [InlineData("Legacy.Maliev.Intranet.Bff.runtimeconfig.json", false)]
    [InlineData("Legacy.Maliev.Intranet.Bff.runtimeconfig.json", true)]
    public async Task MissingOrEmptyBffArtifact_RejectsTheActualImage(string artifact, bool empty)
    {
        await WithImage(artifact, empty, async image =>
        {
            ProcessResult result = await RunGate(image, "MALIEV-Co-Ltd/Legacy.Maliev.Intranet",
                "Legacy.Maliev.Intranet.Bff/Dockerfile");
            Assert.NotEqual(0, result.ExitCode);
            Assert.Equal("", (await Native("docker", ["ps", "--all", "--quiet", "--filter", $"ancestor={image}"])).Output.Trim());
        }, bff: true);
    }

    [Fact]
    public async Task UnknownIntranetDockerfile_FailsClosedInsteadOfBypassingAssetValidation()
    {
        ProcessResult result = await RunGate("sha256:" + new string('0', 64), "MALIEV-Co-Ltd/Legacy.Maliev.Intranet",
            "unreviewed/Dockerfile");
        Assert.NotEqual(0, result.ExitCode);
        Assert.DoesNotContain("not-applicable", result.Output, StringComparison.Ordinal);
    }

    [Fact]
    public void PackagedGate_PrecedesAllImagePublicationAndRunsAfterBuild()
    {
        YamlMappingNode[] steps = PublisherSteps();
        int build = Array.FindIndex(steps, step => Scalar(step, "name") == "Build image once for scanning and publication");
        int gate = Array.FindIndex(steps, step => Scalar(step, "name") == "Verify packaged Intranet assets and source revision");
        int publish = Array.FindIndex(steps, step => Scalar(step, "id") == "publish");
        Assert.True(build >= 0 && gate > build && publish > gate);
        Assert.False(steps[gate].Children.ContainsKey(new YamlScalarNode("continue-on-error")));
        Assert.False(steps[gate].Children.ContainsKey(new YamlScalarNode("if")));
        Assert.Equal("python", Scalar(steps[gate], "shell"));
        YamlMappingNode environment = Assert.IsType<YamlMappingNode>(steps[gate].Children[new YamlScalarNode("env")]);
        Assert.Equal("${{ github.repository }}", Scalar(environment, "CALLER_REPOSITORY"));
        Assert.Equal("${{ env.COMMIT_TAG }}", Scalar(environment, "BUILT_IMAGE"));
        Assert.Equal("${{ inputs.dockerfile }}", Scalar(environment, "SOURCE_DOCKERFILE"));
    }

    [Theory]
    [InlineData("test_intranet_publisher_binding.py", 15)]
    [InlineData("test_intranet_publisher_linux_limits.py", 3)]
    public async Task PublisherSourceControls_RunThroughActualEmbeddedScript(string script, int expectedTests)
    {
        string root = RepositoryContractTests.FindRepositoryRoot();
        ProcessStartInfo start = new(OperatingSystem.IsWindows() ? "python" : "python3")
        {
            WorkingDirectory = root,
        };
        start.ArgumentList.Add("-B");
        start.ArgumentList.Add("-W");
        start.ArgumentList.Add("error");
        start.ArgumentList.Add(Path.Combine(root, "tests", script));
        OwnedTestProcess.Result result = await OwnedTestProcess.RunAsync(start,
            cancellationToken: TestContext.Current.CancellationToken);
        Assert.True(result.ExitCode == 0, result.Error);
        Assert.Contains($"Ran {expectedTests} tests", result.Error, StringComparison.Ordinal);
        Assert.Contains("OK", result.Error, StringComparison.Ordinal);
        Assert.Equal("", result.Output);
    }

    private static async Task WithImage(string? brokenAsset, bool empty, Func<string, Task> acceptance, bool bff = false)
    {
        // Observe the missing pipeline behavior before allocating a disposable Docker fixture.
        Assert.Single(PublisherSteps(), step => Scalar(step, "name") == "Verify packaged Intranet assets and source revision");
        string directory = Path.Combine(Path.GetTempPath(), "workflows-packaged-assets-" + Guid.NewGuid().ToString("N"));
        string image = "local/workflows-fixture-" + Guid.NewGuid().ToString("N")
            + "/legacy-maliev-intranet-" + (bff ? "bff" : "compatibility") + ":" + new string('a', 40);
        string owner = Guid.NewGuid().ToString("N");
        string? imageId = null;
        string? createdIdentity = null;
        bool built = false;
        Directory.CreateDirectory(Path.Combine(directory, "assets"));
        try
        {
            string assembly = bff ? "Legacy.Maliev.Intranet.Bff" : "Legacy.Maliev.Intranet";
            string[] required = bff ? [assembly + ".dll", assembly + ".deps.json", assembly + ".runtimeconfig.json"] : Assets;
            foreach (string asset in required)
            {
                if (asset == brokenAsset && !empty)
                {
                    continue;
                }

                string path = Path.Combine(directory, "assets", asset);
                Directory.CreateDirectory(Path.GetDirectoryName(path)!);
                string content = asset.EndsWith(".deps.json", StringComparison.Ordinal)
                    ? JsonSerializer.Serialize(new { libraries = new Dictionary<string, object> { [assembly + "/1.0.0"] = new { } } })
                    : asset.EndsWith(".runtimeconfig.json", StringComparison.Ordinal)
                        ? "{\"runtimeOptions\":{\"tfm\":\"net10.0\"}}" : "synthetic current artifact";
                await File.WriteAllTextAsync(path, asset == brokenAsset ? "" : content,
                    TestContext.Current.CancellationToken);
            }

            // No base-image pull, registry, credentials, network, executable or application startup.
            await File.WriteAllTextAsync(Path.Combine(directory, "Dockerfile"),
                "FROM scratch\nLABEL org.opencontainers.image.revision=" + new string('a', 40)
                + "\nLABEL maliev.fixture.owner=" + owner
                + "\nCOPY assets /app/\nENTRYPOINT [\"/application-must-not-start\"]\n",
                TestContext.Current.CancellationToken);
            ProcessResult build = await Native("docker", ["build", "--network", "none", "--quiet", "--tag", image, directory]);
            Assert.True(build.ExitCode == 0, $"Disposable scratch-image build failed: {build.Error}");
            built = true;
            imageId = (await Native("docker", ["image", "inspect", "--format", "{{.Id}}", image])).Output.Trim();
            Assert.StartsWith("sha256:", imageId, StringComparison.Ordinal);
            Assert.Equal(71, imageId.Length);
            createdIdentity = (await Native("docker", ["image", "inspect", "--format", "{{.Created}}", imageId])).Output.Trim();
            await acceptance(image);
        }
        finally
        {
            Directory.Delete(directory, recursive: true);
            if (built)
            {
                Assert.NotNull(imageId);
                Assert.NotNull(createdIdentity);
                Assert.Equal(imageId, (await Native("docker", ["image", "inspect", "--format", "{{.Id}}", image])).Output.Trim());
                Assert.Equal(createdIdentity, (await Native("docker", ["image", "inspect", "--format", "{{.Created}}", imageId])).Output.Trim());
                Assert.Equal(owner, (await Native("docker", ["image", "inspect", "--format", "{{index .Config.Labels \"maliev.fixture.owner\"}}", imageId])).Output.Trim());
                ProcessResult removal = await Native("docker", ["image", "rm", imageId]);
                Assert.True(removal.ExitCode == 0, "Owned disposable image cleanup failed.");
                Assert.Equal("", (await Native("docker", ["image", "ls", "--quiet", "--no-trunc", "--filter", $"label=maliev.fixture.owner={owner}"])).Output.Trim());
            }
        }
    }

    private static async Task<ProcessResult> RunGate(string image, string repository,
        string dockerfile = "Legacy.Maliev.Intranet/Dockerfile")
    {
        YamlMappingNode gate = Assert.Single(PublisherSteps(), step => Scalar(step, "name") == "Verify packaged Intranet assets and source revision");
        return await Native(OperatingSystem.IsWindows() ? "python" : "python3", ["-B", "-"],
            Scalar(gate, "run"), new Dictionary<string, string>
            {
                ["BUILT_IMAGE"] = image,
                ["CALLER_REPOSITORY"] = repository,
                ["SOURCE_DOCKERFILE"] = dockerfile,
                ["SOURCE_REVISION"] = new string('a', 40),
                ["GITHUB_OUTPUT"] = OperatingSystem.IsWindows() ? "NUL" : "/dev/null",
            });
    }

    private static async Task<ProcessResult> Native(string executable, string[] arguments, string? input = null,
        IReadOnlyDictionary<string, string>? environment = null)
    {
        ProcessStartInfo start = new(executable)
        {
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            RedirectStandardInput = input is not null,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        foreach (string argument in arguments)
        {
            start.ArgumentList.Add(argument);
        }

        if (environment is not null)
        {
            foreach ((string key, string value) in environment)
            {
                start.Environment[key] = value;
            }
        }

        OwnedTestProcess.Result result = await OwnedTestProcess.RunAsync(start, input,
            cancellationToken: TestContext.Current.CancellationToken);
        return new ProcessResult(result.ExitCode, result.Output, result.Error);
    }

    private static YamlMappingNode[] PublisherSteps()
    {
        YamlStream yaml = [];
        yaml.Load(new StringReader(File.ReadAllText(Path.Combine(RepositoryContractTests.FindRepositoryRoot(), ".github/workflows/publish-image.yml"))));
        YamlMappingNode root = Assert.IsType<YamlMappingNode>(yaml.Documents.Single().RootNode);
        YamlMappingNode jobs = Assert.IsType<YamlMappingNode>(root.Children[new YamlScalarNode("jobs")]);
        YamlMappingNode publish = Assert.IsType<YamlMappingNode>(jobs.Children[new YamlScalarNode("publish")]);
        return Assert.IsType<YamlSequenceNode>(publish.Children[new YamlScalarNode("steps")]).Children.Select(Assert.IsType<YamlMappingNode>).ToArray();
    }

    private static string Scalar(YamlMappingNode mapping, string key) =>
        mapping.Children.TryGetValue(new YamlScalarNode(key), out YamlNode? value) ? ((YamlScalarNode)value).Value ?? "" : "";

    private sealed record ProcessResult(int ExitCode, string Output, string Error);
}

[CollectionDefinition("Packaged image acceptance", DisableParallelization = true)]
public sealed class PackagedImageAcceptanceCollection
{
}
