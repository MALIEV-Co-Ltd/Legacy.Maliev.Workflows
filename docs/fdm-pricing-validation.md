# FDM validation helper library

Source `29214f53f1574b89799e6d58ea1cebea03fffe04`, parent
`135e526d0dab85c415b3afdcefd7b70fe2c82e2f`, Workflows issue339 owns
`.gitattributes` and `.github/workflows/fdm-pricing.yml`. Web551/552 own the
actual pricing, endpoint, startup, browser and readiness test consumers.
Scanner340 remains inventory-only; its source exception/policy is not adopted.

This slice provides three PowerShell interfaces, their sibling stdlib Python
guard, synthetic-only controls and unchanged coverage fixtures. It adds no
workflow, caller repin, runtime consumer, publication or deployment job. The
off-repository FDM workflow proposal remains inactive pending genuine Web551/552
consumers and an independently reviewed full-workflow successor. The baseline
full Web workflow is explicitly rejected by source custody.

The interfaces invoke the sibling guard rather than importing archived tools.
Future wiring must obtain this library through an immutable trusted workflow
identity; that checkout integration is not implemented by this helper-only slice.

- Source: exact expected/observed caller head, clean source (only the reserved
  immutable shared-tools checkout is excluded), no linked/reparse source path,
  bounded immutable byte readback, migrated LF and opaque profile JSON policy,
  current worker SHA256/reference pin, and exact unchanged coverage inputs.
- Admission: source custody rechecked first, a fresh Linux MemAvailable and
  proc observation, >=3072MiB available and zero existing dotnet jobs. No job is
  killed to obtain admission. A new fixed-phase receipt is created exclusively;
  it expires in fifteen minutes. Existing receipts/results cannot be reused.
- TRX: source/head rechecked, fixed per-phase path, unchanged manifest hash,
  unexpired same-phase/head admission, artifact modified within its lease,
  nonempty exact privacy-safe expected roster, unique UUID definition/execution/
  entry/result joins, ordinal definition-name/result-name comparison, every row
  Passed, matching counts and no errors/skips/hidden result rows. Display values
  are compared only in memory and retained as `trx-display/v1` hashes.

Admission is an observation and cooperative finite phase lease. It does not
claim a native CPU/memory cgroup, atomic filesystem lock, authentic test-run
attestation, stopped security qualification, or a persistent SDK role. Hosted
job/step timeouts and native test hang limits remain declared separately. The
actual startup helper's process/container ownership and cleanup are Web552's
required consumer proof, not something a TRX or source grep can certify.

## Required consumer interfaces

`tests/fdm-validation-phases.json` uses exactly these top-level keys:
schemaVersion (integer1), sourceSha/sourceParent (full source identities), and
phases. It contains fourteen unique required IDs listed in `fdm_validation_guards.py`, each
with id, actual filter, and nonempty expectedPassingRows. Each row has class,
method and displaySha256. Use the real reviewed CLR identities and the SHA256
of UTF8 `trx-display/v1\0` plus the real display string. No business test names
are fabricated by the Workflows fixture tests.

`tests/fdm-validation-source.json` keys: schemaVersion (integer1), sourceSha,
sourceParent, fullWorkflowSha (reviewed successor matching the future consumer workflow pins),
files and worker. Each file has path, bytes, sha256 and checkoutPolicy (`lf` or
`opaque`). Required files include the phase manifest, attributes, current split
Application PricingEngine/PricingCatalog, existing margin/ticket test sources,
at least one opaque Sources and Resolved profile JSON, current worker and its
reference. The exact `scripts/Invoke-FdmStartupProof.ps1` path is also mandatory,
with nonempty bytes, SHA256 readback and LF policy. No other scripts path is
admitted by this exception. Missing, unpinned, tampered, empty or wrong-policy
startup proof is refused by source custody before native resource admission.
Worker has path, referencePath, sha256 and the existing16-hex pin.
All paths stay inside declared caller roots and no byte rewriting is performed.

Coverage gate and runsettings SHA256 constants bind the observed unchanged
Web generated-inclusive policy: 80 percent per Web, Application and
Infrastructure assembly, empty exclusions. Legitimate future policy changes
require a new independent review; do not change those constants to hide failures.

Web552 supplies `scripts/Invoke-FdmStartupProof.ps1 -ExpectedHead ...
-ResultsRoot TestResults/fdm/host-startup` with genuine migrated-host liveness,
finite task-owned resource identities and finally verified cleanup. The old
deliberately failing .NET8 host/Gulp/CRLF recipe is not executed. The fourteen
test groups are independently required; none is waived because another broad
filter happens to return passing rows. The existing full Web recipe follows
focused success and retains its security/full-boundary/coverage gates intact,
with exact caller-head checkout and fourteen-day evidence required in its
reviewed successor.

## Validation status

New Python unit controls cover source/roster success and unknown phases,
missing/zero TRX, stale heads, path escapes, duplicate cases, foreign phases,
late/preexisting artifact custody, insufficient memory/foreign jobs, swapped
joins, failure/skip/error/count controls, phase-manifest mutation, source/worker/
coverage tampering, old full pin/dirty source, symlinks and duplicate JSON keys.
Local execution remains NOT RUN under the unchanged resource admission.
Initial hosted run 38091768250 at 44c9e60445937abbea4ddd85a427df1b524061b7
built Release with zero warnings/errors and passed formatting. Its full suite
reported 542 passed, one failed, zero skipped of 543: the Python adapter rejected
the word `skipped` in a passing negative test name. Its preceding exit-zero,
twenty-four-test count and terminal-OK assertions passed in 412ms. Python source
compilation and PowerShell parsing adapter facts passed. This failed run has no
uploaded raw TRX artifact; its audit/analytics follow-up was not run.

