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
covered by #68 / PR #67. The other 1,078 commits
remain pending; this ledger is deliberately not a claim of full migration parity.

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
