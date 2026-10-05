using System.Diagnostics;
using Xunit;

namespace Legacy.Maliev.Workflows.Tests;

public sealed class ValidationStepOrderTests
{
    [Fact]
    public async Task TrustedValidation_ExecutesOriginalBodiesInBuildFormatTestOrder()
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
        start.ArgumentList.Add(Path.Combine(root, "tests", "test_validation_step_order.py"));
        using Process process = Process.Start(start) ?? throw new InvalidOperationException("Validation order controls did not start.");
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
        Assert.Contains("Ran 4 tests", diagnostics, StringComparison.Ordinal);
        Assert.Contains("OK", diagnostics, StringComparison.Ordinal);
        Assert.DoesNotContain("skipped", diagnostics, StringComparison.Ordinal);
        Assert.Equal("", await output);
    }
}
