> **Historical source record — migration provenance only.** This is the original September 2026 record preserved from source commit `c3bf396009bb1c078afcee93a3a059a7d96c6e76`. Its approvals, operational state, reported tests, prices, corpus access and release steps describe that historical source. They do not authorize actions in this migration or establish current Legacy.Maliev service behavior. No private corpus, vendor installation, workbook or physical production evidence was accessed or revalidated for this documentation slice. References to missing family review, matched references, effective profiles and production observations remain unresolved evidence boundaries. Current implementation and validation require separate owner-specific evidence.

# FDM simulation implementation and release decision — 2026-09-20

## Decision

The deterministic MALIEV FDM analytical simulator is implemented through the authoritative server-upload boundary and an accessible shadow report. It is **not approved for automatic customer pricing yet**. `AdditiveSimulation:ShadowEnabled` remains `false` by default, so the current quotation path and its workbook anchors remain authoritative.

This is an evidence decision, not a missing-algorithm decision. The implementation now models physical layers, walls, skins, sparse infill, bridges and overhang speed modifiers, normal and tree support paths, deposited support body/interface volume, role-specific motion, bounded orientation search, machine fit, quantity packing, and explicit oversized-part review scenarios. Bambu Studio is used only as an offline reference oracle; it is not a production dependency.

## Frozen private corpus

The owner authorized read-only use of `Z:\` on 2026-09-20. The inventory tool selected and exact-byte deduplicated 48 files without copying source CAD, filenames, paths, or generated slicer artifacts into Git. It froze 12 digest-sorted entries as an untouched release holdout and 36 as development entries.

| Inventory fact | Result |
| --- | ---: |
| Unique anonymous entries | 48 |
| Release holdout | 12 |
| Development entries | 36 |
| Byte-size buckets | 12 small, 12 medium, 12 large, 12 very-large |
| Formats observed | 45 STL, 2 3MF, 1 OBJ |
| Duplicate digests in manifest | 0 |
| Geometry-family state | 48 `unreviewed` |
| Matched-reference state | 48 `matched_reference_missing` |

Byte-size buckets make acquisition deterministic; they are not physical-size or geometry-family claims. The preregistered floor requires at least eight manually reviewed geometry families and physical size/feature coverage, so the manifest deliberately does not invent those labels. The release holdout must not be used to tune algorithms or pricing constants.

## Evidence status and feature eligibility

| Cell | Implementation | Evidence / release eligibility |
| --- | --- | --- |
| Layer contours and topology | Complete with analytic and scale fixtures | Synthetic eligible; private-reference gate blocked |
| Walls, skins, infill, bridges, overhang timing | Complete with role and conservation fixtures | Shadow-only until matched references exist |
| Normal support body/interface | Complete with ownership, collision, connectivity, and mass fixtures | Shadow-only; support-reference gate blocked |
| Tree support | Deterministic collision-aware path planner complete | Provisional and engineer-reviewed; tree-reference gate blocked |
| Per-feature motion and plate preparation | Complete with numerical kinematic fixtures | Shadow-only; Bambu timing comparison blocked |
| Orientation, fit, and quantity packing | Complete with deterministic bounded candidates and machine scenarios | Shadow-only; fixed-pose private comparison blocked |
| Oversized parts | Reports matching-machine or operator-reviewed partition requirement | Review-only; never resizes an X1C quote |
| Canonical commercial calculation | Support charged once; support-removal labour separate | Eligible with existing workbook anchors only |
| Server upload authority | Receipt/session/digest bound, bounded and cancellable | Eligible for shadow analysis |
| Automatic customer price cutover | Feature-flagged | **Blocked** |

The following evidence is still unavailable and is not replaced with assumptions:

1. Manual geometry-family review for the 48 anonymous entries, including physical size, thin features, cavities, organic forms, bridges/cantilevers, and support-heavy parts.
2. Fixed-pose Bambu Studio results produced from the same transform and exact resolved machine/process/filament bundle for each selected case and build choice.
3. Deployable immutable snapshots of the owner-approved effective Bambu/Polymaker/eSUN profile settings. The runtime provider intentionally returns unavailable rather than guessing a profile.
4. Measured production material, waste, elapsed time, and outcome observations. The owner confirmed these records do not exist, so slicer agreement cannot be described as measured manufacturing accuracy or profit assurance.

Until these gates are satisfied, no percentage accuracy, support false-negative rate, runtime P95, or broad profitability claim is reported. The two workbook anchors remain commercial contract tests: ASA 10 g / 51 min => THB 755 and PLA 207.39 g / 229 min => THB 3,490. They do not prove that CAD analysis predicts those inputs.

## Reproducibility and environment

| Item | Value |
| --- | --- |
| Simulator algorithm version | `fdm-physical-v1` |
| Offline oracle | Bambu Studio `2.8.2.61` |
| Host | Windows 11 Pro `10.0.26200` |
| CPU | 11th Gen Intel Core i9-11900KF @ 3.50 GHz |
| Memory | 31.8 GiB |
| Corpus contract | `private-corpus.v1`, version `2026-09-20.1` |
| Consent record | `owner-instruction-2026-09-20` |

The checked-in test regenerates a synthetic corpus twice and requires byte-identical output, exact-byte deduplication, and absence of source names/paths. A second test freezes the private manifest count, digest uniqueness, holdout count, and fail-closed evidence state.

## Rollback and next evidence run

- Keep `AdditiveSimulation:ShadowEnabled=false`; no customer price is switched by these commits.
- If shadow analysis is unhealthy, disable the flag. Existing line tickets and workbook-based pricing remain unchanged.
- Profile or algorithm version changes invalidate simulation cache identity; do not reuse stale results.
- Keep support and tree outputs provisional until their separate matched-reference gates pass.
- Generate references only in restricted storage. Commit anonymized hashes and aggregate results, never CAD, customer names, source paths, 3MF, or G-code.
- After family review, freeze the candidate revision, run development comparisons, then run the untouched 12-file release holdout once. Report every blocked/failing case in the denominator and inspect the largest underquote before any cutover.

## Issue implication

#58 should remain open: its analytical implementation exists, but its corrected acceptance scope includes matched support, feature-time, build-setting, size/fit, and holdout gates that have not run. #55 remains open for the same missing reference evidence. #56 can count the authoritative shadow boundary as implemented but still needs the approved runtime profile snapshot for automatic issuance. #60 remains open for private-corpus DFM/review-reason coverage. The umbrella issue should remain open until those independent gates close. No GitHub issue state is changed by this evidence record.
