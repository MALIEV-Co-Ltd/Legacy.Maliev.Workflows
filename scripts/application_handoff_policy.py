"""Application handoff policy with injected tools only; no live executor or CLI."""
import copy
import json
import re
import uuid
import importlib.util
from pathlib import Path

STEPS = frozenset({"SNAPSHOT", "VERIFY_SOURCE", "VERIFY_IMAGE", "RESERVE_CAPACITY", "RECHECK_CAPACITY", "CREATE_GREEN", "VERIFY_GREEN", "BEFORE_FIRST_SELECTOR", "READ_CURRENT", "ROUTE_GREEN", "GREEN_HEALTH", "MUTATE_CANONICAL", "VERIFY_CANONICAL", "ROUTE_CANONICAL", "CANONICAL_HEALTH", "DRAIN_GREEN", "FINAL_HEALTH", "RELEASE_CAPACITY", "ROLLBACK_SELECTOR", "VERIFY_FALLBACK", "FALLBACK_SELECTOR"})
ROLLOUT = dict(minReadySeconds=90, drainSeconds=60, terminationGracePeriodSeconds=90, maxSurge=1, maxUnavailable=0)


class HandoffFailure(RuntimeError):
    def __init__(self, step, exit_code=1):
        super().__init__("Application handoff rejected at " + step)
        self.step = step
        self.exit_code = exit_code
        self.canonical_mutation_started = False
        self.fallback_blocked = False
        self.green_uid = None
        self.run_id = None


def require(condition, step):
    if not condition:
        raise HandoffFailure(step)


