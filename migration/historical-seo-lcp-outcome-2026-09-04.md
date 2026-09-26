# Historical SEO, LCP, and outcome-readback decision

This is a migration record for original `maliev-web` commit
[`7851975ee1da8fd4aaea23b6f17a5db56206f4d6`](https://github.com/MALIEV-Co-Ltd/maliev-web/commit/7851975ee1da8fd4aaea23b6f17a5db56206f4d6),
specifically its `docs/seo/2026-09-04-organic-lcp-and-outcome-readback.md`.
The figures and observations below are the source report's **September 2026
historical evidence**, not a current Search Console, CrUX, or production
verification result.

The source report compared 26 August–1 September with 19–25 August 2026:
43 versus 77 Search Console clicks, 2,813 versus 2,520 impressions, 1.53%
versus 3.06% CTR, and average position 14.48 versus 11.18. It did not
attribute the weekly click decline to one defect or claim that LCP caused it.
Its 2 September mobile Core Web Vitals view identified 25 URLs needing
improvement across the main site and Shopify; that field window preceded the
3 September release. It also recorded an authenticated employee browser
navigation to `/Analytics/OutcomeReadback` blocked by a client-side URL
filter, without concluding that employee authentication was missing.

The original decision had three independently scoped changes:

1. Add a 768-pixel responsive WebP hero candidate to eight service pages.
2. Describe custom manufacturing as the multi-process or process-unknown
   intake, distinct from dedicated CNC and 3D-printing pages.
3. Preserve the authenticated `/Analytics/OutcomeReadback` route while making
   `/Operations/OutcomeReadback` available for clients that filter the former.

Legacy Web carries the first two behaviors through [PR #186](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Web/pull/186)
at `1d58887f44c5d0300bb1c24d05d89c4a68f74bfa`; its exact-main
[CI run 33965144094](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Web/actions/runs/33965144094)
passed. Legacy Intranet carries the third behavior through
[PR #188](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Intranet/pull/188)
at `f1061bb445b164d5ad968892d1c59db65a6312fa`; its exact-main
[CI run 36275244002](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Intranet/actions/runs/36275244002)
passed. Both Legacy BFF routes use the same employee-authorized handler;
the Workflows [receipt guide](../tools/analytics/README.md) describes
collection without implying that the offline validator makes HTTP calls.

The source report left post-deployment field validation and an authorized
production receipt collection pending. Neither the old metrics nor these
code/CI checks prove current SEO recovery, current production behavior, or
production-derived database parity. Application deployment and data refresh
remain separate, guarded work.
