using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using Legacy.Maliev.AdditiveBenchmark;
using Xunit;

namespace Legacy.Maliev.Workflows.Tests;

public sealed class AdditiveBenchmarkTests
{
    [Theory]
    [InlineData("1.0")]
    [InlineData("2.0")]
    public void ReadyManifest_ReportsActualVersionAndCanonicalHash(string version)
    {
        using Inputs input = new(version);
        BenchmarkRunResult result = input.Run();
        Assert.Equal(0, result.ExitCode);
        Assert.Equal("ready", result.Status);
        Assert.Equal("2.0", result.Report.SchemaVersion);
        Assert.Equal(version, result.Report.ManifestSchemaVersion);
        Assert.Null(result.Report.InvalidIssues.FirstOrDefault());
        Assert.Equal(72, result.Report.Summary.ReadyCases);
        Assert.DoesNotContain('\r', result.ReportJson);
        Assert.EndsWith("\n", result.ReportJson);
        BenchmarkDeterministicResult deterministic = new(result.Status, result.Report.Summary,
            result.Report.InvalidIssues, result.Report.BlockingIssues, result.Report.Cases);
        Assert.Equal(Hash(JsonSerializer.Serialize(deterministic)), result.Report.DeterministicResultSha256);
        Assert.Equal(result.ReportJson, input.Run().ReportJson);
        string lf = File.ReadAllText(input.ManifestPath);
        Assert.Equal(Hash(lf), result.Report.ManifestSha256);
        File.WriteAllText(input.ManifestPath, lf.Replace("\n", "\r\n", StringComparison.Ordinal));
        Assert.Equal(result.ReportJson, input.Run().ReportJson);
    }

    [Fact]
    public void MissingEvidence_IsBlockedAndNullMetricsStayUnknown()
    {
        using Inputs input = new("1.0");
        input.Manifest["status"] = "blocked";
        JsonObject first = input.Case();
        first["availability"] = "blocked";
        first["missingDataReasons"] = new JsonArray("reference unavailable");
        first["modelSha256"] = null;
        first["profileSha256"] = null;
        first["transform4x4"] = null;
        first["slicerReference"]!["modelPrintSeconds"] = null;
        first["slicerReference"]!["totalMachineSeconds"] = null;
        input.Save();
        BenchmarkRunResult result = input.Run();
        Assert.Equal(2, result.ExitCode);
        Assert.Equal("blocked", result.Status);
        Assert.Empty(result.Report.InvalidIssues);
        Assert.Contains(result.Report.BlockingIssues, issue => issue.Code == "case.blocked");
        Assert.Null(input.Case()["slicerReference"]!["modelPrintSeconds"]);
        Assert.Contains("reference unavailable", result.Report.Cases.Single(item => item.CaseId == "case-a").MissingDataReasons);
    }

    [Theory]
    [InlineData("pose", "reference_pose_mismatch")]
    [InlineData("reference-type", "case.reference_transform_invalid")]
    [InlineData("provenance-type", "case.provenance_type")]
    [InlineData("blocker-type", "blocker.type")]
    [InlineData("unknown", "manifest.undeclared_property")]
    [InlineData("ready-null", "case.ready_missing_slicer_metric")]
    [InlineData("duplicate-case", "case.duplicate_id")]
    [InlineData("profile-sha", "case.sha_invalid")]
    public void InvalidManifest_FailsClosedWithStableIssue(string mutation, string code)
    {
        using Inputs input = new("2.0");
        switch (mutation)
        {
            case "pose": input.Case()["referenceTransform4x4"]![12] = 10; break;
            case "reference-type": input.Case()["referenceTransform4x4"]![0] = "wrong"; break;
            case "provenance-type": input.Case()["provenance"] = new JsonArray(42); break;
            case "blocker-type": input.Manifest["evidenceBlockers"] = new JsonArray(42); break;
            case "unknown": input.Manifest["extra"] = true; break;
            case "ready-null": input.Case()["slicerReference"]!["modelPrintSeconds"] = null; break;
            case "duplicate-case": input.Manifest["cases"]![1]!["caseId"] = "case-a"; break;
            case "profile-sha": input.Case()["profileSha256"] = "wrong"; break;
        }

        input.Save();
        BenchmarkRunResult result = input.Run();
        Assert.Equal(1, result.ExitCode);
        Assert.Equal("invalid", result.Status);
        Assert.Contains(result.Report.InvalidIssues, issue => issue.Code == code);
    }

