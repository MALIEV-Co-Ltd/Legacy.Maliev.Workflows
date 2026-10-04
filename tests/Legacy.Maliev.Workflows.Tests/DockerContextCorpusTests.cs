using System.Diagnostics;
using System.Formats.Tar;
using System.Security.Cryptography;
using System.Text;
using Xunit;

namespace Legacy.Maliev.Workflows.Tests;

// Controlled Docker-engine corpus, not consumer application/locked-restore acceptance.
[Collection("Docker context corpus")]
public sealed class DockerContextCorpusTests
{
    private const string Lock = "build/nuget-locks/Legacy.Maliev.ServiceDefaults/packages.lock.json";
    private static readonly string[] Required =
    [
        "wwwroot/dist/app.min.js.gz", "wwwroot/vendor/jquery.min.js.gz", Lock,
        "build/nuget-locks/Legacy.Maliev.CompatibilityContracts/packages.lock.json",
        ".dependencies/Maliev.Aspire/source.cs",
        ".dependencies/Maliev.MessagingContracts/source.cs",
        ".dependencies/Legacy.Maliev.ServiceDefaults/source.cs",
        ".dependencies/Legacy.Maliev.CompatibilityContracts/source.cs",
    ];

    private static readonly string[] Forbidden =
    [
        ".git/metadata.txt", ".worktrees/other/source.cs", ".codex/cache.txt", "node_modules/cache.js",
        "bin/output.dll", "obj/cache.txt", "TestResults/result.txt", "logs/run.log", "archive/item.backup",
        "build/cache/output.bin", ".github/workflows/private.yml", ".vscode/launch.json", ".vs/state.txt",
        ".idea/workspace.xml", ".codex-staging-fixture/cache.txt", ".superpowers/cache.txt", ".agents/cache.txt",
        ".qwen/cache.txt", "packages/cache.txt", "coverage/report.txt", "__pycache__/cache.pyc", "archive/item.bak",
        ".dependencies/Maliev.Aspire/.git/metadata.txt", ".dependencies/Maliev.Aspire/obj/cache.txt",
    ];

    // Test fixture policy only: actual owner rules must be independently supplied/adopted.
    private const string ControlledPolicy = "**/.git\n**/.github\n**/.vscode\n**/.vs\n**/.idea\n" +
        "**/.worktrees\n**/.codex\n**/.codex-staging-*\n**/.superpowers\n**/.agents\n**/.qwen\n**/node_modules\n" +
        "**/bin\n**/obj\n**/packages\n**/TestResults\n**/coverage\n**/__pycache__\n**/*.py[cod]\n" +
        "**/*.log\n**/*.backup\n**/*.bak\n**/build/*\n!**/build/nuget-locks\n!**/build/nuget-locks/**\n";

    [Fact]
    public async Task ControlledRoot_ExcludesMetadataButRetainsActualCopyInputs()
    {
        await WithContext(ControlledPolicy, async context =>
        {
            Dictionary<string, long> files = await ExportActualCopy(context);
            foreach (string path in Required)
            {
                Assert.True(files.TryGetValue("context/" + path, out long size) && size > 0, path);
                Assert.Equal(0, (await ExplicitCopy(context, path)).ExitCode);
            }

            foreach (string path in Forbidden)
            {
                Assert.False(files.ContainsKey("context/" + path), path);
            }
        });
    }

    [Theory]
    [InlineData("**/dist", "wwwroot/dist/app.min.js.gz")]
    [InlineData("**/vendor", "wwwroot/vendor/jquery.min.js.gz")]
    [InlineData("**/build", Lock)]
    [InlineData(".dependencies", ".dependencies/Maliev.Aspire/source.cs")]
    public async Task OverbroadRule_IsDetectedByExportAndExplicitDockerCopy(string rule, string input)
    {
        await WithContext(ControlledPolicy + rule + "\n", async context =>
        {
            Dictionary<string, long> files = await ExportActualCopy(context);
            Assert.False(files.ContainsKey("context/" + input));
            Assert.NotEqual(0, (await ExplicitCopy(context, input)).ExitCode);
        });
    }

