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
        Assert.Equal(2, root.GetProperty("schemaVersion").GetInt32());
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
        Assert.Equal(root.GetProperty("commitCount").GetInt32(), records.Length);
        Assert.Equal(records.Length, root.GetProperty("nonMergeCommitCount").GetInt32() +
            root.GetProperty("mergeCommitCount").GetInt32());
        Assert.True(root.GetProperty("mergeCommitCount").GetInt32() > 0);
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
            var parents = record.GetProperty("parents").EnumerateArray().ToArray();
            Assert.Equal(parents.Length > 1, record.GetProperty("isMerge").GetBoolean());
            foreach (var parent in parents)
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
            "3644a0d7850dcb82208887ae41d7ca931ea4e60e",
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
        Assert.True(Assert.Single(records, record =>
            record.GetProperty("commit").GetString() == "3644a0d7850dcb82208887ae41d7ca931ea4e60e")
            .GetProperty("isMerge").GetBoolean());
    }

    [Fact]
    public void Resolution_companion_tracks_every_commit_without_claiming_unproven_parity()
    {
        using var ownership = Load("migration/source-commit-ledger.json");
        using var resolutions = Load("migration/source-commit-resolutions.json");
        var source = ownership.RootElement;
        var root = resolutions.RootElement;
        Assert.Equal(1, root.GetProperty("schemaVersion").GetInt32());
        Assert.Equal(source.GetProperty("sourceRepository").GetString(),
            root.GetProperty("sourceRepository").GetString());
        Assert.Equal(source.GetProperty("sourceCheckpoint").GetString(),
            root.GetProperty("sourceCheckpoint").GetString());
        var commits = source.GetProperty("records").EnumerateArray().ToArray();
        var records = root.GetProperty("records").EnumerateArray().ToArray();
        Assert.Equal(commits.Length, root.GetProperty("sourceCommitCount").GetInt32());
        Assert.Equal(commits.Length, records.Length);
        Assert.Equal(commits.Length,
            root.GetProperty("fullyResolvedCommitCount").GetInt32() +
            root.GetProperty("unresolvedCommitCount").GetInt32());
        Assert.False(root.GetProperty("complete").GetBoolean());
        Assert.True(root.GetProperty("unresolvedCommitCount").GetInt32() > 0);

        var seen = new HashSet<string>(StringComparer.Ordinal);
        for (var index = 0; index < commits.Length; index++)
        {
            var sourceCommit = commits[index];
            var record = records[index];
            var sha = record.GetProperty("sourceSha").GetString()!;
            Assert.Equal(sourceCommit.GetProperty("commit").GetString(), sha);
            Assert.True(seen.Add(sha));
            Assert.Equal(sourceCommit.GetProperty("isMerge").GetBoolean(),
                record.GetProperty("isMerge").GetBoolean());
            Assert.Contains(record.GetProperty("status").GetString(),
                new[] { "pending", "partial", "blocked", "migrated", "approved-retirement" });
            var expectedOwners = sourceCommit.GetProperty("classifications").EnumerateArray()
                .Where(item => item.GetProperty("disposition").GetString() == "migration-required")
                .SelectMany(item => item.GetProperty("owners").EnumerateArray().Select(owner => owner.GetString()!))
                .Distinct(StringComparer.Ordinal).Order(StringComparer.Ordinal).ToArray();
            var actualOwners = record.GetProperty("ownerResolutions").EnumerateObject()
                .Select(item => item.Name).Order(StringComparer.Ordinal).ToArray();
            Assert.Equal(expectedOwners, actualOwners);
            foreach (var owner in record.GetProperty("ownerResolutions").EnumerateObject())
            {
                var result = owner.Value;
                Assert.Contains(result.GetProperty("status").GetString(),
                    new[] { "pending", "blocked", "migrated" });
                if (result.GetProperty("status").GetString() == "migrated")
                {
                    Assert.NotEmpty(result.GetProperty("issueUrls").EnumerateArray());
                    Assert.NotEmpty(result.GetProperty("prUrls").EnumerateArray());
                    Assert.Matches(Sha, result.GetProperty("mergedTargetSha").GetString()!);
                    Assert.NotEmpty(result.GetProperty("validationEvidenceUrls").EnumerateArray());
                }
            }
            var retirement = record.GetProperty("retirementApproval");
            if (retirement.ValueKind != JsonValueKind.Null &&
                retirement.GetProperty("status").GetString() == "approved")
            {
                Assert.False(string.IsNullOrWhiteSpace(retirement.GetProperty("reason").GetString()));
                Assert.StartsWith("https://", retirement.GetProperty("evidenceUrl").GetString());
            }
        }

        foreach (var sha in new[]
        {
            "c88a4e93c28b7306a5f2c353ee2ed1b8677ff7f8",
            "3f090e9488d91790636558d3ce59c7f046efa1d8",
            "ce8a2f4037bedf51df1aedde4aef531c2faff3c7",
            "d46b4d6a3fca8148792da1033c77d60d22d7b9d9",
            "49294cf81ec1940c433d9092af0b96f050298930",
            "027e733e8e7a5abebf975598fda86589ca034b32",
        })
        {
            var migrated = Assert.Single(records, record => record.GetProperty("sourceSha").GetString() == sha);
            Assert.Equal("migrated", migrated.GetProperty("status").GetString());
            var web = migrated.GetProperty("ownerResolutions").GetProperty("Legacy.Maliev.Web");
            Assert.Equal("migrated", web.GetProperty("status").GetString());
            Assert.Contains(web.GetProperty("issueUrls").EnumerateArray(),
                url => url.GetString() == "https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Web/issues/276");
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
        Assert.DoesNotContain("rev-list --reverse --no-merges", script, StringComparison.OrdinalIgnoreCase);
        Assert.Contains("Invoke-SourceGit diff --name-only $parents[0] $commit", script, StringComparison.Ordinal);
        Assert.Contains("Invoke-SourceGit ls-remote origin refs/heads/main", script, StringComparison.Ordinal);
        Assert.Contains("git -C $repositoryPath ls-remote origin refs/heads/main", script, StringComparison.Ordinal);
        Assert.DoesNotContain("git -C $repositoryPath fetch", script, StringComparison.OrdinalIgnoreCase);
        Assert.Contains("$mapping.architecturalTargets", script, StringComparison.Ordinal);

        var resolutionScript = File.ReadAllText(Path.Combine(Root, "scripts", "New-SourceCommitResolutionLedger.ps1"));
        Assert.Contains("git -C $SourceRepository ls-remote origin refs/heads/main", resolutionScript, StringComparison.Ordinal);
        Assert.DoesNotContain("git -C $SourceRepository fetch", resolutionScript, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("git -C $SourceRepository reset", resolutionScript, StringComparison.OrdinalIgnoreCase);
        Assert.Contains("merge-base --is-ancestor", resolutionScript, StringComparison.Ordinal);
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
