using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using Xunit;

namespace Legacy.Maliev.Workflows.Tests;

public sealed class HistoricalMeasurementReadbackArchiveTests
{
    private const string ArchivePath = "docs/source-migration/2026-07-26-measurement-readback.md";
    private const string BodyMarker = "## Privacy-filtered historical source body\n\n";

    [Fact]
    public void Readback_preserves_complete_reviewed_content_and_declared_privacy_omissions()
    {
        var archive = Read(ArchivePath);
        var offset = archive.IndexOf(BodyMarker, StringComparison.Ordinal);
        Assert.True(offset >= 0);
        Assert.Equal(offset, archive.LastIndexOf(BodyMarker, StringComparison.Ordinal));
        var prefix = archive[..(offset + BodyMarker.Length)];
        var body = archive[(offset + BodyMarker.Length)..];

        Assert.Equal("db0e251edbdf8955c6d9ef1caf7ce52a4b158d0412da30db47b5b3f76e67c22c", Hash(archive));
        Assert.Equal("a6a528a9962b01d044ed708001da5f859c689672155707bdcec89433a8c84e73", Hash(prefix));
        Assert.Equal("05a57edfc7481b888c2051b6d8ebf5d8af66567a55bb567b1c8809cfdb757e14", Hash(body));
        Assert.Contains("not byte-identical", prefix, StringComparison.Ordinal);
        Assert.Contains("must not be executed", prefix, StringComparison.Ordinal);
        Assert.Equal(1, Regex.Matches(body,
            Regex.Escape("[OMITTED: historical billing resource identifier]")).Count);
        Assert.Equal(1, Regex.Matches(body,
            Regex.Escape("[OMITTED: ambiguous billing/customer/card reference]")).Count);
        Assert.DoesNotMatch(@"billingAccounts/[A-Za-z0-9-]+", body);
        Assert.DoesNotMatch(@"\b\d{4}(?:-\d{4}){3}\b", body);
        Assert.DoesNotContain("-----BEGIN ", body, StringComparison.Ordinal);
    }

    [Fact]
    public void Introduction_has_complete_custody_of_its_other_changed_matrix_path()
    {
        var matrix = Read("docs/source-migration/2026-07-14-measurement-seo-completion-matrix.md");
        const string marker = "## Unchanged historical source body\n\n";
        var offset = matrix.IndexOf(marker, StringComparison.Ordinal);
        Assert.True(offset >= 0);
        Assert.Equal(offset, matrix.LastIndexOf(marker, StringComparison.Ordinal));
        var body = matrix[(offset + marker.Length)..];

        Assert.Equal("b4bee0b53b6cf5a8645bcbb2d4d92b1e8fdf274122ef9b83cbbca457cb313b06", Hash(body));
        Assert.Contains("./2026-07-26-measurement-readback.md", body, StringComparison.Ordinal);
        Assert.True(File.Exists(Path.Combine(
            RepositoryContractTests.FindRepositoryRoot(), ArchivePath)));
    }

    private static string Read(string path) =>
        File.ReadAllText(Path.Combine(RepositoryContractTests.FindRepositoryRoot(), path))
            .Replace("\r\n", "\n", StringComparison.Ordinal);

    private static string Hash(string text) =>
        Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(text)));
}
