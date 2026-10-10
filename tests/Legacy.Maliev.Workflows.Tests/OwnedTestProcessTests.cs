using System.Diagnostics;
using Xunit;

namespace Legacy.Maliev.Workflows.Tests;

public sealed class OwnedTestProcessTests
{
    [Theory]
    [InlineData("pressure", "pressure-complete\n", false)]
    [InlineData("stdout-pressure", "stdout-complete\n", true)]
    public async Task PipePressure_DrainsBothStreamsBeforeWaitingForExit(string mode, string marker, bool stdoutPressure)
    {
        List<OwnedTestProcess.Observation> observations = [];
        OwnedTestProcess.Result result = await OwnedTestProcess.RunAsync(Start(mode),
            timeout: TimeSpan.FromSeconds(10), cancellationToken: TestContext.Current.CancellationToken,
            observe: observations.Add);
        Assert.Equal(0, result.ExitCode);
        Assert.Equal(marker, stdoutPressure ? result.Error : result.Output);
        Assert.Equal(2 * 1024 * 1024, (stdoutPressure ? result.Output : result.Error).Length);
        AssertSettled(observations);
    }

    [Fact]
    public async Task StdinBackpressure_DrainsStderrWhileWritingInputLargerThanThePipe()
    {
        List<OwnedTestProcess.Observation> observations = [];
        string input = new('i', 3 * 1024 * 1024);
        OwnedTestProcess.Result result = await OwnedTestProcess.RunAsync(Start("stdin-pressure"), input,
            timeout: TimeSpan.FromSeconds(10), cancellationToken: TestContext.Current.CancellationToken,
            observe: observations.Add);
        Assert.Equal(0, result.ExitCode);
        Assert.Equal($"stdin-count:{input.Length}\nstdin-complete\n", result.Output);
        Assert.Equal(2 * 1024 * 1024, result.Error.Length);
        AssertSettled(observations);
    }

    [Fact]
    public async Task ObserverFailureBeforeTasks_PreservesTheSameFailureAndSettlesTheChild()
    {
        IOException original = new("observer-start-failure");
        List<OwnedTestProcess.Observation> observations = [];
        IOException actual = await Assert.ThrowsAsync<IOException>(() => OwnedTestProcess.RunAsync(Start("sleep"),
            cancellationToken: TestContext.Current.CancellationToken,
            observe: observation =>
            {
                observations.Add(observation);
                if (!observation.Terminal)
                {
                    throw original;
                }
            }));
        Assert.Same(original, actual);
        AssertSettled(observations);
    }

    [Fact]
    public async Task Timeout_SettlesTheRetainedDirectChild()
    {
        List<OwnedTestProcess.Observation> observations = [];
        await Assert.ThrowsAnyAsync<OperationCanceledException>(() => OwnedTestProcess.RunAsync(Start("sleep"),
            timeout: TimeSpan.FromMilliseconds(200), cancellationToken: TestContext.Current.CancellationToken,
            observe: observations.Add));
        AssertSettled(observations);
    }

    [Fact]
    public async Task Cancellation_SettlesBeforeReturningTheOriginalCancellation()
    {
        using CancellationTokenSource cancellation = CancellationTokenSource.CreateLinkedTokenSource(TestContext.Current.CancellationToken);
        List<OwnedTestProcess.Observation> observations = [];
        await Assert.ThrowsAnyAsync<OperationCanceledException>(() => OwnedTestProcess.RunAsync(Start("sleep"),
            cancellationToken: cancellation.Token, observe: observation =>
            {
                observations.Add(observation);
                if (!observation.Terminal)
                {
                    cancellation.Cancel();
                }
            }));
        AssertSettled(observations);
    }

    [Fact]
    public async Task OutputLimit_PreservesFirstFailureWhenTerminationAlsoThrows()
    {
        List<OwnedTestProcess.Observation> observations = [];
        InvalidDataException failure = await Assert.ThrowsAsync<InvalidDataException>(() => OwnedTestProcess.RunAsync(
            Start("pressure"), outputLimitCharacters: 32768, cancellationToken: TestContext.Current.CancellationToken,
            observe: observations.Add,
            terminate: process =>
            {
                process.Kill(); // Same retained direct-child handle, never a process tree.
                throw new IOException("termination-witness");
            }));
        Assert.IsType<IOException>(failure.Data["OwnedChildCleanupFailure"]);
        AssertSettled(observations);
    }

    [Fact]
    public async Task NonzeroExit_ReturnsActualOutputWithoutFabricatingSuccess()
    {
        List<OwnedTestProcess.Observation> observations = [];
        OwnedTestProcess.Result result = await OwnedTestProcess.RunAsync(Start("exit"),
            cancellationToken: TestContext.Current.CancellationToken, observe: observations.Add);
        Assert.Equal(17, result.ExitCode);
        Assert.Equal("fixture-rejected\n", result.Error);
        AssertSettled(observations);
    }

    [Fact]
    public async Task AlreadyCancelled_DoesNotStartAChild()
    {
        using CancellationTokenSource cancellation = CancellationTokenSource.CreateLinkedTokenSource(TestContext.Current.CancellationToken);
        cancellation.Cancel();
        List<OwnedTestProcess.Observation> observations = [];
        await Assert.ThrowsAnyAsync<OperationCanceledException>(() => OwnedTestProcess.RunAsync(Start("sleep"),
            cancellationToken: cancellation.Token, observe: observations.Add));
        Assert.Empty(observations);
    }

    private static ProcessStartInfo Start(string mode)
    {
        ProcessStartInfo start = new(OperatingSystem.IsWindows() ? "python" : "python3");
        start.ArgumentList.Add("-B");
        start.ArgumentList.Add(Path.Combine(RepositoryContractTests.FindRepositoryRoot(),
            "tests", "fixtures", "owned-process", "pipe-pressure.py"));
        start.ArgumentList.Add(mode);
        return start;
    }

    private static void AssertSettled(List<OwnedTestProcess.Observation> observations)
    {
        OwnedTestProcess.Observation started = Assert.Single(observations, observation => !observation.Terminal);
        OwnedTestProcess.Observation ended = Assert.Single(observations, observation => observation.Terminal);
        Assert.Equal(started.Id, ended.Id);
        Assert.Equal(started.Pid, ended.Pid);
        Assert.Equal(started.StartTimeUtc, ended.StartTimeUtc);
        Assert.True(ended.CleanupVerified);
        Assert.Equal(0, OwnedTestProcess.UnsettledCount);
    }
}
