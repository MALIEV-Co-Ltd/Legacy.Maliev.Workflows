using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Legacy.Maliev.AdditiveBenchmark;
using Xunit;

namespace Legacy.Maliev.Workflows.Tests;

public sealed class BambuStudioProfileResolverTests
{
    [Fact]
    public void Resolve_BaseIncludeLeaf_PreservesPrecedenceWireAndUppercaseHashes()
    {
        using Presets files = new();
        files.Write("base.json", "{\"name\":\"base\",\"type\":\"filament\",\"from\":\"synthetic\",\"density\":[\"1.02\"],\"speed\":[\"10\"]}");
        files.Write("include.json", "{\"name\":\"include\",\"speed\":[\"20\"],\"start\":\"G28\"}");
        string leaf = files.Write("leaf.json", "{\"name\":\"leaf\",\"inherits\":\"base\",\"include\":[\"include\"],\"speed\":[\"30\"]}");
        ResolvedBambuProfile result = BambuStudioProfileResolver.Resolve(leaf, [files.Path]);
        Assert.Equal(new[] { "base", "include", "leaf" }, result.SourceProfileNames);
        Assert.Equal("30", result.Settings["speed"]![0]!.GetValue<string>());
        Assert.Equal("1.02", result.Settings["density"]![0]!.GetValue<string>());
        Assert.Equal("G28", result.Settings["start"]!.GetValue<string>());
        Assert.Equal("base", result.Settings["inherits"]!.GetValue<string>());
        Assert.False(result.Settings.ContainsKey("include"));
        Assert.DoesNotContain('\r', result.Json);
        Assert.EndsWith("\n", result.Json);
        Assert.Equal(Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(leaf))), result.SourceSha256);
        Assert.Equal(Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(result.Json[..^1]))), result.Sha256);
        Assert.Matches("^[A-F0-9]{64}$", result.SourceSha256);
        Assert.Matches("^[A-F0-9]{64}$", result.Sha256);
        Assert.Equal(result.Json, BambuStudioProfileResolver.Resolve(leaf, [files.Path]).Json);
        using JsonDocument wire = JsonDocument.Parse(result.Json);
        Assert.False(wire.RootElement.TryGetProperty("settings", out _));
    }

    [Fact]
    public void Resolve_IdenticalDuplicateNamesAndRepeatedDependencies_RetainsSourceOrder()
    {
        using Presets files = new();
        const string basis = "{\"name\":\"base\",\"type\":\"process\",\"from\":\"synthetic\",\"height\":\"0.12\"}";
        files.Write("base-a.json", basis);
        files.Write("base-b.json", basis);
        string leaf = files.Write("leaf.preset", "{\"name\":\"leaf\",\"inherits\":\"base\",\"include\":[\"base\"]}");
        ResolvedBambuProfile result = BambuStudioProfileResolver.Resolve(leaf, [files.Path, files.Path + System.IO.Path.DirectorySeparatorChar]);
        Assert.Equal(new[] { "base", "base", "leaf" }, result.SourceProfileNames);
        Assert.Equal("0.12", result.Settings["height"]!.GetValue<string>());
    }

    [Theory]
    [InlineData("inherits-number")]
    [InlineData("inherits-null")]
    [InlineData("include-number")]
    [InlineData("include-member")]
    [InlineData("include-empty")]
    [InlineData("missing-parent")]
    [InlineData("cycle")]
    [InlineData("include-cycle")]
    [InlineData("cross-cycle")]
    [InlineData("ambiguous")]
    [InlineData("duplicate-key")]
    [InlineData("malformed-root")]
    [InlineData("missing-metadata")]
    [InlineData("leaf-array")]
    public void Resolve_InvalidSnapshotOrDependency_RejectsWithoutFallback(string mutation)
    {
        using Presets files = new();
        string leaf = files.Write("leaf.json", "{\"name\":\"leaf\",\"type\":\"process\",\"from\":\"synthetic\"}");
        switch (mutation)
        {
            case "inherits-number": files.Write("leaf.json", "{\"name\":\"leaf\",\"type\":\"process\",\"from\":\"synthetic\",\"inherits\":42}"); break;
            case "inherits-null": files.Write("leaf.json", "{\"name\":\"leaf\",\"type\":\"process\",\"from\":\"synthetic\",\"inherits\":null}"); break;
            case "include-number": files.Write("leaf.json", "{\"name\":\"leaf\",\"type\":\"process\",\"from\":\"synthetic\",\"include\":42}"); break;
            case "include-member": files.Write("leaf.json", "{\"name\":\"leaf\",\"type\":\"process\",\"from\":\"synthetic\",\"include\":[42]}"); break;
            case "include-empty": files.Write("leaf.json", "{\"name\":\"leaf\",\"type\":\"process\",\"from\":\"synthetic\",\"include\":[\"\"]}"); break;
            case "missing-parent": files.Write("leaf.json", "{\"name\":\"leaf\",\"type\":\"process\",\"from\":\"synthetic\",\"inherits\":\"missing\"}"); break;
            case "cycle": files.Write("leaf.json", "{\"name\":\"leaf\",\"type\":\"process\",\"from\":\"synthetic\",\"inherits\":\"leaf\"}"); break;
            case "include-cycle": files.Write("leaf.json", "{\"name\":\"leaf\",\"type\":\"process\",\"from\":\"synthetic\",\"include\":[\"leaf\"]}"); break;
            case "cross-cycle":
                files.Write("leaf.json", "{\"name\":\"leaf\",\"type\":\"process\",\"from\":\"synthetic\",\"inherits\":\"base\"}");
                files.Write("base.json", "{\"name\":\"base\",\"include\":[\"leaf\"]}");
                break;
            case "ambiguous": files.Write("other.json", "{\"name\":\"leaf\",\"type\":\"process\",\"from\":\"different\"}"); break;
            case "duplicate-key": files.Write("other.json", "{\"name\":\"other\",\"name\":\"ignored\"}"); break;
            case "malformed-root": files.Write("other.json", "{"); break;
            case "leaf-array": files.Write("leaf.json", "[]"); break;
            default: files.Write("leaf.json", "{\"name\":\"leaf\"}"); break;
        }

        Assert.Throws<InvalidDataException>(() => BambuStudioProfileResolver.Resolve(leaf, [files.Path]));
    }

    [Theory]
    [InlineData("file-count")]
    [InlineData("file-bytes")]
    [InlineData("aggregate-bytes")]
    [InlineData("dependency-depth")]
    [InlineData("directory-depth")]
    [InlineData("branching-expansion")]
    [InlineData("merge-work")]
    [InlineData("node-work")]
    [InlineData("directory-count")]
    [InlineData("entry-count")]
    [InlineData("root-count")]
    [InlineData("missing-root")]
    public void Resolve_AdmissionLimitsAndUnavailableRoots_Reject(string limit)
    {
        using Presets files = new();
        string leaf = files.Write("leaf.json", "{\"name\":\"leaf\",\"type\":\"process\",\"from\":\"synthetic\"}");
        List<string> roots = [files.Path];
        switch (limit)
        {
            case "file-count":
                for (int index = 0; index < BambuStudioProfileResolver.MaximumFiles; index++)
                {
                    files.Write($"unnamed-{index}.json", "{}");
                }
                break;
            case "file-bytes": File.WriteAllBytes(leaf, new byte[4 * 1024 * 1024 + 1]); break;
            case "aggregate-bytes":
                for (int index = 0; index < 5; index++)
                {
                    files.Write($"large-{index}.json", "{\"padding\":\"" + new string('a', 4 * 1024 * 1024 - 100) + "\"}");
                }
                break;
            case "dependency-depth":
                files.Write("leaf.json", "{\"name\":\"leaf\",\"type\":\"process\",\"from\":\"synthetic\",\"inherits\":\"dep0\"}");
                for (int index = 0; index <= BambuStudioProfileResolver.MaximumDepth + 1; index++)
                {
                    files.Write($"dep{index}.json", $"{{\"name\":\"dep{index}\",\"inherits\":\"dep{index + 1}\"}}");
                }
                break;
            case "directory-depth":
                string directory = files.Path;
                for (int index = 0; index <= BambuStudioProfileResolver.MaximumDepth; index++)
                {
                    directory = System.IO.Path.Combine(directory, "nested");
                    Directory.CreateDirectory(directory);
                }
                break;
            case "branching-expansion":
                WriteFanout(files);
                break;
            case "merge-work":
            case "node-work":
                WriteMergeExpansion(files, limit == "node-work");
                break;
            case "root-count": roots.AddRange(Enumerable.Repeat(files.Path, 32)); break;
            case "directory-count":
                for (int index = 0; index < 1024; index++)
                {
                    Directory.CreateDirectory(System.IO.Path.Combine(files.Path, $"dir-{index}"));
                }
                break;
            case "entry-count":
                for (int index = 0; index < 4096; index++)
                {
                    files.Write($"note-{index}.txt", string.Empty);
                }
                break;
            case "missing-root": roots.Add(System.IO.Path.Combine(files.Path, "absent")); break;
        }

        Exception exception = limit == "file-bytes"
            ? Assert.Throws<IOException>(() => BambuStudioProfileResolver.Resolve(leaf, roots))
            : Assert.Throws<InvalidDataException>(() => BambuStudioProfileResolver.Resolve(leaf, roots));
        if (limit == "dependency-depth")
        {
            Assert.Contains("depth", exception.Message);
        }
        if (limit == "branching-expansion")
        {
            Assert.Contains("work", exception.Message);
        }
        if (limit is "merge-work" or "node-work")
        {
            Assert.Contains("merge work", exception.Message);
        }
    }

    [Theory]
    [InlineData("success")]
    [InlineData("duplicate-flag")]
    [InlineData("missing-input")]
    [InlineData("existing-output")]
    [InlineData("bad-inherits")]
    [InlineData("branching")]
    [InlineData("merge-expansion")]
    [InlineData("destination-directory")]
    public async Task ActualCli_ProfileResolution_UsesNewOutputAndRedactedErrors(string scenario)
    {
        using Presets files = new();
        string leaf = files.Write("leaf.json", "{\"name\":\"leaf\",\"type\":\"process\",\"from\":\"synthetic\"}");
        string output = System.IO.Path.Combine(files.Path, "out", "resolved.json");
        string[] arguments = ["resolve-profile", "--profile", leaf, "--search-root", files.Path, "--output", output];
        switch (scenario)
        {
            case "duplicate-flag": arguments[3] = "--profile"; break;
            case "missing-input": arguments[2] = System.IO.Path.Combine(files.Path, "sensitive-customer-name.json"); break;
            case "existing-output": output = leaf; arguments[6] = leaf; break;
            case "bad-inherits": files.Write("leaf.json", "{\"name\":\"leaf\",\"type\":\"process\",\"from\":\"synthetic\",\"inherits\":42}"); break;
            case "branching": WriteFanout(files); break;
            case "merge-expansion": WriteMergeExpansion(files, false); break;
            case "destination-directory": Directory.CreateDirectory(output); break;
        }

        string original = File.ReadAllText(leaf);
        string? expected = scenario == "success" ? BambuStudioProfileResolver.Resolve(leaf, [files.Path]).Json : null;
        (int code, string stdout, string error) = await Cli(arguments);
        if (scenario == "success")
        {
            Assert.Equal(0, code);
            Assert.Empty(error);
            Assert.Equal(expected, File.ReadAllText(output));
            Assert.Contains("Resolved Bambu Studio profile; sha256:", stdout);
        }
        else
        {
            Assert.Equal(1, code);
            Assert.Empty(stdout);
            Assert.DoesNotContain(files.Path, error);
            Assert.DoesNotContain("sensitive-customer-name", error);
            if (output != leaf)
            {
                Assert.False(File.Exists(output));
            }
        }

        Assert.Equal(original, File.ReadAllText(leaf));
        Assert.Empty(Directory.EnumerateFiles(files.Path, ".legacy-profile-*.tmp", SearchOption.AllDirectories));
    }

    [Theory]
    [InlineData("entry")]
    [InlineData("root")]
    [InlineData("ancestor")]
    [InlineData("output")]
    public async Task Resolve_RealDirectoryLinkOrLinkedAncestor_RejectsEscape(string kind)
    {
        using Presets outside = new();
        using Presets files = new();
        using Presets? linkHolder = kind == "output" ? new Presets() : null;
        Directory.CreateDirectory(System.IO.Path.Combine(outside.Path, "sub"));
        string outsideLeaf = System.IO.Path.Combine(outside.Path, "sub", "leaf.json");
        File.WriteAllText(outsideLeaf, "{\"name\":\"outside\",\"type\":\"process\",\"from\":\"synthetic\"}");
        string leaf = files.Write("leaf.json", "{\"name\":\"leaf\",\"type\":\"process\",\"from\":\"synthetic\"}");
        string link = System.IO.Path.Combine(linkHolder?.Path ?? files.Path, "link");
        if (OperatingSystem.IsWindows())
        {
            ProcessStartInfo start = new("cmd.exe") { RedirectStandardOutput = true, RedirectStandardError = true, UseShellExecute = false, CreateNoWindow = true };
            foreach (string argument in new[] { "/c", "mklink", "/J", link, outside.Path })
            {
                start.ArgumentList.Add(argument);
            }
            using Process process = new() { StartInfo = start };
            using CancellationTokenSource budget = CancellationTokenSource.CreateLinkedTokenSource(TestContext.Current.CancellationToken);
            budget.CancelAfter(TimeSpan.FromSeconds(10));
            Assert.True(process.Start());
            try
            {
                Task<string> stdout = process.StandardOutput.ReadToEndAsync(budget.Token);
                Task<string> stderr = process.StandardError.ReadToEndAsync(budget.Token);
                await process.WaitForExitAsync(budget.Token);
                Assert.True(process.ExitCode == 0, await stdout + await stderr);
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
            Directory.CreateSymbolicLink(link, outside.Path);
        }

        try
        {
            if (kind == "output")
            {
                string destination = System.IO.Path.Combine(link, "sub", "new.json");
                (int code, string stdout, string error) = await Cli(["resolve-profile", "--profile", leaf, "--search-root", files.Path, "--output", destination]);
                Assert.Equal(1, code);
                Assert.Empty(stdout);
                Assert.DoesNotContain(files.Path, error);
                Assert.False(File.Exists(System.IO.Path.Combine(outside.Path, "sub", "new.json")));
            }
            else
            {
                string requestedLeaf = kind == "ancestor" ? System.IO.Path.Combine(link, "sub", "leaf.json") : leaf;
                string root = kind == "root" ? link : files.Path;
                Assert.Throws<InvalidDataException>(() => BambuStudioProfileResolver.Resolve(requestedLeaf, [root]));
            }
            Assert.True(File.Exists(outsideLeaf));
        }
        finally
        {
            Directory.Delete(link);
            Assert.False(Directory.Exists(link));
        }
    }

    [Fact]
    public void Resolve_RelativePathsAndEmptyInherits_UsesCallerDirectoryWithoutLosingHashCase()
    {
        using Presets files = new(Directory.GetParent(RepositoryContractTests.FindRepositoryRoot())!.FullName);
        string leaf = files.Write("leaf.json", "{\"name\":\"leaf\",\"type\":\"process\",\"from\":\"synthetic\",\"inherits\":\"\"}");
        string relativeLeaf = System.IO.Path.GetRelativePath(Environment.CurrentDirectory, leaf);
        string relativeRoot = System.IO.Path.GetRelativePath(Environment.CurrentDirectory, files.Path);
        Assert.False(System.IO.Path.IsPathRooted(relativeLeaf));
        Assert.False(System.IO.Path.IsPathRooted(relativeRoot));
        ResolvedBambuProfile relative = BambuStudioProfileResolver.Resolve(relativeLeaf, [relativeRoot]);
        Assert.Equal(BambuStudioProfileResolver.Resolve(leaf, [files.Path]).Json, relative.Json);
        Assert.Equal(new[] { "leaf" }, relative.SourceProfileNames);
    }

    private static void WriteFanout(Presets files)
    {
        files.Write("leaf.json", "{\"name\":\"leaf\",\"type\":\"process\",\"from\":\"synthetic\",\"inherits\":\"dep0\"}");
        for (int index = 0; index < 13; index++)
        {
            files.Write($"dep{index}.json", $"{{\"name\":\"dep{index}\",\"include\":[\"dep{index + 1}\",\"dep{index + 1}\"]}}");
        }
        files.Write("dep13.json", "{\"name\":\"dep13\"}");
    }

    private static void WriteMergeExpansion(Presets files, bool nodes)
    {
        string payload = nodes ? "[" + string.Join(',', Enumerable.Repeat("1", 20000)) + "]" : "\"" + new string('a', 3 * 1024 * 1024) + "\"";
        files.Write("base.json", "{\"name\":\"base\",\"type\":\"process\",\"from\":\"synthetic\",\"padding\":" + payload + "}");
        files.Write("leaf.json", "{\"name\":\"leaf\",\"inherits\":\"base\",\"include\":[\"base\",\"base\",\"base\",\"base\",\"base\",\"base\",\"base\"]}");
    }

    private static async Task<(int Code, string Output, string Error)> Cli(string[] arguments)
    {
        string root = RepositoryContractTests.FindRepositoryRoot();
        ProcessStartInfo start = new("dotnet") { RedirectStandardOutput = true, RedirectStandardError = true, UseShellExecute = false, CreateNoWindow = true };
        start.ArgumentList.Add(System.IO.Path.Combine(root, "tools/additive-benchmark/bin/Release/net10.0/Legacy.Maliev.AdditiveBenchmark.dll"));
        foreach (string argument in arguments)
        {
            start.ArgumentList.Add(argument);
        }

        using Process process = new() { StartInfo = start };
        using CancellationTokenSource budget = CancellationTokenSource.CreateLinkedTokenSource(TestContext.Current.CancellationToken);
        budget.CancelAfter(TimeSpan.FromSeconds(20));
        Assert.True(process.Start());
        try
        {
            Task<string> stdout = process.StandardOutput.ReadToEndAsync(budget.Token);
            Task<string> error = process.StandardError.ReadToEndAsync(budget.Token);
            await process.WaitForExitAsync(budget.Token);
            return (process.ExitCode, await stdout, await error);
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

    private sealed class Presets : IDisposable
    {
        public string Path { get; }
        public Presets(string? parent = null)
        {
            Path = System.IO.Path.Combine(parent ?? System.IO.Path.GetTempPath(), "legacy-preset-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(Path);
        }
        public string Write(string name, string json)
        {
            string target = System.IO.Path.Combine(Path, name);
            File.WriteAllText(target, json);
            return target;
        }
        public void Dispose()
        {
            Directory.Delete(Path, true);
            Assert.False(Directory.Exists(Path));
        }
    }
}
