# Source-commit resolution ledger (#56)

`source-commit-ledger.json` inventories every source commit reachable from the
observed `maliev-web` main, including merges. Merge paths are the first-parent
tree delta, so merge-time conflict resolutions are not silently omitted. Path
ownership and a proposed retirement classification are **not** proof that a
change is migrated, validated, or approved for retirement.

`source-commit-resolutions.json` gives every full source SHA an independent
resolution. Each owning Legacy repository starts `pending`. A candidate
retirement also starts `pending`, even where the path rule says
`approved-retirement` or `source-tooling-only`; the path-rule explanation is not
an owner approval. The generated `complete` flag remains false until every
owner has issue, merged PR, protected-main ancestor SHA, and validation URLs,
and every candidate retirement has an explicit reason and approval URL.
Mixed commits cannot be complete until both kinds of resolution are proven.

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
#81. Six 3D-scanning proof and accessible-tab source commits
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
Web #276 remains open for broader real-upload acceptance. The other 1,046
commits remain pending; this ledger is deliberately not a claim of full
migration parity.

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
