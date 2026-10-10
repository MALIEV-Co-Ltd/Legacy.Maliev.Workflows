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
All newly implemented guards/tests are NOT RUN in this source-only allocation.
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
