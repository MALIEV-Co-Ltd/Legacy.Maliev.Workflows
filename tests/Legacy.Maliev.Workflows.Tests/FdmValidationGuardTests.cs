using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using Xunit;

namespace Legacy.Maliev.Workflows.Tests;

public sealed class FdmValidationGuardTests
{
    [Fact]
    public async Task PythonControls_RequireAllTwentyFourCasesWithoutSkips()
    {
        var result = await Run(OperatingSystem.IsWindows() ? "python" : "python3",
            "-B", "-W", "error", "tests/test_fdm_validation_guards.py");
        string source = File.ReadAllText(Path.Combine(RepositoryContractTests.FindRepositoryRoot(), "tests", "test_fdm_validation_guards.py"));
        HashSet<string> expectedNames = new(Regex.Matches(source, @"(?m)^    def (test_[A-Za-z0-9_]+)\(")
            .Select(match => match.Groups[1].Value), StringComparer.Ordinal);
        EmitActualPythonDiagnostics(result, expectedNames, value =>
        {
            ITestOutputHelper output = TestContext.Current.TestOutputHelper
                ?? throw new InvalidOperationException("Actual Python test output helper unavailable.");
            output.Write(value);
        });
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

    [Theory]
    [InlineData("unexpected-content")]
    [InlineData("missing-case")]
    [InlineData("duplicate-case")]
    [InlineData("unknown-case")]
    [InlineData("skipped-case")]
    [InlineData("oversized-content")]
    [InlineData("unexpected-stdout")]
    [InlineData("malformed-summary")]
    [InlineData("mismatched-case-identity")]
    public void DiagnosticPrivacy_RefusesUnsafeSyntheticShapesBeforeEmission(string mutation)
    {
        HashSet<string> names = new(Enumerable.Range(0, 24).Select(index => $"test_fixture_{index}"), StringComparer.Ordinal);
        string[] rows = names.Order(StringComparer.Ordinal)
            .Select(name => $"{name} (__main__.FdmGuardTests.{name}) ... ok").ToArray();
        string body = string.Join('\n', rows) + "\n\n" + new string('-', 70) + "\nRan 24 tests in 0.1s\n\nOK\n";
        string changed = mutation switch
        {
            "unexpected-content" => body + "private-sentinel\n",
            "missing-case" => body[(body.IndexOf('\n') + 1)..],
            "duplicate-case" => rows[0] + "\n" + body,
            "unknown-case" => body.Replace(rows[0], "test_unreviewed (__main__.FdmGuardTests.test_unreviewed) ... ok", StringComparison.Ordinal),
            "skipped-case" => body.Replace(rows[0], rows[0].Replace(" ... ok", " ... skipped 'private-sentinel'", StringComparison.Ordinal), StringComparison.Ordinal),
            "oversized-content" => new string('x', 300000),
            "unexpected-stdout" => body,
            "malformed-summary" => body.Replace("Ran 24 tests", "Ran 23 tests", StringComparison.Ordinal),
            "mismatched-case-identity" => body.Replace(rows[0], rows[0].Replace($"FdmGuardTests.{names.Order(StringComparer.Ordinal).First()}", "FdmGuardTests.private_sentinel", StringComparison.Ordinal), StringComparison.Ordinal),
            _ => throw new InvalidDataException("Unknown synthetic privacy mutation."),
        };
        string stdout = mutation == "unexpected-stdout" ? "private-sentinel" : "";
        OwnedTestProcess.Result result = new(0, stdout, changed);
        List<string> emitted = [];
        Exception failure = Assert.ThrowsAny<Exception>(() => EmitActualPythonDiagnostics(result, names, emitted.Add));
        Assert.Empty(emitted);
        Assert.DoesNotContain("private-sentinel", failure.Message, StringComparison.Ordinal);
        Assert.DoesNotContain("private_sentinel", failure.Message, StringComparison.Ordinal);
    }

    private static void EmitActualPythonDiagnostics(OwnedTestProcess.Result result, IReadOnlySet<string> expectedNames, Action<string> emit)
    {
        Assert.Equal(0, result.ExitCode);
        Assert.True(result.Output.Length == 0, BoundedFailure("unexpected-stdout", result.Output));
        Assert.Equal(24, expectedNames.Count);
        Assert.True(HasSafePythonDiagnostics(result.Error, expectedNames), BoundedFailure("invalid-stderr-shape", result.Error));
        emit("fdm-python/v1 begin\n");
        emit(result.Error);
        emit("fdm-python/v1 end\n");
    }

    private static string BoundedFailure(string category, string value) =>
        $"FDM Python controls unavailable: {category}; sha256={Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(value))).ToLowerInvariant()}";

    private static bool HasSafePythonDiagnostics(string diagnostics, IReadOnlySet<string> expectedNames)
    {
        if (expectedNames.Count != 24 || Encoding.UTF8.GetByteCount(diagnostics) > 256 * 1024 || !HasNoSkippedOutcomes(diagnostics))
        {
            return false;
        }

        HashSet<string> seen = new(StringComparer.Ordinal);
        int summaries = 0;
        int terminal = 0;
        foreach (string original in diagnostics.Split('\n'))
        {
            string line = original.TrimEnd('\r');
            Match match = Regex.Match(line, @"^(test_[A-Za-z0-9_]+) \(__main__\.FdmGuardTests(?:\.\1)?\) \.\.\. ok$", RegexOptions.CultureInvariant);
            if (match.Success)
            {
                string name = match.Groups[1].Value;
                if (!expectedNames.Contains(name) || !seen.Add(name))
                {
                    return false;
                }
            }
            else if (Regex.IsMatch(line, @"^Ran 24 tests in [0-9]+(?:\.[0-9]+)?s$", RegexOptions.CultureInvariant))
            {
                summaries++;
            }
            else if (line == "OK")
            {
                terminal++;
            }
            else if (line.Length != 0 && line != new string('-', 70))
            {
                return false;
            }
        }

        return seen.SetEquals(expectedNames) && summaries == 1 && terminal == 1
            && diagnostics.TrimEnd().EndsWith("OK", StringComparison.Ordinal);
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
