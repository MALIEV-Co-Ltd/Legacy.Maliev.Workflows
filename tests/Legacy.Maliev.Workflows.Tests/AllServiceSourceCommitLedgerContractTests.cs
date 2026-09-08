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
    public void Generator_is_present_and_read_only_against_source()
    {
        var script = File.ReadAllText(Path.Combine(Root, "scripts", "New-SourceCommitLedger.ps1"));
        Assert.Contains("git -C $SourceRepository", script, StringComparison.Ordinal);
        Assert.DoesNotContain("git -C $SourceRepository fetch", script, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("git -C $SourceRepository pull", script, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("git -C $SourceRepository checkout", script, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("git -C $SourceRepository reset", script, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("git -C $SourceRepository clean", script, StringComparison.OrdinalIgnoreCase);
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
