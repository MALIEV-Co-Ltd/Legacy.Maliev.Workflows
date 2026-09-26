# Historical qualified-outcomes implementation plan

This records the Workflows-owned plan in original `maliev-web` commit
[`d852d3ef0ea45bba51bb29de557784b5e5fffae6`](https://github.com/MALIEV-Co-Ltd/maliev-web/commit/d852d3ef0ea45bba51bb29de557784b5e5fffae6):
`docs/superpowers/plans/2026-09-24-qualified-outcomes-and-measurement-runtime.md`.
It is a dated source decision record, not a current execution checklist. Its
ASP.NET Core 8 paths and commands must not be run against the .NET 10 Legacy
repositories.

The plan divided qualified-outcome measurement into three boundaries:

1. An employee-only QuotationRequestService readback over a complete,
   increasing UTC window of at most 31 days. The receipt contains only current
   request identity, creation time, paired transaction/journey identifiers,
   and current qualification state. It excludes customer PII, employee audit
   history, actor/reason, and campaign or revenue inference. Invalid or
   future windows fail rather than return a partial receipt.
2. An offline scorecard that accepts only the exact receipt wire shape,
   rejects missing, stale, malformed, duplicate, or inconsistent data, and
   keeps unavailable technical conversion and qualified-customer claims
   unavailable rather than converting them to zero.
3. A browser consent proof that prevents rejected, repeated, or diagnostic
   interactions from being counted as a persisted lead and blocks external
   Google requests during tests. The plan did not authorize production
   deployment, Ads claims, or access to production customer records.

The first boundary was migrated into PostgreSQL-only
`Legacy.Maliev.QuotationService` via [issue #52](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.QuotationService/issues/52)
and [PR #53](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.QuotationService/pull/53)
at `c37e9d7c1aefc7ac44b1338197aa6c4f9d5090db`; exact-main
[CI run 36220124573](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.QuotationService/actions/runs/36220124573)
passed. The [outcome receipt guide](../tools/analytics/README.md) documents
the present offline validator and explicit unavailable states. The later
source scorecard commit
[`8e133abe65078c6a0bbca1d43473c6546ed6284f`](https://github.com/MALIEV-Co-Ltd/maliev-web/commit/8e133abe65078c6a0bbca1d43473c6546ed6284f)
made paired transaction/journey emission and production-serializer fixtures
explicit. Its Workflows validator, fixtures, CLI tests, and guide are covered
by [issue #59](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Workflows/issues/59)
and [PR #60](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Workflows/pull/60)
at `33c63bb068e6678fb755e55e13b040bde9200173`; exact-main
[CI run 36224534263](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Workflows/actions/runs/36224534263)
passed. Browser consent commits require their own source-ledger dispositions;
they are not resolved by association. Passing code CI does not prove a live,
authorized receipt was collected or that production-derived database parity
is current.
