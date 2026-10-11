using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using Xunit;

namespace Legacy.Maliev.Workflows.Tests;

public sealed class FdmSourceParityContractTests
{
    [Fact]
    public async Task ActualSourceParityControls_PreserveAllTwentyThreeObligationCases()
    {
        string root = RepositoryContractTests.FindRepositoryRoot();
        const string script = "tests/test_fdm_source_parity_contract.py";
        HashSet<string> expected = Regex.Matches(File.ReadAllText(Path.Combine(root, script)),
            @"(?m)^    def (test_\w+)\(self\):").Select(match => match.Groups[1].Value).ToHashSet(StringComparer.Ordinal);
        ProcessStartInfo start = new(OperatingSystem.IsWindows() ? "python" : "python3")
        {
            WorkingDirectory = root,
        };
        start.ArgumentList.Add("-B");
        start.ArgumentList.Add("-W");
        start.ArgumentList.Add("error");
        start.ArgumentList.Add(script);
        OwnedTestProcess.Result result = await OwnedTestProcess.RunAsync(start,
            cancellationToken: TestContext.Current.CancellationToken);
        string fingerprint = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(result.Error))).ToLowerInvariant();
        string diagnostics = result.Error.Replace("\r\n", "\n", StringComparison.Ordinal);
        MatchCollection rows = Regex.Matches(diagnostics,
            @"(?m)^(test_\w+) \(__main__\.FdmSourceParityContractTests\.\1\) \.\.\. ok$");
        HashSet<string> observed = rows.Select(match => match.Groups[1].Value).ToHashSet(StringComparer.Ordinal);
        bool allowedLines = diagnostics.Split('\n').All(line => line.Length == 0
            || line == "----------------------------------------------------------------------" || line == "OK"
            || Regex.IsMatch(line, @"^Ran 23 tests in [0-9.]+s$")
            || Regex.IsMatch(line, @"^(test_\w+) \(__main__\.FdmSourceParityContractTests\.\1\) \.\.\. ok$"));
        Assert.True(result.ExitCode == 0 && result.Output.Length == 0 && result.Error.Length <= 256 * 1024
            && expected.Count == 23 && rows.Count == 23 && observed.Count == 23 && expected.SetEquals(observed)
            && Regex.Matches(diagnostics, @"(?m)^Ran 23 tests in [0-9.]+s$").Count == 1
            && diagnostics.TrimEnd().EndsWith("\nOK", StringComparison.Ordinal) && allowedLines,
            $"Source parity controls unavailable; exit={result.ExitCode}; stderrSha256={fingerprint}");
    }
}
