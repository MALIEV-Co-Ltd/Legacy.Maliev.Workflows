using System.Diagnostics;
using System.Formats.Tar;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Xunit;

namespace Legacy.Maliev.Workflows.Tests;

// Draft future adapter tests. No consumer Docker build, dependency checkout or locked restore proof.
public sealed class AccountingContextExportContractTests
{
    private const string Profile = "accounting-host-dependencies-v1";
    private const string CallerRef = "ff8fcf61684566b150fe06d88f2ee0c41bc6a33f";
    private static readonly string[] Required =
    [
        "nuget.config",
        "Legacy.Maliev.AccountingService.Api/Legacy.Maliev.AccountingService.Api.csproj",
        "Legacy.Maliev.AccountingService.Application/Legacy.Maliev.AccountingService.Application.csproj",
        "Legacy.Maliev.AccountingService.Domain/Legacy.Maliev.AccountingService.Domain.csproj",
        "Legacy.Maliev.AccountingService.Data/Legacy.Maliev.AccountingService.Data.csproj",
        ".dependencies/Legacy.Maliev.ServiceDefaults/src/Legacy.Maliev.ServiceDefaults/Legacy.Maliev.ServiceDefaults.csproj",
        ".dependencies/Legacy.Maliev.CompatibilityContracts/src/Legacy.Maliev.CompatibilityContracts/Legacy.Maliev.CompatibilityContracts.csproj",
    ];

    public static TheoryData<string> MissingSources
    {
        get
        {
            TheoryData<string> cases = [];
            foreach (string path in Required)
            {
                cases.Add(path);
            }

            return cases;
        }
    }

    [Fact]
    public async Task CompleteAccountingSourcesWithoutWebAssets_AcceptsOnlyExportScope()
    {
        ProcessResult result = await Probe(Required.Select(path => ("context/" + path, "source-sentinel")));
        Assert.Equal(0, result.ExitCode);
        using JsonDocument receipt = JsonDocument.Parse(result.Output);
        Assert.Equal("accepted", receipt.RootElement.GetProperty("status").GetString());
        Assert.Equal(Profile, receipt.RootElement.GetProperty("profile").GetString());
        Assert.Equal(7, receipt.RootElement.GetProperty("requiredSourceCount").GetInt32());
        Assert.Equal("source-context-export-only", receipt.RootElement.GetProperty("scope").GetString());
        Assert.False(receipt.RootElement.GetProperty("provesLockedRestore").GetBoolean());
        Assert.False(receipt.RootElement.GetProperty("provesPinnedDependencyCheckout").GetBoolean());
    }

    [Theory]
    [MemberData(nameof(MissingSources))]
    public async Task MissingRequiredCopySource_Rejects(string omitted)
    {
        ProcessResult result = await Probe(Required.Where(path => path != omitted)
            .Select(path => ("context/" + path, "source-sentinel")));
        Assert.Equal(1, result.ExitCode);
        Assert.DoesNotContain("source-sentinel", result.Output + result.Error, StringComparison.Ordinal);
    }

    [Theory]
    [InlineData(".git/config")]
    [InlineData(".dependencies/Legacy.Maliev.ServiceDefaults/.git/config")]
    [InlineData(".dependencies/Legacy.Maliev.CompatibilityContracts/.git/config")]
    public async Task RootOrNestedGitMetadata_RejectsWithoutContentDisclosure(string metadata)
    {
        ProcessResult result = await Probe(Required.Select(path => ("context/" + path, "source-sentinel"))
            .Append(("context/" + metadata, "owned-metadata-canary")));
        Assert.Equal(1, result.ExitCode);
        Assert.DoesNotContain("owned-metadata-canary", result.Output + result.Error, StringComparison.Ordinal);
    }

    [Theory]
    [InlineData("../context/escape")]
    [InlineData("/context/absolute")]
    [InlineData("context/nested/../../escape")]
    [InlineData("context\\nested\\escape")]
    [InlineData("C:/context/escape")]
    public async Task UnsafeArchivePath_Rejects(string name)
    {
        ProcessResult result = await Probe(Required.Select(path => ("context/" + path, "source-sentinel"))
            .Append((name, "source-sentinel")));
        Assert.Equal(1, result.ExitCode);
    }

    [Fact]
    public async Task DuplicateRequiredEntry_Rejects()
    {
        ProcessResult result = await Probe(Required.Select(path => ("context/" + path, "source-sentinel"))
            .Append(("context/" + Required[0], "duplicate-sentinel")));
        Assert.Equal(1, result.ExitCode);
    }

