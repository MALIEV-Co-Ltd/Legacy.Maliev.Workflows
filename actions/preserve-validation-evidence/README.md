# Final caller evidence retention

Source-candidate metadata accepts the exact net10.0 SDK basename
`.NETCoreApp,Version=v10.0.AssemblyAttributes.cs` under an `obj` component.
This narrow exception does not allow punctuation in inputs or retained payload
paths, copy source text, bypass symlink checks, or certify compiled membership.

Invoke this separate action with `if: always()` **after** the caller's existing
collector and coverage guard. An upload inside `dotnet-validate` runs before
Intranet's later collector and cannot preserve its output. Pin an accepted full
Workflows commit; only the assigned caller CI owner changes that reference.

```yaml
- name: Preserve actual runner validation evidence
  if: always()
  uses: MALIEV-Co-Ltd/Legacy.Maliev.Workflows/actions/preserve-validation-evidence@REVIEWED_FULL_COMMIT
  with:
    results-directory: TestResults
    production-projects: |
      Legacy.Maliev.Intranet.Bff
      Legacy.Maliev.Intranet.Server
      Legacy.Maliev.Intranet.Contracts
```

The producer retains actual Cobertura bytes, original `coverage.runsettings`,
existing Release/net10.0 production DLL/PDB bytes and a relative-path/hash source
candidate inventory. It never copies source text, a whole checkout, private Git,
application settings, environment dumps, arbitrary logs or test assemblies.
TRX is retained only when it exists. Inputs with neither roster section retain
the existing `outcome-only-trx/v1` derivative; they provide no test-roster proof.
Inputs with both `TestDefinitions` and `TestEntries` use the explicit
`privacy-safe-test-roster-trx/v2` schema and manifest transform marker. A partial,
duplicate, nested or inconsistent roster fails preparation before staging.

Version 2 retains definition/entry/result IDs and static class/method identifiers.
Each definition execution joins exactly to one entry and result. The original
definition name must equal the result test name ordinally, including theory case
identity, before both are replaced by a domain-separated SHA256 display hash.
Method identifiers use a bounded ASCII CLR identifier grammar; parameterized
method labels, paths and unsupported identity formats refuse rather than enter
the artifact. Counters retain their existing allowlist, with total and available
passed/failed/not-executed counts checked against the actual result rows.

Test arguments, raw display names, output, failure details, adapter/storage paths
and machine metadata are omitted. Hashed display identities permit equality
comparison; they are not anonymization against guesses of known case values.
Existing file/total limits, source checks, binary/coverage handling and refusal
behavior remain required. The manifest records original and retained hashes;
neither derivative is an unchanged raw TRX claim. A new export cannot reconstruct
definitions or case identities omitted by an earlier outcome-only export.

The version 2 XML is unnamespaced, as the version 1 derivative is. Its allowlisted
shape is:

| Element | Retained attributes |
| --- | --- |
| `TestRun` | `evidenceSchema="privacy-safe-test-roster-trx/v2"` |
| `TestDefinitions/UnitTest` | `id`, `displayNameSha256` |
| `TestDefinitions/UnitTest/Execution` | `id` |
| `TestDefinitions/UnitTest/TestMethod` | `className`, `name` |
| `TestEntries/TestEntry` | `testId`, `executionId`, optional `testListId` |
| `Results/UnitTestResult` | `outcome`, `testId`, `executionId`, `displayNameSha256` |
| `ResultSummary/Counters` | Existing numeric counter allowlist |

Each display hash is lowercase SHA256 of the UTF-8 bytes of
`trx-display/v1`, one zero byte, then the exact parsed display name. Each test ID
and execution ID is unique within its roster; all three sets join exactly. A
consumer must require this schema marker and validate those joins before claiming
a roster. The original/retained artifact hashes bind this derivative to the
captured input; they do not supply missing baseline test evidence or certify
compiled membership.

Missing required coverage/binaries/source candidates produces an explicit partial
manifest and a failing preparation step, while `always()` still preserves that
partial manifest. Missing TRX is recorded as unavailable, never invented. Upload
success is not a coverage/test gate pass. The producer cannot certify DLL/PDB
validity, compiled source membership, complete generated-inclusive coverage,
repository authenticity or an atomic filesystem snapshot. Exact source/PDB
ownership and coverage recomputation belong to the artifact consumer.

Intranet's currently inspected settings exclude `**/obj/**`, and its collector
does not request a TRX logger. Preserve both facts exactly. Removing that exclusion
or introducing a logger requires the separately reviewed caller successor and
fresh gates; this action changes neither. Current coverage floors remain BFF80%,
Server85%, Contracts95%. No source closure follows from artifact preservation.
