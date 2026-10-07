using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Legacy.Maliev.AdditiveBenchmark;
using Xunit;

namespace Legacy.Maliev.Workflows.Tests;

public sealed class PrivateCorpusInventoryTests
{
    [Fact]
    public void SyntheticCorpus_PreservesOriginalAnonymousDeduplicatedContract()
    {
        InSyntheticRoot(root =>
        {
            File.WriteAllText(Path.Combine(root, "synthetic-secret.stl"), "solid one");
            File.WriteAllText(Path.Combine(root, "synthetic-duplicate.stl"), "solid one");
            File.WriteAllText(Path.Combine(root, "synthetic-project.3mf"), "project two");
            PrivateCorpusInventoryResult first = PrivateCorpusInventory.Create(root, 2, "synthetic-consent");
            PrivateCorpusInventoryResult second = PrivateCorpusInventory.Create(root, 2, "synthetic-consent");
            Assert.Equal(first, second);
            Assert.Equal(2, first.EntryCount);
            Assert.DoesNotContain(root, first.Json, StringComparison.OrdinalIgnoreCase);
            Assert.DoesNotContain("synthetic-secret", first.Json, StringComparison.OrdinalIgnoreCase);
            Assert.DoesNotContain("synthetic-duplicate", first.Json, StringComparison.OrdinalIgnoreCase);
            using JsonDocument document = JsonDocument.Parse(first.Json);
            JsonElement value = document.RootElement;
            Assert.Equal("private-corpus.v1", value.GetProperty("schemaVersion").GetString());
            Assert.Equal("2026-09-20.1", value.GetProperty("corpusVersion").GetString());
            Assert.Equal("synthetic-consent", value.GetProperty("consentId").GetString());
            Assert.Equal("restricted-read-only", value.GetProperty("availability").GetString());
            Assert.Equal("sha256-sorted; exact-byte duplicates removed; release holdout frozen before tuning", value.GetProperty("selectionPolicy").GetString());
            string[] digests = value.GetProperty("entries").EnumerateArray().Select(entry => entry.GetProperty("sha256").GetString()!).ToArray();
            Assert.Equal(digests.Order(StringComparer.Ordinal), digests);
            Assert.All(value.GetProperty("entries").EnumerateArray(), entry =>
            {
                Assert.Equal("unreviewed", entry.GetProperty("geometryFamily").GetString());
                Assert.Equal("matched_reference_missing", entry.GetProperty("availability").GetString());
                Assert.False(entry.TryGetProperty("path", out _));
                Assert.False(entry.TryGetProperty("fileName", out _));
            });
            Assert.Equal("private-001", value.GetProperty("entries")[0].GetProperty("id").GetString());
            Assert.Equal("release-holdout", value.GetProperty("entries")[0].GetProperty("split").GetString());
            Assert.Equal("development", value.GetProperty("entries")[1].GetProperty("split").GetString());
        });
    }

    [Fact]
    public void Synthetic48EntryFixture_PreservesFrozenHoldoutShapeWithoutHistoricalPayload()
    {
        InSyntheticRoot(root =>
        {
            for (int index = 0; index < 48; index++)
            {
                File.WriteAllText(Path.Combine(root, index + ".stl"), "synthetic model " + index);
            }
            PrivateCorpusInventoryResult result = PrivateCorpusInventory.Create(root, 48, "synthetic-consent");
            using JsonDocument document = JsonDocument.Parse(result.Json);
            JsonElement[] entries = document.RootElement.GetProperty("entries").EnumerateArray().ToArray();
            Assert.Equal(48, result.EntryCount);
            Assert.Equal(48, entries.Select(entry => entry.GetProperty("sha256").GetString()).Distinct().Count());
            Assert.Equal(12, entries.Count(entry => entry.GetProperty("split").GetString() == "release-holdout"));
        });
    }

