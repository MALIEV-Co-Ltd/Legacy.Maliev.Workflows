using System.Text.Json;
using System.Text.RegularExpressions;
using Xunit;

namespace Legacy.Maliev.Workflows.Tests;

public sealed class AllServiceSourceCommitLedgerContractTests
{
    private static readonly string Root = FindRepositoryRoot();
    private static readonly Regex Sha = new("^[0-9a-f]{40}$", RegexOptions.CultureInvariant);

    [Fact]
    public void Source_f0640_failure_tracing_shared_owner_is_migrated_without_closing_other_owners()
    {
        using var resolutions = Load("migration/source-commit-resolutions.json");
        var record = Assert.Single(resolutions.RootElement.GetProperty("records").EnumerateArray(),
            candidate => candidate.GetProperty("sourceSha").GetString() ==
                "f0640fe0719b2eb6becda378bff08153d955be07");

        Assert.Equal("partial", record.GetProperty("status").GetString());
        var owners = record.GetProperty("ownerResolutions");
        var shared = owners.GetProperty("Legacy.Maliev.ServiceDefaults");
        Assert.Equal("migrated", shared.GetProperty("status").GetString());
        Assert.Equal("5c5f9479313710fa576f83d3b396442997a2fcf4",
            shared.GetProperty("mergedTargetSha").GetString());
        Assert.Contains("https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Workflows/issues/162",
            shared.GetProperty("issueUrls").EnumerateArray().Select(item => item.GetString()));
        foreach (int pullRequest in new[] { 32, 45, 49, 50 })
        {
            Assert.Contains($"https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.ServiceDefaults/pull/{pullRequest}",
                shared.GetProperty("prUrls").EnumerateArray().Select(item => item.GetString()));
        }
        Assert.Contains("https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.ServiceDefaults/actions/runs/36359872119",
            shared.GetProperty("validationEvidenceUrls").EnumerateArray().Select(item => item.GetString()));
        Assert.Contains("https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.ServiceDefaults/actions/runs/36377717135",
            shared.GetProperty("validationEvidenceUrls").EnumerateArray().Select(item => item.GetString()));
        var auth = owners.GetProperty("Legacy.Maliev.AuthService");
        Assert.Equal("pending", auth.GetProperty("status").GetString());
        Assert.Contains("https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.AuthService/pull/96",
            auth.GetProperty("prUrls").EnumerateArray().Select(item => item.GetString()));
        var country = owners.GetProperty("Legacy.Maliev.CountryService");
        Assert.Equal("migrated", country.GetProperty("status").GetString());
        Assert.Equal("df4aa56353949b43bd534fc7daf20ebb41c42106",
            country.GetProperty("mergedTargetSha").GetString());
        Assert.Contains("https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.CountryService/pull/27",
            country.GetProperty("prUrls").EnumerateArray().Select(item => item.GetString()));
        Assert.Contains("https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.CountryService/actions/runs/36384608409",
            country.GetProperty("validationEvidenceUrls").EnumerateArray().Select(item => item.GetString()));
        var quotation = owners.GetProperty("Legacy.Maliev.QuotationService");
        Assert.Equal("migrated", quotation.GetProperty("status").GetString());
        Assert.Equal("db1427dcc73e3d98f14f7192c36e3d13b72fc42a",
            quotation.GetProperty("mergedTargetSha").GetString());
        Assert.Contains("https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.QuotationService/pull/63",
            quotation.GetProperty("prUrls").EnumerateArray().Select(item => item.GetString()));
        Assert.Equal("pending", owners.GetProperty("Legacy.Maliev.Web").GetProperty("status").GetString());
        Assert.Equal("pending", owners.GetProperty("Legacy.Maliev.OrderService").GetProperty("status").GetString());
    }

    [Fact]
    public void Source_062953_Travelers_warning_fix_has_reviewed_Intranet_disposition()
    {
        using var resolutions = Load("migration/source-commit-resolutions.json");
        var record = Assert.Single(resolutions.RootElement.GetProperty("records").EnumerateArray(),
            candidate => candidate.GetProperty("sourceSha").GetString() ==
                "062953f6287d62015c4c57b17127e3901afd96f3");

        Assert.Equal("migrated", record.GetProperty("status").GetString());
        var intranet = record.GetProperty("ownerResolutions").GetProperty("Legacy.Maliev.Intranet");
        Assert.Equal("migrated", intranet.GetProperty("status").GetString());
        Assert.Equal("7378a4b65ad6b7023b5baa53839772bb51a1e687",
            intranet.GetProperty("mergedTargetSha").GetString());
        Assert.Contains("https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Intranet/issues/211",
            intranet.GetProperty("issueUrls").EnumerateArray().Select(item => item.GetString()));
        Assert.Contains("https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Intranet/pull/214",
            intranet.GetProperty("prUrls").EnumerateArray().Select(item => item.GetString()));
        Assert.Contains("https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Intranet/actions/runs/36381239567",
            intranet.GetProperty("validationEvidenceUrls").EnumerateArray().Select(item => item.GetString()));
    }

