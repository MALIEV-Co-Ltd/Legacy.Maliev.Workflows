using System.Diagnostics;
using System.Text.Json.Nodes;
using Xunit;

namespace Legacy.Maliev.Workflows.Tests;

public sealed class ProductionObservabilityRunbookContractTests
{
    private const string Revision = "0123456789abcdef0123456789abcdef01234567";
    private const string Digest = "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
    private const string Pod = "11111111111111111111111111111111";
    private const string Diagnostic = "22222222222222222222222222222222";
    private const string Incident = "33333333333333333333333333333333";

    [Fact]
    public async Task Complete_independent_console_and_Cloud_metadata_accepts_explicit_zero_natural_errors()
    {
        var result = await ValidateAsync(Complete().ToJsonString());
        Assert.Equal(0, result.ExitCode);
        Assert.Equal("verified", result.Summary["visibility"]!.GetValue<string>());
        Assert.Equal(0, result.Summary["actionSevereEvents"]!.GetValue<int>());
        Assert.Equal(0, result.Summary["baselineSevereEvents"]!.GetValue<int>());
    }

    [Theory]
    [InlineData("original_namespace")]
    [InlineData("missing_main_validation")]
    [InlineData("mixed_revision")]
    [InlineData("wrong_digest")]
    [InlineData("unready_pod")]
    [InlineData("empty_pods")]
    [InlineData("duplicate_pod")]
    [InlineData("proxy_only")]
    [InlineData("public_access")]
    [InlineData("missing_incident")]
    [InlineData("multiple_probes")]
    [InlineData("forward_still_running")]
    [InlineData("deadline_exceeded")]
    [InlineData("missing_cloud_error")]
    [InlineData("duplicate_warning_not_three_severities")]
    [InlineData("severity_mismatch")]
    [InlineData("wrong_diagnostic")]
    [InlineData("truncated_action")]
    [InlineData("truncated_baseline")]
    [InlineData("unavailable_natural")]
    [InlineData("wrong_windows")]
    [InlineData("unknown_private_field")]
    [InlineData("stale_capture")]
    [InlineData("future_capture")]
    [InlineData("capture_over_180seconds")]
    [InlineData("record_outside_capture")]
    [InlineData("nonadjacent_windows")]
    [InlineData("unmarked_framework_error")]
    [InlineData("duplicate_roster")]
    [InlineData("too_many_roster_ids")]
    [InlineData("wrong_roster_type")]
    public async Task Incomplete_or_untrusted_metadata_fails_closed_without_returning_zero(string scenario)
    {
        var input = Complete();
        var pod = input["pods"]![0]!;
        switch (scenario)
        {
            case "original_namespace": input["namespace"] = "maliev"; break;
            case "missing_main_validation": input["exactMainValidation"] = false; break;
            case "mixed_revision": pod["revision"] = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"; break;
            case "wrong_digest": pod["imageDigest"] = "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"; break;
            case "unready_pod": pod["ready"] = false; break;
            case "empty_pods": input["pods"] = new JsonArray(); break;
            case "duplicate_pod": ((JsonArray)input["pods"]!).Add(pod.DeepClone()); break;
            case "proxy_only": pod["socketLoopback"] = false; break;
            case "public_access": pod["publicStatus"] = 500; break;
            case "missing_incident": pod["incidentId"] = null; break;
            case "multiple_probes": pod["probeCount"] = 2; break;
            case "forward_still_running": pod["portForwardStopped"] = false; break;
            case "deadline_exceeded": pod["observationSeconds"] = 181; break;
            case "missing_cloud_error": ((JsonArray)pod["cloud"]!).RemoveAt(1); break;
            case "duplicate_warning_not_three_severities": pod["cloud"] = new JsonArray(pod["cloud"]![0]!.DeepClone(), pod["cloud"]![0]!.DeepClone(), pod["cloud"]![0]!.DeepClone()); break;
            case "severity_mismatch": pod["cloud"]![1]!["severity"] = "INFO"; break;
            case "wrong_diagnostic": pod["cloud"]![1]!["diagnosticId"] = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"; break;
            case "truncated_action": input["actionTruncated"] = true; break;
            case "truncated_baseline": input["baselineTruncated"] = true; break;
            case "unavailable_natural": input["naturalAvailability"] = "unavailable"; break;
            case "wrong_windows": input["baselineWindowSeconds"] = 86400; break;
            case "unknown_private_field": input["customerBody"] = "PRIVATE_SENTINEL_NOT_FOR_OUTPUT"; break;
            case "stale_capture": input["captureCompletedUtc"] = "2026-10-02T11:59:59Z"; input["captureStartedUtc"] = "2026-10-02T11:59:00Z"; break;
            case "future_capture": input["captureCompletedUtc"] = "2026-10-02T12:03:01Z"; break;
            case "capture_over_180seconds": input["captureStartedUtc"] = "2026-10-02T11:59:59Z"; break;
            case "record_outside_capture": pod["cloud"]![1]!["occurredAtUtc"] = "2026-10-02T11:59:59Z"; break;
            case "nonadjacent_windows": input["baselineToUtc"] = "2026-10-01T12:02:59Z"; break;
            case "unmarked_framework_error": pod["cloud"]![1]!["synthetic"] = false; pod["cloud"]![1]!["diagnosticId"] = null; break;
            case "duplicate_roster": input["servingPodUids"] = new JsonArray(Pod, Pod); break;
            case "too_many_roster_ids": input["servingPodUids"] = new JsonArray(Enumerable.Range(0, 65).Select(value => JsonValue.Create(value.ToString("x32"))).ToArray()); break;
            case "wrong_roster_type": input["servingPodUids"] = true; break;
            default: throw new InvalidOperationException("Unknown controlled case.");
        }
        await AssertUnavailableAsync(input.ToJsonString());
    }

