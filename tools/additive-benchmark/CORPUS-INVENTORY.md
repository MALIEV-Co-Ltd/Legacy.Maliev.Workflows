# Bounded inventory helper

`PrivateCorpusInventory.Create(root, limit, consentId)` preserves the original anonymous inventory record and JSON field names. The `inventory-corpus` CLI exposes this helper with explicit root, output and consent metadata arguments; it has no directory defaults, vendor executor, or sample private inventory. Callers must independently have authority to access the supplied caller-owned regular files. `consentId` is output metadata, not proof of consent or permission to read customer files.

Supported formats remain STL, OBJ and 3MF, case-insensitively. Exact-byte duplicates are removed across formats. Selection retains the original four byte-size buckets and bucket allocation followed by deterministic fill; final uppercase digests are sorted and anonymous IDs assigned. The release holdout remains the first `min(12, max(1, count / 4))` entries. Geometry is unreviewed and matched references missing. Empty input remains empty metadata rather than usable benchmark evidence. Version identifiers and record fields are unchanged; JSON ends in one LF.

Admission caps selection at 128, supported candidates at 256, all directory entries at 4096, directories including root at 128, and depth at 16 below root. One candidate is limited to 256 MiB; actual unique-path hash work is limited to 512 MiB with a fixed 4096-byte read buffer. Repeated selection passes reuse captured hashes rather than reading files again. The identifier is strict UTF-8, at most 256 bytes, and contains no control characters. These explicit target limits are stricter than the legacy unbounded helper and may reject a larger caller corpus.

Root, ancestor and encountered links/reparse points are rejected. Input length is checked against metadata before and after streaming. This assumes stable caller-owned regular files and promptly responding local filesystem operations; it is not an adversarial filesystem sandbox or a filesystem timeout. Same-length concurrent rewrites are not attested as a consistent snapshot. No private/customer model or historical corpus has been accessed for this migration slice.

The original deterministic anonymous deduplication regression is retained with generated fixtures. The historical 48-entry payload check is represented by 48 newly generated synthetic files and 12 holdouts; it does not assert historical model digests, actual consent, physical correctness or production qualification. Native build and tests are required before repository acceptance.

## Command and historical source association

The command migrated from source commit `b3a4a28603c1e246cd4622a8394da65c11e08142` is:

```text
dotnet Legacy.Maliev.AdditiveBenchmark.dll inventory-corpus --root <directory> --output <new-path> --consent-id <id> [--limit <count>]
```

Selection defaults to 48. Exit 0 means the requested unique count was captured; exit 2 means fewer entries were available, including an empty corpus; exit 1 means malformed arguments, denied input admission, or output failure. The anonymous JSON is written as UTF-8 without BOM to the output file. Standard output contains only the selected count, and errors use fixed messages.

Target security adaptations reject duplicate options and existing destinations, avoid printing file paths or exception messages, and write through an owned temporary file before a no-overwrite move. Existing link, size, depth, hash-work and consent-metadata admission checks remain active. This CLI portion does not establish the source commit's private payload, matched references, Web UI or physical simulation parity.