    [Fact]
    public async Task EmptyRequiredSource_Rejects()
    {
        ProcessResult result = await Probe(Required.Select(path => ("context/" + path,
            path == Required[5] ? "" : "source-sentinel")));
        Assert.Equal(1, result.ExitCode);
    }

    [Fact]
    public async Task UnknownOwnerProfile_RejectsWithoutFallback()
    {
        ProcessResult result = await Probe(Required.Select(path => ("context/" + path, "source-sentinel")),
            "unreviewed-owner-profile");
        Assert.Equal(1, result.ExitCode);
    }

    [Fact]
    public async Task ArchiveEntryBound_Rejects()
    {
        ProcessResult result = await Probe(Required.Select(path => ("context/" + path, "source-sentinel"))
            .Concat(Enumerable.Range(0, 2049).Select(index => ($"context/extra/{index}.txt", "source-sentinel"))));
        Assert.Equal(1, result.ExitCode);
    }

    [Theory]
    [InlineData("callerHead")]
    [InlineData("sourceBase")]
    [InlineData("publisherHead")]
    [InlineData("defaultsHead")]
    [InlineData("defaultsTree")]
    [InlineData("contractsHead")]
    [InlineData("contractsTree")]
    [InlineData("dockerfileSha256")]
    [InlineData("policySha256")]
    public async Task WrongFrozenIdentity_Rejects(string field)
    {
        ProcessResult result = await Probe(Required.Select(path => ("context/" + path, "source-sentinel")),
            mutateProvenance: provenance => provenance[field] = new string('0', field.EndsWith("Sha256", StringComparison.Ordinal) ? 64 : 40));
        Assert.Equal(1, result.ExitCode);
    }

    [Fact]
    public async Task MissingRequiredSourceProvenance_Rejects()
    {
        ProcessResult result = await Probe(Required.Select(path => ("context/" + path, "source-sentinel")),
            mutateProvenance: provenance => provenance["requiredSources"]!.AsObject().Remove(Required[0]));
        Assert.Equal(1, result.ExitCode);
    }

    [Fact]
    public async Task SourceDigestMismatch_Rejects()
    {
        ProcessResult result = await Probe(Required.Select(path => ("context/" + path, "source-sentinel")),
            mutateProvenance: provenance => provenance["requiredSources"]![Required[0]] = new string('0', 64));
        Assert.Equal(1, result.ExitCode);
    }

    [Fact]
    public async Task UnexpectedProvenanceField_Rejects()
    {
        ProcessResult result = await Probe(Required.Select(path => ("context/" + path, "source-sentinel")),
            mutateProvenance: provenance => provenance["unreviewedField"] = "owned-provenance-canary");
        Assert.Equal(1, result.ExitCode);
        Assert.DoesNotContain("owned-provenance-canary", result.Output + result.Error, StringComparison.Ordinal);
    }

    [Fact]
    public async Task OversizedRegularMember_Rejects()
    {
        ProcessResult result = await Probe(Required.Select(path => ("context/" + path, "source-sentinel"))
            .Append(("context/extra/oversized.txt", new string('x', 1048577))));
        Assert.Equal(1, result.ExitCode);
    }

