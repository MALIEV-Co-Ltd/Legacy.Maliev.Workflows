> **Historical source record: reference only.** This document preserves the 2026-07-26 measurement readback. Dates, counts, approvals, platform states, test results and production claims describe the historical source. They are not current status or independently revalidated evidence.
>
> **Current acceptance boundary.** This archive grants no Ads, GTM, GA4, Search Console, billing, credential, customer-data, financial, runtime, release or deployment authority. Embedded commands and instructions are historical quotations and must not be executed from this archive. Diagnostic events, persisted submissions, qualified business leads and revenue remain distinct historical contracts.

## Source provenance

Original path: `docs/seo/2026-07-26-measurement-readback.md`.

Source checkpoint: `770cb58032969ae4a0fe169686b53ab61a44fff8`. Original final body Git blob: `4484ff1986b59beb0b53e67a1e9891bc4bc78251`. The body below retains that final source with exactly the two privacy substitutions listed below. It is **not byte-identical** to the original source. No other body text is changed.

| Source commit | Parent | Readback before blob | Readback after blob |
| --- | --- | --- | --- |
| `6f8a3d7937811f0b5e6e6a9ec062728672bee507` | `c050c0f57b0744891bd962995c7282ddaaa94605` | absent | `02008a8c3f5224d0bdab196e3259e798ee316248` |
| `d2c79249a4d5a314ccb4e8d99685e127ef06c1b0` | `6f8a3d7937811f0b5e6e6a9ec062728672bee507` | `02008a8c3f5224d0bdab196e3259e798ee316248` | `5dabb08a085d6606043dd2aefeca3d396a0067d7` |
| `b05f822e374f27f82b08887af8fbf572d86df473` | `d2c79249a4d5a314ccb4e8d99685e127ef06c1b0` | `5dabb08a085d6606043dd2aefeca3d396a0067d7` | `07247c8e0a0fa6ab2c5fcbb649756b33cf522283` |
| `c8e05585b3e7481ae95adcee86c08d904b116373` | `b05f822e374f27f82b08887af8fbf572d86df473` | `07247c8e0a0fa6ab2c5fcbb649756b33cf522283` | `f16e7ac4250e3b4c42ad6a29a13cc2cdda97e84b` |
| `c63b0cdc06b455d64d1dfcc9226d845d7386e8df` | `c8e05585b3e7481ae95adcee86c08d904b116373` | `f16e7ac4250e3b4c42ad6a29a13cc2cdda97e84b` | `4a9fd896bc34e38055fd09149c56c92218850376` |
| `98d5dc59384089a7af0711cbed7ca632cc8f1dce` | `c63b0cdc06b455d64d1dfcc9226d845d7386e8df` | `4a9fd896bc34e38055fd09149c56c92218850376` | `bc61b9f7f9d2b57f7ba49e7bd478df8e3d338b10` |
| `6e74329a7c670ddcc8785f2cc12351ec92eaf9c7` | `98d5dc59384089a7af0711cbed7ca632cc8f1dce` | `bc61b9f7f9d2b57f7ba49e7bd478df8e3d338b10` | `6695e6cf69460e0238570d108a37fac2b617b965` |
| `c1322c3880250f5fbadbd7a31f76fdcec77a2c47` | `4a5d21a5bf7b50be9180f170cb753c2d2afe6cbd` | `f8867dfdc76f3626e32efdd3dae034c6ceee67d8` | `4484ff1986b59beb0b53e67a1e9891bc4bc78251` |

The introduction `6f8a3d7937811f0b5e6e6a9ec062728672bee507` also changes `docs/seo/2026-07-14-measurement-seo-completion-matrix.md` from `021341c376bfcf7090def6ff9ef6ea6c599a6626` to `3455f1d77fcc435d3d3ba39d16cecd7ac3583161`. That complete source body is already retained in [the historical matrix](./2026-07-14-measurement-seo-completion-matrix.md), current archive Git blob `9ac12ffa4c1e9faa19fd255dc56d103eaf0bae4f`. This document completes its existing relative readback link; it does not reaccept the matrix's other source history.

## Final-source supersessions

The final source contains the original sequence from GTM versions 6 to 7 to 8, registered definitions replacing planned definitions, observed recrawl replacing pending recrawl, and the later release account replacing preliminary release wording. Earlier values are not asserted as simultaneous final state.