def valid_uid(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", value) is not None


def deployment_shape(deployment, step):
    require(isinstance(deployment, dict) and valid_uid(deployment.get("uid")), step)
    count = deployment.get("replicas")
    require(type(count) is int and 1 <= count <= 10, step)
    require(type(deployment.get("ready")) is int and type(deployment.get("available")) is int and 0 <= deployment["ready"] <= count and 0 <= deployment["available"] <= count, step)
    require(isinstance(deployment.get("imageDigest"), str) and re.fullmatch(r"sha256:[0-9a-f]{64}", deployment["imageDigest"]), step)


def healthy(deployment, step):
    deployment_shape(deployment, step)
    require(deployment["ready"] == deployment["replicas"] and deployment["available"] == deployment["replicas"], step)


def service_shape(service, step):
    require(isinstance(service, dict) and valid_uid(service.get("uid")), step)
    require(isinstance(service.get("resourceVersion"), str) and re.fullmatch(r"[1-9][0-9]*", service["resourceVersion"]), step)
    require(service.get("selector") in ("original", "green") and isinstance(service.get("portsSignature"), str) and 0 < len(service["portsSignature"]) <= 4096, step)
    require(valid_uid(service.get("selectorUid")), step)


def run_handoff(application, source_commit, image_digest, tool, *, require_read_only_startup=False, startup_contract=None, green_contract=None):
    """Execute reviewed logical operations through a caller-supplied boundary.

    This module cannot attest a real cluster, scheduler, image or consumer adoption.
    On failure it preserves the original failure code and owned fallback identity.
    """
    require(isinstance(application, str) and re.fullmatch(r"Legacy\.Maliev\.[A-Za-z]{1,40}", application), "SNAPSHOT")
    require(isinstance(source_commit, str) and re.fullmatch(r"[0-9a-f]{40}", source_commit), "VERIFY_SOURCE")
    require(isinstance(image_digest, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", image_digest), "VERIFY_IMAGE")
    require(callable(tool) and type(require_read_only_startup) is bool, "SNAPSHOT")
    green_arguments = None
    green_metadata_plan = None
    green_metadata_baseline = None
    if green_contract is not None:
        try:
            spec = importlib.util.spec_from_file_location("legacy_workflows_green_metadata", Path(__file__).resolve().with_name("green_metadata.py"))
            require(spec is not None and spec.loader is not None, "VERIFY_GREEN_SOURCE")
            green_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(green_module)
            MetadataRejected = green_module.MetadataRejected
            decode_green_metadata = green_module.decode_green_metadata
            plan_green_metadata = green_module.plan_green_metadata
            verify_green_metadata = green_module.verify_green_metadata
            green_arguments = green_module.contract_shape(application, green_contract)
        except Exception:
            raise HandoffFailure("VERIFY_GREEN_SOURCE") from None
    startup_plan = None
    startup_arguments = None
    if startup_contract is not None:
        require(type(startup_contract) is dict and set(startup_contract) == {"target_application", "source_sha", "endpoint", "source_probe"}, "VERIFY_STARTUP_SOURCE")
        # Existing callers load this file directly with spec_from_file_location
        # and do not place scripts/ on sys.path. Bind only the trusted sibling
        # module; leave default callers free of the optional module dependency.
        try:
            spec = importlib.util.spec_from_file_location("legacy_workflows_startup_protection", Path(__file__).resolve().with_name("startup_protection.py"))
            require(spec is not None and spec.loader is not None, "VERIFY_STARTUP_SOURCE")
            startup_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(startup_module)
            StartupRejected = startup_module.StartupRejected
            plan_startup_update = startup_module.plan_startup_update
            verify_startup_readback = startup_module.verify_startup_readback
        except Exception:
            raise HandoffFailure("VERIFY_STARTUP_SOURCE") from None
        try:
            admitted = plan_startup_update(application=application, current_probe=None, rollout=ROLLOUT, **startup_contract)
            if admitted["changed"]:
                startup_arguments = copy.deepcopy(startup_contract)
        except StartupRejected:
            raise HandoffFailure("VERIFY_STARTUP_SOURCE") from None
    run_id = uuid.uuid4().hex
    context = dict(application=application, sourceCommit=source_commit, imageDigest=image_digest, runId=run_id)
    canonical_started = False
    green = None
    baseline = None
    original_service = None
    reservation = None

    def invoke(step, **arguments):
        require(step in STEPS, "SNAPSHOT")
        request = copy.deepcopy(dict(context, **arguments))
        try:
            response = tool(step, request)
        except Exception:
            # Callback failures never carry trusted phase/exit metadata, even
            # when a caller throws this library's public exception class.
            raise HandoffFailure(step) from None
        try:
            require(isinstance(response, dict) and set(response) == {"exitCode", "receipt"}, step)
            code = response["exitCode"]
            require(type(code) is int and 0 <= code <= 2147483647, step)
            if code:
                raise HandoffFailure(step, code)
            receipt = response["receipt"]
            require(isinstance(receipt, dict) and len(json.dumps(receipt, allow_nan=False).encode("utf-8")) <= 16384, step)
            return copy.deepcopy(receipt)
        except HandoffFailure:
            raise
        except Exception:
            raise HandoffFailure(step) from None

    def current(step="READ_CURRENT", expected_selector=None, expected_image=None, require_healthy=True):
        receipt = invoke(step)
        deployment = receipt.get("deployment")
        service = receipt.get("service")
        if require_healthy:
            healthy(deployment, step)
        else:
            deployment_shape(deployment, step)
            require(canonical_started and baseline is not None and deployment["imageDigest"] in (baseline["imageDigest"], image_digest), step)
        service_shape(service, step)
        if green_arguments is not None and require_healthy:
            require("greenMetadata" in deployment, step)
            try:
                deployment["greenMetadata"] = decode_green_metadata(deployment["greenMetadata"])
                if green_metadata_baseline is not None and not canonical_started:
                    verify_green_metadata(green_metadata_baseline, deployment["greenMetadata"])
            except MetadataRejected:
                raise HandoffFailure(step) from None
        if startup_arguments is not None and require_healthy:
            require("startupProbe" in deployment, step)
            if startup_plan is not None:
                stage = "canonical" if canonical_started else "preflight"
                try:
                    verify_startup_readback(startup_plan, deployment["startupProbe"], stage)
                except StartupRejected:
                    raise HandoffFailure(step) from None
        if baseline is not None:
            require(deployment["uid"] == baseline["uid"] and deployment["replicas"] == baseline["replicas"], step)
            require(service["uid"] == original_service["uid"] and service["portsSignature"] == original_service["portsSignature"], step)
            if service["selector"] == "original":
                require(service["selectorUid"] == baseline["uid"], step)
            else:
                require(green is not None and service["selectorUid"] == green["uid"], step)
        if expected_selector is not None:
            require(service["selector"] == expected_selector, step)
            target_uid = green["uid"] if expected_selector == "green" else deployment["uid"]
            require(service["selectorUid"] == target_uid, step)
        if expected_image is not None:
            require(deployment["imageDigest"] == expected_image, step)
            if expected_image == baseline["imageDigest"] and not canonical_started:
                require(deployment.get("settingsSignature") == baseline.get("settingsSignature"), step)
        return deployment, service

    def route(step, service, selector):
        target_uid = green["uid"] if selector == "green" else baseline["uid"]
        receipt = invoke(step, service=service, selector=selector, targetDeploymentUid=target_uid)
        service_shape(receipt, step)
        require(receipt["uid"] == service["uid"] and receipt["portsSignature"] == service["portsSignature"] and receipt["selector"] == selector, step)
        # Numeric same-Service contract; avoid machine/Python integer width limits.
        before_version = service["resourceVersion"]
        after_version = receipt["resourceVersion"]
        require((len(after_version), after_version) > (len(before_version), before_version), step)
        require(receipt["selectorUid"] == target_uid, step)
        return receipt

    def prove(step, target):
        receipt = invoke(step, deploymentUid=target["uid"])
        healthy(receipt, step)
        require(receipt["uid"] == target["uid"] and receipt["imageDigest"] == image_digest and receipt.get("processVerified") is True, step)
        require(receipt["replicas"] == baseline["replicas"], step)
        settings = receipt.get("rollout")
        require(isinstance(settings, dict) and settings == ROLLOUT and all(type(v) is int for v in settings.values()), step)
        if target is green:
            require(receipt.get("runId") == run_id and receipt.get("standbyVerified") is True, step)
            if green_metadata_plan is not None:
                require("greenMetadataPlan" in receipt, step)
                try:
                    verify_green_metadata(green_metadata_plan, receipt["greenMetadataPlan"])
                except MetadataRejected:
                    raise HandoffFailure(step) from None
        if startup_plan is not None:
            require("startupProbe" in receipt, step)
            try:
                verify_startup_readback(startup_plan, receipt["startupProbe"], "canonical" if target is baseline else "green")
            except StartupRejected:
                raise HandoffFailure(step) from None
        if require_read_only_startup:
            require(receipt.get("readOnlyStartupVerified") is True, step)
        return receipt

    def observe(step):
        target = green if step == "GREEN_HEALTH" else baseline
        receipt = invoke(step, minimumSeconds=180, deploymentUid=target["uid"])
        require(receipt.get("imageDigest") == image_digest and receipt.get("publicHealthy") is True and receipt.get("endpointsVerified") is True
                and receipt.get("processRouteVerified") is True and receipt.get("deploymentUid") == target["uid"], step)
        seconds = receipt.get("observedSeconds")
        require(type(seconds) is int and 180 <= seconds <= 3600, step)

    def observe_before_first_selector():
        # Source health gate targets prepared green while public routing is still
        # canonical. No green process-route proof or 180-second window applies yet.
        step = "BEFORE_FIRST_SELECTOR"
        receipt = invoke(step, minimumSeconds=0, deploymentUid=green["uid"])
        require(receipt.get("imageDigest") == image_digest and receipt.get("deploymentUid") == green["uid"]
                and receipt.get("continuousPublicHealthy") is True and receipt.get("endpointsVerified") is True, step)
        seconds = receipt.get("observedSeconds")
        require(type(seconds) is int and 0 <= seconds <= 3600, step)

    try:
        baseline, original_service = current("SNAPSHOT", expected_selector="original")
        if startup_arguments is not None:
            try:
                startup_plan = plan_startup_update(application=application, current_probe=baseline["startupProbe"], rollout=ROLLOUT, **startup_arguments)
            except StartupRejected:
                raise HandoffFailure("SNAPSHOT") from None
        if green_arguments is not None:
            require("greenMetadata" in baseline, "SNAPSHOT")
            if green_arguments["artifact"] == "maliev-materialservice-api":
                require(startup_plan is not None, "SNAPSHOT")
                require_read_only_startup = True
            try:
                green_metadata_baseline = copy.deepcopy(baseline["greenMetadata"])
                green_metadata_plan = plan_green_metadata(green_arguments, green_metadata_baseline, image_digest,
                    startup_probe=startup_plan["desiredProbe"] if startup_plan else None, read_only=require_read_only_startup)
            except MetadataRejected:
                raise HandoffFailure("SNAPSHOT") from None
        require(invoke("VERIFY_SOURCE").get("sourceCommit") == source_commit, "VERIFY_SOURCE")
        image = invoke("VERIFY_IMAGE")
        require(image.get("sourceCommit") == source_commit and image.get("imageDigest") == image_digest and image.get("immutable") is True, "VERIFY_IMAGE")
        temporary_slots = baseline["replicas"] + ROLLOUT["maxSurge"]
        capacity = invoke("RESERVE_CAPACITY", additionalSlots=temporary_slots, peakReplicas=baseline["replicas"] + temporary_slots)
        require(type(capacity.get("availableSlots")) is int and capacity["availableSlots"] >= temporary_slots and type(capacity.get("reservedSlots")) is int and capacity["reservedSlots"] == temporary_slots and valid_uid(capacity.get("reservationId")), "RESERVE_CAPACITY")
        reservation = capacity["reservationId"]
        green = invoke("CREATE_GREEN", reservationId=reservation, replicas=baseline["replicas"], standby=True, rollout=ROLLOUT,
            **({"startupProbe": startup_plan["desiredProbe"]} if startup_plan else {}),
            **({"greenMetadataPlan": green_metadata_plan} if green_metadata_plan else {}))
        require(valid_uid(green.get("uid")) and green.get("uid") != baseline["uid"] and green.get("runId") == run_id and green.get("imageDigest") == image_digest, "CREATE_GREEN")
        if green_metadata_plan is not None:
            require("greenMetadataPlan" in green, "CREATE_GREEN")
            try:
                verify_green_metadata(green_metadata_plan, green["greenMetadataPlan"])
            except MetadataRejected:
                raise HandoffFailure("CREATE_GREEN") from None
        prove("VERIFY_GREEN", green)
        observe_before_first_selector()
        _, service = current(expected_selector="original", expected_image=baseline["imageDigest"])
        route("ROUTE_GREEN", service, "green")
        observe("GREEN_HEALTH")
        capacity = invoke("RECHECK_CAPACITY", reservationId=reservation, additionalSlots=1)
        require(capacity.get("reservationId") == reservation and type(capacity.get("availableSlots")) is int and capacity["availableSlots"] >= 1 and type(capacity.get("reservedSlots")) is int and capacity["reservedSlots"] == temporary_slots, "RECHECK_CAPACITY")
        _, service = current(expected_selector="green", expected_image=baseline["imageDigest"])
        if green_metadata_plan is not None:
            prove("VERIFY_GREEN", green)
        canonical_started = True  # An unsuccessful operation can still have applied.
        invoke("MUTATE_CANONICAL", deploymentUid=baseline["uid"], expectedImage=baseline["imageDigest"], rollout=ROLLOUT, service=service,
            **({"startupProbe": startup_plan["desiredProbe"], "expectedStartupProbe": startup_plan["previousProbe"]} if startup_plan else {}),
            **({"greenDeploymentUid": green["uid"], "expectedGreenMetadataPlan": green_metadata_plan,
                "expectedCanonicalMetadata": green_metadata_baseline, "expectedCanonicalReplicas": baseline["replicas"],
                "expectedGreenReplicas": baseline["replicas"]} if green_metadata_plan else {}))
        prove("VERIFY_CANONICAL", baseline)
        _, service = current(expected_selector="green", expected_image=image_digest)
        route("ROUTE_CANONICAL", service, "original")
        observe("CANONICAL_HEALTH")
        prove("VERIFY_CANONICAL", baseline)
        drained = invoke("DRAIN_GREEN", greenUid=green["uid"], runId=run_id)
        require(drained.get("greenUid") == green["uid"] and type(drained.get("remainingProcesses")) is int and drained["remainingProcesses"] == 0 and drained.get("ownedDeleted") is True, "DRAIN_GREEN")
        green = None
        observe("FINAL_HEALTH")
        current(expected_selector="original", expected_image=image_digest)
        released = invoke("RELEASE_CAPACITY", reservationId=reservation)
        require(released.get("reservationId") == reservation and released.get("released") is True, "RELEASE_CAPACITY")
        return dict(status="CONTROLLED_HANDOFF_COMPLETED", sourceCommit=source_commit, imageDigest=image_digest, runId=run_id, runtimeAccepted=False, consumerAdoptionAccepted=False)
    except HandoffFailure as failure:
        failure.canonical_mutation_started = canonical_started
        if startup_plan is not None:
            failure.startup_rollback_available = True
            failure.previous_startup_probe = copy.deepcopy(startup_plan["previousProbe"])
        failure.green_uid = green.get("uid") if green else None
        failure.run_id = run_id
        if baseline is not None:
            try:
                if canonical_started and green is not None:
                    prove("VERIFY_FALLBACK", green)
                    # The canonical backend can be unhealthy after mutation. Its
                    # identity still fences fallback; the target green must pass
                    # the independent healthy/process/owned proof above.
                    _, service = current(require_healthy=False)
                    if service["selector"] != "green":
                        route("FALLBACK_SELECTOR", service, "green")
                    else:
                        require(service["selectorUid"] == green["uid"], "VERIFY_FALLBACK")
                elif canonical_started:
                    failure.fallback_blocked = True
                elif not canonical_started:
                    _, service = current(expected_image=baseline["imageDigest"])
                    if service["selector"] == "green":
                        route("ROLLBACK_SELECTOR", service, "original")
            except HandoffFailure:
                failure.fallback_blocked = True
        raise failure from None