    [Theory]
    [InlineData("mismatch", "schema.manifest_version_mismatch")]
    [InlineData("root", "schema.root_type")]
    [InlineData("properties", "schema.version_contract_missing")]
    [InlineData("duplicate", "schema.invalid_json")]
    [InlineData("open", "schema.open_root_contract")]
    public void SchemaEnvelopeAndPin_AreRequired(string mutation, string code)
    {
        using Inputs input = new("2.0");
        JsonObject schema = JsonNode.Parse(File.ReadAllText(input.SchemaPath))!.AsObject();
        string bytes;
        switch (mutation)
        {
            case "mismatch": schema["properties"]!["schemaVersion"]!["const"] = "1.0"; bytes = schema.ToJsonString(); break;
            case "properties": schema["properties"] = 42; bytes = schema.ToJsonString(); break;
            case "open": schema["additionalProperties"] = true; bytes = schema.ToJsonString(); break;
            case "duplicate": bytes = "{\"type\":\"object\",\"type\":\"object\"}"; break;
            default: bytes = "[]"; break;
        }

        File.WriteAllText(input.SchemaPath, bytes);
        BenchmarkRunResult result = input.Run();
        Assert.Equal(1, result.ExitCode);
        Assert.Contains(result.Report.InvalidIssues, issue => issue.Code == code);
    }

    [Theory]
    [InlineData("{")]
    [InlineData("{\"schemaVersion\":\"2.0\",\"schemaVersion\":\"1.0\"}")]
    [InlineData("{\"nested\":{\"x\":1,\"x\":2}}")]
    public void UnparseableManifest_ReportsNullVersion(string text)
    {
        using Inputs input = new("2.0");
        File.WriteAllText(input.ManifestPath, text);
        BenchmarkRunResult result = input.Run();
        Assert.Equal(1, result.ExitCode);
        Assert.Null(result.Report.ManifestSchemaVersion);
        Assert.Contains(result.Report.InvalidIssues, issue => issue.Code == "manifest.invalid_json");
        Assert.Contains("\"manifestSchemaVersion\": null", result.ReportJson);
    }

    [Theory]
    [InlineData("1.0", "ready", 0)]
    [InlineData("1.0", "blocked", 2)]
    [InlineData("1.0", "invalid", 1)]
    [InlineData("2.0", "ready", 0)]
    [InlineData("2.0", "blocked", 2)]
    [InlineData("2.0", "invalid", 1)]
    public async Task ActualCli_EmitsReportAndExitCode(string version, string status, int exitCode)
    {
        using Inputs input = new(version);
        if (status == "blocked")
        {
            input.Manifest["status"] = "blocked";
            input.Manifest["evidenceBlockers"] = new JsonArray(new JsonObject
            {
                ["blockerId"] = "synthetic",
                ["status"] = "blocked",
                ["missingDataReason"] = "not observed",
            });
        }
        else if (status == "invalid")
        {
            input.Manifest["extra"] = true;
        }

        input.Save();
        string reportPath = Path.Combine(input.DirectoryPath, "report.json");
        (int code, string output, string error) = await Cli("--manifest", input.ManifestPath, "--schema", input.SchemaPath, "--report", reportPath);
        Assert.Equal(exitCode, code);
        Assert.Equal($"Additive benchmark manifest status: {status}", output.Trim());
        Assert.Empty(error);
        byte[] report = File.ReadAllBytes(reportPath);
        Assert.Equal(input.Run().ReportJson, Encoding.UTF8.GetString(report));
        Assert.False(report.AsSpan().StartsWith(new byte[] { 239, 187, 191 }));
        using JsonDocument emitted = JsonDocument.Parse(report);
        using JsonDocument schema = JsonDocument.Parse(File.ReadAllText(Path.Combine(RepositoryContractTests.FindRepositoryRoot(), "tools/additive-benchmark/schemas/report.v2.schema.json")));
        Assert.Equal(schema.RootElement.GetProperty("required").EnumerateArray().Select(item => item.GetString()).Order(StringComparer.Ordinal),
            emitted.RootElement.EnumerateObject().Select(item => item.Name).Order(StringComparer.Ordinal));
        Assert.Equal(version, emitted.RootElement.GetProperty("manifestSchemaVersion").GetString());
        AssertReportSchema(emitted.RootElement, schema.RootElement, schema.RootElement);
    }