Intervening mixed-owner source `4a5d21a5bf7b50be9180f170cb753c2d2afe6cbd`, parent `6e74329a7c670ddcc8785f2cc12351ec92eaf9c7`, changes this file from `6695e6cf69460e0238570d108a37fac2b617b965` to `f8867dfdc76f3626e32efdd3dae034c6ceee67d8` before the final listed documentation update. Its quotation-decision examples and final platform state remain historical context only. This archive claims no additional migration credit for that mixed-owner commit, current event behavior, platform changes or deployment.

## Privacy omissions

Exactly two identifier spans in the historical “Billing and deployment boundary” paragraph are omitted. The original values are not reproduced here or in the regression sources. Offsets are zero-based UTF-8 byte offsets in original body blob `4484ff1986b59beb0b53e67a1e9891bc4bc78251`, before substitution.

| Omission | Source byte offset | Source byte length | Replacement | Reason |
| --- | ---: | ---: | --- | --- |
| billing-resource-identifier | 11036 | 36 | `[OMITTED: historical billing resource identifier]` | Private financial resource identifier is unnecessary for historical source custody. |
| ambiguous-financial-reference | 11095 | 19 | `[OMITTED: ambiguous billing/customer/card reference]` | Source explicitly describes an ambiguous billing/customer/card reference; preserve the rejection meaning without that value. |

No screenshots, customer-level records, raw query/event rows, credentials, tokens, private keys or private account exports are imported. Retained numerical tables are aggregate event counts or public-site URL inspection observations. The operator email is a historical business principal, not a customer identity or a credential. Provider resource IDs and OAuth scope names in the quoted body confer no access. Linked historical material is not imported or accepted by this archive.

## Privacy-filtered historical source body

# MALIEV live measurement readback

Readback date: 2026-07-26 (Asia/Bangkok)

This note supersedes the live-measurement claims in the 2026-07-14 matrix where the external systems have since changed. It records what is directly verified, what is source-backed, and what still requires a downstream business contract.

## Application event contract

The Web application emits privacy-safe, scalar data-layer events. Labels translated for the visitor are not used as analytics identifiers.

### Finder funnel

`/services` emits the following events as the visitor progresses through the finder:

- `service_finder_started` — once on the first meaningful finder interaction.
- `service_finder_step_completed` — `step_key`, `answer_id`, and numeric `step_number`.
- `service_finder_completed` — comma-separated `recommended_service_ids` and `>`-separated `finder_path`.
- `service_finder_recommendation_clicked` — stable `service_id` and the same scalar `finder_path`.
- `service_finder_step_skipped` and `service_finder_results_viewed` are also emitted for diagnostic coverage.

Finder answers and the validated recommendation path are carried into the manual quotation flow and persisted through the existing nullable attribution contract. The reserved metadata envelope is versioned and preserved when the operator-facing quotation notes are edited; it is not used as an opaque replacement for operator notes.

### Quote, upload, material, and contact diagnostics

The instant quotation flow emits `quote_started`, `quote_submit_attempt`, `quote_submission_error`, `review_reached`, `file_upload_start`, `file_upload_complete`, `upload_failure`, and `estimate_shown`. The material comparison emits `material_detail_viewed`. Contact-channel events use `maliev_contact_click` with scalar `channel`, `destination`, `contact_destination`, `placement`, `locale`, and optional stable `service_id`, `intent`, and `finder_path` fields.

The sole persisted-lead emitter remains `_GoogleTagManagerPartial`. `maliev_lead_submitted` is emitted only after the quotation/contact record is saved and includes the allowlisted stable fields `transaction_id`, `lead_type`, `lead_status`, `service`, `intent`, and `finder_path`. No name, email, phone, message, file name, or other PII is sent to the data layer.

### Customer quotation decision

The member quotation view now queues `maliev_quote_decision` only after the accepted or declined quotation PUT succeeds. The event is rendered once through `_GoogleTagManagerPartial` after the redirect and is removed from TempData when consumed:

```json
{
  "event": "maliev_quote_decision",
  "transaction_id": "quotation-{positive quotation id}",
  "decision": "accepted|declined",
  "source": "customer_portal"
}
```

`decision` and `transaction_id` are allowlisted scalar values; no customer identity, notes, invoice content, or payment data is emitted. The event is diagnostic only and is not a GA4 key event or Google Ads conversion. The quotation decision remains a customer-portal milestone, not proof of payment or revenue.

## GTM live state

Directly verified in the authenticated GTM UI:

- Container: `GTM-KHDDLVRR` (account `4651223587`, container `258194166`).
- **Version 8 is live**, published 2026-07-26 by `natthapol.vanasrivilai@maliev.com` after the custom ADC client was re-authorized with GTM container-version management scope.
- The refreshed `maliev-google-ads-local-adc` token was read back with `cloud-platform`, `analytics.edit`, `analytics.readonly`, `tagmanager.edit.containers`, `tagmanager.edit.containerversions`, `tagmanager.publish`, and `webmasters` scopes; no developer token or OAuth secret is stored in the repository.
- Live totals: 12 tags, 8 triggers, 28 variables.
- Diagnostic trigger: `CE - diagnostic_quote_funnel`, matching the non-lead diagnostic events `quote_started|quote_submission_error|quote_submit_attempt|review_reached|file_upload_start|file_upload_complete|upload_failure|estimate_shown|material_detail_viewed|service_finder_step_skipped|service_finder_results_viewed|maliev_quote_decision`.
- Diagnostic tag: `GA4 - diagnostic quote funnel`, sending the event name from `{{Event}}` to `G-YYYMMW7P1Z` and mapping the allowlisted scalar fields (`service_id`, `intent`, `locale`, upload/material fields, contact fields, finder fields, lead fields, `platform`, `transaction_id`, and `decision`).
- `GA4 - contact click` now maps the complete allowlisted scalar contact contract: `channel`, `destination`, `context`, `platform`, `contact_destination`, `placement`, `locale`, `service_id`, `intent`, and `finder_path`.
- Existing persisted-lead, contact, review, finder, Google tag, and Conversion Linker tags remain in place. No Ads campaign, budget, bid, or conversion-action write was made in this slice.

The source and the live container intentionally keep persisted lead conversion separate from diagnostic clicks and funnel steps.

## GA4 state

- Property: `291185106`.
- Web stream: `G-YYYMMW7P1Z`.
- `generate_lead` is configured as a key event.
- The Ads link is `6744219291`.
- Existing custom definitions cover `channel`, `destination`, `context`, `has_files`, `intent`, `service`, `lead_status`, `lead_type`, `recommended_service_ids`, `platform`, `service_id`, `answer_id`, `finder_path`, and `step_key`.
- The live GTM tags now send the additional scalar diagnostic and contact parameters. GA4 Admin now contains 25 event-scoped custom dimensions, including the newly registered `contact_destination`, `placement`, `locale`, `failure_category`, `material_id`, `process`, `file_type`, `source`, `file_upload_completed`, `material`, and `decision`. Numeric event-scoped custom metrics `file_count` and `step_number` are also registered. GA4 does not retroactively populate a dimension or metric for events received before its registration.
- Existing Explore work includes `MALIEV event and service report`, `MALIEV lead funnel`, a finder-to-lead funnel, a path exploration, and user-behaviour views. DebugView/Tag Assistant should be used for a fresh browser receipt check after consent; this documentation does not claim a new DebugView session.

### Analytics UI verification (2026-07-26)

The authenticated Analytics UI was checked for property `291185106` after the ADC reauthorization:

- The saved `MALIEV event and service report` opens as a free-form exploration with event name rows, device-category columns, and Active users/Event count metrics. It includes the finder and lead events alongside normal page and session events.
- The saved `MALIEV lead funnel` opens as a funnel exploration with the ordered steps `Finder started` → `Finder completed` → `Quote started` → `Persisted lead`, with device-category breakdowns.
- The saved `Funnel` exploration is present in Recently accessed and remains available for the broader service-finder analysis.
- GA4 DebugView is accessible, but it currently reports **0 development devices** and “Waiting for debug events.” A production contact click was exercised separately, but the browser session did not expose a debug device or page data layer, so no parameter-level DebugView receipt is claimed here.

## Google Ads state

- Conversion action `7682972324` (`Website - Persisted lead`) is enabled, primary, and included in conversions.
- The imported GA4 conversion action remains hidden/excluded to prevent duplicate bidding conversions.
- The last authoritative readback recorded one counted persisted-lead conversion for PMax on 2026-07-23.
- Search-term hygiene and campaign-scoped negative keywords remain owned by the Ads task. No campaign structure, budget, bid, or goal writes were made here.

Ads currently optimizes toward a persisted submission. There is no verified CRM/order boundary for `qualified_lead`, quote accepted, order confirmed, payment received, or revenue, so those stages cannot be represented honestly or imported as offline conversions yet.

## GA4 receipt readback

The GA4 Data API read back the following events for the last 28 days, proving that the live property is receiving the core funnel events (this is aggregate event evidence, not a claim that every event has an Ads conversion):

