"""Selected metadata plan only; caller mappings and physical adapters need review."""
import copy
import json
import math
import re

SOURCE_SHA = "3fd301fe85cd8ca61434569eccb67a369eda47a4"
ARTIFACTS = frozenset("maliev-authservice-api maliev-countryservice-api maliev-currencyservice-api maliev-customerservice-api maliev-emailservice-api maliev-employeeservice-api maliev-intranet maliev-invoiceservice-api maliev-jobservice-api maliev-materialservice-api maliev-messageservice-api maliev-orderservice-api maliev-orderstatusservice-api maliev-paymentservice-api maliev-pdfservice-api maliev-predictionservice-api maliev-purchaseorderservice-api maliev-quotationrequestservice-api maliev-quotationservice-api maliev-receiptservice-api maliev-supplierservice-api maliev-uploadservice-api maliev-web".split())
PROBES = frozenset({"readinessProbe", "livenessProbe", "startupProbe"})
CONTAINER_FIELDS = PROBES | {"ports", "resources", "imagePullPolicy", "securityContext", "envFrom"}
POD_FIELDS = frozenset({"serviceAccountName", "automountServiceAccountToken", "imagePullSecrets", "nodeSelector", "affinity", "tolerations", "securityContext", "dnsPolicy", "restartPolicy", "schedulerName"})
FLAGS = frozenset({"ASPNETCORE_ENVIRONMENT", "DOTNET_ENVIRONMENT", "MALIEV_OBSERVABILITY_STANDBY", "MALIEV_OBSERVABILITY_READ_ONLY_STARTUP"})


class MetadataRejected(ValueError):
    def __init__(self):
        super().__init__("Green metadata contract rejected.")


def require(condition):
    if not condition:
        raise MetadataRejected()


def bounded(value):
    """Reject non-JSON, excessive depth/width/strings before serialization."""
    nodes = 0
    def visit(item, depth=0):
        nonlocal nodes
        nodes += 1
        require(nodes <= 1024 and depth <= 16)
        if type(item) is dict:
            require(len(item) <= 128)
            for key, child in item.items():
                require(type(key) is str and len(key) <= 256)
                visit(child, depth + 1)
        elif type(item) is list:
            require(len(item) <= 128)
            for child in item:
                visit(child, depth + 1)
        elif type(item) is str:
            require(len(item) <= 16384)
        elif type(item) is int:
            require(-2147483648 <= item <= 2147483647)
        elif type(item) is float:
            require(math.isfinite(item))
        else:
            require(item is None or type(item) is bool)
    visit(value)
    try:
        text = json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":"), ensure_ascii=False)
        require(len(text.encode("utf-8")) <= 16384)
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise MetadataRejected() from None
    return copy.deepcopy(value)


def decode_green_metadata(observation):
    """Decode the selected receipt field; never fetch a resource or default a field."""
    if type(observation) is str:
        rejected = False
        try:
            require(len(observation) <= 16384 and len(observation.encode("utf-8")) <= 16384)
            def unique(pairs):
                result = {}
                for key, value in pairs:
                    require(key not in result)
                    result[key] = value
                return result
            def reject_constant(_):
                raise MetadataRejected()
            observation = json.loads(observation, object_pairs_hook=unique, parse_constant=reject_constant)
        except (ValueError, UnicodeError, RecursionError):
            rejected = True
        # Raise outside the parser handler so raw JSON is not retained in exception context.
        if rejected:
            raise MetadataRejected()
    observation = bounded(observation)
    require(type(observation) is dict and set(observation) == {"containerNames", "unsafeFields", "environment", "containerMetadata", "podMetadata"})
    return observation


