using System.Text.Json;
using Xunit;

namespace Legacy.Maliev.Workflows.Tests;

public sealed class SourcePageAcceptanceContractTests
{
    [Fact]
    public void Source_page_inventory_is_complete_but_does_not_claim_workflow_acceptance()
    {
        var root = FindRepositoryRoot();
        var path = Path.Combine(root, "migration", "source-page-acceptance.json");
        using var document = JsonDocument.Parse(File.ReadAllText(path));
        var inventory = document.RootElement;

        Assert.Equal(1, inventory.GetProperty("schemaVersion").GetInt32());
        Assert.Equal("MALIEV-Co-Ltd/maliev-web", inventory.GetProperty("sourceRepository").GetString());
        Assert.Matches("^[0-9a-f]{40}$", inventory.GetProperty("sourceCommit").GetString()!);

        var pageTrees = inventory.GetProperty("sourcePageTrees");
        Assert.Matches("^[0-9a-f]{40}$", pageTrees.GetProperty("Maliev.Web/Pages").GetString()!);
        Assert.Matches("^[0-9a-f]{40}$", pageTrees.GetProperty("Maliev.Intranet/Pages").GetString()!);

        var pages = inventory.GetProperty("pages").EnumerateArray().ToArray();
        Assert.Equal(79, pages.Length);
        Assert.Equal(35, pages.Count(page =>
            page.GetProperty("ownerRepository").GetString() == "Legacy.Maliev.Web"));
        Assert.Equal(44, pages.Count(page =>
            page.GetProperty("ownerRepository").GetString() == "Legacy.Maliev.Intranet"));

        var paths = new HashSet<string>(StringComparer.Ordinal);
        foreach (var page in pages)
        {
            var sourcePath = page.GetProperty("sourcePath").GetString()!;
            Assert.True(paths.Add(sourcePath), $"Duplicate source page: {sourcePath}");
            Assert.Matches("^Maliev\\.(Web|Intranet)/Pages/.+\\.cshtml$", sourcePath);
            var owner = sourcePath.StartsWith("Maliev.Web/", StringComparison.Ordinal)
                ? "Legacy.Maliev.Web"
                : "Legacy.Maliev.Intranet";
            Assert.Equal(owner, page.GetProperty("ownerRepository").GetString());
            Assert.Equal("unverified", page.GetProperty("status").GetString());
            Assert.Equal(JsonValueKind.Null, page.GetProperty("targetRoute").ValueKind);
            Assert.Empty(page.GetProperty("evidence").EnumerateArray());
        }

        var sorted = paths.Order(StringComparer.Ordinal).ToArray();
        Assert.Equal(sorted, pages.Select(page => page.GetProperty("sourcePath").GetString()!).ToArray());
    }

    [Fact]
    public void Source_verifier_is_read_only_and_detects_tree_or_inventory_drift()
    {
        var path = Path.Combine(FindRepositoryRoot(), "scripts", "Test-SourcePageAcceptance.ps1");
        var script = File.ReadAllText(path);
        Assert.Contains("ls-remote origin refs/heads/main", script, StringComparison.Ordinal);
        Assert.Contains("cat-file -e", script, StringComparison.Ordinal);
        Assert.Contains("source_page_tree_changed", script, StringComparison.Ordinal);
        Assert.Contains("source_page_inventory_changed", script, StringComparison.Ordinal);
        foreach (var forbidden in new[] { " fetch ", " pull ", " checkout ", " reset ", " clean ", " push " })
        {
            Assert.DoesNotContain(forbidden, script, StringComparison.OrdinalIgnoreCase);
        }
    }

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
