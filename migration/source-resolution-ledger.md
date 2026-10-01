# Source-commit resolution ledger (#56)

### October 1 verified Search Console bundle

Source `dd9de3053cffd082df603950e8e3be3669d89ccb` now has complete evidence
for both owners: Web PR430/main `6d0dc9f7095b4128becbf25af5f4de2b22ed7731`
with exact-main run36809860319, and Workflows PR257/main
`7752b418ff5c93fdd51a8a1a251f61dfb5bd9a41` with exact-main run36810479590.
Both are green. The reporter/fixture preserve source blobs; actual ten offline
cases pass from main. Historical query/page measurements are retained and all19
numeric tuples were independently compared against the committed source.
This does not prove present-time Google performance, authorize release/indexing,
or include separately excluded CNC expansion. Other SEO source owners stay open.

The complete inventory remains 1,098 source commits; this one two-owner bundle
advances fully resolved entries to 159 and leaves 939 unresolved/partial.
`complete=false` remains mandatory. Current target-main references are refreshed
without changing any of the 1,098 ownership records. Historical counts below
describe their earlier checkpoints, not the current total.

Independent ledger validation: Release build zero warnings/errors; focused
58 and full 135 tests passed with zero skips; formatting, both package audits,
credential scan and whitespace checks passed. Both reviewed generators checked
live source main before/after inventory. All source ownership records and every
other resolution record remain byte-semantically unchanged. This ledger bundle
still requires its own protected-main PR and exact-main CI acceptance.

`source-page-acceptance.json` separately inventories all 79 Razor Pages with a
first-line `@page` directive at source `bed10c7d15e0698e0b75f1329d0f312937f5d77f`
(35 Web, 44 Intranet). Pages remain `unverified` except the two owner-approved
Travelers retirements. A source-file mapping, an existing Legacy route, and a
passing unit suite do not prove
authenticated workflow, responsive, localization, or persisted-data parity.
The owner approved retirement of the obsolete Travelers feature in Intranet
issue #211. The two source pages (`/Travelers` and `/Travelers/Create`) are
recorded as retired in the acceptance inventory; authenticated direct GETs to
those paths and the historical target `/Travelers/Index` return 410 Gone.
`scripts/Test-SourcePageAcceptance.ps1` compares both source page-tree Git IDs
and the exact path set to live source `origin/main` without modifying it. This
is a source-page census for issue #98, not the complete route, API, role, or
feature acceptance matrix; those remain pending.

`source-commit-ledger.json` inventories every source commit reachable from the
observed `maliev-web` main, including merges. Merge paths are the first-parent
tree delta, so merge-time conflict resolutions are not silently omitted. Path
ownership and a proposed retirement classification are **not** proof that a
change is migrated, validated, or approved for retirement.

September 30 ESD wave advances the complete source inventory from 1,096 to
1,098 commits. Source `7b4703576cf183abc09cf558148b5c8afb97d20c` and merge
`bed10c7d15e0698e0b75f1329d0f312937f5d77f` retain separate pending records;
their Catalog, Web and Workflows owners link shared issues #29, #418 and #234,
respectively. The merged tree delta includes automatic PA612-ESD/ABS-ESD
pricing, profiles, generated assets, material descriptions and producer
reconciliation, not CNC expansion. Existing PC-ESD keys/relationships must
remain intact. Source objects were acquired only in an isolated bare cache;
the original checkout and refs were not fetched, edited or executed.
The page-tree checkpoint is refreshed without changing any route/acceptance
status. The prior 1,096 resolution records and evidence remain unchanged:
157 resolved, with 941 pending/partial after the two new commits. This is
inventory and tracking evidence, not migrated ESD behavior or release approval.

### Verified ESD Web owner checkpoint

Both full source SHAs retain separate records. Their Web owner now records
**partial**, not migrated: Web PR #420 merged at
`4483e3eb768e8ee59a4a2cf6ba9e2f452e0f3ed0`, and exact-main validation
[`36735708564`](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Web/actions/runs/36735708564)
passed. Canonical Web main equals live origin/main. The bounded catalog/profile
slice passed independent Release builds with zero warnings/errors, focused191,
full2481, four browser cases, JS157, asset/static/security checks. Publication
remained disabled. Web #418 remains open for coordinated activation and wider
acceptance; Catalog #29 and Workflows #234 remain pending. The global total is
still **157 resolved / 941 unresolved / 1,098 source commits**. Grouped work and
a green Web PR do not resolve the other owners or the merge as a whole.

Separate already-tracked follow-on work is Web #275's commercial-policy bundle,
Quotation #70's employee actor/live authority chain and Auth #113's newly
reproduced normal-DI PostgreSQL refresh retry/family-concurrency prerequisite.
Intranet PR #236 is under exact-head CI and is not main acceptance yet. Data
execution remains owned by the dedicated migration chat; none of these code
checkpoints authorizes deployment, data refresh, schema application or cutover.

Workflows #193 corrects the source owner map: `Maliev.MessageService.*` belongs
to ContactService, while `Maliev.EmailService.*` remains NotificationService.
At the pinned source checkpoint this covers 25 commits and 104 Message paths;
103 path classifications change (the `f0640fe` Startup path was already
Contact-owned). Twenty-four commits receive an independent
`messageOwnerTransition` review record. Three Message-only commits lose a
pending Notification owner; mixed Email/Message commits retain Notification
and all existing migration evidence. Earlier `ownerSetTransition` records are
preserved separately. New Contact owner entries remain pending unless already
independently evidenced; this mapping correction is not migration acceptance.

`source-commit-resolutions.json` gives every full source SHA an independent
resolution. Each owning Legacy repository starts `pending`. A candidate
retirement also starts `pending`, even where the path rule says
`approved-retirement` or `source-tooling-only`; the path-rule explanation is not
an owner approval. The generated `complete` flag remains false until every
owner is independently resolved. Runtime migration requires issue, merged PR,
protected-main ancestor SHA, and validation URLs; candidate retirement needs
an explicit reason and approval URL. Mixed commits cannot be complete until
all owner and retirement decisions are proven. An exact formatting-only no-op
has a separate disposition and is never labeled runtime migration.