    [Theory]
    [InlineData("STL", ".stl")]
    [InlineData("OBJ", ".obj")]
    [InlineData("3MF", ".3mf")]
    public void SupportedExtension_ReportsExactCapturedBytesAndDigest(string extension, string expected)
    {
        InSyntheticRoot(root =>
        {
            byte[] bytes = Encoding.UTF8.GetBytes("synthetic model");
            File.WriteAllBytes(Path.Combine(root, "fixture." + extension), bytes);
            using JsonDocument document = JsonDocument.Parse(PrivateCorpusInventory.Create(root, 1, "synthetic-consent").Json);
            JsonElement entry = document.RootElement.GetProperty("entries")[0];
            Assert.Equal(expected, entry.GetProperty("format").GetString());
            Assert.Equal((long)bytes.Length, entry.GetProperty("bytes").GetInt64());
            Assert.Equal(Convert.ToHexString(SHA256.HashData(bytes)), entry.GetProperty("sha256").GetString());
            Assert.Equal("small", entry.GetProperty("byteSizeBucket").GetString());
        });
    }

    [Fact]
    public void EmptyOrUnsupportedCorpus_RemainsEmptyMetadata()
    {
        InSyntheticRoot(root =>
        {
            File.WriteAllText(Path.Combine(root, "fixture.txt"), "synthetic unsupported");
            PrivateCorpusInventoryResult result = PrivateCorpusInventory.Create(root, 1, "synthetic-consent");
            Assert.Equal(0, result.EntryCount);
            using JsonDocument document = JsonDocument.Parse(result.Json);
            Assert.Equal(0, document.RootElement.GetProperty("entries").GetArrayLength());
        });
    }

    [Fact]
    public void ExactByteDuplicatesAcrossFormatsAndNestedPaths_SelectOneEntry()
    {
        InSyntheticRoot(root =>
        {
            Directory.CreateDirectory(Path.Combine(root, "nested"));
            File.WriteAllText(Path.Combine(root, "first.stl"), "same bytes");
            File.WriteAllText(Path.Combine(root, "nested/second.obj"), "same bytes");
            Assert.Equal(1, PrivateCorpusInventory.Create(root, 2, "synthetic-consent").EntryCount);
        });
    }

    [Theory]
    [InlineData(-1)]
    [InlineData(0)]
    [InlineData(129)]
    public void InvalidSelectionLimit_RejectsBeforeCorpusObservation(int limit)
    {
        Assert.Throws<ArgumentOutOfRangeException>(() => PrivateCorpusInventory.Create("missing-synthetic-root", limit, "synthetic-consent"));
    }

    [Theory]
    [InlineData(128, true)]
    [InlineData(129, false)]
    public void MetadataIdentifier_UsesUtf8ByteLimit(int characters, bool accepted)
    {
        InSyntheticRoot(root =>
        {
            string identifier = new('é', characters);
            if (accepted)
            {
                Assert.Equal(0, PrivateCorpusInventory.Create(root, 1, identifier).EntryCount);
            }
            else
            {
                Assert.Throws<InvalidDataException>(() => PrivateCorpusInventory.Create(root, 1, identifier));
            }
        });
    }

    [Theory]
    [InlineData("synthetic\nidentifier")]
    [InlineData("synthetic\0identifier")]
    public void UnsafeMetadataIdentifier_IsRefused(string identifier)
    {
        Assert.Throws<InvalidDataException>(() => PrivateCorpusInventory.Create("missing-synthetic-root", 1, identifier));
    }

    [Fact]
    public void MalformedUnicodeMetadataIdentifier_IsRefused()
    {
        Assert.Throws<InvalidDataException>(() => PrivateCorpusInventory.Create("missing-synthetic-root", 1, new string('\ud800', 1)));
    }

    [Fact]
    public void ExactCandidateAndSelectionBounds_RetainOriginalSelectionLimit()
    {
        InSyntheticRoot(root =>
        {
            for (int index = 0; index < 256; index++)
            {
                File.WriteAllText(Path.Combine(root, index + ".stl"), "synthetic " + index);
            }
            Assert.Equal(128, PrivateCorpusInventory.Create(root, 128, "synthetic-consent").EntryCount);
        });
    }

