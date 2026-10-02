"""Validate bounded, sanitized observability metadata offline; never collect logs."""

import json
import re
import sys
from datetime import datetime, timedelta, timezone


MAX_BYTES = 65536
MAX_DEPTH = 8
MAX_PODS = 64
MAX_RECORDS = 256
HEX32 = re.compile(r"[0-9a-f]{32}\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
LEVELS = {"Trace": "DEBUG", "Debug": "DEBUG", "Information": "INFO",
          "Warning": "WARNING", "Error": "ERROR", "Critical": "CRITICAL"}
SEVERITY = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4}
WARNING_CATEGORY = "Legacy.Maliev.Web.Middleware.ObservabilityDiagnosticMiddleware"
CRITICAL_CATEGORY = "Legacy.Maliev.Web.Middleware.ErrorIncidentMiddleware"
ERROR_CATEGORY = "Microsoft.AspNetCore.Diagnostics.ExceptionHandlerMiddleware"
EXCEPTION = "ObservabilityDiagnosticException"


class InvalidMetadata(ValueError):
    """Input cannot establish available evidence; never retain its contents."""


def require(condition):
    if not condition:
        raise InvalidMetadata("unavailable")


def keys(value, expected):
    require(type(value) is dict and set(value) == set(expected))


def text(value, maximum, nullable=False):
    if nullable and value is None:
        return
    require(type(value) is str and 0 < len(value) <= maximum)
    require(all(ord(character) >= 32 for character in value))


def identity(value):
    require(type(value) is str and HEX32.fullmatch(value) is not None)


def timestamp(value):
    require(type(value) is str and UTC.fullmatch(value) is not None)
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def unique_object(pairs):
    result = {}
    for name, value in pairs:
        require(name not in result)
        result[name] = value
    return result


def reject_constant(_):
    raise InvalidMetadata("unavailable")


def depth(value, current=0):
    require(current <= MAX_DEPTH)
    if type(value) is dict:
        require(len(value) <= 32)
        for name, child in value.items():
            text(name, 64)
            depth(child, current + 1)
    elif type(value) is list:
        require(len(value) <= MAX_RECORDS)
        for child in value:
            depth(child, current + 1)


def records(value, start, end, inclusive_end=True):
    require(type(value) is list and len(value) <= MAX_RECORDS)
    captured = {}
    for record in value:
        keys(record, ["recordId", "podUid", "severity", "logLevel", "category",
                      "eventName", "exceptionType", "synthetic", "diagnosticId",
                      "traceId", "incidentId", "occurredAtUtc"])
        identity(record["recordId"])
        identity(record["podUid"])
        require(type(record["severity"]) is str and record["severity"] in SEVERITY)
        require(type(record["logLevel"]) is str and record["logLevel"] in LEVELS)
        text(record["category"], 96)
        text(record["eventName"], 64, nullable=True)
        text(record["exceptionType"], 64, nullable=True)
        require(type(record["synthetic"]) is bool)
        # A malformed diagnostic ID cannot earn synthetic classification, but must
        # not erase an otherwise valid natural business failure.
        text(record["diagnosticId"], 64, nullable=True)
        for field in ("traceId", "incidentId"):
            if record[field] is not None:
                identity(record[field])
        occurred = timestamp(record["occurredAtUtc"])
        require(start <= occurred and (occurred <= end if inclusive_end else occurred < end))
        captured_identity = (record["podUid"], record["recordId"])
        require(captured_identity not in captured or captured[captured_identity] == record)
        captured[captured_identity] = record
    return value


def is_synthetic(record):
    diagnostic_id = record["diagnosticId"]
    if (record["synthetic"] is not True or type(diagnostic_id) is not str
            or HEX32.fullmatch(diagnostic_id) is None):
        return False
    if record["category"] == WARNING_CATEGORY:
        return (record["eventName"] == "ObservabilityPipelineProbe"
                and record["exceptionType"] is None
                and record["logLevel"] == "Warning")
    if record["category"] == CRITICAL_CATEGORY:
        return (record["eventName"] == "ObservabilityDiagnosticFailure"
                and record["exceptionType"] == EXCEPTION
                and record["logLevel"] == "Critical")
    return (record["category"] == ERROR_CATEGORY
            and record["eventName"] is None
            and record["exceptionType"] == EXCEPTION
            and record["logLevel"] == "Error")


def proof(record_list, pod):
    observed = set()
    for record in record_list:
        require(record["podUid"] == pod["podUid"])
        require(record["diagnosticId"] == pod["diagnosticId"])
        require(record["severity"] == LEVELS[record["logLevel"]])
        require(is_synthetic(record))
        if record["severity"] == "CRITICAL":
            require(record["incidentId"] == pod["incidentId"])
        else:
            # Warning/framework Error may not own an IncidentId. Bind them by
            # pod+diagnostic to the independently observed Critical/header ID.
            require(record["incidentId"] in (None, pod["incidentId"]))
        observed.add(record["severity"])
    require(observed == {"WARNING", "ERROR", "CRITICAL"})