## September 30 Country and authenticated-profile bundles

The shared additive pricing issue Web #275 also tracks eight previously
unlinked, still-pending Web source entries independently:
`e5432817078e133604239ebfe2b806465ed8e436`,
`a8c358f338e6d6853517d1c546061c338f5895f8`,
`5320f8ea6cf9ffdeb1c3f2bf51c75b3511f525a1`,
`a3c5c4a53907e03ac202620cc051393c20fc28e3`,
`f0ae0e8f4f71231d5a4cbb9adebbb107323519e2`,
`499b6eb0841829ca7c91b7e1e6b756dbbd7530cc`,
`2712f7d05d982ba7a3a2e4905c3ff61073d0f13a`, and
`faf702a7f7990aaca6b60c652bae64fbc62987f3`.
The last entry also links to Web #309 for STEP/active-upload physical-pricing
acceptance. The source trees were inspected read-only, and the existing issues
are reused rather than creating duplicate commit tickets. These are tracking
links, not migration, test, or source-behavior acceptance evidence. All eight
statuses, target SHAs and validation lists remain pending/empty; the overall
resolved count stays 157/1,096. CNC expansion remains outside this bundle.

Country issue #30 / PR #31 resolves only the Country owner of
`03eaff1194c3ae2a54ceefeae31deffaff90436f`,
`9e51e6c5da29de8e617b65b59d46882cde6d3b64`, and
`03dc9a1271c16e6535934445e9dd6e3f30e8fffe`, at protected main
`c1e6222e9b7de6431b0e5115e4e43419e12e1323`. Exact-head CI
`36682469410` and exact-main CI `36682800993` passed. Root independently
rebuilt Release with zero warnings/errors, ran focused 6/6 and full 50/50
tests, and verified formatting. Real Docker-context exclusion/retention,
actual Production HTTP/disposable PostgreSQL/native private incident, and
generated/published XML/non-root image evidence is recorded in that PR.
Existing Country `5ac7d045` PR #24 and `f0640fe0` PR #27 provenance remains
unchanged. Whole-service coverage and broader lifecycle acceptance remain
open in Country #32; this is not production-derived data or Aspire parity.

Each of the five authenticated-profile source SHAs remains **pending** and
now links to the shared Web issue #415. Producer prerequisites in Customer
PRs #30/#32/#34 do not substitute for a merged, validated Web consumer or
its Auth/Redis/browser and durable quotation retry acceptance. No pending
consumer has been marked migrated merely because another repository merged.
Other owners and retirement decisions remain untouched. The overall total
therefore stays **157 resolved / 939 pending or partial / 1,096 source commits**.

Workflows #238 resolves nine Web-only source commits individually against
merged Web PR #186 (`1d58887f44c5d0300bb1c24d05d89c4a68f74bfa`;
successful validation run `33964899428`). Source diffs and the PR's runtime
and test files were compared at those Git objects:

| Source SHA | Merged Web evidence |
| --- | --- |
| `e79640c8f30f6d030ac487e92f9914c974435164` | CNC search-intent copy in `CncMachiningContent.razor` and `CncMachiningStaticSsrRouteTests.cs` |
| `a07b98ce97b3d4d5593a5247ded663b1cadf4191` | Native multi-part review/color and summary in `InstantQuotationReview.razor` and `InstantQuotationReviewEditParityTests.cs` |
| `8b7ff7a2ef26c10e35a74b4d3d5526ba01f0102c` | Per-part preview snapshot/color refresh in `workflow-interop.mjs`, `instant-quotation-viewer.test.mjs`, and review markup |
| `fb3595dd9c4b5f43e7b6165deed7cea9151f3147` | CAD face ranges and boundary topology in `model-viewer.mjs` and `instant-quotation-viewer.test.mjs` |
| `9cb9e89de948637ac9931241f88e7cab8ee91b35` | Preview/incident separation in `ErrorDisplayModelResolver.cs`, middleware, and `ErrorRoutePolicyTests.cs` |
| `6c6824f90550ec80ec46ed65a683a76e7ff532f2` | Transparent resting recovery links in `space-error.css` and route asset tests |
| `441828056b209f277c8009ea6e40fe408d77eb10` | Three-note scan preparation in `ThreeDimensionalScanningContent.razor` and `ScanningPresentationContractTests.cs` |
| `0a7ae412d2992530516d2816d64d3b3113edc42e` | Native quotation validation and building guidance in customer form, address-validation module, and tests |
| `4486f0e964e508e5eb7b43a59eeaec46cc052c67` | Strict page-size parsing for career/member routes in `PageSizeQuery.cs` and `PageSizeQueryValidationTests.cs` |

This is code-migration evidence only, not deployment, route acceptance, or
data parity. The other pending Web commits in #234 remain pending.