    [Fact]
    public void CandidateCountOverflow_RefusesWholeSnapshotRatherThanTruncating()
    {
        InSyntheticRoot(root =>
        {
            for (int index = 0; index < 257; index++)
            {
                File.WriteAllText(Path.Combine(root, index + ".stl"), "synthetic");
            }
            Assert.Throws<InvalidDataException>(() => PrivateCorpusInventory.Create(root, 1, "synthetic-consent"));
        });
    }

    [Fact]
    public void DirectoryBreadthOverflow_RefusesWholeSnapshot()
    {
        InSyntheticRoot(root =>
        {
            for (int index = 0; index < 128; index++)
            {
                Directory.CreateDirectory(Path.Combine(root, index.ToString()));
            }
            Assert.Throws<InvalidDataException>(() => PrivateCorpusInventory.Create(root, 1, "synthetic-consent"));
        });
    }

    [Fact]
    public void DirectoryDepthOverflow_RefusesWholeSnapshot()
    {
        InSyntheticRoot(root =>
        {
            string child = root;
            for (int index = 0; index < 17; index++)
            {
                child = Path.Combine(child, "n");
                Directory.CreateDirectory(child);
            }
            Assert.Throws<InvalidDataException>(() => PrivateCorpusInventory.Create(root, 1, "synthetic-consent"));
        });
    }

    [Fact]
    public void EntryOverflow_RejectsUnsupportedFileFlood()
    {
        InSyntheticRoot(root =>
        {
            for (int index = 0; index < 4097; index++)
            {
                File.WriteAllText(Path.Combine(root, index + ".txt"), string.Empty);
            }
            Assert.Throws<InvalidDataException>(() => PrivateCorpusInventory.Create(root, 1, "synthetic-consent"));
        });
    }

    [Fact]
    public void OutputIsCanonicalLfAndRetainsZeroByteDeduplication()
    {
        InSyntheticRoot(root =>
        {
            File.WriteAllBytes(Path.Combine(root, "zero.stl"), []);
            File.WriteAllBytes(Path.Combine(root, "same.obj"), []);
            PrivateCorpusInventoryResult result = PrivateCorpusInventory.Create(root, 128, "synthetic-consent");
            Assert.Equal(1, result.EntryCount);
            Assert.EndsWith("\n", result.Json);
            Assert.DoesNotContain("\r", result.Json, StringComparison.Ordinal);
        });
    }

    [Fact]
    public void OversizedFile_IsRefusedBeforeHashing()
    {
        InSyntheticRoot(root =>
        {
            using (FileStream file = File.Create(Path.Combine(root, "synthetic.stl")))
            {
                file.SetLength(256L * 1024 * 1024 + 1);
            }
            Assert.Throws<InvalidDataException>(() => PrivateCorpusInventory.Create(root, 1, "synthetic-consent"));
        });
    }

    [Fact]
    public void ActualHashWorkOverflow_IsRefusedAcrossDuplicateCandidates()
    {
        InSyntheticRoot(root =>
        {
            for (int index = 0; index < 3; index++)
            {
                using FileStream file = File.Create(Path.Combine(root, index + ".stl"));
                file.SetLength(180L * 1024 * 1024);
            }
            Assert.Throws<InvalidDataException>(() => PrivateCorpusInventory.Create(root, 2, "synthetic-consent"));
        });
    }

    [Fact]
    public void OriginalFourSizeBuckets_RemainSelectableWithGeneratedFiles()
    {
        InSyntheticRoot(root =>
        {
            long[] lengths = [0, 1_000_001, 10_000_001, 100_000_001];
            for (int index = 0; index < lengths.Length; index++)
            {
                using FileStream file = File.Create(Path.Combine(root, index + ".stl"));
                file.SetLength(lengths[index]);
            }
            PrivateCorpusInventoryResult result = PrivateCorpusInventory.Create(root, 4, "synthetic-consent");
            using JsonDocument document = JsonDocument.Parse(result.Json);
            string[] buckets = document.RootElement.GetProperty("entries").EnumerateArray()
                .Select(entry => entry.GetProperty("byteSizeBucket").GetString()!).Order(StringComparer.Ordinal).ToArray();
            Assert.Equal(new[] { "large", "medium", "small", "very-large" }, buckets);
        });
    }

