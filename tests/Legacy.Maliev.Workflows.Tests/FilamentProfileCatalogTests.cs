using System.Text.Json.Nodes;
using Legacy.Maliev.AdditiveBenchmark;
using Xunit;

namespace Legacy.Maliev.Workflows.Tests;

public sealed class FilamentProfileCatalogTests
{
    [Fact]
    public void Catalog_SyntheticCoverageAndSubmittedEligibility_PreservesRecordFields()
    {
        JsonObject catalog = Catalog(Entry("PA12"), Entry("ABS-FR"));
        FilamentProfileCatalogValidation result = FilamentProfileCatalogValidator.Validate(catalog.ToJsonString(), ["ABS-FR", "PA12"]);
        Assert.True(result.IsValid, string.Join(',', result.Errors));
        Assert.Empty(result.Errors);
        Assert.Equal(new[] { "ABS-FR", "PA12" }, result.MaterialKeys);
        Assert.All(result.Entries, entry => Assert.True(entry.OperatorApproved && entry.ExactMaterialMatch && entry.AutomationEligible));
        Assert.Equal(new FilamentProfileCatalogEntry("PA12", "synthetic-profile", new string('A', 64), true, true, true), result.Entries[0]);
    }

    [Theory]
    [InlineData(false, false, false)]
    [InlineData(false, false, true)]
    [InlineData(false, true, false)]
    [InlineData(false, true, true)]
    [InlineData(true, false, false)]
    [InlineData(true, false, true)]
    [InlineData(true, true, false)]
    [InlineData(true, true, true)]
    public void Catalog_EligibleClaim_RequiresExactApprovedProfile(bool exact, bool approved, bool profile)
    {
        JsonObject entry = Entry("synthetic");
        entry["exactMaterialMatch"] = exact;
        entry["operatorApproved"] = approved;
        entry["profileId"] = profile ? "synthetic-profile" : null;
        entry["resolvedSha256"] = profile ? new string('A', 64) : null;
        FilamentProfileCatalogValidation result = FilamentProfileCatalogValidator.Validate(Catalog(entry).ToJsonString(), ["synthetic"]);
        Assert.Equal(exact && approved && profile, result.IsValid);
    }

    [Fact]
    public void Catalog_UnresolvedIneligibleDecisionAndCaseInsensitiveCoverage_RemainValid()
    {
        JsonObject entry = Entry("synthetic");
        entry["profileId"] = null;
        entry["resolvedSha256"] = null;
        entry["automationEligible"] = false;
        FilamentProfileCatalogValidation result = FilamentProfileCatalogValidator.Validate(Catalog(entry).ToJsonString(), ["SYNTHETIC", "synthetic"]);
        Assert.True(result.IsValid);
        Assert.Single(result.Entries);
        Assert.Null(result.Entries[0].ProfileId);
        Assert.Null(result.Entries[0].ResolvedSha256);
        Assert.False(result.Entries[0].AutomationEligible);
    }

    [Theory]
    [InlineData("missing-material")]
    [InlineData("unexpected-material")]
    [InlineData("case-duplicate")]
    [InlineData("profile-only")]
    [InlineData("hash-only")]
    [InlineData("empty-profile")]
    [InlineData("bad-boolean")]
    [InlineData("root-array")]
    [InlineData("entry-array")]
    [InlineData("version-number")]
    [InlineData("slicer-number")]
    [InlineData("slicer-version-number")]
    [InlineData("bad-version")]
    [InlineData("bad-slicer")]
    [InlineData("material-number")]
    public void Catalog_InvalidShapeOrCoverage_ReturnsInvalidWithoutFallback(string mutation)
    {
        JsonObject entry = Entry("synthetic");
        JsonObject catalog = Catalog(entry);
        string[] expected = ["synthetic"];
        switch (mutation)
        {
            case "missing-material": expected = ["synthetic", "absent"]; break;
            case "unexpected-material": expected = []; break;
            case "case-duplicate": catalog["entries"]!.AsArray().Add(Entry("SYNTHETIC")); break;
            case "profile-only": entry["resolvedSha256"] = null; break;
            case "hash-only": entry["profileId"] = null; break;
            case "empty-profile": entry["profileId"] = " "; break;
            case "bad-boolean": entry["operatorApproved"] = "true"; break;
            case "entry-array": catalog["entries"]![0] = new JsonArray(); break;
            case "version-number": catalog["schemaVersion"] = 1; break;
            case "slicer-number": catalog["slicer"] = 1; break;
            case "slicer-version-number": catalog["slicerVersion"] = 1; break;
            case "bad-version": catalog["schemaVersion"] = "2.0"; break;
            case "bad-slicer": catalog["slicer"] = "unknown"; break;
            case "material-number": entry["materialKey"] = 1; break;
        }
        string json = mutation == "root-array" ? "[]" : catalog.ToJsonString();
        FilamentProfileCatalogValidation result = FilamentProfileCatalogValidator.Validate(json, expected);
        Assert.False(result.IsValid);
        Assert.NotEmpty(result.Errors);
    }

