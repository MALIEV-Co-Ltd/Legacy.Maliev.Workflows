# Historical wall-thickness design and plan — 2026-09-22

This records three Workflows-owned documents in the original, read-only
`maliev-web` history:

- [`774e0c19c7a6e6f4e8009e0b69be2a71957d2204`](https://github.com/MALIEV-Co-Ltd/maliev-web/commit/774e0c19c7a6e6f4e8009e0b69be2a71957d2204) added `docs/superpowers/specs/2026-09-22-instant-quotation-wall-thickness-analysis-design.md`, an approved design.
- [`07e92563f661354db12460f1687f5e03be70aa5b`](https://github.com/MALIEV-Co-Ltd/maliev-web/commit/07e92563f661354db12460f1687f5e03be70aa5b) added `docs/superpowers/plans/2026-09-22-instant-quotation-wall-thickness-analysis.md`, its original Razor Pages/Three.js implementation checklist.
- [`663dd8c9c36eece39cd2f641895027ac926e1183`](https://github.com/MALIEV-Co-Ltd/maliev-web/commit/663dd8c9c36eece39cd2f641895027ac926e1183) amended both documents with a compact quotation-summary requirement.

These are dated decisions, not instructions to execute their old paths,
commands, or deployment steps in the .NET 10 Legacy repositories. The
wall-thickness decision called for an independently authored, bounded
normal-ray analysis in a browser worker. ScanRuler's AGPL-3.0 source was
research evidence, not an implementation dependency. The geometric field
is process-independent; fixed presentation policies use FDM 0.8–4.0 mm and
SLA/DLP 0.6–3.0 mm limits. A material change reinterprets retained evidence.
Unmeasured/open/degenerate or resource-limited geometry must not become zero
thickness or a false safe result. The heatmap is optional, but applicable
warnings remain visible. Thickness evidence is advisory: it must not change
price, server pricing/submission contracts, review eligibility, or the
selected material. The plan required deterministic sampling, explicit
budgets, cancellation/stale-result handling, worker and browser tests,
localization, and accessibility.

The active target is Blazor/ES modules, not the original Razor/Three.js file
map. [Web issue #281](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Web/issues/281)
and [PR #292](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Web/pull/292)
ported the bounded advisory worker, transport, process policy, heatmap, and
focused target-native tests at merge
`94931cea28e1d1c95b9a788a2d2d94afdab2a8e0`.
[Exact-main CI 35900642700](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Web/actions/runs/35900642700)
succeeded. This is code-parity evidence, not proof of a deployed feature or
a full real-upload quotation journey.

The later `663dd8c9` amendment separately required a summary collapsed by
default while keeping total, lead time, Review, and engineer contact visible,
with an accessible details toggle and no repricing. The target-native summary
dock in [Web PR #293](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Web/pull/293)
and its [later refinement in PR #332](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Web/pull/332)
established the Blazor presentation. [Web PR #346](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Web/pull/346)
then placed the actual lead-time value in the collapsed `<summary>`, kept
the total and localized Show/Hide disclosure visible, and left Review,
engineer contact, and both legal links outside the hidden detail content.
Its [exact-main CI 36296081818](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Web/actions/runs/36296081818)
passed with browser tests for collapsed/expanded behavior and narrow widths.
This is target-native code and browser-fixture evidence, not a claim that a
live priced upload journey or a deployed application was verified.

This Workflows record first merged at
[`02734c7496f7a82c2681857ed0ade0cb8b41aa38`](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Workflows/commit/02734c7496f7a82c2681857ed0ade0cb8b41aa38)
with [exact-main CI 36285262361](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Workflows/actions/runs/36285262361).
Together with the Web evidence above, the three dated documentation commits
have a preserved Workflows disposition. Their original Razor/Three.js file
paths and runnable commands were not copied into the migrated runtime.
