using Xunit;

namespace Legacy.Maliev.Workflows.Tests;

public sealed class RepositoryScopeContractTests
{
    [Fact]
    public void ReusableWorkflowRepositoryDoesNotCarryProjectMigrationTracking()
    {
        var root = RepositoryContractTests.FindRepositoryRoot();
        Assert.False(Directory.Exists(Path.Combine(root, "migration")));
        foreach (var script in new[] { "New-SourceCommitLedger.ps1", "New-SourceCommitResolutionLedger.ps1", "Test-SourcePageAcceptance.ps1" })
        {
            Assert.False(File.Exists(Path.Combine(root, "scripts", script)));
        }

        var readme = File.ReadAllText(Path.Combine(root, "README.md"));
        Assert.Contains("Legacy.Maliev.MigrationTracking", readme, StringComparison.Ordinal);
        Assert.DoesNotContain("## All-service source commit ledger", readme, StringComparison.Ordinal);
    }
}
