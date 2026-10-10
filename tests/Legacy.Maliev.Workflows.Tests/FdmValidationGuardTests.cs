using System.Diagnostics;
using Xunit;

namespace Legacy.Maliev.Workflows.Tests;

public sealed class FdmValidationGuardTests
{
    [Fact]
    public async Task PythonControls_RequireAllTwentyFourCasesWithoutSkips()
    {
        var result = await Run(OperatingSystem.IsWindows() ? "python" : "python3",
            "-B", "-W", "error", "tests/test_fdm_validation_guards.py");
        Assert.Equal(0, result.ExitCode);
        Assert.Equal("", result.Output);
        Assert.Contains("Ran 24 tests", result.Error, StringComparison.Ordinal);
        Assert.True(result.Error.TrimEnd().EndsWith("OK", StringComparison.Ordinal), result.Error);
        Assert.True(HasNoSkippedOutcomes(result.Error), result.Error);
    }

    [Fact]
    public async Task PythonSources_CompileWithoutExecutingGuards()
    {
        var result = await Run(OperatingSystem.IsWindows() ? "python" : "python3",
            "-B", "-W", "error", "-c",
            "from pathlib import Path; " +
            "paths=('scripts/fdm_validation_guards.py','tests/test_fdm_validation_guards.py'); " +
            "[compile(Path(p).read_bytes(),p,'exec') for p in paths]");
        Assert.Equal(0, result.ExitCode);
        Assert.Equal("", result.Output);
        Assert.Equal("", result.Error);
    }

    [Fact]
    public async Task PowerShellInterfaces_ParseWithoutExecutingScripts()
    {
        var result = await Run("pwsh", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command",
            "$ErrorActionPreference='Stop'; " +
            "foreach($name in @('Source','Admission','Trx')) { " +
            "$tokens=$null; $errors=$null; " +
            "$null=[System.Management.Automation.Language.Parser]::ParseFile(" +
            "(Join-Path (Get-Location).Path ('scripts/Assert-FdmValidation'+$name+'.ps1'))," +
            "[ref]$tokens,[ref]$errors); if($errors.Count -ne 0) { exit 2 } }");
        Assert.Equal(0, result.ExitCode);
        Assert.Equal("", result.Output);
        Assert.Equal("", result.Error);
    }

    [Theory]
    [InlineData("test_failed_skipped_error_and_bad_counters_are_refused (Demo.Cases) ... ok\nRan 24 tests in 0.1s\nOK\n", true)]
    [InlineData("test_guard (Demo.Cases) ... skipped 'fixture unavailable'\nRan 24 tests in 0.1s\nOK (skipped=1)\n", false)]
    [InlineData("Ran 24 tests in 0.1s\nOK (skipped=1)\n", false)]
    [InlineData("test_guard (Demo.Cases) ... ok\nRan 24 tests in 0.1s\nOK\n", true)]
    public void SkipOutcomes_DistinguishVerbosePassingNamesFromActualSkippedCases(string diagnostics, bool expected)
    {
        Assert.Equal(expected, HasNoSkippedOutcomes(diagnostics));
    }

    private static bool HasNoSkippedOutcomes(string diagnostics) =>
        !diagnostics.Split('\n').Any(line =>
            line.Contains(" ... skipped", StringComparison.Ordinal)
            || line.TrimStart().StartsWith("OK (skipped=", StringComparison.Ordinal));

    private static Task<OwnedTestProcess.Result> Run(string executable, params string[] arguments)
    {
        ProcessStartInfo start = new(executable)
        {
            WorkingDirectory = RepositoryContractTests.FindRepositoryRoot(),
        };
        start.Environment["PYTHONDONTWRITEBYTECODE"] = "1";
        foreach (string argument in arguments)
        {
            start.ArgumentList.Add(argument);
        }

        return OwnedTestProcess.RunAsync(start,
            timeout: TimeSpan.FromSeconds(30),
            cancellationToken: TestContext.Current.CancellationToken);
    }
}
