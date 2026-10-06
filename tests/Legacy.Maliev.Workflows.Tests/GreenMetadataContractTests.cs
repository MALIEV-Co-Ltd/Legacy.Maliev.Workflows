using System.Diagnostics;
using System.Text;
using Xunit;

namespace Legacy.Maliev.Workflows.Tests;

public sealed class GreenMetadataContractTests
{
    private const int OutputCharacterLimit = 65536;

    [Fact]
    public async Task GreenMetadataContracts_AdmitSelectedShapesAndRejectForeignReadbacks()
    {
        string root = RepositoryContractTests.FindRepositoryRoot();
        ProcessStartInfo start = new("python")
        {
            WorkingDirectory = root,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
        };
        foreach (string argument in new[] { "-B", "-W", "error", "-m", "unittest", "discover", "-s", Path.Combine(root, "tests"), "-p", "test_green*.py", "-v" })
        {
            start.ArgumentList.Add(argument);
        }

        start.Environment["PYTHONDONTWRITEBYTECODE"] = "1";
        using Process process = Process.Start(start) ?? throw new InvalidOperationException("Green metadata contract worker did not start.");
        using CancellationTokenSource deadline = CancellationTokenSource.CreateLinkedTokenSource(TestContext.Current.CancellationToken);
        deadline.CancelAfter(TimeSpan.FromSeconds(30));
        Task<string> output = ReadBoundedAsync(process.StandardOutput, deadline.Token);
        Task<string> error = ReadBoundedAsync(process.StandardError, deadline.Token);
        try
        {
            await process.WaitForExitAsync(deadline.Token);
            string[] messages = await Task.WhenAll(output, error);
            Assert.True(process.ExitCode == 0, string.Concat(messages));
        }
        finally
        {
            if (!process.HasExited)
            {
                // Retained exact child handle only; this worker starts no children.
                process.Kill();
                if (!process.WaitForExit(5000))
                {
                    throw new TimeoutException("Contract worker cleanup exceeded its expiry.");
                }
            }
        }
    }

    [Fact]
    public async Task ContractWorkerOutput_WhenAboveLimit_IsDrainedAndRejected()
    {
        using StringReader reader = new(new string('x', OutputCharacterLimit + 1));
        InvalidOperationException failure = await Assert.ThrowsAsync<InvalidOperationException>(() => ReadBoundedAsync(reader, CancellationToken.None));
        Assert.Equal("Contract worker output exceeded its bound.", failure.Message);
        Assert.Equal(-1, reader.Read());
    }

    private static async Task<string> ReadBoundedAsync(TextReader reader, CancellationToken cancellationToken)
    {
        char[] buffer = new char[1024];
        StringBuilder retained = new();
        bool overflow = false;
        int count;
        while ((count = await reader.ReadAsync(buffer.AsMemory(), cancellationToken)) != 0)
        {
            int available = OutputCharacterLimit - retained.Length;
            retained.Append(buffer, 0, Math.Min(count, available));
            overflow |= count > available;
        }

        if (overflow)
        {
            throw new InvalidOperationException("Contract worker output exceeded its bound.");
        }

        return retained.ToString();
    }
}
