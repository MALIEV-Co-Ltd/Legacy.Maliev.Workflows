using System.Text.RegularExpressions;
using Xunit;
using YamlDotNet.RepresentationModel;

namespace Legacy.Maliev.Workflows.Tests;

public sealed class NormalValidationCustodyContractTests
{
    [Fact]
    public void OptIn_WhenParsed_PreservesDefaultActionAndCurrentPhaseOrder()
    {
        string root = RepositoryContractTests.FindRepositoryRoot();
        string source = File.ReadAllText(Path.Combine(root, "actions/dotnet-validate/action.yml"));
        YamlStream yaml = new();
        yaml.Load(new StringReader(source));
        YamlMappingNode action = Assert.IsType<YamlMappingNode>(yaml.Documents[0].RootNode);
        YamlMappingNode inputs = Assert.IsType<YamlMappingNode>(action.Children[new YamlScalarNode("inputs")]);
        YamlMappingNode mode = Assert.IsType<YamlMappingNode>(inputs.Children[new YamlScalarNode("normal-custody-mode")]);
        Assert.Equal("disabled", ((YamlScalarNode)mode.Children[new YamlScalarNode("default")]).Value);
        string[] commands = Regex.Matches(source, @"(?m)^        (dotnet [^\r\n]+)$")
            .Select(match => match.Groups[1].Value).ToArray();
        Assert.Equal(5, commands.Length);
        Assert.Equal(new[] { "restore", "build", "format", "test", "list" },
            commands.Select(command => command.Split(' ')[1]).ToArray());
        Assert.DoesNotContain(commands, command => command.Contains("--filter", StringComparison.Ordinal));
        Assert.Contains("NORMAL_CUSTODY_ACTION_REF: ${{ github.action_ref }}", source, StringComparison.Ordinal);
        Assert.Contains("NORMAL_CUSTODY_ACTION_REPOSITORY: ${{ github.action_repository }}", source, StringComparison.Ordinal);
        Assert.Contains("authenticate(os.environ, absolute_deadline=", source, StringComparison.Ordinal);
        Assert.True(source.IndexOf("authenticate(os.environ, absolute_deadline=", StringComparison.Ordinal)
            < source.LastIndexOf("load_authenticated_modules(package).main()", StringComparison.Ordinal));
    }

    [Fact]
    public void UnreleasedLifecycle_WhenAuthored_CannotLaunchOrClaimPass()
    {
        string root = RepositoryContractTests.FindRepositoryRoot();
        string helper = File.ReadAllText(Path.Combine(root, "scripts/normal_validation_custody.py"));
        Assert.Contains("RELEASED_LIFECYCLE = False", helper, StringComparison.Ordinal);
        Assert.Contains("Actual producer source review and kernel qualification unavailable", helper, StringComparison.Ordinal);
        Assert.Contains("original_deadline-RESERVE", helper, StringComparison.Ordinal);
        Assert.Contains("/usr/bin/python3 -I -S -B", File.ReadAllText(Path.Combine(root,
            "actions/dotnet-validate/action.yml")), StringComparison.Ordinal);
    }
}