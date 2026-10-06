import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from application_handoff_policy import HandoffFailure, run_handoff
from startup_protection import SOURCE_SHA
from test_application_handoff_policy import COMMIT, DIGEST, FakeTools


ENDPOINT = dict(path="/materials/liveness", port=8080, scheme="HTTP")
PROBE = dict(httpGet=ENDPOINT, failureThreshold=60, periodSeconds=5, successThreshold=1, timeoutSeconds=5)
CONTRACT = dict(target_application="Legacy.Maliev.CatalogService", source_sha=SOURCE_SHA, endpoint=ENDPOINT, source_probe=PROBE)


class StartupTools(FakeTools):
    """Injected producer consumes the real policy requests; no deployment adapter."""
    def __init__(self, *, previous=None, fault=None, **kwargs):
        super().__init__(**kwargs)
        self.deployment["startupProbe"] = copy.deepcopy(previous)
        self.startup_fault = fault

    def __call__(self, step, request):
        if step == "MUTATE_CANONICAL" and "startupProbe" in request:
            if request["expectedStartupProbe"] != self.deployment["startupProbe"]:
                return dict(exitCode=79, receipt={})
        response = super().__call__(step, request)
        if step == "CREATE_GREEN" and "startupProbe" in request:
            self.green["startupProbe"] = copy.deepcopy(request["startupProbe"])
            response["receipt"]["startupProbe"] = copy.deepcopy(self.green["startupProbe"])
        if step == "MUTATE_CANONICAL" and "startupProbe" in request:
            self.deployment["startupProbe"] = copy.deepcopy(request["startupProbe"])
            response["receipt"]["startupProbe"] = copy.deepcopy(self.deployment["startupProbe"])
        if self.startup_fault:
            self.startup_fault(self, step, response["receipt"])
        return response


