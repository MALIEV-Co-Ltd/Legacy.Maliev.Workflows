"""Controlled injected-tool state tests; never invokes a deployment client."""
import copy
import importlib.util
import pathlib
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts/application_handoff_policy.py"
COMMIT = "1" * 40
DIGEST = "sha256:" + "2" * 64
OLD = "sha256:" + "3" * 64
UID = "11111111-1111-1111-1111-111111111111"
SERVICE = "22222222-2222-2222-2222-222222222222"
GREEN = "33333333-3333-3333-3333-333333333333"
RESERVATION = "44444444-4444-4444-4444-444444444444"


class FakeTools:
    def __init__(self, fail=None, mutate=None, replicas=1):
        self.events = []
        self.requests = []
        self.fail = fail
        self.mutate = mutate
        self.deployment = dict(uid=UID, imageDigest=OLD, replicas=replicas, ready=replicas, available=replicas, settingsSignature="original")
        self.service = dict(uid=SERVICE, resourceVersion="1", selector="original", selectorUid=UID, portsSignature="preserved")
        self.green = None
        self.capacity = replicas + 1
        self.reserved = 0
        self.states = []

    def __call__(self, step, request):
        self.events.append(step)
        self.requests.append((step, copy.deepcopy(request)))
        receipt = {}
        if step in ("SNAPSHOT", "READ_CURRENT"):
            receipt = dict(deployment=copy.deepcopy(self.deployment), service=copy.deepcopy(self.service))
        elif step == "VERIFY_SOURCE":
            receipt = dict(sourceCommit=COMMIT)
        elif step == "VERIFY_IMAGE":
            receipt = dict(sourceCommit=COMMIT, imageDigest=DIGEST, immutable=True)
        elif step in ("RESERVE_CAPACITY", "RECHECK_CAPACITY"):
            if step == "RESERVE_CAPACITY":
                self.reserved = request["additionalSlots"]
            receipt = dict(availableSlots=self.capacity, reservedSlots=self.reserved, reservationId=RESERVATION)
        elif step == "CREATE_GREEN":
            count = request["replicas"]
            self.green = dict(uid=GREEN, runId=request["runId"], imageDigest=DIGEST, replicas=count, ready=count, available=count, rollout=copy.deepcopy(request["rollout"]))
            receipt = copy.deepcopy(self.green)
        elif step in ("VERIFY_GREEN", "VERIFY_CANONICAL", "VERIFY_FALLBACK"):
            item = self.deployment if step == "VERIFY_CANONICAL" else self.green
            receipt = dict(**copy.deepcopy(item), processVerified=True, standbyVerified=step != "VERIFY_CANONICAL", readOnlyStartupVerified=True)
        elif step in ("ROUTE_GREEN", "ROUTE_CANONICAL", "ROLLBACK_SELECTOR", "FALLBACK_SELECTOR"):
            assert request["service"] == self.service, "CAS expected snapshot differs from simulated service"
            self.service["selector"] = request["selector"]
            self.service["selectorUid"] = request.get("targetDeploymentUid", GREEN if request["selector"] == "green" else UID)
            self.service["resourceVersion"] = str(int(self.service["resourceVersion"]) + 1)
            receipt = copy.deepcopy(self.service)
        elif step == "BEFORE_FIRST_SELECTOR":
            assert self.service["selector"] == "original"
            receipt = dict(imageDigest=self.green["imageDigest"], deploymentUid=self.green["uid"], continuousPublicHealthy=True, endpointsVerified=True, observedSeconds=0)
        elif step in ("GREEN_HEALTH", "CANONICAL_HEALTH", "FINAL_HEALTH"):
            assert self.service["selector"] == ("green" if step == "GREEN_HEALTH" else "original")
            receipt = dict(imageDigest=DIGEST, publicHealthy=True, endpointsVerified=True, observedSeconds=180, processRouteVerified=True, deploymentUid=self.service["selectorUid"])
        elif step == "MUTATE_CANONICAL":
            assert self.service["selector"] == "green" and self.green["ready"] == self.deployment["replicas"]
            self.deployment.update(imageDigest=DIGEST, settingsSignature="owned-rollout", rollout=copy.deepcopy(request["rollout"]))
            receipt = copy.deepcopy(self.deployment)
        elif step == "DRAIN_GREEN":
            assert request["greenUid"] == self.green["uid"] and request["runId"] == self.green["runId"]
            self.green = None
            receipt = dict(greenUid=GREEN, remainingProcesses=0, ownedDeleted=True)
        elif step == "RELEASE_CAPACITY":
            assert self.green is None
            self.reserved = 0
            receipt = dict(reservationId=RESERVATION, released=True)
        else:
            raise AssertionError("Unreviewed operation")
        if self.mutate:
            self.mutate(step, receipt, self)
        self.states.append(dict(step=step, originalReady=self.deployment["ready"], originalAvailable=self.deployment["available"], selector=self.service["selector"], image=self.deployment["imageDigest"]))
        return dict(exitCode=73 if self.fail == step else 0, receipt=receipt)