    [Fact]
    public async Task PythonBehavioralSuite_PassesMetadataAndOwnedStagingControls()
    {
        string script = Path.Combine(RepositoryContractTests.FindRepositoryRoot(), "tests", "test_accounting_context.py");
        ProcessStartInfo start = new(OperatingSystem.IsWindows() ? "python" : "python3")
        {
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        start.ArgumentList.Add("-B");
        start.ArgumentList.Add(script);
        using Process process = new() { StartInfo = start };
        using CancellationTokenSource budget = CancellationTokenSource.CreateLinkedTokenSource(TestContext.Current.CancellationToken);
        budget.CancelAfter(TimeSpan.FromSeconds(30));
        Assert.True(process.Start());
        try
        {
            Task<string> output = process.StandardOutput.ReadToEndAsync(budget.Token);
            Task<string> error = process.StandardError.ReadToEndAsync(budget.Token);
            await process.WaitForExitAsync(budget.Token);
            await Task.WhenAll(output, error).WaitAsync(TimeSpan.FromSeconds(10), TestContext.Current.CancellationToken);
            Assert.True(process.ExitCode == 0, await error);
        }
        finally
        {
            if (!process.HasExited)
            {
                process.Kill(entireProcessTree: true);
                using CancellationTokenSource termination = new(TimeSpan.FromSeconds(10));
                await process.WaitForExitAsync(termination.Token);
            }
        }
    }

    private static async Task<ProcessResult> Probe(IEnumerable<(string Name, string Content)> entries,
        string profile = Profile, Action<JsonObject>? mutateProvenance = null)
    {
        string root = RepositoryContractTests.FindRepositoryRoot();
        string script = Path.Combine(root, "scripts", "validate-host-dependency-context.py");
        Assert.True(File.Exists(script), "Trusted Accounting context-export validator is not implemented yet.");
        string directory = Path.Combine(Path.GetTempPath(), "workflows-accounting-context-" + Guid.NewGuid().ToString("N"));
        bool terminal = true;
        try
        {
            Directory.CreateDirectory(directory);
            (string Name, string Content)[] materialized = entries.ToArray();
            string archive = Path.Combine(directory, "context.tar");
            await using (FileStream stream = File.Create(archive))
            using (TarWriter writer = new(stream, leaveOpen: true))
            {
                foreach ((string name, string content) in materialized)
                {
                    using MemoryStream data = new(Encoding.UTF8.GetBytes(content));
                    PaxTarEntry entry = new(TarEntryType.RegularFile, name) { DataStream = data };
                    writer.WriteEntry(entry);
                }
            }

            JsonObject requiredSources = new();
            foreach (string path in Required)
            {
                string content = materialized.FirstOrDefault(entry => entry.Name == "context/" + path).Content ?? "source-sentinel";
                requiredSources[path] = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(content))).ToLowerInvariant();
            }

            JsonObject provenance = new()
            {
                ["schemaVersion"] = 1,
                ["profile"] = Profile,
                ["callerHead"] = CallerRef,
                ["sourceBase"] = CallerRef,
                ["publisherHead"] = "e3a6093324a24968876782153286f52db8b29fd8",
                ["defaultsHead"] = "8f4f5f27b226ffe406c4c79b1903742e8c2e7dd3",
                ["defaultsTree"] = "2b02094f45bcd3ac112a2c6da66dc2a4bb6994c0",
                ["contractsHead"] = "78e48ffc4ee000df0510cba5e7c7a3c4c4d539d7",
                ["contractsTree"] = "b8172e57562f2e276554e47d4fa0964736c8cbe8",
                ["dockerfileSha256"] = "2150a1d560902ed683a3e0c9aa39c8572a66c3dd48fb1e8b404451feab860fcc",
                ["policySha256"] = "5984866d3f136fd22a64d3147c942eac8423638bf2f5703232c2d11cc1ed0db5",
                ["requiredSources"] = requiredSources,
            };
            mutateProvenance?.Invoke(provenance);
            string provenancePath = Path.Combine(directory, "provenance.json");
            await File.WriteAllTextAsync(provenancePath, provenance.ToJsonString(), TestContext.Current.CancellationToken);

            ProcessStartInfo start = new(OperatingSystem.IsWindows() ? "python" : "python3")
            {
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true,
            };
            foreach (string argument in new[] { "-B", script, "--profile", profile, "--archive", archive,
                "--provenance", provenancePath, "--caller-ref", CallerRef })
            {
                start.ArgumentList.Add(argument);
            }

            using Process process = new() { StartInfo = start };
            using CancellationTokenSource budget = CancellationTokenSource.CreateLinkedTokenSource(TestContext.Current.CancellationToken);
            budget.CancelAfter(TimeSpan.FromSeconds(20));
            Assert.True(process.Start());
            terminal = false;
            try
            {
                Task<string> output = process.StandardOutput.ReadToEndAsync(budget.Token);
                Task<string> error = process.StandardError.ReadToEndAsync(budget.Token);
                await process.WaitForExitAsync(budget.Token);
                await Task.WhenAll(output, error).WaitAsync(TimeSpan.FromSeconds(10), TestContext.Current.CancellationToken);
                terminal = true;
                return new ProcessResult(process.ExitCode, await output, await error);
            }
            finally
            {
                if (!process.HasExited)
                {
                    process.Kill(entireProcessTree: true);
                    using CancellationTokenSource termination = new(TimeSpan.FromSeconds(10));
                    await process.WaitForExitAsync(termination.Token);
                }

                // A root exit without drained pipes is not a proved terminal fixture.
                if (!terminal)
                {
                    budget.Cancel();
                }
            }
        }
        finally
        {
            if (terminal)
            {
                string full = Path.GetFullPath(directory);
                Assert.StartsWith(Path.GetFullPath(Path.GetTempPath()), full, StringComparison.OrdinalIgnoreCase);
                Assert.StartsWith("workflows-accounting-context-", Path.GetFileName(full), StringComparison.Ordinal);
                if (Directory.Exists(full))
                {
                    Directory.Delete(full, recursive: true);
                }
            }
        }
    }

    private sealed record ProcessResult(int ExitCode, string Output, string Error);
}
