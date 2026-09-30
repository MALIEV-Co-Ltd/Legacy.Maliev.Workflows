# SEO/search ownership evidence bundle

Parent tracking: Workflows #234. This batch resolves five individually tracked
source commits against real runtime/test ancestors, not the docs-only manifest.

| Source SHA | Target implementation SHA | Preserved behavior |
| --- | --- | --- |
| 25db5545b0f5f575f61616af2ba54ee45e656a20 | b363dd6a416cff2bd361937bfbc56202f868dc69 | Custom manufacturing owns process-unknown searches; specialist service pages link to it; localized metadata/schema. |
| bf4c550cb28fd0432d9c178a7072d07d61e43e13 | 41e4e0ff330148b3e06081417c7d87b088b04e8a | SEO verifier excludes ordinary script templates from document metadata/heading counts, retaining JSON-LD. |
| d173d0bbc9c77958e2fd49f50cdb1d25531e33f6 | 6a4c8d1cf2fb08800c32dc392affdfabda0fcc64 | Nationwide printing title, without Bangkok/Nonthaburi service-boundary narrowing. |
| 30a22afb243306726b820cbd0eaee0977600e331 | 6d566d24be3eb19531b04da3fb222cb7471a2d2b | Unknown/multiprocess ownership, procurement inputs and quotation-output expectations in Thai/English. |
| 7b1a8fd28c54f465c0ac966b3cf132ec49680bf7 | 02721f7e5504acd2f3cb09f7b2a5ba4cbe265dca | Localized finishing Service/FAQ schema and recursive Service discovery/rejection tests. |

All five implementations belong to [Web PR #179](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Web/pull/179),
merged at `895b8662af69edda7b88abcf112d15e90c3ee9be`.
Exact-merge [CI Main](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Web/actions/runs/33284307077)
passed its deterministic asset and .NET validation jobs. The merge remains an
ancestor of protected Web main. Historical validation reported Release zero
warnings/errors, 1,458 Web tests and 109 browser-module tests; these historical
counts are not claims of new local executions.

Current acceptance owners include CustomManufacturingStaticSsrRouteTests,
CustomManufacturingParityTests, SeoBusinessContractParityTests,
PublicServiceStructuredDataMigrationTests and ProductionSeoVerifier.Tests.ps1.
Later marketing copy supersedes some historical titles/search text; the preserved
contract is ownership and nationwide semantics, not byte-identical old strings.

This does not prove live Google indexing, deployment or physical quotation
pricing. In particular, source 499b6eb0841829ca7c91b7e1e6b756dbbd7530cc and
505c67cfda7ebfe79b5ceed9d3d0d9a114232821 remain incomplete under Web #300.
The preliminary-logo repair belongs to its own cohort and is not included here.
