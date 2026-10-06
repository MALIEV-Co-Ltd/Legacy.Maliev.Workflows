# Additive benchmark manifest CLI

Validate a supplied metadata manifest using the versioned schema pin:

```sh
dotnet run --project tools/additive-benchmark --configuration Release -- --manifest manifest.json --schema tools/additive-benchmark/schemas/manifest.v2.schema.json --report report.json
```

Exit codes: `0` means metadata ready; `2` means valid but evidence blocked; `1` means invalid metadata or input/output admission failure. Ready does not certify simulator accuracy or execute a slicer, provider, profile resolver, corpus inventory, or customer operation. Unknown metrics stay null; they never become zero. The runner applies its explicit C# semantic contract and checks the supplied schema envelope and version pin; it does not implement a general JSON Schema interpreter.

Historical manifest v1 coverage requires 24 models (16 calibration and 8 validation), 72 cases, all eight families and all three preferences. These requirements cannot be lowered to declare ready. Manifest v2 retains its source-defined configurable coverage contract and requires non-null matched-input hashes. Coverage preferences and missing-data reasons must be valid and unique. Invalid input availability is reported as `invalid`, so invalid reports still conform to the report schema.

Each input is limited to 4 MiB and JSON depth 64. Duplicate property names are rejected at every depth. The CLI requires exactly one manifest, schema and report flag. Input/output failures omit filesystem paths from console diagnostics. Reports must use a distinct destination; callers must also avoid filesystem aliases such as hard links and symbolic links.

Report contract 2.0 preserves the historical report fields and ordering. `manifestSchemaVersion` is the supported version observed in parsed input, or null if absent, unsupported or unreadable. Historical report schema 1.0 is retained for provenance and is not emitted. Report JSON is UTF-8 without BOM, with LF and a final LF. `manifestSha256` hashes UTF-8 input after CRLF-to-LF normalization. `deterministicResultSha256` preserves the source recipe: compact System.Text.Json serialization of BenchmarkDeterministicResult with PascalCase record property names and default escaping, then SHA-256. Report field names remain camelCase. Issues sort ordinally by path/code/message and cases by caseId; list order can still affect indexed issue paths.

Adapted from original checkpoint 135e526d0dab85c415b3afdcefd7b70fe2c82e2f: AdditiveBenchmarkRunner and BenchmarkReferenceValidator, plus manifest schemas 1.0/2.0 and historical report schema 1.0. Eight-source/113-path cohort analysis remains external migration evidence. This slice integrates only manifest/report validation. Resolver, inventory, slicer invocation/results, G-code, catalog and other consumer obligations remain separate.
