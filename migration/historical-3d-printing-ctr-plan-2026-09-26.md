# Historical 3D-printing CTR and funnel plan — 2026-09-26

Original `maliev-web` commit
[`a73acf2e4de9a611c7eda22cf6dbdae333d231cf`](https://github.com/MALIEV-Co-Ltd/maliev-web/commit/a73acf2e4de9a611c7eda22cf6dbdae333d231cf)
added `docs/superpowers/plans/2026-09-26-3d-printing-ctr-funnel.md`.
This record preserves its migration-relevant decisions without treating the
source's agent checklist or absolute source paths as instructions to execute.

The plan separates click-through rate (clicks divided by impressions),
route-choice intent, and completed quotation leads. A
3D-printing quote CTA should identify a stable service, route, placement, and
locale with scalar-only telemetry. Repeated clicks may be counted as intent;
they must not emit `maliev_lead_submitted` or `generate_lead`. Those lead
events remain contingent on a persisted quotation. The existing instant-quote
`journey_id` is retained. No contact details, file names, query strings,
tokens, or row-level business data belong in diagnostic events.

The employee qualification readback is a separate fixed-path, session-bound,
no-store bridge. It must validate linked outcome identity, allowed fields and
states, ordering, uniqueness, and time window, and must suppress raw upstream
errors and credentials. The source plan also deferred any public metadata
decision until the complete post-2026-09-18 28-day Search Console window plus
lag matured, approximately 2026-10-19/20; it
did not authorize publication, GTM/GA4 changes, Ads changes, indexing
submissions, or application deployment.

Implementation ownership is tracked separately by
[Web #322](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Web/issues/322),
[Web #323](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Web/issues/323),
[QuotationService #52](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.QuotationService/issues/52),
and [Intranet #177](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Intranet/issues/177).
This historical record is not independent evidence that those runtime
changes, SEO measurement, or authenticated Aspire acceptance are complete.