    [Theory]
    [InlineData("15077df15879488b2010808bf38f94a2e91f3bf5", "wwwroot/dist/app.min.js.gz")]
    [InlineData("6268fb47c8a3ebdb9e9fe3935d16b47f93e9bb32", Lock)]
    public async Task OriginalSourceRules_HaveAnActualRequiredInputCompatibilityHazard(string sha, string input)
    {
        await WithContext(SourcePolicy(sha), async context =>
        {
            Dictionary<string, long> files = await ExportActualCopy(context);
            Assert.False(files.ContainsKey("context/" + input));
            Assert.NotEqual(0, (await ExplicitCopy(context, input)).ExitCode);
        });
    }

    [Fact]
    public async Task SecondSource_RetainsDistVendorAndDependencySourcesWithoutMakingBuildLocksSafe()
    {
        await WithContext(SourcePolicy("6268fb47c8a3ebdb9e9fe3935d16b47f93e9bb32"), async context =>
        {
            Dictionary<string, long> files = await ExportActualCopy(context);
            foreach (string input in Required.Where(path => !path.StartsWith("build/", StringComparison.Ordinal)))
            {
                Assert.True(files.TryGetValue("context/" + input, out long size) && size > 0, input);
            }

            Assert.False(files.ContainsKey("context/" + Lock));
        });
    }

    private static string SourcePolicy(string sha)
    {
        string expected = sha switch
        {
            "15077df15879488b2010808bf38f94a2e91f3bf5" => "086BC334C86323D6D5D690939521CC07B4AC8E9A1BE2EDFBE39B20CA35C63200",
            "6268fb47c8a3ebdb9e9fe3935d16b47f93e9bb32" => "A5F5031411855D206F65B31E1403D3BC33352C13BA29D2764F7EB412E5217D47",
            _ => throw new ArgumentOutOfRangeException(nameof(sha)),
        };
        byte[] bytes = File.ReadAllBytes(Path.Combine(RepositoryContractTests.FindRepositoryRoot(),
            "tests", "fixtures", "docker-context", sha + ".dockerignore"));
        Assert.Equal(expected, Convert.ToHexString(SHA256.HashData(bytes)));
        return Encoding.UTF8.GetString(bytes);
    }

