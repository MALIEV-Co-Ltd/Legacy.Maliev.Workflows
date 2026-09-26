using System.Text.Json;
using System.Text.RegularExpressions;
using Xunit;

namespace Legacy.Maliev.Workflows.Tests;

public sealed class AllServiceSourceCommitLedgerContractTests
{
    private static readonly string Root = FindRepositoryRoot();
    private static readonly Regex Sha = new("^[0-9a-f]{40}$", RegexOptions.CultureInvariant);

    [Fact]
    public void Ownership_map_has_unambiguous_valid_rules()
    {
        using var document = Load("migration/source-path-owners.json");
        var root = document.RootElement;
        Assert.Equal(1, root.GetProperty("schemaVersion").GetInt32());
        Assert.Equal("MALIEV-Co-Ltd/maliev-web", root.GetProperty("sourceRepository").GetString());
        Assert.Equal(
            ["Legacy.Maliev.ContactService"],
            root.GetProperty("architecturalTargets").EnumerateArray().Select(item => item.GetString()!).ToArray());

        var patterns = new HashSet<string>(StringComparer.Ordinal);
        foreach (var rule in root.GetProperty("rules").EnumerateArray())
        {
            var pattern = Assert.IsType<string>(rule.GetProperty("pattern").GetString());
            Assert.True(patterns.Add(pattern), $"Duplicate mapping pattern: {pattern}");
            _ = new Regex(pattern, RegexOptions.CultureInvariant);

            var hasOwners = rule.TryGetProperty("owners", out var owners) && owners.GetArrayLength() > 0;
            var hasDisposition = rule.TryGetProperty("disposition", out var disposition)
                && disposition.GetString() is "approved-retirement" or "source-tooling-only";
            Assert.True(hasOwners ^ hasDisposition, $"Rule must define owners or an approved non-runtime disposition: {pattern}");
        }
    }

    [Theory]
    [InlineData("Maliev.Intranet/deploy.ps1", "approved-retirement", null)]
    [InlineData("Maliev.Intranet/package-lock.json", "approved-retirement", null)]
    [InlineData("tools/Validate-DeploymentScripts.ps1", "approved-retirement", null)]
    [InlineData("docs/superpowers/plans/2026-09-26-3d-printing-ctr-funnel.md", "source-tooling-only", null)]
    [InlineData("docs/seo/2026-09-26-3d-printing-ctr-decision-pack.md", "migration-required", "Legacy.Maliev.Web")]
    public void Recent_source_paths_have_one_explicit_owner_or_retirement(
        string path,
        string expectedDisposition,
        string? expectedOwner)
    {
        using var document = Load("migration/source-path-owners.json");
        var matches = document.RootElement.GetProperty("rules").EnumerateArray()
            .Where(rule => Regex.IsMatch(path, rule.GetProperty("pattern").GetString()!, RegexOptions.CultureInvariant))
            .ToArray();

        var rule = Assert.Single(matches);
        var disposition = rule.TryGetProperty("disposition", out var value)
            ? value.GetString()
            : "migration-required";
        Assert.Equal(expectedDisposition, disposition);
        if (expectedOwner is not null)
        {
            Assert.Contains(expectedOwner, rule.GetProperty("owners").EnumerateArray().Select(owner => owner.GetString()));
        }
        else
        {
            Assert.False(string.IsNullOrWhiteSpace(rule.GetProperty("decision").GetString()));
        }
    }

