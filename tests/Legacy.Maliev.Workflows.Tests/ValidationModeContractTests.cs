using System.Diagnostics;
using Xunit;
using YamlDotNet.RepresentationModel;

namespace Legacy.Maliev.Workflows.Tests;

public sealed class ValidationModeContractTests
{
    private static YamlMappingNode Action()
    {
        YamlStream yaml = new();
        yaml.Load(new StringReader(File.ReadAllText(Path.Combine(
            RepositoryContractTests.FindRepositoryRoot(), "actions/dotnet-validate/action.yml"))));
        return (YamlMappingNode)yaml.Documents.Single().RootNode;
    }

    private static string Scalar(YamlMappingNode node, string key) =>
        ((YamlScalarNode)node.Children[new YamlScalarNode(key)]).Value ?? string.Empty;

    private static YamlMappingNode[] Steps() =>
        ((YamlSequenceNode)((YamlMappingNode)Action().Children[new YamlScalarNode("runs")])
            .Children[new YamlScalarNode("steps")]).Children.Cast<YamlMappingNode>().ToArray();

    [Fact]
    public void DefaultFull_AndPhaseSpecificGuards_PreserveRequiredFullValidation()
    {
        YamlMappingNode inputs = (YamlMappingNode)Action().Children[new YamlScalarNode("inputs")];
        Assert.Equal("full", Scalar((YamlMappingNode)inputs.Children[new YamlScalarNode("validation-mode")], "default"));
        YamlMappingNode[] steps = Steps();
        Assert.Equal("Validate validation mode before helpers", Scalar(steps[0], "name"));
        foreach (string name in new[] { "Restore", "Build", "Test", "Audit vulnerable packages" })
        {
            Assert.Equal("${{ inputs.normal-custody-mode == 'disabled' && inputs.validation-mode == 'full' }}",
                Scalar(steps.Single(step => Scalar(step, "name") == name), "if"));
        }
        Assert.Equal("${{ inputs.normal-custody-mode == 'disabled' }}",
            Scalar(steps.Single(step => Scalar(step, "name") == "Verify formatting"), "if"));
        Assert.Equal("${{ inputs.normal-custody-mode == 'notification-n62-v1' }}",
            Scalar(steps.Single(step => Scalar(step, "name") == "Run owned Notification normal validation with original job custody"), "if"));
        foreach (string name in new[] { "Scan repository for leaked secrets", "Scan JWT signing resources", "Scan tracked current-tree credentials" })
        {
            YamlMappingNode scanner = steps.Single(step => Scalar(step, "name") == name);
            Assert.False(scanner.Children.ContainsKey(new YamlScalarNode("if")));
            Assert.False(scanner.Children.ContainsKey(new YamlScalarNode("continue-on-error")));
        }
    }

    [Theory]
    [InlineData("full", "disabled", "", 0)]
    [InlineData("full", "notification-n62-v1", "request", 0)]
    [InlineData("format-only", "disabled", "", 0)]
    [InlineData("format-only", "disabled", "request", 2)]
    [InlineData("format-only", "notification-n62-v1", "", 2)]
    [InlineData("format-only", "notification-n62-v1", "request", 2)]
    [InlineData("format-only", "unknown", "", 2)]
    [InlineData("", "disabled", "", 2)]
    [InlineData("FULL", "disabled", "", 2)]
    [InlineData("format", "disabled", "", 2)]
    [InlineData("format-only ", "disabled", "", 2)]
    [InlineData("unknown", "disabled", "", 2)]
    public async Task ActualModeGuard_RejectsUnknownModesAndCustodyCombinationsBeforeHelpers(
        string mode, string custody, string request, int expected)
    {
        ProcessStartInfo start = new(OperatingSystem.IsWindows() ? "C:/Program Files/Git/bin/bash.exe" : "bash");
        foreach (string argument in new[] { "--noprofile", "--norc", "-e", "-o", "pipefail", "-s" })
        {
            start.ArgumentList.Add(argument);
        }
        start.Environment["VALIDATION_MODE"] = mode;
        start.Environment["NORMAL_CUSTODY_MODE"] = custody;
        start.Environment["NORMAL_CUSTODY_REQUEST"] = request;
        OwnedTestProcess.Result result = await OwnedTestProcess.RunAsync(start,
            input: Scalar(Steps()[0], "run"), timeout: TimeSpan.FromSeconds(5),
            outputLimitCharacters: 16 * 1024, cancellationToken: TestContext.Current.CancellationToken);
        Assert.Equal(expected, result.ExitCode);
        Assert.Equal(string.Empty, result.Output);
        if (expected == 0)
        {
            Assert.Equal(string.Empty, result.Error);
        }
        else
        {
            Assert.NotEmpty(result.Error);
        }
    }
}