Workflows #236 resolves four Web-only source changes from the additive quotation
series individually: `5650867256ebfddecb4e3bf96afc962269dcd08e` (calibrated
FDM price, Web #268), `da2796fd4dd395cb2a839057f4e8dfd99f13f6b6`
(auditable order cost, Web #270), `54a3033842b19967766d10dcb6cf18f8f032f155`
(resin evidence gate, Web #269), and `8b54af5097b8b4232bc42dcd5684d293c3c9c37b`
(preliminary estimate disclosure, Web #268). Merged Web PR #272 at
`26ffc9df5f14f4f0df531fb7beef64c26095c0a7` includes matching runtime
and regression-test files; required validation run `35489575192` passed.
Adjacent multi-owner additive commits stay pending. This proves those four
code-migration records, not route acceptance, deployment, or data parity.

Source `cbac7d7155da2208c77d56103b6a2cb19196fc83` removed an embedded
HS256 key and required external signing material. AuthService's merged PR #1
replaced this with required runtime-projected RS256 private-key material and
startup validation; current-main CI 36417095916 passed. This is a deliberate
security-preserving architectural replacement, not HS256 wire compatibility.
Workflows issue #191 tracks the remaining issuer/validator owners. The overall
source SHA remains partial until each changed-path owner has independent
evidence; this entry does not authorize deployment or token cutover.

Source `beba894f9554044722fcdeac7adfd0ef5b71cff1` (secure email
verification resend) is fully resolved for its sole Web owner. Web issue #170
and merged PR #169 (`7b13f0547d58e39625124b93e92107725632c003`)
cover the credential-validated, one-time recovery grant, localized resend UI,
and its regression tests; PR validation run `30753044213` passed. This records
existing protected-main behavior, not a new Web change or data-parity claim.

Source `5e2030b7339d4d9bd699fd8c3f406b71706b377d` changes `Maliev.sln`
only to add `Maliev.Intranet.Tests` and its build configurations; it does not
add the already-registered `Maliev.Identities` project. Issue #233 pins a
commit-specific owner correction for this solution path: the split
`Legacy.Maliev.Intranet.slnx` already includes `Legacy.Maliev.Intranet.Tests`
and Intranet CI explicitly builds and tests it (protected-main run
`36505513282`). AppHost and Workflows retain their own test-inclusive
solutions (protected-main runs `36446506100` and `36514003643`), so neither
inherits an Intranet project reference. The generic `Maliev.sln` rule remains
unchanged for other commits. The Intranet callback and employee creation owner
is resolved separately by Intranet issue #227 and merged PR #228 at
`455b81ca90ffb3e018d0e9dad6bcb07cd9426071`; PR CI `36512981051`
and exact-main CI `36515502211` validate the migrated code. Source commit
`5e2030b7339d4d9bd699fd8c3f406b71706b377d` is therefore resolved across
its Auth, Intranet, and Web owners. This is not deployed-HTTPS-origin or
authenticated email-callback acceptance: Intranet issue #229 remains open for
that release gate, including the original disabled-checkbox POST inference.

The same merged Web PR #169 covers source `e25c833ee9a6eea2740210e850b2663d9c292d38`
for verification and first-login security. Web PR #167
(`19b42e1e4c1dd4c87a61c397ea136b3169d306c1`, validation run
`30729578789`) covers source `e62d177b06fc20f1512b7033fe8f14e1e0959935`
motion, `b16aa08b760ad4c2ddb46a3505d5fcc0d0962756` frontend dependency
replacement, and `81909e65ba634ab851b3a794b4ca31b4c3a853bc` service
chapter navigation. Source `04c9bb0d80ddc9d8be97af632c71f1348307c332`
has its Web HLC matcher owner resolved by #167, but the separate Workflows
design-QA evidence owner remains pending in issue #225. These are source-SHA
code/document decisions only, not full feature-route or data-backed acceptance.

Source `2fbee81b4c8a788db4236376dc15231c5eae5b30` finishing guidance is
covered by Web PR #167. Source `7055e4e5f64f8e405033509de324f57362868200`
has both owners resolved: the Web matcher diagnostic code in #167 and the
portable, PII-free measurement contract in Workflows #227 / PR #228
(`4c6787bcc92e6ee44e57360bc9fb0063f908814b`, exact-main CI
`36511604965`). Live GTM/GA4 configuration and production telemetry remain
unverified in Project #2 issue #229; this source-commit code/doc disposition
does not authorize tag publication or claim a production analytics outcome.

AccountingService #32 / PR #33 reconciles the original Invoice, Payment, and
Receipt validator changes under the split Accounting owner. It pins the
RS256-only shared validator, tests accepted/rejected JWT algorithms and
protected routes, and merged at `f64cade04dd6f6dfb2b9b4891f16cd5942db05ad`;
exact-main CI `36426205947` passed. CareerService #21 / PR #22 independently
reconciles the original JobService validator changes with service-specific
issuer, audience, key, algorithm, and route tests. It merged at
`9c69ad0d53fbdad516c766b1be86181fb2997982`; exact-main CI `36427359118`
passed. Both builds had zero warnings/errors and their full affected suites
passed. These are two owner resolutions, not whole-commit completion.

CatalogService #25 / PR #26 (`fcf02d30453ff1402edd59228729aba4cd405b7e`,
exact-main CI `36433603183`) and ContactService #24 / PR #25
(`14449bb228b17135632579c1c8fa867b39f1e595`, CI `36433615000`)
resolve the split Country/Currency/Material and Message validator owners.
CountryService #28 / PR #29 (`aadff644213bd53328d3e2a07f699cfb6f36f46e`,
CI `36432571798`), DocumentService #32 / PR #33
(`0ac95bbbd1b16408ddb989dfe3b7fbe0d348c6c8`, CI `36433403221`),
and EmployeeService #22 / PR #23 (`7b15f78958626b4d929082f250ee5257d2dc7240`,
CI `36431868154`) independently pin the validated RS256 shared validator
and test production issuer, audience, signing key, and algorithm rejection.
DocumentService also supplies non-secret issuer/audience defaults while its
public key remains externally injected. Each owner passed its affected full
suite and exact-main CI, with image publication gated off. The source SHA
remains partial, despite seven more completed split-service owner slices:
CustomerService #27 / PR #28 (`d70051778809133168b6ed1fce0acf973471e5f0`,
CI `36437973409`), FileService #35 / PR #36
(`ed973193daa446ecd5e3c9a6e89ce12b0a13eade`, CI `36438724821`),
NotificationService #37 / PR #38 (`5098626ebc1f640db0f8c49ecf7146d0a22823a2`,
CI `36439394379`), OrderService #42 / PR #43
(`b7e6ccfed23baeddc717738f746b7c6bbe74c6f8`, CI `36439969535`),
ProcurementService #22 / PR #23 (`18e02b0013ad7539b2c977a967a1bb208722f371`,
CI `36440670906`), QuotationService #66 / PR #67
(`9788378d7628917c8fef9bc7df70bfbf41afd7fa`, CI `36441811934`), and
ServiceDefaults #55 / PR #56 (`515c5898a478eef914d5515eabd95930c1d2d8b7`,
CI `36436862954`). These pin the shared RS256 validator, exercise
production-mode acceptance and rejection, and preserve the split service
boundaries. Quotation's exact-main CI passed; no image was published.
Workflows #197 remains partial: AppHost #121 / PR #122, AuthService #101 /
PR #102, Intranet #219 / PR #220, and Web #384 / PR #385 now pin the
corrected redacted action at `d7efac266bc66273bc45eab583618871292ecbd6`.
The Intranet exact-main run is still being verified; the DataMigration consumer
remains on an earlier action pin and is owned by its separate guarded-data
workstream. The proposed
PredictionService retirement still lacks explicit owner approval. Neither a
source path classification nor a superseded runtime is retirement authority.

