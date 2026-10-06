"""Pure startup/rollout contract; endpoint mapping must be reviewed by its owner."""
import copy
import json
import re

SOURCE_SHA = "eb11c81a6c759e1d4bcd1a1b3b28dc5f30cc02cb"
ROLLOUT = dict(minReadySeconds=90, drainSeconds=60, terminationGracePeriodSeconds=90, maxSurge=1, maxUnavailable=0)


class StartupRejected(ValueError):
    def __init__(self):
        super().__init__("Startup protection contract rejected.")


def require(condition):
    if not condition:
        raise StartupRejected()


def parse_probe_json(payload):
    require(type(payload) is str and len(payload) <= 16384)
    try:
        require(len(payload.encode("utf-8")) <= 16384)
    except UnicodeError:
        raise StartupRejected() from None

    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result)
            result[key] = value
        return result

    try:
        return json.loads(payload, object_pairs_hook=unique, parse_constant=lambda _: (_ for _ in ()).throw(StartupRejected()))
    except (ValueError, RecursionError):
        raise StartupRejected() from None


def endpoint_shape(endpoint):
    require(type(endpoint) is dict and set(endpoint) == {"path", "port", "scheme"})
    require(type(endpoint["path"]) is str and re.fullmatch(r"/[A-Za-z0-9/_-]{1,200}", endpoint["path"]) is not None)
    require(type(endpoint["port"]) is int and 1 <= endpoint["port"] <= 65535 and endpoint["scheme"] == "HTTP")
    return copy.deepcopy(endpoint)


def probe_shape(probe, endpoint, *, allow_none=False):
    endpoint = endpoint_shape(endpoint)
    if probe is None:
        require(allow_none)
        return None
    required = {"httpGet", "failureThreshold", "periodSeconds", "successThreshold", "timeoutSeconds"}
    require(type(probe) is dict and required <= set(probe) <= required | {"initialDelaySeconds"})
    require(type(probe["httpGet"]) is dict and probe["httpGet"] == endpoint and set(probe["httpGet"]) == set(endpoint))
    require(type(probe["httpGet"]["port"]) is int)
    for field, expected in [("failureThreshold", 60), ("periodSeconds", 5), ("successThreshold", 1), ("timeoutSeconds", 5)]:
        require(type(probe[field]) is int and probe[field] == expected)
    if "initialDelaySeconds" in probe:
        require(type(probe["initialDelaySeconds"]) is int and probe["initialDelaySeconds"] == 0)
    return {"failureThreshold": 60, "httpGet": endpoint, "periodSeconds": 5, "successThreshold": 1, "timeoutSeconds": 5}


def plan_startup_update(*, application, target_application, source_sha, endpoint, source_probe, current_probe, rollout):
    """Return detached metadata only. No callback, file, network or deployment."""
    require(type(application) is str and type(target_application) is str)
    require(re.fullmatch(r"Legacy\.Maliev\.[A-Za-z]{1,40}", application) is not None)
    require(re.fullmatch(r"Legacy\.Maliev\.[A-Za-z]{1,40}", target_application) is not None)
    if application != target_application:
        return dict(changed=False, previousProbe=copy.deepcopy(current_probe), desiredProbe=copy.deepcopy(current_probe))
    require(source_sha == SOURCE_SHA)
    require(type(rollout) is dict and rollout == ROLLOUT and all(type(value) is int for value in rollout.values()))
    desired = probe_shape(source_probe, endpoint)
    probe_shape(current_probe, endpoint, allow_none=True)
    # Keep original null/owned shape, including optional initialDelaySeconds=0,
    # for exact rollback. Canonical normalization is only for validation.
    return dict(changed=True, previousProbe=copy.deepcopy(current_probe), desiredProbe=desired)


def verify_startup_readback(plan, actual_probe, stage):
    require(type(plan) is dict and set(plan) == {"changed", "previousProbe", "desiredProbe"} and type(plan["changed"]) is bool)
    require(stage in ("preflight", "green", "canonical", "rollback"))
    expected = plan["previousProbe"] if stage in ("preflight", "rollback") else plan["desiredProbe"]
    # Type-sensitive JSON comparison prevents True and 1 comparing as equal.
    try:
        actual_json = json.dumps(actual_probe, sort_keys=True, allow_nan=False, separators=(",", ":"))
        expected_json = json.dumps(expected, sort_keys=True, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError, RecursionError):
        raise StartupRejected() from None
    require(actual_json == expected_json)
    return dict(verified=True, stage=stage, runtimeAccepted=False)
