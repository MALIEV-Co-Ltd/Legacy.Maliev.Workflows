# Controlled application handoff policy

`application_handoff_policy.py` is a reusable policy library with no CLI, deployment client, network access, native subprocess or default live executor. Call `run_handoff(application, exact_source_commit, image_digest, injected_tool, require_read_only_startup=False)` only through a separately reviewed caller boundary.

The injected boundary receives one approved `STEPS` operation and a structured request. It returns exactly `exitCode` (a nonnegative integer) and `receipt` (a JSON-compatible dictionary bounded to 16 KiB). Nonzero exit codes propagate in `HandoffFailure.exit_code`; public failure messages contain only the reviewed step. A callback exception normalizes to a redacted failure. There is no operation for provider/IAM/database/configuration migration or arbitrary resource mutation.

Thrown callback exceptions, including an instance of this library's own public
exception class, normalize to the requested step and exit 1. Only the structured
response's bounded nonnegative exit code is trusted for propagation; callback-
supplied exception messages, steps and codes cannot bypass that boundary.

The policy binds the caller's immutable source and image digest before creating a workload. It snapshots a healthy original and service identity, preserves its bounded desired replica count in owned standby green, uses service UID/resource-version/ports and exact target deployment UID in selector compare-and-swap requests, observes public health/endpoints and process routing for 180 seconds, rechecks surge capacity, and then changes only the canonical application. Exact owned rollout settings are min-ready 90, drain 60, termination 90, surge 1 and unavailable 0.

This adapter's service revision receipt contract is a positive canonical decimal token, bounded by the complete 16 KiB receipt rather than a fixed bit/digit width. It passes the exact captured token back in CAS requests and compares successful same-Service numeric receipts by digit length and lexicographic order, without integer conversion. It is not a universal Kubernetes resource-version adapter: callers targeting an opaque-version contract must supply a separately reviewed adapter rather than infer numeric ordering. Numeric ordering here never compares different resources or substitutes for UID/ports/selector fences.

For a Kubernetes consumer, the reviewed boundary must bind these operations to the same `core/v1` Service and establish the target API's numeric revision contract. Current Kubernetes documentation includes numeric same-kind ordering in 1.35+ conformance and explicitly prohibits assuming a fixed integer width: [resource versions](https://kubernetes.io/docs/reference/using-api/api-concepts/#resource-versions). This controlled candidate selects no live cluster and observes no API version. Older opaque-version compatibility and any extension API behavior remain separate caller review obligations. The 16 KiB envelope is this tool's receipt bound, not a claim about the server's resource-version width. Source, image, UID, selector-target and proof request/receipt keys are unchanged by this compatibility clarification.

Capacity receipts represent application replica-equivalent headroom and a bound reservation identity. The original desired count must be an integer from 1 through 10. For a baseline of N replicas, green creation and every owned green/canonical/fallback proof require N replicas. The reservation is N+1 temporary slots (green plus one canonical surge), with peak 2N+1 replicas; the recheck retains that exact reservation and requires at least one surge slot still available. A real caller must compute that headroom from schedulable resources and matching application requests; the policy does not inspect a scheduler or establish infrastructure capacity. Insufficient or unavailable proof cannot authorize scaling down the healthy original or changing infrastructure.

Each `GREEN_HEALTH`, `CANONICAL_HEALTH` and `FINAL_HEALTH` request includes the exact expected `deploymentUid`. The receipt must return that same UID and Boolean `processRouteVerified=true`, in addition to the approved image, public health, endpoints and bounded observation duration. Green health binds the owned green UID; canonical and final health bind the unchanged baseline UID. Digest equality alone cannot admit public traffic from another process. Missing, false, string-valued or foreign-UID route proof rejects at that actual gate and retains the established pre/post-mutation fallback rules. This tightens the injected boundary: existing callers must supply both new route fields and the baseline-sized green/capacity receipts; no live caller adoption is inferred.

Before canonical mutation, rollback can restore the original selector only while the original deployment UID/image/healthy counts/settings and service UID/ports remain unchanged. The canonical-mutation marker is set before invoking the operation because a failed response may follow a partial application. After that point the policy never requests the former image: it retains or routes to the independently proven owned green. A foreign selector target, changed ownership, missing/deleted green or failed fallback proof blocks fallback instead of changing another resource. Failure evidence retains owned green/run identity; automatic failure cleanup is deliberately not inferred.

An unhealthy canonical backend after mutation does not prevent routing back to a
separately proven healthy owned green. This failure-only read still requires the
original canonical UID and desired replica count, a structurally valid zero-to-
desired readiness count, either the original or approved immutable image, and
the unchanged Service UID/ports/recognized selector target. Foreign canonical
image/UID/replica changes block fallback. All initial and normal-path health
requirements remain strict, and the original operation failure code is preserved.

Success drains only the exact owned green, verifies no remaining processes, checks final canonical/public state and releases its exact reservation. Receipts always keep `runtimeAccepted=false` and `consumerAdoptionAccepted=false`. Injected proof claims are controlled orchestration evidence, not actual cluster/image/process/endpoint observations.

The controlled tests independently simulate deployment, service, green and capacity state. They fault every operation, assert original exit propagation, preserve healthy backends, exercise pre/post-canonical rollback differences, verify exact selector targets and rollout settings, block concurrency/foreign ownership, reject insufficient observation and required read-only proof, and check callback redaction and oversized receipts.

This is a policy adaptation of original source commits `1ec9ef70db2010936964b51a741bf282133298fa`, `44b1420029793e6acd914582364b9d38c3944d78` and `aa73f4bb0d633b2524a8c030a985d4fac6fbc746`. The integrated baseline-capacity and public process-route behavior also adapts the bounded logical requirements of `c9c91b556d36301bad10e1b02c22528443f51287` and `3f3ef910498d4266281ff0ee841466c4f65b5fb5`. It does not restore their direct deployment scripts or establish whole-source closure. Each owner retains separate exact caller/manifests/runtime acceptance. Shared publisher guards or scanner pins do not close those source obligations.

This library's application label is a correlation value, not authorization to
release an artifact. The original case-sensitive artifact allowlist, namespace,
context, provider identity and resource mutation admission remain separately
required at a reviewed caller boundary. There is no consumer adoption in this
slice and no claim that every original release guard has been migrated.