Workflows #195 / PR #196 added redacted publication-time detection of JWT
signing material in `.resx` and generated resource comments (merged
`512d1acca3e2fe70dd341a6324b9a8237f3de2e0`, exact-main CI `36426293884`).
Workflows #197 / PR #198 added the same scan to the shared .NET validation
action (merged `73dd7304ffe85ec504389fd7664cc39070b9f148`, exact-main CI
`36427714339`). Workflows #202 / PR #203 corrected multi-checkout repository
selection in that action (merged `d7efac266bc66273bc45eab583618871292ecbd6`,
CI `36445163234`). The Workflows owner remains partial until the action is
pinned and validated in every affected service; one consumer is not evidence
for all services.

Source `e2fbd8e608748bf6f9f1e58824beb41cd1b0f379` removed a stale JWT
resource secret from generated XML documentation. AuthService #103 / PR #104
adds a source-specific absence regression and pins the XML-aware scanner,
merged at `3b549aed37258df676bef9f9acc5d5101ad8229b` with exact-main CI
`36450205432` green. Workflows #205 / PR #206 adds bounded, redacted
generated-XML member scanning with positive and negative tests; it merged at
`b856eb3dc57fe6597c7a491ecbf65b2938c330a1`, CI `36449262634` green.
That shared owner remains partial until the corrected action is pinned and
validated across all relevant consumers. No stale resource value is copied
into the Legacy repositories.

Source `c5fe0e4446f4bf96917d6d1e2a84216f9ea0bea3` externalized provider
credentials. NotificationService #39 / PR #40 confirms the existing runtime-
only Brevo configuration rejects blank keys and accepts an externally supplied
key in production, merged at `cfc4a8cfdb5e9f1a266589d2f972008183cac535`
with exact-main CI `36452071826` green. Workflows #207 / PR #208 adds redacted
provider-resource detection for `.resx`, generated XML, and generated comments,
merged at `4ddf7c0d74295927f5a6eb8571c18aad924faec3` with exact-main CI
`36453207817` green. The scanner still needs adoption by every affected split
consumer, and proposed PayPal retirement lacks explicit approval, so the
source SHA remains partial. No credential values, old
resource files, or application deployment are included in this disposition.
Workflows #210 separately tracks the next source SHA,
`868b5909406cc3759254ee10520e04d4ad5beab0`, whose secret-scan and
PostgreSQL-parity test changes are still pending split-repository acceptance.

Source `7255bd59625694a9da85b964ad6ffa32c1490cec` adds a fail-closed,
PII-free aggregate outcome receipt validator with quotation/invoice wire
fixtures and regression tests. Workflows #180 links its sole owner to the
adapted Legacy implementation in PR #23, merged at
`6e3bb55f5ff3ee2b69dd6b4aee6333777ba0ed36` with exact-main CI
33964911473. The Legacy quotation/invoice producers serialize PascalCase,
so the target validator deliberately accepts that producer wire shape rather
than the source's camelCase payload. Its synthetic fixtures, 16 Python tests,
and seven .NET wire fixtures pass. This resolution does not assert a collected
live receipt, Ads attribution, or production deployment.

Source `894e437e064c1e4b693b43fe45d15b6ac1d70168` has distinct Intranet
and Workflows owners under #182. Intranet PR #155 merged the authenticated
employee-session outcome bridge, fixed producer routes, UTC-window and
source-specific permission checks, aggregate allowlist, generic unavailable
receipts, and no-store response; PR #188 retained the original
`/Analytics/OutcomeReadback` route as an authenticated alias. Their merged
protected-main SHAs `736eeb74f53e9f8c58b1d0f5ddabf01d124262ea` and
`f1061bb445b164d5ad968892d1c59db65a6312fa` passed exact-main CI
33969206504 and 36275244245. Workflows PR #67 merged the offline receipt
collector documentation for the canonical Operations route and Analytics alias
at `7f01550a94d1140615f6591e7ad05122e3ae4c8b`, exact-main CI
36275583537. These satisfy this source commit's code and documentation
behavior; Intranet #183 remains open for authenticated production-derived
Aspire acceptance. Neither mock tests nor route existence prove live receipt,
production data, or deployment parity.

Source `61df92fb171a5c1c65a46a07cd70777d87e1a46e` is an approved no-op for
both QuotationService and Web under Workflows #175. The committed three-path
diff removes only final newlines; `git diff --ignore-space-at-eol --exit-code`
against its first parent is empty. The resolution generator limits this
disposition to the exact SHA, three paths and two owners, then verifies each
owner's reviewed target SHA is an ancestor of the ledger's protected-main
snapshot. Neither owner has a migration PR or merged runtime SHA for this
source commit. It does not certify broader quotation or Web parity, deployment,
or production data.

