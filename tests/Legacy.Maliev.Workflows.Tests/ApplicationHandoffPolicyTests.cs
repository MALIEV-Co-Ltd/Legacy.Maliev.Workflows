using System.Diagnostics;
using Xunit;

namespace Legacy.Maliev.Workflows.Tests;

public sealed class ApplicationHandoffPolicyTests
{
    [Fact]
    public async Task ControlledPythonSuite_VerifiesOrderingOwnershipCapacityAndRollback()
    {
        string script = Path.Combine(RepositoryContractTests.FindRepositoryRoot(), "tests", "test_application_handoff_policy.py");
        ProcessStartInfo start = new(OperatingSystem.IsWindows() ? "python" : "python3")
        {
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        start.ArgumentList.Add("-B");
        start.ArgumentList.Add(script);
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
            Assert.Contains("Ran 29 tests", await error);
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