def severe_event_count(record_list):
    # Natural historic Cloud INFO entries still retain the Error/Critical
    # LogLevel overlay. Never downgrade either independent severe indicator.
    actionable = [record for record in record_list
                  if max(SEVERITY[record["severity"]],
                         SEVERITY[LEVELS[record["logLevel"]]]) >= 3
                  and not is_synthetic(record)]
    parent = list(range(len(actionable)))

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    links = {}
    for index, record in enumerate(actionable):
        identities = [(field, record[field]) for field in ("traceId", "incidentId")
                      if record[field] is not None]
        # Distinct uncorrelated records survive; repeated same captured record
        # may deduplicate without using a missing/null identity as a group key.
        identities.append(("recordId", record["podUid"], record["recordId"]))
        for identifier in identities:
            if identifier in links:
                parent[find(index)] = find(links[identifier])
            else:
                links[identifier] = index
    return len({find(index) for index in range(len(actionable))})


def validate(payload, now):
    keys(payload, ["schemaVersion", "namespace", "expectedRevision",
                   "expectedImageDigest", "exactMainValidation", "captureStartedUtc",
                   "captureCompletedUtc", "naturalAvailability", "actionFromUtc",
                   "actionToUtc", "baselineFromUtc", "baselineToUtc",
                   "actionWindowSeconds", "baselineWindowSeconds", "actionTruncated",
                   "baselineTruncated", "actionRecords", "baselineRecords", "servingPodUids", "pods"])
    require(type(payload["schemaVersion"]) is int and payload["schemaVersion"] == 1)
    require(payload["namespace"] == "maliev-legacy")
    require(type(payload["expectedRevision"]) is str
            and SHA.fullmatch(payload["expectedRevision"]) is not None)
    require(type(payload["expectedImageDigest"]) is str
            and DIGEST.fullmatch(payload["expectedImageDigest"]) is not None)
    require(payload["exactMainValidation"] is True)
    require(payload["naturalAvailability"] == "available")
    require(payload["actionTruncated"] is False and payload["baselineTruncated"] is False)
    require(type(payload["actionWindowSeconds"]) is int and payload["actionWindowSeconds"] == 86400)
    require(type(payload["baselineWindowSeconds"]) is int and payload["baselineWindowSeconds"] == 604800)
    started = timestamp(payload["captureStartedUtc"])
    completed = timestamp(payload["captureCompletedUtc"])
    require(timedelta(0) <= completed - started <= timedelta(seconds=180))
    require(timedelta(0) <= now - completed <= timedelta(seconds=180))
    action_start, action_end = timestamp(payload["actionFromUtc"]), timestamp(payload["actionToUtc"])
    baseline_start, baseline_end = timestamp(payload["baselineFromUtc"]), timestamp(payload["baselineToUtc"])
    require(action_end == completed and action_end - action_start == timedelta(days=1))
    require(baseline_end == action_start and baseline_end - baseline_start == timedelta(days=7))
    pods = payload["pods"]
    require(type(pods) is list and 1 <= len(pods) <= MAX_PODS)
    roster = payload["servingPodUids"]
    require(type(roster) is list and 1 <= len(roster) <= MAX_PODS)
    for pod_uid in roster:
        identity(pod_uid)
    require(len(set(roster)) == len(roster))
    seen_pods, seen_diagnostics = set(), set()
    for pod in pods:
        keys(pod, ["podUid", "ready", "revision", "imageDigest", "socketLoopback",
                   "publicStatus", "privateStatus", "probeCount", "diagnosticId",
                   "incidentId", "portForwardStopped", "observationSeconds", "console", "cloud"])
        identity(pod["podUid"])
        identity(pod["diagnosticId"])
        identity(pod["incidentId"])
        require(pod["podUid"] not in seen_pods and pod["diagnosticId"] not in seen_diagnostics)
        seen_pods.add(pod["podUid"])
        seen_diagnostics.add(pod["diagnosticId"])
        require(pod["ready"] is True and pod["socketLoopback"] is True and pod["portForwardStopped"] is True)
        require(pod["revision"] == payload["expectedRevision"] and pod["imageDigest"] == payload["expectedImageDigest"])
        for name, expected in (("publicStatus", 404), ("privateStatus", 500), ("probeCount", 1)):
            require(type(pod[name]) is int and pod[name] == expected)
        require(type(pod["observationSeconds"]) is int and 0 <= pod["observationSeconds"] <= 180)
        for collection in ("console", "cloud"):
            proof(records(pod[collection], started, completed), pod)
    require(seen_pods == set(roster))
    action = records(payload["actionRecords"], action_start, action_end, inclusive_end=False)
    baseline = records(payload["baselineRecords"], baseline_start, baseline_end, inclusive_end=False)
    return {"visibility": "verified", "actionSevereEvents": severe_event_count(action),
            "baselineSevereEvents": severe_event_count(baseline)}


def main():
    summary = {"visibility": "unavailable", "actionSevereEvents": None,
               "baselineSevereEvents": None}
    code = 1
    try:
        require(len(sys.argv) == 1 or (len(sys.argv) == 3 and sys.argv[1] == "--now-utc"))
        now = timestamp(sys.argv[2]) if len(sys.argv) == 3 else datetime.now(timezone.utc)
        raw = sys.stdin.buffer.read(MAX_BYTES + 1)
        require(len(raw) <= MAX_BYTES)
        payload = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object,
                             parse_constant=reject_constant)
        depth(payload)
        summary = validate(payload, now)
        code = 0
    except (ValueError, TypeError, RecursionError, OverflowError):
        pass
    print(json.dumps(summary, separators=(",", ":")))
    return code


if __name__ == "__main__":
    sys.exit(main())