Source `f0640fe0719b2eb6becda378bff08153d955be07` has a CatalogService
owner for the original MaterialService exception-handler change. CatalogService
#21 / PR #22 pins the redacted shared middleware and contracts its use without
the retired LoggerService handler. Protected Catalog main
`45629ed48c92c0bf938d4e1076b09ea86441bd8c` passed exact-main CI
36388500752; local Release build, focused and full Catalog suites, shared
failure-logging tests, formatting, dependency audit, and secret scan passed.
This resolves only the Catalog owner of that source SHA. Other owners remain
independently pending; no deployment or production data parity is implied.

The AuthService owner of the same source SHA is resolved separately by
AuthService PR #96, merged at
`649f89898fdddbece38d2ae7a151c55cd077528f` with exact-main CI
36378234171. It pins the redacted shared middleware and tests bounded
correlation identifiers, safe fallback, generic 500 responses, and incident
correlation. This does not resolve the other f0640fe owners.

The EmployeeService and CustomerService owners of `f0640fe` are also resolved
independently. EmployeeService #18 / PR #19 merged at
`997fc23dc7c6b77f12e19b3b1a83e9537b253071` with exact-main CI
36391144381, Release build, 48/48 tests, format, vulnerability audit, and
secret scan. CustomerService #25 / PR #26 merged at
`cebf45e8e1eeb600d760a565f8b0970c7f434148` with exact-main CI
36391610412, Release build, 89/89 tests, format, vulnerability audit, and
secret scan. Both pin the redacting shared failure middleware and add focused
contract regression coverage. The source commit remains partial: other owners
and the proposed PredictionService retirement still require independent proof.

Additional `f0640fe` owners were independently reconciled on 2026-09-28:
AccountingService #29 / PR #30 (`bb8b7edb`, exact-main CI 36392134819),
FileService #29 and #31 / PRs #30 and #32 (`26a9e775`, exact-main CI
36393766167), OrderService #40 / PR #41 (`773214c2`, exact-main CI
36394029041), ProcurementService #20 / PR #21 (`f9084920`, exact-main CI
36393820622), and DocumentService #28 / PR #29 (`f309f6a8`, exact-main CI
36394708345). Each pins the redacted shared failure middleware and has
service-specific error/trace contracts; their protected-main Release builds,
affected test suites, and gated CI passed. NotificationService #31 / PR #33
(`32d21588`, exact-main CI 36392560478) covers only the Email path, so its
owner remains **partial** until MessageService #32 is resolved. Intranet,
Web, Workflows, and the proposed PredictionService
retirement remain pending. No app deployment or data parity is implied.

Workflows #173 reviews the LoggerService ownership boundary separately.
`Maliev.LoggerService.*` contains the retired HTTP logger/API and NLog behavior,
not retained message-wire contracts. The 21 source commits touching that path
are enumerated exactly in the generator and contract test: 18 lose the false
CompatibilityContracts owner while retaining ServiceDefaults, each with a
per-SHA owner-set transition. `5fac706a`, `72eb9f19`, and `90f34b38` retain
CompatibilityContracts because they also change actual shared/middleware
paths. No owner-set correction itself proves a ServiceDefaults runtime
migration or completes any other owner of these commits.

Source commit `7ebe7e4bf83a435ecb18afc29cf263424ed2bb74` persists
quotation-request journey attribution. Its QuotationService owner is migrated
through QuotationService #35 / PR #36, merged at
`55a9689bca494b8bdd0deab4aee2ed9ea83f30c3` and present in protected
main `4be2bc83dcc9eb49739aebbfb6bb91d24d20b509`; exact-main CI run
36296023712 passed. The target preserves optional `JourneyId` on create,
read, list, and idempotent replay, does not change it on update, and adds a
nullable PostgreSQL UUID with a filtered index and contract/upgrade tests.
Workflows #111 tracks the QuotationService resolution. The Web owner is also
covered by Web #259 / PR #260, merged at
`17626967d0eb93142e1cf517038c01af4e1381b6`, an ancestor of protected
main `02e0226c45e8d117d58726ebc70b3994f48c9d59`; exact-main CI run
36320839013 passed. The Web implementation sends a stable non-PII journey GUID
through manual and instant quotation submissions, requires the API response to
echo that GUID, and queues the returned persisted journey identifier only
after a successful response. The Web client validates its request/response
contract, while Web tests cover the quotation client and `journey_id`
analytics payload. Workflows #113 tracks this source-SHA
mapping specifically: Web #259 / PR #260 were implemented against the later
related source commit `3ce9936b6e39f41c000e542f005a18645f445a8a`, so
their source SHA alone was not assumed to prove this earlier commit. The
DataMigration owner remains pending independent evidence; the source commit
is still not complete.

Source `3ce9936b6e39f41c000e542f005a18645f445a8a` is a separate Web-only
CNC attribution commit. Web #259 / PR #260 explicitly migrate its API-owned
`request-{id}` transaction IDs for manual, instant-3D, and CNC quotation,
including `instant_cnc_quote` / `cnc_machining`, validated journey GUIDs,
finder attribution, and contained analytics failure. PR #260's merge
`17626967d0eb93142e1cf517038c01af4e1381b6` is in protected Web main
`02e0226c45e8d117d58726ebc70b3994f48c9d59`, with successful exact-main
CI run 36320839013. Workflows #115 tracks the full-SHA resolution. This
Web-only commit has no additional mapped owner; the record is complete as a
code migration, without asserting deployment or production-data parity.

Source `7c416cc8cfd27ef7440e7c046529011630276807` switches the site's
Latin typography to Outfit. Web #261 / PR #262 explicitly migrate this
Web-only source commit: self-hosted Outfit 400/500/600 Latin and Latin-ext
assets and license replace Inter, Noto Sans Thai remains for Thai text, and
site/error CSS plus generated bundles and font-delivery contracts are updated.
PR #262 merged at `1a31a06b48dee6aa1ab7ecf2d81e122b3c62c3b0`, an
ancestor of protected Web main `02e0226c45e8d117d58726ebc70b3994f48c9d59`;
exact-main CI run 36320839013 passed. Workflows #117 tracks this full-SHA
resolution. This is code and shipped-asset parity, not proof of visual
acceptance or an application deployment.