    [Theory]
    [InlineData("0e7e95216bc4c73495d3e64ae910f88d26f139b9")]
    [InlineData("e1cfd932ef2aee6a909a61c96d3df6803ceb6184")]
    [InlineData("b1c233dd42899b24821d69b773ea24bd9a84c9f2")]
    [InlineData("a0227738295a3bd39b7a56987534d22bc087cc94")]
    [InlineData("f007faa5054fae855104d954b8d207af7d0a5d95")]
    [InlineData("0c667c3173165c2b11cd2c71dfcb4523bfcbdd17")]
    [InlineData("9c1bc774fe8c5e9c12af08f22b532222c0182776")]
    [InlineData("68aab629a4133fbe4e31aed378141f9fc7233fb2")]
    [InlineData("ea0743c0c7e8653462eebe813af6c7a5dbfd8438")]
    public void Fdm_source_commits_remain_individually_tracked_without_false_completion(string sourceSha)
    {
        using var resolutions = Load("migration/source-commit-resolutions.json");
        var record = Assert.Single(resolutions.RootElement.GetProperty("records").EnumerateArray(),
            candidate => candidate.GetProperty("sourceSha").GetString() == sourceSha);

        Assert.Equal("pending", record.GetProperty("status").GetString());
        var web = record.GetProperty("ownerResolutions").GetProperty("Legacy.Maliev.Web");
        Assert.Equal("pending", web.GetProperty("status").GetString());
        Assert.Contains("https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Workflows/issues/164",
            web.GetProperty("issueUrls").EnumerateArray().Select(item => item.GetString()));
    }

    [Theory]
    [InlineData("5a3f24d9ecf4723ac49670e241c6c19d37b540fd", 371,
        "c4c076115aebcf3055b9792a879987cb6216c48c", 36367135684L)]
    [InlineData("07845568583107d38aab31ee8d1ef87e094ea57c", 372,
        "12be9f6894fbc951b137a3d845035643f9d60730", 36368526344L)]
    public void Single_owner_Web_pricing_slices_remain_partial_until_full_source_parity(
        string sourceSha, int pullRequest, string mergedSha, long validationRun)
    {
        using var resolutions = Load("migration/source-commit-resolutions.json");
        var record = Assert.Single(resolutions.RootElement.GetProperty("records").EnumerateArray(),
            candidate => candidate.GetProperty("sourceSha").GetString() == sourceSha);

        Assert.Equal("partial", record.GetProperty("status").GetString());
        var web = record.GetProperty("ownerResolutions").GetProperty("Legacy.Maliev.Web");
        Assert.Equal("partial", web.GetProperty("status").GetString());
        Assert.Equal(mergedSha, web.GetProperty("mergedTargetSha").GetString());
        Assert.Contains("https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Web/issues/275",
            web.GetProperty("issueUrls").EnumerateArray().Select(item => item.GetString()));
        Assert.Contains($"https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Web/pull/{pullRequest}",
            web.GetProperty("prUrls").EnumerateArray().Select(item => item.GetString()));
        Assert.Contains($"https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Web/actions/runs/{validationRun}",
            web.GetProperty("validationEvidenceUrls").EnumerateArray().Select(item => item.GetString()));
    }

    [Fact]
    public void Source_d6d06_Auth_async_callback_warning_has_equivalent_merged_boundary()
    {
        using var resolutions = Load("migration/source-commit-resolutions.json");
        var record = Assert.Single(resolutions.RootElement.GetProperty("records").EnumerateArray(),
            candidate => candidate.GetProperty("sourceSha").GetString() ==
                "d6d06a282125f01d119ac2beec7f8d335608328f");

        Assert.Equal("migrated", record.GetProperty("status").GetString());
        var auth = record.GetProperty("ownerResolutions").GetProperty("Legacy.Maliev.AuthService");
        Assert.Equal("migrated", auth.GetProperty("status").GetString());
        Assert.Equal("b328301b0ec901e6c0261cc29544e0b542a93197",
            auth.GetProperty("mergedTargetSha").GetString());
        Assert.Contains("https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.AuthService/pull/70",
            auth.GetProperty("prUrls").EnumerateArray().Select(item => item.GetString()));
        Assert.Contains("https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.AuthService/actions/runs/36360294396",
            auth.GetProperty("validationEvidenceUrls").EnumerateArray().Select(item => item.GetString()));
    }

    [Fact]
    public void Ownership_map_has_unambiguous_valid_rules()
    {
        using var document = Load("migration/source-path-owners.json");
        var root = document.RootElement;
        Assert.Equal(1, root.GetProperty("schemaVersion").GetInt32());
        Assert.Equal("MALIEV-Co-Ltd/maliev-web", root.GetProperty("sourceRepository").GetString());
        Assert.Equal(
            ["Legacy.Maliev.ContactService"],
            root.GetProperty("architecturalTargets").EnumerateArray().Select(item => item.GetString()!).ToArray());

        var patterns = new HashSet<string>(StringComparer.Ordinal);
        foreach (var rule in root.GetProperty("rules").EnumerateArray())
        {
            var pattern = Assert.IsType<string>(rule.GetProperty("pattern").GetString());
            Assert.True(patterns.Add(pattern), $"Duplicate mapping pattern: {pattern}");
            _ = new Regex(pattern, RegexOptions.CultureInvariant);

            var hasOwners = rule.TryGetProperty("owners", out var owners) && owners.GetArrayLength() > 0;
            var hasDisposition = rule.TryGetProperty("disposition", out var disposition)
                && disposition.GetString() is "approved-retirement" or "source-tooling-only";
            Assert.True(hasOwners ^ hasDisposition, $"Rule must define owners or an approved non-runtime disposition: {pattern}");
        }
    }

