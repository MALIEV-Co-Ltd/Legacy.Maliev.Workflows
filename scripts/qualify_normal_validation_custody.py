"""Source-only qualification contracts. This module never launches a worker.

A parsed permit is an association check, not authentication or execution
permission. Native qualification still requires the existing admitted owner.
"""
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import re
from types import MappingProxyType
import sys
import uuid

PRODUCER = "84b2516dfd8e4b48387a412767a52cd58b0b598b"
ISSUER = "019fc21e-50f0-7112-834f-9fb3b35b9dfe"
OWNER = "01a1009c-83f6-7010-9a59-df89ecbb1b1f"
SOURCE_PINS = {'actions/dotnet-validate/action.yml': 'c5d82ee453b754a4dd4210a078c195f1f856df594df46ae2c8bf4e3cd2b2f394', 'scripts/normal_validation_custody.py': '03a9a7f0715d624acad1e6317e151cbb10ef931e193c132b91353e2270bf2acb', 'scripts/normal_validation_controller.py': 'aa59e1c2232d2405a98b87b9085692b58e7c0f225cf60009e181ed7873d082b3', 'scripts/normal_validation_exec_gate.py': 'c1771473003b2cc8f411493f4717c4b9e71461ef93b7906da69c22d24341fe03', 'scripts/normal_validation_lifecycle.py': '8c2000ffeeade09de62af69d3f09e4ecb9001bfab2f783244668f4dd98d6424b'}
RESERVE = 300
PERMIT_KEYS = {"schema", "issuer", "owner", "kind", "leaseId", "issuedUtc",
               "expiresUtc", "producer", "run", "attempt", "job", "clockSha256"}
CLOCK_KEYS = {"schema", "run", "attempt", "job", "head", "runner", "startedUtc",
              "sampleWall", "sampleMono", "boot", "deadlineMono", "reserve"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, "Duplicate key")
        value[key] = item
    return value


def parse(raw):
    require(type(raw) is bytes and len(raw) <= 16384, "Bounded JSON bytes required")
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))


def number(value):
    require(type(value) in (int, float) and 0 <= value <= sys.float_info.max and math.isfinite(value),
            "Finite strict number required")
    return value


def utc(value):
    require(type(value) is str, "UTC string required")
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(parsed.utcoffset() == dt.timedelta(0), "UTC required")
    return parsed


def compile_authenticated(sources):
    """Compile held immutable bytes only; never exec, import or reopen paths."""
    require(type(sources) is dict and set(sources) == set(SOURCE_PINS), "Complete immutable source set")
    codes = {}
    for name, digest in SOURCE_PINS.items():
        raw = sources[name]
        require(type(raw) is bytes and 0 < len(raw) <= 131072
                and hashlib.sha256(raw).hexdigest() == digest, "Source digest mismatch")
        if name.endswith(".py"):
            codes[name] = compile(raw, name, "exec")
    return codes