Workflows #119 records three separate Web-only public-surface commits, each
with its own source SHA, target issue, merged PR, and protected-main evidence:

- `14a7f42608526b1773643e8050a2ec9c775e6723`: per-part quotation
  thumbnails and settled additive processing state through Web #255 / PR #257,
  merged at `3913dc07d8af3120a6fd6832559ab71acea4b154`. The target takes
  `viewer.snapshot(partId)` rather than a snapshot of whichever part is active;
  the focused interop contract tests this distinction.
- `96392ed2a1913cb0c95bf8adc4668d35cc8137ff`: Thai service-page intent,
  quote-ready printing/CNC file guidance, and static-SSR/rollback metadata
  through Web #266 / PR #267, merged at
  `051b42f4bc21522ab452fd0a595d0db36363de96`.
- `5928c0198ca32731514f97d1e1ff7c83cd2393be`: nationwide parcel and
  appointment guidance with a qualified THB 100 shipping starting price,
  visible content, and FAQ/SEO contracts through Web #277 / PR #278, merged
  at `1dc5ee13bb4aeada575c9fcfb34a8ce62be22d6c`.

All three merges are ancestors of protected Web main
`02e0226c45e8d117d58726ebc70b3994f48c9d59`, and exact-main CI run
36320839013 passed. Web #277 also mentions three other source commits; those
remain pending because PR #278 does not independently cite their full SHAs.
These records prove migrated code and contract coverage, not visual acceptance,
deployment, or current production data.

Three cookie-consent source commits
(`1b3cda47e94604df1304930d48fcabf395626f31`,
`9523c5a3cf8a9db6da459aa48dfde81636ebac88`, and
`251bb70bf3e9e747d9437828f7df75983eebaab7`) have Web runtime parity
through #284 / PR #286 and a completed EN/TH, light/dark, desktop/mobile
native-dialog browser regression through PR #349, merged main
`02e0226c45e8d117d58726ebc70b3994f48c9d59`. Exact-head CI runs
35882259414 and 36319804683 passed. This verifies the migrated browser
test matrix; it does not claim authenticated production consent telemetry or
a Legacy application deployment.

Source merge `4d9954c086c391698399b9a089f64dd57fbf5a95` was reviewed
against its first parent independently. Its five-file delta changes the
cookie dialog and Thai resource, application-shell CSS, and source/browser
tests. The native modal, localized optional-cookie choices, centered
responsive presentation, dismissal/persistence, and consent timing are
represented by Web #350, merged PRs #286/#349, and successful exact-main
Web CI run 36320839013 at
`02e0226c45e8d117d58726ebc70b3994f48c9d59`. Unrelated source merge
`07203ead903be395aeb3f56c13c562b58cc77392` also contains scanning/CNC
changes and remains pending its own disposition; it is not inferred from
the cookie consent merge.

The 3D-printing pricing-integrity release has ten Web owner resolutions through
Web #256 / PR #258, merged main `ad393a5c5c74174a2a8f8989d0bf03263c20e42d`
and successful PR CI run 34948586706. These include eight Web-only commits and
the Web side of source `60d3677264e046fd73028ff3ccb75097d153bedb` and
merge `2d126d1d55a3240e40678136e6aa621c7f10ed47`. Their separate
Workflows ownership, plus source design and plan commits
`d957038a208b2cbdf1604010a6d82f1d74f1a06c` and
`2128395c31a1ebfe94f9d0ced846bdc861fe62f4`, is resolved through
Workflows #100 / PR #102, merged at
`3542bf908fc345a2151314fbcb95455deb3cb818` with successful CI run
36320209418. The dated design, validation intent, and no-deployment
boundary are preserved in
`migration/historical-additive-pricing-integrity-2026-09-14.md` and its
contract test. Web implementation evidence alone was not used to resolve
the Workflows owner.