    [Theory]
    [InlineData("Maliev.Intranet/deploy.ps1", "approved-retirement", null)]
    [InlineData("Maliev.Intranet/package-lock.json", "approved-retirement", null)]
    [InlineData("tools/Validate-DeploymentScripts.ps1", "approved-retirement", null)]
    [InlineData("docs/superpowers/plans/2026-09-26-3d-printing-ctr-funnel.md", "migration-required", "Legacy.Maliev.Workflows")]
    [InlineData("docs/seo/2026-09-26-3d-printing-ctr-decision-pack.md", "migration-required", "Legacy.Maliev.Web")]
    public void Recent_source_paths_have_one_explicit_owner_or_retirement(
        string path,
        string expectedDisposition,
        string? expectedOwner)
    {
        using var document = Load("migration/source-path-owners.json");
        var matches = document.RootElement.GetProperty("rules").EnumerateArray()
            .Where(rule => Regex.IsMatch(path, rule.GetProperty("pattern").GetString()!, RegexOptions.CultureInvariant))
            .ToArray();

        var rule = Assert.Single(matches);
        var disposition = rule.TryGetProperty("disposition", out var value)
            ? value.GetString()
            : "migration-required";
        Assert.Equal(expectedDisposition, disposition);
        if (expectedOwner is not null)
        {
            Assert.Contains(expectedOwner, rule.GetProperty("owners").EnumerateArray().Select(owner => owner.GetString()));
        }
        else
        {
            Assert.False(string.IsNullOrWhiteSpace(rule.GetProperty("decision").GetString()));
        }
    }

    [Fact]
    public void Native_logging_and_WebApi_history_has_exact_reviewed_owner_transitions()
    {
        string[] reviewedShas =
        [
            "5fac706a7983a6d359b39acbd670e6800afe020e",
            "3d6506285a58671651d046e97a35fbb8885cea4f",
            "9e51e6c5da29de8e617b65b59d46882cde6d3b64",
            "7b311e4e7f0dd80be0441abc2625dab295179f1a",
            "03dc9a1271c16e6535934445e9dd6e3f30e8fffe",
            "5ac7d045c51194edd9e64d8564f1b726b001be34",
        ];
        string[] ownerSetTransitions =
        [
            "3d6506285a58671651d046e97a35fbb8885cea4f",
            "7b311e4e7f0dd80be0441abc2625dab295179f1a",
            "5ac7d045c51194edd9e64d8564f1b726b001be34",
        ];
        using var mapping = Load("migration/source-path-owners.json");
        using var ownership = Load("migration/source-commit-ledger.json");
        using var resolutions = Load("migration/source-commit-resolutions.json");
        var rules = mapping.RootElement.GetProperty("rules").EnumerateArray().ToArray();
        foreach (var path in new[]
        {
            "Maliev.NativeLogging/LoggingBuilderExtensions.cs",
            "Maliev.Service.WebApi/WebApiService.cs",
            "Maliev.Service.WebApi/Maliev.Service.WebApi.xml",
        })
        {
            var rule = Assert.Single(rules, candidate => Regex.IsMatch(path, candidate.GetProperty("pattern").GetString()!));
            Assert.Equal(["Legacy.Maliev.ServiceDefaults"],
                rule.GetProperty("owners").EnumerateArray().Select(owner => owner.GetString()!).ToArray());
        }

        var sharedRule = Assert.Single(rules, candidate =>
            Regex.IsMatch("Maliev.Common/Shared.cs", candidate.GetProperty("pattern").GetString()!));
        Assert.Equal(
            ["Legacy.Maliev.CompatibilityContracts", "Legacy.Maliev.ServiceDefaults"],
            sharedRule.GetProperty("owners").EnumerateArray().Select(owner => owner.GetString()!).ToArray());

        var affected = ownership.RootElement.GetProperty("records").EnumerateArray()
            .Where(record => record.GetProperty("classifications").EnumerateArray().Any(classification =>
                classification.GetProperty("path").GetString() is { } path &&
                (path.StartsWith("Maliev.NativeLogging/", StringComparison.Ordinal) ||
                 path.StartsWith("Maliev.Service.WebApi/", StringComparison.Ordinal))))
            .ToArray();
        Assert.Equal(reviewedShas.Order(StringComparer.Ordinal),
            affected.Select(record => record.GetProperty("commit").GetString()!).Order(StringComparer.Ordinal));
        foreach (var record in affected)
        {
            foreach (var classification in record.GetProperty("classifications").EnumerateArray().Where(classification =>
                classification.GetProperty("path").GetString() is { } path &&
                (path.StartsWith("Maliev.NativeLogging/", StringComparison.Ordinal) ||
                 path.StartsWith("Maliev.Service.WebApi/", StringComparison.Ordinal))))
            {
                Assert.Equal(["Legacy.Maliev.ServiceDefaults"],
                    classification.GetProperty("owners").EnumerateArray().Select(owner => owner.GetString()!).ToArray());
            }
        }

        var transitioned = resolutions.RootElement.GetProperty("records").EnumerateArray()
            .Where(record => record.TryGetProperty("ownerSetTransition", out _)).ToArray();
        Assert.Equal(ownerSetTransitions.Order(StringComparer.Ordinal),
            transitioned.Select(record => record.GetProperty("sourceSha").GetString()!).Order(StringComparer.Ordinal));
        foreach (var record in transitioned)
        {
            var transition = record.GetProperty("ownerSetTransition");
            Assert.Equal("Legacy.Maliev.CompatibilityContracts", transition.GetProperty("removedOwner").GetString());
            Assert.Equal("Legacy.Maliev.ServiceDefaults", transition.GetProperty("retainedOwner").GetString());
            Assert.Equal("https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Workflows/issues/138",
                transition.GetProperty("issueUrl").GetString());
            var priorIssueUrls = transition.GetProperty("priorIssueUrls").EnumerateArray()
                .Select(item => item.GetString()!).ToArray();
            Assert.Equal(record.GetProperty("sourceSha").GetString() ==
                "7b311e4e7f0dd80be0441abc2625dab295179f1a"
                    ? ["https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Workflows/issues/138"]
                    : [], priorIssueUrls);
            Assert.False(record.GetProperty("ownerResolutions").TryGetProperty("Legacy.Maliev.CompatibilityContracts", out _));
            var serviceDefaults = record.GetProperty("ownerResolutions")
                .GetProperty("Legacy.Maliev.ServiceDefaults");
            Assert.Equal(record.GetProperty("sourceSha").GetString() is
                "7b311e4e7f0dd80be0441abc2625dab295179f1a" or
                "5ac7d045c51194edd9e64d8564f1b726b001be34" ? "migrated" : "pending",
                serviceDefaults.GetProperty("status").GetString());
        }
        foreach (var sha in reviewedShas.Except(ownerSetTransitions, StringComparer.Ordinal))
        {
            var record = Assert.Single(resolutions.RootElement.GetProperty("records").EnumerateArray(),
                candidate => candidate.GetProperty("sourceSha").GetString() == sha);
            Assert.True(record.GetProperty("ownerResolutions")
                .TryGetProperty("Legacy.Maliev.CompatibilityContracts", out _));
            Assert.False(record.TryGetProperty("ownerSetTransition", out _));
        }
    }

