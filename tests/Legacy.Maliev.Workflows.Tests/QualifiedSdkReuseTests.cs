using System.Diagnostics;
using Xunit;
using YamlDotNet.RepresentationModel;

namespace Legacy.Maliev.Workflows.Tests;

public sealed class QualifiedSdkReuseTests
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
    public void DefaultInstallerRemainsEnabled_AndOnlyQualifiedReuseSkipsInstaller()
    {
        YamlMappingNode inputs = (YamlMappingNode)Action().Children[new YamlScalarNode("inputs")];
        Assert.Equal("install", Scalar((YamlMappingNode)inputs.Children[new YamlScalarNode("dotnet-setup-mode")], "default"));
        YamlMappingNode[] steps = Steps();
        int guard = Array.FindIndex(steps, step => Scalar(step, "name") == "Qualify existing private .NET installation");
        int installer = Array.FindIndex(steps, step => Scalar(step, "name") == "Set up .NET");
        Assert.True(guard >= 0 && installer == guard + 1);
        Assert.Equal("${{ inputs.dotnet-setup-mode == 'install' }}", Scalar(steps[installer], "if"));
        Assert.False(steps[guard].Children.ContainsKey(new YamlScalarNode("continue-on-error")));
    }

    [Theory]
    [InlineData("install", "10.0.x", "", "10.0.402", "10.0.13", "10.0.13", false, false, 0)]
    [InlineData("qualified-existing", "10.0.402", "10.0.13", "10.0.402", "10.0.13", "10.0.13", false, false, 0)]
    [InlineData("unknown", "10.0.402", "10.0.13", "10.0.402", "10.0.13", "10.0.13", false, false, 2)]
    [InlineData("install", "10.0.402", "10.0.13", "10.0.402", "10.0.13", "10.0.13", false, false, 2)]
    [InlineData("qualified-existing", "10.0.x", "10.0.13", "10.0.402", "10.0.13", "10.0.13", false, false, 2)]
    [InlineData("qualified-existing", "10.0.402", "", "10.0.402", "10.0.13", "10.0.13", false, false, 2)]
    [InlineData("qualified-existing", "10.0.402", "10.0.13", "10.0.403", "10.0.13", "10.0.13", false, false, 1)]
    [InlineData("qualified-existing", "10.0.402", "10.0.13", "10.0.402", "10.0.14", "10.0.13", false, false, 1)]
    [InlineData("qualified-existing", "10.0.402", "10.0.13", "10.0.402", "10.0.13", "10.0.14", false, false, 1)]
    [InlineData("qualified-existing", "10.0.402", "10.0.13", "10.0.402", "10.0.13", "10.0.13", true, false, 1)]
    [InlineData("qualified-existing", "10.0.402", "10.0.13", "10.0.402", "10.0.13", "10.0.13", false, true, 1)]
    public async Task ActualGuard_RejectsUnqualifiedInstallationsBeforeValidation(
        string mode, string sdk, string runtime, string actualSdk, string core, string asp,
        bool extraRuntime, bool wrongExecutable, int expected)
    {
        string temporary = Path.Combine(Path.GetTempPath(), "qualified-sdk-" + Guid.NewGuid().ToString("N"));
        string installation = Path.Combine(temporary, "private");
        string other = Path.Combine(temporary, "other");
        Directory.CreateDirectory(installation);
        Directory.CreateDirectory(other);
        try
        {
            string stub = """
                #!/usr/bin/env bash
                case "$1" in
                  --version) printf '%s\n' "$ACTUAL_SDK" ;;
                  --list-runtimes)
                    printf 'Microsoft.NETCore.App %s [%s/shared/Microsoft.NETCore.App]\n' "$ACTUAL_CORE" "$DOTNET_ROOT"
                    printf 'Microsoft.AspNetCore.App %s [%s/shared/Microsoft.AspNetCore.App]\n' "$ACTUAL_ASP" "$DOTNET_ROOT"
                    if test "$EXTRA_RUNTIME" = true; then echo 'Microsoft.NETCore.App 10.0.14 [extra]'; fi
                    ;;
                  *) exit 3 ;;
                esac
                """ + "\n";
            string executable = Path.Combine(wrongExecutable ? other : installation, "dotnet");
            await File.WriteAllTextAsync(executable, stub, TestContext.Current.CancellationToken);
            ProcessStartInfo start = new(OperatingSystem.IsWindows() ? "C:/Program Files/Git/bin/bash.exe" : "bash");
            foreach (string argument in new[] { "--noprofile", "--norc", "-e", "-o", "pipefail", "-s" })
            {
                start.ArgumentList.Add(argument);
            }
            start.Environment["SDK_SETUP_MODE"] = mode;
            start.Environment["REQUESTED_SDK"] = sdk;
            start.Environment["REQUESTED_RUNTIME"] = runtime;
            start.Environment["ACTUAL_SDK"] = actualSdk;
            start.Environment["ACTUAL_CORE"] = core;
            start.Environment["ACTUAL_ASP"] = asp;
            start.Environment["EXTRA_RUNTIME"] = extraRuntime ? "true" : "false";
            start.Environment["TEST_INSTALLATION"] = installation;
            start.Environment["TEST_EXECUTABLE"] = executable;
            start.Environment["TEST_TEMP"] = temporary;
            string prefix = """
                export RUNNER_TEMP="$(realpath "$TEST_TEMP")"
                export DOTNET_ROOT="$(realpath "$TEST_INSTALLATION")"
                chmod +x "$TEST_EXECUTABLE"
                export PATH="$(dirname "$(realpath "$TEST_EXECUTABLE")"):$PATH"
                """ + "\n";
            string guard = Scalar(Steps().Single(step => Scalar(step, "name") == "Qualify existing private .NET installation"), "run");
            OwnedTestProcess.Result result = await OwnedTestProcess.RunAsync(start,
                input: prefix + guard, timeout: TimeSpan.FromSeconds(5), outputLimitCharacters: 16 * 1024,
                cancellationToken: TestContext.Current.CancellationToken);
            Assert.Equal(expected, result.ExitCode);
        }
        finally
        {
            Directory.Delete(temporary, recursive: true);
        }
    }
}
