> **Historical source record — migration provenance only.** This is the original September 2026 record preserved from source commit `67a798e5cee4f66e913e08804e7218af5774e98f`. Its approvals, operational state, reported tests, prices, corpus access and release steps describe that historical source. They do not authorize actions in this migration or establish current Legacy.Maliev service behavior. No private corpus, vendor installation, workbook or physical production evidence was accessed or revalidated for this documentation slice. References to missing family review, matched references, effective profiles and production observations remain unresolved evidence boundaries. Current implementation and validation require separate owner-specific evidence.

# Additive quotation production completion plan

## Objective

Resolve the implementation-ready portions of issues #56-#64, release the validated
legacy-web changes, and close only issues whose acceptance boundary is actually met.

## Owner decisions

- FDM profiles are Bambu Lab X1C `0.12mm High Quality`, `0.20mm Standard`, and
  `0.20mm Strength`, with official Polymaker presets and the operator-provided eSUN
  X1C exports as filament evidence.
- Resin pricing may use a conservative, research-backed generic MSLA profile. It must
  remain labelled preliminary and include enough commercial protection to avoid
  knowingly loss-making quotes.
- Printers are available 24 hours per day, are normally idle, and have no queue feed.
  Customer lead time is therefore calculated from occupied machine time with the
  existing two-day promise buffer.
- Paid-order and realized-margin reconciliation belongs to the future .NET 10 system.
  The legacy site must preserve quote receipts and must not infer settlement from bank
  transfer or Thai QR records.

## Slices

1. Bind every protected line quote to a server-computed upload hash and upload revision;
   reject invalid geometry and stale/replaced uploads at submission.
2. Activate the workbook-sequence order calculator and persist its auditable breakdown
   in the protected order receipt.
3. Record approved FDM profile evidence and add the conservative generic resin profile
   with explicit provenance and preliminary confidence.
4. Persist review/DFM confidence and calculate a capacity-based lead-time range from
   the verified line receipts.
5. Validate build, focused tests, affected suite, formatting, and static checks.
6. Triage #56-#64 against evidence. Keep isolated slicing and future finance work open
   when their production dependencies remain absent.
7. Push the exact validated commits to `main`, deploy that exact revision through the
   repository release path, and verify public English/Thai quotation behavior.

## Commit boundaries

1. Trusted upload identity and quote receipt v2.
2. Auditable commercial total and lead-time/review receipt.
3. Profile evidence, generic resin policy, and operational documentation.
4. Release documentation only when required by repository policy.