    [Theory]
    [InlineData("duplicate")]
    [InlineData("unknown")]
    [InlineData("missing")]
    [InlineData("oversize")]
    [InlineData("schema-oversize")]
    [InlineData("alias")]
    public async Task ActualCli_RejectsAdmissionWithoutLeakingPaths(string mutation)
    {
        using Inputs input = new("2.0");
        string report = Path.Combine(input.DirectoryPath, "report.json");
        string[] args = ["--manifest", input.ManifestPath, "--schema", input.SchemaPath, "--report", report];
        switch (mutation)
        {
            case "duplicate": args[2] = "--manifest"; break;
            case "unknown": args[2] = "--unknown"; break;
            case "missing": args[1] = Path.Combine(input.DirectoryPath, "sensitive-name.json"); break;
            case "oversize": File.WriteAllBytes(input.ManifestPath, new byte[4 * 1024 * 1024 + 1]); break;
            case "schema-oversize": File.WriteAllBytes(input.SchemaPath, new byte[4 * 1024 * 1024 + 1]); break;
            case "alias": args[5] = input.ManifestPath; break;
        }

        string before = File.ReadAllText(input.ManifestPath);
        (int code, string output, string error) = await Cli(args);
        Assert.Equal(1, code);
        Assert.Empty(output);
        Assert.DoesNotContain(input.DirectoryPath, error);
        Assert.DoesNotContain("sensitive-name", error);
        Assert.False(File.Exists(report));
        Assert.Equal(before, File.ReadAllText(input.ManifestPath));
    }

    [Fact]
    public void ReportSchemaV2_PermitsObservedVersionAndRetainsHistoricalV1()
    {
        string root = RepositoryContractTests.FindRepositoryRoot();
        using JsonDocument v1 = JsonDocument.Parse(File.ReadAllText(Path.Combine(root, "tools/additive-benchmark/schemas/report.v1.schema.json")));
        using JsonDocument v2 = JsonDocument.Parse(File.ReadAllText(Path.Combine(root, "tools/additive-benchmark/schemas/report.v2.schema.json")));
        Assert.Equal("1.0", v1.RootElement.GetProperty("properties").GetProperty("manifestSchemaVersion").GetProperty("const").GetString());
        Assert.Equal("2.0", v2.RootElement.GetProperty("properties").GetProperty("schemaVersion").GetProperty("const").GetString());
        Assert.Equal(new string?[] { "1.0", "2.0", null }, v2.RootElement.GetProperty("properties").GetProperty("manifestSchemaVersion").GetProperty("enum").EnumerateArray().Select(value => value.GetString()).ToArray());
    }

    [Fact]
    public void HistoricalV1Coverage_CannotBeLoweredToDeclareReady()
    {
        using Inputs input = new("1.0");
        input.Manifest["coverageRequirements"]!["modelCount"] = 1;
        input.Manifest["coverageRequirements"]!["families"] = new JsonArray();
        input.Save();
        BenchmarkRunResult result = input.Run();
        Assert.Equal(1, result.ExitCode);
        Assert.Contains(result.Report.InvalidIssues, issue => issue.Code == "coverage.v1_contract");
    }

