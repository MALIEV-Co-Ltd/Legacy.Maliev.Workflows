# Synthetic producer wire proof v1

The verifier joins nine fixed fixture names with exact Root-reviewed producer
receipt hashes. It makes no network requests and receives no credentials or
private production source. The approval file and its separately supplied digest
must originate from trusted Root review of native producer evidence.

The approval is a JSON object with exactly `schemaVersion: 1` and `producers`,
an array of exactly two pins. Each pin has exactly:

- `producerRepository`: `Legacy.Maliev.QuotationService` or `Legacy.Maliev.AccountingService`.
- `producerCommit`: the full lowercase 40-character native-tested commit.
- `nativeRunUrl`: an Actions run in that producer repository.
- `receiptFile`: a flat lowercase JSON filename within the supplied receipt directory.
- `receiptSha256`: the exact producer receipt bytes' lowercase SHA-256.
- `dtoSourceSha256`: one to eight relative `.cs` paths mapped to exact source hashes.
- `serializerSourceSha256`: one to eight relative `.cs` paths mapped to exact source hashes.

Each producer receipt has exactly `schemaVersion: 1`, `producerRepository`,
`producerCommit`, `nativeRunUrl`, `synthetic: true`,
`productionDtoAndSerializer: true`, `dtoSourceSha256`,
`serializerSourceSha256`, and `fixtures`. Metadata and source-hash maps must
match the approved pin exactly. `fixtures` maps exact fixture filenames to
SHA-256 hashes of producer-emitted UTF-8 bytes, including their final newline.

Producer-emitted bytes are authoritative. The initial checked-in fixture
hashes and local generator do not prescribe serializer field order, decimal
scale or final-newline policy. If the native exporter emits different bytes,
Root must review the actual DTO/serializer witness and explicitly adapt the
corresponding fixture and local generator before approving the joined pins.
Never reformat, reorder, rescale or append/remove bytes from producer output
to satisfy copied fixture hashes. A final newline is included in the hash only
when the native exporter actually emits one.

Quotation owns `quotation-empty.json`, `quotation-zero.json`,
`quotation-mixed.json`, `qualification-empty.json`, and
`qualification-mixed.json`. Accounting owns `invoice-empty.json`,
`invoice-zero.json`, `invoice-mixed.json`, and `invoice-null-currency.json`.
Missing, duplicate, extra, misplaced or altered producer/fixture entries fail.
Duplicate JSON fields, wrong types, unsupported schemas, invalid identities,
source-path traversal, symlinked receipt/fixture files and oversized inputs fail.
Inputs are bounded to 128 KiB approval, 64 KiB receipt and 256 KiB per fixture.
Unknown/private payload fields fail the existing strict outcome allowlists.

The producer exporter may retain additional native controls under its own
names, such as `null-currency-negative`, `repository-http` or
`null-days-negative`. These are separate native checks, not extra entries in
the nine-fixture joined receipt. Root and the sole producer writer must agree
which actual emitted artifact supplies each canonical fixture name. Renaming
an artifact or recording that name mapping must preserve its bytes and digest;
the native implementation and exact receipt remain subject to Root review.

The synthetic window is 2026-08-25 17:00 UTC through 2026-09-01 17:00 UTC.
Qualification deliberately uses camelCase because the route has its own Web
serializer. Quotation/invoice retain PascalCase. All eight valid fixtures must
pass the strict consumer contract; the null-currency invoice fixture must be
rejected. Do not count rejection of that negative control as a missing producer.
The negative control must be exactly one day and one amount, with only the
`Currency` key omitted by null serialization. Its root/day/amount shapes must
be exact; window, UTC labels, counts, count reconciliation and monetary types
must all remain valid. The verifier checks a separate in-memory validation
projection with only that missing key supplied. It never changes emitted
payloads or bytes. Unknown/private fields or any other invalid condition reject
the proof, even after receipt hashes have been approved.

Invoice `DayUtc` labels must end in `Z`, matching the current Accounting DTO
serializer's actual UTC values. The historical local generator used Unspecified
dates; its three nonempty invoice vectors are explicitly adapted to UTC.
Their filenames and monetary/count values are retained. Even a newly pinned
receipt cannot authorize non-UTC invoice vectors. Quotation day labels retain
their own existing producer contract. This finite adaptation does not close
historical source obligations or establish native producer acceptance.

The Boolean production-origin fields are receipt claims. Root must check the
native test implementation, run identity, commit and emitted hashes before
approving a receipt. The local verifier checks the resulting pins and equality;
it does not independently authenticate CI, inspect private producer source,
establish live authentication or certify deployments. Tests use wholly synthetic
receipts/pins and do not create genuine accepted producer evidence.