def contract_shape(application, contract):
    contract = bounded(contract)
    require(type(contract) is dict and set(contract) == {"source_sha", "target_application", "artifact", "container", "namespace"})
    require(type(contract["target_application"]) is str and re.fullmatch(r"Legacy\.Maliev\.[A-Za-z]{1,40}", contract["target_application"]) is not None)
    require(type(contract["artifact"]) is str and contract["source_sha"] == SOURCE_SHA and contract["artifact"] in ARTIFACTS)
    for field in ("container", "namespace"):
        require(type(contract[field]) is str and re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", contract[field]) is not None)
    return contract if application == contract["target_application"] else None


def probe_shape(probe):
    require(type(probe) is dict)
    actions = {"httpGet", "tcpSocket", "grpc"} & set(probe)
    numbers = {"initialDelaySeconds", "timeoutSeconds", "periodSeconds", "successThreshold", "failureThreshold", "terminationGracePeriodSeconds"}
    require(len(actions) == 1 and set(probe) <= actions | numbers)
    action = next(iter(actions))
    handler = probe[action]
    require(type(handler) is dict)
    allowed = {"httpGet": {"path", "port", "host", "scheme"}, "tcpSocket": {"port", "host"}, "grpc": {"port", "service"}}[action]
    require("port" in handler and set(handler) <= allowed)
    port = handler["port"]
    require((type(port) is int and 1 <= port <= 65535) or (action != "grpc" and type(port) is str and re.fullmatch(r"[a-z][a-z0-9-]{0,14}", port) is not None))
    for key, value in handler.items():
        if key == "port":
            continue
        require(type(value) is str and 0 < len(value) <= 256)
        if key == "scheme":
            require(value in ("HTTP", "HTTPS"))
        if key == "path":
            require(value.startswith("/") and "\r" not in value and "\n" not in value)
    for key in numbers & set(probe):
        require(type(probe[key]) is int and (0 if key == "initialDelaySeconds" else 1) <= probe[key] <= 3600)


def environment_shape(environment, read_only):
    require(type(environment) is list)
    result, names = [], set()
    for entry in environment:
        require(type(entry) is dict and "name" in entry and set(entry) in ({"name", "value"}, {"name", "valueFrom"}))
        name = entry["name"]
        require(type(name) is str and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,127}", name) is not None and name not in names)
        names.add(name)
        if "valueFrom" in entry:
            reference = entry["valueFrom"]
            require(name not in {"MALIEV_OBSERVABILITY_STANDBY", "MALIEV_OBSERVABILITY_READ_ONLY_STARTUP"})
            require(type(reference) is dict and len(reference) == 1 and set(reference) <= {"secretKeyRef", "configMapKeyRef", "fieldRef", "resourceFieldRef"})
            require(type(next(iter(reference.values()))) is dict and bool(next(iter(reference.values()))))
            result.append(copy.deepcopy(entry))
        else:
            require(name in FLAGS)
            value = entry["value"]
            value = str(value).lower() if type(value) is bool else value
            require(type(value) is str and value in ("Production", "true", "false"))
            if name in {"ASPNETCORE_ENVIRONMENT", "DOTNET_ENVIRONMENT"}:
                result.append(dict(name=name, value=value))
    result.append(dict(name="MALIEV_OBSERVABILITY_STANDBY", value="true"))
    if read_only:
        result.append(dict(name="MALIEV_OBSERVABILITY_READ_ONLY_STARTUP", value="true"))
    return result


def plan_green_metadata(contract, metadata, image_digest, *, startup_probe=None, read_only=False):
    """Plan selected fields; this is neither a Deployment manifest nor approval."""
    require(type(contract) is dict and "target_application" in contract)
    contract = contract_shape(contract["target_application"], contract)
    metadata = bounded(metadata)
    require(type(read_only) is bool and type(metadata) is dict and set(metadata) == {"containerNames", "unsafeFields", "environment", "containerMetadata", "podMetadata"})
    require(metadata["containerNames"] == [contract["container"]] and type(metadata["containerNames"]) is list)
    require(type(metadata["unsafeFields"]) is list and metadata["unsafeFields"] == [])
    require(type(image_digest) is str and re.fullmatch(r"sha256:[a-f0-9]{64}", image_digest) is not None)
    container, pod = metadata["containerMetadata"], metadata["podMetadata"]
    require(type(container) is dict and set(container) <= CONTAINER_FIELDS and type(pod) is dict and set(pod) <= POD_FIELDS)
    if contract["artifact"] == "maliev-materialservice-api":
        require(read_only and startup_probe is not None)
    planned = {key: copy.deepcopy(value) for key, value in container.items() if value is not None}
    if startup_probe is not None:
        planned["startupProbe"] = bounded(startup_probe)
    for name in PROBES & set(planned):
        probe_shape(planned[name])
    require("readinessProbe" in planned and "livenessProbe" in planned)
    for name in {"ports", "envFrom"} & set(planned):
        require(type(planned[name]) is list and all(type(item) is dict for item in planned[name]))
    for name in {"resources", "securityContext"} & set(planned):
        require(type(planned[name]) is dict)
    if "imagePullPolicy" in planned:
        require(planned["imagePullPolicy"] in ("Always", "IfNotPresent", "Never"))
    for name, value in pod.items():
        if value is None:
            continue
        expected_type = bool if name == "automountServiceAccountToken" else list if name in {"imagePullSecrets", "tolerations"} else dict if name in {"nodeSelector", "affinity", "securityContext"} else str
        require(type(value) is expected_type)
    planned.update(name=contract["container"], imageDigest=image_digest, env=environment_shape(metadata["environment"], read_only),
                   lifecycle=dict(preStop=dict(exec=dict(command=["/bin/sh", "-c", "sleep 60"]))))
    planned_pod = {key: copy.deepcopy(value) for key, value in pod.items() if value is not None}
    planned_pod.update(containers=[planned], terminationGracePeriodSeconds=90)
    return bounded(dict(namespace=contract["namespace"], pod=planned_pod))


def verify_green_metadata(expected, actual):
    expected, actual = bounded(expected), bounded(actual)
    require(json.dumps(expected, sort_keys=True, separators=(",", ":")) == json.dumps(actual, sort_keys=True, separators=(",", ":")))
    return dict(verified=True, runtimeAccepted=False)
