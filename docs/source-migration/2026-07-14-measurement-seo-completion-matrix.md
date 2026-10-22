> **Historical source record: reference only.** The complete document below is preserved from the final source checkpoint. Its dates, counts, approvals, reported tests, production state, platform readbacks, capability statements and instructions describe the historical source. Every use of "current" or "live" in that body belongs to its historical context and is not a statement about this migration's current state.
>
> **Current acceptance boundary.** This archive grants no runtime, pricing, calibration, CNC expansion, private-corpus or geometry access, data-copy, credential, analytics-provider, publication, release or deployment authority. Embedded commands and instructions are historical quotations, not instructions to execute. Historical approvals do not renew media or geometry permissions. Current behavior and owner acceptance require separate reviewed evidence.

## Source provenance

Original path: `docs/seo/2026-07-14-measurement-seo-completion-matrix.md`.

Final source checkpoint: [`770cb58032969ae4a0fe169686b53ab61a44fff8`](https://github.com/MALIEV-Co-Ltd/maliev-web/blob/770cb58032969ae4a0fe169686b53ab61a44fff8/docs/seo/2026-07-14-measurement-seo-completion-matrix.md). Unchanged body Git blob: `3455f1d77fcc435d3d3ba39d16cecd7ac3583161`.

Canonical source-path owner: `Legacy.Maliev.Workflows`. Workflows is the archive custodian; this copy does not reclassify source ownership, change a resolution or accept another owner's runtime obligations.

The following source changes affect this document. Later final-source text is retained as context without additional source-commit credit.

| Source commit | Parent | Before blob | After blob |
| --- | --- | --- | --- |
| `09222471e90af81695f1b82a306201f730e5127c` | `c964d49a1616d59d19c803a43506b74e589215da` | `aa45ce8e73def8541d33b96b5d778dfca3630332` | `3f5c3b810fbec4a0b509da1bff85593a31b6974e` |

Relative references and historical identifiers in the unchanged body retain their original source context. Linked documents are not imported or accepted by this archive. No external profile, analytics account, deployment, private model or customer record was accessed or revalidated for this preservation slice.

## Unchanged historical source body

# MALIEV measurement and technical SEO completion matrix

> Current measurement status: the 2026-07-14 measurement rows are historical. See [the 2026-07-26 live measurement readback](./2026-07-26-measurement-readback.md) for the current GTM/GA4/Ads state after the latest deployment and container publication.

Audit date: 2026-07-14 (Asia/Bangkok)

Source lineage audited through the current `codex/measurement-technical-seo` branch.

Overall status: **not complete**. The application, sitemap, and public edge are validated; GA4/Ads hygiene and Search Console submission are corrected. The GTM security restriction, end-to-end measurement proof, legacy cleanup, indexed consolidation, and authority work still contain required gaps.

## Evidence rules

| Status | Meaning |
|---|---|
| **Proven — source** | Current committed source plus a fresh focused test/build directly proves the requirement before deployment. |
| **Proven — live** | Authenticated UI/API or public HTTP readback directly proves the external state. |
| **Partial** | Some required evidence is direct, but another required boundary remains absent or contradictory. |
| **Incomplete** | Authoritative evidence contradicts completion or the required implementation is absent. |
| **Owner action** | Completion requires an external communication, business proof, or release authorization that must not be inferred. |

Tests, local manifests, and draft configurations never count as proof that production or a Google surface changed.

## 1. Trusted edge, privacy, and technical SEO

| Requirement | Status | Direct evidence | Remaining acceptance gate |
|---|---|---|---|
| Permanent HTTP-to-HTTPS redirect at the public edge | **Proven — live** | GKE FrontendConfig, Ingress reference, target HTTP proxy, redirect URL map, direct origin, and Cloudflare-proxied public HTTP all read back with the permanent redirect. | Re-run the production verifier after edge changes. |
| HSTS at the public edge | **Proven — live** | GKE BackendConfig and Service reference are live, and direct-origin plus Cloudflare-proxied HTTPS return `max-age=63072000; includeSubDomains`. | Re-run the production verifier after edge changes. |
| No spoofable application-level forwarded-header trust | **Proven — source** | Current source/security contracts pass in the 155-test web suite. | Reconfirm after the exact commit is deployed. |
| Personalized pages are never publicly cached | **Proven — live** for current contact and quotation pages | Production verifier read `no-store, no-cache` on `/contact` and `/quotation`; source privacy tests also pass. | Re-run after deployment to prevent regression. |
| Consent defaults denied before analytics/ads load | **Partial** | Production source contains denied defaults before `GTM-KHDDLVRR` and no legacy container ID. | Tag Assistant must still prove pre-consent suppression and post-choice behavior after GTM clearance. |
| Meta SDK is consent-gated | **Proven — source** | Tracking privacy source tests pass. | Browser/network validation after deployment is still required. |
| One canonical owner per service intent | **Partial** | All four production owners return `200` with exact self-canonicals; legacy specialist URLs return permanent redirects. Google still selected legacy `/3d-printing` at the inspection snapshot. | Wait for the requested recrawl and confirm Google-selected canonical consolidation. |
| Exact canonical sitemap without fabricated `lastmod` | **Proven — live** | Production exposes exactly 22 unique canonical URLs, no `lastmod`, and every URL returns `200` with an exact self-canonical. Search Console downloaded the resubmission with 0 warnings and 0 errors. | Recheck after route changes and monitor Search Console processing. |
| Account utilities do not compete for organic indexing | **Proven — source/runtime** | [`2026-07-14-account-utility-indexing-readback.md`](./2026-07-14-account-utility-indexing-readback.md) records folder-wide `noindex,follow`, final-response `X-Robots-Tag`, sitemap exclusion, successful-page rendered markup, and error-response headers. The production verifier now enforces the login-page contract. | Deploy, pass anonymous production readback, then confirm stale account snippets age out after Google recrawls. |
| Stable localized alternates | **Proven — source** | Localized-alternate source tests pass and stable routes are committed. | Public English/Thai canonical and `hreflang` readback after deployment. |
| Monday-Friday 09:00-18:00; weekends closed | **Proven — live configuration; public cache pending** | Production `LocalBusiness` passes; authenticated GBP, LINE OA, and Meta messaging readbacks show the correct schedule. A 2026-07-14 Google search/crawl result for LINE still exposed the superseded 10:00-19:00 schedule, so configured state and search-visible state are not yet fully converged. | Keep special/holiday hours current; recheck Shopify/public profiles and the indexed LINE result until no 10:00-19:00 conflict remains. |
| LocalBusiness map identity and description match visible facts | **Proven — source/runtime** | [`2026-07-14-local-entity-location-readback.md`](./2026-07-14-local-entity-location-readback.md) records the shared Maps redirect and exact listing coordinates. Fresh Thai/English rendered JSON-LD parses with actual language text, `hasMap`, `13.9469417,100.4588118`, the registered Khlong Khoi address, and 09:00-18:00 hours. The organization description no longer applies a process-specific no-minimum claim to every service. | Deploy and confirm the anonymous production JSON-LD plus GBP map pin remain identical. |
| LINE OA primary; Messenger retained | **Proven — live** for the audited contact profiles and Ads assets | LINE and Meta readback documents plus Ads campaign attachment readback show both channels, with LINE primary. | Continue channel-specific measurement without promoting clicks to lead conversions. |

## 2. Measurement contract and decommissioning

| Requirement | Status | Direct evidence | Remaining acceptance gate |
|---|---|---|---|
| Persisted lead emits `maliev_lead_submitted` only after storage | **Proven — source/runtime boundary** | Measurement and queue-failure tests pass; event fields are allowlisted and contain no customer PII. The Razor-facing consume boundary is public while enqueue methods remain application-internal, and local runtime compilation renders the GTM partial without the prior access failure. | One live persisted test lead must match application record, data layer, GA4, and Ads exactly once. |
| Contact clicks emit separate LINE/Messenger/Facebook/Instagram values | **Proven — source** | Contact-channel source tests pass and preserve distinct `channel`, `destination`, and `context` fields. | Live browser/GA4 validation for all four values after deployment. |
| Contact clicks never fire an Ads conversion | **Proven — source** | Source contract excludes Ads conversion semantics for `maliev_contact_click`. | GTM Preview and Ads diagnostics must show no conversion tag for representative clicks. |
| Google review-link use is measurable without becoming a lead | **Proven — source** | The shipped-order Maps CTA emits `maliev_review_link_click` with only `platform: google_business_profile` and member-page context. It excludes order/customer identifiers and Ads conversion semantics. | After GTM clearance and deployment, validate one GA4 diagnostic event and no Ads tag in Preview/DebugView. |
| Clean GTM container `GTM-KHDDLVRR` is safe and operational | **Incomplete** | Fresh authenticated readback at 04:01 ICT in [`2026-07-14-gtm-restriction-readback.md`](./2026-07-14-gtm-restriction-readback.md) confirms that Version 1 empty container and Version 2 native-only tags are still malware-flagged; all five tags remain forcibly paused with no firing triggers. | Google security review must clear or explain the restriction before triggers are restored. |
| Clean GTM includes diagnostic interaction events | **Incomplete** | Clean Version 2 has only `CE - maliev_lead_submitted`; the promised contact and review-link triggers/variables/GA4 tags are absent. | Add only after malware clearance, then validate all four contact channels plus the Google review-link diagnostic. |
| GA4 receives clean page/lead/contact data | **Incomplete** | Admin cleanup leaves only custom `generate_lead` plus system `purchase` as key events and exactly eight allowlisted event dimensions. GTM remains unable to fire, so no end-to-end DebugView evidence exists. | After GTM clearance, validate consent, page view, persisted lead, and separate contact values without PII. |
| Google Ads receives only the approved website persisted-lead conversion | **Partial** | Obsolete upload, request-quote, and appointment actions are secondary/excluded; website persisted lead remains secondary/excluded; calls and hosted lead forms remain separately qualified. | Prove one persisted lead, then make `7682972324` primary/included only if diagnostics and application record agree. |
| Google-hosted lead forms and calls remain separately qualified | **Partial** | Account readback identifies the retained actions and PMax lead-form correction. | Verify lead quality and one-per-interaction counting where supported. |
| Legacy GTM and obsolete tags/triggers/PII variables are removed | **Incomplete** | Production no longer references `GTM-5VBH5LK`, but the contaminated container inventory still exists because the replacement is malware-paused and cannot be end-to-end validated. | After clean live validation, export one short-lived audit and delete/decommission the legacy container without leaving a parallel rollback. |
| Obsolete Google Ads conversion actions are removed or permanently excluded | **Incomplete** | Disposition is documented; no destructive cleanup occurred before replacement validation. | After clean cutover, delete removable actions and keep Google-hosted non-lead actions non-biddable where deletion is unavailable. |
| Final inventory contains no UA, Optimize, duplicate pixels, or PII scraping | **Incomplete** | Source excludes legacy identifiers, but the old active container still contains these objects. | Final signed-in GTM and Ads readback after decommission. |

## 3. Search visibility, competitors, and authority

| Requirement | Status | Direct evidence | Remaining acceptance gate |
|---|---|---|---|
| Competitor/SERP gap research | **Proven — live observation** | Dated evidence covers TKK3D, Chalawan3D, MTF3D, PWAT, Union Metal, Atachi, FactoryMax, Kolawat, and LWN3D. [`2026-07-14-competitor-refresh-and-ranking-actions.md`](./2026-07-14-competitor-refresh-and-ranking-actions.md) separates public-page evidence from variable rank observations and orders the remaining actions. | Refresh quarterly or after material SERP change; do not copy unsupported competitor claims. |
| Authenticated Search Console baseline | **Proven — live** | Domain property reports 395 clicks, 16,656 impressions, 2.4% CTR, and average position 12.8; `รับ` cohort is approximately 1,400 impressions, 4 clicks, 0.3% CTR, position 30.3. | Compare fixed complete weeks after deployment. |
| Repeatable intent-cohort reporting | **Proven — source** | `SummarizeSearchConsole.ps1` and two passing Pester tests keep printing/CNC/scanning/custom-manufacturing separate and retain unmatched queries. | Run on each complete-week export and retain the raw CSV plus JSON report. |
| Exact Thai transactional page ownership | **Partial** | Titles/H1/openings and routes are committed for printing, CNC, scanning, and custom manufacturing. Each page renders a visible bilingual Home → Services → service hierarchy with matching canonical `BreadcrumbList` JSON-LD plus a visible verified Pak Kret/Nonthaburi location, 09:00-18:00 weekday hours, Maps, LINE, and quotation module. Eight local Thai/English render checks returned `200`; the Thai `ที่` sequence rendered as `U+0E17 U+0E35 U+0E48`. Current indexed production predates the release. | Deploy, inspect, request recrawl once, and monitor query-to-page assignment. |
| Service-to-education internal links | **Proven — source** | Service pages include selected technical-guide links with localized routes. | Public crawl readback after deployment. |
| Shopify-to-service reciprocal links | **Partial** | Shopify Admin source and Thai pages contain intended backlinks; some English canonical storefront projections were stale during readback. | Recheck canonical English pages until visible source matches Admin state. |
| Qualified 3D-scanning accuracy wording | **Partial** | [`2026-07-14-scanning-accuracy-channel-audit.md`](./2026-07-14-scanning-accuracy-channel-audit.md) records corrected source/LINE wording and clear GBP, Facebook, Instagram, YouTube, TikTok, and public Threads profile readbacks. Both production scanning URLs still serve the obsolete `0.10mm` copy. | Deploy and verify the canonical/legacy route behavior, request recrawl once, and complete the Threads profile refresh through an authenticated editor. |
| Current real facility/process/inspection proof | **Incomplete** | [`2026-07-14-service-proof-provenance-and-capture-brief.md`](./2026-07-14-service-proof-provenance-and-capture-brief.md) classifies current service images as generated, third-party, or unproven for operational use and defines the fail-closed evidence manifest. No approved proof module per service is proven live. | Owner supplies/approves one real project media set and factual record per specialist service using [`service-proof-evidence.template.json`](./service-proof-evidence.template.json); then publish and verify each module. |
| GBP prominence and reviews | **Partial** | Hours are corrected, but authenticated profile had only 5 reviews and no new photo for 2,484 days. [`2026-07-14-post-shipment-review-workflow.md`](./2026-07-14-post-shipment-review-workflow.md) records a source-validated, non-incentivized order-detail invitation gated on canonical `Shipped` history, with customer arrival confirmation and a separate LINE issue route. | Deploy and verify the authenticated customer UI; add current real GBP photos and monitor review volume without rewards, sentiment filtering, or pressure. |
| Relevant industrial citations/backlinks | **Partial** | Thirteen current first-party candidate routes, eligibility boundaries, destination rules, and execution waves are documented in [`2026-07-14-authority-citation-inventory.md`](./2026-07-14-authority-citation-inventory.md). The public discovery pass also found existing D&B, Ensun, and ThaiThurkic references plus a stale indexed LINE profile; none was falsely counted as a newly acquired citation. | Reconcile known profile conflicts, perform authenticated duplicate searches, then validate/claim candidates individually and record each live relevant referring URL. Membership fees or exhibitions require owner approval. |
| Search Console recrawl/index requests | **Proven — live request** | Search Console accepted one priority crawl request for each service owner after validating the live release and resubmitted 0-warning sitemap. [`2026-07-14-google-platform-and-indexing-readback.md`](./2026-07-14-google-platform-and-indexing-readback.md) records the pre-request states. | Wait for processing; confirm new crawls and Google-selected canonicals without repeated submission. |
| AI Overview/AI Mode observation | **Partial** | Owner screenshots establish the initial absence and competitor citations; Google exposes no guaranteed AI-citation KPI. | Record controlled weekly observations while treating Search Console/qualified leads as primary evidence. |
| Mobile service-page JavaScript and icon delivery | **Partial** | [`2026-07-14-service-page-performance-readback.md`](./2026-07-14-service-page-performance-readback.md) records removal of the Font Awesome DOM-replacement runtime, repair of corrupt 6.7.2 webfonts, clean Chromium icon/font/Thai readback, and two after-samples with zero Font Awesome JavaScript work. | Deploy, then remeasure production Lighthouse and Search Console Core Web Vitals; current field data still contains 16 poor mobile URLs and the local LCP samples did not improve. |

## 4. Customer messaging and localization

| Requirement | Status | Direct evidence | Remaining acceptance gate |
|---|---|---|---|
| LINE OA profile, welcome/away behavior, FAQ paths, and rich menu | **Proven — live** | Authenticated readback records corrected hours, bilingual guidance, primary contact path, and published rich-menu state. | Recheck after any LINE OA editor change. |
| Meta Facebook/Instagram greeting, away schedule, and FAQ routing | **Proven — live** | Authenticated Meta readback records distinct bilingual messages, weekday schedule, LINE/quotation/human routes, and no invented promises. | Recheck after any inbox automation change. |
| YouTube profile service, hours, and contact copy | **Proven — live** | [`2026-07-14-youtube-profile-readback.md`](./2026-07-14-youtube-profile-readback.md) records signed-in Studio saved state plus propagated public metadata with corrected Thai, confirmed hours, LINE-first routing, quotation upload, and Messenger. | Recheck after future channel-profile changes; keep click behavior diagnostic rather than a primary Ads conversion. |
| TikTok profile service, hours, and contact copy | **Proven — live** | [`2026-07-14-tiktok-threads-profile-readback.md`](./2026-07-14-tiktok-threads-profile-readback.md) records the signed-in editor, exact 67-code-point bio, saved visible copy, and matching public metadata. | Recheck after future profile changes; keep LINE clicks diagnostic rather than a primary Ads conversion. |
| Threads profile service, hours, and contact copy | **Partial** | The same readback proves the canonical `@maliev.manufacturing` identity and no contradictory scanning number, but the public profile lacks hours/LINE and its editor required an unavailable Instagram login. | Refresh through an authenticated Instagram/Threads session and verify the canonical public profile. |
| Thai typography and tone marks in generated contact creative | **Proven — rendered/live** | [`2026-07-14-line-rich-menu-typography-readback.md`](./2026-07-14-line-rich-menu-typography-readback.md) records local Inter/Noto Sans Thai sources, inline SVG icons, exact `ที่` code points, byte-identical fresh renders, and the authenticated LINE OA rich-menu readback. | Re-run the deterministic render/readiness check after any copy, font, icon, or layout change. |

## 5. Fresh verification evidence

Commands run on 2026-07-14 against the audited commit:

```text
dotnet test .\Maliev.Web.Tests\Maliev.Web.Tests.csproj -c Release --no-restore --nologo
Passed: 168, Failed: 0, Skipped: 0

dotnet build .\Maliev.Web\Maliev.Web.csproj -c Release --no-restore --nologo
Build succeeded. 0 warnings, 0 errors.

Invoke-Pester .\Maliev.Web\tests\ProductionSeoVerifier.Tests.ps1
Passed: 19, Failed: 0

Invoke-Pester .\Maliev.Web\tests\SearchConsoleCohortReport.Tests.ps1
Passed: 2, Failed: 0
```

Fresh production readback after the application release shows denied consent defaults, only `GTM-KHDDLVRR`, no `GTM-5VBH5LK` or `UA-133315708-1`, a 22-route sitemap with no `lastmod`, and 22 successful exact-canonical page responses. GKE and Cloudflare-proxied public traffic now pass the permanent redirect and exact HSTS policy. The repaired verifier passed all 32 checks in `production-seo-audit-2026-07-14-post-edge.json`. GTM remains malware-paused, so production source correctness is not end-to-end measurement proof. See [`2026-07-14-google-platform-and-indexing-readback.md`](./2026-07-14-google-platform-and-indexing-readback.md).

Authenticated GTM readback at `2026-07-14T04:01:35+07:00` confirmed that live/latest clean-container Version 2 remains malware-flagged. The native GA4 event, Google tag, Conversion Linker, Google Ads tag, and persisted-lead conversion tag are all forcibly paused and have no firing triggers. Empty Version 1 remains flagged as well. No tag was unpaused and no legacy or Ads cleanup was attempted. See [`2026-07-14-gtm-restriction-readback.md`](./2026-07-14-gtm-restriction-readback.md).

Local runtime readback covered the Thai and English variants of `/services/3d-printing`, `/services/cnc-machining`, `/services/3d-scanning`, and `/services/custom-manufacturing`. All eight responses returned `200`; each visible breadcrumb contained its localized current-page name, and each parsed `BreadcrumbList` contained exactly three ordered entries with culture-correct canonical URLs. A subsequent `/services/3d-printing` readback returned `200` and parsed all five JSON-LD blocks; its `LocalBusiness` object contained `hasMap: https://goo.gl/maps/AXqLnqUu5dM2`, coordinates `13.9469417,100.4588118`, the registered address, and 09:00-18:00 hours. The authenticated order-detail review workflow has direct model/source coverage, including canonical `Shipped` eligibility, positive-or-critical review wording, shared Maps/LINE destinations, no incentive, and exact Thai tone-mark preservation. A local browser interaction with a temporary non-production review anchor queued exactly `{ event: "maliev_review_link_click", platform: "google_business_profile", context: "other" }` in the page's main `dataLayer`, produced no console warnings/errors, and the fixture was removed immediately afterward. The production order CTA derives `context: "member"` from its actual route. This is source/runtime evidence only until the exact release is deployed.

## 6. Ordered completion path

1. **GTM security review:** submit the prepared malware-review case with owner confirmation; do not manually unpause flagged tags.
2. **GTM clearance and Preview:** synchronize from live Version 2, add the allowlisted diagnostic contact slice, attach intended triggers, and prove consent plus event behavior in Preview.
3. **GA4/Ads validation:** match one persisted lead across application storage, data layer, GA4, and Ads; separately validate all four contact channels as diagnostic only.
4. **Destructive cleanup:** export short-lived legacy evidence, delete/decommission the contaminated GTM configuration, and remove/exclude obsolete Ads actions. Read back the final inventories.
5. **Indexing:** wait for the four accepted requests, then retain new crawl, canonical, rendered-page, impression, and position evidence.
6. **Prominence and proof:** publish real service proof, add current GBP photos, run policy-compliant review requests, and validate relevant citation opportunities one at a time.
7. **Weekly control loop:** keep the 32-check production verifier green and compare complete Search Console cohorts, GBP actions, GA4 channel splits, and qualified persisted leads; annotate releases and tracking changes.

The active goal can be marked complete only after the GTM, end-to-end measurement, cleanup, indexing-follow-up, and authority gates have direct evidence. A green production verifier, a support case, or an indexing request alone is insufficient.
