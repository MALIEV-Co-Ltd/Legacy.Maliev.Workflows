# Final caller evidence retention

Source-candidate metadata accepts the exact net10.0 SDK basename
`.NETCoreApp,Version=v10.0.AssemblyAttributes.cs` under an `obj` component.
This narrow exception does not allow punctuation in inputs or retained payload
paths, copy source text, bypass symlink checks, or certify compiled membership.

Invoke this separate action with `if: always()` **after** the caller's existing
collector and coverage guard. An upload inside `dotnet-validate` runs before
Intranet's later collector and cannot preserve its output. Pin an accepted full
Workflows commit; only the assigned caller CI owner changes that reference.

```yaml
- name: Preserve actual runner validation evidence
  if: always()
  uses: MALIEV-Co-Ltd/Legacy.Maliev.Workflows/actions/preserve-validation-evidence@REVIEWED_FULL_COMMIT
  with:
    results-directory: TestResults
    production-projects: |
      Legacy.Maliev.Intranet.Bff
      Legacy.Maliev.Intranet.Server
      Legacy.Maliev.Intranet.Contracts
```

The producer retains actual Cobertura bytes, original `coverage.runsettings`,
existing Release/net10.0 production DLL/PDB bytes and a relative-path/hash source
candidate inventory. It never copies source text, a whole checkout, private Git,
application settings, environment dumps, arbitrary logs or test assemblies.
TRX is retained only when it exists: outcomes/counters/opaque result IDs are
copied into an explicitly labeled `outcome-only-trx/v1` derivative. Test arguments,
output, failure details and machine paths are omitted. The manifest records both
original and retained hashes; this is not an unchanged raw TRX claim.

Missing required coverage/binaries/source candidates produces an explicit partial
manifest and a failing preparation step, while `always()` still preserves that
partial manifest. Missing TRX is recorded as unavailable, never invented. Upload
success is not a coverage/test gate pass. The producer cannot certify DLL/PDB
validity, compiled source membership, complete generated-inclusive coverage,
repository authenticity or an atomic filesystem snapshot. Exact source/PDB
ownership and coverage recomputation belong to the artifact consumer.

Intranet's currently inspected settings exclude `**/obj/**`, and its collector
does not request a TRX logger. Preserve both facts exactly. Removing that exclusion
or introducing a logger requires the separately reviewed caller successor and
fresh gates; this action changes neither. Current coverage floors remain BFF80%,
Server85%, Contracts95%. No source closure follows from artifact preservation.
