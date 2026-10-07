using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Legacy.Maliev.AdditiveBenchmark;

/// <summary>Materializes preset inheritance from a bounded snapshot of caller-supplied roots.</summary>
public static class BambuStudioProfileResolver
{
    /// <summary>Maximum number of JSON files admitted across all roots.</summary>
    public const int MaximumFiles = 256;
    /// <summary>Maximum aggregate bytes admitted across all JSON files.</summary>
    public const int MaximumTotalBytes = 16 * 1024 * 1024;
    /// <summary>Maximum directory nesting and profile dependency nesting.</summary>
    public const int MaximumDepth = 32;
    /// <summary>Maximum profile resolutions, including repeated dependency occurrences.</summary>
    public const int MaximumResolutionSteps = 1024;

    /// <summary>Resolves base, included presets, then leaf settings; dependency names are ordinal.</summary>
    public static ResolvedBambuProfile Resolve(string profilePath, IReadOnlyCollection<string> searchRoots)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(profilePath);
        ArgumentNullException.ThrowIfNull(searchRoots);
        string leaf = Path.GetFullPath(profilePath);
        RejectLink(leaf);
        Dictionary<string, CapturedPreset> byName = new(StringComparer.Ordinal);
        StringComparer pathComparer = OperatingSystem.IsWindows() ? StringComparer.OrdinalIgnoreCase : StringComparer.Ordinal;
        Dictionary<string, CapturedPreset?> captured = new(pathComparer);
        int totalBytes = 0;
        int directories = 0;
        HashSet<string> visitedDirectories = new(pathComparer);
        int admittedEntries = 0;
        if (searchRoots.Count > 32)
        {
            throw new InvalidDataException("Preset search root admission limit exceeded.");
        }

        List<string> roots = searchRoots.Append(Path.GetDirectoryName(leaf)!).Select(path => Path.TrimEndingDirectorySeparator(Path.GetFullPath(path))).Distinct(pathComparer).Order(pathComparer).ToList();
        Capture(leaf);
        foreach (string root in roots)
        {
            if (!Directory.Exists(root))
            {
                throw new InvalidDataException("A preset search root is unavailable.");
            }

            Walk(root, 0);
        }

        if (!captured.TryGetValue(leaf, out CapturedPreset? leafPreset) || leafPreset is null)
        {
            throw new InvalidDataException("Leaf preset must be an admitted named JSON object.");
        }

        List<string> sourceNames = [];
        HashSet<string> resolving = new(StringComparer.Ordinal);
        int resolutionSteps = 0;
        long resolutionInputBytes = 0;
        int mergedNodes = 0;
        long mergedBytes = 0;
        JsonObject settings = ResolvePreset(leafPreset, 0);
        settings.Remove("include");
        foreach (string field in new[] { "type", "name", "from" })
        {
            if (ReadString(settings, field) is not string value || string.IsNullOrWhiteSpace(value))
            {
                throw new InvalidDataException("Resolved preset requires type, name and from metadata.");
            }
        }

