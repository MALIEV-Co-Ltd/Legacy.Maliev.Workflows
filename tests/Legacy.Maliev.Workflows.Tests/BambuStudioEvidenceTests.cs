using System.Text.Json;
using System.Text.Json.Nodes;
using Legacy.Maliev.AdditiveBenchmark;
using Xunit;

namespace Legacy.Maliev.Workflows.Tests;

public sealed class BambuStudioEvidenceTests
{
    private const string Result = """
        {"return_code":0,"layer_height":0.2,"sparse_infill_density":15,"wall_loops":3,
         "sliced_plates":[{"main_predication":10,"total_predication":12,"filaments":[{"total_used_g":2},{"total_used_g":3}]},
                          {"main_predication":20,"total_predication":25,"filaments":[{"total_used_g":4}]}]}
        """;

    [Fact]
    public void Result_MultiplePlates_PreservesVendorFieldsMetricsAndPublicRecordShape()
    {
        BambuStudioSliceMetrics metrics = BambuStudioResultParser.Parse(Result);
        Assert.Equal(new BambuStudioSliceMetrics(30, 37, 7, 9, 0.2, 15, 3, 2), metrics);
        using JsonDocument wire = JsonDocument.Parse(JsonSerializer.Serialize(metrics));
        Assert.Equal(new[] { "ModelSeconds", "TotalSeconds", "PreparationSeconds", "TotalMaterialGrams",
            "LayerHeightMillimetres", "SparseInfillPercent", "WallLoops", "PlateCount" },
            wire.RootElement.EnumerateObject().Select(property => property.Name));
    }

    [Theory]
    [InlineData("root-array")]
    [InlineData("return-string")]
    [InlineData("missing-return")]
    [InlineData("failed-return")]
    [InlineData("empty-plates")]
    [InlineData("plate-array")]
    [InlineData("missing-model")]
    [InlineData("model-string")]
    [InlineData("negative-time")]
    [InlineData("plate-inverted")]
    [InlineData("empty-filaments")]
    [InlineData("filament-array")]
    [InlineData("material-null")]
    [InlineData("material-negative")]
    [InlineData("layer-zero")]
    [InlineData("infill-negative")]
    [InlineData("wall-zero")]
    [InlineData("wall-fraction")]
    public void Result_InvalidStructureOrMetric_RejectsWithoutZeroFallback(string mutation)
    {
        JsonObject root = JsonNode.Parse(Result)!.AsObject();
        JsonObject plate = root["sliced_plates"]![0]!.AsObject();
        JsonObject filament = plate["filaments"]![0]!.AsObject();
        string json;
        switch (mutation)
        {
            case "root-array": json = "[]"; break;
            case "return-string": root["return_code"] = "0"; json = root.ToJsonString(); break;
            case "missing-return": root.Remove("return_code"); json = root.ToJsonString(); break;
            case "failed-return": root["return_code"] = 4; root["error_string"] = "sensitive-customer-path"; json = root.ToJsonString(); break;
            case "empty-plates": root["sliced_plates"] = new JsonArray(); json = root.ToJsonString(); break;
            case "plate-array": root["sliced_plates"]![0] = new JsonArray(); json = root.ToJsonString(); break;
            case "missing-model": plate.Remove("main_predication"); json = root.ToJsonString(); break;
            case "model-string": plate["main_predication"] = "10"; json = root.ToJsonString(); break;
            case "negative-time": plate["total_predication"] = -1; json = root.ToJsonString(); break;
            case "plate-inverted": plate["total_predication"] = 9; json = root.ToJsonString(); break;
            case "empty-filaments": plate["filaments"] = new JsonArray(); json = root.ToJsonString(); break;
            case "filament-array": plate["filaments"]![0] = new JsonArray(); json = root.ToJsonString(); break;
            case "material-null": filament["total_used_g"] = null; json = root.ToJsonString(); break;
            case "material-negative": filament["total_used_g"] = -1; json = root.ToJsonString(); break;
            case "layer-zero": root["layer_height"] = 0; json = root.ToJsonString(); break;
            case "infill-negative": root["sparse_infill_density"] = -1; json = root.ToJsonString(); break;
            case "wall-zero": root["wall_loops"] = 0; json = root.ToJsonString(); break;
            default: root["wall_loops"] = 1.5; json = root.ToJsonString(); break;
        }
        InvalidDataException failure = Assert.Throws<InvalidDataException>(() => BambuStudioResultParser.Parse(json));
        Assert.DoesNotContain("sensitive-customer-path", failure.Message);
    }