    [Fact]
    public void Source_7b311_is_resolved_only_after_all_five_owners_have_merged_evidence()
    {
        using var resolutions = Load("migration/source-commit-resolutions.json");
        var record = Assert.Single(resolutions.RootElement.GetProperty("records").EnumerateArray(),
            candidate => candidate.GetProperty("sourceSha").GetString() ==
                "7b311e4e7f0dd80be0441abc2625dab295179f1a");

        Assert.Equal("migrated", record.GetProperty("status").GetString());
        var owners = record.GetProperty("ownerResolutions").EnumerateObject().ToArray();
        Assert.Equal(5, owners.Length);
        Assert.All(owners, owner =>
        {
            Assert.Equal("migrated", owner.Value.GetProperty("status").GetString());
            Assert.Matches(Sha, owner.Value.GetProperty("mergedTargetSha").GetString()!);
            Assert.NotEmpty(owner.Value.GetProperty("validationEvidenceUrls").EnumerateArray());
        });

        var web = Assert.Single(owners, owner => owner.Name == "Legacy.Maliev.Web").Value;
        Assert.Equal("caf92bdbb89acd18819f22f82d218632ac67f360",
            web.GetProperty("mergedTargetSha").GetString());
        Assert.Contains("https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Web/actions/runs/36352974809",
            web.GetProperty("validationEvidenceUrls").EnumerateArray().Select(item => item.GetString()));
    }

    [Fact]
    public void Source_5ac7_shared_logging_owner_is_proven_without_claiming_consumer_parity()
    {
        using var resolutions = Load("migration/source-commit-resolutions.json");
        var record = Assert.Single(resolutions.RootElement.GetProperty("records").EnumerateArray(),
            candidate => candidate.GetProperty("sourceSha").GetString() ==
                "5ac7d045c51194edd9e64d8564f1b726b001be34");

        Assert.Equal("partial", record.GetProperty("status").GetString());
        var owners = record.GetProperty("ownerResolutions");
        var accounting = owners.GetProperty("Legacy.Maliev.AccountingService");
        Assert.Equal("migrated", accounting.GetProperty("status").GetString());
        Assert.Equal("cb5f75c34d6783cebb705219a64b9fa3b71baf12",
            accounting.GetProperty("mergedTargetSha").GetString());
        Assert.Contains("https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.AccountingService/actions/runs/36360378615",
            accounting.GetProperty("validationEvidenceUrls").EnumerateArray().Select(item => item.GetString()));
        var defaults = owners.GetProperty("Legacy.Maliev.ServiceDefaults");
        Assert.Equal("migrated", defaults.GetProperty("status").GetString());
        Assert.Equal("d22f0e6f95254b10cf4fe891c8dce5df7c419f3f",
            defaults.GetProperty("mergedTargetSha").GetString());
        Assert.Contains("https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.ServiceDefaults/pull/47",
            defaults.GetProperty("prUrls").EnumerateArray().Select(item => item.GetString()));
        var notification = owners.GetProperty("Legacy.Maliev.NotificationService");
        Assert.Equal("migrated", notification.GetProperty("status").GetString());
        Assert.Equal("79a9184649f749de67c9b644857ce216e34cd8cb",
            notification.GetProperty("mergedTargetSha").GetString());
        Assert.Contains("https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.NotificationService/actions/runs/36355739408",
            notification.GetProperty("validationEvidenceUrls").EnumerateArray().Select(item => item.GetString()));
        var order = owners.GetProperty("Legacy.Maliev.OrderService");
        Assert.Equal("migrated", order.GetProperty("status").GetString());
        Assert.Equal("9617b32b63bf50ba24b187a099a507559011b5ef",
            order.GetProperty("mergedTargetSha").GetString());
        Assert.Contains("https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.OrderService/actions/runs/36357161937",
            order.GetProperty("validationEvidenceUrls").EnumerateArray().Select(item => item.GetString()));
        var appHost = owners.GetProperty("Legacy.Maliev.AppHost");
        Assert.Equal("migrated", appHost.GetProperty("status").GetString());
        Assert.Equal("3fc07638e818dbe33abf26fde199b238ad5452f4",
            appHost.GetProperty("mergedTargetSha").GetString());
        Assert.Contains("https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.AppHost/actions/runs/36356967445",
            appHost.GetProperty("validationEvidenceUrls").EnumerateArray().Select(item => item.GetString()));
        var auth = owners.GetProperty("Legacy.Maliev.AuthService");
        Assert.Equal("migrated", auth.GetProperty("status").GetString());
        Assert.Equal("371a6e8ec4338e975acc0029815ed8fd721021b9",
            auth.GetProperty("mergedTargetSha").GetString());
        Assert.Contains("https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.AuthService/actions/runs/36359697617",
            auth.GetProperty("validationEvidenceUrls").EnumerateArray().Select(item => item.GetString()));
        var country = owners.GetProperty("Legacy.Maliev.CountryService");
        Assert.Equal("migrated", country.GetProperty("status").GetString());
        Assert.Equal("f4577b8d08ef2e58d07a3e56a012876209fa7a1c",
            country.GetProperty("mergedTargetSha").GetString());
        Assert.Contains("https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.CountryService/actions/runs/36358731086",
            country.GetProperty("validationEvidenceUrls").EnumerateArray().Select(item => item.GetString()));
        var intranet = owners.GetProperty("Legacy.Maliev.Intranet");
        Assert.Equal("migrated", intranet.GetProperty("status").GetString());
        Assert.Equal("e245c1a544ee520acff0f517d3206c9439fe68ac",
            intranet.GetProperty("mergedTargetSha").GetString());
        Assert.Contains("https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Intranet/actions/runs/36357239217",
            intranet.GetProperty("validationEvidenceUrls").EnumerateArray().Select(item => item.GetString()));
        Assert.Contains(owners.EnumerateObject(), owner =>
            owner.Name != "Legacy.Maliev.ServiceDefaults" &&
            owner.Value.GetProperty("status").GetString() == "pending");
        Assert.Equal("pending", record.GetProperty("retirementApproval").GetProperty("status").GetString());
    }