class PolicyTests(unittest.TestCase):
    def run_policy(self, tools, **kwargs):
        self.assertTrue(SCRIPT.is_file(), "Reviewed handoff policy is absent")
        spec = importlib.util.spec_from_file_location("handoff_policy", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.module = module
        return module.run_handoff("Legacy.Maliev.NotificationService", COMMIT, DIGEST, tools, **kwargs)

    def test_success_order_and_independent_state(self):
        tools = FakeTools()
        receipt = self.run_policy(tools)
        self.assertEqual("CONTROLLED_HANDOFF_COMPLETED", receipt["status"])
        self.assertFalse(receipt["runtimeAccepted"])
        self.assertLess(tools.events.index("VERIFY_IMAGE"), tools.events.index("CREATE_GREEN"))
        self.assertLess(tools.events.index("GREEN_HEALTH"), tools.events.index("MUTATE_CANONICAL"))
        self.assertLess(tools.events.index("CANONICAL_HEALTH"), tools.events.index("DRAIN_GREEN"))
        self.assertEqual(DIGEST, tools.deployment["imageDigest"])
        self.assertEqual("original", tools.service["selector"])
        self.assertIsNone(tools.green)
        self.assertEqual(0, tools.reserved)
        self.assertTrue(all(s["originalReady"] == 1 and s["originalAvailable"] == 1 for s in tools.states))

    def test_each_nonzero_failure_propagates(self):
        phases = ["SNAPSHOT", "VERIFY_SOURCE", "VERIFY_IMAGE", "RESERVE_CAPACITY", "CREATE_GREEN", "VERIFY_GREEN", "BEFORE_FIRST_SELECTOR", "ROUTE_GREEN", "GREEN_HEALTH", "RECHECK_CAPACITY", "MUTATE_CANONICAL", "VERIFY_CANONICAL", "ROUTE_CANONICAL", "CANONICAL_HEALTH", "DRAIN_GREEN", "FINAL_HEALTH", "RELEASE_CAPACITY"]
        for phase in phases:
            with self.subTest(phase=phase):
                tools = FakeTools(fail=phase)
                with self.assertRaises(Exception) as caught:
                    self.run_policy(tools)
                self.assertEqual(73, getattr(caught.exception, "exit_code", None))
                self.assertEqual(phase, getattr(caught.exception, "step", None))

    def test_image_proof_failure_has_no_workload_mutation(self):
        def fault(step, receipt, tools):
            if step == "VERIFY_IMAGE":
                receipt["imageDigest"] = OLD
        tools = FakeTools(mutate=fault)
        with self.assertRaises(Exception):
            self.run_policy(tools)
        self.assertNotIn("CREATE_GREEN", tools.events)
        self.assertEqual(OLD, tools.deployment["imageDigest"])

    def test_capacity_refusal_preserves_original(self):
        tools = FakeTools()
        tools.capacity = 1
        with self.assertRaises(Exception):
            self.run_policy(tools)
        self.assertNotIn("CREATE_GREEN", tools.events)
        self.assertEqual(1, tools.deployment["ready"])

    def test_capacity_loss_before_surge_restores_original_selector(self):
        def fault(step, receipt, tools):
            if step == "RECHECK_CAPACITY":
                receipt["availableSlots"] = 0
        tools = FakeTools(mutate=fault)
        with self.assertRaises(Exception):
            self.run_policy(tools)
        self.assertNotIn("MUTATE_CANONICAL", tools.events)
        self.assertEqual("original", tools.service["selector"])

    def test_initial_handoff_failure_rolls_back_healthy_baseline(self):
        tools = FakeTools(fail="GREEN_HEALTH")
        with self.assertRaises(Exception):
            self.run_policy(tools)
        self.assertIn("ROLLBACK_SELECTOR", tools.events)
        self.assertEqual(OLD, tools.deployment["imageDigest"])
        self.assertEqual("original", tools.service["selector"])

    def test_canonical_failure_forbids_old_image_rollback(self):
        tools = FakeTools(fail="MUTATE_CANONICAL")
        with self.assertRaises(Exception) as caught:
            self.run_policy(tools)
        self.assertTrue(getattr(caught.exception, "canonical_mutation_started", False))
        self.assertNotIn("ROLLBACK_SELECTOR", tools.events)
        self.assertEqual(DIGEST, tools.deployment["imageDigest"])
        self.assertEqual("green", tools.service["selector"])

    def test_late_failure_routes_to_verified_owned_green(self):
        tools = FakeTools(fail="CANONICAL_HEALTH")
        with self.assertRaises(Exception):
            self.run_policy(tools)
        self.assertIn("VERIFY_FALLBACK", tools.events)
        self.assertIn("FALLBACK_SELECTOR", tools.events)
        self.assertEqual("green", tools.service["selector"])

    def test_wrong_green_identity_blocks_fallback(self):
        def fault(step, receipt, tools):
            if step == "VERIFY_FALLBACK":
                receipt["uid"] = UID
        tools = FakeTools(fail="CANONICAL_HEALTH", mutate=fault)
        with self.assertRaises(Exception) as caught:
            self.run_policy(tools)
        self.assertTrue(getattr(caught.exception, "fallback_blocked", False))
        self.assertNotIn("FALLBACK_SELECTOR", tools.events)

    def test_unhealthy_canonical_after_switch_routes_to_proven_green(self):
        def fault(step, receipt, tools):
            if step == "CANONICAL_HEALTH":
                tools.deployment.update(ready=0, available=0)
        tools = FakeTools(fail="CANONICAL_HEALTH", mutate=fault)
        with self.assertRaises(Exception) as caught:
            self.run_policy(tools)
        self.assertEqual(73, caught.exception.exit_code)
        self.assertFalse(caught.exception.fallback_blocked)
        self.assertIn("FALLBACK_SELECTOR", tools.events)
        self.assertEqual("green", tools.service["selector"])
        self.assertEqual(GREEN, tools.service["selectorUid"])
        self.assertIsNotNone(tools.green)
        self.assertNotIn("ROLLBACK_SELECTOR", tools.events)

    def test_unhealthy_foreign_canonical_blocks_green_fallback(self):
        for change in ({"uid": SERVICE}, {"imageDigest": "sha256:" + "4" * 64}, {"replicas": 2}):
            with self.subTest(change=change):
                def fault(step, receipt, tools):
                    if step == "CANONICAL_HEALTH":
                        tools.deployment.update(ready=0, available=0, **change)
                tools = FakeTools(fail="CANONICAL_HEALTH", mutate=fault)
                with self.assertRaises(Exception) as caught:
                    self.run_policy(tools)
                self.assertEqual(73, caught.exception.exit_code)
                self.assertTrue(caught.exception.fallback_blocked)
                self.assertNotIn("FALLBACK_SELECTOR", tools.events)

    def test_insufficient_health_observation_rejects(self):
        def fault(step, receipt, tools):
            if step == "GREEN_HEALTH":
                receipt["observedSeconds"] = 179
        with self.assertRaises(Exception):
            self.run_policy(FakeTools(mutate=fault))

    def test_missing_read_only_proof_rejects_when_owner_requires_it(self):
        def fault(step, receipt, tools):
            if step == "VERIFY_GREEN":
                receipt["readOnlyStartupVerified"] = False
        with self.assertRaises(Exception):
            self.run_policy(FakeTools(mutate=fault), require_read_only_startup=True)

    def test_wrong_selector_target_uid_rejected(self):
        def fault(step, receipt, tools):
            if step == "ROUTE_GREEN":
                receipt["selectorUid"] = UID
        with self.assertRaises(Exception):
            self.run_policy(FakeTools(mutate=fault))

    def test_wrong_owned_rollout_settings_rejected(self):
        def fault(step, receipt, tools):
            if step == "VERIFY_CANONICAL":
                receipt["rollout"]["maxUnavailable"] = 1
        with self.assertRaises(Exception):
            self.run_policy(FakeTools(mutate=fault))

    def test_changed_service_identity_blocks_cas(self):
        def fault(step, receipt, tools):
            if step == "READ_CURRENT":
                receipt["service"]["uid"] = GREEN
        tools = FakeTools(mutate=fault)
        with self.assertRaises(Exception):
            self.run_policy(tools)
        self.assertNotIn("ROUTE_GREEN", tools.events)
        self.assertNotIn("MUTATE_CANONICAL", tools.events)

    def test_unhealthy_original_rejects_before_image(self):
        tools = FakeTools()
        tools.deployment["available"] = 0
        with self.assertRaises(Exception):
            self.run_policy(tools)
        self.assertNotIn("VERIFY_IMAGE", tools.events)

    def test_raw_callback_failure_redacted(self):
        def tool(step, request):
            raise ValueError("owned-private-output-canary")
        with self.assertRaises(Exception) as caught:
            self.run_policy(tool)
        self.assertNotIn("owned-private-output-canary", str(caught.exception))

    def test_callback_policy_exception_cannot_bypass_redaction_or_exit_bounds(self):
        def tool(step, request):
            raise self.module.HandoffFailure("owned-private-output-canary", -73)
        with self.assertRaises(Exception) as caught:
            self.run_policy(tool)
        self.assertNotIn("owned-private-output-canary", str(caught.exception))
        self.assertEqual("SNAPSHOT", caught.exception.step)
        self.assertEqual(1, caught.exception.exit_code)

    def test_oversized_receipt_rejected(self):
        def fault(step, receipt, tools):
            if step == "VERIFY_IMAGE":
                receipt["unused"] = "x" * 16385
        with self.assertRaises(Exception):
            self.run_policy(FakeTools(mutate=fault))

    def test_foreign_selector_target_blocks_rollback(self):
        def fault(step, receipt, tools):
            if step == "GREEN_HEALTH":
                tools.service["selectorUid"] = SERVICE
        tools = FakeTools(fail="GREEN_HEALTH", mutate=fault)
        with self.assertRaises(Exception) as caught:
            self.run_policy(tools)
        self.assertTrue(getattr(caught.exception, "fallback_blocked", False))
        self.assertNotIn("ROLLBACK_SELECTOR", tools.events)

    def test_wrong_green_replica_count_rejects_before_routing(self):
        def fault(step, receipt, tools):
            if step == "VERIFY_GREEN":
                receipt.update(replicas=2, ready=2, available=2)
        tools = FakeTools(mutate=fault)
        with self.assertRaises(Exception):
            self.run_policy(tools)
        self.assertNotIn("ROUTE_GREEN", tools.events)
        self.assertNotIn("MUTATE_CANONICAL", tools.events)

    def test_wrong_canonical_replica_count_rejects_before_canonical_routing(self):
        def fault(step, receipt, tools):
            if step == "VERIFY_CANONICAL":
                receipt.update(replicas=2, ready=2, available=2)
        tools = FakeTools(mutate=fault)
        with self.assertRaises(Exception):
            self.run_policy(tools)
        self.assertNotIn("ROUTE_CANONICAL", tools.events)

    def test_large_numeric_service_revision_preserves_exact_cas_token(self):
        tools = FakeTools()
        tools.service["resourceVersion"] = "1" + "0" * 40
        receipt = self.run_policy(tools)
        self.assertEqual("CONTROLLED_HANDOFF_COMPLETED", receipt["status"])

    def test_baseline_capacity_is_preserved_for_green_and_canonical(self):
        for count in (1, 3, 10):
            with self.subTest(replicas=count):
                tools = FakeTools(replicas=count)
                receipt = self.run_policy(tools)
                requests = dict(tools.requests)
                self.assertEqual("CONTROLLED_HANDOFF_COMPLETED", receipt["status"])
                self.assertEqual(count, requests["CREATE_GREEN"]["replicas"])
                self.assertEqual(count + 1, requests["RESERVE_CAPACITY"]["additionalSlots"])
                self.assertEqual(2 * count + 1, requests["RESERVE_CAPACITY"]["peakReplicas"])
                self.assertEqual(count, tools.deployment["replicas"])
                self.assertTrue(all(s["originalReady"] == count and s["originalAvailable"] == count for s in tools.states))
                self.assertEqual(GREEN, requests["GREEN_HEALTH"]["deploymentUid"])
                self.assertEqual(UID, requests["CANONICAL_HEALTH"]["deploymentUid"])
                self.assertEqual(UID, requests["FINAL_HEALTH"]["deploymentUid"])

    def test_missing_false_or_foreign_process_route_proof_fails_at_actual_gate(self):
        for phase in ("GREEN_HEALTH", "CANONICAL_HEALTH", "FINAL_HEALTH"):
            for change in ({"processRouteVerified": None}, {"processRouteVerified": False}, {"processRouteVerified": "true"}, {"deploymentUid": SERVICE}):
                with self.subTest(phase=phase, change=change):
                    def fault(step, receipt, tools):
                        if step == phase:
                            receipt.update(change)
                    tools = FakeTools(replicas=3, mutate=fault)
                    with self.assertRaises(Exception) as caught:
                        self.run_policy(tools)
                    self.assertEqual(phase, caught.exception.step)
                    self.assertEqual(1, caught.exception.exit_code)
                    self.assertEqual(3, tools.deployment["replicas"])
                    if phase == "GREEN_HEALTH":
                        self.assertNotIn("MUTATE_CANONICAL", tools.events)
                        self.assertEqual("original", tools.service["selector"])
                    elif phase == "CANONICAL_HEALTH":
                        self.assertNotIn("DRAIN_GREEN", tools.events)
                        self.assertEqual("green", tools.service["selector"])
                    else:
                        self.assertTrue(caught.exception.fallback_blocked)
                        self.assertNotIn("RELEASE_CAPACITY", tools.events)

    def test_capacity_and_owned_replica_admission_rejects_without_original_scale_down(self):
        for mode in ("unavailable", "short-reservation", "lost-reservation", "short-green"):
            with self.subTest(mode=mode):
                def fault(step, receipt, tools):
                    if mode == "unavailable" and step == "RESERVE_CAPACITY":
                        receipt["availableSlots"] = 3
                    if mode == "short-reservation" and step == "RESERVE_CAPACITY":
                        receipt["reservedSlots"] = 3
                    if mode == "lost-reservation" and step == "RECHECK_CAPACITY":
                        receipt["reservedSlots"] = 3
                    if mode == "short-green" and step == "VERIFY_GREEN":
                        receipt.update(replicas=1, ready=1, available=1)
                tools = FakeTools(replicas=3, mutate=fault)
                with self.assertRaises(Exception):
                    self.run_policy(tools)
                self.assertNotIn("MUTATE_CANONICAL", tools.events)
                self.assertEqual(3, tools.deployment["replicas"])
                self.assertEqual(3, tools.deployment["ready"])
                self.assertEqual("original", tools.service["selector"])

    def test_replica_inventory_bound_rejects_before_image_or_capacity_requests(self):
        for count in (0, 11, True):
            with self.subTest(replicas=count):
                tools = FakeTools(replicas=count)
                with self.assertRaises(Exception) as caught:
                    self.run_policy(tools)
                self.assertEqual("SNAPSHOT", caught.exception.step)
                self.assertNotIn("VERIFY_IMAGE", tools.events)
                self.assertNotIn("RESERVE_CAPACITY", tools.events)

    def test_multi_replica_canonical_failure_retains_proven_owned_green_capacity(self):
        tools = FakeTools(replicas=3, fail="CANONICAL_HEALTH")
        with self.assertRaises(Exception) as caught:
            self.run_policy(tools)
        self.assertEqual(73, caught.exception.exit_code)
        self.assertFalse(caught.exception.fallback_blocked)
        self.assertEqual("green", tools.service["selector"])
        self.assertEqual(3, tools.green["ready"])
        self.assertEqual(3, tools.green["replicas"])
        self.assertEqual(4, tools.reserved)
        self.assertNotIn("DRAIN_GREEN", tools.events)


    def test_preselector_nonzero_blocks_first_selector(self):
        tools = FakeTools(fail="BEFORE_FIRST_SELECTOR")
        with self.assertRaises(Exception) as caught:
            self.run_policy(tools)
        self.assertEqual("BEFORE_FIRST_SELECTOR", caught.exception.step)
        self.assertEqual(73, caught.exception.exit_code)
        self.assertNotIn("ROUTE_GREEN", tools.events)
        self.assertNotIn("MUTATE_CANONICAL", tools.events)
        self.assertEqual(OLD, tools.deployment["imageDigest"])

    def test_preselector_invalid_proof_blocks_first_selector(self):
        faults = [("continuousPublicHealthy", None), ("continuousPublicHealthy", False),
                  ("continuousPublicHealthy", 1), ("endpointsVerified", None),
                  ("endpointsVerified", False), ("deploymentUid", UID),
                  ("imageDigest", OLD), ("observedSeconds", None),
                  ("observedSeconds", True), ("observedSeconds", -1),
                  ("observedSeconds", 3601), ("observedSeconds", "0")]
        for field, value in faults:
            with self.subTest(field=field, value=value):
                def fault(step, receipt, tools):
                    if step == "BEFORE_FIRST_SELECTOR":
                        if value is None:
                            receipt.pop(field, None)
                        else:
                            receipt[field] = value
                tools = FakeTools(mutate=fault)
                with self.assertRaises(Exception) as caught:
                    self.run_policy(tools)
                self.assertEqual("BEFORE_FIRST_SELECTOR", caught.exception.step)
                self.assertNotIn("ROUTE_GREEN", tools.events)
                self.assertNotIn("MUTATE_CANONICAL", tools.events)

    def test_preselector_zero_seconds_and_unrouted_green_allowed(self):
        tools = FakeTools()
        self.run_policy(tools)
        index = tools.events.index("BEFORE_FIRST_SELECTOR")
        self.assertEqual("VERIFY_GREEN", tools.events[index - 1])
        self.assertEqual(["READ_CURRENT", "ROUTE_GREEN"], tools.events[index + 1:index + 3])
        request = tools.requests[index][1]
        self.assertEqual(0, request["minimumSeconds"])
        self.assertEqual(GREEN, request["deploymentUid"])
        self.assertEqual("original", tools.states[index]["selector"])
        for step, request in tools.requests:
            if step in ("GREEN_HEALTH", "CANONICAL_HEALTH", "FINAL_HEALTH"):
                self.assertEqual(180, request["minimumSeconds"])

    def test_preselector_observer_service_change_is_freshly_read(self):
        def fault(step, receipt, tools):
            if step == "BEFORE_FIRST_SELECTOR":
                tools.service["resourceVersion"] = "9"
        tools = FakeTools(mutate=fault)
        self.run_policy(tools)
        self.assertIn("BEFORE_FIRST_SELECTOR", tools.events)
        route = next(request for step, request in tools.requests if step == "ROUTE_GREEN")
        self.assertEqual("9", route["service"]["resourceVersion"])

    def test_preselector_observer_selector_race_blocks_first_selector(self):
        def fault(step, receipt, tools):
            if step == "BEFORE_FIRST_SELECTOR":
                tools.service.update(selector="green", selectorUid=GREEN, resourceVersion="9")
        tools = FakeTools(mutate=fault)
        with self.assertRaises(Exception) as caught:
            self.run_policy(tools)
        self.assertEqual("READ_CURRENT", caught.exception.step)
        self.assertNotIn("ROUTE_GREEN", tools.events)
        self.assertNotIn("MUTATE_CANONICAL", tools.events)

if __name__ == "__main__":
    unittest.main()
