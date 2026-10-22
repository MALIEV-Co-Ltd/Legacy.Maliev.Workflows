> **Historical source record: reference only.** The complete document below is preserved from the final source checkpoint. Its dates, counts, approvals, reported tests, production state, platform readbacks, capability statements and instructions describe the historical source. Every use of "current" or "live" in that body belongs to its historical context and is not a statement about this migration's current state.
>
> **Current acceptance boundary.** This archive grants no runtime, pricing, calibration, CNC expansion, private-corpus or geometry access, data-copy, credential, analytics-provider, publication, release or deployment authority. Embedded commands and instructions are historical quotations, not instructions to execute. Historical approvals do not renew media or geometry permissions. Current behavior and owner acceptance require separate reviewed evidence.

## Source provenance

Original path: `docs/seo/2026-09-03-scanning-sample-display-plan.md`.

Final source checkpoint: [`770cb58032969ae4a0fe169686b53ab61a44fff8`](https://github.com/MALIEV-Co-Ltd/maliev-web/blob/770cb58032969ae4a0fe169686b53ab61a44fff8/docs/seo/2026-09-03-scanning-sample-display-plan.md). Unchanged body Git blob: `a053f5c5e4bb05edefa588b0c3b0df8d723f1bb1`.

Canonical source-path owner: `Legacy.Maliev.Workflows`. Workflows is the archive custodian; this copy does not reclassify source ownership, change a resolution or accept another owner's runtime obligations.

The following source changes affect this document. Later final-source text is retained as context without additional source-commit credit.

| Source commit | Parent | Before blob | After blob |
| --- | --- | --- | --- |
| `e7d5fcca8d09aa98ff335ac178989a55a29ef9af` | `eb1dce3cf9169c20647a61e9c8481db67e08f232` | `dbaa46e02a31fc10d81f36d2157a8f721d52e6df` | `df4f67d13cda67d7ed2cd1d81cfcce92a98d650c` |
| `e31a94baeb02d33c8484e886843c825c89a90b1c` | `e7d5fcca8d09aa98ff335ac178989a55a29ef9af` | `df4f67d13cda67d7ed2cd1d81cfcce92a98d650c` | `8f9e8d1dcadf22907b5a798522c9473cc62863e3` |
| `31d470efcc13b9c041a3aac0247e3eae79b90fe0` | `e31a94baeb02d33c8484e886843c825c89a90b1c` | `8f9e8d1dcadf22907b5a798522c9473cc62863e3` | `a053f5c5e4bb05edefa588b0c3b0df8d723f1bb1` |

Relative references and historical identifiers in the unchanged body retain their original source context. Linked documents are not imported or accepted by this archive. No external profile, analytics account, deployment, private model or customer record was accessed or revalidated for this preservation slice.

## Unchanged historical source body

# Scanning sample display plan

Prepared September 3, 2026 for the scanning proof handoff. The owner subsequently replied **"yes approve"** to the exact cast-housing screenshot case and production release. That approval covers the image comparison below, not distribution of scan or CAD geometry. No production sample or measurement is invented.

## Approved screenshot implementation

The scanning service page now contains a real cast-housing **Scan / CAD** comparison ahead of the generic workflow guide. The owner-reviewed close-up pair is the approved subject; two real geometry exports use the same orthographic camera, framing and original coordinates. A single-housing STEP was kernel-validated to select the close-up region; the full scan and full CAD geometry were retained during rendering. No source geometry was modified or independently fitted to the image bounds.

The selected scan's cleanup history and physical STL units are unconfirmed, so the public label says **Scan / สแกน**, not **raw scan**, **cleaned**, **accurate**, or **measurement result**. Visible feature correspondence supports this limited comparison; no dimensional tolerance, inspection pass, camera capture location, operator, customer identity, or manufacturing outcome is asserted. The rendered source pair is derived from actual supplied project geometry, not AI-generated media. A same-case photograph or deviation report was not found and is not fabricated. The general future-proof-set requirements below remain applicable to any broader case study.

Native buttons offer Compare, Scan, CAD and Side by side in a connected neutral-grey group. The owner-requested follow-up removes the extra quotation CTA from this sample section; the existing quotation links elsewhere on the page remain. A 28-pixel round in-image handle has a 44-pixel hit target, accessible slider semantics and keyboard navigation. Pointer capture, disabled native image dragging and a touch-safe handle support continuous dragging. The separate lower range input has been removed at the owner's request. Pointer interaction suppresses the handle outline and border; keyboard interaction and subsequent keyboard refocusing retain a visible neutral focus ring. Without JavaScript, the two complete images and captions remain visible; mobile stacks that fallback. The existing Thai/English culture configuration and Thai fallback for unsupported cultures are preserved. No model viewer, model download, new tracking event or schema claim is added. Quotation routing remains the existing scanning quotation route.

Private original-image hashes (the source paths and customer identifiers stay in the existing internal attachment manifest):

| Approved original | SHA-256 |
|---|---|
| Scan close-up, 2400 x 1600 | `f9be66f6a2f1ef6f416ff5f786592e14f8c4fd0eb56df98cfe4289326d59b6ee` |
| CAD close-up, 2400 x 1600 | `4b7a4a5a90d9afa5ed314218fd580daf1eccd468fc7650c1e0b5cca3811b6bf5` |

Website derivatives use RGB WebP, quality 86, Lanczos resizing and the same 3:2 framing. The encoder omits source metadata. Every filename below is under `/src/images/services/scanning/proof/`; no source model is deployed. Images are lazy-loaded below the hero, with intrinsic dimensions and responsive candidates.

| Derivative | Bytes | SHA-256 |
|---|---:|---|
| cast-housing-scan-480.webp | 14914 | `03bd9205d3f6cd3610d4899570568a2b26ab6297b8d755dd5409997f65192de9` |
| cast-housing-scan-900.webp | 50464 | `83ac222ea2ceb36e0f694b3a1f5c5a221f9e89b45fd2f27c7e7499faef321d92` |
| cast-housing-scan-1500.webp | 153306 | `b7b763abd8f3ce6247675a4aab1c5e8bbb67094084bc6e5aad08a0e7083f3ebc` |
| cast-housing-cad-480.webp | 14926 | `a207c8c85b478cb9d1acda13288bd02dbc74f6418bc9bea301e2dbdb6a26a20d` |
| cast-housing-cad-900.webp | 38820 | `06cbfbb0f5922d06596646848cfbd644dd54e74e9c10aec06650b068c613a722` |
| cast-housing-cad-1500.webp | 81882 | `5f52eb0e9745ae493bc7c7b8ff932b13c9c7ddfe55120952c36be732b3107563` |

Deploy the Razor view, dedicated comparison CSS/JS and all six WebP files together through the existing Web release. No configuration, migration, API contract or authentication change is required. Production deployment remains with the coordinating task. Reverting this module restores the prior page; retained private originals and approval records are not deleted.

### Owner-requested grey and edge revision

Both surfaces use diffuse RGB (0.64, 0.64, 0.64), the unchanged approved camera and unchanged source geometry. The scan displays all 1,209,129 original triangle faces and their real edges without decimation. The CAD displays 5,256 actual B-rep edge curves; surface tessellation diagonals are disabled. CAD ambient occlusion uses VTK SSAO (radius 20 source-coordinate units, bias 2, kernel 256, blur enabled, MSAA disabled), with specular 0.24 and power 40 for a slight sheen. These rendering settings do not establish physical units or dimensional accuracy. Finest scan triangles become texture when downsampled on mobile.

The PNG and derivative hashes above now identify this requested revision. All image src and srcset URLs carry `?v=grey-edges-20260903` to avoid serving the former blue CAD from browser caches. The existing private derivative manifest retains source provenance and exact rendering settings; no private model or customer identifier is published.

### Grey and edge revision validation

- `dotnet build Maliev.Web.Tests/Maliev.Web.Tests.csproj -c Release -v quiet`: zero warnings, zero errors.
- Focused `ScanningComparisonBrowserTests`: 9 passed, zero failed/skipped. Includes 30-step mouse dragging with zero native image drag events, real Chromium touch input from 50% to 75% without page scrolling, keyboard/modes, exact 28-pixel circular handle and 44-pixel hit target, short labels, removed lower range, locales and no-JavaScript fallback.
- Full `Maliev.Web.Tests` suite: 668 passed, zero failed/skipped; duration 9 minutes 18 seconds (`scanning-grey-full-suite.trx`).
- `dotnet format whitespace ... --verify-no-changes`, Node syntax, CleanCSS parsing and `git diff --check`: passed.
- All six final image byte counts and SHA-256 hashes matched the derivative manifest. Full-size source renders and actual desktop/mobile page renders were visually reviewed.
- Linux self-contained Docker build: zero warnings/errors. Thirteen packaged asset hashes matched source, including the six new images, dedicated CSS/JS, shared bundles and existing policy PDF.

### Initial implementation validation (before this revision)

- `dotnet build Maliev.Web.Tests/Maliev.Web.Tests.csproj -c Release --no-restore -v quiet`: passed with zero warnings and zero errors, including the Web/Razor project.
- `dotnet test Maliev.Web.Tests/Maliev.Web.Tests.csproj -c Release --no-build --no-restore --filter FullyQualifiedName~ScanningComparisonBrowserTests`: 8 passed. Verified TH/EN at 390/1440 pixels, unsupported RU retaining the existing Thai fallback, native Home/End/arrows, visible focus, all display modes, pointer dragging, decoded lazy images, quotation destination and the no-JavaScript fallback.
- `dotnet test Maliev.Web.Tests/Maliev.Web.Tests.csproj -c Release --no-build --no-restore --logger "trx;LogFileName=scanning-comparison-full-suite.trx"`: 667 passed, zero failed, zero skipped; duration 8 minutes 40 seconds.
- `dotnet format whitespace Maliev.Web.Tests/Maliev.Web.Tests.csproj --no-restore --include Maliev.Web.Tests/ScanningComparisonBrowserTests.cs --verify-no-changes`: passed after applying the repository's CRLF/no-final-newline convention to the new test file.
- Node syntax check, ESLint `no-undef`/`no-unused-vars`, scoped CSS parse/minification, and `git diff --check`: passed. All six images decoded at the documented dimensions, matched their hashes and contained no EXIF/XMP/ICC source metadata.
- Desktop and Thai mobile rendered screenshots were visually inspected. No new geometry viewer, downloadable geometry, analytics event, qualification rule or shared layout behavior was introduced by this slice. Live production verification belongs to the coordinated release.

## Recommended presentation

Lead with a real part photograph and a matched **raw scan / reconstructed CAD** comparison. Offer **View in 3D** as an optional second level. The comparison explains the deliverable immediately; 3D lets an interested buyer inspect less visible surfaces without making every visitor load the geometry.

For the first case, use this order:

1. Real part photograph and a short factual task description.
2. Matched scan/CAD images with a draggable divider. Include **Raw scan**, **CAD** and **Side by side** buttons, so dragging is never the only way to inspect either image.
3. A concise deliverable explanation: what was measured, what was reconstructed, what files were supplied, and what was outside scope.
4. Optional **View in 3D** panel with Raw scan / CAD controls and a shared camera. Start with one panel; do not mount several heavy viewers down the page.
5. A genuine deviation report or drawing extract only when that same case has an approved report. End with the existing scanning quotation and contact routes.

Do not use a prettier/smoother surface as a claim of accuracy. A scan-derived mesh and a reconstructed design are different deliverables. A visualization mesh does not demonstrate an editable feature tree, watertight solid, manufacturing readiness or dimensional compliance.

## Comparison-image contract

The two pictures must show the same part and region, using identical camera projection, angle, framing, scale, orientation, background and lighting. Use the same clipping/crop. The approved grey/edge revision intentionally adds CAD ambient occlusion and sheen as display treatment while retaining the shared camera and base lighting. Do not independently normalize the two models to their bounding boxes: that can conceal a scale or dimensional difference.

Create the views from actual source geometry, not generated artwork. Preserve holes, damage, missing scan coverage and real surface differences. Label any cleanup explicitly; a repaired mesh is not the raw capture. Use two or three useful views if one angle hides the changed features. Keep original files unchanged and record the export transform and units separately.

The ordinary view must work without JavaScript: two labeled images and their explanations. Enhance it with an accessible in-image slider handle and separate view buttons. Support keyboard arrows, visible focus and touch; do not rely only on color or a dragging gesture. On narrow screens, offer full-width Raw scan/CAD views rather than making two tiny images the only option. Maintain enough contrast for mesh edges against the background.

Suggested captions, to adapt only to verified facts:

- Raw scan / ข้อมูลสแกน: captured surface geometry, including the case's actual gaps or surface condition.
- Reconstructed CAD / CAD จาก Reverse Engineering: surfaces/features rebuilt for the stated deliverable.
- Comparison / เปรียบเทียบ: the same camera and scale; visual comparison is not a dimensional inspection report.

## Interactive-model contract

- Keep original scan files (STL, PLY, OBJ or the actual scanner format) and engineering CAD (STEP/IGES/native) private unless their exact release is approved.
- Create GLB display derivatives from approved geometry. A GLB preview contains tessellated visual geometry; it is not the downloadable editable CAD deliverable.
- Use one shared coordinate system, orientation and scale for both display derivatives. Record verified source units and conversion transforms. If alignment or scale is unknown, do not offer a misleading synchronized comparison.
- Export only the exterior/detail necessary to illustrate the service when confidentiality requires it, subject to explicit geometry approval. Publicly delivered 3D geometry can be retrieved by visitors; removing a download button does not protect it.
- Show a lightweight poster first. Load viewer code and model data only after View in 3D. Give each state a loading indicator, useful error message and a static-image fallback.
- Keep vertical page scrolling usable on touch devices, permit keyboard operation, and avoid automatic rotation. Respect reduced motion.
- Set a measured preview budget before publishing: initially target no more than 5 MB per display model, then validate visual fidelity and interaction on a representative mobile device. This is a design target, not evidence that any source meets it. Do not decimate away the features being demonstrated merely to meet the budget.
- Do not expose customer file names, internal folder paths, job numbers, annotations, title blocks or identifiers in URLs, mesh/node names, image metadata or visible captions.

An image-first comparison is the initial release recommendation. Add 3D for the best one or two suitable cases after actual model sizes, rights and mobile performance are known. A short recorded turntable can be an optional fallback for a very complex model, but it does not replace the direct image comparison or the real deliverable explanation.

## Measured-deviation evidence

Use a color map only from a real comparison for the same case. Record the reference model, alignment method (for example datum alignment or best fit), units, signed color scale, tolerance if one was actually agreed, excluded/unmeasured regions and the source report. Keep display mesh simplification separate from inspection calculations.

Do not invent ± values, reuse a scanner's advertised resolution as part accuracy, or label an all-green image as a pass without the actual acceptance criteria. Hide this section when a report is unavailable.

## Source and approval records

Reuse [the existing evidence template](service-proof-evidence.template.json) and [provenance brief](2026-07-14-service-proof-provenance-and-capture-brief.md). Keep the already approved September 2 local-proof register as the preparation record. Do not create a replacement provenance registry.

For each candidate, add an internal attachment manifest alongside that record containing:

- A nonidentifying candidate alias and references to the existing evidence record.
- Read-only source paths, format, bytes and SHA-256 for the raw scan, CAD, real photograph and optional report.
- Evidence that the scan and CAD are the same project/part. A matching filename or folder alone is only a candidate signal.
- Source units, coordinate frame, any registration/export transforms and whether these were verified or remain unknown.
- Raw versus cleaned mesh state; reconstruction/drawing/inspection scope and the factual reviewer.
- Exact media and geometry release permission, customer confidentiality disposition, privacy reviewer and approval date.
- Derivative paths/hashes, export settings, display role and Thai/English captions/alt text.

Folder access permits investigation. Customer publication rights and project facts must be established for the selected files. Website model derivatives and documentary Google Business Profile photos are separate placements. Previously published photos remain ineligible for the new-GBP-photo task; that does not by itself determine a different website placement's rights.

## Acceptance and rollout

Before implementation: select at most one scan-to-CAD case and one drawing-to-part case; resolve pairing, units, geometry/media permission and factual deliverables. No placeholder case is published while these facts are missing.

After the actual files arrive: render matched image exports, review the static comparison first, then evaluate whether the 3D preview materially helps. Preserve the existing distinction between scan-only mesh, additional reverse-engineering CAD and additional DWG drafting. Preserve quotation/contact routing and the frozen Printing experiment.

For a future source change, build the affected project with zero warnings/errors, run focused interaction/provenance tests and the affected suite, then verify Thai/English rendering, keyboard/touch controls, no-JavaScript fallback, absent WebGL/model-load failure and model requests occurring only after activation. Confirm real image/model hashes, URL/metadata privacy and preview performance. Review exact public assets before release; retain original files and approval records when rolling back a module.

## Sources

- [model-viewer loading and posters](https://modelviewer.dev/examples/loading/): poster/manual-reveal and delayed model presentation patterns.
- [model-viewer API](https://modelviewer.dev/docs/index.html): glTF/GLB support and loading/camera controls. Library choice remains an implementation decision; the existing quotation viewer is not assumed reusable without inspecting its upload/auth coupling.
- [W3C slider pattern](https://www.w3.org/WAI/ARIA/apg/patterns/slider/): keyboard semantics and touch-assistive-technology limitations motivate the explicit buttons and static fallback.

These sources support implementation mechanics, not a claim of increased conversions. The display recommendation is a design judgment for explaining MALIEV's engineering deliverables.

## Connected controls follow-up validation

Owner-requested neutral connected controls, sample CTA removal and pointer-only focus treatment: source/Linux builds zero warnings/errors; 11 focused browser cases passed including TH/EN at 320 pixels and pointer-to-keyboard focus recovery; full Web suite 670 passed, zero failed/skipped (6 minutes 9 seconds). Scoped whitespace/Node/CSS/diff checks passed, and all 13 packaged asset hashes matched source. Source geometry and public render files are unchanged.