| Event | Count |
|---|---:|
| `service_finder_step_completed` | 180 |
| `service_finder_started` | 29 |
| `service_finder_completed` | 22 |
| `service_finder_recommendation_clicked` | 3 |
| `maliev_contact_click` | 5 |
| `generate_lead` | 3 |

The diagnostic event tag and the custom definitions are now both present. A fresh consent-aware DebugView replay is still useful for validating individual parameter values, but the property-level receipt is confirmed.

The parameter-scoped readback also confirms that the historical `maliev_contact_click` rows contain the older `channel`/`destination` values. A new contact click was not observable through the browser verification session because that session did not expose the page data layer after navigation; therefore this release does not claim a fresh DebugView parameter receipt. The next consented contact click should be checked in DebugView/Realtime to confirm the newly mapped scalar fields.

## Search Console and SEO recrawl

The authenticated Search Console API was re-read on 2026-07-26. The canonical sitemap `https://www.maliev.com/sitemap` was downloaded at `2026-07-25T22:37:21Z`, is not pending, and reports 0 warnings and 0 errors (25 submitted URLs).

URL Inspection now shows the canonical migration has been processed for two owner pages:

| URL | Google state | Last crawl | Google-selected canonical |
|---|---|---|---|
| `/services/3d-printing` | Submitted and indexed | `2026-07-25T12:47:23Z` | `/services/3d-printing` |
| `/services/cnc-machining` | Submitted and indexed | `2026-07-25T20:15:31Z` | `/services/cnc-machining` |
| `/services/3d-scanning` | Crawled - currently not indexed | `2026-03-04T10:41:39Z` | Not returned |
| `/services/custom-manufacturing` | Discovered - currently not indexed | Not returned | Not returned |

The 3D-printing and CNC canonical results are direct evidence that Google has recrawled and consolidated those URLs; the two remaining rows are Google-controlled indexing states, not application HTTP failures. Search Analytics for the comparable final window `2026-06-28..2026-07-25` returned 377 query/page rows, 23 clicks, and 2,640 impressions. The new canonical 3D-printing URL had no rows in that window, while the CNC owner had 368 impressions and 0 clicks (weighted average position 23.17), so the next comparison must use a later complete window.

Previously accepted recrawl/indexing requests remain asynchronous. A request does not force an immediate crawl or canonical replacement, and the site cannot force Google to index a page. Recheck the two not-indexed owners after Google processes the current sitemap and page responses; do not repeatedly submit unchanged URLs.

## Billing and deployment boundary

The GKE deployment project `maliev-website` is already billing-enabled and is linked to the Cloud Billing resource `[OMITTED: historical billing resource identifier]`. The supplied value `[OMITTED: ambiguous billing/customer/card reference]` was rejected by `gcloud billing projects link` as an invalid Cloud Billing account resource ID, so no billing link was changed. It is likely a billing profile/customer/card reference rather than the resource ID accepted by the Cloud Billing API. GA4 reporting itself does not require GCP billing; GKE, Artifact Registry, and related deployment/API usage do.

## Validation and release record

- Source release commit: `4a5d21a` (`Add quotation decision measurement`).
- The source release and the GTM/GA4 mapping are independently readable: the application commit is on `main`, while the external container is live at version 8.
- Focused Web tests: **18 passed, 0 failed, 0 skipped** (`dotnet test .\\Maliev.Web.Tests\\Maliev.Web.Tests.csproj -c Release --no-restore --nologo --verbosity minimal --filter "FullyQualifiedName~Maliev.Web.Tests.MeasurementTrackingSourceTests"`).
- Full Web tests: **240 passed, 0 failed, 0 skipped** (`dotnet test .\\Maliev.Web.Tests\\Maliev.Web.Tests.csproj -c Release --no-restore --nologo --verbosity minimal`).
- Release build: **0 warnings, 0 errors** (`dotnet build .\\Maliev.Web\\Maliev.Web.csproj -c Release --no-restore --nologo`).
- Production deployment: **completed** with image `v2026.07.26.1250` (digest `sha256:7a8f51d6c6bde32419914e719d1873a4d9b7bd58f2aec5b9cfff8f94566ef707`); `kubectl -n maliev rollout status deployment/maliev-web` reported a successful rollout, and the deployment readback reached 3/3 ready pods (revision 564).
- Production HTTP readback: `/services`, `/services/3d-printing`, and `/contact` each returned `200`; each contained `GTM-KHDDLVRR`, cache-busted assets, and no legacy `GTM-5VBH5LK`, Universal Analytics `UA-*`, or `google-analytics.com/analytics.js` reference.
