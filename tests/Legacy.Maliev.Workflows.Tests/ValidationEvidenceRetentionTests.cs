using System.Diagnostics;
using Xunit;
using YamlDotNet.RepresentationModel;

namespace Legacy.Maliev.Workflows.Tests;

public sealed class ValidationEvidenceRetentionTests
{
    [Fact]
    public void CompositeAction_UsesExplicitInputsAndPreservesPartialEvidenceWithoutWeakeningPreparation()
    {
        string path = Path.Combine(RepositoryContractTests.FindRepositoryRoot(), "actions", "preserve-validation-evidence", "action.yml");
        YamlStream yaml = [];
        yaml.Load(new StringReader(File.ReadAllText(path)));
        var root = Assert.IsType<YamlMappingNode>(yaml.Documents.Single().RootNode);
        var inputs = Assert.IsType<YamlMappingNode>(root.Children[new YamlScalarNode("inputs")]);
        Assert.Equal(new[] { "production-projects", "results-directory" }, inputs.Children.Keys.Select(key => ((YamlScalarNode)key).Value).Order());
        foreach (var value in inputs.Children.Values)
        {
            Assert.Equal("true", ((YamlScalarNode)((YamlMappingNode)value).Children[new YamlScalarNode("required")]).Value);
        }

        var runs = Assert.IsType<YamlMappingNode>(root.Children[new YamlScalarNode("runs")]);
        Assert.Equal("composite", ((YamlScalarNode)runs.Children[new YamlScalarNode("using")]).Value);
        var steps = Assert.IsType<YamlSequenceNode>(runs.Children[new YamlScalarNode("steps")]);
        Assert.Equal(2, steps.Children.Count);
        var prepare = Assert.IsType<YamlMappingNode>(steps.Children[0]);
        Assert.False(prepare.Children.ContainsKey(new YamlScalarNode("continue-on-error")));
        var upload = Assert.IsType<YamlMappingNode>(steps.Children[1]);
        Assert.Equal("always() && steps.prepare.outputs.artifact-path != ''", ((YamlScalarNode)upload.Children[new YamlScalarNode("if")]).Value);
        Assert.Equal("actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02", ((YamlScalarNode)upload.Children[new YamlScalarNode("uses")]).Value);
        var options = Assert.IsType<YamlMappingNode>(upload.Children[new YamlScalarNode("with")]);
        Assert.Equal("error", ((YamlScalarNode)options.Children[new YamlScalarNode("if-no-files-found")]).Value);
        Assert.Equal("false", ((YamlScalarNode)options.Children[new YamlScalarNode("include-hidden-files")]).Value);
        Assert.Equal("${{ steps.prepare.outputs.artifact-path }}", ((YamlScalarNode)options.Children[new YamlScalarNode("path")]).Value);
    }

    [Theory]
    [InlineData("test_preserve_validation_evidence.py", 15)]
    [InlineData("test_trx_roster_identity.py", 17)]
    public async Task ActualEvidenceProducer_EnforcesPathsPrivacyAvailabilityAndByteRetention(string controls, int expectedTests)
    {
        string root = RepositoryContractTests.FindRepositoryRoot();
        ProcessStartInfo start = new(OperatingSystem.IsWindows() ? "python" : "python3")
        {
            WorkingDirectory = root,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        };
        start.Environment["PYTHON"] = start.FileName;
        start.ArgumentList.Add("-B");
        start.ArgumentList.Add(Path.Combine(root, "tests", controls));
        using Process process = Process.Start(start) ?? throw new InvalidOperationException("Retention controls did not start.");
        Task<string> output = process.StandardOutput.ReadToEndAsync(TestContext.Current.CancellationToken);
        Task<string> error = process.StandardError.ReadToEndAsync(TestContext.Current.CancellationToken);
        using CancellationTokenSource budget = CancellationTokenSource.CreateLinkedTokenSource(TestContext.Current.CancellationToken);
        budget.CancelAfter(TimeSpan.FromSeconds(60));
        try
        {
            await process.WaitForExitAsync(budget.Token);
        }
        catch (OperationCanceledException)
        {
            process.Kill(entireProcessTree: true);
            throw;
        }

        string diagnostics = await error;
        Assert.Equal(0, process.ExitCode);
        Assert.Contains($"Ran {expectedTests} tests", diagnostics, StringComparison.Ordinal);
        Assert.Contains("OK", diagnostics, StringComparison.Ordinal);
        Assert.DoesNotContain("skipped", diagnostics, StringComparison.Ordinal);
        Assert.Equal("", await output);
    }
}
