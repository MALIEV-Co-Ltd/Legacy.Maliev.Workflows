using System.Diagnostics;
using Xunit;

namespace Legacy.Maliev.Workflows.Tests;

public sealed class OfflineReleaseSourceTests
{
    [Fact]
    public async Task ActualGitSourceGuard_RejectsDirtyStaleRedirectedAndAmbiguousObservations()
    {
        string root = RepositoryContractTests.FindRepositoryRoot();
        ProcessStartInfo start = new(OperatingSystem.IsWindows() ? "python" : "python3")
        {
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        start.ArgumentList.Add("-B");
        start.ArgumentList.Add(Path.Combine(root, "tests", "test_offline_release_source.py"));
        using Process process = new() { StartInfo = start };
        using CancellationTokenSource budget = CancellationTokenSource.CreateLinkedTokenSource(TestContext.Current.CancellationToken);
        budget.CancelAfter(TimeSpan.FromSeconds(90));
        Assert.True(process.Start());
        try
        {
            Task<string> output = process.StandardOutput.ReadToEndAsync(budget.Token);
            Task<string> error = process.StandardError.ReadToEndAsync(budget.Token);
            await process.WaitForExitAsync(budget.Token);
            await Task.WhenAll(output, error).WaitAsync(TimeSpan.FromSeconds(10), TestContext.Current.CancellationToken);
            string diagnostics = await error;
            Assert.True(process.ExitCode == 0, diagnostics);
            Assert.Contains("Ran 29 tests", diagnostics);
            Assert.Contains("OK", diagnostics);
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
