using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Legacy.Maliev.AdditiveBenchmark;

/// <summary>Creates a deterministic anonymous inventory of a restricted CAD corpus.</summary>
public static class PrivateCorpusInventory
{
    private const int MaximumCandidates = 256;
    private const int MaximumEntries = 4096;
    private const int MaximumDirectories = 128;
    private const int MaximumDepth = 16;
    private const long MaximumFileBytes = 256L * 1024 * 1024;
    private const long MaximumHashedBytes = 512L * 1024 * 1024;
    private static readonly System.Text.UTF8Encoding StrictUtf8 = new(false, true);

    private static readonly HashSet<string> SupportedExtensions = new(StringComparer.OrdinalIgnoreCase)
    {
        ".stl",
        ".obj",
        ".3mf",
    };

    private static readonly JsonSerializerOptions SerializerOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        WriteIndented = true,
        DefaultIgnoreCondition = JsonIgnoreCondition.Never,
    };

    /// <summary>Hashes and selects unique restricted models without emitting paths or names.</summary>
    public static PrivateCorpusInventoryResult Create(string root, int limit, string consentId)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(root);
        ArgumentException.ThrowIfNullOrWhiteSpace(consentId);
        if (limit is < 1 or > 128)
        {
            throw new ArgumentOutOfRangeException(nameof(limit));
        }

        try
        {
            if (StrictUtf8.GetByteCount(consentId) > 256 || consentId.Any(char.IsControl))
            {
                throw new InvalidDataException("Corpus metadata identifier is outside admission limits.");
            }
        }
        catch (System.Text.EncoderFallbackException)
        {
            throw new InvalidDataException("Corpus metadata identifier is outside admission limits.");
        }

        string fullRoot = Path.GetFullPath(root);
        if (!Directory.Exists(fullRoot))
        {
            throw new DirectoryNotFoundException("The restricted corpus root is unavailable.");
        }

        BambuStudioProfileResolver.RejectLinkedAncestors(fullRoot);
        FileCandidate[] candidates = CaptureCandidates(fullRoot)
            .OrderBy(file => file.Bucket, StringComparer.Ordinal)
            .ThenBy(file => file.Bytes)
            .ThenBy(file => file.Path, StringComparer.OrdinalIgnoreCase)
            .ThenBy(file => file.Path, StringComparer.Ordinal)
            .ToArray();
        Dictionary<string, HashedCandidate> cache = new(StringComparer.Ordinal);
        long hashedBytes = 0;
        HashedCandidate CaptureHash(FileCandidate candidate)
        {
            if (cache.TryGetValue(candidate.Path, out HashedCandidate? captured))
            {
                return captured;
            }
            BambuStudioProfileResolver.RejectLinkedAncestors(candidate.Path);
            using FileStream stream = new(candidate.Path, FileMode.Open, FileAccess.Read, FileShare.Read);
            if (stream.Length != candidate.Bytes)
            {
                throw new InvalidDataException("Corpus file changed after metadata admission.");
            }
            using IncrementalHash hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
            byte[] buffer = new byte[4096];
            long actualBytes = 0;
            int read;
            while ((read = stream.Read(buffer, 0, buffer.Length)) != 0)
            {
                actualBytes += read;
                hashedBytes += read;
                if (actualBytes > candidate.Bytes || hashedBytes > MaximumHashedBytes)
                {
                    throw new InvalidDataException("Corpus hash work admission limit exceeded.");
                }
                hash.AppendData(buffer, 0, read);
            }
            if (actualBytes != candidate.Bytes)
            {
                throw new InvalidDataException("Corpus file changed after metadata admission.");
            }
            captured = new HashedCandidate(Convert.ToHexString(hash.GetHashAndReset()), actualBytes, candidate.Bucket, candidate.Extension);
            cache.Add(candidate.Path, captured);
            return captured;
        }
        var selected = new List<HashedCandidate>();
        var seen = new HashSet<string>(StringComparer.Ordinal);
        string[] buckets = ["small", "medium", "large", "very-large"];
        int targetPerBucket = Math.Max(1, (int)Math.Ceiling(limit / (double)buckets.Length));

        foreach (string bucket in buckets)
        {
            foreach (FileCandidate candidate in candidates.Where(item => item.Bucket == bucket))
            {
                HashedCandidate hashed = CaptureHash(candidate);
                if (!seen.Add(hashed.Sha256))
                {
                    continue;
                }

                selected.Add(hashed);
                if (selected.Count(item => item.Bucket == bucket) >= targetPerBucket || selected.Count == limit)
                {
                    break;
                }
            }

            if (selected.Count == limit)
            {
                break;
            }
        }

        if (selected.Count < limit)
        {
            foreach (FileCandidate candidate in candidates)
            {
                HashedCandidate hashed = CaptureHash(candidate);
                if (!seen.Add(hashed.Sha256))
                {
                    continue;
                }

                selected.Add(hashed);
                if (selected.Count == limit)
                {
                    break;
                }
            }
        }

        HashedCandidate[] ordered = selected
            .OrderBy(item => item.Sha256, StringComparer.Ordinal)
            .ToArray();
        int releaseCount = Math.Min(12, Math.Max(1, ordered.Length / 4));
        CorpusEntry[] entries = ordered.Select((item, index) => new CorpusEntry(
            $"private-{index + 1:D3}",
            item.Sha256,
            item.Bytes,
            item.Extension,
            item.Bucket,
            index < releaseCount ? "release-holdout" : "development",
            "unreviewed",
            "matched_reference_missing")).ToArray();
        var document = new CorpusDocument(
            "private-corpus.v1",
            "2026-09-20.1",
            consentId,
            "restricted-read-only",
            "sha256-sorted; exact-byte duplicates removed; release holdout frozen before tuning",
            entries.Length,
            entries);
        string json = JsonSerializer.Serialize(document, SerializerOptions).Replace("\r\n", "\n", StringComparison.Ordinal) + "\n";
        return new PrivateCorpusInventoryResult(json, entries.Length);
    }

    private static List<FileCandidate> CaptureCandidates(string root)
    {
        List<FileCandidate> candidates = [];
        Stack<(string Path, int Depth)> pending = new();
        pending.Push((root, 0));
        int directories = 0;
        int entries = 0;
        while (pending.TryPop(out var directory))
        {
            if (++directories > MaximumDirectories || directory.Depth > MaximumDepth)
            {
                throw new InvalidDataException("Corpus directory admission limit exceeded.");
            }
            BambuStudioProfileResolver.RejectLinkedAncestors(directory.Path);
            foreach (string path in Directory.EnumerateFileSystemEntries(directory.Path))
            {
                if (++entries > MaximumEntries)
                {
                    throw new InvalidDataException("Corpus entry admission limit exceeded.");
                }
                BambuStudioProfileResolver.RejectLinkedAncestors(path);
                FileAttributes attributes = File.GetAttributes(path);
                if ((attributes & FileAttributes.Directory) != 0)
                {
                    pending.Push((path, directory.Depth + 1));
                    if (pending.Count + directories > MaximumDirectories)
                    {
                        throw new InvalidDataException("Corpus directory admission limit exceeded.");
                    }
                    continue;
                }
                FileInfo file = new(path);
                if (!SupportedExtensions.Contains(file.Extension))
                {
                    continue;
                }
                if (candidates.Count == MaximumCandidates || file.Length > MaximumFileBytes)
                {
                    throw new InvalidDataException("Corpus file admission limit exceeded.");
                }
                candidates.Add(new FileCandidate(file.FullName, file.Length, Bucket(file.Length), file.Extension.ToLowerInvariant()));
            }
        }
        return candidates;
    }

    private static string Bucket(long bytes) => bytes switch
    {
        <= 1_000_000 => "small",
        <= 10_000_000 => "medium",
        <= 100_000_000 => "large",
        _ => "very-large",
    };

    private sealed record FileCandidate(string Path, long Bytes, string Bucket, string Extension);

    private sealed record HashedCandidate(string Sha256, long Bytes, string Bucket, string Extension);

    private sealed record CorpusDocument(
        string SchemaVersion,
        string CorpusVersion,
        string ConsentId,
        string Availability,
        string SelectionPolicy,
        int EntryCount,
        IReadOnlyList<CorpusEntry> Entries);

    private sealed record CorpusEntry(
        string Id,
        string Sha256,
        long Bytes,
        string Format,
        string ByteSizeBucket,
        string Split,
        string GeometryFamily,
        string Availability);
}

/// <summary>Serialized private-corpus inventory and selected unique-entry count.</summary>
public sealed record PrivateCorpusInventoryResult(string Json, int EntryCount);
