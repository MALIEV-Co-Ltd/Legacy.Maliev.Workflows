"""Historical Service-only wrapper policy; injected boundary, no native executor."""
import copy
import hashlib
import json
import re

SEPARATION_SOURCE = "3a393215d883fa35e1461f69c876bf2ead7ce36e"
CHECKPOINT = "135e526d0dab85c415b3afdcefd7b70fe2c82e2f"
SERVICES = {
    "Legacy.Maliev.FileService": "maliev-uploadservice-api",
    "Legacy.Maliev.DocumentService": "maliev-pdfservice-api",
    "Legacy.Maliev.NotificationService": "maliev-emailservice-api",
}
CANONICAL_IDENTITIES = {
    "Legacy.Maliev.FileService": {"legacy-maliev-file", "legacy-maliev-file-service"},
    "Legacy.Maliev.DocumentService": {"legacy-maliev-document-service"},
    "Legacy.Maliev.NotificationService": {"legacy-maliev-notification-service"},
}


class ServiceWrapperFailure(RuntimeError):
    def __init__(self, exit_code=1):
        super().__init__("Service manifest wrapper rejected; details withheld.")
        self.exit_code = exit_code


def _require(condition):
    if not condition:
        raise ServiceWrapperFailure()


def _snapshot(value):
    # Copy through strict JSON before invoking caller code. No provider bytes in errors.
    try:
        def shape(item, depth=0):
            _require(depth <= 32)
            if type(item) is dict:
                _require(all(type(key) is str for key in item))
                for child in item.values():
                    shape(child, depth + 1)
            elif type(item) is list:
                for child in item:
                    shape(child, depth + 1)
            else:
                _require(item is None or type(item) in (str, int, float, bool))
        shape(value)
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                             separators=(",", ":")).encode("utf-8")
        _require(len(encoded) <= 16384)
        return json.loads(encoded), hashlib.sha256(encoded).hexdigest()
    except Exception:
        raise ServiceWrapperFailure() from None


def run_service_wrapper(application, source_commit, manifest, tool):
    """Carry the Service-only and exit-status obligations through one injected call.

    Historical namespace and resource identities are retained. This boundary does
    not authorize a canonical namespace adaptation or attest actual Kubernetes I/O.
    """
    _require(type(application) is str and application in SERVICES)
    _require(type(source_commit) is str and re.fullmatch(r"[0-9a-f]{40}", source_commit) is not None)
    _require(callable(tool) and type(manifest) is dict)
    document, digest = _snapshot(manifest)
    name = SERVICES[application]
    _require(document.get("apiVersion") == "v1" and document.get("kind") == "Service")
    metadata = document.get("metadata")
    _require(type(metadata) is dict and metadata.get("name") == name and metadata.get("namespace") == "maliev")
    spec = document.get("spec")
    _require(type(spec) is dict and spec.get("selector") == {"run": name})
    ports = spec.get("ports")
    _require(type(ports) is list and len(ports) > 0 and all(type(p) is dict for p in ports))
    # Prevent a mixed resource list hidden in a Service-shaped envelope.
    _require("items" not in document)
    request = dict(application=application, sourceCommit=source_commit,
                   manifestSha256=digest, manifest=copy.deepcopy(document))
    _, request_digest = _snapshot(request)
    try:
        result = tool("APPLY_SERVICE_MANIFEST", request)
    except Exception:
        # Even this public exception is untrusted when supplied by caller code.
        raise ServiceWrapperFailure() from None
    result, _ = _snapshot(result)
    _require(type(result) is dict and set(result) == {"exitCode", "receipt"})
    code = result["exitCode"]
    _require(type(code) is int and 0 <= code <= 2147483647)
    if code:
        raise ServiceWrapperFailure(code)
    _, observed_request_digest = _snapshot(request)
    _require(observed_request_digest == request_digest)
    receipt = result["receipt"]
    _require(type(receipt) is dict and set(receipt) == {"sourceCommit", "manifestSha256"})
    _require(receipt["sourceCommit"] == source_commit and receipt["manifestSha256"] == digest)
    return dict(schemaVersion="offline-service-wrapper/v1", sourceCommit=source_commit,
                application=application, manifestSha256=digest, exitCode=0,
                deploymentAllowed=False, runtimeAccepted=False, consumerAdoptionAccepted=False)


def verify_canonical_service_projection(application, source_commit, services, active_identities):
    """Admit the dormant canonical Service projection without an apply boundary.

    The caller renders committed GitOps source and supplies only Service documents
    and kind/name/namespace identities from the active environment. No secrets or
    workload configuration are returned. Observations are not runtime attestation.
    """
    _require(type(application) is str and application in CANONICAL_IDENTITIES)
    _require(type(source_commit) is str and re.fullmatch(r"[0-9a-f]{40}", source_commit) is not None)
    _require(type(services) is list and type(active_identities) is list)
    service_copy, service_digest = _snapshot(services)
    active_copy, active_digest = _snapshot(active_identities)
    for identity in active_copy:
        _require(type(identity) is dict and set(identity) == {"kind", "name", "namespace"})
        _require(all(type(identity[key]) is str and identity[key] for key in ("kind", "name")))
        _require(type(identity["namespace"]) is str)
        _require(identity["namespace"] == "" or re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", identity["namespace"]) is not None)
        _require(not (identity["namespace"] == "maliev-legacy" and identity["name"] in CANONICAL_IDENTITIES[application]))
    if application != "Legacy.Maliev.NotificationService":
        # File has no Service lane; Document currently renders only its secret projection.
        _require(service_copy == [])
    else:
        _require(len(service_copy) == 1)
        document = service_copy[0]
        _require(type(document) is dict and set(document) == {"apiVersion", "kind", "metadata", "spec"})
        _require(document["apiVersion"] == "v1" and document["kind"] == "Service")
        metadata = document["metadata"]
        _require(type(metadata) is dict and set(metadata) == {"name", "namespace", "labels"})
        name = "legacy-maliev-notification-service"
        _require(metadata["name"] == name and metadata["namespace"] == "maliev-legacy")
        labels = {"app.kubernetes.io/name": name, "app.kubernetes.io/environment": "legacy"}
        _require(metadata["labels"] == labels)
        spec = document["spec"]
        _require(type(spec) is dict and set(spec) == {"type", "selector", "ports"})
        _require(spec["type"] == "ClusterIP" and spec["selector"] == labels)
        ports = spec["ports"]
        _require(type(ports) is list and len(ports) == 1 and type(ports[0]) is dict)
        port = ports[0]
        _require(set(port) == {"name", "port", "targetPort", "protocol"})
        _require(port["name"] == "http" and type(port["port"]) is int and port["port"] == 8080
                 and port["targetPort"] == "http" and port["protocol"] == "TCP")
    return dict(schemaVersion="offline-canonical-service-projection/v1", application=application,
                sourceCommit=source_commit, servicesSha256=service_digest, activeIdentitiesSha256=active_digest,
                serviceCount=len(service_copy), dormantProjectionConsistent=True,
                deploymentAllowed=False, runtimeAccepted=False, consumerAdoptionAccepted=False)
