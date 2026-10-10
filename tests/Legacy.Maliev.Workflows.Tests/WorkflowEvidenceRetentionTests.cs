using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using Xunit;
using YamlDotNet.RepresentationModel;

namespace Legacy.Maliev.Workflows.Tests;

public sealed class WorkflowEvidenceRetentionTests
{
    [Fact]
    public void OwnEvidenceJobs_PreserveRequiredValidationAndBoundPrivacyRetention()
    {
        AssertEvidenceContract(File.ReadAllText(Path.Combine(RepositoryContractTests.FindRepositoryRoot(), ".github", "workflows", "validate.yml")));
    }

    [Theory]
    [InlineData("retention-days: 14", "retention-days: 7")]
    [InlineData("path: TestResults/workflows-retained/", "path: TestResults/raw-evidence/")]
    [InlineData("VSTestLogger: trx", "VSTestLogger: console")]
    [InlineData("actions/dotnet-validate@ce7a577d9672c44cd445915420e3c552c70317d1", "actions/dotnet-validate@main")]
    [InlineData("&& github.event.pull_request.number == 341", "&& github.event.pull_request.number != 0")]
    [InlineData("python3 -B .maliev-evidence-controls/scripts/retain_workflows_test_evidence.py", "echo retained")]
    public void EvidenceContract_RejectsLostCustodyOrPrivacy(string original, string replacement)
    {
        string source = File.ReadAllText(Path.Combine(RepositoryContractTests.FindRepositoryRoot(), ".github", "workflows", "validate.yml"));
        string changed = source.Replace(original, replacement, StringComparison.Ordinal);
        Assert.NotEqual(source, changed);
        Assert.ThrowsAny<Exception>(() => AssertEvidenceContract(changed));
    }

    [Fact]
    public async Task ActualRetentionControls_RequireAllSeventeenPrivacyAndCustodyCases()
    {
        ProcessStartInfo start = new(OperatingSystem.IsWindows() ? "python" : "python3")
        {
            WorkingDirectory = RepositoryContractTests.FindRepositoryRoot(),
        };
        start.ArgumentList.Add("-B");
        start.ArgumentList.Add("-W");
        start.ArgumentList.Add("error");
        start.ArgumentList.Add("tests/test_retain_workflows_test_evidence.py");
        OwnedTestProcess.Result result = await OwnedTestProcess.RunAsync(start,
            cancellationToken: TestContext.Current.CancellationToken);
        Assert.Equal(0, result.ExitCode);
        Assert.True(result.Output.Length == 0, "Retention controls emitted unexpected stdout; payload withheld.");
        string fingerprint = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(result.Error))).ToLowerInvariant();
        Assert.True(result.Error.Contains("Ran 17 tests", StringComparison.Ordinal)
            && result.Error.TrimEnd().EndsWith("OK", StringComparison.Ordinal),
            $"Retention control result unavailable; sha256={fingerprint}");
    }

    private static void AssertEvidenceContract(string source)
    {
        YamlStream stream = [];
        stream.Load(new StringReader(source));
        var root = Assert.IsType<YamlMappingNode>(stream.Documents.Single().RootNode);
        var jobs = Mapping(root, "jobs");
        var original = Mapping(jobs, "validate");
        Assert.Equal("./.github/workflows/dotnet-validate.yml", Scalar(original, "uses"));
        foreach (string label in new[] { "head", "baseline" })
        {
            var job = Mapping(jobs, $"raw-{label}-evidence");
            Assert.Equal("20", Scalar(job, "timeout-minutes"));
            Assert.Equal("read", Scalar(Mapping(job, "permissions"), "contents"));
            var environment = Mapping(job, "env");
            Assert.Equal("trx", Scalar(environment, "VSTestLogger"));
            Assert.Equal("${{ github.workspace }}/TestResults/raw-evidence", Scalar(environment, "VSTestResultsDirectory"));
            Assert.Equal("${{ github.event.pull_request.head.sha || github.sha }}", Scalar(environment, "EVIDENCE_OWNER_HEAD"));
            var steps = Assert.IsType<YamlSequenceNode>(job.Children[new YamlScalarNode("steps")]);
            var validation = steps.Children.Cast<YamlMappingNode>().Single(s => Scalar(s, "name") == "Run unchanged full validation with actual TRX logging");
            Assert.Equal("MALIEV-Co-Ltd/Legacy.Maliev.Workflows/actions/dotnet-validate@ce7a577d9672c44cd445915420e3c552c70317d1", Scalar(validation, "uses"));
            Assert.False(validation.Children.ContainsKey(new YamlScalarNode("continue-on-error")));
            var prepare = steps.Children.Cast<YamlMappingNode>().Single(s => Scalar(s, "name") == "Prepare privacy-safe actual test evidence");
            Assert.Equal("always()", Scalar(prepare, "if"));
            Assert.Contains("python3 -B .maliev-evidence-controls/scripts/retain_workflows_test_evidence.py", Scalar(prepare, "run"), StringComparison.Ordinal);
            Assert.Contains("test -z \"$(git -C .maliev-evidence-controls status --porcelain)\"", Scalar(prepare, "run"), StringComparison.Ordinal);
            var upload = steps.Children.Cast<YamlMappingNode>().Single(s => Scalar(s, "name") == "Retain complete or explicitly unavailable evidence");
            Assert.Equal("always()", Scalar(upload, "if"));
            Assert.Equal("actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02", Scalar(upload, "uses"));
            var options = Mapping(upload, "with");
            Assert.Equal("14", Scalar(options, "retention-days"));
            Assert.Equal("TestResults/workflows-retained/", Scalar(options, "path"));
            Assert.Equal("false", Scalar(options, "include-hidden-files"));
            Assert.Equal("error", Scalar(options, "if-no-files-found"));
        }

        Assert.Equal("github.event_name == 'pull_request' && github.event.pull_request.number == 341", Scalar(Mapping(jobs, "raw-baseline-evidence"), "if"));
        Assert.Equal("a08d488e64071cc97bd5a4b270808b5ff28f10a3", Scalar(Mapping(Mapping(jobs, "raw-baseline-evidence"), "env"), "EXPECTED_SOURCE_HEAD"));
    }

    private static YamlMappingNode Mapping(YamlMappingNode node, string key) =>
        Assert.IsType<YamlMappingNode>(node.Children[new YamlScalarNode(key)]);

    private static string Scalar(YamlMappingNode node, string key) =>
        Assert.IsType<YamlScalarNode>(node.Children[new YamlScalarNode(key)]).Value
        ?? throw new InvalidDataException("Evidence contract scalar unavailable.");
}
