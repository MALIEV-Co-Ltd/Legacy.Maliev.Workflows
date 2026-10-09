using System.Text;

namespace Legacy.Maliev.AdditiveBenchmark;

/// <summary>Validates manifest metadata and writes a deterministic report.</summary>
public static class AdditiveBenchmarkCli
{
    /// <summary>Returns zero for ready, two for blocked, and one for invalid or file admission failure.</summary>
    public static int Run(string[] args)
    {
        if (args.Length > 0 && args[0] == "resolve-profile")
        {
            return RunProfile(args[1..]);
        }

        if (args.Length > 0 && args[0] == "inventory-corpus")
        {
            return RunInventoryCorpus(args[1..]);
        }

        Dictionary<string, string> paths = new(StringComparer.Ordinal);
        if (args.Length != 6)
        {
            return Usage();
        }

        for (int index = 0; index < args.Length; index += 2)
        {
            if (args[index] is not ("--manifest" or "--schema" or "--report")
                || string.IsNullOrWhiteSpace(args[index + 1])
                || !paths.TryAdd(args[index], args[index + 1]))
            {
                return Usage();
            }
        }

        try
        {
            string manifest = Path.GetFullPath(paths["--manifest"]);
            string schema = Path.GetFullPath(paths["--schema"]);
            string report = Path.GetFullPath(paths["--report"]);
            StringComparison comparison = OperatingSystem.IsWindows() ? StringComparison.OrdinalIgnoreCase : StringComparison.Ordinal;
            if (string.Equals(report, manifest, comparison) || string.Equals(report, schema, comparison))
            {
                Console.Error.WriteLine("Report path must differ from input paths.");
                return 1;
            }

            BenchmarkRunResult result = AdditiveBenchmarkRunner.Run(manifest, schema);
            Directory.CreateDirectory(Path.GetDirectoryName(report)!);
            File.WriteAllText(report, result.ReportJson, new UTF8Encoding(false));
            Console.WriteLine($"Additive benchmark manifest status: {result.Status}");
            return result.ExitCode;
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or ArgumentException or NotSupportedException)
        {
            Console.Error.WriteLine("Unable to admit benchmark inputs or write the report.");
            return 1;
        }
    }

    private static int RunInventoryCorpus(string[] args)
    {
        Dictionary<string, string> options = new(StringComparer.Ordinal);
        for (int index = 0; index < args.Length; index += 2)
        {
            if (index + 1 >= args.Length
                || args[index] is not ("--root" or "--output" or "--consent-id" or "--limit")
                || string.IsNullOrWhiteSpace(args[index + 1])
                || !options.TryAdd(args[index], args[index + 1]))
            {
                return InventoryUsage();
            }
        }

        int limit = 48;
        if (!options.TryGetValue("--root", out string? root)
            || !options.TryGetValue("--output", out string? output)
            || !options.TryGetValue("--consent-id", out string? consentId)
            || (options.TryGetValue("--limit", out string? value)
                && !int.TryParse(value, System.Globalization.NumberStyles.Integer, System.Globalization.CultureInfo.InvariantCulture, out limit)))
        {
            return InventoryUsage();
        }

        string? temporary = null;
        bool ownsTemporary = false;
        try
        {
            PrivateCorpusInventoryResult inventory = PrivateCorpusInventory.Create(root, limit, consentId);
            string destination = Path.GetFullPath(output);
            string directory = Path.GetDirectoryName(destination)!;
            BambuStudioProfileResolver.RejectLinkedAncestors(directory);
            Directory.CreateDirectory(directory);
            BambuStudioProfileResolver.RejectLinkedAncestors(directory);
            temporary = Path.Combine(directory, ".legacy-inventory-" + Guid.NewGuid().ToString("N") + ".tmp");
            using (FileStream file = new(temporary, FileMode.CreateNew, FileAccess.Write))
            {
                ownsTemporary = true;
                using StreamWriter writer = new(file, new UTF8Encoding(false));
                writer.Write(inventory.Json);
            }
            File.Move(temporary, destination, overwrite: false);
            ownsTemporary = false;
            Console.WriteLine($"Anonymous private corpus inventory: {inventory.EntryCount} unique entries.");
            return inventory.EntryCount == limit ? 0 : 2;
        }
        catch (Exception exception) when (exception is IOException or InvalidDataException or UnauthorizedAccessException or ArgumentException or NotSupportedException)
        {
            Console.Error.WriteLine("Unable to admit corpus inputs or create anonymous inventory output.");
            return 1;
        }
        finally
        {
            if (ownsTemporary)
            {
                try
                {
                    File.Delete(temporary!);
                }
                catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
                {
                    Console.Error.WriteLine("Unable to remove owned temporary inventory output.");
                }
            }
        }
    }

    private static int InventoryUsage()
    {
        Console.Error.WriteLine("Usage: Legacy.Maliev.AdditiveBenchmark inventory-corpus --root <directory> --output <new-path> --consent-id <id> [--limit <count>]");
        return 1;
    }

    private static int RunProfile(string[] args)
    {
        string? leaf = null;
        string? output = null;
        List<string> roots = [];
        for (int index = 0; index < args.Length; index += 2)
        {
            if (index + 1 >= args.Length || string.IsNullOrWhiteSpace(args[index + 1]))
            {
                return ProfileUsage();
            }

            switch (args[index])
            {
                case "--profile" when leaf is null: leaf = args[index + 1]; break;
                case "--output" when output is null: output = args[index + 1]; break;
                case "--search-root" when roots.Count < 32: roots.Add(args[index + 1]); break;
                default: return ProfileUsage();
            }
        }

        if (leaf is null || output is null || roots.Count == 0)
        {
            return ProfileUsage();
        }

        string? temporary = null;
        bool ownsTemporary = false;
        try
        {
            ResolvedBambuProfile profile = BambuStudioProfileResolver.Resolve(leaf, roots);
            string destination = Path.GetFullPath(output);
            string directory = Path.GetDirectoryName(destination)!;
            BambuStudioProfileResolver.RejectLinkedAncestors(directory);
            Directory.CreateDirectory(directory);
            BambuStudioProfileResolver.RejectLinkedAncestors(directory);
            temporary = Path.Combine(directory, ".legacy-profile-" + Guid.NewGuid().ToString("N") + ".tmp");
            using (FileStream file = new(temporary, FileMode.CreateNew, FileAccess.Write))
            {
                ownsTemporary = true;
                using StreamWriter writer = new(file, new UTF8Encoding(false));
                writer.Write(profile.Json);
            }
            File.Move(temporary, destination, overwrite: false);
            ownsTemporary = false;
            Console.WriteLine($"Resolved Bambu Studio profile; sha256: {profile.Sha256}");
            return 0;
        }
        catch (Exception exception) when (exception is IOException or InvalidDataException or UnauthorizedAccessException or ArgumentException or NotSupportedException)
        {
            Console.Error.WriteLine("Unable to admit preset snapshot or create resolved output.");
            return 1;
        }
        finally
        {
            if (ownsTemporary)
            {
                try
                {
                    File.Delete(temporary!);
                }
                catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
                {
                    Console.Error.WriteLine("Unable to remove owned temporary preset output.");
                }
            }
        }
    }

    private static int ProfileUsage()
    {
        Console.Error.WriteLine("Usage: Legacy.Maliev.AdditiveBenchmark resolve-profile --profile <path> --search-root <directory> [--search-root <directory>] --output <new-path>");
        return 1;
    }

    private static int Usage()
    {
        Console.Error.WriteLine("Usage: Legacy.Maliev.AdditiveBenchmark --manifest <path> --schema <path> --report <path>");
        return 1;
    }
}
