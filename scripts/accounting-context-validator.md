# Accounting source context inspection

`validate-host-dependency-context.py` accepts only profile `accounting-host-dependencies-v1`. It does not invoke Git, Docker, a registry or an application. The caller supplies an uncompressed `context/`-prefixed tar and a bounded provenance JSON manifest:

```text
python -B scripts/validate-host-dependency-context.py --profile accounting-host-dependencies-v1 --caller-ref <reviewed-40-character-caller-commit> --archive context.tar --provenance provenance.json
```

Manifest keys are exactly `schemaVersion` (integer 1), `profile`, `callerHead`, `sourceBase`, `publisherHead`, `defaultsHead`, `defaultsTree`, `contractsHead`, `contractsTree`, `dockerfileSha256`, `policySha256` and `requiredSources`. The last field maps exactly the seven `REQUIRED` paths in the script to lowercase SHA256 digests. The frozen family identities live in `IDENTITIES`; callerHead must match the separately supplied reviewed caller commit. Duplicate keys and unknown fields fail closed.

The parser limits archive bytes to 32 MiB, regular members to 1 MiB, physical headers to 2048, PAX metadata to 16 KiB and manifest bytes to 64 KiB. It checks physical headers before PAX reads, supports bounded local USTAR/PAX metadata, and rejects unsupported types, links, traversal, duplicate normalized names, Git metadata, malformed padding/end markers and unexpected trailing data. It reads the archive directly; the default mode creates no files.

Optional `--stage-root <existing-output-parent>` creates a fresh owned `workflows-accounting-context-*` directory containing the verified archive bytes. This mode additionally requires the exact frozen Accounting `.dockerignore` and API Dockerfile bytes. It preserves them without interpreting or replacing their ordered rules. Failed staging removes only the directory created by that invocation. Successful staging is owned by the caller and its returned absolute path is `stageDirectory`.

Accepted source receipts explicitly leave `provesPinnedDependencyCheckout`, `provesLockedRestore` and `provesDockerignoreSemantics` false. Supplied commit/tree declarations and matching file digests cannot establish an independently observed checkout. The owner must independently acquire and verify the reviewed caller plus exact dependency commits, supply the real engine context export, and perform its locked restore under its separately admitted native lane. Neither inspection nor staging publishes an image.

The context identity fixtures preserve Accounting committed object bytes at source base `ff8fcf61684566b150fe06d88f2ee0c41bc6a33f`: `.dockerignore` blob `a57a86c6e090914913b753d06e6eb86d1d48d7bd`, API Dockerfile blob `88eed4c2ba3f676fc1b1d06e765f1d7d677c9652`. They are test inputs, not a policy template for another service.
