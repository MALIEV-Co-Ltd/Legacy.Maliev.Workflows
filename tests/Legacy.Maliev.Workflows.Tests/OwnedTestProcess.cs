using System.Collections.Concurrent;
using System.ComponentModel;
using System.Diagnostics;
using System.Runtime.ExceptionServices;
using System.Text;
using System.Text.Json;

namespace Legacy.Maliev.Workflows.Tests;

/// <summary>Finite direct-child custody for test fixtures, not Linux descendant attestation.</summary>
internal static class OwnedTestProcess
{
    private static readonly ConcurrentDictionary<Guid, UnsettledChild> Unsettled = new();
    internal static int UnsettledCount => Unsettled.Count;
    internal sealed record Result(int ExitCode, string Output, string Error);
    internal sealed record Observation(Guid Id, int Pid, DateTime? StartTimeUtc,
        string RequestedExecutable, string? ActualExecutable, bool Terminal, bool CleanupVerified)
    {
        public int OwningProcessId { get; init; } = Environment.ProcessId;
        public DateTime ExpiresUtc { get; init; }
        public string JournalPath { get; init; } = string.Empty;
    }
    private sealed record UnsettledChild(Process Process, Task[] Tasks, Observation Identity);

    internal static async Task<Result> RunAsync(ProcessStartInfo start, string? input = null,
        TimeSpan? timeout = null, int outputLimitCharacters = 4 * 1024 * 1024,
        CancellationToken cancellationToken = default, Action<Observation>? observe = null,
        Action<Process>? terminate = null)
    {
        TimeSpan runtime = timeout ?? TimeSpan.FromSeconds(30);
        if (runtime <= TimeSpan.Zero || runtime > TimeSpan.FromSeconds(30)
            || outputLimitCharacters <= 0 || outputLimitCharacters > 4 * 1024 * 1024)
        {
            throw new ArgumentOutOfRangeException(nameof(timeout), "Finite fixture limits required.");
        }

        cancellationToken.ThrowIfCancellationRequested();
        start.RedirectStandardInput = true;
        start.RedirectStandardOutput = true;
        start.RedirectStandardError = true;
        start.UseShellExecute = false;
        start.CreateNoWindow = true;
        using CancellationTokenSource budget = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        budget.CancelAfter(runtime);
        Process process = new() { StartInfo = start };
        Observation? identity = null;
        ExceptionDispatchInfo? firstFailure = null;
        Exception? cleanupFailure = null;
        Task[] tasks = [];
        Task<string>? output = null;
        Task<string>? error = null;
        int captured = 0;
        int exitCode = -1;
        bool started = false;
        bool settled = false;
        Guid resourceId = Guid.NewGuid();
        string journal = Path.Combine(Path.GetTempPath(), $"workflows-owned-test-child-{resourceId:N}.jsonl");

        void Record(Observation observation, bool create)
        {
            // Metadata only, no argv, stdin, output, credentials or customer data.
            using FileStream stream = new(journal, create ? FileMode.CreateNew : FileMode.Append,
                FileAccess.Write, FileShare.Read, 4096, FileOptions.WriteThrough);
            byte[] bytes = Encoding.UTF8.GetBytes(JsonSerializer.Serialize(observation) + "\n");
            stream.Write(bytes);
            stream.Flush(flushToDisk: true);
        }

        void Fail(Exception failure)
        {
            Interlocked.CompareExchange(ref firstFailure, ExceptionDispatchInfo.Capture(failure), null);
            budget.Cancel();
        }

        async Task<T> Track<T>(Func<Task<T>> action)
        {
            try
            {
                return await action().ConfigureAwait(false);
            }
            catch (Exception failure)
            {
                Fail(failure);
                throw;
            }
        }

        async Task<string> Drain(StreamReader reader)
        {
            char[] buffer = new char[4096];
            StringBuilder text = new();
            while (true)
            {
                int count = await reader.ReadAsync(buffer.AsMemory(), budget.Token).ConfigureAwait(false);
                if (count == 0)
                {
                    return text.ToString();
                }

                if (Interlocked.Add(ref captured, count) > outputLimitCharacters)
                {
                    throw new InvalidDataException("Owned fixture output exceeded its shared character limit.");
                }

                text.Append(buffer, 0, count);
            }
        }

        try
        {
            started = process.Start();
            if (!started)
            {
                throw new InvalidOperationException("Owned fixture child did not start.");
            }

            _ = process.SafeHandle; // Retain the actual direct-child handle through settlement.
            DateTime? startTime = null;
            string? executable = null;
            try
            {
                startTime = process.StartTime.ToUniversalTime();
                executable = process.MainModule?.FileName;
            }
            catch (InvalidOperationException) when (process.HasExited)
            {
                // A terminal child may disappear before /proc metadata is read.
            }
            catch (Win32Exception) when (process.HasExited)
            {
            }

            identity = new(resourceId, process.Id, startTime, start.FileName, executable, false, false)
            {
                ExpiresUtc = DateTime.UtcNow + runtime + TimeSpan.FromSeconds(5),
                JournalPath = journal,
            };
            Record(identity, create: true);
            observe?.Invoke(identity);
            output = Track(() => Drain(process.StandardOutput));
            error = Track(() => Drain(process.StandardError));
            Task<bool> stdin = Track(async () =>
            {
                if (input is not null)
                {
                    await process.StandardInput.WriteAsync(input.AsMemory(), budget.Token).ConfigureAwait(false);
                }

                process.StandardInput.Close();
                return true;
            });
            Task<bool> exit = Track(async () =>
            {
                await process.WaitForExitAsync(budget.Token).ConfigureAwait(false);
                return true;
            });
            tasks = [output, error, stdin, exit];
            await Task.WhenAll(tasks).ConfigureAwait(false);
            exitCode = process.ExitCode;
        }
        catch (Exception failure)
        {
            Fail(failure);
        }
        finally
        {
            budget.Cancel();
            Stopwatch cleanupClock = Stopwatch.StartNew();
            TimeSpan Remaining()
            {
                TimeSpan remaining = TimeSpan.FromSeconds(5) - cleanupClock.Elapsed;
                if (remaining <= TimeSpan.Zero)
                {
                    throw new TimeoutException("Exact owned-child cleanup deadline exhausted.");
                }

                return remaining;
            }

            if (started)
            {
                try
                {
                    if (!process.HasExited)
                    {
                        try
                        {
                            if (terminate is null)
                            {
                                process.Kill(); // Retained direct child only; never enumerate or kill a tree.
                            }
                            else
                            {
                                terminate(process);
                            }
                        }
                        catch (Exception failure)
                        {
                            cleanupFailure = failure;
                        }
                    }

                    await process.WaitForExitAsync(CancellationToken.None).WaitAsync(Remaining()).ConfigureAwait(false);
                    // Faulted/cancelled drain tasks are settled too; observe their exceptions.
                    try
                    {
                        await Task.WhenAll(tasks).WaitAsync(Remaining()).ConfigureAwait(false);
                    }
                    catch (Exception) when (tasks.All(task => task.IsCompleted))
                    {
                    }

                    settled = process.HasExited && tasks.All(task => task.IsCompleted);
                }
                catch (Exception failure)
                {
                    cleanupFailure ??= failure;
                }
            }

            if (!started || settled)
            {
                try
                {
                    process.Dispose();
                }
                catch (Exception failure)
                {
                    cleanupFailure ??= failure;
                    settled = false;
                }
            }

            if (started && !settled)
            {
                // Preserve handles and exact ownership if settlement fails. The enclosing
                // finite manager must enforce final lifetime; this is never acceptance.
                identity ??= new(resourceId, process.Id, null, start.FileName, null, false, false)
                {
                    ExpiresUtc = DateTime.UtcNow,
                    JournalPath = journal,
                };
                Unsettled[identity.Id] = new(process, tasks, identity);
                cleanupFailure ??= new TimeoutException("Unsettled direct-child ownership retained.");
            }

            if (identity is not null)
            {
                try
                {
                    Observation ended = identity with { Terminal = settled, CleanupVerified = settled };
                    Record(ended, create: !File.Exists(journal));
                    observe?.Invoke(ended);
                }
                catch (Exception failure)
                {
                    cleanupFailure ??= failure;
                }
            }
        }

        if (cleanupFailure is not null)
        {
            if (firstFailure is null)
            {
                firstFailure = ExceptionDispatchInfo.Capture(cleanupFailure);
            }
            else
            {
                firstFailure.SourceException.Data["OwnedChildCleanupFailure"] = cleanupFailure;
            }
        }

        if (!settled && identity is not null && firstFailure is not null)
        {
            firstFailure.SourceException.Data["UnsettledOwnedChild"] = identity;
        }

        firstFailure?.Throw();
        // ExitCode was captured by the completed wait before the process was disposed.
        return new(exitCode, output!.Result, error!.Result);
    }
}
