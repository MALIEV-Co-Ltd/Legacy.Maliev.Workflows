# Historical additive pricing-integrity decision — 2026-09-14

This record preserves the original `maliev-web` design
[`d957038a208b2cbdf1604010a6d82f1d74f1a06c`](https://github.com/MALIEV-Co-Ltd/maliev-web/commit/d957038a208b2cbdf1604010a6d82f1d74f1a06c),
implementation plan
[`2128395c31a1ebfe94f9d0ced846bdc861fe62f4`](https://github.com/MALIEV-Co-Ltd/maliev-web/commit/2128395c31a1ebfe94f9d0ced846bdc861fe62f4),
validation/plan update
[`60d3677264e046fd73028ff3ccb75097d153bedb`](https://github.com/MALIEV-Co-Ltd/maliev-web/commit/60d3677264e046fd73028ff3ccb75097d153bedb),
and release merge
[`2d126d1d55a3240e40678136e6aa621c7f10ed47`](https://github.com/MALIEV-Co-Ltd/maliev-web/commit/2d126d1d55a3240e40678136e6aa621c7f10ed47).
The source plan's Razor Pages paths, old issue numbers, deploy steps, and
`additive-2026-09-14.v1` policy version are historical, not commands or
current release authority for the .NET 10 Legacy repositories.

The architectural contract is still relevant: physical FDM profiles model
layer height, walls, infill, skins and speed; bounded layer-overlap evidence
informs support cost without treating browser geometry as manufacturing
metrology; resin cost uses occupied plates for each quantity tier and
canonical Standard rather than FDM profiles. Server-protected, short-lived
line and order tickets bind part/session identity, policy, canonical THB
money, destination and shipping state before a downstream quotation or order
write. Foreign-currency pricing must fail closed without a valid rate;
international delivery is explicitly to be quoted, not silently charged
domestic shipping. Payment stays disabled pending engineering review.

The migration is tracked by [Web #256](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Web/issues/256)
and [Web PR #258](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Web/pull/258),
merged at `ad393a5c5c74174a2a8f8989d0bf03263c20e42d` with
[successful CI run 34948586706](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Web/actions/runs/34948586706).
The target uses `additive-2026-09-19.v2`, not the superseded source
policy version. Target evidence includes the FDM profile and physical
calculator, unsupported-area contract and geometry worker, resin pricing,
shipping calculator, protected ticket service, submission service, and
pricing/workflow/browser regressions. The original validation commit's
test intent is represented by those target tests; the original test files
are not copied as runnable tests because their Razor Pages and source
application paths do not apply to the Blazor target.

This is source-to-code and test evidence, not an authenticated production
quotation, real-upload/browser end-to-end pass, database parity proof, or
deployment. The source design approved a one-time production release of
the original application; it does not authorize deploying any Legacy
application or changing traffic. Exact-main Aspire acceptance and a
separately approved deployment remain cutover gates.