    [Fact]
    public async Task Two_independently_correlated_pods_require_complete_proof_for_both()
    {
        var input = TwoPods();
        var accepted = await ValidateAsync(input.ToJsonString());
        Assert.Equal(0, accepted.ExitCode);
        Assert.Equal("verified", accepted.Summary["visibility"]!.GetValue<string>());
        ((JsonArray)input["pods"]![1]!["cloud"]!).RemoveAt(1);
        await AssertUnavailableAsync(input.ToJsonString());
    }

    [Fact]
    public async Task Missing_independent_serving_inventory_is_not_complete_pod_proof()
    {
        var input = Complete();
        input.Remove("servingPodUids");
        await AssertUnavailableAsync(input.ToJsonString());
    }

    [Fact]
    public async Task Missing_entire_second_pod_is_detected_against_independent_inventory()
    {
        var input = TwoPods();
        input["servingPodUids"] = new JsonArray(Pod, "88888888888888888888888888888888");
        ((JsonArray)input["pods"]!).RemoveAt(1);
        await AssertUnavailableAsync(input.ToJsonString());
    }

    [Fact]
    public async Task Trace_incident_bridge_deduplicates_transitively_without_losing_uncorrelated_errors()
    {
        var input = Complete();
        var first = Record("ERROR", "Error", "Legacy.Maliev.Web.Business", "Failure", "BusinessException", false);
        var bridge = first.DeepClone();
        bridge["recordId"] = "55555555555555555555555555555555";
        bridge["incidentId"] = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
        var last = bridge.DeepClone();
        last["recordId"] = "77777777777777777777777777777777";
        last["traceId"] = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
        var uncorrelated = first.DeepClone();
        uncorrelated["recordId"] = "88888888888888888888888888888888";
        uncorrelated["traceId"] = null;
        uncorrelated["incidentId"] = null;
        var another = uncorrelated.DeepClone();
        another["recordId"] = "99999999999999999999999999999999";
        input["actionRecords"] = new JsonArray(first, bridge, last, uncorrelated, another);
        var result = await ValidateAsync(input.ToJsonString());
        Assert.Equal(0, result.ExitCode);
        Assert.Equal(3, result.Summary["actionSevereEvents"]!.GetValue<int>());
    }

