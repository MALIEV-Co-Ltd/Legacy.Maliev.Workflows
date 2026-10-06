using YamlDotNet.RepresentationModel;
using Xunit;

namespace Legacy.Maliev.Workflows.Tests;

public sealed class AnalyticsWireWorkflowContractTests
{
    [Fact]
    public void AnalyticsJobWaitsForBothScannerProtectedValidationJobsAndHasFiniteLifetime()
    {
        YamlMappingNode job = ReadJob();
        Assert.Equal("ubuntu-latest", Scalar(job, "runs-on"));
        Assert.Equal("10", Scalar(job, "timeout-minutes"));
        YamlSequenceNode needs = Assert.IsType<YamlSequenceNode>(Node(job, "needs"));
        Assert.Equal(["validate", "scanner-caller-subdirectory"], needs.Children.Select(Assert.IsType<YamlScalarNode>).Select(node => node.Value));
        Assert.False(job.Children.ContainsKey(new YamlScalarNode("if")));
        Assert.False(job.Children.ContainsKey(new YamlScalarNode("continue-on-error")));
        YamlMappingNode permissions = Assert.IsType<YamlMappingNode>(Node(job, "permissions"));
        Assert.Equal("read", Scalar(permissions, "contents"));
        Assert.Single(permissions.Children);
        YamlMappingNode concurrency = Assert.IsType<YamlMappingNode>(Node(job, "concurrency"));
        Assert.Equal("true", Scalar(concurrency, "cancel-in-progress"));
        Assert.Contains("github.ref", Scalar(concurrency, "group"), StringComparison.Ordinal);
    }

    [Fact]
    public void CheckoutUsesExistingPinnedActionsAndNeverRequestsPrivateRepositoryCredentials()
    {
        YamlMappingNode[] steps = Steps();
        YamlMappingNode[] actions = steps.Where(step => step.Children.ContainsKey(new YamlScalarNode("uses"))).ToArray();
        Assert.Equal(2, actions.Length);
        Assert.Equal("actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1", Scalar(actions[0], "uses"));
        Assert.Equal("actions/setup-dotnet@a98b56852c35b8e3190ac28c8c2271da59106c68", Scalar(actions[1], "uses"));
        YamlMappingNode checkout = Assert.IsType<YamlMappingNode>(Node(actions[0], "with"));
        Assert.Equal("false", Scalar(checkout, "persist-credentials"));
        Assert.Single(checkout.Children);
        Assert.DoesNotContain(steps, step => step.Children.ContainsKey(new YamlScalarNode("continue-on-error")));
        Assert.DoesNotContain(steps, step => step.Children.ContainsKey(new YamlScalarNode("if")));
    }

    [Fact]
    public void ActualGeneratorBuildPrecedesVerifyAndTheCompleteAnalyticsSuite()
    {
        string[] commands = Steps().Where(step => step.Children.ContainsKey(new YamlScalarNode("run")))
            .Select(step => Scalar(step, "run")).ToArray();
        Assert.Equal(3, commands.Length);
        Assert.StartsWith("dotnet build tools/analytics/WireFixtures/WireFixtures.csproj ", commands[0], StringComparison.Ordinal);
        Assert.Contains("--configuration Release", commands[0], StringComparison.Ordinal);
        Assert.Contains("--disable-build-servers", commands[0], StringComparison.Ordinal);
        Assert.Contains("-m:1", commands[0], StringComparison.Ordinal);
        Assert.StartsWith("dotnet run --no-build --no-restore ", commands[1], StringComparison.Ordinal);
        Assert.Contains("-- --verify tools/analytics/fixtures", commands[1], StringComparison.Ordinal);
        Assert.DoesNotContain("--write", commands[1], StringComparison.Ordinal);
        Assert.Equal("python3 -B -W error -m unittest discover -s tools/analytics/tests -p 'test_*.py' -v", commands[2]);
    }

    [Fact]
    public void HostedSyntheticGateNeverInventsAProducerApprovalOrChangesPayloads()
    {
        foreach (string command in Steps().Where(step => step.Children.ContainsKey(new YamlScalarNode("run")))
                     .Select(step => Scalar(step, "run")))
        {
            Assert.DoesNotContain("--approval", command, StringComparison.Ordinal);
            Assert.DoesNotContain("--write", command, StringComparison.Ordinal);
            Assert.DoesNotContain("curl", command, StringComparison.Ordinal);
            Assert.DoesNotContain("gh api", command, StringComparison.Ordinal);
        }
        YamlMappingNode env = Assert.IsType<YamlMappingNode>(Node(ReadJob(), "env"));
        Assert.Equal("1", Scalar(env, "DOTNET_CLI_DO_NOT_USE_MSBUILD_SERVER"));
        Assert.Equal("1", Scalar(env, "MSBUILDDISABLENODEREUSE"));
        Assert.Equal("1", Scalar(env, "PYTHONDONTWRITEBYTECODE"));
    }

    private static YamlMappingNode ReadJob()
    {
        string root = RepositoryContractTests.FindRepositoryRoot();
        YamlStream yaml = new();
        using StringReader reader = new(File.ReadAllText(Path.Combine(root, ".github/workflows/validate.yml")));
        yaml.Load(reader);
        YamlMappingNode workflow = Assert.IsType<YamlMappingNode>(yaml.Documents.Single().RootNode);
        YamlMappingNode jobs = Assert.IsType<YamlMappingNode>(Node(workflow, "jobs"));
        return Assert.IsType<YamlMappingNode>(Node(jobs, "analytics-wire"));
    }

    private static YamlMappingNode[] Steps() => Assert.IsType<YamlSequenceNode>(Node(ReadJob(), "steps"))
        .Children.Select(Assert.IsType<YamlMappingNode>).ToArray();

    private static YamlNode Node(YamlMappingNode mapping, string key) => mapping.Children[new YamlScalarNode(key)];

    private static string Scalar(YamlMappingNode mapping, string key) => Assert.IsType<YamlScalarNode>(Node(mapping, key)).Value!;
}
