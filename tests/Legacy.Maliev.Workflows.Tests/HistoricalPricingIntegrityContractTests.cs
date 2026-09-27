using Xunit;

namespace Legacy.Maliev.Workflows.Tests;

public sealed class HistoricalPricingIntegrityContractTests
{
    [Fact]
    public void PricingIntegrityHistory_PreservesEverySourceCommitAndReleaseBoundary()
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);
        while (directory is not null && !File.Exists(Path.Combine(directory.FullName, "Legacy.Maliev.Workflows.slnx")))
        {
            directory = directory.Parent;
        }

        var root = directory?.FullName ?? throw new DirectoryNotFoundException("Repository root was not found.");
        var record = File.ReadAllText(Path.Combine(root, "migration", "historical-additive-pricing-integrity-2026-09-14.md"));

        foreach (var sourceSha in new[]
        {
            "d957038a208b2cbdf1604010a6d82f1d74f1a06c",
            "2128395c31a1ebfe94f9d0ced846bdc861fe62f4",
            "60d3677264e046fd73028ff3ccb75097d153bedb",
            "2d126d1d55a3240e40678136e6aa621c7f10ed47",
        })
        {
            Assert.Contains(sourceSha, record, StringComparison.Ordinal);
        }

        Assert.Contains("ad393a5c5c74174a2a8f8989d0bf03263c20e42d", record, StringComparison.Ordinal);
        Assert.Contains("additive-2026-09-19.v2", record, StringComparison.Ordinal);
        Assert.Contains("not an authenticated production", record, StringComparison.Ordinal);
        Assert.Contains("does not authorize deploying", record, StringComparison.Ordinal);
    }
}