        string json = settings.ToJsonString(new JsonSerializerOptions { WriteIndented = true }).Replace("\r\n", "\n", StringComparison.Ordinal);
        return new ResolvedBambuProfile(settings, sourceNames.ToArray(),
            Convert.ToHexString(SHA256.HashData(leafPreset.Bytes)), Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(json))), json + "\n");

        void Walk(string directory, int depth)
        {
            RejectLink(directory);
            if (!visitedDirectories.Add(directory))
            {
                return;
            }

            if (depth > MaximumDepth || ++directories > 1024)
            {
                throw new InvalidDataException("Preset directory admission limit exceeded.");
            }

            List<string> entries = [];
            foreach (string entry in Directory.EnumerateFileSystemEntries(directory))
            {
                if (++admittedEntries > 4096)
                {
                    throw new InvalidDataException("Preset entry admission limit exceeded.");
                }

                entries.Add(entry);
            }

            entries.Sort(pathComparer);
            foreach (string entry in entries)
            {
                RejectLink(entry);
                if (Directory.Exists(entry))
                {
                    Walk(entry, depth + 1);
                }
                else if (string.Equals(Path.GetExtension(entry), ".json", StringComparison.OrdinalIgnoreCase))
                {
                    Capture(Path.GetFullPath(entry));
                }
            }
        }

        void Capture(string path)
        {
            if (captured.ContainsKey(path))
            {
                return;
            }

            if (captured.Count >= MaximumFiles)
            {
                throw new InvalidDataException("Preset file admission limit exceeded.");
            }

            byte[] bytes = BoundedJson.Read(path);
            totalBytes = checked(totalBytes + bytes.Length);
            if (totalBytes > MaximumTotalBytes)
            {
                throw new InvalidDataException("Preset aggregate byte admission limit exceeded.");
            }

            JsonObject? profile = null;
            try
            {
                using JsonDocument document = BoundedJson.Parse(bytes);
                if (document.RootElement.ValueKind == JsonValueKind.Object)
                {
                    profile = JsonNode.Parse(document.RootElement.GetRawText())!.AsObject();
                }
            }
            catch (JsonException)
            {
                throw new InvalidDataException("Preset root contains malformed or duplicate-key JSON.");
            }

            string? name = profile is null ? null : ReadString(profile, "name");
            CapturedPreset? preset = string.IsNullOrWhiteSpace(name) ? null : new CapturedPreset(bytes, profile!, name);
            captured.Add(path, preset);
            if (preset is null)
            {
                return;
            }

            if (byName.TryGetValue(preset.Name, out CapturedPreset? previous))
            {
                if (!previous.Bytes.AsSpan().SequenceEqual(bytes))
                {
                    throw new InvalidDataException("Preset name is ambiguous across supplied roots.");
                }
            }
            else
            {
                byName.Add(preset.Name, preset);
            }
        }

        JsonObject ResolvePreset(CapturedPreset preset, int depth)
        {
            resolutionInputBytes += preset.Bytes.Length;
            if (++resolutionSteps > MaximumResolutionSteps || resolutionInputBytes > 32 * 1024 * 1024)
            {
                throw new InvalidDataException("Preset resolution work admission limit exceeded.");
            }

            if (depth > MaximumDepth || !resolving.Add(preset.Name))
            {
                throw new InvalidDataException("Preset inheritance contains a cycle or exceeds its depth limit.");
            }

            try
            {
                JsonObject resolved = new();
                if (preset.Profile.TryGetPropertyValue("inherits", out JsonNode? inherits))
                {
                    if (inherits is not JsonValue value || !value.TryGetValue(out string? name))
                    {
                        throw new InvalidDataException("Preset inherits must be a string when present.");
                    }

                    if (!string.IsNullOrWhiteSpace(name))
                    {
                        Merge(resolved, ResolveNamed(name, depth + 1));
                    }
                }

                if (preset.Profile.TryGetPropertyValue("include", out JsonNode? includes))
                {
                    if (includes is not JsonArray array)
                    {
                        throw new InvalidDataException("Preset include must be an array of non-empty names.");
                    }

                    foreach (JsonNode? include in array)
                    {
                        if (include is not JsonValue value || !value.TryGetValue(out string? name) || string.IsNullOrWhiteSpace(name))
                        {
                            throw new InvalidDataException("Preset include must contain non-empty names.");
                        }

                        Merge(resolved, ResolveNamed(name, depth + 1));
                    }
                }

                Merge(resolved, preset.Profile);
                resolved.Remove("include");
                sourceNames.Add(preset.Name);
                return resolved;
            }
            finally
            {
                resolving.Remove(preset.Name);
            }
        }

        JsonObject ResolveNamed(string name, int depth)
        {
            if (!byName.TryGetValue(name, out CapturedPreset? preset))
            {
                throw new InvalidDataException("Preset dependency was not found in the supplied snapshot.");
            }

            return ResolvePreset(preset, depth);
        }

        void Merge(JsonObject target, JsonObject source)
        {
            AdmitMergeWork(source);
            foreach ((string key, JsonNode? value) in source)
            {
                target[key] = value?.DeepClone();
            }
        }

        void AdmitMergeWork(JsonNode? node)
        {
            if (++mergedNodes > 65536 || mergedBytes > 32 * 1024 * 1024)
            {
                throw new InvalidDataException("Preset merge work admission limit exceeded.");
            }

            if (node is JsonObject valueObject)
            {
                foreach ((string key, JsonNode? child) in valueObject)
                {
                    mergedBytes += Encoding.UTF8.GetByteCount(key);
                    AdmitMergeWork(child);
                }
            }
            else if (node is JsonArray array)
            {
                foreach (JsonNode? child in array)
                {
                    AdmitMergeWork(child);
                }
            }
            else if (node is JsonValue value)
            {
                mergedBytes += value.TryGetValue(out string? text) && text is not null
                    ? Encoding.UTF8.GetByteCount(text) : Encoding.UTF8.GetByteCount(value.ToJsonString());
            }
            else
            {
                mergedBytes += 4;
            }

            if (mergedBytes > 32 * 1024 * 1024)
            {
                throw new InvalidDataException("Preset merge work admission limit exceeded.");
            }
        }
    }

    private static void RejectLink(string path)
    {
        _ = File.GetAttributes(path);
        RejectLinkedAncestors(path);
    }

    internal static void RejectLinkedAncestors(string path)
    {
        for (string? component = Path.GetFullPath(path); component is not null; component = Path.GetDirectoryName(Path.TrimEndingDirectorySeparator(component)))
        {
            FileAttributes attributes;
            try
            {
                attributes = File.GetAttributes(component);
            }
            catch (Exception exception) when (exception is FileNotFoundException or DirectoryNotFoundException)
            {
                continue;
            }

            if ((attributes & FileAttributes.ReparsePoint) != 0)
            {
                throw new InvalidDataException("Preset admission rejects symbolic links and reparse points.");
            }
        }
    }

    private static string? ReadString(JsonObject profile, string name) =>
        profile[name] is JsonValue value && value.TryGetValue(out string? text) ? text : null;

    private sealed record CapturedPreset(byte[] Bytes, JsonObject Profile, string Name);
}

/// <summary>Resolved preset settings and uppercase source/resolved SHA-256 digests.</summary>
/// <param name="Settings">Merged settings.</param>
/// <param name="SourceProfileNames">Names merged in precedence order.</param>
/// <param name="SourceSha256">Digest of captured leaf bytes.</param>
/// <param name="Sha256">Digest of canonical JSON before its final LF.</param>
/// <param name="Json">Resolved settings JSON with a final LF.</param>
public sealed record ResolvedBambuProfile(JsonObject Settings, IReadOnlyList<string> SourceProfileNames, string SourceSha256, string Sha256, string Json);