The backfill verifies six Web-only source commits through issue #276, six
more recent CTR/qualification commits across Web, Intranet, and Workflows,
and source commits `fd37fbd03bc767f026a625fd6a91107ada91a96f` (Web
#313 / PR #314) and `1e45a63becfc696459fc6527ef4c85980fb059cc` (Web
#316 / PR #318), and `63d68317f7ae12def6b7caceca9883a7b75475df` (Web
#319 / PR #321). Each has owning issues, merged PRs, protected-main
ancestor SHAs, and successful exact-main validation. Source
`b80a47f85ac064c66464bbb83c4329e3b5149e44` is covered by Web #337 / PR
#186, while `22b4fa5064e223b3460bbe87fca48aca96b4f0ee` and
`1cbc27f152f7f00a3e7e712935f52ab883c8ad71` are covered by Intranet
#187 / PR #188; the first of those also has a Workflows documentation owner
covered by #68 / PR #67. Source `7851975ee1da8fd4aaea23b6f17a5db56206f4d6`
has Web behavior through PR #186 and a dated Workflows evidence record through
#71 / PR #72. Source `dcff89963b113e82738476126a545b91a3087a60`
has Web technical-filament pricing behavior through #338 / PR #186. Source
`d852d3ef0ea45bba51bb29de557784b5e5fffae6` has its
QuotationRequestService producer through QuotationService #52 / PR #53 and
its dated historical qualification plan through Workflows #74 / PR #75.
Source `8e133abe65078c6a0bbca1d43473c6546ed6284f` has its qualified
quotation scorecard fixtures and validation through Workflows #59 / PR #60.
Source `1360173adfdd038cdb1f179cec886ac644a4bbc6` and
`c544f7145c12592d8e6069b690cc704858ed9b7f` have Web 404 route/assets
through PR #186 and browser interaction parity through #339 / PR #340,
including the shipped physics-bundle export repair. Source
`eb52167166e12d832ea6c800795a8357d526f759` has Web route behavior
through #315 / PR #317 and a dated Workflows decision record through #80 / PR
#81.

Source `a73acf2e4de9a611c7eda22cf6dbdae333d231cf` is a separate dated
3D-printing CTR/funnel implementation plan. Workflows #77 / PR #133 preserve
its measurement, qualification-readback, and no-release decisions in
`historical-3d-printing-ctr-plan-2026-09-26.md`; the protected-main merge is
`538faed560f40164df77327583d4ea6d0f169d5e` with successful exact-main
CI run 36342823633. This resolves the source authoring artifact as historical
context, not as live CTR, qualification, or Aspire acceptance proof.

Six 3D-scanning proof and accessible-tab source commits
(`ae7ca00ed5318d9041f022a874d36bb6c53e85a9`,
`d364df8f4a323ac7cd96efd17c0f7726d903b679`,
`b8877ed45bc868e0148dd558cbd60d00c3e53de7`,
`2c2e547e428446024805315617e9828ed9b7de39`,
`c7b9dfe167f994e8cf895a537f047227856b19b2`, and
`15d2d6a9ed04ee85d4f27905c0dd0335f228ac1f`) have their Web owner
through #283 / PR #288, merged main `25d570adff80f7f9cd50c295c3511b9efc9e186b`
and successful exact-main CI run 35891559390. Source
`da58002047bcea0d00d0769deb99173ef21bdf81` has its one-sided
qualification identity boundary through QuotationService #57 / PR #58
(exact-main CI 36279902615), persisted-lead consent browser lifecycle through
Web #341 / PR #342 (exact-main CI 36282184647), and optional qualification
receipt CLI behavior through Workflows #59 / PR #60 (exact-main CI
36224534263). Eight Web-only wall-thickness advisory source commits
(`e69ffe1f7054c72ed0ea63c8313bca54ca54094e`,
`d9f4b0f3cef18f4df43ba8f3cd3f2c6d813289d6`,
`976bcb0089ae52c6023567613a95ce9246dd59f8`,
`81eda1540c56046d5bd80542badaeca249499666`,
`f72f263a33d7f9ef0c06d696c59395b5d5a78b60`,
`3f766fa00f23fffda6c15cab2ba231117c6eee50`,
`483a2fdb0beeafa014bb6b0a5ca1e85cd7bdbb74`, and
`351825232f787ef988c7c058910520a14aa70123`) have their bounded
worker, evidence transport, process policy, heatmap, and thin-surface
presentation through Web #281 / PR #292, merged main
`94931cea28e1d1c95b9a788a2d2d94afdab2a8e0` and successful exact-main
CI run 35900642700. This is advisory target parity, not production upload
end-to-end proof. Source `c690f466e53868443ea0cf82caa460bcbcc8598f`
changes only final newlines in nine Web test files; Web #281 / PR #292
explicitly records the normalized target regression tests, with merged main
`94931cea28e1d1c95b9a788a2d2d94afdab2a8e0` and exact-main CI
35900642700. This formatting-only resolution does not establish additional
runtime or real-upload browser acceptance. Source
`3b8bfe3658a1205b4811d063d44bec8cfa88d895` has its Intranet linked
request-to-quotation provenance through #192 / PR #193, merged main
`337b0e2e02ad074eb83af1697c6fd7e064f46153` and exact-main CI
36290275905. The QuotationService first-acceptance outcome, deterministic
event key, employee readback, and PostgreSQL adoption are on protected main
through #21 / PRs #23 and #32, with merged main
`bd201a5cd93fc862669a87f7f1bfd94086ba1047` and successful current-main
CI 36279902615. This resolves that source-code owner, not #21's separate
production-derived Aspire acceptance gate. DataMigration's Quotation schema
alignment remains pending under #94 and #132, so the source commit is partial,
not complete. Source `4198baa6b0e7903f2b9b6e3d5d68f9d2c2b5b0db` is an
approved retirement: owner-authored and merged Intranet PR #182 documents that
the original `js-yaml` lockfile patch has no npm/Gulp dependency graph in the
migrated .NET application; Intranet issue #181 is closed with that evidence.
This adds no Node dependency or runtime behavior. Source
`e78ab85594e688aed223f54ef31c7b6df399a735` has the identical stable
Git patch ID (`a37c998b5c69e15cd528ae3e8ef2d7369e448a79`) as earlier
source `be7443919e54a66c933bc49af8c79d2a9ab0f1cf`. The qualification
workflow was migrated through Intranet #172 / PR #173, merged at
`a94c9cb472ce0c5fce323ebbff1a9c03705f2bd8` with successful exact-head
CI. Intranet #195 records the duplicate SHA independently; no second runtime
patch is needed. Separate aggregate qualification and authenticated
production-derived Aspire acceptance remains open under Intranet #183. Source
`7f010ba7742e96367bdf5039dd03e994fadcfa1b` has its password-setup
email/token validation localization through Web #294 / PR #295 and its
instant-quotation tax/building guidance through Web #276 / PR #347. Both are
on protected Web main `c1c4211aa81ef14651e06da0a71e862f430be5a6`
with successful exact-main CI run 36312107291. Web #276 remains open for
broader uploaded-part acceptance; that is separate from this source commit's
specific localization changes. Four more Web-only source commits are now
independently resolved through Web #276 / PR #348 on protected Web main
`92d3f273b53a26754c35b982cb7c163749d5b320`: `03254079a98245509e73a41e143ff75bf536449b`
(native review fields and actions), `7aa95d1111528d3d875d8001a43676118974c1d0`
(bounded bilingual analysis status), `20fe822f80cb8f04d671897281a96a9c7dc33510`
(expanded detail and keyboard-scroll assertions), and
`b6f9eacea2669c7fcf0f619dc0c96f2f104ca861` (native dock equivalent of
the source-only metrics wrapper test). Exact-head CI run 36314839372 passed;
Web #276 remains open for broader real-upload acceptance. This evidence is
deliberately not a claim of full migration parity.

