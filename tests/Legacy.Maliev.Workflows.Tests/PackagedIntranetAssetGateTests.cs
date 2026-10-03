using System.Diagnostics;
using System.Text.Json;
using YamlDotNet.RepresentationModel;
using Xunit;

namespace Legacy.Maliev.Workflows.Tests;

[Collection("Packaged image acceptance")]
public sealed class PackagedIntranetAssetGateTests
{
    // Independent expected corpus from source ac62eab210926ade460f8a04129953579968de2b.
    // Removing any asset check must let a deliberately broken real image through.
    private static readonly string[] Assets =
    [
        "vendor.min.css.gz", "app.min.css.gz", "vendor.min.js.gz", "app.min.js.gz",
        "jquery.min.js.gz", "jquery.validate.min.js.gz", "jquery.validate.unobtrusive.min.js.gz",
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
            Assert.Equal("accepted", receipt.RootElement.GetProperty("status").GetString());
            Assert.Equal(7, receipt.RootElement.GetProperty("assetCount").GetInt32());
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
        ProcessResult result = await RunGate("sha256:" + new string('0', 64), "MALIEV-Co-Ltd/Legacy.Maliev.Intranet",
            "Legacy.Maliev.Intranet.Bff/Dockerfile");
        Assert.Equal(0, result.ExitCode);
        using JsonDocument receipt = JsonDocument.Parse(result.Output);
        Assert.Equal("not-applicable", receipt.RootElement.GetProperty("status").GetString());
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
        int gate = Array.FindIndex(steps, step => Scalar(step, "name") == "Verify packaged Intranet assets");
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

    private static async Task WithImage(string? brokenAsset, bool empty, Func<string, Task> acceptance)
    {
        // Observe the missing pipeline behavior before allocating a disposable Docker fixture.
        Assert.Single(PublisherSteps(), step => Scalar(step, "name") == "Verify packaged Intranet assets");
        string directory = Path.Combine(Path.GetTempPath(), "workflows-packaged-assets-" + Guid.NewGuid().ToString("N"));
        string image = "legacy-workflows-asset-test:" + Guid.NewGuid().ToString("N");
        bool built = false;
        Directory.CreateDirectory(Path.Combine(directory, "assets"));
        try
        {
            foreach (string asset in Assets)
            {
                if (asset == brokenAsset && !empty)
                {
                    continue;
                }

                await File.WriteAllBytesAsync(Path.Combine(directory, "assets", asset),
                    asset == brokenAsset ? [] : [0x1f, 0x8b, 0x01], TestContext.Current.CancellationToken);
            }

            // No base-image pull, registry, credentials, network, executable or application startup.
            await File.WriteAllTextAsync(Path.Combine(directory, "Dockerfile"),
                "FROM scratch\nCOPY assets /app/wwwroot/dist/\nENTRYPOINT [\"/application-must-not-start\"]\n",
                TestContext.Current.CancellationToken);
            ProcessResult build = await Native("docker", ["build", "--network", "none", "--quiet", "--tag", image, directory]);
            Assert.True(build.ExitCode == 0, $"Disposable scratch-image build failed: {build.Error}");
            built = true;
            await acceptance(image);
        }
        finally
        {
            Directory.Delete(directory, recursive: true);
            if (built)
            {
                ProcessResult removal = await Native("docker", ["image", "rm", "--force", image]);
                Assert.True(removal.ExitCode == 0, "Owned disposable image cleanup failed.");
            }
        }
    }

    private static async Task<ProcessResult> RunGate(string image, string repository,
        string dockerfile = "Legacy.Maliev.Intranet/Dockerfile")
    {
        YamlMappingNode gate = Assert.Single(PublisherSteps(), step => Scalar(step, "name") == "Verify packaged Intranet assets");
        return await Native(OperatingSystem.IsWindows() ? "python" : "python3", ["-B", "-"],
            Scalar(gate, "run"), new Dictionary<string, string>
            {
                ["BUILT_IMAGE"] = image,
                ["CALLER_REPOSITORY"] = repository,
                ["SOURCE_DOCKERFILE"] = dockerfile,
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

        using Process process = Process.Start(start) ?? throw new InvalidOperationException("Fixture process did not start.");
        Task<string> output = process.StandardOutput.ReadToEndAsync(TestContext.Current.CancellationToken);
        Task<string> error = process.StandardError.ReadToEndAsync(TestContext.Current.CancellationToken);
        if (input is not null)
        {
            await process.StandardInput.WriteAsync(input);
            process.StandardInput.Close();
        }

        await process.WaitForExitAsync(TestContext.Current.CancellationToken);
        return new ProcessResult(process.ExitCode, await output, await error);
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
