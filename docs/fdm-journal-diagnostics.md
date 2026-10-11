# Original FDM journal diagnostics

`scripts/fdm_journal_evidence.py` consumes the original `{atUtc, phase, parts}` JSONL produced by source `29214f53f1574b89799e6d58ea1cebea03fffe04` (parent `135e526d0dab85c415b3afdcefd7b70fe2c82e2f`). It preserves18 fixed labels and the original HTTP handler/event families. This is diagnostic consumption, not runtime or migration acceptance.

```text
python3 -B scripts/fdm_journal_evidence.py --root . \
  --journal TestResults/readiness/pipeline-progress.jsonl \
  --started-utc 2026-10-11T01:00:00Z --finished-utc 2026-10-11T01:01:00Z \
  --required-fixed pdf_case_start --scenario normal
```

The interval and required labels must come from a separately reviewed invocation binding. This example supplies no authenticated source or execution custody. Exit0 means the input can produce the following diagnostic; it does not mean a test, workflow, cleanup, network operation or deployment passed. Exit2 emits only `FDM journal evidence rejected` on stderr, with empty stdout. Existing logs must be retained even when diagnosis fails.

The public output has exactly these fields:

| Field | Meaning |
| --- | --- |
| schema | `fdm-journal-diagnostic/v1` |
| journalSha256, journalBytes | Identity of the bytes consumed by a bounded stable regular-file read |
| observations | Number of original journal records |
| fixedOperationsComplete | Recorded fixed start/completion pairs are balanced, and no recorded cleanup failed |
| journalOperationsComplete | Always false: the original journal cannot establish complete network execution |
| networkDiagnostics | `adverse` for recorded failed requests or HTTP4xx/5xx; otherwise `unknown` |
| networkCompleteness | `unverifiable-original-cap-no-request-ids` |
| headCustodyVerified, runtimeAcceptance, activationPermitted | Always false |

Cleanup requires one ordered outcome for each part's started attempt. Sequential same-part attempts and interleaved different-part attempts are supported. Overlapping same-part starts are ambiguous because the original has no attempt IDs; mismatched parts, duplicate outcomes or incomplete operations are refused. Completed and failed outcomes across different valid attempts are accepted as diagnostic input, while fixedOperationsComplete is false if any cleanup failed.

The original emitter caps HTTP observations at32 and has no request IDs. The consumer does not pair requests and responses, require absent responses, or infer network success from successful/no observations. It preserves seventh .NET timestamp ticks rather than rounding interval boundaries. Duplicate/extra JSON fields, unknown labels, invalid parts/time, records outside the supplied interval and oversized input are refused. Public output contains hashes and aggregate diagnostics, not raw record values.

## Required producer binding before a workflow uses this diagnostic

Web owns the real producers in FdmQuantityPricingBrowserTests.cs, InstantQuotationBrowserFixture.cs and InstantQuotationPreliminaryQuotationBrowserTests.cs. The original shared output path has no head, run, GUID or test identity. Web must provide an isolated fresh capture and finite invocation receipt, with exact source head/tree, behavior/scenario, begin/end interval and original journal bytes/hash. Prior and failed journals remain recovery evidence. The reviewed producer must demonstrate that no prior or concurrent test contributes to the capture; a supplied interval alone proves none of those properties.

Workflows' later consumer adapter must first execute the accepted source/admission/TRX guards on the exact reviewed source and phase manifest. It must join the producer invocation receipt to that phase's actual unique test/execution GUID roster, source pins and capture hash before passing journal bytes/interval/subset to this CLI. The CLI's flags remain false even after that external join. The workflow must separately inspect adverse/incomplete diagnostic fields and preserve raw evidence; process exit0 alone cannot satisfy a gate. No such producer or workflow adapter is installed by this change.

All20 source paths,19 journal identities and14 original behavior groups remain obligations in the source-parity contract. Journal subsets belong to genuine producer scenarios; every group is not a browser journal producer. A failed cleanup is a diagnostic branch, not a required passing outcome. The immutable accepted Web candidate_head recipe/caller successor and human product approval remain dependencies. Issue339, Web551/552 and the whole source SHA remain open for runtime acceptance. No FDM forwarder or stopped financial/security qualification is activated.

## Validation boundaries

The Python controls exercise the original wire shape, cleanup multiplicity, adverse/unknown HTTP policy, public diagnostic schema and CLI success/failure privacy. `FdmJournalEvidenceTests` runs that exact source-known20-case suite through the unchanged owned-process timeout/cancellation infrastructure. Python cases are subprocess controls, not20 additional .NET tests. Before protected merge require Release0warnings/errors, the focused C# adapter, affected full suite, formatting/static/security checks, exact-head raw test rosters/artifact custody, and protected-main validation under existing repository policies. These parser tests do not replace Web's native journal, startup, browser, full-suite or coverage acceptance.

The Workflows-only focused retention job executes portable retention controls and the actual one-Fact adapter before the unchanged shared full validation. Its narrow retainer requires an original Completed summary, one passing known Fact, exact native GUID joins and the frozen16-counter allowlist (total/executed/passed1, every other counter0). Any ErrorInfo or RunInfo is refused before the unchanged privacy exporter is called. The original one-Fact producer has no RunInfo messages; unknown or informational labels cannot be assumed safe. Raw outputs and unknown counter attributes are never exported as focused success. Always-retained metadata explicitly marks evidence unavailable on validation failure; the original full-suite/scanner/coverage gates remain mandatory.

The portable native-shape fixture is a privacy-minimized regression input derived from an earlier actual local focused report. It removes host/path/time/output details and retains only known test identity, native GUID joins and counters. Its provenance hash is review evidence for that fixture transformation, not new execution, source-custody or runtime-parity proof. The focused artifact contains transformed actual TRX plus original hash and source/run/workflow bindings; it explicitly reports that raw internal Python20 diagnostics are not exported. Matching-source local Python20 proof remains separate.