    [Theory]
    [InlineData("duplicate-root")]
    [InlineData("duplicate-nested")]
    [InlineData("malformed")]
    [InlineData("model-overflow")]
    [InlineData("material-overflow")]
    [InlineData("nonfinite-field")]
    public void Result_AmbiguousOrNonfiniteEvidence_Rejects(string mutation)
    {
        string json = mutation switch
        {
            "duplicate-root" => Result.Replace("\"return_code\":0", "\"return_code\":5,\"return_code\":0", StringComparison.Ordinal),
            "duplicate-nested" => Result.Replace("\"total_used_g\":2", "\"total_used_g\":8,\"total_used_g\":2", StringComparison.Ordinal),
            "malformed" => "{",
            "model-overflow" => Result.Replace("\"main_predication\":10", "\"main_predication\":1e308", StringComparison.Ordinal)
                .Replace("\"main_predication\":20", "\"main_predication\":1e308", StringComparison.Ordinal)
                .Replace("\"total_predication\":12", "\"total_predication\":1e308", StringComparison.Ordinal)
                .Replace("\"total_predication\":25", "\"total_predication\":1e308", StringComparison.Ordinal),
            "material-overflow" => Result.Replace("\"total_used_g\":2", "\"total_used_g\":1e308", StringComparison.Ordinal)
                .Replace("\"total_used_g\":3", "\"total_used_g\":1e308", StringComparison.Ordinal),
            _ => Result.Replace("\"total_used_g\":2", "\"total_used_g\":1e999", StringComparison.Ordinal),
        };
        Assert.Throws<InvalidDataException>(() => BambuStudioResultParser.Parse(json));
    }

    [Fact]
    public void GCode_SourceRegression_TracksModesResetsToolsArcsAndAmbiguity()
    {
        const string gcode = """
            M82
            ; FEATURE: Outer wall
            G1 X10 E2
            G1 E1.5
            G92 E0
            T1
            ; FEATURE: Support
            G2 X20 Y10 I5 J0 E3
            M83
            G1 E-0.4
            G1 X30 E1.2
            ; FEATURE: Custom
            G1 X31 E0.2
            """;
        GCodeExtrusionEvidence evidence = BambuStudioResultParser.ParseGCodeEvidence(gcode);
        Assert.Equal(6.4, evidence.TotalPositiveExtrusionMillimetres, 6);
        Assert.Equal(4.2, evidence.SupportExtrusionMillimetres, 6);
        Assert.Null(evidence.SupportExtrusionMillimetresForCertification);
        Assert.Equal(new[] { "ambiguous_feature_role" }, evidence.ReasonCodes);
    }

    [Theory]
    [InlineData("M82\n; FEATURE: Support\nG0 E2\nG1 E1\nG92 E0\nG3 E4", 6)]
    [InlineData("M83\r\n; FEATURE: Support interface\r\nG1 E2\r\nG2 E3", 5)]
    [InlineData("M82\r; FEATURE: Support\rT0\rG1 E2\rT1\rG1 E3\rT0\rG1 E4", 7)]
    [InlineData("M83\n; FEATURE: Support\nG1 E1e-2 ; E900", 0.01)]
    [InlineData("; FEATURE: Support\nG1 X1e2", 0)]
    public void GCode_SupportedForms_PreserveFiniteSupportEvidence(string input, double expected)
    {
        GCodeExtrusionEvidence evidence = BambuStudioResultParser.ParseGCodeEvidence(input);
        Assert.Equal(expected, evidence.TotalPositiveExtrusionMillimetres, 6);
        Assert.Equal(expected, evidence.SupportExtrusionMillimetres, 6);
        Assert.Equal(expected, evidence.SupportExtrusionMillimetresForCertification!.Value, 6);
        Assert.Empty(evidence.ReasonCodes);
    }

    [Theory]
    [InlineData("G1 E2", "missing_feature_role")]
    [InlineData("; FEATURE: Custom\nG1 E2", "ambiguous_feature_role")]
    [InlineData("; FEATURE: Support\nG01 E2", "unsupported_extrusion_command")]
    [InlineData("; FEATURE: Support\nG1E2", "unsupported_extrusion_command")]
    [InlineData("; FEATURE: Support\nG1 X0E2", "unsupported_extrusion_command")]
    [InlineData("; FEATURE: Support\nG1 X0\tE2", "unsupported_extrusion_command")]
    [InlineData("; FEATURE: Support\ng1 X0E2", "unsupported_extrusion_command")]
    [InlineData("; FEATURE: Support\nG01 X0E2", "unsupported_extrusion_command")]
    [InlineData("; FEATURE: Support\ng01 x0E2", "unsupported_extrusion_command")]
    [InlineData("; FEATURE: Support\nG92oops E2", "unsupported_extrusion_command")]
    public void GCode_UnclearEvidence_LeavesCertificationUnavailable(string input, string reason)
    {
        GCodeExtrusionEvidence evidence = BambuStudioResultParser.ParseGCodeEvidence(input);
        Assert.Null(evidence.SupportExtrusionMillimetresForCertification);
        Assert.Contains(reason, evidence.ReasonCodes);
        Assert.True(double.IsFinite(evidence.TotalPositiveExtrusionMillimetres));
    }

