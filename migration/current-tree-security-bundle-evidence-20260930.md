# Current-tree credential scanner bundle — September 30, 2026

Code-review candidate based on Workflows main
`1ee9c2d1b9b950d10ea18889d8d879826b3df42f`, independently re-observed
at live origin/main with successful exact-main CI `36690074546`.
Original source main was read-only committed-object evidence at
`4198baa6b0e7903f2b9b6e3d5d68f9d2c2b5b0db`.
No source edits, consumer edits, ledger changes, retirement approvals,
deployment, persistent data access, or application release are part of this slice.

## Scope and retained per-SHA obligations

| Source SHA | Parents | Included behavior | Deliberately unresolved |
| --- | --- | --- | --- |
| `7a660e9630e2ff10dbdf6f03766f89f125fdba4f` | `2aab25eb07894fc0267b03b85bad96490219d2fa` | General current tracked-tree credentials, base64 service-account detection, redacted output, default Gitleaks retained | Historical producer/configuration tests and full wave0 release-gate acceptance are not inferred from scanner tests |
| `12b0dca5b59ce3b2cb2a04847446ae24d68ea99f` | `79fa2e5c55a384b543a2aee11ab917119f84182b` | Standalone password aliases and declaration-scoped credential-holder detection | Other services' embedded credential removal is not implemented or accepted here |
| `868b5909406cc3759254ee10520e04d4ad5beab0` | `c5fe0e4446f4bf96917d6d1e2a84216f9ea0bea3` | Split-construction synthetic scanner fixtures without persisted credential material | Web/DataMigration configuration and parity fixture contracts remain under issue210 and their owners |
| `eb8ed86672bd9afccc6560b547b734d0fcd7363b` | `6da103d234ea312ce3b404fefaed343c172517b1`, `868b5909406cc3759254ee10520e04d4ad5beab0` | Scanner, security tests, Gitleaks configuration and wave0 gate paths have no second-parent merge delta | Separate type-tagged length-prefixed parity canonicalization/null-tag merge change, inventory/parity tests and other split owners remain pending under211 |
| `0e84bc0704b614631a6f0a2b1234060cefa0c301` | `f79657bdd06b878dc99fe45fbf26c40eeffb25f0` | Real Python f-string identifier placeholders only; literal same-line negatives retained | Brevo/Web/deleted Logger producer/test dispositions are not silently copied, retired or resolved |

Root owns the resolution ledger and Project2. Existing Workflows197 is the
shared scanner/consumer rollout parent (In Progress);210 and211 remain open
for the split contract and merge-owner obligations. There is no new per-SHA
ticket and no whole-owner or whole-source completion claim. The inspected
ledger remains157/1,096 resolved and939 pending/partial.

## Scanner contract

The selected path must belong to a Git worktree. Git supplies its repository
root and NUL-delimited index entries; only those entries' current working-tree
bytes are scanned. A caller subdirectory therefore still scans its entire
owning repository. No Git history, arbitrary filesystem recursion, other
repositories, ignored/untracked files, or private source history is scanned.
Tracked files remain included even when ignored by current ignore rules.
Staged additions are included; unstaged changes to tracked files are included.

Missing/unreadable tracked files, unresolved index stages, symlinks, gitlinks,
paths outside the root, unavailable Git, Git command failures and files over
128MiB fail closed. Binary files are inspected for ASCII credential signatures.
The existing hardened JWT/provider-resource PowerShell scanner remains
unchanged and is invoked separately; its XML/DTD/read-error guards are retained.

Exit0 means inspection completed without findings; exit1 means findings;
exit2 means incomplete inspection, invalid arguments or unavailable tooling.
PowerShell7 and Python3.11+ are required (Windows `python`, Linux/macOS
`python3`); the runner never installs a fallback interpreter or continues when
the scanner/runtime is missing. Python is invoked with `-B`, without bytecode.

Findings contain JSON-escaped rule/path/line metadata, never matched values or
decoded credential content. Credential-shaped filenames are masked; control
characters cannot create GitHub workflow-command lines. Inspection failures
emit fixed redacted diagnostics, not exceptions, command stderr, identity
objects or source contents.

The source-reviewed exception set is empty. No CLI/caller allowlist or historical
inline exemption is inherited. Any future exception requires exact rule, path,
line, raw-byte file SHA256 and an explicit MALIEV GitHub issue/PR approval URL;
changed content invalidates it. The digest uses raw bytes, not lossy decoding.
Gitleaks exceptions/history remain independently governed and unchanged.

Python password placeholders are recognized only inside real parsed f-string
AST spans in `.py` files and only when the entire password value is an
identifier or dotted identifier interpolation. Comments, quoted fake f-strings,
other file types, expressions, suffixes and a different literal on the same
line do not inherit the exemption.

## Invocation and immutable acquisition

The composite action resolves its scanner from its own `GITHUB_ACTION_PATH`
and scans the caller's configured working directory, before restore. Existing
Gitleaks history and JWT resource checks are retained.

The reusable workflow must not assume scripts exist in the caller checkout.
It serializes the supported `job` context with `toJSON(job)` into an environment
variable, does not echo it from the script, and validates the documented called-workflow
`workflow_repository` against the fixed
`MALIEV-Co-Ltd/Legacy.Maliev.Workflows` identity and `workflow_sha` against a full
lowercase40-hex SHA. Missing, malformed or unsupported identities fail closed;
there is no `github` caller-context, branch or main fallback.

