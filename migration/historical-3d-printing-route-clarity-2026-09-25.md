# Historical 3D-printing quotation route decision — 2026-09-25

Original `maliev-web` commit
[`eb52167166e12d832ea6c800795a8357d526f759`](https://github.com/MALIEV-Co-Ltd/maliev-web/commit/eb52167166e12d832ea6c800795a8357d526f759)
added `docs/superpowers/plans/2026-09-25-3d-printing-route-clarity.md`.
This is a dated decision record, not a runnable implementation or deployment
checklist for the .NET 10 Legacy repositories.

The decision was to make two existing quotation paths immediately distinguishable
on `/services/3d-printing`: FDM/resin parts can seek an instant estimate, while
industrial, metal, safety-critical, or requirement-led parts should request
engineering review. English and Thai labels, route destinations, and stable
route hooks make the choice testable. Review guidance should state what model,
drawing, material, quantity, use, and critical requirements to provide and what
the engineer must confirm. A supported file extension alone does not promise an
instant price.

The owner-confirmed claim boundary was a compact facility inventory. The page
must not imply a large equipment fleet or in-house SLM/DMLS ownership, add an
equipment showcase, or disclose suppliers or fulfillment arrangements. This
slice did not change the quotation calculator, persistence, APIs, metadata,
consent/lead events, pricing, or material catalogue.

The migrated Web implementation is tracked by [issue #315](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Web/issues/315)
and [PR #317](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Web/pull/317),
merged as `196bde33e2b26fe2553b3440a47e2f85fc4d7b3f`. The [route page](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Web/blob/196bde33e2b26fe2553b3440a47e2f85fc4d7b3f/Legacy.Maliev.Web/Components/Pages/Services/ThreeDimensionalPrintingContent.razor),
[responsive styles](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Web/blob/196bde33e2b26fe2553b3440a47e2f85fc4d7b3f/Legacy.Maliev.Web/wwwroot/src/app/css/service-pages.css),
[route contract tests](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Web/blob/196bde33e2b26fe2553b3440a47e2f85fc4d7b3f/Legacy.Maliev.Web.Tests/ThreeDimensionalPrintingParityTests.cs)
are the migrated code and test evidence. [Exact-main CI run 36185964751](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Web/actions/runs/36185964751)
succeeded at that merge SHA. This is code-parity evidence, not proof of a public
deployment or production measurement outcome. The source plan's old deploy and
rollback steps confer no authority to release the migrated service.
