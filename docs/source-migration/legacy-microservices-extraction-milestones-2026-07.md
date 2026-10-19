> **Historical source record: reference only.** This document preserves the July 2026 migration plan and its twelve historical service-extraction milestones. Dates, test counts, repository status, approvals, protections, Project states, upload limits and reported completion describe the historical source. They are not current status, current policy or independently revalidated evidence.
>
> **Current acceptance boundary.** Preservation grants no runtime, data-copy, financial, credential, private-resource, release or deployment authority. Embedded commands, instructions, skill suggestions and operational procedures are historical quotations and must not be executed on the strength of this document. Current service behavior and acceptance require separate owner-specific evidence.

## Source provenance

Original path: `docs/plans/2026-07-14-legacy-microservices-migration-plan.md`.

The complete source body below is unchanged from final source checkpoint [`770cb58032969ae4a0fe169686b53ab61a44fff8`](https://github.com/MALIEV-Co-Ltd/maliev-web/commit/770cb58032969ae4a0fe169686b53ab61a44fff8), Git blob `6c56c37e4fbd1c9aa9e3526862acb4a6137a7d76`. The twelve documentation-only source changes recorded here all affect that one path. This provenance does not establish current runtime parity or qualify other source commits.

| Historical milestone | Source commit | Parent | Before blob | After blob |
| --- | --- | --- | --- | --- |
| Contact | `d69ab93d495b31c91dfea94cbd11076f3a8e8713` | `2be6cd0ff25f371ed8c4ed704256a8f5023c4b51` | `2f286680680edf3c2ab34a711485344216e252cb` | `f8871f629a60064cce83625ffa7142fdbcd84d3e` |
| Career | `526b9767f60741e94ffa5cc4b76163ca2577542d` | `d69ab93d495b31c91dfea94cbd11076f3a8e8713` | `f8871f629a60064cce83625ffa7142fdbcd84d3e` | `d59c764f23fb19afd379e69faf3f46eb0ab51acd` |
| Notification | `568a568bbc602d1a9aec60bf2cc1595fb1c66235` | `526b9767f60741e94ffa5cc4b76163ca2577542d` | `d59c764f23fb19afd379e69faf3f46eb0ab51acd` | `b96aa9f4362af6139e96c4f3981f1f8aeb5042fd` |
| Catalog | `223781be14d3b63af0189113d775f5faf189b0e1` | `568a568bbc602d1a9aec60bf2cc1595fb1c66235` | `b96aa9f4362af6139e96c4f3981f1f8aeb5042fd` | `f99fed441c7e1fbec8241c190a920d181408a0a7` |
| File | `677efc0d304acb13e2dbd9b846e82daf0aff2533` | `223781be14d3b63af0189113d775f5faf189b0e1` | `f99fed441c7e1fbec8241c190a920d181408a0a7` | `c7019f240f3dd9a5c82dfe0a84745db0685d37e2` |
| Customer | `f186722f6d7e36e058a30941879c63daa16b2c83` | `677efc0d304acb13e2dbd9b846e82daf0aff2533` | `c7019f240f3dd9a5c82dfe0a84745db0685d37e2` | `0395dfe3d7441bf52a58b444e08ae0c506ab5b58` |
| Employee | `f36a16cb0e16e67044fd20ab96285fc4f1870865` | `f186722f6d7e36e058a30941879c63daa16b2c83` | `0395dfe3d7441bf52a58b444e08ae0c506ab5b58` | `1c267ff791ab8fa0f223d350642de22643cde431` |
| Procurement | `930c9c706c70f9b53333d111e7c96e2a5b9af31c` | `f36a16cb0e16e67044fd20ab96285fc4f1870865` | `1c267ff791ab8fa0f223d350642de22643cde431` | `1cf2fd3bc64771543d94c61b8f59a9b410d2cc3f` |
| Quotation | `814d6bc118bcf400e660a39a08b7a791eb7971ed` | `930c9c706c70f9b53333d111e7c96e2a5b9af31c` | `1cf2fd3bc64771543d94c61b8f59a9b410d2cc3f` | `4a4dd8bfaa7e01ceddf803335854d16d9ecd539c` |
| Order | `c0c1e5e29cbdc3886dec493d273e4c7b558b2aad` | `814d6bc118bcf400e660a39a08b7a791eb7971ed` | `4a4dd8bfaa7e01ceddf803335854d16d9ecd539c` | `bc86668985d5c5d98079e4176490585da2b9f99f` |
| Accounting | `f3554308a1f3713c6e3f43fc8cfa3ca0b0ac6eac` | `c0c1e5e29cbdc3886dec493d273e4c7b558b2aad` | `bc86668985d5c5d98079e4176490585da2b9f99f` | `bd99245b60ba13ece40ace34ae7a5e06228fb8c7` |
| Document | `5abf77a1354de36a189e3e5f60056152ba810270` | `f3554308a1f3713c6e3f43fc8cfa3ca0b0ac6eac` | `bd99245b60ba13ece40ace34ae7a5e06228fb8c7` | `8d462c208c8c0784dc05d284274646f6a6e72fd9` |

Final-source context, not additional migration credit:

- `21e0ebf176de6b60ec6a5837184e26e150820a5c`, parent `a40ae59b9a9cc4182ed397eb02f18f861180c51f`, adds the historical identity-copy rehearsal account.
- `f79657bdd06b878dc99fe45fbf26c40eeffb25f0`, parent `7b311e4e7f0dd80be0441abc2625dab295179f1a`, removes retired PayPal wording, including wording in the Document milestone. The final source body retains that supersession.

The dated extraction claims, operational references and historical limits below remain historical even where a service has since changed. No current data, deployment, credential, provider or financial execution was performed to preserve this record.

## Unchanged historical source body

# Legacy MALIEV Migration Implementation Plan

Date: 2026-07-14
Architecture: docs/architecture/2026-07-14-legacy-microservices-migration.md
Tracking project: Legacy MALIEV .NET 10 Service Migration

## Purpose

This plan turns the approved architecture into independently verifiable delivery slices. A wave may start discovery before the previous wave completes, but production cutover cannot pass a dependency gate from an unfinished wave.

Every task records evidence in the private migration project. Public repository issues contain only non-sensitive engineering details.

## Global execution rules

- Work from a sanitized source snapshot pinned to a recorded maliev-web commit.
- Create public repositories only after Wave 0 secret-history gates pass.
- Never copy the complete monorepo Git history into a public repository.
- Keep old and new implementations runnable until cutover evidence and rollback rehearsal pass.
- Preserve method/path/JSON/auth/database behavior through compatibility endpoints.
- Commit one validated concern at a time.
- Update maliev-gitops only by pull request.
- Never put a production secret in GitHub, a build log, a test fixture or a container layer.
- Do not execute EF migrations against a preserved legacy production database.
- Attach commands, test reports, image digests, GitOps commits and screenshots as evidence.

## Project field values

Status: Backlog, Ready, In Progress, Validation, Cutover Ready, Blocked, Done.

Risk: Critical, High, Medium, Low.

Contract state: Not Captured, Baseline Captured, Compatible, Exception Approved, Retired.

Environment: Local, CI, Development, Staging, Canary, Production.

Wave: 0 through 8.

## Wave 0: safety, inventory and baselines

### 0.1 Record authoritative source state

Deliverables:

- source commit SHA;
- solution/project inventory;
- project-reference graph;
- NuGet and container dependency inventory;
- route/controller/action inventory;
- database connection ownership inventory;
- Kubernetes deployment/ingress inventory;
- Web and Intranet consumer-call inventory;
- active Google tag and measurement inventory.

Validation:

- every deployed route maps to a source action and target bounded context;
- every database name maps to one target owner;
- every currently deployed workload is marked migrate, consolidate, archive or remove.

### 0.2 Secret and history audit

Search current files and all commits for connection strings, passwords, JWT keys, GCP keys, API keys, reCAPTCHA values, email credentials and private certificates.

Deliverables:

- private finding list: generate locally with `python tools/migration/secret_audit.py scan . docs/migration/evidence/legacy-secret-history-audit.json`;
- affected credential owners: captured as redacted detector owners in the evidence report;
- rotation order: captured as detector rotation guidance in the evidence report;
- sanitized extraction allow/deny rules: captured in the evidence report;
- verification that generated repositories contain no prohibited material.

Do not paste discovered secret values into project items.

Exit gate:

- exposed credentials rotated or explicitly disabled;
- old credentials verified unusable;
- repository history scan passes against the sanitized snapshot.

### 0.3 Database restore rehearsal

Restore gs://maliev.com/database/full/2026-07-14/ into an isolated non-production environment.

Capture:

- restore commands and duration;
- database list and schema fingerprints;
- row-count summaries for critical tables;
- referential-integrity checks;
- application read-only smoke test;
- destruction/cleanup confirmation for the rehearsal environment.

Exit gate: a second operator or repeatable automation can restore and validate without accessing production.

### 0.4 Contract baseline harness

Build a harness that captures:

- OpenAPI where available;
- route manifest when Swagger metadata is incomplete;
- canonical request/response JSON;
- auth and authorization outcomes;
- upload/download headers;
- PDF fixtures;
- Web/Intranet consumer expectations.

Store only synthetic or redacted data. Commit fixtures to Legacy.Maliev.CompatibilityContracts after it is safely public.

### 0.5 Operational baseline

Measure each deployed workload:

- request volume and error rate;
- p50/p95/p99 latency;
- CPU and memory working set;
- startup time;
- database query count and duration;
- outbound dependency latency;
- current pod requests/limits;
- availability and restart history.

Exit gate: performance claims in later waves have a comparable baseline.

## Wave 1: engineering baseline and pilot

### 1.1 Create Legacy.Maliev.ServiceDefaults

Public repository contents:

- hosting extensions for health, telemetry, authentication integration and resilience;
- logging filters and redaction;
- standard error codes and correlation propagation;
- test helpers;
- package publishing workflow;
- Dependabot;
- CODEOWNERS/ownership documentation;
- security policy and contribution guidance;
- branch rules and required checks.

Validation:

- sample API starts as non-root;
- liveness/readiness/startup behavior passes;
- telemetry contains no test secret;
- pinned package works without a source-project reference.

### 1.2 Create Legacy.Maliev.CompatibilityContracts

Public repository contents:

- legacy route manifest;
- OpenAPI snapshots;
- DTO/JSON fixtures;
- auth outcome fixtures;
- consumer contract runner;
- compatibility diff tool;
- breaking-change allowlist requiring reason and approval.

No production data or credentials may be included.

### 1.3 Standard CI workflow

Reusable design for each public repo:

PR jobs:

1. restore with locked dependencies;
2. build;
3. format;
4. unit tests;
5. contract tests;
6. integration tests;
7. architecture tests;
8. OpenAPI diff;
9. secret scan;
10. CodeQL and dependency audit;
11. SBOM;
12. container build;
13. container vulnerability scan;
14. manifest validation.

Main jobs:

1. repeat trusted validation;
2. build immutable image;
3. OIDC login to GCP;
4. push Artifact Registry digest;
5. open maliev-gitops PR;
6. report deployment evidence.

Permissions default to read-only and are elevated per job only.

### 1.4 Pilot service selection

Use CareerService as the pilot unless inventory reveals an unknown critical dependency.

Pilot proves:

- public sanitized extraction;
- .NET 10 structure;
- OpenAPI/Scalar;
- CI and Dependabot;
- OIDC Artifact Registry publication;
- GitOps PR and Argo CD deployment;
- contract replay;
- canary and rollback;
- observed resource reduction.

Do not copy pilot code blindly; promote only validated reusable behavior into ServiceDefaults.

## Wave 2: authentication and BFF sessions

Repository: Legacy.Maliev.AuthService.

### 2.1 Freeze identity contracts

Capture validate, token, long-lived-token and customer/employee identity behavior, including failure and expiry semantics.

### 2.2 Introduce new token model

Implement:

- asymmetric key ring with key IDs;
- short access-token lifetime;
- separate durable refresh-token store;
- hashed rotating tokens;
- token-family reuse detection;
- session/user/family revocation;
- clock-skew tests;
- audit events without token content.

### 2.3 Dual validation

Validate legacy and new tokens during a bounded transition. Record usage of the legacy scheme. Define and test the condition for disabling it.

Identity data-copy rehearsal evidence (2026-07-15):

- `CustomerIdentity` and `EmployeeIdentity` were restored from the approved 2026-07-14 backup artifacts into a digest-pinned disposable SQL Server container and passed `DBCC CHECKDB`;
- the source login had `SELECT` permission only on `dbo.AspNetUsers`, and the migration connection explicitly used `ApplicationIntent=ReadOnly`;
- the merged AuthService migration tool at `352195c55ad4237a23a89a9bc5b72c785599e2fb` transactionally copied and then independently validated 3,048 customer identities and 4 employee identities into separate digest-pinned PostgreSQL 18 containers;
- source and destination semantic fingerprints matched for both databases, including normalized SQL Server 100-nanosecond and PostgreSQL microsecond timestamp precision;
- full container ID plus unique run-label cleanup removed every disposable rehearsal container, and no production or GKE resource was changed;
- redacted receipts are stored in `docs/migration/evidence/legacy-identity-copy-2026-07-15.json`;
- production authority remains unchanged until shadow-login comparison and rollback evidence pass in the existing cluster.

### 2.4 Web and Intranet BFF migration

- server-side refresh handling;
- Secure HttpOnly cookie;
- CSRF defense for cookie-authenticated writes;
- no browser local-storage tokens;
- session renewal and sign-out tests;
- parallel-session and revoked-session tests.

Exit gate: identity database schemas are unchanged; both frontends pass end-to-end auth tests; legacy signing secret rotation and rollback are rehearsed.

## Wave 3: low-risk domains

### 3.1 Legacy.Maliev.CatalogService

Consolidate Material, Country and Currency APIs.

Status on 2026-07-15:

- public repository created: `https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.CatalogService`;
- extracted from sanitized Country, Currency and Material source contracts without copying monorepo Git history or secret-bearing legacy configuration;
- migrated to a .NET 10 layered structure: `Api`, `Application`, `Data`, `Domain`, `Tests`;
- all 42 legacy endpoints are contract-tested across `/Countries`, `/Currencies`, `/currencies/exchangerates`, `/Materials`, `/materials/Colors`, `/materials/MaterialGroups` and `/materials/SurfaceFinishes`;
- legacy PascalCase JSON, null omission, material sort values, search fields, pagination shape, named routes and anonymous country/currency list access are preserved;
- PostgreSQL mappings preserve the nine legacy tables, `ID`/foreign-key column names, decimal precision and relationship names while using native `xmin` concurrency;
- the initial PostgreSQL migration was applied successfully to a disposable PostgreSQL 18 Testcontainers instance; it creates no custom `xmin` column and does not contact or alter source SQL Server;
- Redis-backed read caching uses the `legacy:catalog:` instance prefix, bounded expiration, mutation invalidation and PostgreSQL fallback;
- the public Frankfurter exchange-rate client uses the shared resilient HTTP pipeline and preserves the legacy string-valued rates response;
- Swashbuckle and `Maliev.LoggerService` are not present; Scalar/OpenAPI and built-in structured logging come from service defaults;
- local validation passed: Release build with zero warnings, 45 tests including PostgreSQL migration integration, format verification, package vulnerability audit and gitleaks;
- main CI passed on commit `7d7f7609bfd644259649fb05b4ba5c882769b7e9`: `https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.CatalogService/actions/runs/29386004444`;
- main branch protection is enabled with strict `validate / validate`, admin enforcement, linear history, force-push/deletion disabled and conversation resolution;
- GitHub Project #2 marks the CatalogService repository item `Done` with compatible contract and CI evidence;
- deployment is intentionally gated on `legacy-maliev-catalog` Workload Identity Federation and `maliev-gitops/3-apps/_legacy-catalog-service`. It must use the existing cluster, `maliev-legacy` namespace and no new node pool.

Tasks:

- assign database access per domain inside one deployable context;
- preserve three ingress route prefixes;
- add long-lived HybridCache entries and invalidation;
- eliminate N+1 supplier/material queries;
- compare sorted/paginated results;
- load-test reference lookups.

### 3.2 Legacy.Maliev.CareerService

Consolidate Jobs API and prove the pilot pipeline.

Status on 2026-07-15:

- public repository created: `https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.CareerService`;
- extracted from a sanitized source snapshot without copying monorepo Git history or legacy secret-bearing configuration;
- migrated to .NET 10 layered structure: `Api`, `Application`, `Data`, `Domain`, `Tests`;
- legacy routes preserved as `/Jobs`, `/Jobs/job-opening-status` and `/jobs/Levels`;
- legacy database mappings preserved for `Offer`, `Level`, `ID` and `LevelID`;
- Swashbuckle and `Maliev.LoggerService` are not present; Scalar/OpenAPI and built-in logging come from service defaults;
- local validation passed: restore, build, 16 tests, format, package vulnerability audit, actionlint and gitleaks;
- main CI passed on commit `5f4a0633be35b12595e0f6994e097f47ea7a2921`;
- main branch protection is enabled with strict `validate / validate`, admin enforcement, linear history, force-push/deletion disabled and conversation resolution;
- deployment is intentionally gated because `legacy-maliev-career` Workload Identity Federation and `maliev-gitops/3-apps/_legacy-career-service` do not exist yet. Any existing `maliev-career-service` GitOps path is reserved for the new implementation and must not be overwritten by this legacy service.

Tasks:

- preserve job-opening-status behavior;
- add anonymous safe output caching if contract allows;
- validate public job flow from Legacy.Maliev.Web.

### 3.3 Legacy.Maliev.ContactService

Rename MessageService while retaining /messages compatibility.

Status on 2026-07-15:

- public repository created: `https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.ContactService`;
- extracted from a sanitized source snapshot without copying monorepo Git history or legacy secret-bearing configuration;
- migrated to .NET 10 layered structure: `Api`, `Application`, `Data`, `Domain`, `Tests`;
- legacy route preserved as `/Messages` with `messageId` route values and legacy sort names;
- Swashbuckle and `Maliev.LoggerService` are not present; Scalar/OpenAPI and built-in logging come from service defaults;
- local validation passed: restore, build, test, format, package vulnerability audit, actionlint and gitleaks;
- main CI passed on commit `73e1cc5ab3e985517bd83c5fecc77f03f2848c39`;
- main branch protection is enabled with strict `validate / validate`, admin enforcement, linear history, force-push/deletion disabled and conversation resolution;
- deployment is intentionally gated because `legacy-maliev-contact` Workload Identity Federation and `maliev-gitops/3-apps/_legacy-contact-service` do not exist yet. The existing `maliev-contact-service` GitOps path belongs to the new implementation and must not be overwritten by this legacy service.

Tasks:

- server-side validation;
- rate limiting and abuse controls;
- idempotency/duplicate-submission behavior;
- notification handoff;
- conversion-event preservation.

### 3.4 Legacy.Maliev.NotificationService

Consolidate email endpoints.

Status on 2026-07-15:

- public repository created: `https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.NotificationService`;
- extracted from a sanitized source snapshot without copying monorepo Git history or legacy secret-bearing resource files;
- migrated to .NET 10 layered structure: `Api`, `Application`, `Data`, `Domain`, `Tests`;
- legacy routes preserved as `/Emails/info`, `/Emails/manufacturing`, `/Emails/noreply`, `/Emails/support` and their `*-plaintext` variants;
- legacy query/form fields preserved: `to`, `subject`, `body`, `replyTo`, `cc`, `bcc` and `files`;
- legacy combined attachment size limit preserved at 200 MB;
- old Identity, EF, NLog, Swashbuckle and `Maliev.LoggerService` dependencies are not present; Scalar/OpenAPI and built-in logging come from service defaults;
- Brevo provider configuration now uses typed runtime options. `Brevo:ApiKey` must be sourced from `maliev-legacy-secrets`, not source files;
- the service owns no database; no PostgreSQL instance is required for this slice;
- local validation passed: restore, build, 20 tests, format, package vulnerability audit, actionlint and gitleaks;
- main CI passed on commit `16afeb053b2a26e64f2cca3a5627f8d12c4f92bb`;
- main branch protection is enabled with strict `validate / validate`, admin enforcement, linear history, force-push/deletion disabled and conversation resolution;
- GitHub Project #2 was updated: the NotificationService repository item is `Done`, and Wave 3 evidence now lists CatalogService and FileService as the remaining low-risk service extractions;
- deployment is intentionally gated because `legacy-maliev-notification` Workload Identity Federation and `maliev-gitops/3-apps/_legacy-notification-service` do not exist yet. Any existing `maliev-notification-service` GitOps path is reserved for the new implementation and must not be overwritten by this legacy service.

Tasks:

- accept explicit versioned DTOs rather than reading Customer databases;
- bounded queue and retry policy;
- idempotent message identifier;
- provider timeout/circuit breaker;
- template rendering tests;
- PII-safe logs;
- dead-letter/recovery procedure.

### 3.5 Legacy.Maliev.FileService

Status on 2026-07-15:

- public repository created: `https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.FileService`;
- extracted from `Maliev.UploadService` without copying monorepo Git history, legacy configuration or the embedded service-account resource;
- migrated to a .NET 10 layered structure: `Api`, `Application`, `Data`, `Domain`, `Tests`;
- authenticated legacy routes are preserved as `/Uploads` and `/uploads/SignedUrl`, including multipart field `files`, all query names, the optional custom path, 200 MB aggregate limit, `201` location and PascalCase response JSON;
- upload handling is fail closed: private GCS quarantine, complete-file ClamAV INSTREAM scan, clean-only promotion, metadata commit and then signed URL;
- malware, scanner timeout, scanner error and unknown scanner responses cannot create clean metadata or signed URLs; traversal and unapproved buckets are rejected;
- GCS uses Application Default Credentials/Workload Identity with no public ACL or credential file; signed URLs require clean `Upload` metadata and are capped at seven days;
- PostgreSQL mapping preserves the legacy `Upload` table, `ID`, field lengths and timestamps, and the initial migration creates no custom `xmin` column;
- the initial migration passed against a disposable PostgreSQL 18 Testcontainers instance without contacting or altering source SQL Server or existing GCS objects;
- Redis is intentionally excluded from signed URLs and object authorization so delete/move revocation is immediate;
- local validation passed: zero-warning build, 28 tests, format verification, package vulnerability audit and gitleaks;
- main CI passed on commit `b7f041b4c70546e2f4600feb3a7d202a5c8739b3`: `https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.FileService/actions/runs/29387056859`;
- main is public and protected with strict `validate / validate`, admin enforcement, linear history, force-push/deletion disabled and conversation resolution;
- GitHub Project #2 marks the FileService item `Done`, contract `Compatible`, environment `CI`, with commit/run/database/deployment evidence;
- deployment is intentionally gated on dedicated `legacy-maliev-file` WIF, `maliev-gitops/3-apps/_legacy-file-service`, resource-bounded ClamAV, GCS quarantine lifecycle and `legacy-postgres-file` parity/cutover gates in the existing cluster and `maliev-legacy` namespace. No new node pool or Cloud SQL is permitted.

Tasks:

- integrate the extracted service into `Legacy.Maliev.AppHost` with a local ClamAV/GCS-emulator-compatible development boundary;
- add GitOps manifests only after dedicated WIF and migration parity gates exist;
- run an artifact-backed historical `Upload` row/object reconciliation and cutover rehearsal;
- validate upload, move, delete and signed-read flows through Legacy.Maliev.Web and Legacy.Maliev.Intranet.

Exit gate: all five services independently deploy and old deployments can be rolled back without data repair.

## Wave 4: customer, employee and procurement

### 4.1 Legacy.Maliev.CustomerService

- customer/address contract snapshots;
- remove identity DB access;
- route identity operations to AuthService;
- cache user-scoped reads safely;
- invalidate after writes;
- test authorization ownership boundaries;
- verify Web consumer flow.

Extraction completion evidence (2026-07-15):

- public repository: `https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.CustomerService`;
- .NET 10 layers preserve the 20 customer, address, company, email and identity-compatibility routes, PascalCase/null-omission JSON, legacy pagination fields and sort values;
- `CustomerIdentity` stays AuthService-owned; customer identity DTOs exclude credential secrets and credential validation no longer permits anonymous account enumeration;
- PostgreSQL preserves `Customer`, `Company` and `Address` table, column, index and constraint names; source SQL Server remains untouched;
- Redis caches authorized customer-by-ID projections, fails open to PostgreSQL and invalidates all customer projections affected by customer, address or company writes;
- local validation passed: zero-warning Release build, 28 tests including a PostgreSQL 18 migration/behavior test, format verification, package vulnerability audit and gitleaks history scan;
- main CI passed on commit `7808667a3b4560e4027f0a7f0905b644afc70b57`: `https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.CustomerService/actions/runs/29388391366`;
- public `main` is protected with strict `validate / validate`, admin enforcement, one approval, linear history and force-push/deletion disabled;
- GitHub Project #2 marks the CustomerService item `Done`, contract `Compatible`, environment `CI`, with commit/run/database/deployment evidence;
- deployment remains gated on the AuthService legacy customer-identity adapter, dedicated `legacy-maliev-customer` WIF and GitOps path, data parity/rollback evidence and migration of the Intranet password-in-route caller. Deployment remains in the existing cluster and `maliev-legacy` namespace with no new node pool or Cloud SQL.

### 4.2 Legacy.Maliev.EmployeeService

- employee/signature contract snapshots;
- remove employee identity DB access;
- route identity operations to AuthService;
- validate staff-role policies;
- verify Intranet consumer flow.

Extraction completion evidence (2026-07-15):

- public repository: `https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.EmployeeService`;
- .NET 10 layers preserve 24 employee, address, role, signature and identity-compatibility actions, PascalCase/null-omission JSON, legacy pagination fields and four sort values;
- `EmployeeIdentity` stays AuthService-owned; safe identity DTOs exclude credential/recovery secrets and credential validation is no longer an anonymous account oracle;
- PostgreSQL preserves `Employee`, `Address`, `Role` and `SignatureImageFile` table, column, length and FK names; signature records retain GCS bucket/object metadata only and source SQL Server remains untouched;
- Redis caches authorized employee-by-ID projections, fails open to PostgreSQL and invalidates projections affected by employee, address or role changes;
- local validation passed: zero-warning Release build, 28 tests including a PostgreSQL 18 migration/behavior test, format verification, package vulnerability audit and gitleaks history scan;
- main CI passed on commit `bfc72cf1fe8188e64a2c9bcf8cf6fae039a14edc`: `https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.EmployeeService/actions/runs/29389143865`;
- public `main` is protected with strict `validate / validate`, admin enforcement, one approval, linear history and force-push/deletion disabled;
- GitHub Project #2 marks the EmployeeService item `Done`, contract `Compatible`, environment `CI`, with commit/run/database/deployment evidence;
- deployment remains gated on the AuthService employee-identity adapter, dedicated `legacy-maliev-employee` WIF and GitOps path, employee/signature parity and rollback evidence and migration of the Intranet password-in-route caller. Deployment remains in the existing cluster and `maliev-legacy` namespace with no new node pool or Cloud SQL.

### 4.3 Legacy.Maliev.ProcurementService

- consolidate Supplier and PurchaseOrder;
- preserve supplier/material associations without cross-DB queries;
- replace cross-domain joins with application composition or snapshots;
- verify purchase-order PDF input contract;
- test write idempotency and concurrency.

Extraction completion evidence (2026-07-15):

- public repository: `https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.ProcurementService`;
- .NET 10 layers preserve all 30 supplier, supplier-address, purchase-order, purchase-order-address, order-item and file-metadata actions, PascalCase/null-omission JSON, named routes, pagination and sort values;
- one deployable service owns two isolated PostgreSQL databases on the planned `legacy-postgres-procurement` cluster: `Supplier` retains `Supplier` plus its `Address1`/`Address2` table, while `PurchaseOrder` retains `PurchaseOrder`, its incompatible `AddressLine1`/`AddressLine2` table, `OrderItem` and `PurchaseOrderFile`;
- `SupplierID` and `EmployeeID` remain scalar external references, no cross-database FK or direct Material/Accounting access was introduced, and source SQL Server remains untouched;
- purchase-order files retain Google Cloud Storage bucket/object metadata only for ADC/Workload Identity access;
- Redis provides fail-open authorized read caching and SHA-256-keyed 24-hour create idempotency; `ModifiedDate` concurrency rejects stale purchase-order and order-item writes without altering legacy columns;
- local validation passed: zero-warning Release build, 36 tests including PostgreSQL 18 migrations for both databases, computed subtotal and stale-write behavior, format verification, package vulnerability audit and gitleaks history scan;
- main CI passed on commit `3a3590482cbff697a7187873b7a57c44ce6d758e`: `https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.ProcurementService/actions/runs/29390435158`;
- public `main` is protected with strict `validate / validate`, admin enforcement, one approval, conversation resolution, linear history and force-push/deletion disabled;
- GitHub Project #2 marks the ProcurementService item and Wave 4 `Done`, contract `Compatible`, environment `CI`, with repository, commit, run, database and cutover evidence;
- deployment remains gated on repeatable parity/rollback artifacts for both databases, GCS reconciliation, Web/Intranet/PDF consumer validation, dedicated `legacy-maliev-procurement` WIF and GitOps manifests. Deployment remains in the existing cluster and `maliev-legacy` namespace with no new node pool or Cloud SQL.

Exit gate: Web and Intranet no longer reference legacy identity DbContexts, and procurement has no direct Material/Accounting database access.

## Wave 5: transactional core

### 5.1 Legacy.Maliev.QuotationService

- merge Quotation and QuotationRequest;
- preserve files, statistics, withholding-tax behavior and customer lookup shape;
- make Customer/Material dependencies explicit clients;
- test decimal/currency calculations with golden cases;
- add idempotency to externally retried writes;
- capture document-rendering snapshot DTO.

Extraction completion evidence (2026-07-15):

- public repository: `https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.QuotationService`;
- .NET 10 layers merge the two APIs while preserving 33 controller actions, 34 route templates, PascalCase/null-omission JSON, named routes, six-value sort enums and pagination fields;
- the planned `legacy-postgres-quotation` cluster retains two isolated databases: `Quotation` owns `Quotation`, `OrderItem`, `QuotationFile` and `QuotationHasOrder`; `QuotationRequest` owns `Request` and `RequestFile`;
- PostgreSQL preserves legacy names and `numeric(18,2)` behavior, including database-computed line `Subtotal` and quotation `QuotedAmount`; source SQL Server remains untouched;
- golden tests preserve the historical withholding-tax date boundaries and unrounded decimal behavior; expiry transitions are atomic and statistics retain accepted/declined/open semantics;
- `QuotationDocumentSnapshot` supplies quotation, line and GCS metadata to the future QuestPDF renderer without Customer, Material, Order or Accounting database access; external IDs remain scalar references;
- Redis provides fail-open authorized read caching and SHA-256-keyed 24-hour create idempotency; `ModifiedDate` concurrency rejects stale quotation, line and request writes without adding source columns;
- embedded legacy SQL/NLog credentials and database logging were not copied; GCS rows retain bucket/object metadata only for ADC/Workload Identity access;
- local validation passed: zero-warning Release build, 33 tests including PostgreSQL 18 migrations/behavior for both databases, format verification, package vulnerability audit and gitleaks history scan;
- main CI passed on commit `70527696f91370f711e048f9d125fe13ad69d908`: `https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.QuotationService/actions/runs/29391224452`;
- public `main` is protected with strict `validate / validate`, admin enforcement, one approval, conversation resolution, linear history and force-push/deletion disabled;
- GitHub Project #2 marks the QuotationService item `Done`, contract `Compatible`, environment `CI`, with repository, run, database and cutover evidence; Wave 5 remains in progress for OrderService and AccountingService;
- deployment remains gated on repeatable parity/rollback artifacts for both databases, golden QuestPDF comparison, GCS reconciliation, Web/Intranet consumer tests, dedicated WIF and GitOps manifests in the existing cluster and `maliev-legacy` namespace. No new node pool or Cloud SQL is permitted.

### 5.2 Legacy.Maliev.OrderService

- merge Order and OrderStatus;
- preserve pending/by-customer/file behavior;
- enforce customer ownership and staff policies;
- eliminate cross-service DB reads;
- test concurrent status transitions;
- document permitted state transitions.

Extraction completion evidence (2026-07-15):

- public repository: `https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.OrderService`;
- .NET 10 layers merge Order and OrderStatus while preserving 55 actions, 56 route templates, pending/customer filtering, all 14 named status shortcuts, named routes, pagination and sort values;
- planned `legacy-postgres-order` retains two isolated databases: `Order` owns `Order`, `OrderFile`, `Process`, `Category`, `FileFormat`; `OrderStatus` owns `OrderStatus`, `OrderStatusHasPossibleStatus`, `OrderStatusHistory`;
- PostgreSQL preserves names, precision, FKs and computed `Remaining`, discounted `Subtotal` and `Turnaround`; source SQL Server remains untouched;
- status transitions are serialized, validate the preserved possible-status graph, reject illegal/concurrent moves and retain ordered/latest history behavior;
- external domain IDs remain scalar references, GCS rows retain bucket/object metadata only, and embedded SQL/NLog credentials were not copied;
- Redis provides fail-open authorized read caching and SHA-256-keyed idempotency; `ModifiedDate` concurrency rejects stale order/history writes without source schema changes;
- local validation passed: zero-warning Release build, 27 tests including PostgreSQL 18 behavior for both databases, format verification, vulnerability audit and gitleaks;
- main CI passed on `1d9c7835ecc6648fd4bb2f8ddc121055ed79597b`: `https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.OrderService/actions/runs/29391895822`;
- public `main` has strict `validate / validate`, admin enforcement, one approval, conversation resolution, linear history and force-push/deletion disabled; Project #2 is `Done / Compatible / CI`;
- deployment remains gated on parity/rollback for both DBs, status seed/graph verification, GCS reconciliation, Web/Intranet ownership/workflow tests, dedicated WIF and GitOps in existing GKE `maliev-legacy`. No new node pool or Cloud SQL.

### 5.3 Legacy.Maliev.AccountingService

- merge old Payment records, Invoice and Receipt;
- do not execute a payment provider;
- preserve financial data and JSON behavior;
- centralize decimal/rounding/tax invariants;
- verify quotation/invoice/receipt relationships through APIs or immutable snapshots;
- test duplicate accounting writes;
- document reconciliation and recovery.

Extraction completion evidence (2026-07-15):

- public repository: `https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.AccountingService`;
- .NET 10 layers merge Payment records, Invoice and Receipt while preserving 66 controller actions and 67 route templates across 13 authenticated, permission-gated controllers with PascalCase/null-omission JSON and Scalar/OpenAPI;
- planned `legacy-postgres-accounting` retains three isolated databases: `Payment` owns historical payments, accounts, directions, methods, types and files; `Invoice` owns invoices, invoice files and its `OrderItem`; `Receipt` owns receipts, receipt files and its separate `OrderItem`;
- PostgreSQL preserves legacy table/column/FK names and decimal behavior, including database-computed invoice/receipt line `Subtotal` and receipt `AmountPaid`; source SQL Server remains untouched;
- historical summaries retain current/previous, delta and currency behavior plus yearly daily income/expense details; all provider SDKs and execution paths are absent, leaving future Omise/Opn execution to the new `Maliev.PaymentService`;
- Customer, Employee, Currency and cross-document IDs remain scalar external references, and GCS rows retain bucket/object metadata for ADC/Workload Identity without service-account keys;
- Redis provides fail-open authorized entity caching and SHA-256-keyed 24-hour create idempotency; conditional `ModifiedDate` updates reject stale financial writes without adding source columns;
- local validation passed: zero-warning Release build, 16 tests including PostgreSQL 18 migrations and financial behavior across all three databases, format verification, vulnerability audit, gitleaks and live 103 KB OpenAPI generation;
- main CI passed on `c0f38c0a5a0505abd13b9250b25c326a833105fe`: `https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.AccountingService/actions/runs/29393253021`;
- public `main` has strict `validate / validate`, admin enforcement, one approval, conversation resolution, linear history and force-push/deletion disabled; Project #2 marks AccountingService and Wave 5 `Done`, contract `Compatible`, environment `CI`;
- deployment remains gated on repeatable row/financial parity, reconciliation, rollback, GCS and quote-to-receipt consumer evidence, dedicated WIF and GitOps in existing GKE `maliev-legacy`. No new node pool, Cloud SQL or paid service is permitted.

Exit gate: a synthetic end-to-end quote-to-order-to-invoice-to-receipt flow matches legacy behavior without shared database access.

## Wave 6: QuestPDF documents

Repository: Legacy.Maliev.DocumentService.

### 6.1 Capture baselines

Generate iText fixtures for every document type and edge case defined in the architecture.

### 6.2 Implement QuestPDF renderers

- embed approved Thai-capable fonts;
- separate document model from persistence models;
- accept immutable render snapshots;
- preserve page size, margins, headers, footers, tables, images and totals;
- keep deterministic metadata for visual comparison.

### 6.3 Parity runner

For each fixture compare:

- extracted semantic text;
- page number and boxes;
- fonts and images;
- geometry;
- fixed-DPI render with defined perceptual threshold.

### 6.4 Shadow deployment

Render QuestPDF alongside authoritative iText without returning the new file. Record mismatch metrics. Manually approve representative Thai documents.

Extraction completion evidence (2026-07-15):

- public repository: `https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.DocumentService`;
- .NET 10 Domain, Application, Rendering and API layers preserve the five authenticated `POST /Pdfs/*` routes and PascalCase/null-omission wire shape while keeping the service stateless and database-free;
- QuestPDF 2026 with embedded Noto Sans and Noto Sans Thai replaces iText; QuestPDF and SIL OFL license notices are committed, Thai combining marks were raster-reviewed, and production code contains neither iText nor Sarabun;
- 22 immutable iText PDFs freeze six invoice, seven quotation, five receipt, three purchase-order and one order-label variants with SHA-256, semantic text, page count and page geometry metadata;
- 24 automated tests cover all legacy routes, page geometry, calculations, two-copy receipts, deterministic clock behavior, Thai glyph clusters, font policy and normalized section-anchor visual parity while bank-transfer content remains;
- local validation passed with a zero-warning Release build, format verification, clean vulnerability and gitleaks audits, a successful non-root Docker build, and container liveness/OpenAPI responses of 200 exposing all five PDF routes;
- main CI passed on `b7492444e0a3960778ab19d554a6bc17158cfd80`: `https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.DocumentService/actions/runs/29397542261`;
- public `main` has strict `validate / validate`, admin enforcement, one approval, conversation resolution, linear history and force-push/deletion disabled; Project #2 marks DocumentService and Wave 6 `Done`, contract `Compatible`, environment `CI`;
- production deployment is deferred until the complete migration plan is ready. The eventual workload uses only the existing GKE cluster and `maliev-legacy` namespace and needs no database, Redis allocation, node pool, Cloud SQL or paid service.

Exit gate: license eligibility documented, automated parity passes, manual Thai review passes, rollback flag tested.

## Wave 7: frontends and Google systems

### 7.1 Legacy.Maliev.Web

- remove all direct domain DbContexts;
- use typed service clients through BFF boundaries;
- preserve routes, accessibility and browser behavior;
- move barcode generation client-side only if still required;
- retain Omise as future unintegrated work;
- migrate GTM/GA4/Ads/Search Console implementation and tests.

### 7.2 Legacy.Maliev.Intranet

- remove direct employee/domain DbContexts;
- use service clients and server-side session handling;
- preserve staff workflows and authorization;
- add downstream failure UX and correlation IDs.

### 7.3 Google validation

- inventory GTM container and tag destinations;
- eliminate unsafe/unnecessary Custom HTML;
- confirm consent defaults before tag firing;
- verify clean network requests for GA4 and Ads;
- validate conversion events exactly once;
- verify Search Console property, sitemap, canonical and Safe Browsing;
- publish clean GTM version;
- wait for rescan and record result.

Exit gate: browser tests and Google diagnostics pass in production, with no malware flag and no duplicate/missing conversion events.

## Wave 8: retirement and optimization

### 8.1 Remove superseded deployments

After soak and rollback windows:

- remove LoggerService;
- remove PredictionService;
- remove barcode backend if present;
- stop iText path;
- disable old per-controller services now served by bounded contexts.

### 8.2 Archive state

- verify Log DB is read-only;
- verify prediction/Hangfire/ML stores are archived;
- record retention and restore procedure;
- retain required audit/financial data;
- remove unused credentials and IAM grants.

### 8.3 Resource tuning

- compare final metrics to Wave 0;
- tune CPU/memory requests and limits;
- tune cache TTLs from observed hit rate;
- tune connection pools and HTTP concurrency;
- validate cluster headroom for new MALIEV services;
- document final cost and resource change.

### 8.4 Closeout

- confirm all public repos have branch rules, Dependabot and runbooks;
- confirm project evidence links are complete;
- confirm every legacy route is owned or deliberately retired;
- confirm every database has an owner/archive state;
- perform final backup and rollback audit;
- close project only after production observation period.

## Repository creation checklist

Apply to each Legacy.Maliev.* repository:

- public visibility;
- exact approved name and description;
- main as default branch;
- sanitized initial commit and MIGRATION_PROVENANCE.md;
- LICENSE decision recorded;
- README with purpose and boundaries;
- SECURITY.md without sensitive disclosure details;
- CODEOWNERS or ownership statement;
- .editorconfig and Directory.Build.props;
- locked dependency restore;
- Dependabot for NuGet, Docker and Actions;
- least-privilege Actions permissions;
- OIDC deployment environment;
- environment protections where available;
- required status checks;
- force-push/deletion blocked;
- issue templates that do not solicit secrets;
- vulnerability reporting instructions;
- release/runbook documentation.

## Per-cutover evidence template

- Service and repository:
- Source commit:
- Container digest:
- GitOps pull request and commit:
- Contract report:
- Schema fingerprint comparison:
- Security reports:
- Performance comparison:
- Canary 5%:
- Canary 25%:
- Canary 50%:
- Production 100%:
- Rollback rehearsal:
- Dashboard:
- Open risks:
- Approval:
- Old deployment shutdown time:

## Project backlog seed

Create one private epic item for every architecture workstream and one service item for every target repository. Each service item links its public implementation issues but holds sensitive evidence only in the private item.

Required initial private items:

- Confirm QuestPDF license eligibility.
- Rotate all credentials discovered in monorepo history.
- Restore and fingerprint 2026-07-14 backup.
- Capture complete endpoint/JSON/auth baseline.
- Create sanitized extraction automation.
- Configure GitHub-to-GCP Workload Identity Federation.
- Define maliev-legacy-secrets JSON schema and rotation runbook.
- Define contract mismatch and canary rollback thresholds.
- Audit GTM destinations and malware status.
- Establish Wave 0 performance baseline.
- Create each approved public repository.
- Execute each wave exit review.