    [Fact]
    public async Task Exact_diagnostic_is_filtered_but_unmarked_framework_failure_and_baseline_business_event_remain()
    {
        var input = Complete();
        var diagnostic = Record("CRITICAL", "Critical", "Legacy.Maliev.Web.Middleware.ErrorIncidentMiddleware", "ObservabilityDiagnosticFailure", "ObservabilityDiagnosticException", true);
        var unmarked = Record("ERROR", "Error", "Microsoft.AspNetCore.Diagnostics.ExceptionHandlerMiddleware", null, "ObservabilityDiagnosticException", false);
        unmarked["recordId"] = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
        unmarked["diagnosticId"] = null;
        var baseline = Record("ERROR", "Error", "Legacy.Maliev.Web.Business", "Failure", "BusinessException", false);
        baseline["occurredAtUtc"] = "2026-09-30T12:00:00Z";
        input["actionRecords"] = new JsonArray(diagnostic, unmarked);
        input["baselineRecords"] = new JsonArray(baseline);
        var result = await ValidateAsync(input.ToJsonString());
        Assert.Equal(0, result.ExitCode);
        Assert.Equal(1, result.Summary["actionSevereEvents"]!.GetValue<int>());
        Assert.Equal(1, result.Summary["baselineSevereEvents"]!.GetValue<int>());
    }

    [Fact]
    public async Task Historical_INFO_overlay_never_hides_actual_Error_LogLevel()
    {
        var input = Complete();
        input["actionRecords"] = new JsonArray(Record("INFO", "Error", "Legacy.Maliev.Web.Business", "Failure", "BusinessException", false));
        var result = await ValidateAsync(input.ToJsonString());
        Assert.Equal(0, result.ExitCode);
        Assert.Equal(1, result.Summary["actionSevereEvents"]!.GetValue<int>());
    }

    [Fact]
    public async Task Baseline_at_action_start_is_not_inside_half_open_baseline()
    {
        var input = Complete();
        var record = Record("ERROR", "Error", "Legacy.Maliev.Web.Business", "Failure", null, false);
        record["occurredAtUtc"] = "2026-10-01T12:03:00Z";
        input["baselineRecords"] = new JsonArray(record);
        await AssertUnavailableAsync(input.ToJsonString());
    }

    [Fact]
    public async Task Action_at_its_start_is_included_in_half_open_action()
    {
        var input = Complete();
        var record = Record("ERROR", "Error", "Legacy.Maliev.Web.Business", "Failure", null, false);
        record["occurredAtUtc"] = "2026-10-01T12:03:00Z";
        input["actionRecords"] = new JsonArray(record);
        var result = await ValidateAsync(input.ToJsonString());
        Assert.Equal(0, result.ExitCode);
        Assert.Equal(1, result.Summary["actionSevereEvents"]!.GetValue<int>());
    }

    [Fact]
    public async Task Shared_window_boundary_cannot_be_counted_in_both_natural_windows()
    {
        var input = Complete();
        var record = Record("ERROR", "Error", "Legacy.Maliev.Web.Business", "Failure", null, false);
        record["occurredAtUtc"] = "2026-10-01T12:03:00Z";
        input["baselineRecords"] = new JsonArray(record);
        input["actionRecords"] = new JsonArray(record.DeepClone());
        await AssertUnavailableAsync(input.ToJsonString());
    }

    [Fact]
    public async Task Same_record_id_on_different_pods_does_not_collapse_uncorrelated_errors()
    {
        var input = Complete();
        var record = Record("ERROR", "Error", "Legacy.Maliev.Web.Business", "Failure", null, false);
        record["traceId"] = null;
        record["incidentId"] = null;
        var second = record.DeepClone();
        second["podUid"] = "99999999999999999999999999999999";
        input["actionRecords"] = new JsonArray(record, second);
        var result = await ValidateAsync(input.ToJsonString());
        Assert.Equal(0, result.ExitCode);
        Assert.Equal(2, result.Summary["actionSevereEvents"]!.GetValue<int>());
    }

    [Fact]
    public async Task Contradictory_metadata_for_same_pod_record_identity_is_unavailable()
    {
        var input = Complete();
        var record = Record("ERROR", "Error", "Legacy.Maliev.Web.Business", "Failure", null, false);
        var conflicting = record.DeepClone();
        conflicting["eventName"] = "DifferentFailure";
        input["actionRecords"] = new JsonArray(record, conflicting);
        await AssertUnavailableAsync(input.ToJsonString());
    }