    [Theory]
    [InlineData("G1 E1 E2")]
    [InlineData("G1 E")]
    [InlineData("G1 Ebad")]
    [InlineData("G1 ENaN")]
    [InlineData("G1 EInfinity")]
    [InlineData("G1 E1e999")]
    [InlineData("T64")]
    [InlineData("T-1")]
    [InlineData("; FEATURE: Support\nT2147483648\nG1 E2")]
    [InlineData("; FEATURE: Support\nT999999999999\nG1 E2")]
    [InlineData("; FEATURE: Support\nt999999999999\nG1 E2")]
    [InlineData("M83\nG1 E1e308\nG1 E1e308")]
    [InlineData("G92 E-1e308\nG1 E1e308")]
    public void GCode_InvalidOrNonfiniteExtrusion_Rejects(string input)
    {
        Assert.Throws<InvalidDataException>(() => BambuStudioResultParser.ParseGCodeEvidence(input));
    }

    [Theory]
    [InlineData("json-bytes")]
    [InlineData("gcode-bytes")]
    [InlineData("unicode-bytes")]
    [InlineData("lines")]
    [InlineData("line-length")]
    [InlineData("tokens")]
    public void Evidence_AdmissionLimits_RejectBeforePublishing(string limit)
    {
        if (limit == "json-bytes")
        {
            Assert.Throws<InvalidDataException>(() => BambuStudioResultParser.Parse("{" + new string(' ', BambuStudioResultParser.MaximumInputBytes)));
            return;
        }
        string input = limit switch
        {
            "gcode-bytes" => new string(';', BambuStudioResultParser.MaximumInputBytes + 1),
            "unicode-bytes" => new string('ก', BambuStudioResultParser.MaximumInputBytes / 3 + 1),
            "lines" => string.Concat(Enumerable.Repeat(";\n", 65537)),
            "line-length" => ";" + new string('a', 16384),
            _ => "G1 " + string.Concat(Enumerable.Repeat("X0 ", 128)) + "E1",
        };
        Assert.Throws<InvalidDataException>(() => BambuStudioResultParser.ParseGCodeEvidence(input));
    }

    [Theory]
    [InlineData(BambuStudioOrientationPolicy.Fixed)]
    [InlineData(BambuStudioOrientationPolicy.Search)]
    public void Arguments_PreserveExactOrderingAndLiteralPathsWithoutExecuting(BambuStudioOrientationPolicy policy)
    {
        BambuStudioSliceRequest request = Request() with { ModelPath = policy == BambuStudioOrientationPolicy.Fixed ? "prepared pose.3mf" : "model with spaces.stl", OrientationPolicy = policy };
        List<string> expected = ["--debug", "2", "--outputdir", "output", "--curr-bed-type", "High Temp Plate",
            "--load-settings", "machine's profile.json;process profile.json", "--load-filaments", "filament.json",
            "--slice", "0", "--export-3mf", "slice.3mf"];
        if (policy == BambuStudioOrientationPolicy.Search)
        {
            expected.AddRange(["--orient", "1", "--arrange", "1"]);
        }
        expected.Add(request.ModelPath);
        Assert.Equal(expected, BambuStudioCli.BuildArguments(request));
    }

    [Theory]
    [InlineData("fixed-stl")]
    [InlineData("enum")]
    [InlineData("empty-model")]
    [InlineData("option-model")]
    [InlineData("empty-machine")]
    [InlineData("settings-delimiter")]
    [InlineData("empty-filament")]
    [InlineData("empty-output")]
    [InlineData("bed-newline")]
    [InlineData("model-nul")]
    [InlineData("argument-bytes")]
    [InlineData("output-parent")]
    [InlineData("output-backslash")]
    [InlineData("output-drive")]
    [InlineData("output-option")]
    [InlineData("output-suffix")]
    public void Arguments_InvalidRequest_RejectsWithoutVendorExecution(string mutation)
    {
        BambuStudioSliceRequest request = mutation switch
        {
            "fixed-stl" => Request() with { OrientationPolicy = BambuStudioOrientationPolicy.Fixed },
            "enum" => Request() with { OrientationPolicy = (BambuStudioOrientationPolicy)42 },
            "empty-model" => Request() with { ModelPath = " " },
            "option-model" => Request() with { ModelPath = "--help" },
            "empty-machine" => Request() with { MachineProfilePath = "" },
            "settings-delimiter" => Request() with { ProcessProfilePath = "one;two.json" },
            "empty-filament" => Request() with { FilamentProfilePath = "" },
            "empty-output" => Request() with { OutputDirectory = "" },
            "bed-newline" => Request() with { BedType = "one\ntwo" },
            "model-nul" => Request() with { ModelPath = "one\0two.stl" },
            "argument-bytes" => Request() with { BedType = new string('ก', 5462) },
            "output-parent" => Request() with { OutputFileName = "../slice.3mf" },
            "output-backslash" => Request() with { OutputFileName = "..\\slice.3mf" },
            "output-drive" => Request() with { OutputFileName = "C:slice.3mf" },
            "output-option" => Request() with { OutputFileName = "--slice.3mf" },
            _ => Request() with { OutputFileName = "slice.stl" },
        };
        Assert.Throws<ArgumentException>(() => BambuStudioCli.BuildArguments(request));
    }

    private static BambuStudioSliceRequest Request() => new("model.stl", "machine's profile.json", "process profile.json", "filament.json", "output", "slice.3mf", "High Temp Plate");
}
