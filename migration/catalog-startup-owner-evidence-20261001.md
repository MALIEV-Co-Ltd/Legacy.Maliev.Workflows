# Catalog startup reconciliation owner evidence

Live source main remains `bed10c7d15e0698e0b75f1329d0f312937f5d77f`.
All 1,098 reachable commits, including merges, are already inventoried. This
bundle adds independently verified runtime evidence to three existing Catalog
owner records; it introduces no new source SHA or fully resolved source commit.

| Source SHA | Catalog disposition |
| --- | --- |
| `1c611bb96d3a077090a8c65587cb7c4270af0aa4` | Partial: reviewed catalog and guarded PostgreSQL startup reconciliation. |
| `7b4703576cf183abc09cf558148b5c8afb97d20c` | Partial: PA612-ESD/ABS-ESD definitions and relationships, preserving historical PC-ESD. |
| `bed10c7d15e0698e0b75f1329d0f312937f5d77f` | Partial: independently retain the merge owner and its first-parent path inventory. |

Implementation is [Catalog PR #30](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.CatalogService/pull/30),
merged at `a961b28f959c5814d7c2ff97c246c61843a88616`. Canonical Catalog main
equals live origin/main; [exact-main validation](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.CatalogService/actions/runs/36719487180)
and [publication gate](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.CatalogService/actions/runs/36719486203)
are successful. [Catalog #29](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.CatalogService/issues/29)
remains open for coordinated activation and wider acceptance.

Independent daily verification on October 1: Release build with warnings as
errors passed with zero warnings/errors; focused actual startup suite passed
22/22; affected suite passed 136/136, both zero skips. Whole-solution
`dotnet format --verify-no-changes --no-restore` passed, and the transitive
vulnerability scan found no vulnerable packages across the five Catalog projects.
Tests use actual Production-host HTTP/authentication and disposable PostgreSQL
and Redis. They cover source literals/relationships, existing IDs/commercial
fields, default-off startup, concurrent reconciliation, rerun, rollback,
cancellation/60-second timeout, and strict Redis invalidation failure/recovery.

Source definitions and startup/reconciler contracts were read from committed
Git objects only. The original source checkout and refs were not modified.
No new Catalog implementation was necessary: the already merged implementation
was inspected and executed, rather than inferred from a documentation mapping.

Activation remains disabled by default. These disposable tests do not prove
production-derived Aspire data parity, coordinated cache/drain activation,
historical Order/Quotation acceptance, or the complete source consumer chain.
The Web and Workflows owner records, prior provenance, and global resolved
count are preserved. No persistent data write, application deployment, traffic
change, schema DDL or cutover accompanies this evidence bundle.
