# Procurement startup/context owner evidence

ProcurementService #24 is completed by PR #25, merged at
`c54a47ba53562741dd1842725b3e25974f2196a4`. Required PR CI
[36672931685](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.ProcurementService/actions/runs/36672931685)
and exact-main CI
[36673487592](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.ProcurementService/actions/runs/36673487592)
passed; canonical main is clean and synchronized.

The coherent bundle retains a separate owner record for every source SHA:

| Source SHA | Procurement acceptance |
| --- | --- |
| `5ac7d045c51194edd9e64d8564f1b726b001be34` | Actual Production startup uses native console/OpenTelemetry diagnostics and safe correlated failure events, with no NativeLogging runtime dependency. |
| `9e51e6c5da29de8e617b65b59d46882cde6d3b64` | Both former Supplier/PurchaseOrder paths use the retained native logging architecture without deprecated NLog or LoggerService. |
| `03dc9a1271c16e6535934445e9dd6e3f30e8fffe` | Generated XML documentation stays outside source; actual built/published XML contains assembly/member metadata. |
| `03eaff1194c3ae2a54ceefeae31deffaff90436f` | Actual root Docker context excludes nested private/generated artifacts while retaining required source/dependency build inputs. |

The existing `f0640fe0719b2eb6becda378bff08153d955be07` Procurement record
retains its original PR #21 merge `f9084920af54c8c8bb765fb7d55869f8ced733b8`
and validation provenance. PR #25 appends stronger actual-host/database proof;
it does not overwrite historical evidence.

Real PostgreSQL read/save failures demonstrated duplicate EF diagnostics that
embedded provider details despite safe middleware output. Both contexts now
suppress only those duplicate exception-rendering events; standard correlated
critical failures remain. Incompatible Supplier and PurchaseOrder Address schemas
stay in separate contexts/databases, and all existing API/permission/cache
contracts are retained.

Root independently reviewed the diff and reran exact-CI-pinned Release build
with zero warnings/errors plus the complete 65/65 suite. Agent evidence adds
focused 11/11, formatting, package/security scans, and actual UID1654 Docker
liveness/authenticated failure/native/XML acceptance. Existing aggregate API
coverage remains below 80%; this bundle does not claim full-service coverage,
arbitrary-message redaction, live OTLP export, or production-derived Aspire proof.

These are owner-specific resolutions. Other owners and retirement decisions
on each multi-owner source commit remain pending; a bundle is not a blanket
global migration closure. No source repository, persistent database, application
deployment, image publication, or traffic was modified.