The correction checks actual verbose skip outcomes and the unittest skip summary,
preserving the exact count/exit/terminal-OK checks. Four authored parser cases
distinguish a passing name containing `skipped`, a real skipped row, a skip summary,
and an ordinary pass. These new cases and the corrected adapter are NOT RUN.
The original twenty-four Python controls and existing process supervisor are
unchanged. New exact-head full hosted acceptance remains required.
Earlier proposal YAML checks and Tracking338 tests do not validate this successor.

The hosted C# suite includes `FdmValidationGuardTests`: it compiles the module
and controls without execution, runs all twenty-four Python controls (including
opaque CLI refusal cases), and parses all three PowerShell wrappers without
invoking them. All three adapter facts use the unchanged existing `OwnedTestProcess.RunAsync`
supervisor with its supported thirty-second limit, cancellation token, bounded
shared output drain, metadata journal and retained-handle settlement. No custom
kill/cleanup loop or limit relaxation is introduced. The existing supervisor's
fault tests remain in the required full suite. The twenty-four controls use
synthetic temporary files and in-process mocks; their actual duration is NOT RUN
and must fit the unchanged limit in hosted validation.

Existing repository YAML checks remain unchanged; this slice adds
no YAML workflow. Local checks are NOT RUN because Root's memory admission is
below the unchanged threshold. Draft publication may use the owner-approved
2026-10-10 migration validation-order exception; all exact-head hosted Release,
focused/full-suite, formatting, static/security and applicable boundary checks
remain required before protected merge. Native build/focused/full/browser/raw-coverage/protected
head/main checks remain pending and require their own allocation and genuine
Web551/552 consumer integration. No runtime acceptance or whole-source-SHA
closure follows from this packet.


## Actual evidence retention successor (not executed)

The first corrected hosted run 38092330239 at ce7a577d9672c44cd445915420e3c552c70317d1
reported 547 passed, zero failed/skipped, a zero-warning/error Release build and
passing existing format/security/audit/analytics checks. Its unchanged workflow
uploaded no TRX or per-case identity roster. It is not sufficient raw evidence
for protected merge; no merge or issue339 closure follows.

This proposal preserves the existing required `validate / validate` job and all
existing reusable workflow/action interfaces. Two own-repository hosted evidence
jobs use the unchanged full validation composite at immutable ce7a577. They run
sequentially after existing validation. The proposed-head checkout is bound to
the event's exact head; the frozen a08d488 baseline lane runs only for PR341.
MSBuild VSTestLogger=trx and the fixed owned results directory supply actual test
reports without test filtering. The baseline 540 roster is still unavailable;
its genuine hosted report must be inspected, not inferred from source counts.

The new retainer consumes the existing reviewed privacy-safe TRX/v2 transform:
real IDs and complete definition/execution/entry/result joins, static class/method
and display hashes. Original and transformed SHA256 values are both retained.
Raw arbitrary outputs, exception values, source paths and display values are not
exported. This is transformed actual TRX, not a claim of verbatim raw TRX bytes.

The Python24 adapter emits its actual bounded result stderr through the existing
xUnit `ITestOutputHelper` API. The retainer extracts only that exact passed test,
checks all twenty-four source-known synthetic method rows, unique complete
membership, count and terminal OK, then retains the actual validated diagnostics
separately. Unknown content, failed/skipped rows, duplicated blocks or oversized
output cannot enter retained diagnostics. The original lifecycle supervisor,
timeout and Python controls are unchanged.

Both jobs retain evidence with always-upload, an immutable upload-artifact action,
fourteen-day retention and exact source/control/action/workflow/run binding.
The retainer creates a new fixed output directory, bounds reads, rejects linked
paths and refuses output overwrite. Missing reports or diagnostics remain
explicitly unavailable, fail the preparer and do not certify acceptance.

There is no Workflows coverage collector or current coverage gate in this solution.
The actual production projects are AdditiveBenchmark and WireFixtures. The
namespace-restricted production exporter is not fed a fictitious Workflows
production project. Genuine Cobertura is retained only if it exists; availability
is recorded separately. No coverage percentage, collector, exclusion, threshold,
security qualification or SDK role is introduced. The Web80 coverage fixture
and genuine Web consumer/full-workflow successor dependencies remain unchanged.

New retention controls: seventeen authored Python cases and seventeen authored
C# cases (two retention facts, six workflow mutation cases, nine producer-boundary
negative cases). All new source compilation/tests/YAML/browser/
native/format/security checks are NOT RUN under unchanged local admission. The
existing full suite and process fault negatives remain required. Hosted exact-head
evidence, baseline roster preservation and exact protected-main checks remain
pending; no runtime or whole-source-SHA acceptance is claimed.

xUnit output API reference: https://api.xunit.net/v3/2.0.0/Xunit.ITestOutputHelper.html


Producer privacy correction: actual Python diagnostics are validated BEFORE any
ITestOutputHelper emission. The gate requires native exit zero, empty stdout,
exact twenty-four source-known unique passing names and their matching optional
descriptor method suffix, one exact count summary, terminal OK and a256KiB bound.
Only then does it emit the unchanged actual result stderr. Invalid data fails
with fixed category/hash metadata; raw invalid stdout/stderr is not an assertion
message. Nine authored negative cases call the emission boundary itself and
assert no payload is emitted for arbitrary output, stdout, missing/duplicate/
unknown/skipped cases, mismatched identity, malformed summary and oversized data.
These are synthetic negative fixtures, not substitute successful diagnostics.
Actual passing evidence still requires the genuine Python24 subprocess result.
The retainer also rejects a mismatched descriptor suffix, and its control adapter
failure messages withhold generic payloads. All new cases remain NOT RUN.
