import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from startup_protection import ROLLOUT, SOURCE_SHA, StartupRejected, parse_probe_json, plan_startup_update, verify_startup_readback


class StartupProtectionTests(unittest.TestCase):
    def setUp(self):
        # Historical source endpoint only; no current Catalog endpoint assertion.
        self.endpoint = dict(path="/materials/liveness", port=8080, scheme="HTTP")
        self.probe = dict(failureThreshold=60, httpGet=copy.deepcopy(self.endpoint), periodSeconds=5, successThreshold=1, timeoutSeconds=5)
        self.arguments = dict(application="Legacy.Maliev.CatalogService", target_application="Legacy.Maliev.CatalogService",
                              source_sha=SOURCE_SHA, endpoint=self.endpoint, source_probe=self.probe, current_probe=None, rollout=copy.deepcopy(ROLLOUT))

    def plan(self, **changes):
        return plan_startup_update(**dict(self.arguments, **changes))

    def test_null_previous_probe_survives_preflight_and_rollback(self):
        plan = self.plan()
        self.assertIsNone(plan["previousProbe"])
        for stage in ("preflight", "rollback"):
            self.assertFalse(verify_startup_readback(plan, None, stage)["runtimeAccepted"])

    def test_exact_owned_previous_shape_survives_rollback(self):
        owned = dict(self.probe, initialDelaySeconds=0)
        plan = self.plan(current_probe=owned)
        self.assertEqual(plan["previousProbe"], owned)
        verify_startup_readback(plan, owned, "rollback")
        with self.assertRaises(StartupRejected):
            verify_startup_readback(plan, self.probe, "rollback")

    def test_green_and_canonical_require_same_300_second_probe(self):
        plan = self.plan()
        self.assertEqual(300, plan["desiredProbe"]["failureThreshold"] * plan["desiredProbe"]["periodSeconds"])
        for stage in ("green", "canonical"):
            verify_startup_readback(plan, self.probe, stage)
            with self.assertRaises(StartupRejected):
                verify_startup_readback(plan, None, stage)

    def test_concurrent_probe_change_rejects_preflight(self):
        plan = self.plan()
        with self.assertRaises(StartupRejected):
            verify_startup_readback(plan, self.probe, "preflight")

    def test_source_probe_mutations_reject(self):
        mutations = [None, [], "private-value", dict(self.probe, failureThreshold=600), dict(self.probe, failureThreshold=True),
                     dict(self.probe, periodSeconds="5"), dict(self.probe, initialDelaySeconds=1), dict(self.probe, unknown="private-value"),
                     dict(self.probe, httpGet=dict(self.endpoint, path="/materials/write")),
                     dict(self.probe, httpGet=dict(self.endpoint, port=True)),
                     dict(self.probe, httpGet=dict(self.endpoint, httpHeaders=[dict(value="private-value")])),
                     dict(self.probe, exec=dict(command=["private-value"]))]
        for value in mutations:
            with self.subTest(probe=value), self.assertRaises(StartupRejected) as captured:
                self.plan(source_probe=value)
            self.assertNotIn("private-value", str(captured.exception))

    def test_foreign_existing_probe_rejects_before_plan(self):
        with self.assertRaises(StartupRejected):
            self.plan(current_probe=dict(exec=dict(command=["private-value"])))

    def test_unrelated_service_keeps_existing_probe_without_injection(self):
        existing = dict(exec=dict(command=["existing-owned-command"]))
        plan = self.plan(application="Legacy.Maliev.CountryService", endpoint=None, source_probe=None, current_probe=existing)
        self.assertFalse(plan["changed"])
        self.assertEqual(existing, plan["desiredProbe"])
        plan["desiredProbe"]["exec"]["command"].append("mutated")
        self.assertEqual(["existing-owned-command"], existing["exec"]["command"])
        self.assertEqual(existing, plan["previousProbe"])

    def test_missing_or_malformed_endpoint_rejects(self):
        for endpoint in (None, {}, dict(self.endpoint, scheme="HTTPS"), dict(self.endpoint, host="private-value"), dict(self.endpoint, path="/write?token=private-value")):
            with self.subTest(endpoint=endpoint), self.assertRaises(StartupRejected):
                self.plan(endpoint=endpoint)

    def test_all_rollout_settings_are_exact_and_type_sensitive(self):
        for field in ROLLOUT:
            mutated = dict(ROLLOUT)
            mutated[field] += 1
            with self.subTest(field=field), self.assertRaises(StartupRejected):
                self.plan(rollout=mutated)
        with self.assertRaises(StartupRejected):
            self.plan(rollout=dict(ROLLOUT, maxUnavailable=False))

    def test_duplicate_missing_and_oversize_json_reject(self):
        for payload in ('{"httpGet":{},"httpGet":{}}', '{', '"' + 'x' * 16384 + '"', '{"value":NaN}'):
            with self.subTest(payload=payload[:30]), self.assertRaises(StartupRejected):
                parse_probe_json(payload)
        self.assertEqual(self.probe, parse_probe_json(json.dumps(self.probe)))

    def test_inputs_are_detached_from_plan(self):
        before = copy.deepcopy(self.arguments)
        plan = self.plan()
        plan["desiredProbe"]["httpGet"]["path"] = "/mutated"
        self.assertEqual(before, self.arguments)

    def test_malformed_unicode_and_multibyte_oversize_reject_without_diagnostics(self):
        for payload in ('"\ud800"', '"' + '\u0e01' * 6000 + '"'):
            with self.subTest(length=len(payload)), self.assertRaises(StartupRejected) as caught:
                parse_probe_json(payload)
            self.assertEqual("Startup protection contract rejected.", str(caught.exception))

    def test_oversize_character_length_rejects(self):
        with self.assertRaises(StartupRejected):
            parse_probe_json("x" * 16385)

    def test_source_identity_and_unknown_stage_reject(self):
        with self.assertRaises(StartupRejected):
            self.plan(source_sha="a" * 40)
        with self.assertRaises(StartupRejected):
            verify_startup_readback(self.plan(), self.probe, "unknown")


if __name__ == "__main__":
    unittest.main()
