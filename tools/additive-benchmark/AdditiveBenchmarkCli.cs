using System.Text;

namespace Legacy.Maliev.AdditiveBenchmark;

/// <summary>Validates manifest metadata and writes a deterministic report.</summary>
public static class AdditiveBenchmarkCli
{
    /// <summary>Returns zero for ready, two for blocked, and one for invalid or file admission failure.</summary>
    public static int Run(string[] args)
    {
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

    private static int Usage()
    {
        Console.Error.WriteLine("Usage: Legacy.Maliev.AdditiveBenchmark --manifest <path> --schema <path> --report <path>");
        return 1;
    }
}
