> **Historical source record — migration provenance only.** This is the complete September 2026 record preserved from source commit `199e5f94562d3f1621f20c598ae5abef4d6c98d0`. Its approvals, operational state, reported tests, prices, corpus access and release steps describe that historical source. They do not authorize actions in this migration or establish current Legacy.Maliev service behavior. No private corpus, vendor installation, workbook or physical production evidence was accessed or revalidated for this documentation slice. References to missing family review, matched references, effective profiles and production observations remain unresolved evidence boundaries. Current implementation and validation require separate owner-specific evidence.

> **Current acceptance boundary — no runtime, pricing or release authority.** Both the pre-release statements and the production-release update below are historical documentation only. They grant no current runtime or automatic-pricing acceptance, private-corpus access, profile approval, release authorization, deployment authorization or permission to execute the historical steps. Preserving this document does not accept the separate Web owner obligations of the source commit.

Source revision: [`199e5f94562d3f1621f20c598ae5abef4d6c98d0`](https://github.com/MALIEV-Co-Ltd/maliev-web/commit/199e5f94562d3f1621f20c598ae5abef4d6c98d0). The complete source body follows unchanged.

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

## Validation performed

| Check | Result |
| --- | --- |
| `dotnet build Maliev.Web.Tests/Maliev.Web.Tests.csproj -c Release -warnaserror` | Passed, 0 warnings and 0 errors |
| Additive benchmark tests | Passed, 13/13 |
| FDM simulation tests | Passed, 70/70 |
| Pricing engine and additive cost tests | Passed, 70/70; includes THB 755 and THB 3,490 anchors |
| Physical simulation browser state test | Passed, 1/1 |
| Checked-in manifest validator | Expected blocked result, exit code 2 |
| Formatter over branch-changed C# files | Passed after final-newline normalization |
| `git diff --check` | Passed |

The repository-wide test suite was attempted with a five-minute hang detector but did not complete cleanly. Two unrelated CNC browser cases timed out: `DetectedThreads_ShowAdvisoryWithoutBlockingReviewOrChangingMachiningPlan` stopped after 180 seconds with `parseComplete=false`, and `AxialThreadGeometry_PublishesSerializableCanonicalCadTopology` exceeded its 90-second Playwright wait. The run was stopped after those failures. The repository-wide formatter also reports pre-existing final-newline, import-order, and one CNC whitespace violation in untouched files; the scoped changed-file formatter passes. These baseline failures do not become FDM passes, and they remain residual repository risk.

## Rollback and next evidence run

- Keep `AdditiveSimulation:ShadowEnabled=false`; no customer price is switched by these commits.
- If shadow analysis is unhealthy, disable the flag. Existing line tickets and workbook-based pricing remain unchanged.
- Profile or algorithm version changes invalidate simulation cache identity; do not reuse stale results.
- Keep support and tree outputs provisional until their separate matched-reference gates pass.
- Generate references only in restricted storage. Commit anonymized hashes and aggregate results, never CAD, customer names, source paths, 3MF, or G-code.
- After family review, freeze the candidate revision, run development comparisons, then run the untouched 12-file release holdout once. Report every blocked/failing case in the denominator and inspect the largest underquote before any cutover.

## Production release update (2026-09-20)

The earlier feature-eligibility table records the pre-release state. The production candidate now embeds an immutable X1C machine snapshot, the owner-approved Bambu Studio 0.20 mm Standard, 0.12 mm High Quality, and 0.20 mm Strength process snapshots, and all 19 FDM material mappings. A successful server result may replace legacy pricing only for an eligible material/build cell. Every unavailable, cancelled, malformed, provisional, or substitution result retains the existing price and `engineer_review_required` state.

The profile catalog contains 57 material/build cells. Forty-eight are eligible. ASA-CF, PC-FR, and PA12 remain resolvable but provisional across all three builds because the deployed artifacts are conservative vendor substitutions rather than locally resolved exact stocked-vendor profiles. HIPS is now eligible from the exact local `eSUN HIPS White @Bambu Lab X1 Carbon 0.4 nozzle` artifact (SHA-256 `A0F19BF4EE3B395302A7AACF19060601DAEB4F0E67E06932A7789D03508F6464`, density 1.05 g/cm3, maximum volumetric flow 8 mm3/s).

Official-source research confirmed:

- Bambu publishes an exact ASA-CF product/profile family for enclosed printers and hardened 0.4 mm or larger nozzles; it remains a vendor substitution because MALIEV requested eSUN or Polymaker as the stocked-vendor starting point.
- Polymaker publishes a Bambu Studio P1/X1 profile for PolyMax PC-FR. The profile is documented but could not be downloaded and resolved into the release manifest in this run, so the existing Bambu PC FR substitution remains provisional.
- Polymaker publishes PA12-CF10, not plain PA12. eSUN now publishes plain PA12 product documentation, but no exact locally resolved X1C profile was available, so plain PA12 remains provisional.
- No exact current Polymaker HIPS preset was found; MALIEV's local exact eSUN X1C HIPS profile supplies that cell instead.

Server normalization is authoritative for STL, OBJ, 3MF, GLB, and self-contained GLTF. External-buffer or transformed GLTF that cannot be represented safely fails closed. STEP/STP and IGES/IGS remain accepted customer formats, but without a production server CAD kernel their physical simulation is unavailable and the request receives the existing quote plus engineer review. No client geometry or parse failure can remove a quote.

## Issue implication

#58 should remain open: its analytical implementation exists, but its corrected acceptance scope includes matched support, feature-time, build-setting, size/fit, and holdout gates that have not run. #55 remains open for the same missing reference evidence. #56 can count the authoritative shadow boundary as implemented but still needs the approved runtime profile snapshot for automatic issuance. #60 remains open for private-corpus DFM/review-reason coverage. The umbrella issue should remain open until those independent gates close. No GitHub issue state is changed by this evidence record.
