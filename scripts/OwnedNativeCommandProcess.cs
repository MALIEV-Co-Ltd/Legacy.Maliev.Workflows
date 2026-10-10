#nullable enable
using System;
using System.IO;
using System.ComponentModel;
using System.Diagnostics;
using System.Globalization;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;

namespace Legacy.Maliev.Workflows.NativeCommands;

public sealed class OwnedHostProcessIdentity : IDisposable
{
    public sealed record Observation(int Pid, string Birth, string Executable);

    private readonly Process _original;
    private readonly SafeProcessHandle _originalHandle;
    private readonly Observation _birth;
    private readonly SafeFileHandle? _pidfd;

    private OwnedHostProcessIdentity(Process original, SafeProcessHandle handle, Observation birth, SafeFileHandle? pidfd)
    {
        _original = original;
        _originalHandle = handle;
        _birth = birth;
        _pidfd = pidfd;
    }

    public static OwnedHostProcessIdentity Capture(Process original)
    {
        var handle = original.SafeHandle;
        if (original.HasExited) throw new InvalidOperationException("Host exited before ownership capture.");
        var before = ObserveFresh(original.Id);
        SafeFileHandle? pidfd = null;
        try
        {
            if (OperatingSystem.IsLinux())
            {
                var descriptor = NativePidfdOpen(original.Id, 0);
                if (descriptor < 0) throw new Win32Exception(Marshal.GetLastPInvokeError(), "pidfd_open failed; manager cleanup required.");
                pidfd = new SafeFileHandle((IntPtr)descriptor, ownsHandle: true);
            }
            RequireSame(before, ObserveFresh(original.Id));
            // Reject a descriptor opened after the original child exited/reaped.
            if (original.HasExited) throw new InvalidOperationException("Original host exited during ownership capture.");
            return new OwnedHostProcessIdentity(original, handle, before, pidfd);
        }
        catch (Exception primary)
        {
            try { pidfd?.Dispose(); }
            catch (Exception cleanup) { primary.Data["PidfdCaptureCleanupFailure"] = cleanup; }
            throw;
        }
    }

    public static Observation ObserveFresh(int pid)
    {
        if (OperatingSystem.IsLinux())
        {
            var stat = File.ReadAllText($"/proc/{pid}/stat");
            var fields = stat[(stat.LastIndexOf(')') + 2)..].Split(' ', StringSplitOptions.RemoveEmptyEntries);
            // Field 22, preserved as exact kernel clock ticks; no DateTime rounding.
            var birth = ulong.Parse(fields[19], CultureInfo.InvariantCulture).ToString(CultureInfo.InvariantCulture);
            var executable = new FileInfo($"/proc/{pid}/exe").LinkTarget
                ?? throw new InvalidOperationException("Fresh proc executable unavailable.");
            var after = File.ReadAllText($"/proc/{pid}/stat");
            var afterFields = after[(after.LastIndexOf(')') + 2)..].Split(' ', StringSplitOptions.RemoveEmptyEntries);
            if (fields[19] != afterFields[19] || executable != new FileInfo($"/proc/{pid}/exe").LinkTarget) throw new InvalidOperationException("Process birth changed during OS observation.");
            return new Observation(pid, birth, executable);
        }
        if (OperatingSystem.IsWindows())
        {
            // A NEW Process instance for every observation: no cached StartTime/Modules reuse.
            using var fresh = Process.GetProcessById(pid);
            return new Observation(pid, fresh.StartTime.ToUniversalTime().Ticks.ToString(CultureInfo.InvariantCulture),
                fresh.MainModule?.FileName ?? throw new InvalidOperationException("Fresh executable unavailable."));
        }
        throw new PlatformNotSupportedException("Owned host cleanup requires reviewed Windows or Linux observers.");
    }

    public static void RequireSame(Observation expected, Observation actual)
    {
        var comparison = OperatingSystem.IsWindows() ? StringComparison.OrdinalIgnoreCase : StringComparison.Ordinal;
        if (expected.Pid != actual.Pid || expected.Birth != actual.Birth ||
            !string.Equals(expected.Executable, actual.Executable, comparison))
            throw new InvalidOperationException("Fresh OS process identity changed; manager cleanup required.");
    }

    public void VerifyFresh()
    {
        if (_originalHandle.IsClosed || _originalHandle.IsInvalid)
            throw new InvalidOperationException("Retained original process handle unavailable.");
        RequireSame(_birth, ObserveFresh(_birth.Pid));
    }

    public void Graceful()
    {
        VerifyFresh();
        if (OperatingSystem.IsLinux()) SendLinuxSignal(15); // SIGTERM on exact retained pidfd.
        else _original.CloseMainWindow();
    }

    public void Escalate()
    {
        VerifyFresh(); // Independent fresh observation before escalation.
        if (OperatingSystem.IsLinux()) SendLinuxSignal(9); // SIGKILL, exact retained pidfd.
        else _original.Kill(); // Original retained Windows handle; never a tree selector.
    }

    private void SendLinuxSignal(int signal)
    {
        if (_pidfd is null || _pidfd.IsClosed || _pidfd.IsInvalid)
            throw new InvalidOperationException("Retained Linux pidfd unavailable; no PID-only fallback.");
        if (NativePidfdSendSignal(_pidfd, signal, IntPtr.Zero, 0) != 0)
        {
            var error = Marshal.GetLastPInvokeError();
            if (error == 3 && _original.HasExited) return; // ESRCH for the exact exited child.
            throw new Win32Exception(error, "Exact pidfd signal failed; manager cleanup required.");
        }
    }

    public void Dispose() => _pidfd?.Dispose(); // Original Process owns its SafeProcessHandle.

    // Ubuntu's glibc >=2.36 exports these APIs. Unsupported hosts fail closed.
    [DllImport("libc.so.6", EntryPoint = "pidfd_open", SetLastError = true)]
    private static extern int NativePidfdOpen(int pid, uint flags);

    [DllImport("libc.so.6", EntryPoint = "pidfd_send_signal", SetLastError = true)]
    private static extern int NativePidfdSendSignal(SafeFileHandle pidfd, int signal, IntPtr info, uint flags);
}