    [Theory]
    [InlineData("2.0", "inputArtifactSha256", "case.matched_sha_required")]
    [InlineData("2.0", "profileBundleSha256", "case.matched_sha_required")]
    [InlineData("2.0", "preferences", "coverage.preference_invalid")]
    [InlineData("2.0", "duplicate-preferences", "coverage.preference_duplicate")]
    [InlineData("1.0", "missing-reasons", "case.missing_reason_duplicate")]
    [InlineData("2.0", "missing-reasons", "case.missing_reason_duplicate")]
    [InlineData("2.0", "availability", "case.availability")]
    public async Task ActualCli_RejectsSchemaAdmissionGapsAndProducesConformingCaseResults(string version, string mutation, string issue)
    {
        using Inputs input = new(version);
        switch (mutation)
        {
            case "preferences": input.Manifest["coverageRequirements"]!["preferences"] = new JsonArray(42); break;
            case "duplicate-preferences": input.Manifest["coverageRequirements"]!["preferences"] = new JsonArray("standard", "standard"); break;
            case "availability": input.Case()["availability"] = "wrong"; break;
            case "missing-reasons":
                input.Manifest["status"] = "blocked";
                input.Case()["availability"] = "blocked";
                input.Case()["missingDataReasons"] = new JsonArray("unobserved", "unobserved");
                break;
            default: input.Case()[mutation] = null; break;
        }

        input.Save();
        BenchmarkRunResult result = input.Run();
        Assert.Equal(1, result.ExitCode);
        Assert.Contains(result.Report.InvalidIssues, item => item.Code == issue);
        string report = Path.Combine(input.DirectoryPath, "report.json");
        (int code, string output, string error) = await Cli("--manifest", input.ManifestPath, "--schema", input.SchemaPath, "--report", report);
        Assert.Equal(1, code);
        Assert.Equal("Additive benchmark manifest status: invalid", output.Trim());
        Assert.Empty(error);
        Assert.Equal(result.ReportJson, File.ReadAllText(report));
        using JsonDocument emitted = JsonDocument.Parse(File.ReadAllText(report));
        using JsonDocument schema = JsonDocument.Parse(File.ReadAllText(Path.Combine(RepositoryContractTests.FindRepositoryRoot(), "tools/additive-benchmark/schemas/report.v2.schema.json")));
        AssertReportSchema(emitted.RootElement, schema.RootElement, schema.RootElement);
        foreach (BenchmarkCaseResult item in result.Report.Cases)
        {
            Assert.Contains(item.Availability, new[] { "ready", "blocked", "invalid" });
            Assert.Equal(item.MissingDataReasons.Length, item.MissingDataReasons.Distinct(StringComparer.Ordinal).Count());
        }
    }