    [Fact]
    public void Worker_only_source_commits_are_resolved_without_claiming_broader_additive_parity()
    {
        using var resolutions = Load("migration/source-commit-resolutions.json");
        var records = resolutions.RootElement.GetProperty("records").EnumerateArray().ToArray();
        foreach (var sha in new[]
        {
            "b36d919905ab063911dc5352ebb003c97af9a8b0",
            "7e76659f875eeaa745aeed1f8ea5508f88bcbaee",
            "f9c3ac3460925fe54833b87b209407efabba908c",
        })
        {
            var record = Assert.Single(records, candidate => candidate.GetProperty("sourceSha").GetString() == sha);
            Assert.Equal("migrated", record.GetProperty("status").GetString());
            var web = record.GetProperty("ownerResolutions").GetProperty("Legacy.Maliev.Web");
            Assert.Equal("migrated", web.GetProperty("status").GetString());
            Assert.Equal("d5780cc410ffe571ecc8f10a0ad1ac1830568410", web.GetProperty("mergedTargetSha").GetString());
            Assert.Contains("https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Web/pull/290",
                web.GetProperty("prUrls").EnumerateArray().Select(item => item.GetString()));
        }

        foreach (var sha in new[]
        {
            "744d3c5225e7cbf7a88af5c1f4fdb47442e2c325",
            "ea0743c0c7e8653462eebe813af6c7a5dbfd8438",
        })
        {
            var record = Assert.Single(records, candidate => candidate.GetProperty("sourceSha").GetString() == sha);
            Assert.NotEqual("migrated", record.GetProperty("status").GetString());
        }
    }

    [Fact]
    public void Source_7387_SCB_display_is_migrated_but_payment_account_data_is_pending()
    {
        using var resolutions = Load("migration/source-commit-resolutions.json");
        var record = Assert.Single(resolutions.RootElement.GetProperty("records").EnumerateArray(),
            candidate => candidate.GetProperty("sourceSha").GetString() ==
                "7387d9e88e4f1b1b254c48f5ab0933ec3bbf20d3");

        Assert.Equal("partial", record.GetProperty("status").GetString());
        var owners = record.GetProperty("ownerResolutions");
        var web = owners.GetProperty("Legacy.Maliev.Web");
        Assert.Equal("migrated", web.GetProperty("status").GetString());
        Assert.Equal("85bbefdd380f278ed949b05433d3055c2a602847",
            web.GetProperty("mergedTargetSha").GetString());
        Assert.Contains("https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Web/pull/287",
            web.GetProperty("prUrls").EnumerateArray().Select(item => item.GetString()));
        var data = owners.GetProperty("Legacy.Maliev.DataMigration");
        Assert.Equal("pending", data.GetProperty("status").GetString());
        Assert.Contains("https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.DataMigration/issues/201",
            data.GetProperty("issueUrls").EnumerateArray().Select(item => item.GetString()));
    }

    [Fact]
    public void Source_8ec87_ABS_heated_enclosure_energy_is_resolved_on_Web_main()
    {
        using var resolutions = Load("migration/source-commit-resolutions.json");
        var record = Assert.Single(resolutions.RootElement.GetProperty("records").EnumerateArray(),
            candidate => candidate.GetProperty("sourceSha").GetString() ==
                "8ec87e40c1104485537823bb5059833f2735cc9e");

        Assert.Equal("migrated", record.GetProperty("status").GetString());
        var web = record.GetProperty("ownerResolutions").GetProperty("Legacy.Maliev.Web");
        Assert.Equal("migrated", web.GetProperty("status").GetString());
        Assert.Equal("5f5fb73591fe980433c1771d6b8d7c93f86e2269",
            web.GetProperty("mergedTargetSha").GetString());
        Assert.Contains("https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Web/pull/368",
            web.GetProperty("prUrls").EnumerateArray().Select(item => item.GetString()));
        Assert.Contains("https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Web/actions/runs/36363602749",
            web.GetProperty("validationEvidenceUrls").EnumerateArray().Select(item => item.GetString()));
    }

