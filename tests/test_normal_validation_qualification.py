"""Pure qualification contract refusals; no kernel or SDK qualification."""
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("qualification_contract", ROOT/"scripts/qualify_normal_validation_custody.py")
Q = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(Q)


class QualificationControls(unittest.TestCase):
    def setUp(self):
        self.wall = dt.datetime(2026, 10, 12, 9, tzinfo=dt.timezone.utc).timestamp()
        self.mono = 1000
        self.context = {"run": 123, "attempt": 1, "job": 456, "head": "a"*40, "runner": "fixture", "boot": "12345678-1234-1234-1234-123456789abc"}
        self.clock = {"schema": "n62-job-deadline-v1", **self.context,
                      "startedUtc": "2026-10-12T09:00:00Z", "sampleWall": self.wall,
                      "sampleMono": self.mono, "deadlineMono": 3700, "reserve": 300}
        self.raw = json.dumps(self.clock).encode()
        self.permit = {"schema": "normal-qualification-permit-v1", "issuer": Q.ISSUER, "owner": Q.OWNER,
                       "kind": "kernel", "leaseId": "12345678-1234-1234-1234-123456789abc",
                       "issuedUtc": "2026-10-12T09:00:00Z", "expiresUtc": "2026-10-12T09:15:00Z",
                       "producer": Q.PRODUCER, "run": 123, "attempt": 1, "job": 456,
                       "clockSha256": hashlib.sha256(self.raw).hexdigest()}

    def fence(self, **kw):
        return Q.Fence(kw.get("raw", self.raw), kw.get("context", self.context),
                       kw.get("permit", self.permit), kw.get("wall", self.wall),
                       kw.get("mono", self.mono), kw.get("kind", "kernel"))

    def test_report_and_import_cannot_allocate(self):
        with patch("subprocess.Popen", side_effect=AssertionError("allocation")), patch("socket.socket", side_effect=AssertionError("socket")), patch("os.system", side_effect=AssertionError("shell")):
            isolated = importlib.util.module_from_spec(SPEC)
            SPEC.loader.exec_module(isolated)
            r = isolated.report()
        self.assertEqual({"schema", "producer", "status", "checks", "executionAuthorized", "runtimeReleased", "resourceAllocated"}, set(r))
        self.assertEqual("UNAVAILABLE", r["status"])
        self.assertFalse(any(r[k] for k in ("executionAuthorized", "runtimeReleased", "resourceAllocated")))
        self.assertEqual("NOT_OBSERVED", r["checks"]["userManager"])
        self.assertFalse(r["checks"]["callerAuthenticated"])

    def test_narrow_budget_preserves_original_clock(self):
        fence = self.fence()
        self.assertEqual(3700, fence.record["deadlineMono"])
        self.assertEqual(1900, fence.deadline)
        self.assertEqual(1600, fence.active_deadline)
        self.assertEqual(600, fence.remaining(self.wall, self.mono))
        self.assertEqual(900, fence.remaining(self.wall, self.mono, cleanup=True))
        self.assertEqual(1600, fence.service_expiry(self.wall, self.mono))
        self.assertEqual(self.raw, json.dumps(self.clock).encode())

    def test_permit_drift_and_extra_fields_refused(self):
        mutations = {"issuer": "other", "owner": "other", "producer": "b"*40, "run": 124,
                     "attempt": True, "job": 0, "kind": "sdk", "clockSha256": "0"*64,
                     "leaseId": "bad", "schema": "unknown", "extra": "field"}
        for key, value in mutations.items():
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.fence(permit={**self.permit, key: value})

    def test_expired_naive_extended_and_short_permits_refused(self):
        for expiry in ("2026-10-12T08:59:59Z", "2026-10-12T09:15:01Z", "2026-10-12T09:15:00", "2026-10-12T09:05:00Z"):
            with self.subTest(expiry=expiry), self.assertRaises(ValueError):
                self.fence(permit={**self.permit, "expiresUtc": expiry})

    def test_clock_reset_drift_and_reserve_refused(self):
        for key, value in (("deadlineMono", 3701), ("reserve", 299), ("job", 457), ("sampleMono", 999)):
            raw = json.dumps({**self.clock, key: value}).encode()
            permit = {**self.permit, "clockSha256": hashlib.sha256(raw).hexdigest()}
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.fence(raw=raw, permit=permit)
        with self.assertRaises(ValueError): self.fence(wall=self.wall+3)
        fence = self.fence()
        fence.remaining(self.wall+1, self.mono+1)
        with self.assertRaises(ValueError): fence.remaining(self.wall, self.mono)
        with self.assertRaises(ValueError): fence.remaining(self.wall+901, self.mono+901, cleanup=True)

    def test_cancellation_never_releases_dependents_but_keeps_cleanup(self):
        fence = self.fence()
        fence.cancel(); fence.cancel()
        with self.assertRaises(ValueError): fence.remaining(self.wall+1, self.mono+1)
        self.assertEqual(899, fence.remaining(self.wall+1, self.mono+1, cleanup=True))

    def test_partial_or_reused_custody_never_authorizes_stop(self):
        row = {"unit": "owned", "invocation": "abc", "run": "nonce", "scopeDevice": 1, "scopeInode": 2}
        self.assertTrue(Q.may_stop(row, dict(row)))
        for key in row:
            self.assertFalse(Q.may_stop(row, {k: v for k, v in row.items() if k != key}))
            self.assertFalse(Q.may_stop(row, {**row, key: "reused"}))
        self.assertFalse(Q.may_stop({}, row))
        self.assertFalse(Q.may_stop({**row, "scopeInode": True}, row))

    def test_kernel_and_sdk_vectors_remain_separate(self):
        self.assertFalse(Q.vector("kernel", ["/usr/bin/sleep", "2"])["executionAuthorized"])
        for args in (["dotnet", "test"], ["/usr/bin/sleep", "3"], ["sh", "-c", "echo x"]):
            with self.assertRaises(ValueError): Q.vector("kernel", args)
        expected = ["dotnet", "test", "reviewed.slnx", "--no-build"]
        self.assertFalse(Q.vector("sdk", expected, expected)["executionAuthorized"])
        for args in (expected+["--filter", "x"], expected+["--filter=x"], ["dotnet", "test", "other.slnx"]):
            with self.assertRaises(ValueError): Q.vector("sdk", args, expected)
        with self.assertRaises(ValueError): self.fence(kind="sdk")

    def test_compilation_authenticates_all_held_bytes_without_execution(self):
        sources = {name: (ROOT/name).read_bytes().replace(b"\r\n", b"\n") for name in Q.SOURCE_PINS}
        codes = Q.compile_authenticated(sources)
        self.assertEqual(4, len(codes))
        for name in sources:
            with self.subTest(name=name), self.assertRaises(ValueError):
                Q.compile_authenticated({**sources, name: sources[name]+b" "})
        with self.assertRaises(ValueError): Q.compile_authenticated({})

    def test_valid_looking_unsigned_permit_never_grants_execution(self):
        # These strings match expected associations but prove no external grant.
        fence = self.fence()
        self.assertFalse(hasattr(fence, "launch"))
        self.assertFalse(Q.report()["executionAuthorized"])
        self.assertFalse(Q.report()["resourceAllocated"])
        self.assertFalse(Q.report()["runtimeReleased"])
        with self.assertRaises(TypeError): fence.record["deadlineMono"] = 9999
        with self.assertRaises(AttributeError): fence.deadline = 9999
        with self.assertRaises(AttributeError): fence.active_deadline = 9999

    def test_huge_json_integer_is_consistent_value_error(self):
        huge = 10**400
        with self.assertRaises(ValueError): Q.number(huge)
        raw = json.dumps({**self.clock, "sampleMono": huge}).encode()
        permit = {**self.permit, "clockSha256": hashlib.sha256(raw).hexdigest()}
        with self.assertRaises(ValueError): self.fence(raw=raw, permit=permit)
        self.assertEqual(1, Q.number(1))

    def test_strict_json_and_numeric_types(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b" "*16385):
            with self.assertRaises(ValueError): Q.parse(raw)
        for value in (True, float("inf"), float("nan"), -1):
            with self.assertRaises(ValueError): Q.number(value)


if __name__ == "__main__":
    unittest.main()
