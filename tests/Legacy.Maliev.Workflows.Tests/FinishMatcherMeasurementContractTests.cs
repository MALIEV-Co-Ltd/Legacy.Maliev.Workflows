using System.Text.Json;
using Xunit;

namespace Legacy.Maliev.Workflows.Tests;

public sealed class FinishMatcherMeasurementContractTests
{
    [Fact]
    public void FinishMatcherContract_DiagnosticEventsKeepScalarPrivacyBoundary()
    {
        var path = Path.Combine(RepositoryContractTests.FindRepositoryRoot(), "migration", "finish-matcher-measurement-contract.json");
        using var contract = JsonDocument.Parse(File.ReadAllText(path));
        var root = contract.RootElement;

        Assert.Equal(1, root.GetProperty("schemaVersion").GetInt32());
        Assert.Equal("7055e4e5f64f8e405033509de324f57362868200", root.GetProperty("sourceSha").GetString());
        Assert.Equal("runtime-migrated-analytics-release-unverified", root.GetProperty("status").GetString());
        Assert.Equal("generate_lead", root.GetProperty("outcomeEvent").GetString());
        Assert.False(root.GetProperty("adsConversion").GetBoolean());
        Assert.False(root.GetProperty("ga4KeyEvent").GetBoolean());

        var events = root.GetProperty("diagnosticEvents").EnumerateArray().ToArray();
        Assert.Equal(new[]
        {
            "finish_matcher_viewed", "finish_matcher_started", "finish_matcher_recommendation_selected",
            "finish_matcher_guidance_opened", "finish_matcher_quote_clicked", "finish_matcher_error",
        }, events.Select(item => item.GetProperty("name").GetString()));
        string[][] expectedParameters =
        [
            [],
            ["input_method"],
            ["step_number", "selection_type", "sheen", "match_quality"],
            ["guidance_topic"],
            ["step_number", "selection_type", "sheen", "match_quality", "input_method", "has_pantone"],
            ["failure_category", "input_method"],
        ];
        for (var index = 0; index < events.Length; index++)
        {
            Assert.Equal(expectedParameters[index], events[index].GetProperty("parameters")
                .EnumerateArray().Select(item => item.GetString()));
        }

        var common = root.GetProperty("commonParameters").EnumerateArray()
            .Select(item => item.GetString()!).ToArray();
        Assert.Equal(new[] { "service_id", "intent", "locale", "source" }, common);
        var allowedParameters = common.Concat(events.SelectMany(item => item.GetProperty("parameters")
            .EnumerateArray().Select(value => value.GetString()!))).ToHashSet(StringComparer.Ordinal);
        var prohibited = root.GetProperty("prohibitedPayloads").EnumerateArray()
            .Select(item => item.GetString()!).ToArray();
        Assert.Empty(allowedParameters.Intersect(prohibited, StringComparer.Ordinal));
        Assert.Contains("has_pantone", allowedParameters);
        Assert.DoesNotContain("pantone_code", allowedParameters);
        Assert.DoesNotContain("customer_text", allowedParameters);
        Assert.DoesNotContain("url_query", allowedParameters);

        var values = root.GetProperty("allowedValues");
        Assert.Equal(new[]
        {
            "failure_category", "guidance_topic", "input_method", "intent", "locale", "match_quality",
            "selection_type", "service_id", "sheen", "source",
        }, values.EnumerateObject().Select(item => item.Name).Order(StringComparer.Ordinal));
        Assert.Equal(new[] { "en", "th" }, values.GetProperty("locale").EnumerateArray()
            .Select(item => item.GetString()));
        Assert.Equal(new[] { "close", "noticeable", "large_difference" },
            values.GetProperty("match_quality").EnumerateArray().Select(item => item.GetString()));
    }

    [Fact]
    public void FinishMatcherGuide_KeepsExternalTagValidationPending()
    {
        var path = Path.Combine(RepositoryContractTests.FindRepositoryRoot(), "migration", "finish-matcher-measurement.md");
        var guide = File.ReadAllText(path);

        Assert.Contains("7055e4e5f64f8e405033509de324f57362868200", guide, StringComparison.Ordinal);
        Assert.Contains("does **not** say GTM or GA4 is live", guide, StringComparison.Ordinal);
        Assert.Contains("post-persistence", guide, StringComparison.Ordinal);
        Assert.Contains("denied consent", guide, StringComparison.Ordinal);
        Assert.DoesNotContain("C:\\Users\\", guide, StringComparison.OrdinalIgnoreCase);
    }
}