    [Fact]
    public void Source_492577_web_no_prune_is_resolved_only_after_exact_main_validation()
    {
        using var resolutions = Load("migration/source-commit-resolutions.json");
        var record = Assert.Single(resolutions.RootElement.GetProperty("records").EnumerateArray(),
            candidate => candidate.GetProperty("sourceSha").GetString() ==
                "492577b8272a1286db48876840499078b27c0858");

        Assert.Equal("migrated", record.GetProperty("status").GetString());
        var web = record.GetProperty("ownerResolutions").GetProperty("Legacy.Maliev.Web");
        Assert.Equal("migrated", web.GetProperty("status").GetString());
        Assert.Equal("9f66db11194c30be03b1c707f0e90a35c661ea56",
            web.GetProperty("mergedTargetSha").GetString());
        Assert.Contains("https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Web/pull/365",
            web.GetProperty("prUrls").EnumerateArray().Select(item => item.GetString()));
        Assert.Contains("https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Web/actions/runs/36355748835",
            web.GetProperty("validationEvidenceUrls").EnumerateArray().Select(item => item.GetString()));
    }

    [Fact]
    public void Source_adf8_web_consent_regression_is_resolved_only_after_exact_main_validation()
    {
        using var resolutions = Load("migration/source-commit-resolutions.json");
        var record = Assert.Single(resolutions.RootElement.GetProperty("records").EnumerateArray(),
            candidate => candidate.GetProperty("sourceSha").GetString() ==
                "adf8c36b49171e6e15e0c6b9d9de982a598387be");

        Assert.Equal("migrated", record.GetProperty("status").GetString());
        var web = record.GetProperty("ownerResolutions").GetProperty("Legacy.Maliev.Web");
        Assert.Equal("migrated", web.GetProperty("status").GetString());
        Assert.Equal("35a0d5a72e97f5820cb9820ba975650df34a61d3",
            web.GetProperty("mergedTargetSha").GetString());
        Assert.Contains("https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Web/pull/367",
            web.GetProperty("prUrls").EnumerateArray().Select(item => item.GetString()));
        Assert.Contains("https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Web/actions/runs/36358523237",
            web.GetProperty("validationEvidenceUrls").EnumerateArray().Select(item => item.GetString()));
    }

    [Fact]
    public void Historical_ctr_plan_preserves_source_identity_and_non_release_boundary()
    {
        var record = File.ReadAllText(Path.Combine(Root, "migration", "historical-3d-printing-ctr-plan-2026-09-26.md"));
        Assert.Contains("a73acf2e4de9a611c7eda22cf6dbdae333d231cf", record, StringComparison.Ordinal);
        Assert.Contains("did not authorize publication", record, StringComparison.Ordinal);
        Assert.Contains("persisted quotation", record, StringComparison.Ordinal);
    }

    [Fact]
    public void Ledger_is_complete_structurally_and_fail_closed()
    {
        using var document = Load("migration/source-commit-ledger.json");
        var root = document.RootElement;
        Assert.Equal(2, root.GetProperty("schemaVersion").GetInt32());
        Assert.Equal("MALIEV-Co-Ltd/maliev-web", root.GetProperty("sourceRepository").GetString());
        Assert.Matches(Sha, root.GetProperty("sourceCheckpoint").GetString()!);
        var targets = root.GetProperty("legacyTargets");
        Assert.True(targets.EnumerateObject().Any());
        Assert.True(targets.TryGetProperty("Legacy.Maliev.ContactService", out _),
            "The extracted ContactService must retain target-SHA evidence even without a one-to-one source project.");
        foreach (var target in targets.EnumerateObject())
        {
            var mainSha = target.Value.GetProperty("mainSha").GetString()!;
            Assert.Matches(Sha, mainSha);
            Assert.Equal($"https://github.com/MALIEV-Co-Ltd/{target.Name}/commit/{mainSha}", target.Value.GetProperty("evidence").GetString());
        }

        var records = root.GetProperty("records").EnumerateArray().ToArray();
        Assert.Equal(root.GetProperty("commitCount").GetInt32(), records.Length);
        Assert.Equal(records.Length, root.GetProperty("nonMergeCommitCount").GetInt32() +
            root.GetProperty("mergeCommitCount").GetInt32());
        Assert.True(root.GetProperty("mergeCommitCount").GetInt32() > 0);
        Assert.NotEmpty(records);

        var commits = new HashSet<string>(StringComparer.Ordinal);
        for (var index = 0; index < records.Length; index++)
        {
            var record = records[index];
            Assert.Equal(index + 1, record.GetProperty("ordinal").GetInt32());
            var commit = record.GetProperty("commit").GetString()!;
            Assert.Matches(Sha, commit);
            Assert.True(commits.Add(commit), $"Duplicate source commit: {commit}");
            Assert.Equal($"https://github.com/MALIEV-Co-Ltd/maliev-web/commit/{commit}", record.GetProperty("sourceEvidence").GetString());

            _ = record.GetProperty("authoredAt").GetDateTimeOffset();
            var parents = record.GetProperty("parents").EnumerateArray().ToArray();
            Assert.Equal(parents.Length > 1, record.GetProperty("isMerge").GetBoolean());
            foreach (var parent in parents)
            {
                Assert.Matches(Sha, parent.GetString()!);
            }
            Assert.False(string.IsNullOrWhiteSpace(record.GetProperty("subject").GetString()));

            var classifications = record.GetProperty("classifications").EnumerateArray().ToArray();
            Assert.NotEmpty(classifications);
            foreach (var classification in classifications)
            {
                Assert.False(string.IsNullOrWhiteSpace(classification.GetProperty("path").GetString()));
                var disposition = classification.GetProperty("disposition").GetString();
                Assert.Contains(disposition, new[] { "migration-required", "approved-retirement", "source-tooling-only" });
                if (disposition == "migration-required")
                {
                    var owners = classification.GetProperty("owners").EnumerateArray().ToArray();
                    Assert.NotEmpty(owners);
                    Assert.All(owners, owner => Assert.True(targets.TryGetProperty(owner.GetString()!, out _), $"Missing target evidence for {owner.GetString()}"));
                }
                else
                {
                    Assert.False(string.IsNullOrWhiteSpace(classification.GetProperty("decision").GetString()));
                }
            }
        }
    }