Source `7f70e8e758e6faf3bb9d809f3c8937c32c4c72cf` fixes signed GCS
downloads using a basename attachment filename. FileService #27 / PR #28
migrated that behavior with slash/backslash normalization, header-safe
Content-Disposition encoding, and Thai `filename*` support. The target is on
protected FileService main `74cd4deb594482ee933f396ff639b4389a8926c8`,
and exact-main CI run 36327086782 passed. The existing route, clean-metadata
authorization, seven-day maximum, V4 signing, and ADC/WIF boundary remain
unchanged. The original commit's generated documentation and historical
package reference do not represent additional behavior. After this single
SHA resolution, 1,024 of 1,096 source commits remain pending.

Source `b75d73e4c06426a948b4eb07fc3fde50f45ea87c` changes only the
original Web injection-molding FAQ assertion from six to seven entries.
Legacy Web already asserts seven rendered FAQ details and seven FAQ schema
questions in `LowVolumeInjectionMoldingParityTests.cs`. Web PR #182 introduced
those assertions in merged commit
`304d4372e930d902fede3620cf8e8500925067b4`, which is an ancestor of
protected main `02e0226c45e8d117d58726ebc70b3994f48c9d59`; exact-main
CI run 36320839013 passed. Workflows #121 records this source SHA separately.
This is an already-implemented test-contract resolution, not a claim of
deployment or full production-data parity.

Source `f83453b48d1ad9d365de7d4e09d8afc1b4093c3a` preserves rounded
customer-facing additive line prices through order totals. Web #298 / PR #301
ported that behavior and its pricing, ticket, and submission regressions in
merged commit `77d6ac58db29cc2d63ccdb1db3111cac7a86605e`. Required PR
CI run 35908136674 passed; the commit is an ancestor of protected Web main
`02e0226c45e8d117d58726ebc70b3994f48c9d59`, whose exact-main CI run
36320839013 passed. Workflows #124 records this specific source SHA. Broader
additive simulation and tier behavior remains tracked separately by Web #275;
this entry does not imply its completion, deployment, or database parity.

Source `a785bcd6bcb07740b879b8f74c519a14282848d4` removes unsupported
native CAD formats from the public 3D-printing quote guide and standardizes
Thai scanning comparison copy. Web #351 / PR #352 replaced the guide with
the same formats accepted by the instant-quotation upload/viewer contract,
and added EN/TH rendered-SSR and component regressions. The target Thai
scanning heading already matched; the PR adds a rendered regression proving
that equivalence. PR #352 merged as
`51fd6e76aa11b46c2654e42fae65c83ece402958` after required CI run
36332704456 passed; exact-main CI run 36333622139 provides the post-merge
check. Workflows #123 tracks this full SHA independently. The separate source
TOC-ordering change `cea523b0f06df9be7ef091d6ef8abd7a6ccb6552` is
tracked separately by Web #353 and Workflows #129. Web PR #354 places the
in-page TOC after quick facts and before the quotation guide, preserves the
anchor targets, and tests rendered English/Thai order. It merged as
`b99b628dd125b8fc52c8b3be94a55fd11af1f6ce`; required PR CI 36335175684
and exact-main CI 36336302750 passed. This resolves that source SHA as code
parity only, without claiming deployment or production-data parity.

Two customer-details presentation commits have separate resolution records:
`2e2d482eb49d43cb2c46c21e50b0746a7776af44` moves the order ledger and
customer form into the redesigned panes, while
`ba886067587c947ea11b090ef8aa473fbee2fb12` improves the scrollable form,
thumbnail crop, and responsive action note. Web #279 / PR #291 names both
source SHAs and ports the target-native layout in merged commit
`3cd65b0822b15938bf0b23cb52b2de4d722d76b5`; it keeps all 27 posted
form-name entries, action, and antiforgery behavior and tests desktop, tablet,
mobile, keyboard, and Thai/English presentation. PR CI 35895552158 and
protected Web main CI 36320839013 passed. Workflows #127 tracks both full
SHAs individually; no deployment or database parity is inferred.

Source `eef114c7e95cbd9378f700710525c58c8cc7cffc` corrects the CNC
SolidWorks upload guidance. Web #282 / PR #285 makes English and Thai public
copy, dropzone, client rejection, and server rejection agree that SLDPRT
must be exported to STEP, with focused CNC and full Web regression coverage.
The merged target is `3de5bcb5cb5f4e46a83596d906c74ed92dccbe8d`, an
ancestor of protected Web main; required PR CI 35878993230 and exact-main
CI 36320839013 passed. Workflows #130 records this source SHA separately.
This is not a claim of deployment or production-data parity.

The generator preserves previously reviewed entries, rejects removed source
commits or changed owner/retirement sets, verifies the source checkpoint
against live `origin/main`, checks exact reachability/order, and verifies each
claimed merged SHA is an ancestor of the corresponding protected-main SHA in
the ownership ledger. Do not infer all-commit parity from `legacyTargets`,
which is only a repository-head snapshot.

From an isolated Workflows worktree, with the original repository read-only:

```powershell
& .\scripts\New-SourceCommitLedger.ps1 `
  -SourceRepository '\\maliev\repository\maliev-web' `
  -SourceRef origin/main -LegacyRoot 'B:\maliev-legacy'
& .\scripts\New-SourceCommitResolutionLedger.ps1 `
  -SourceRepository '\\maliev\repository\maliev-web' `
  -LegacyRoot 'B:\maliev-legacy'
```

For each reviewed owner, update only its own `ownerResolutions` entry with
`status: migrated`, issue and PR URLs, the actual merged target SHA, and a
validation evidence URL, then regenerate. For a retirement candidate, record
the exact paths, owner-approved reason, and approval URL. Leave unknown work
`pending` or `blocked`; never manufacture evidence to make the count zero.