class StartupHandoffTests(unittest.TestCase):
    def run_policy(self, tools, **changes):
        return run_handoff("Legacy.Maliev.CatalogService", COMMIT, DIGEST, tools, startup_contract=copy.deepcopy(CONTRACT), **changes)

    def test_actual_handoff_requests_and_readbacks_share_startup_contract(self):
        tools = StartupTools()
        result = self.run_policy(tools)
        self.assertFalse(result["runtimeAccepted"])
        for step in ("CREATE_GREEN", "MUTATE_CANONICAL"):
            request = next(request for actual, request in tools.requests if actual == step)
            self.assertEqual(PROBE, request["startupProbe"])
        mutation = next(request for actual, request in tools.requests if actual == "MUTATE_CANONICAL")
        self.assertIsNone(mutation["expectedStartupProbe"])

    def test_bad_source_contract_rejects_before_any_callback(self):
        tools = StartupTools()
        contract = copy.deepcopy(CONTRACT)
        contract["source_probe"]["failureThreshold"] = 600
        with self.assertRaises(HandoffFailure) as caught:
            run_handoff("Legacy.Maliev.CatalogService", COMMIT, DIGEST, tools, startup_contract=contract)
        self.assertEqual("VERIFY_STARTUP_SOURCE", caught.exception.step)
        self.assertEqual([], tools.events)

    def test_equal_baseline_and_desired_digest_still_applies_startup_only_change(self):
        tools = StartupTools()
        tools.deployment["imageDigest"] = DIGEST
        result = self.run_policy(tools)
        self.assertEqual("CONTROLLED_HANDOFF_COMPLETED", result["status"])
        request = next(request for step, request in tools.requests if step == "MUTATE_CANONICAL")
        self.assertEqual(DIGEST, request["expectedImage"])
        self.assertIsNone(request["expectedStartupProbe"])
        self.assertEqual(PROBE, tools.deployment["startupProbe"])

    def test_uncertain_failed_mutation_with_equal_digest_accepts_owned_previous_probe_for_fallback(self):
        class BeforeMutationFailure(StartupTools):
            def __call__(self, step, request):
                if step == "MUTATE_CANONICAL":
                    self.events.append(step)
                    self.requests.append((step, copy.deepcopy(request)))
                    return dict(exitCode=79, receipt={})
                return super().__call__(step, request)
        tools = BeforeMutationFailure()
        tools.deployment["imageDigest"] = DIGEST
        with self.assertRaises(HandoffFailure) as caught:
            self.run_policy(tools)
        self.assertEqual(79, caught.exception.exit_code)
        self.assertFalse(caught.exception.fallback_blocked)
        self.assertEqual("green", tools.service["selector"])
        self.assertIsNone(tools.deployment["startupProbe"])
        self.assertEqual(PROBE, tools.green["startupProbe"])

    def test_foreign_existing_probe_rejects_before_image_and_green(self):
        tools = StartupTools(previous=dict(exec=dict(command=["private-value"])))
        with self.assertRaises(HandoffFailure) as caught:
            self.run_policy(tools)
        self.assertEqual("SNAPSHOT", caught.exception.step)
        self.assertNotIn("VERIFY_IMAGE", tools.events)
        self.assertNotIn("CREATE_GREEN", tools.events)
        self.assertNotIn("private-value", str(caught.exception))

    def test_green_probe_absence_or_bad_budget_blocks_routing(self):
        for missing in (True, False):
            def fault(tools, step, receipt):
                if step == "VERIFY_GREEN":
                    if missing:
                        receipt.pop("startupProbe", None)
                    else:
                        receipt["startupProbe"]["periodSeconds"] = 50
            tools = StartupTools(fault=fault)
            with self.subTest(missing=missing), self.assertRaises(HandoffFailure) as caught:
                self.run_policy(tools)
            self.assertEqual("VERIFY_GREEN", caught.exception.step)
            self.assertNotIn("ROUTE_GREEN", tools.events)
            self.assertNotIn("MUTATE_CANONICAL", tools.events)

    def test_concurrent_probe_change_rejects_before_canonical_mutation(self):
        def fault(tools, step, receipt):
            if step == "READ_CURRENT":
                receipt["deployment"]["startupProbe"] = copy.deepcopy(PROBE)
        tools = StartupTools(fault=fault)
        with self.assertRaises(HandoffFailure) as caught:
            self.run_policy(tools)
        self.assertEqual("READ_CURRENT", caught.exception.step)
        self.assertNotIn("MUTATE_CANONICAL", tools.events)

    def test_canonical_missing_probe_rejects_and_preserves_proven_green(self):
        def fault(tools, step, receipt):
            if step == "VERIFY_CANONICAL":
                receipt.pop("startupProbe", None)
        tools = StartupTools(fault=fault)
        with self.assertRaises(HandoffFailure) as caught:
            self.run_policy(tools)
        self.assertEqual("VERIFY_CANONICAL", caught.exception.step)
        self.assertFalse(caught.exception.fallback_blocked)
        self.assertEqual("green", tools.service["selector"])
        self.assertNotIn("DRAIN_GREEN", tools.events)

    def test_stateful_canonical_probe_failure_after_routing_retains_owned_green(self):
        for corruption in ("missing", "corrupt"):
            def fault(tools, step, receipt):
                if step == "ROUTE_CANONICAL":
                    if corruption == "missing":
                        tools.deployment.pop("startupProbe", None)
                    else:
                        tools.deployment["startupProbe"] = dict(exec=dict(command=["private-value"]))
            tools = StartupTools(fault=fault)
            with self.subTest(corruption=corruption), self.assertRaises(HandoffFailure) as caught:
                self.run_policy(tools)
            self.assertEqual("VERIFY_CANONICAL", caught.exception.step)
            self.assertFalse(caught.exception.fallback_blocked)
            self.assertEqual("green", tools.service["selector"])
            self.assertNotIn("DRAIN_GREEN", tools.events)
            self.assertEqual(PROBE, tools.green["startupProbe"])

    def test_foreign_canonical_identity_still_blocks_fallback(self):
        def fault(tools, step, receipt):
            if step == "ROUTE_CANONICAL":
                tools.deployment["uid"] = "55555555-5555-4555-8555-555555555555"
        tools = StartupTools(fault=fault)
        with self.assertRaises(HandoffFailure) as caught:
            self.run_policy(tools)
        self.assertTrue(caught.exception.fallback_blocked)
        self.assertNotIn("DRAIN_GREEN", tools.events)

    def test_null_and_owned_previous_probe_are_available_on_failure(self):
        for previous in (None, dict(PROBE, initialDelaySeconds=0)):
            tools = StartupTools(previous=previous, fail="CANONICAL_HEALTH")
            with self.subTest(previous=previous), self.assertRaises(HandoffFailure) as caught:
                self.run_policy(tools)
            self.assertTrue(caught.exception.startup_rollback_available)
            self.assertEqual(previous, caught.exception.previous_startup_probe)
            self.assertFalse(caught.exception.fallback_blocked)

    def test_unrelated_application_receives_no_startup_injection(self):
        tools = StartupTools(previous=dict(exec=dict(command=["existing-owner"])))
        result = run_handoff("Legacy.Maliev.CountryService", COMMIT, DIGEST, tools, startup_contract=copy.deepcopy(CONTRACT))
        self.assertFalse(result["runtimeAccepted"])
        for step, request in tools.requests:
            self.assertNotIn("startupProbe", request)
            self.assertNotIn("expectedStartupProbe", request)


if __name__ == "__main__":
    unittest.main()
