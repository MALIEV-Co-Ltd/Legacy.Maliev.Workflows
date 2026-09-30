# Verified owner evidence update

This records completed runtime slices, not a blanket migration closure.

- Source `e8eaf82abbaf2ed3bc9a19b910b4127818dbaf3f`: Web #411/#412,
  merge `27997dd1faedf357aac4fe20521efbb997c4df6d`, exact-main CI
  [36516218044](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Web/actions/runs/36516218044).
  The preliminary quotation's data URI uses WebP, matching the canonical bundled
  logo. Signature tests and a real generated quotation popup verify image decode,
  MIME and nonzero natural width. This does not close open-sheet behavior #397.
- Sources `5ac7d045c51194edd9e64d8564f1b726b001be34` and
  `f0640fe0719b2eb6becda378bff08153d955be07`: Career #25/#26, merge
  `50d351f7f4c44430588c98cd340da96e2871ec14`, exact-main CI
  [36670765258](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.CareerService/actions/runs/36670765258).
  Actual Production-host and non-root Docker acceptance preserve anonymous reads,
  authenticated writes, safe error payloads and correlated critical diagnostics.
  Real PostgreSQL read/save failures exposed duplicate EF exception rendering;
  Career's narrow diagnostic suppression preserves middleware incident logging.
  Root reran exact-pinned Release with zero warnings/errors and all 36 tests.
  Other source owners and the pending PredictionService retirement remain open.
  The already-migrated f064 record retains its original PR20 merge SHA while
  appending PR26 and its stronger validation; historical provenance is preserved.

The source checkpoint is unchanged at
`4198baa6b0e7903f2b9b6e3d5d68f9d2c2b5b0db`. Target heads were refreshed through
the reviewed generator, which independently reads live remote main and committed
source objects. No source repository was modified, no application was deployed,
and no persistent database migration was run.