    [Fact]
    public void Ledger_tracks_every_recent_source_commit_without_treating_retired_inputs_as_runtime()
    {
        using var document = Load("migration/source-commit-ledger.json");
        var records = document.RootElement.GetProperty("records").EnumerateArray().ToArray();
        foreach (var commit in new[]
        {
            "a73acf2e4de9a611c7eda22cf6dbdae333d231cf",
            "c97ced90bd8913a1686fec16405efd57c62d3176",
            "31ba7d7c9816330529c8c335939fde5d0fc4a632",
            "92f2263531971457cd9d71da41a653e91a1b6079",
            "de75a0e55240ee78053c8c87eb4a83b67cdd32f2",
            "0665dcd54788c037ee663ff90f32741014f0c81c",
            "3e38f9691b1c502755f1ab2b00ed90f8261eafef",
            "7435f6b8fde7cb06c439532f5aac0f8a31778175",
            "4198baa6b0e7903f2b9b6e3d5d68f9d2c2b5b0db",
            "3644a0d7850dcb82208887ae41d7ca931ea4e60e",
        })
        {
            Assert.Contains(records, record => record.GetProperty("commit").GetString() == commit);
        }

        var deployment = Assert.Single(records, record =>
            record.GetProperty("commit").GetString() == "7435f6b8fde7cb06c439532f5aac0f8a31778175");
        Assert.All(deployment.GetProperty("classifications").EnumerateArray(), classification =>
            Assert.Equal("approved-retirement", classification.GetProperty("disposition").GetString()));
        var dependency = Assert.Single(records, record =>
            record.GetProperty("commit").GetString() == "4198baa6b0e7903f2b9b6e3d5d68f9d2c2b5b0db");
        Assert.All(dependency.GetProperty("classifications").EnumerateArray(), classification =>
            Assert.Equal("approved-retirement", classification.GetProperty("disposition").GetString()));
        Assert.True(Assert.Single(records, record =>
            record.GetProperty("commit").GetString() == "3644a0d7850dcb82208887ae41d7ca931ea4e60e")
            .GetProperty("isMerge").GetBoolean());
    }

