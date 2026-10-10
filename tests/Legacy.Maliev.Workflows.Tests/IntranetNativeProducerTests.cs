using System.Diagnostics;
using Xunit;

namespace Legacy.Maliev.Workflows.Tests;

public sealed class IntranetNativeProducerTests
{
    [Theory]
    [InlineData("test_intranet_native_handoff.py", 10)]
    [InlineData("test_intranet_deployment_binding.py", 6)]
    public async Task RepoBoundSourceControls_ConsumePinnedPolicyAndOwnedNativeState(string script, int expectedTests)
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
}
