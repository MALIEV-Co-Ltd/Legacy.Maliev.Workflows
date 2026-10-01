# Historical Search Console baseline — 2026-07-14

This is migrated historical evidence, not a current Google measurement or an
instruction to deploy, publish, request indexing, change advertising, or access
Google accounts. The source capture reported authenticated access; this migration
does not independently repeat that capture.

Source: [`dd9de3053cffd082df603950e8e3be3669d89ccb`](https://github.com/MALIEV-Co-Ltd/maliev-web/commit/dd9de3053cffd082df603950e8e3be3669d89ccb),
`docs/seo/2026-07-14-search-console-baseline.md`. Capture date: July 14, 2026,
Asia/Bangkok. Property: `sc-domain:maliev.com`. Performance window: April 12
through July 11, 2026. Indexing report last updated June 30, 2026. The filtered
performance report described an update approximately 4.5 hours before capture.

## Recorded domain and query evidence

| Domain metric | Historical value |
|---|---:|
| Web clicks | 395 |
| Impressions | 16,656 |
| CTR | 2.4% |
| Average position | 12.8 |
| Indexed pages | 119 |
| Not-indexed pages | 107 |

The source's `รับ` query filter contained 56 variants: 4 clicks, approximately
1,400 impressions, 0.3% CTR, and average position 30.3. This is not the same
population as the reporter's four mutually exclusive service cohorts.

| Query | Clicks | Impressions | CTR | Average position |
|---|---:|---:|---:|---:|
| ปริ้น 3d | 2 | 131 | 1.5% | 7.1 |
| ปริ้น3d | 2 | 73 | 2.7% | 6.1 |
| รับปริ้น 3d | 0 | 141 | 0% | 23.5 |
| รับพิมพ์ 3d | 0 | 128 | 0% | 30.7 |
| รับพิมพ์ 3 มิติ | 0 | 100 | 0% | 31.0 |
| งาน cnc | 1 | 38 | 2.6% | 10.3 |
| รับ cnc | 1 | 7 | 14.3% | 11.4 |
| รับงาน cnc | 0 | 2 | 0% | 46.5 |
| รับ สแกน ชิ้น งาน 3 มิติ | 0 | 57 | 0% | 19.7 |
| สแกน 3d | 0 | 25 | 0% | 10.2 |
| รับสแกน 3d | 0 | 1 | 0% | 20.0 |
| รับผลิตชิ้นงานตามแบบ | 0 | 126 | 0% | 44.0 |
| ผลิตชิ้นงานตามแบบ | 0 | 15 | 0% | 48.9 |

For `รับพิมพ์ 3d`, the source attributed 127 of 128 impressions to
`https://www.maliev.com/3d-printing`. Its diagnosis was weak relevance, evidence,
authority and indexed production copy, not cannibalization for that exact query.

| Page | Clicks | Impressions | CTR | Average position |
|---|---:|---:|---:|---:|
| https://www.maliev.com/3d-printing | 68 | 4,096 | 1.7% | 15.1 |
| https://www.maliev.com/cnc-machining | 30 | 1,277 | 2.3% | 24.9 |
| https://www.maliev.com/3d-scanning | 7 | 449 | 1.6% | 12.4 |
| https://www.maliev.com/quotation | 2 | 180 | 1.1% | 2.2 |
| https://www.maliev.com/ | 91 | 1,453 | 6.3% | 4.4 |
| https://shop.maliev.com/th/products/เครื่องฉีดพลาสติกขนาดเล็ก | 52 | 2,870 | 1.8% | 7.4 |

## Recorded indexing and experience evidence

| Exclusion | Pages |
|---|---:|
| Crawled, currently not indexed | 81 |
| Blocked by robots.txt | 8 |
| Not found (404) | 7 |
| Duplicate, Google chose different canonical | 4 |
| Alternate page with proper canonical | 3 |
| Excluded by noindex | 2 |
| Discovered, currently not indexed | 2 |

The 81-page cohort included seasonal products, spare components, localized
duplicates, `/collections/all` and an Atom feed. The source called for deliberate
strategic review, not forcing all URLs into the index or mass submission.

| Report | Historical values |
|---|---|
| Mobile Core Web Vitals | 0 good, 13 need improvement, 16 poor |
| Desktop Core Web Vitals | 13 good, 0 need improvement, 0 poor |
| HTTPS | 29 HTTPS, 0 non-HTTPS |
| Product snippets | 14 valid, 0 invalid |
| Merchant listings | 69 valid, 0 invalid |
| Google Business Profile | 5 reviews; source reported no added photos for 2,484 days |

## Preserved decisions and current migration boundaries

The historical priority was printing (largest service demand), scanning (nearest
page-one opportunity), then CNC relevance/proof, with a custom-manufacturing
canonical owner. Preserve one owner per transactional intent. Truthful obsolete
URL handling may restore, redirect only to an equivalent page, or retain 404/410.
Canonical, localization, sitemap, rendered HTML and mobile field evidence require
verification after an independently authorized release, before any recrawl.

Historical weekly signals were canonical localized priority URLs returning 200,
correct query/page ownership, complete-week impressions then position/CTR,
printing queries moving toward top 10, scanning/CNC sustaining top 10, and custom
manufacturing earning impressions. These are not ranking guarantees. Aggregate
position is not a personalized search result; Search Console has no guaranteed
separate AI Overview or AI Mode citation metric. Structured-product eligibility
does not prove service relevance or mobile quality.

LINE, Messenger, Facebook and Instagram remain distinct diagnostic channels;
their clicks are not primary Ads conversions. Qualified persisted leads remain
the outcome. Facility photos/reviews must be real and policy compliant.

The offline reporter is migrated separately in
[Web PR #430](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Web/pull/430).
From a Legacy Web checkout, run `pwsh -NoProfile -File
./tests/SummarizeSearchConsole.ps1 -InputPath <queries-export.csv> -OutputPath
<cohort-report.json>` against an independently obtained complete-window export.
It requires English `Top queries`, `Clicks`, `Impressions`, `CTR`, `Position`
columns, calculates impression-weighted positions, keeps unmatched rows, and
does not infer qualified leads. Its fixture is not a new authenticated export.

The historical `cnc` cohort is measurement only; separately excluded CNC expansion
work is not included. This record proves neither current SEO outcomes, production
data parity, application release, authenticated Aspire acceptance, nor completion
of other Web/Workflows source owners.