    [Fact]
    public async Task Identical_repeated_uncorrelated_capture_counts_once()
    {
        var input = Complete();
        var record = Record("ERROR", "Error", "Legacy.Maliev.Web.Business", "Failure", null, false);
        record["traceId"] = null;
        record["incidentId"] = null;
        input["actionRecords"] = new JsonArray(record, record.DeepClone());
        var result = await ValidateAsync(input.ToJsonString());
        Assert.Equal(0, result.ExitCode);
        Assert.Equal(1, result.Summary["actionSevereEvents"]!.GetValue<int>());
    }

    [Fact]
    public async Task Generic_synthetic_flag_never_suppresses_business_errors_and_incident_trace_duplicates_collapse()
    {
        var input = Complete();
        var first = Record("ERROR", "Error", "Legacy.Maliev.Web.Business", "OrderFailure", "BusinessException", true);
        first["diagnosticId"] = Diagnostic;
        var duplicate = first.DeepClone();
        duplicate["severity"] = "CRITICAL";
        duplicate["logLevel"] = "Critical";
        duplicate["recordId"] = "55555555555555555555555555555555";
        input["actionRecords"] = new JsonArray(first, duplicate);
        var result = await ValidateAsync(input.ToJsonString());
        Assert.Equal(0, result.ExitCode);
        Assert.Equal(1, result.Summary["actionSevereEvents"]!.GetValue<int>());
        Assert.Equal("verified", result.Summary["visibility"]!.GetValue<string>());
    }

    [Theory]
    [InlineData("wrong_type")]
    [InlineData("wrong_category")]
    [InlineData("wrong_event")]
    [InlineData("missing_flag")]
    [InlineData("invalid_id")]
    public async Task Diagnostic_lookalikes_remain_actionable_natural_errors(string variant)
    {
        var input = Complete();
        var record = Record("CRITICAL", "Critical", "Legacy.Maliev.Web.Middleware.ErrorIncidentMiddleware", "ObservabilityDiagnosticFailure", "ObservabilityDiagnosticException", true);
        switch (variant)
        {
            case "wrong_type": record["exceptionType"] = "BusinessException"; break;
            case "wrong_category": record["category"] = "Legacy.Maliev.Web.Business"; break;
            case "wrong_event": record["eventName"] = "BusinessFailure"; break;
            case "missing_flag": record["synthetic"] = false; break;
            case "invalid_id": record["diagnosticId"] = "not-a-guid"; break;
        }
        input["actionRecords"] = new JsonArray(record);
        var result = await ValidateAsync(input.ToJsonString());
        Assert.Equal(0, result.ExitCode);
        Assert.Equal(1, result.Summary["actionSevereEvents"]!.GetValue<int>());
    }

    [Theory]
    [InlineData("duplicate_json_property")]
    [InlineData("too_many_pods")]
    [InlineData("too_many_records")]
    [InlineData("too_deep")]
    [InlineData("too_many_bytes")]
    [InlineData("boolean_is_not_integer")]
    [InlineData("integer_is_not_boolean")]
    [InlineData("nonfinite_number")]
    [InlineData("missing_key")]
    [InlineData("baseline_outside_window")]
    public async Task Malformed_or_over_budget_inputs_return_only_fixed_unavailable_summary(string variant)
    {
        var input = Complete();
        string text;
        switch (variant)
        {
            case "duplicate_json_property": text = input.ToJsonString().Insert(1, "\"schemaVersion\":1,"); break;
            case "too_many_pods":
                input["pods"] = new JsonArray(Enumerable.Range(0, 65).Select(_ => input["pods"]![0]!.DeepClone()).ToArray());
                text = input.ToJsonString(); break;
            case "too_many_records":
                input["actionRecords"] = new JsonArray(Enumerable.Range(0, 257).Select(_ => Record("ERROR", "Error", "Legacy.Maliev.Web.Business", "Failure", null, false)).ToArray());
                text = input.ToJsonString(); break;
            case "too_deep": text = "{\"PRIVATE_SENTINEL_NOT_FOR_OUTPUT\":" + new string('[', 10) + "0" + new string(']', 10) + "}"; break;
            case "too_many_bytes": text = "{\"PRIVATE_SENTINEL_NOT_FOR_OUTPUT\":\"" + new string('x', 65536) + "\"}"; break;
            case "boolean_is_not_integer": input["pods"]![0]!["probeCount"] = true; text = input.ToJsonString(); break;
            case "integer_is_not_boolean": input["exactMainValidation"] = 1; text = input.ToJsonString(); break;
            case "nonfinite_number": text = input.ToJsonString().Replace("\"observationSeconds\":180", "\"observationSeconds\":NaN", StringComparison.Ordinal); break;
            case "missing_key": input.Remove("naturalAvailability"); text = input.ToJsonString(); break;
            case "baseline_outside_window": input["baselineRecords"] = new JsonArray(Record("ERROR", "Error", "Legacy.Maliev.Web.Business", "Failure", null, false)); text = input.ToJsonString(); break;
            default: throw new InvalidOperationException("Unknown controlled case.");
        }
        await AssertUnavailableAsync(text);
    }