    private static async Task WithContext(string policy, Func<string, Task> assertion)
    {
        string directory = Path.Combine(Path.GetTempPath(), "workflows-context-corpus-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(directory);
        try
        {
            foreach (string relative in Required.Concat(Forbidden))
            {
                string path = Path.Combine(directory, relative);
                Directory.CreateDirectory(Path.GetDirectoryName(path)!);
                await File.WriteAllTextAsync(path, "synthetic-context-sentinel", TestContext.Current.CancellationToken);
            }

            await File.WriteAllTextAsync(Path.Combine(directory, ".dockerignore"), policy, TestContext.Current.CancellationToken);
            await assertion(directory);
        }
        finally
        {
            string full = Path.GetFullPath(directory);
            Assert.StartsWith(Path.GetFullPath(Path.GetTempPath()), full, StringComparison.OrdinalIgnoreCase);
            Assert.StartsWith("workflows-context-corpus-", Path.GetFileName(full), StringComparison.Ordinal);
            Directory.Delete(full, recursive: true);
        }
    }

    private static async Task<Dictionary<string, long>> ExportActualCopy(string context)
    {
        string image = "legacy-workflows-context-test:" + Guid.NewGuid().ToString("N");
        string container = "legacy-context-corpus-" + Guid.NewGuid().ToString("N");
        bool buildAttempted = false;
        bool createAttempted = false;
        try
        {
            await File.WriteAllTextAsync(Path.Combine(context, "Dockerfile"),
                "FROM scratch\nCOPY . /context/\nENTRYPOINT [\"/must-never-start\"]\n", TestContext.Current.CancellationToken);
            buildAttempted = true;
            ProcessResult build = await Docker(["build", "--network", "none", "--quiet", "--tag", image, context]);
            Assert.True(build.ExitCode == 0, "Owned scratch context build failed.");
            createAttempted = true;
            ProcessResult create = await Docker(["create", "--name", container, "--network", "none", "--read-only",
                "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true", image]);
            Assert.Equal(0, create.ExitCode);
            ProcessResult export = await Docker(["export", container]);
            Assert.Equal(0, export.ExitCode);
            Assert.InRange(export.Output.Length, 1, 16 * 1024 * 1024);
            using MemoryStream stream = new(export.Output);
            using TarReader tar = new(stream);
            Dictionary<string, long> files = new(StringComparer.Ordinal);
            while (tar.GetNextEntry(copyData: false) is { } entry)
            {
                if (entry.EntryType is not (TarEntryType.RegularFile or TarEntryType.V7RegularFile))
                {
                    continue;
                }

                string name = entry.Name.TrimStart('/');
                while (name.StartsWith("./", StringComparison.Ordinal))
                {
                    name = name[2..];
                }

                Assert.True(files.TryAdd(name, entry.Length), "Duplicate exported fixture path.");
            }

            return files;
        }
        finally
        {
            try
            {
                if (createAttempted)
                {
                    await RemoveOwnedResource("container", container);
                }
            }
            finally
            {
                if (buildAttempted)
                {
                    await RemoveOwnedResource("image", image);
                }
            }
        }
    }

    private static async Task<ProcessResult> ExplicitCopy(string context, string input)
    {
        string image = "legacy-workflows-context-test:" + Guid.NewGuid().ToString("N");
        await File.WriteAllTextAsync(Path.Combine(context, "Dockerfile"),
            $"FROM scratch\nCOPY [\"{input}\", \"/required-input\"]\nENTRYPOINT [\"/must-never-start\"]\n",
            TestContext.Current.CancellationToken);
        try
        {
            return await Docker(["build", "--network", "none", "--quiet", "--tag", image, context]);
        }
        finally
        {
            await RemoveOwnedResource("image", image);
        }
    }

    private static async Task RemoveOwnedResource(string kind, string name)
    {
        Assert.True((kind == "image" && name.StartsWith("legacy-workflows-context-test:", StringComparison.Ordinal)) ||
            (kind == "container" && name.StartsWith("legacy-context-corpus-", StringComparison.Ordinal)));
        ProcessResult inspect = await Docker([kind, "inspect", name]);
        if (inspect.ExitCode == 0)
        {
            Assert.Equal(0, (await Docker([kind, "rm", "--force", name])).ExitCode);
            inspect = await Docker([kind, "inspect", name]);
        }

        Assert.NotEqual(0, inspect.ExitCode);
        Assert.Contains("No such " + kind, inspect.Error, StringComparison.OrdinalIgnoreCase);
    }

    private static async Task<ProcessResult> Docker(string[] arguments)
    {
        ProcessStartInfo start = new("docker")
        {
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        foreach (string argument in arguments)
        {
            start.ArgumentList.Add(argument);
        }

        using Process process = Process.Start(start) ?? throw new InvalidOperationException("Owned Docker child did not start.");
        using MemoryStream output = new();
        Task copy = CopyBounded(process.StandardOutput.BaseStream, output);
        Task<string> error = process.StandardError.ReadToEndAsync(TestContext.Current.CancellationToken);
        try
        {
            await process.WaitForExitAsync(TestContext.Current.CancellationToken).WaitAsync(TimeSpan.FromMinutes(1), TestContext.Current.CancellationToken);
            await copy;
            return new ProcessResult(process.ExitCode, output.ToArray(), await error);
        }
        finally
        {
            if (!process.HasExited)
            {
                process.Kill(entireProcessTree: true);
                await process.WaitForExitAsync(CancellationToken.None).WaitAsync(TimeSpan.FromSeconds(10));
            }
        }
    }

    private static async Task CopyBounded(Stream input, MemoryStream output)
    {
        byte[] buffer = new byte[16384];
        while (true)
        {
            int count = await input.ReadAsync(buffer, TestContext.Current.CancellationToken);
            if (count == 0)
            {
                break;
            }

            if (output.Length + count > 16 * 1024 * 1024)
            {
                throw new InvalidDataException("Owned fixture output exceeded its bound.");
            }

            output.Write(buffer, 0, count);
        }
    }

    private sealed record ProcessResult(int ExitCode, byte[] Output, string Error);
}

[CollectionDefinition("Docker context corpus", DisableParallelization = true)]
public sealed class DockerContextCorpusCollection
{
}