    [Theory]
    [InlineData("lowercase")]
    [InlineData("short")]
    [InlineData("long")]
    [InlineData("nonhex")]
    [InlineData("final-lf")]
    public void Catalog_DigestMustBeExactlyUppercase64Hex(string invalid)
    {
        JsonObject entry = Entry("synthetic");
        entry["resolvedSha256"] = invalid switch
        {
            "lowercase" => new string('a', 64),
            "short" => new string('A', 63),
            "long" => new string('A', 65),
            "nonhex" => new string('Z', 64),
            _ => new string('A', 64) + "\n",
        };
        Assert.False(FilamentProfileCatalogValidator.Validate(Catalog(entry).ToJsonString(), ["synthetic"]).IsValid);
    }

    [Theory]
    [InlineData("malformed")]
    [InlineData("duplicate-root")]
    [InlineData("duplicate-entry")]
    [InlineData("json-bytes")]
    [InlineData("json-depth")]
    [InlineData("entry-count")]
    [InlineData("expected-count")]
    [InlineData("expected-text")]
    [InlineData("material-text")]
    [InlineData("profile-text")]
    public void Catalog_AmbiguousOrOversizedInput_IsInvalid(string mutation)
    {
        JsonObject catalog = Catalog(Entry("synthetic"));
        string json = catalog.ToJsonString();
        string[] expected = ["synthetic"];
        switch (mutation)
        {
            case "malformed": json = "{"; break;
            case "duplicate-root": json = json.Replace("\"schemaVersion\":\"1.0\"", "\"schemaVersion\":\"2.0\",\"schemaVersion\":\"1.0\"", StringComparison.Ordinal); break;
            case "duplicate-entry": json = json.Replace("\"operatorApproved\":true", "\"operatorApproved\":false,\"operatorApproved\":true", StringComparison.Ordinal); break;
            case "json-bytes": json = "{" + new string(' ', 4 * 1024 * 1024); break;
            case "json-depth": json = new string('[', 65) + "0" + new string(']', 65); break;
            case "entry-count": json = Catalog(Enumerable.Range(0, 257).Select(index => Entry($"synthetic-{index}")).ToArray()).ToJsonString(); break;
            case "expected-count": expected = Enumerable.Repeat("synthetic", 257).ToArray(); break;
            case "expected-text": expected = [new string('ก', 86)]; break;
            case "material-text": catalog["entries"]![0]!["materialKey"] = new string('ก', 86); json = catalog.ToJsonString(); break;
            case "profile-text": catalog["entries"]![0]!["profileId"] = new string('ก', 342); json = catalog.ToJsonString(); break;
        }
        FilamentProfileCatalogValidation result = FilamentProfileCatalogValidator.Validate(json, expected);
        Assert.False(result.IsValid);
        Assert.NotEmpty(result.Errors);
    }

    [Fact]
    public void Catalog_UnboundedExpectedEnumerable_StopsAfter257Observations()
    {
        int observations = 0;
        IEnumerable<string> Keys()
        {
            while (true)
            {
                observations++;
                yield return "synthetic";
            }
        }
        FilamentProfileCatalogValidation result = FilamentProfileCatalogValidator.Validate(Catalog(Entry("synthetic")).ToJsonString(), Keys());
        Assert.False(result.IsValid);
        Assert.Equal(257, observations);
    }

    private static JsonObject Catalog(params JsonObject[] entries) => new()
    {
        ["schemaVersion"] = "1.0",
        ["slicer"] = "Bambu Studio",
        ["slicerVersion"] = "synthetic-version",
        ["entries"] = new JsonArray(entries.Select(entry => (JsonNode)entry).ToArray()),
    };

    private static JsonObject Entry(string key) => new()
    {
        ["materialKey"] = key,
        ["profileId"] = "synthetic-profile",
        ["resolvedSha256"] = new string('A', 64),
        ["exactMaterialMatch"] = true,
        ["operatorApproved"] = true,
        ["automationEligible"] = true,
    };
}