    private static JsonObject Complete() => new()
    {
        ["schemaVersion"] = 1,
        ["namespace"] = "maliev-legacy",
        ["expectedRevision"] = Revision,
        ["expectedImageDigest"] = Digest,
        ["exactMainValidation"] = true,
        ["captureStartedUtc"] = "2026-10-02T12:00:00Z",
        ["captureCompletedUtc"] = "2026-10-02T12:03:00Z",
        ["naturalAvailability"] = "available",
        ["actionFromUtc"] = "2026-10-01T12:03:00Z",
        ["actionToUtc"] = "2026-10-02T12:03:00Z",
        ["baselineFromUtc"] = "2026-09-24T12:03:00Z",
        ["baselineToUtc"] = "2026-10-01T12:03:00Z",
        ["actionWindowSeconds"] = 86400,
        ["baselineWindowSeconds"] = 604800,
        ["actionTruncated"] = false,
        ["baselineTruncated"] = false,
        ["actionRecords"] = new JsonArray(),
        ["baselineRecords"] = new JsonArray(),
        ["servingPodUids"] = new JsonArray(Pod),
        ["pods"] = new JsonArray(new JsonObject
        {
            ["podUid"] = Pod,
            ["ready"] = true,
            ["revision"] = Revision,
            ["imageDigest"] = Digest,
            ["socketLoopback"] = true,
            ["publicStatus"] = 404,
            ["privateStatus"] = 500,
            ["probeCount"] = 1,
            ["diagnosticId"] = Diagnostic,
            ["incidentId"] = Incident,
            ["portForwardStopped"] = true,
            ["observationSeconds"] = 180,
            ["console"] = ThreeSeverities(),
            ["cloud"] = ThreeSeverities(),
        }),
    };

    private static JsonArray ThreeSeverities()
    {
        var warning = Record("WARNING", "Warning", "Legacy.Maliev.Web.Middleware.ObservabilityDiagnosticMiddleware", "ObservabilityPipelineProbe", null, true);
        warning["incidentId"] = null; // The actual source/Web466 warning does not own an incident yet.
        var error = Record("ERROR", "Error", "Microsoft.AspNetCore.Diagnostics.ExceptionHandlerMiddleware", null, "ObservabilityDiagnosticException", true);
        error["recordId"] = "55555555555555555555555555555555";
        error["incidentId"] = null;
        var critical = Record("CRITICAL", "Critical", "Legacy.Maliev.Web.Middleware.ErrorIncidentMiddleware", "ObservabilityDiagnosticFailure", "ObservabilityDiagnosticException", true);
        critical["recordId"] = "77777777777777777777777777777777";
        return new JsonArray(warning, error, critical);
    }

    private static JsonObject TwoPods()
    {
        var input = Complete();
        var second = input["pods"]![0]!.DeepClone();
        second["podUid"] = "88888888888888888888888888888888";
        second["diagnosticId"] = "99999999999999999999999999999999";
        second["incidentId"] = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
        foreach (string collection in new[] { "console", "cloud" })
        {
            foreach (var record in (JsonArray)second[collection]!)
            {
                record!["podUid"] = "88888888888888888888888888888888";
                record["diagnosticId"] = "99999999999999999999999999999999";
                if (record["incidentId"] is not null)
                {
                    record["incidentId"] = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
                }
            }
        }
        ((JsonArray)input["pods"]!).Add(second);
        ((JsonArray)input["servingPodUids"]!).Add("88888888888888888888888888888888");
        return input;
    }