    [Fact]
    public void Resolution_companion_tracks_every_commit_without_claiming_unproven_parity()
    {
        using var ownership = Load("migration/source-commit-ledger.json");
        using var resolutions = Load("migration/source-commit-resolutions.json");
        var source = ownership.RootElement;
        var root = resolutions.RootElement;
        Assert.Equal(1, root.GetProperty("schemaVersion").GetInt32());
        Assert.Equal(source.GetProperty("sourceRepository").GetString(),
            root.GetProperty("sourceRepository").GetString());
        Assert.Equal(source.GetProperty("sourceCheckpoint").GetString(),
            root.GetProperty("sourceCheckpoint").GetString());
        var commits = source.GetProperty("records").EnumerateArray().ToArray();
        var records = root.GetProperty("records").EnumerateArray().ToArray();
        Assert.Equal(commits.Length, root.GetProperty("sourceCommitCount").GetInt32());
        Assert.Equal(commits.Length, records.Length);
        Assert.Equal(commits.Length,
            root.GetProperty("fullyResolvedCommitCount").GetInt32() +
            root.GetProperty("unresolvedCommitCount").GetInt32());
        Assert.False(root.GetProperty("complete").GetBoolean());
        Assert.True(root.GetProperty("unresolvedCommitCount").GetInt32() > 0);

        var seen = new HashSet<string>(StringComparer.Ordinal);
        for (var index = 0; index < commits.Length; index++)
        {
            var sourceCommit = commits[index];
            var record = records[index];
            var sha = record.GetProperty("sourceSha").GetString()!;
            Assert.Equal(sourceCommit.GetProperty("commit").GetString(), sha);
            Assert.True(seen.Add(sha));
            Assert.Equal(sourceCommit.GetProperty("isMerge").GetBoolean(),
                record.GetProperty("isMerge").GetBoolean());
            Assert.Contains(record.GetProperty("status").GetString(),
                new[] { "pending", "partial", "blocked", "migrated", "approved-retirement" });
            var expectedOwners = sourceCommit.GetProperty("classifications").EnumerateArray()
                .Where(item => item.GetProperty("disposition").GetString() == "migration-required")
                .SelectMany(item => item.GetProperty("owners").EnumerateArray().Select(owner => owner.GetString()!))
                .Distinct(StringComparer.Ordinal).Order(StringComparer.Ordinal).ToArray();
            var actualOwners = record.GetProperty("ownerResolutions").EnumerateObject()
                .Select(item => item.Name).Order(StringComparer.Ordinal).ToArray();
            Assert.Equal(expectedOwners, actualOwners);
            foreach (var owner in record.GetProperty("ownerResolutions").EnumerateObject())
            {
                var result = owner.Value;
                Assert.Contains(result.GetProperty("status").GetString(),
                    new[] { "pending", "partial", "blocked", "migrated" });
                if (result.GetProperty("status").GetString() is "partial" or "migrated")
                {
                    Assert.NotEmpty(result.GetProperty("issueUrls").EnumerateArray());
                    Assert.NotEmpty(result.GetProperty("prUrls").EnumerateArray());
                    Assert.Matches(Sha, result.GetProperty("mergedTargetSha").GetString()!);
                    Assert.NotEmpty(result.GetProperty("validationEvidenceUrls").EnumerateArray());
                }
            }
            var retirement = record.GetProperty("retirementApproval");
            if (retirement.ValueKind != JsonValueKind.Null &&
                retirement.GetProperty("status").GetString() == "approved")
            {
                Assert.False(string.IsNullOrWhiteSpace(retirement.GetProperty("reason").GetString()));
                Assert.StartsWith("https://", retirement.GetProperty("evidenceUrl").GetString());
            }
        }

        foreach (var sha in new[]
        {
            "c88a4e93c28b7306a5f2c353ee2ed1b8677ff7f8",
            "3f090e9488d91790636558d3ce59c7f046efa1d8",
            "ce8a2f4037bedf51df1aedde4aef531c2faff3c7",
            "d46b4d6a3fca8148792da1033c77d60d22d7b9d9",
            "49294cf81ec1940c433d9092af0b96f050298930",
            "027e733e8e7a5abebf975598fda86589ca034b32",
            "c97ced90bd8913a1686fec16405efd57c62d3176",
            "31ba7d7c9816330529c8c335939fde5d0fc4a632",
            "92f2263531971457cd9d71da41a653e91a1b6079",
            "de75a0e55240ee78053c8c87eb4a83b67cdd32f2",
            "0665dcd54788c037ee663ff90f32741014f0c81c",
            "3e38f9691b1c502755f1ab2b00ed90f8261eafef",
            "89ddd5a49ae7e781ca29225b8eae50fb9c2b1d0e",
            "3e95e397f7180356f0b5a8acfeed0119d1db62ad",
            "7ebbc97b0b93c6f71b8b5079ebd404e42c259338",
            "99462c12c33fc62da281fc90fc61a8ee458d0d7a",
        })
        {
            var migrated = Assert.Single(records, record => record.GetProperty("sourceSha").GetString() == sha);
            Assert.Equal("migrated", migrated.GetProperty("status").GetString());
            Assert.All(migrated.GetProperty("ownerResolutions").EnumerateObject(), owner =>
                Assert.Equal("migrated", owner.Value.GetProperty("status").GetString()));
        }

        var qualificationContract = Assert.Single(records, record =>
            record.GetProperty("sourceSha").GetString() == "362308b605ff94878f684258ade46c67ae0b08ee");
        Assert.Equal("partial", qualificationContract.GetProperty("status").GetString());
        var qualifications = qualificationContract.GetProperty("ownerResolutions");
        Assert.Equal("migrated", qualifications.GetProperty("Legacy.Maliev.QuotationService")
            .GetProperty("status").GetString());
        Assert.Equal("pending", qualifications.GetProperty("Legacy.Maliev.DataMigration")
            .GetProperty("status").GetString());
    }

    [Fact]
    public void Generator_is_present_and_read_only_against_source()
    {
        var script = File.ReadAllText(Path.Combine(Root, "scripts", "New-SourceCommitLedger.ps1"));
        Assert.Contains("git -C $SourceRepository", script, StringComparison.Ordinal);
        Assert.DoesNotContain("git -C $SourceRepository fetch", script, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("git -C $SourceRepository pull", script, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("git -C $SourceRepository checkout", script, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("git -C $SourceRepository reset", script, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("git -C $SourceRepository clean", script, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("rev-list --reverse --no-merges", script, StringComparison.OrdinalIgnoreCase);
        Assert.Contains("Invoke-SourceGit diff --name-only $parents[0] $commit", script, StringComparison.Ordinal);
        Assert.Contains("Invoke-SourceGit ls-remote origin refs/heads/main", script, StringComparison.Ordinal);
        Assert.Contains("git -C $repositoryPath ls-remote origin refs/heads/main", script, StringComparison.Ordinal);
        Assert.DoesNotContain("git -C $repositoryPath fetch", script, StringComparison.OrdinalIgnoreCase);
        Assert.Contains("$mapping.architecturalTargets", script, StringComparison.Ordinal);

        var resolutionScript = File.ReadAllText(Path.Combine(Root, "scripts", "New-SourceCommitResolutionLedger.ps1"));
        Assert.Contains("git -C $SourceRepository ls-remote origin refs/heads/main", resolutionScript, StringComparison.Ordinal);
        Assert.DoesNotContain("git -C $SourceRepository fetch", resolutionScript, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("git -C $SourceRepository reset", resolutionScript, StringComparison.OrdinalIgnoreCase);
        Assert.Contains("merge-base --is-ancestor", resolutionScript, StringComparison.Ordinal);
    }

    private static JsonDocument Load(string relativePath) =>
        JsonDocument.Parse(File.ReadAllText(Path.Combine(Root, relativePath.Replace('/', Path.DirectorySeparatorChar))));

    private static string FindRepositoryRoot()
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);
        while (directory is not null && !File.Exists(Path.Combine(directory.FullName, "Legacy.Maliev.Workflows.slnx")))
        {
            directory = directory.Parent;
        }

        return directory?.FullName ?? throw new InvalidOperationException("Repository root was not found.");
    }
}
