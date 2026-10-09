using System.Diagnostics;
using System.Text.Json;
using Legacy.Maliev.AdditiveBenchmark;
using Xunit;

namespace Legacy.Maliev.Workflows.Tests;

public sealed class PrivateCorpusInventoryCliTests
{
    [Theory]
    [InlineData(48, null, 0)]
    [InlineData(2, "2", 0)]
    [InlineData(1, "2", 2)]
    [InlineData(0, "1", 2)]
    public async Task EntryPoint_WritesExactAnonymousHelperOutputAndOriginalExitCode(int count, string? limit, int expected)
    {
        using Fixture files = new();
        for (int index = 0; index < count; index++)
        {
            File.WriteAllText(Path.Combine(files.Root, $"synthetic-secret-{index}.stl"), $"synthetic unique model {index}");
        }
        if (count > 0)
        {
            File.Copy(Path.Combine(files.Root, "synthetic-secret-0.stl"), Path.Combine(files.Root, "duplicate.obj"));
        }
        string[] args = files.Arguments();
        if (limit is not null)
        {
            args = [.. args, "--limit", limit];
        }
        var result = await Cli(args);
        Assert.Equal(expected, result.Code);
        Assert.Empty(result.Error);
        Assert.Equal($"Anonymous private corpus inventory: {count} unique entries.{Environment.NewLine}", result.Output);
        Assert.Equal(PrivateCorpusInventory.Create(files.Root, limit is null ? 48 : int.Parse(limit, System.Globalization.CultureInfo.InvariantCulture), "synthetic-consent").Json, File.ReadAllText(files.Output));
        byte[] bytes = File.ReadAllBytes(files.Output);
        Assert.False(bytes.Length >= 3 && bytes[0] == 0xef && bytes[1] == 0xbb && bytes[2] == 0xbf);
        string json = File.ReadAllText(files.Output);
        Assert.DoesNotContain(files.DirectoryPath, json, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("synthetic-secret", json, StringComparison.Ordinal);
        using JsonDocument document = JsonDocument.Parse(json);
        Assert.Equal(count, document.RootElement.GetProperty("entryCount").GetInt32());
        Assert.Equal("synthetic-consent", document.RootElement.GetProperty("consentId").GetString());
        Assert.All(document.RootElement.GetProperty("entries").EnumerateArray(), entry =>
        {
            Assert.Equal("unreviewed", entry.GetProperty("geometryFamily").GetString());
            Assert.Equal("matched_reference_missing", entry.GetProperty("availability").GetString());
        });
        files.AssertNoTemporaryOutput();
    }

    [Theory]
    [InlineData("missing-root")]
    [InlineData("missing-output")]
    [InlineData("missing-consent")]
    [InlineData("dangling")]
    [InlineData("unknown")]
    [InlineData("duplicate")]
    [InlineData("blank")]
    [InlineData("limit-text")]
    [InlineData("limit-zero")]
    [InlineData("limit-too-large")]
    [InlineData("root-absent")]
    [InlineData("consent-control")]
    public async Task EntryPoint_InvalidOrDeniedArgumentsReturnOneWithoutOutputOrPrivateDiagnostics(string mutation)
    {
        using Fixture files = new();
        List<string> args = [.. files.Arguments()];
        switch (mutation)
        {
            case "missing-root": args.RemoveRange(1, 2); break;
            case "missing-output": args.RemoveRange(3, 2); break;
            case "missing-consent": args.RemoveRange(5, 2); break;
            case "dangling": args.Add("--limit"); break;
            case "unknown": args.AddRange(["--unknown", "private-value"]); break;
            case "duplicate": args.AddRange(["--root", files.Root]); break;
            case "blank": args[6] = " "; break;
            case "limit-text": args.AddRange(["--limit", "private-value"]); break;
            case "limit-zero": args.AddRange(["--limit", "0"]); break;
            case "limit-too-large": args.AddRange(["--limit", "129"]); break;
            case "root-absent": args[2] = Path.Combine(files.DirectoryPath, "private-missing"); break;
            case "consent-control": args[6] = "private-value\n"; break;
        }
        var result = await Cli([.. args]);
        Assert.Equal(1, result.Code);
        Assert.Empty(result.Output);
        Assert.NotEmpty(result.Error);
        Assert.DoesNotContain(files.DirectoryPath, result.Error, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("private-value", result.Error, StringComparison.Ordinal);
        Assert.DoesNotContain("private-missing", result.Error, StringComparison.Ordinal);
        Assert.False(File.Exists(files.Output));
        files.AssertNoTemporaryOutput();
    }

    [Theory]
    [InlineData(false)]
    [InlineData(true)]
    public async Task EntryPoint_OutputConflictPreservesExistingFileAndRemovesOwnedTemporary(bool useInput)
    {
        using Fixture files = new();
        string destination = useInput ? Path.Combine(files.Root, "synthetic-secret.stl") : files.Output;
        File.WriteAllText(destination, "preserved synthetic bytes");
        string[] args = files.Arguments();
        args[4] = destination;
        var result = await Cli([.. args, "--limit", "1"]);
        Assert.Equal(1, result.Code);
        Assert.Empty(result.Output);
        Assert.Equal("preserved synthetic bytes", File.ReadAllText(destination));
        Assert.DoesNotContain(destination, result.Error, StringComparison.OrdinalIgnoreCase);
        files.AssertNoTemporaryOutput();
    }

    [Fact]
    public async Task EntryPoint_CannotCreateOutputUnderARegularFile()
    {
        using Fixture files = new();
        string parent = Path.Combine(files.DirectoryPath, "parent-file");
        File.WriteAllText(parent, "preserved synthetic parent");
        string[] args = files.Arguments();
        args[4] = Path.Combine(parent, "output.json");
        var result = await Cli(args);
        Assert.Equal(1, result.Code);
        Assert.Empty(result.Output);
        Assert.Equal("preserved synthetic parent", File.ReadAllText(parent));
        Assert.DoesNotContain(files.DirectoryPath, result.Error, StringComparison.OrdinalIgnoreCase);
        files.AssertNoTemporaryOutput();
    }

    private static async Task<(int Code, string Output, string Error)> Cli(string[] arguments)
    {
        string root = RepositoryContractTests.FindRepositoryRoot();
        ProcessStartInfo start = new("dotnet")
        {
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        start.ArgumentList.Add(Path.Combine(root, "tools/additive-benchmark/bin/Release/net10.0/Legacy.Maliev.AdditiveBenchmark.dll"));
        foreach (string argument in arguments)
        {
            start.ArgumentList.Add(argument);
        }
        using Process process = new() { StartInfo = start };
        using CancellationTokenSource budget = CancellationTokenSource.CreateLinkedTokenSource(TestContext.Current.CancellationToken);
        budget.CancelAfter(TimeSpan.FromSeconds(20));
        Task<string>? output = null;
        Task<string>? error = null;
        bool started = false;
        try
        {
            Assert.True(process.Start());
            started = true;
            output = process.StandardOutput.ReadToEndAsync();
            error = process.StandardError.ReadToEndAsync();
            await process.WaitForExitAsync(budget.Token);
            await Task.WhenAll(output, error).WaitAsync(budget.Token);
            Assert.InRange(output.Result.Length + error.Result.Length, 0, 8192);
            return (process.ExitCode, output.Result, error.Result);
        }
        finally
        {
            if (started)
            {
                using CancellationTokenSource cleanup = new(TimeSpan.FromSeconds(5));
                if (!process.HasExited)
                {
                    process.Kill();
                }
                await process.WaitForExitAsync(cleanup.Token);
                if (output is not null && error is not null)
                {
                    await Task.WhenAll(output, error).WaitAsync(cleanup.Token);
                }
                Assert.True(process.HasExited);
            }
        }
    }

    private sealed class Fixture : IDisposable
    {
        public string DirectoryPath { get; } = Path.Combine(Path.GetTempPath(), "legacy-inventory-cli-" + Guid.NewGuid().ToString("N"));
        public string Root => Path.Combine(DirectoryPath, "synthetic-input");
        public string Output => Path.Combine(DirectoryPath, "output.json");

        public Fixture() => Directory.CreateDirectory(Root);

        public string[] Arguments() => ["inventory-corpus", "--root", Root, "--output", Output, "--consent-id", "synthetic-consent"];

        public void AssertNoTemporaryOutput() => Assert.Empty(Directory.EnumerateFiles(DirectoryPath, ".legacy-inventory-*.tmp", SearchOption.AllDirectories));

        public void Dispose()
        {
            string full = Path.GetFullPath(DirectoryPath);
            string parent = Path.GetFullPath(Path.GetTempPath());
            Assert.Equal(Path.TrimEndingDirectorySeparator(parent), Path.GetDirectoryName(full), OperatingSystem.IsWindows() ? StringComparer.OrdinalIgnoreCase : StringComparer.Ordinal);
            Directory.Delete(full, recursive: true);
            Assert.False(Directory.Exists(full));
        }
    }
}