class Fence:
    __slots__ = ("_record", "_deadline", "_active_deadline", "last_mono", "cancelled", "kind")
    """Pure narrower deadline state; cannot start, stop or signal processes."""
    def __init__(self, raw_clock, context, permit, wall, mono, kind):
        record = parse(raw_clock)
        require(type(record) is dict and set(record) == CLOCK_KEYS, "Exact original clock")
        require(record["schema"] == "n62-job-deadline-v1" and type(record["reserve"]) is int
                and record["reserve"] == RESERVE, "Original reserve required")
        require(type(context) is dict and set(context) == {"run", "attempt", "job", "head", "runner", "boot"}, "Exact caller context")
        for key in ("run", "attempt", "job"):
            require(type(record[key]) is int and record[key] > 0 and type(context[key]) is int,
                    "Strict caller identity")
        require(type(record["head"]) is str and re.fullmatch("[0-9a-f]{40}", record["head"])
                and type(record["runner"]) is str and bool(record["runner"])
                and type(record["boot"]) is str and re.fullmatch("[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", record["boot"]), "Strict original clock identity")
        require(all(type(record[key]) is type(context[key]) and record[key] == context[key] for key in context), "Original caller association")
        for key in ("sampleWall", "sampleMono", "deadlineMono"):
            number(record[key])
        number(wall); number(mono)
        elapsed = record["sampleWall"] - utc(record["startedUtc"]).timestamp()
        require(0 <= elapsed < 2700 and abs(record["sampleMono"] + 2700 - elapsed
                - record["deadlineMono"]) <= .001, "Original 45-minute clock required")
        require(mono >= record["sampleMono"] and abs(wall - record["sampleWall"]
                - (mono - record["sampleMono"])) <= 2, "Clock drift")
        require(type(permit) is dict and set(permit) == PERMIT_KEYS, "Exact permit")
        require(kind in ("kernel", "sdk") and permit["kind"] == kind, "Distinct permit kind")
        require(permit["schema"] == "normal-qualification-permit-v1" and permit["issuer"] == ISSUER
                and permit["owner"] == OWNER and permit["producer"] == PRODUCER, "Permit association")
        require(all(type(permit[k]) is int and permit[k] == record[k] for k in ("run", "attempt", "job")), "Permit caller association")
        require(permit["clockSha256"] == hashlib.sha256(raw_clock).hexdigest(), "Original clock digest")
        require(type(permit["leaseId"]) is str and str(uuid.UUID(permit["leaseId"])) == permit["leaseId"], "Canonical lease")
        issued, expiry = utc(permit["issuedUtc"]), utc(permit["expiresUtc"])
        require(0 < (expiry - issued).total_seconds() <= 900 and issued.timestamp() <= wall < expiry.timestamp(), "Finite current permit")
        self._record = MappingProxyType(dict(record))
        self._deadline = min(record["deadlineMono"], mono + expiry.timestamp() - wall)
        require(self.deadline - mono > RESERVE, "Cleanup reserve unavailable")
        self._active_deadline = min(self.deadline - RESERVE, mono + 600)
        self.last_mono = mono
        self.cancelled = False
        self.kind = kind

    @property
    def record(self):
        return self._record

    @property
    def deadline(self):
        return self._deadline

    @property
    def active_deadline(self):
        return self._active_deadline

    def remaining(self, wall, mono, cleanup=False):
        number(wall); number(mono)
        require(type(cleanup) is bool and mono >= self.last_mono, "Monotonic clock cannot reset")
        require(abs(wall - self.record["sampleWall"] - (mono - self.record["sampleMono"])) <= 2, "Clock drift")
        self.last_mono = mono
        if self.cancelled and not cleanup:
            raise ValueError("Cancellation prevents dependent release")
        remaining = (self.deadline if cleanup else self.active_deadline) - mono
        require(remaining > 0, "Finite qualification expired")
        return remaining

    def cancel(self):
        # A future admitted owner wires first/repeated signals to this state;
        # this pure method registers no handler and performs no signal operation.
        self.cancelled = True

    def service_expiry(self, wall, mono):
        return mono + min(600, self.remaining(wall, mono))


def may_stop(original, observed):
    """Uncertain partial allocation preserves finite expiry, never guesses ownership."""
    required = {"unit", "invocation", "run", "scopeDevice", "scopeInode"}
    if type(original) is not dict or type(observed) is not dict or not required <= set(original):
        return False
    if any(type(original[key]) is not str or not original[key] for key in ("unit", "invocation", "run")):
        return False
    if any(type(original[key]) is not int or original[key] < 1 for key in ("scopeDevice", "scopeInode")):
        return False
    return all(type(observed.get(key)) is type(original[key]) and observed.get(key) == original[key] for key in required)


def vector(kind, argv, expected_sdk=None):
    require(type(argv) is list and all(type(x) is str for x in argv), "Exact argument vector")
    if kind == "kernel":
        require(argv == ["/usr/bin/sleep", "2"], "Harmless frozen kernel vector only")
    elif kind == "sdk":
        require(type(expected_sdk) is list and len(expected_sdk) >= 3
                and expected_sdk[0] == "dotnet" and argv == expected_sdk
                and not any(x in ("--filter", "--list-tests") or x.startswith("--filter=") for x in argv), "Reviewed unfiltered SDK vector only")
    else:
        raise ValueError("Unknown permit kind")
    # Association validation intentionally returns no executable authority.
    return {"kind": kind, "executionAuthorized": False}


def report():
    """Read-only API inventory; manager/kernel observations require a later owner."""
    checks = {"linux": sys.platform == "linux", "githubJob": os.environ.get("GITHUB_ACTIONS") == "true",
              "pidfdOpen": hasattr(os, "pidfd_open"), "pidfdSignal": hasattr(signal, "pidfd_send_signal"),
              "fdExec": os.execve in os.supports_fd,
              "isolatedInterpreter": bool(sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode),
              "userManager": "NOT_OBSERVED", "cgroupCaps": "NOT_OBSERVED",
              "physicalAdmission": "NOT_OBSERVED", "callerAuthenticated": False}
    return {"schema": "normal-qualification-report-v1", "producer": PRODUCER,
            "status": "UNAVAILABLE", "checks": checks, "executionAuthorized": False,
            "runtimeReleased": False, "resourceAllocated": False}


if __name__ == "__main__":
    require(sys.argv[1:] in ([], ["--report"]), "Only non-allocating report is implemented")
    print(json.dumps(report(), sort_keys=True))