    [Fact]
    public void Ledger_is_complete_structurally_and_fail_closed()
    {
        using var document = Load("migration/source-commit-ledger.json");
        var root = document.RootElement;
        Assert.Equal(1, root.GetProperty("schemaVersion").GetInt32());
        Assert.Equal("MALIEV-Co-Ltd/maliev-web", root.GetProperty("sourceRepository").GetString());
        Assert.Matches(Sha, root.GetProperty("sourceCheckpoint").GetString()!);
        var targets = root.GetProperty("legacyTargets");
        Assert.True(targets.EnumerateObject().Any());
        Assert.True(targets.TryGetProperty("Legacy.Maliev.ContactService", out _),
            "The extracted ContactService must retain target-SHA evidence even without a one-to-one source project.");
        foreach (var target in targets.EnumerateObject())
        {
            var mainSha = target.Value.GetProperty("mainSha").GetString()!;
            Assert.Matches(Sha, mainSha);
            Assert.Equal($"https://github.com/MALIEV-Co-Ltd/{target.Name}/commit/{mainSha}", target.Value.GetProperty("evidence").GetString());
        }

        var records = root.GetProperty("records").EnumerateArray().ToArray();
        Assert.Equal(root.GetProperty("nonMergeCommitCount").GetInt32(), records.Length);
        Assert.NotEmpty(records);

        var commits = new HashSet<string>(StringComparer.Ordinal);
        for (var index = 0; index < records.Length; index++)
        {
            var record = records[index];
            Assert.Equal(index + 1, record.GetProperty("ordinal").GetInt32());
            var commit = record.GetProperty("commit").GetString()!;
            Assert.Matches(Sha, commit);
            Assert.True(commits.Add(commit), $"Duplicate source commit: {commit}");
            Assert.Equal($"https://github.com/MALIEV-Co-Ltd/maliev-web/commit/{commit}", record.GetProperty("sourceEvidence").GetString());

            _ = record.GetProperty("authoredAt").GetDateTimeOffset();
            foreach (var parent in record.GetProperty("parents").EnumerateArray())
            {
                Assert.Matches(Sha, parent.GetString()!);
            }
            Assert.False(string.IsNullOrWhiteSpace(record.GetProperty("subject").GetString()));

            var classifications = record.GetProperty("classifications").EnumerateArray().ToArray();
            Assert.NotEmpty(classifications);
            foreach (var classification in classifications)
            {
                Assert.False(string.IsNullOrWhiteSpace(classification.GetProperty("path").GetString()));
                var disposition = classification.GetProperty("disposition").GetString();
                Assert.Contains(disposition, new[] { "migration-required", "approved-retirement", "source-tooling-only" });
                if (disposition == "migration-required")
                {
                    var owners = classification.GetProperty("owners").EnumerateArray().ToArray();
                    Assert.NotEmpty(owners);
                    Assert.All(owners, owner => Assert.True(targets.TryGetProperty(owner.GetString()!, out _), $"Missing target evidence for {owner.GetString()}"));
                }
                else
                {
                    Assert.False(string.IsNullOrWhiteSpace(classification.GetProperty("decision").GetString()));
                }
            }
        }
    }

    [Fact]
    public void Ledger_tracks_every_recent_source_commit_without_treating_retired_inputs_as_runtime()
    {
        using var document = Load("migration/source-commit-ledger.json");
        var records = document.RootElement.GetProperty("records").EnumerateArray().ToArray();
        foreach (var commit in new[]
        {
            "a73acf2e4de9a611c7eda22cf6dbdae333d231cf",
            "c97ced90bd8913a1686fec16405efd57c62d3176",
            "31ba7d7c9816330529c8c335939fde5d0fc4a632",
            "92f2263531971457cd9d71da41a653e91a1b6079",
            "de75a0e55240ee78053c8c87eb4a83b67cdd32f2",
            "0665dcd54788c037ee663ff90f32741014f0c81c",
            "3e38f9691b1c502755f1ab2b00ed90f8261eafef",
            "7435f6b8fde7cb06c439532f5aac0f8a31778175",
            "4198baa6b0e7903f2b9b6e3d5d68f9d2c2b5b0db",
        })
        {
            Assert.Contains(records, record => record.GetProperty("commit").GetString() == commit);
        }

        var deployment = Assert.Single(records, record =>
            record.GetProperty("commit").GetString() == "7435f6b8fde7cb06c439532f5aac0f8a31778175");
        Assert.All(deployment.GetProperty("classifications").EnumerateArray(), classification =>
            Assert.Equal("approved-retirement", classification.GetProperty("disposition").GetString()));
        var dependency = Assert.Single(records, record =>
            record.GetProperty("commit").GetString() == "4198baa6b0e7903f2b9b6e3d5d68f9d2c2b5b0db");
        Assert.All(dependency.GetProperty("classifications").EnumerateArray(), classification =>
            Assert.Equal("approved-retirement", classification.GetProperty("disposition").GetString()));
    }

    [Fact]
    public void Generator_is_present_and_read_only_against_source()
    {
        var script = File.ReadAllText(Path.Combine(Root, "scripts", "New-SourceCommitLedger.ps1"));
        Assert.Contains("git -C $SourceRepository", script, StringComparison.Ordinal);
        Assert.DoesNotContain("git -C $SourceRepository fetch", script, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("git -C $SourceRepository pull", script, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("git -C $SourceRepository checkout", script, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("git -C $SourceRepository reset", script, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("git -C $SourceRepository clean", script, StringComparison.OrdinalIgnoreCase);
        Assert.Contains("git -C $repositoryPath ls-remote origin refs/heads/main", script, StringComparison.Ordinal);
        Assert.DoesNotContain("git -C $repositoryPath fetch", script, StringComparison.OrdinalIgnoreCase);
        Assert.Contains("$mapping.architecturalTargets", script, StringComparison.Ordinal);
    }

    private static JsonDocument Load(string relativePath) =>
        JsonDocument.Parse(File.ReadAllText(Path.Combine(Root, relativePath.Replace('/', Path.DirectorySeparatorChar))));

    private static string FindRepositoryRoot()
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);
        while (directory is not null && !File.Exists(Path.Combine(directory.FullName, "Legacy.Maliev.Workflows.slnx")))
        {
            directory = directory.Parent;
        }

        return directory?.FullName ?? throw new InvalidOperationException("Repository root was not found.");
    }
}
