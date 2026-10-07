# Additive benchmark manifest CLI

Validate a supplied metadata manifest using the versioned schema pin:

```sh
dotnet run --project tools/additive-benchmark --configuration Release -- --manifest manifest.json --schema tools/additive-benchmark/schemas/manifest.v2.schema.json --report report.json
```

Exit codes: `0` means metadata ready; `2` means valid but evidence blocked; `1` means invalid metadata or input/output admission failure. Ready does not certify simulator accuracy or execute a slicer, provider, profile resolver, corpus inventory, or customer operation. Unknown metrics stay null; they never become zero. The runner applies its explicit C# semantic contract and checks the supplied schema envelope and version pin; it does not implement a general JSON Schema interpreter.

Historical manifest v1 coverage requires 24 models (16 calibration and 8 validation), 72 cases, all eight families and all three preferences. These requirements cannot be lowered to declare ready. Manifest v2 retains its source-defined configurable coverage contract and requires non-null matched-input hashes. Coverage preferences and missing-data reasons must be valid and unique. Invalid input availability is reported as `invalid`, so invalid reports still conform to the report schema.

Each input is limited to 4 MiB and JSON depth 64. Duplicate property names are rejected at every depth. The CLI requires exactly one manifest, schema and report flag. Input/output failures omit filesystem paths from console diagnostics. Reports must use a distinct destination; callers must also avoid filesystem aliases such as hard links and symbolic links.

Report contract 2.0 preserves the historical report fields and ordering. `manifestSchemaVersion` is the supported version observed in parsed input, or null if absent, unsupported or unreadable. Historical report schema 1.0 is retained for provenance and is not emitted. Report JSON is UTF-8 without BOM, with LF and a final LF. `manifestSha256` hashes UTF-8 input after CRLF-to-LF normalization. `deterministicResultSha256` preserves the source recipe: compact System.Text.Json serialization of BenchmarkDeterministicResult with PascalCase record property names and default escaping, then SHA-256. Report field names remain camelCase. Issues sort ordinally by path/code/message and cases by caseId; list order can still affect indexed issue paths.

Adapted from original checkpoint 135e526d0dab85c415b3afdcefd7b70fe2c82e2f: AdditiveBenchmarkRunner and BenchmarkReferenceValidator, plus manifest schemas 1.0/2.0 and historical report schema 1.0. Eight-source/113-path cohort analysis remains external migration evidence. Manifest/report validation and explicit preset resolution are integrated. Inventory, slicer invocation/results, G-code, catalog and other consumer obligations remain separate.

## Resolve supplied preset metadata

```sh
dotnet run --project tools/additive-benchmark --configuration Release -- resolve-profile --profile leaf.json --search-root presets --output resolved.json
```

Resolution captures each admitted file once, applies inherited base settings followed by includes in declared order and finally leaf settings. Identical duplicate names are allowed only for identical raw bytes. Names compare ordinally; paths compare case-insensitively on Windows and ordinally elsewhere. Relative leaf/root/output paths resolve against the current working directory. The leaf directory is also indexed, preserving the source contract. Explicit leaf filenames may use any suffix; other indexed files use the `.json` suffix.

Limits: 32 search roots, 256 captured JSON files, 4 MiB per file, 16 MiB in total, 1,024 directories, 4,096 entries and directory/dependency depth 32. Resolution also admits at most 1,024 profile visits and 32 MiB of visited raw input, counting repeated dependencies. Before each clone/merge, cumulative work admits at most 65,536 nodes and 32 MiB of UTF-8 key/value content. Symbolic links/reparse points and linked path ancestors are rejected for input and output admission. These checks assume caller-owned stable roots and do not provide an adversarial filesystem sandbox. No slicer is launched and no private corpus is inventoried.

Intentional admission corrections: missing roots, malformed/duplicate-key JSON anywhere in an indexed root, typed-invalid inherits/include, cycles, ambiguous names and exceeded limits fail closed. Unnamed valid JSON is counted toward the limits but is not a preset. Empty string `inherits` retains the historical no-parent meaning. Each include name must be a non-empty string; include order remains significant. The output destination must be new, preventing replacement of existing presets or resolved files. Output is written and closed in a uniquely created adjacent temporary file, then renamed without overwrite; failed publication removes only that owned temporary file. Console failures omit filesystem paths.

The output is the merged settings object, not an envelope. `include` is removed; the inherited `inherits` metadata remains as in the source. Resolved JSON uses LF with a final LF. Source SHA hashes the captured leaf bytes; resolved SHA hashes the LF settings JSON before the final LF. Both digests remain uppercase, and source profile names retain merge order including repeated dependency occurrences. The historical source wire fields are unchanged; readiness and physical certification still require separate benchmark evidence.

## Pure slicer evidence and argument helpers

`BambuStudioResultParser.Parse` reads vendor-reported result JSON using the historical `main_predication`, `total_predication`, and `total_used_g` fields. It retains the public metrics record and rejects missing/invalid structures, duplicate JSON properties, nonfinite fields or aggregate sums, inverted per-plate time, and exit-zero results without plates or filament metrics. Each input is capped at4MiB UTF-8; JSON depth is capped at64. Error messages omit the vendor error string.

`ParseGCodeEvidence` retains positive extrusion accounting for absolute/relative modes, per-tool positions, G92 resets, retractions, linear moves and arcs. Its supported grammar uses space-separated words and the original feature roles; unknown roles, missing roles or unsupported extrusion command forms make the historical nullable support-for-certification field unavailable. Tabs and uppercase E embedded in a coordinate word are conservatively ambiguous with compact extrusion and leave support unavailable; fully numeric lowercase scientific coordinates such as X1e2 remain supported. Tool identifiers that cannot be parsed as bounded integers reject, rather than silently retaining the previous tool. That field is a syntactic evidence gate, not proof of physical certification. Duplicate/malformed/nonfinite extrusion words and nonfinite arithmetic reject the input. Additional caps:65536lines,16384characters per line,128space-separated tokens per command and64tool IDs. The parser consumes one string through a StringReader rather than materializing all lines.

`BambuStudioCli.BuildArguments` only constructs an argument list. Fixed-pose requests require a prepared3MF filename and omit orientation/arrangement switches; search requests retain the original switches and exact order. Callers remain responsible for artifact hashes, transforms, provenance and vendor execution. Empty/control-containing or oversized arguments, undefined policies, option-like model filenames, ambiguous settings-bundle delimiters and nonportable output basenames reject. Spaces and apostrophes remain literal argument content.

These helpers do not launch Bambu Studio, discover vendor/private profiles, inspect customer CAD/G-code, generate references, publish a result report or establish physical/provider acceptance. Only synthetic regressions are included. Existing manifest and profile commands are unchanged.
