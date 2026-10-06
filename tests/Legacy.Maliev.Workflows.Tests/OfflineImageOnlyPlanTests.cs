using System.Diagnostics;
using Xunit;

namespace Legacy.Maliev.Workflows.Tests;

public sealed class OfflineImageOnlyPlanTests
{
    [Fact]
    public async Task OfflinePlan_AdmitsOptionalProbeShapesAndPreservesSingletonMetadata()
    {
        await RunScenarios("OfflineImageMetadataScenarios.ps1", "offline-image-metadata-controls:35 passed");
    }

    [Fact]
    public async Task OfflinePlan_PreservesOtherFieldsAndRejectsForeignIdentityAndProvenance()
    {
        await RunScenarios("OfflineImageOnlyPlanScenarios.ps1", "offline-image-only-controls:25 passed");
    }

    private static async Task RunScenarios(string script, string expected)
    {
        string root = RepositoryContractTests.FindRepositoryRoot();
        ProcessStartInfo start = new("pwsh")
        {
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        start.ArgumentList.Add("-NoProfile");
        start.ArgumentList.Add("-File");
        start.ArgumentList.Add(Path.Combine(root, "tests", script));
        start.ArgumentList.Add("-RepositoryRoot");
        start.ArgumentList.Add(root);
        using Process process = new() { StartInfo = start };
        using CancellationTokenSource budget = CancellationTokenSource.CreateLinkedTokenSource(TestContext.Current.CancellationToken);
        budget.CancelAfter(TimeSpan.FromSeconds(30));
        Assert.True(process.Start());
        try
        {
            Task<string> output = process.StandardOutput.ReadToEndAsync(budget.Token);
            Task<string> error = process.StandardError.ReadToEndAsync(budget.Token);
            await process.WaitForExitAsync(budget.Token);
            await Task.WhenAll(output, error).WaitAsync(TimeSpan.FromSeconds(10), TestContext.Current.CancellationToken);
            Assert.True(process.ExitCode == 0, await error);
            Assert.Contains(expected, await output);
        }
        finally
        {
            if (!process.HasExited)
            {
                process.Kill(entireProcessTree: true);
                using CancellationTokenSource termination = new(TimeSpan.FromSeconds(10));
                await process.WaitForExitAsync(termination.Token);
            }
        }
    }
}
