# Portable finishing matcher design QA

Tracks [Workflows #225](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Workflows/issues/225)
and source `04c9bb0d80ddc9d8be97af632c71f1348307c332` (`design-qa.md`).
The source's workstation image paths and historical passed conclusion are not
current evidence. Its conceptual board is not a complete responsive browser
viewport; no pixel-equivalence or production colour calibration is claimed.

## Preserved decisions

- Technical colour controls, ranked open HLC references, one unambiguous selected
  reference and one quotation action.
- No reproduced licensed Pantone cards. An official external finder and an
  optional customer-supplied reference remain separate from the open atlas.
- English and Thai explain screen estimates, Delta E limitations and required
  physical spray-out/reference approval. A digital preview is not certification.
- Keyboard focus and selected state remain distinct, not conveyed by colour alone.
- Current ranking has ten lightness-ordered references. The historical expansion
  to twenty and old Inter/Noto observations do not override the current source
  implementation or site tokens.

## Current runtime evidence, not the old screenshots

[Web PR #427](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Web/pull/427)
contains the portable Web report `docs/finishing-color-design-qa-20261001.md`
and real SSR/Chromium regressions. Its runtime initialization repair publishes
the pinned Three namespace before matcher side-effect modules execute. The
original two desktop/mobile preview regressions were genuinely red; neither CSP
nor WebGL/preview expectations were relaxed.

The tests use the normal compiled application on a loopback Kestrel host, reject
optional consent, and control only the country API. They are not authenticated
production-derived Aspire acceptance. New cases exercise English/Thai at 390 and
1360 CSS pixels (912 high), keyboard reference/sheens, invalid HEX/non-image
errors, preserved selection, the physical caveat and official finder. The actual
quotation form receives HEX, selected HLC, sheen and customer Pantone reference.
The primary action remains visible without document overflow. Reduced-motion
checks observe actual preview pointer callbacks, not unrelated page-scroll RAF.

Root inspected four current matcher screenshots produced by these tests. The
screenshots live in ignored test outputs and are not copied as broken local
links. Sticky page navigation can appear in locator captures; these remain
interaction/layout evidence, not an unavailable conceptual board comparison.
Reproduce from the exact Web revision using its CI dependency pins and existing
browser host preparation (not arbitrary latest dependency checkouts):

```powershell
# Set MalievWorkspaceRoot to this checkout's private CI-pinned dependency clones.
./scripts/prepare-profile-producer-boundary.ps1
dotnet build Legacy.Maliev.Web.slnx -c Release -warnaserror -p:UseLocalMalievDependencies=true
./Legacy.Maliev.Web.Tests/bin/Release/net10.0/playwright.ps1 install chromium
dotnet test Legacy.Maliev.Web.Tests/Legacy.Maliev.Web.Tests.csproj -c Release --no-build --no-restore -p:UseLocalMalievDependencies=true --filter 'FullyQualifiedName~FinishingColorDesignQaBrowserTests|FullyQualifiedName~FinishingColorParityTests'
```

The complete CI workflow also regenerates and verifies committed browser assets,
installs browser OS dependencies, and executes the full affected suite.

Root composed verification: Release zero warnings/errors; focused 53/53 and full
2566/2566, zero skips; solution format and transitive NuGet audit passed; browser
modules 176 passed; geometry 565 passed with ten existing opt-in skips; npm audit
and scoped secret scan clean. A mistaken nonexistent asset-path hash comparison
was explicitly excluded; rebuilding the actual finishing asset was deterministic.

## Acceptance gates

The original draft held resolution pending protected-main acceptance. That gate
passed: Web PR #427 merged at `636ad950dc6a7d37e51a7d6bc4886dadd7ab20a9`,
required-head run 36768471894 and exact-main run 36771208716 both succeeded.
Workflows PR #252 merged this portable record at
`b665f3245666b3285205a1db81ad3fef912019a5`; required-head run 36771843019
and exact-main run 36772137594 both succeeded. Deployment remained skipped.
The follow-up ledger change resolves only this source SHA's Workflows owner;
close #225 only after that ledger PR and its exact-main checks also pass.
Preserve the Web owner's historical PR #167/target SHA evidence separately.
Telemetry privacy and external GTM/GA4 release verification in #229 are separate;
this record neither activates tags nor proves conversions. No application, data,
traffic, deployment, CNC acceptance or physical colour certification is changed.