Only that validated SHA is emitted as a bounded step output. A fixed-repository
checkout acquires scanners at that exact SHA under `.maliev-validation-tools`;
an existing caller path with that name is rejected before checkout. Checkout
uses the existing immutable checkout action pin and does not persist credentials.
The workflow verifies acquired HEAD equals the admitted SHA and all four
scanner files exist before executing them against the original caller directory.
No new input or consumer pin change is made here.

Official primary documentation:
[GitHub job context and reusable-workflow identity example](https://docs.github.com/en/enterprise-cloud@latest/actions/reference/workflows-and-actions/contexts#job-context).
The documented properties identify the workflow defining the current job,
including called reusable workflows, and are unavailable on Enterprise Server.
The `toJSON(job)` projection avoids direct-new-property incompatibility in
actionlint1.7.12 without a suppression. Runtime availability still needs hosted proof.
Only repository/SHA fields are consumed. GitHub's runner may display non-secret
job-context metadata in its automatic environment preamble; this document does
not claim that the full object can never appear in hosted logs. No secret-bearing
context fields or outputs are added.

`validate.yml` preserves the original full-solution job and adds a separate
same-commit reusable caller using `working-directory: tools/analytics/WireFixtures`
and `solution: WireFixtures.csproj`. This is actual hosted caller/subdirectory
coverage, not source-only proof. Consumer repositories still require separate
owner-reviewed immutable pin rollouts;197 must remain open until those pass.

## Local validation and remaining merge gates

Baseline: Release build0warnings/0errors; full115/115, zero skips.
Scanner absence was observed RED1/1; missing invocation/acquisition steps were
observed RED7/8. Additional RED regressions caught reserved checkout collision
(exit0 instead2) and lossy-decoding allowlist bypass (0findings instead1).
Windows test-Git readonly cleanup was repaired only inside boundary-checked,
uniquely named test fixtures; no repository/worktree cleanup occurred.

Final combined focused71/71 passed, including real composite invocation,
exact-head shared-tools verification and separate nested caller scanning,
missing/malformed identity negatives. The final Python behavior suite has23tests;
its strict native-error-preference regression confirms findings remain exit1,
and a RED/GREEN filename regression ensures encoded credentials cannot leak
through metadata paths. Final affected .NET suite132/132 passed with zero skips.
All tests construct synthetic credential-shaped values from fragments; only
test-owned temporary repositories/files receive complete synthetic values.
No credentials, PII or production evidence are persisted in source fixtures.

Final local commands and results:

| Check | Result |
| --- | --- |
| `dotnet build Legacy.Maliev.Workflows.slnx -c Release --no-restore` | PASS, zero warnings/errors |
| `dotnet test Legacy.Maliev.Workflows.slnx -c Release --no-build --no-restore --filter 'FullyQualifiedName~CurrentTreeCredentialScannerTests\|FullyQualifiedName~RepositoryContractTests'` | PASS71/71, zero skips |
| `dotnet test Legacy.Maliev.Workflows.slnx -c Release --no-build --no-restore` | PASS132/132, zero skips |
| `python -B -m unittest discover -s tools/security/tests -v` | PASS23/23; imports/syntax exercised without bytecode |
| `dotnet format Legacy.Maliev.Workflows.slnx --verify-no-changes --no-restore` | PASS |
| `actionlint` on all three `.github/workflows/*.yml` files | PASS, v1.7.12; no suppressions |
| `git diff --check` | PASS |
| `gitleaks git . --redact=100 --exit-code 1 --no-banner --no-color` | PASS194commits,5.40MB, no leaks |
| `gitleaks dir . --redact=100 --exit-code 1 --no-banner --no-color` | PASS4.94MB after evidence readback, no leaks |
| `dotnet list Legacy.Maliev.Workflows.slnx package --vulnerable --include-transitive --no-restore` | No vulnerable packages in both projects |
| Actual current-tree/JWT PowerShell runner invocation against this Workflows worktree | PASS, current-tree0findings; newly untracked artifacts also independently scanned by the Python23suite and Gitleaks dir |
| JWT runner/scanner working-tree Git blob IDs versus HEAD | Exact equality; both existing files unchanged |
| Writable-path census and canonical status | Exactly nine approved files changed/new; canonical main remains clean; no `__pycache__` present |

Required hosted gates are protected exact-head CI, both hosted
reusable caller jobs (including actual `toJSON(job)` identity availability),
and exact-main CI. They have not been run by this writer. No commit, push or
PR has been created; ledger resolutions remain pending.

Independent root acceptance before integration: Release build with warnings as
errors passed at zero warnings/errors; focused 71/71 and complete 132/132 passed
with zero skips. Formatting, workflow lint, diff whitespace, PowerShell parsing,
current-tree runner invocation, candidate Gitleaks scan (4.94MB) and both
projects' transitive vulnerability audit passed. Root TRX files are retained
outside this repository at `B:\maliev-legacy\.artifacts\workflows-current-tree-root-20260930`.
These local results do not establish hosted reusable-job identity availability
or complete any other source owner or consumer rollout.

Root should inspect the actual identity-validation, immutable checkout,
HEAD/required-files verification, and both scanner step conclusions in each
hosted job. Both jobs are unconditional and retain the existing checks; a
successful job therefore supplies runtime identity/acquisition proof that the
local JSON simulations cannot provide. Inspect checkout SHA against the
called-workflow commit. The subdirectory job must show its configured caller
working directory while obtaining tools from the separate immutable checkout.