    private static string Hash(string value) => Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(value)));

    // The report schema uses only these vocabulary entries. Unsupported entries fail the test.
    private static void AssertReportSchema(JsonElement value, JsonElement rule, JsonElement root)
    {
        string[] supported = ["$schema", "$id", "title", "$defs", "$ref", "type", "const", "enum", "required", "properties", "additionalProperties", "items", "uniqueItems", "minLength", "minimum", "pattern"];
        Assert.All(rule.EnumerateObject(), property => Assert.Contains(property.Name, supported));
        if (rule.TryGetProperty("$ref", out JsonElement reference))
        {
            string[] parts = reference.GetString()!.Split('/');
            Assert.Equal("#", parts[0]);
            JsonElement resolved = root;
            foreach (string part in parts.Skip(1))
            {
                resolved = resolved.GetProperty(part);
            }

            AssertReportSchema(value, resolved, root);
            return;
        }

        if (rule.TryGetProperty("type", out JsonElement type))
        {
            string[] types = type.ValueKind == JsonValueKind.Array
                ? type.EnumerateArray().Select(item => item.GetString()!).ToArray() : [type.GetString()!];
            string actual = value.ValueKind switch
            {
                JsonValueKind.Object => "object",
                JsonValueKind.Array => "array",
                JsonValueKind.String => "string",
                JsonValueKind.Null => "null",
                JsonValueKind.Number when value.TryGetInt64(out _) => "integer",
                _ => throw new InvalidOperationException("Unexpected report value kind."),
            };
            Assert.Contains(actual, types);
        }

        if (rule.TryGetProperty("const", out JsonElement constant))
        {
            Assert.True(JsonNode.DeepEquals(JsonNode.Parse(value.GetRawText()), JsonNode.Parse(constant.GetRawText())));
        }

        if (rule.TryGetProperty("enum", out JsonElement allowed))
        {
            Assert.Contains(allowed.EnumerateArray(), item => JsonNode.DeepEquals(JsonNode.Parse(value.GetRawText()), JsonNode.Parse(item.GetRawText())));
        }

        if (value.ValueKind == JsonValueKind.Object)
        {
            JsonElement properties = rule.GetProperty("properties");
            if (rule.TryGetProperty("required", out JsonElement required))
            {
                Assert.All(required.EnumerateArray(), item => Assert.True(value.TryGetProperty(item.GetString()!, out _)));
            }

            foreach (JsonProperty property in value.EnumerateObject())
            {
                Assert.True(properties.TryGetProperty(property.Name, out JsonElement child));
                AssertReportSchema(property.Value, child, root);
            }
        }
        else if (value.ValueKind == JsonValueKind.Array)
        {
            if (rule.TryGetProperty("uniqueItems", out JsonElement unique) && unique.GetBoolean())
            {
                string[] items = value.EnumerateArray().Select(item => item.GetRawText()).ToArray();
                Assert.Equal(items.Length, items.Distinct(StringComparer.Ordinal).Count());
            }

            JsonElement child = rule.GetProperty("items");
            Assert.All(value.EnumerateArray(), item => AssertReportSchema(item, child, root));
        }
        else if (value.ValueKind == JsonValueKind.String)
        {
            string text = value.GetString()!;
            if (rule.TryGetProperty("minLength", out JsonElement length))
            {
                Assert.True(text.Length >= length.GetInt32());
            }

            if (rule.TryGetProperty("pattern", out JsonElement pattern))
            {
                Assert.True(Regex.IsMatch(text, pattern.GetString()!, RegexOptions.CultureInvariant, TimeSpan.FromMilliseconds(250)));
            }
        }
        else if (value.ValueKind == JsonValueKind.Number && rule.TryGetProperty("minimum", out JsonElement minimum))
        {
            Assert.True(value.GetInt64() >= minimum.GetInt64());
        }
    }

    private static async Task<(int Code, string Output, string Error)> Cli(params string[] args)
    {
        string root = RepositoryContractTests.FindRepositoryRoot();
        string dll = Path.Combine(root, "tools/additive-benchmark/bin/Release/net10.0/Legacy.Maliev.AdditiveBenchmark.dll");
        ProcessStartInfo start = new("dotnet")
        {
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        start.ArgumentList.Add(dll);
        foreach (string arg in args)
        {
            start.ArgumentList.Add(arg);
        }

        using Process process = new() { StartInfo = start };
        using CancellationTokenSource budget = CancellationTokenSource.CreateLinkedTokenSource(TestContext.Current.CancellationToken);
        budget.CancelAfter(TimeSpan.FromSeconds(20));
        Assert.True(process.Start());
        try
        {
            Task<string> output = process.StandardOutput.ReadToEndAsync(budget.Token);
            Task<string> error = process.StandardError.ReadToEndAsync(budget.Token);
            await process.WaitForExitAsync(budget.Token);
            return (process.ExitCode, await output, await error);
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

    private sealed class Inputs : IDisposable
    {
        public string DirectoryPath { get; } = Path.Combine(Path.GetTempPath(), "legacy-additive-" + Guid.NewGuid().ToString("N"));
        public string ManifestPath => Path.Combine(DirectoryPath, "manifest.json");
        public string SchemaPath => Path.Combine(DirectoryPath, "schema.json");
        public JsonObject Manifest { get; }

        public Inputs(string version)
        {
            Directory.CreateDirectory(DirectoryPath);
            string root = RepositoryContractTests.FindRepositoryRoot();
            File.Copy(Path.Combine(root, "tools/additive-benchmark/schemas/manifest.v" + version[0] + ".schema.json"), SchemaPath);
            Manifest = new JsonObject
            {
                ["schemaVersion"] = version,
                ["benchmarkVersion"] = "synthetic-only",
                ["status"] = "ready",
                ["evidenceBlockers"] = new JsonArray(),
                ["coverageRequirements"] = new JsonObject
                {
                    ["modelCount"] = 24,
                    ["calibrationModelCount"] = 16,
                    ["validationModelCount"] = 8,
                    ["minimumCases"] = 72,
                    ["families"] = new JsonArray("thin_lettering", "flat_plates", "hollow_parts", "tall_walls", "curved_surfaces", "dense_parts", "small_details", "support_heavy"),
                    ["preferences"] = new JsonArray("quality", "standard", "strength"),
                },
                ["cases"] = CreateCases(version),
            };
            Save();
        }

        public JsonObject Case() => Manifest["cases"]![0]!.AsObject();
        public void Save() => File.WriteAllText(ManifestPath, Manifest.ToJsonString(new JsonSerializerOptions { WriteIndented = true }).Replace("\r\n", "\n", StringComparison.Ordinal) + "\n");
        public BenchmarkRunResult Run() => AdditiveBenchmarkRunner.Run(ManifestPath, SchemaPath);
        public void Dispose()
        {
            Directory.Delete(DirectoryPath, true);
            Assert.False(Directory.Exists(DirectoryPath));
        }

        private static JsonArray CreateCases(string version)
        {
            string[] families = ["thin_lettering", "flat_plates", "hollow_parts", "tall_walls", "curved_surfaces", "dense_parts", "small_details", "support_heavy"];
            JsonArray cases = new();
            for (int model = 0; model < 24; model++)
            {
                foreach (string preference in new[] { "quality", "standard", "strength" })
                {
                    string id = model == 0 && preference == "quality" ? "case-a" : $"case-{model:D2}-{preference}";
                    JsonObject item = CreateCase(id, model < 16 ? "calibration" : "validation", version);
                    item["modelId"] = $"model-{model:D2}";
                    item["family"] = families[model / 3];
                    item["preference"] = preference;
                    cases.Add(item);
                }
            }

            return cases;
        }

        private static JsonObject CreateCase(string id, string split, string version)
        {
            string sha = new('a', 64);
            JsonArray Transform() => new(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1);
            JsonObject Metrics() => new()
            {
                ["modelPrintSeconds"] = null,
                ["preparationSeconds"] = null,
                ["totalMachineSeconds"] = null,
                ["modelGrams"] = null,
                ["supportGrams"] = null,
                ["purgeWasteGrams"] = null,
                ["resinMilliliters"] = null,
            };
            JsonObject result = new()
            {
                ["caseId"] = id,
                ["modelId"] = "model-" + id,
                ["family"] = "flat_plates",
                ["split"] = split,
                ["preference"] = "standard",
                ["availability"] = "ready",
                ["modelSha256"] = sha,
                ["sourceUri"] = "urn:synthetic:" + id,
                ["sourceUnits"] = "mm",
                ["transform4x4"] = Transform(),
                ["materialSku"] = null,
                ["machineProfileId"] = "synthetic",
                ["processProfileId"] = "synthetic",
                ["filamentProfileId"] = "synthetic",
                ["profileSha256"] = sha,
                ["slicerVersion"] = "synthetic",
                ["supportMode"] = "none",
                ["orientationPolicyVersion"] = "synthetic",
                ["quantity"] = 1,
                ["expected"] = Metrics(),
                ["slicerReference"] = Metrics(),
                ["productionActual"] = Metrics(),
                ["workbookInputs"] = new JsonObject { ["printTimeSeconds"] = null, ["materialGrams"] = null, ["priceThb"] = null },
                ["provenance"] = new JsonArray(new JsonObject
                {
                    ["sourceKind"] = "synthetic",
                    ["uri"] = "urn:synthetic:fixture",
                    ["sha256"] = null,
                    ["observedAtUtc"] = null,
                    ["notes"] = "Synthetic metadata; no physical evidence.",
                }),
                ["missingDataReasons"] = new JsonArray(),
            };
            result["slicerReference"]!["modelPrintSeconds"] = 60;
            result["slicerReference"]!["totalMachineSeconds"] = 70;
            if (version == "2.0")
            {
                result["orientationPolicy"] = "fixed";
                result["inputArtifactSha256"] = sha;
                result["profileBundleSha256"] = sha;
                result["referenceTransform4x4"] = Transform();
                result["metricDefinitions"] = new JsonObject { ["time"] = "seconds", ["material"] = "grams", ["support"] = "grams" };
            }

            return result;
        }
    }
}