    private static JsonObject Record(string severity, string level, string category, string? eventName, string? exceptionType, bool synthetic) => new()
    {
        ["recordId"] = "44444444444444444444444444444444",
        ["podUid"] = Pod,
        ["severity"] = severity,
        ["logLevel"] = level,
        ["category"] = category,
        ["eventName"] = eventName,
        ["exceptionType"] = exceptionType,
        ["synthetic"] = synthetic,
        ["diagnosticId"] = Diagnostic,
        ["traceId"] = "66666666666666666666666666666666",
        ["incidentId"] = Incident,
        ["occurredAtUtc"] = "2026-10-02T12:02:00Z",
    };

    private static async Task AssertUnavailableAsync(string input)
    {
        var result = await ValidateAsync(input);
        Assert.Equal(1, result.ExitCode);
        Assert.Equal("unavailable", result.Summary["visibility"]!.GetValue<string>());
        Assert.Null(result.Summary["actionSevereEvents"]);
        Assert.Null(result.Summary["baselineSevereEvents"]);
        Assert.Equal(3, result.Summary.Count);
    }

    private static async Task<(int ExitCode, JsonObject Summary)> ValidateAsync(string input)
    {
        string root = RepositoryContractTests.FindRepositoryRoot();
        string validator = Path.Combine(root, "scripts", "validate-production-observability.py");
        Assert.True(File.Exists(validator), "Offline operational evidence validator is not implemented.");
        ProcessStartInfo start = new(OperatingSystem.IsWindows() ? "python" : "python3")
        {
            RedirectStandardInput = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        start.ArgumentList.Add(validator);
        start.ArgumentList.Add("--now-utc");
        start.ArgumentList.Add("2026-10-02T12:03:00Z");
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(TestContext.Current.CancellationToken);
        timeout.CancelAfter(TimeSpan.FromSeconds(10));
        using Process process = Process.Start(start)!;
        try
        {
            Task<string> stdout = ReadBoundedAsync(process.StandardOutput, timeout.Token);
            Task<string> stderr = ReadBoundedAsync(process.StandardError, timeout.Token);
            try
            {
                await process.StandardInput.WriteAsync(input.AsMemory(), timeout.Token);
                process.StandardInput.Close();
            }
            catch (IOException) when (System.Text.Encoding.UTF8.GetByteCount(input) > 65536)
            {
                // The bounded consumer can reject/close stdin before an oversized
                // writer finishes. Still require its actual exit and fixed summary.
            }
            await process.WaitForExitAsync(timeout.Token);
            string output = await stdout;
            Assert.True((await stderr).Length == 0, "Offline validator wrote unexpected diagnostics; content withheld.");
            Assert.False(output.Contains("PRIVATE_SENTINEL_NOT_FOR_OUTPUT", StringComparison.Ordinal), "Rejected input reached output; content withheld.");
            Assert.InRange(output.Length, 1, 1024);
            var summary = Assert.IsType<JsonObject>(JsonNode.Parse(output));
            Assert.Equal(3, summary.Count);
            return (process.ExitCode, summary);
        }
        finally
        {
            if (!process.HasExited)
            {
                process.Kill(entireProcessTree: true);
                using var cleanup = new CancellationTokenSource(TimeSpan.FromSeconds(5));
                await process.WaitForExitAsync(cleanup.Token);
            }
        }
    }

    private static async Task<string> ReadBoundedAsync(StreamReader reader, CancellationToken cancellationToken)
    {
        var output = new System.Text.StringBuilder();
        var buffer = new char[256];
        int count;
        while ((count = await reader.ReadAsync(buffer.AsMemory(), cancellationToken)) != 0)
        {
            if (output.Length + count > 1024)
            {
                throw new InvalidOperationException("Offline validator output budget exceeded; content withheld.");
            }
            output.Append(buffer, 0, count);
        }
        return output.ToString();
    }
}