    [Theory]
    [InlineData("root")]
    [InlineData("ancestor")]
    [InlineData("entry")]
    public async Task LinkedCorpus_IsRefusedWithoutChangingOutsideFixture(string kind)
    {
        string root = Path.Combine(Path.GetTempPath(), "workflows-synthetic-link-" + Guid.NewGuid().ToString("N"));
        string outside = Path.Combine(Path.GetTempPath(), "workflows-synthetic-outside-" + Guid.NewGuid().ToString("N"));
        string link = Path.Combine(root, "link");
        try
        {
            Directory.CreateDirectory(root);
            Directory.CreateDirectory(Path.Combine(outside, "nested"));
            string fixture = Path.Combine(outside, "nested", "synthetic.stl");
            File.WriteAllText(fixture, "synthetic outside fixture");
            if (OperatingSystem.IsWindows())
            {
                ProcessStartInfo start = new("cmd.exe") { RedirectStandardOutput = true, RedirectStandardError = true, UseShellExecute = false, CreateNoWindow = true };
                foreach (string argument in new[] { "/d", "/c", "mklink", "/J", link, outside })
                {
                    start.ArgumentList.Add(argument);
                }
                using Process process = new() { StartInfo = start };
                using CancellationTokenSource budget = CancellationTokenSource.CreateLinkedTokenSource(TestContext.Current.CancellationToken);
                budget.CancelAfter(TimeSpan.FromSeconds(10));
                Assert.True(process.Start());
                try
                {
                    Task output = DrainBounded(process.StandardOutput.BaseStream, budget);
                    Task error = DrainBounded(process.StandardError.BaseStream, budget);
                    await Task.WhenAll(output, error, process.WaitForExitAsync(budget.Token));
                    Assert.Equal(0, process.ExitCode);
                }
                finally
                {
                    if (!process.HasExited)
                    {
                        process.Kill();
                        using CancellationTokenSource cleanup = new(TimeSpan.FromSeconds(5));
                        await process.WaitForExitAsync(cleanup.Token);
                    }
                }
            }
            else
            {
                Directory.CreateSymbolicLink(link, outside);
            }
            string requested = kind == "root" ? link : kind == "ancestor" ? Path.Combine(link, "nested") : root;
            Assert.Throws<InvalidDataException>(() => PrivateCorpusInventory.Create(requested, 1, "synthetic-consent"));
            Assert.Equal("synthetic outside fixture", File.ReadAllText(fixture));
        }
        finally
        {
            if (Directory.Exists(link))
            {
                Directory.Delete(link);
            }
            foreach (string ownedRoot in new[] { root, outside })
            {
                if (Directory.Exists(ownedRoot))
                {
                    Directory.Delete(ownedRoot, true);
                }
                Assert.False(Directory.Exists(ownedRoot));
            }
        }
    }

    private static async Task DrainBounded(Stream stream, CancellationTokenSource budget)
    {
        byte[] buffer = new byte[1024];
        int total = 0;
        try
        {
            int read;
            while ((read = await stream.ReadAsync(buffer.AsMemory(), budget.Token)) != 0)
            {
                total += read;
                if (total > 4096)
                {
                    throw new InvalidDataException("Synthetic junction helper output exceeded admission limit.");
                }
            }
        }
        catch
        {
            budget.Cancel();
            throw;
        }
    }

    private static void InSyntheticRoot(Action<string> action)
    {
        string root = Path.Combine(Path.GetTempPath(), "workflows-synthetic-corpus-" + Guid.NewGuid().ToString("N"));
        try
        {
            Directory.CreateDirectory(root);
            action(root);
        }
        finally
        {
            if (Directory.Exists(root))
            {
                Directory.Delete(root, true);
            }
            Assert.False(Directory.Exists(root));
        }
    }
}
