import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from application_handoff_policy import HandoffFailure, run_handoff
from test_application_handoff_policy import COMMIT, DIGEST, GREEN, FakeTools
from test_green_metadata import CONTRACT, METADATA
from startup_protection import SOURCE_SHA as STARTUP_SOURCE
from green_metadata import decode_green_metadata, MetadataRejected


class GreenTools(FakeTools):
    """Consume actual requests and prove stored state, without a physical adapter."""
    def __init__(self, *, metadata=None, fault=None, mutation_fault=None, **changes):
        super().__init__(**changes)
        self.deployment["greenMetadata"] = copy.deepcopy(METADATA if metadata is None else metadata)
        self.deployment["startupProbe"] = None
        self.metadata_fault = fault
        self.mutation_fault = mutation_fault

    def __call__(self, step, request):
        if step == "MUTATE_CANONICAL" and self.mutation_fault:
            self.mutation_fault(self)
        if step == "MUTATE_CANONICAL" and "expectedGreenMetadataPlan" in request:
            same = lambda left, right: json.dumps(left, sort_keys=True) == json.dumps(right, sort_keys=True)
            if (request["greenDeploymentUid"] != self.green["uid"]
                or request["deploymentUid"] != self.deployment["uid"]
                or request["expectedImage"] != self.deployment["imageDigest"]
                or not same(request["service"], self.service)
                or type(self.deployment["replicas"]) is not int or self.deployment["replicas"] != request["expectedCanonicalReplicas"]
                or type(self.green["replicas"]) is not int or self.green["replicas"] != request["expectedGreenReplicas"]
                or not same(request["expectedGreenMetadataPlan"], self.green["greenMetadataPlan"])
                or not same(request["expectedCanonicalMetadata"], self.deployment.get("greenMetadata"))):
                self.events.append(step)
                self.requests.append((step, copy.deepcopy(request)))
                return dict(exitCode=91, receipt={})
        response = super().__call__(step, request)
        if step == "CREATE_GREEN" and "greenMetadataPlan" in request:
            self.green["greenMetadataPlan"] = copy.deepcopy(request["greenMetadataPlan"])
            response["receipt"]["greenMetadataPlan"] = copy.deepcopy(self.green["greenMetadataPlan"])
        if step == "CREATE_GREEN" and "startupProbe" in request:
            self.green["startupProbe"] = copy.deepcopy(request["startupProbe"])
            response["receipt"]["startupProbe"] = copy.deepcopy(self.green["startupProbe"])
        if step == "MUTATE_CANONICAL" and "startupProbe" in request:
            self.deployment["startupProbe"] = copy.deepcopy(request["startupProbe"])
            response["receipt"]["startupProbe"] = copy.deepcopy(self.deployment["startupProbe"])
        if self.metadata_fault:
            self.metadata_fault(self, step, response["receipt"])
        return response


class GreenHandoffTests(unittest.TestCase):
    def run_policy(self, tools, **changes):
        return run_handoff(CONTRACT["target_application"], COMMIT, DIGEST, tools, green_contract=copy.deepcopy(CONTRACT), **changes)

    def test_selected_json_observation_flows_through_actual_handoff_consumer(self):
        for startup in ("absent", None, copy.deepcopy(METADATA["containerMetadata"]["readinessProbe"])):
            metadata = copy.deepcopy(METADATA)
            if startup != "absent":
                metadata["containerMetadata"]["startupProbe"] = startup
            def encode(tools, step, receipt):
                if step in ("SNAPSHOT", "READ_CURRENT"):
                    receipt["deployment"]["greenMetadata"] = json.dumps(receipt["deployment"]["greenMetadata"], ensure_ascii=False)
            tools = GreenTools(metadata=metadata, fault=encode)
            result = self.run_policy(tools)
            self.assertFalse(result["runtimeAccepted"])
            request = next(value for step, value in tools.requests if step == "CREATE_GREEN")
            container = request["greenMetadataPlan"]["pod"]["containers"][0]
            self.assertEqual(metadata["containerMetadata"]["envFrom"], container["envFrom"])
            self.assertEqual(metadata["podMetadata"]["imagePullSecrets"], request["greenMetadataPlan"]["pod"]["imagePullSecrets"])
            mutation = next(value for step, value in tools.requests if step == "MUTATE_CANONICAL")
            self.assertEqual(metadata, mutation["expectedCanonicalMetadata"])
            self.assertEqual(startup != "absent", "startupProbe" in mutation["expectedCanonicalMetadata"]["containerMetadata"])

    def test_malformed_selected_json_rejects_before_source_or_image_callbacks(self):
        for payload in ('{"private":"SYNTHETIC_PRIVATE"', '{"containerNames":[],"containerNames":[]}', 'null', '[]', '{"value":NaN}', '"' + ('x' * 16384) + '"'):
            def corrupt(tools, step, receipt):
                if step == "SNAPSHOT":
                    receipt["deployment"]["greenMetadata"] = payload
            tools = GreenTools(fault=corrupt)
            with self.assertRaises(HandoffFailure) as caught:
                self.run_policy(tools)
            self.assertEqual("SNAPSHOT", caught.exception.step)
            self.assertNotIn("SYNTHETIC_PRIVATE", str(caught.exception))
            self.assertNotIn("VERIFY_SOURCE", tools.events)
            self.assertNotIn("VERIFY_IMAGE", tools.events)

    def test_unsafe_selected_json_shapes_reject_before_verification_callbacks(self):
        for case in ("readiness", "liveness", "envFrom", "pullSecrets", "tolerations", "reference", "literal", "probe"):
            metadata = copy.deepcopy(METADATA)
            if case in ("readiness", "liveness"):
                del metadata["containerMetadata"][case + "Probe"]
            elif case == "envFrom":
                metadata["containerMetadata"]["envFrom"] = {"configMapRef": {"name": "owned-config"}}
            elif case == "pullSecrets":
                metadata["podMetadata"]["imagePullSecrets"] = {"name": "existing-pull"}
            elif case == "tolerations":
                metadata["podMetadata"]["tolerations"] = {"key": "owned"}
            elif case == "reference":
                metadata["environment"][1]["valueFrom"] = "SYNTHETIC_PRIVATE"
            elif case == "literal":
                metadata["environment"][1] = {"name": "CONNECTION", "value": "SYNTHETIC_PRIVATE"}
            else:
                metadata["containerMetadata"]["startupProbe"] = {"httpGet": {"port": 8080}, "exec": {"command": ["SYNTHETIC_PRIVATE"]}}
            def encode(tools, step, receipt):
                if step == "SNAPSHOT":
                    receipt["deployment"]["greenMetadata"] = json.dumps(metadata)
            tools = GreenTools(fault=encode)
            with self.assertRaises(HandoffFailure) as caught:
                self.run_policy(tools)
            self.assertEqual("SNAPSHOT", caught.exception.step)
            self.assertNotIn("SYNTHETIC_PRIVATE", str(caught.exception))
            self.assertNotIn("VERIFY_SOURCE", tools.events)
            self.assertNotIn("VERIFY_IMAGE", tools.events)
            self.assertNotIn("CREATE_GREEN", tools.events)

    def test_parser_refusal_does_not_retain_private_json_exception_context(self):
        with self.assertRaises(MetadataRejected) as caught:
            decode_green_metadata('{"value":"SYNTHETIC_PRIVATE"')
        self.assertIsNone(caught.exception.__context__)
        self.assertIsNone(caught.exception.__cause__)
        self.assertNotIn("SYNTHETIC_PRIVATE", str(caught.exception))

    def test_changed_selected_json_readback_blocks_before_routing(self):
        def change(tools, step, receipt):
            if step == "READ_CURRENT":
                metadata = receipt["deployment"]["greenMetadata"]
                metadata["podMetadata"]["imagePullSecrets"] = {"name": "changed"}
                receipt["deployment"]["greenMetadata"] = json.dumps(metadata)
        tools = GreenTools(fault=change)
        with self.assertRaises(HandoffFailure) as caught:
            self.run_policy(tools)
        self.assertEqual("READ_CURRENT", caught.exception.step)
        self.assertNotIn("ROUTE_GREEN", tools.events)


    def test_actual_create_request_and_stored_green_proof_keep_complete_plan(self):
        tools = GreenTools()
        result = self.run_policy(tools)
        self.assertFalse(result["runtimeAccepted"])
        self.assertFalse(result["consumerAdoptionAccepted"])
        request = next(request for step, request in tools.requests if step == "CREATE_GREEN")
        container = request["greenMetadataPlan"]["pod"]["containers"][0]
        self.assertEqual(METADATA["environment"][1], container["env"][1])
        self.assertEqual(METADATA["containerMetadata"]["ports"], container["ports"])
        self.assertEqual(DIGEST, container["imageDigest"])
        self.assertFalse(tools.deployment["greenMetadata"]["podMetadata"]["automountServiceAccountToken"])

    def test_bad_mapping_rejects_before_any_injected_callback(self):
        tools = GreenTools()
        with self.assertRaises(HandoffFailure) as caught:
            run_handoff(CONTRACT["target_application"], COMMIT, DIGEST, tools, green_contract=dict(CONTRACT, artifact="foreign"))
        self.assertEqual("VERIFY_GREEN_SOURCE", caught.exception.step)
        self.assertEqual([], tools.events)

    def test_selected_unsafe_shape_rejects_before_image_preparation_or_mutation(self):
        for field in ("initContainers", "command", "args", "volumeMounts", "volumes"):
            metadata = copy.deepcopy(METADATA)
            metadata["unsafeFields"] = [field]
            tools = GreenTools(metadata=metadata)
            with self.assertRaises(HandoffFailure) as caught:
                self.run_policy(tools)
            self.assertEqual("SNAPSHOT", caught.exception.step)
            self.assertNotIn("VERIFY_IMAGE", tools.events)
            self.assertNotIn("CREATE_GREEN", tools.events)
            self.assertNotIn("MUTATE_CANONICAL", tools.events)

    def test_missing_selected_metadata_rejects_before_source_and_image_callbacks(self):
        tools = GreenTools()
        del tools.deployment["greenMetadata"]
        with self.assertRaises(HandoffFailure):
            self.run_policy(tools)
        self.assertNotIn("VERIFY_SOURCE", tools.events)
        self.assertNotIn("VERIFY_IMAGE", tools.events)

    def test_create_readback_refusal_prevents_routing_and_canonical_mutation(self):
        for key in ("missing", "changed"):
            def fault(tools, step, receipt):
                if step == "CREATE_GREEN":
                    if key == "missing":
                        del receipt["greenMetadataPlan"]
                    else:
                        receipt["greenMetadataPlan"]["namespace"] = "foreign"
            tools = GreenTools(fault=fault)
            with self.assertRaises(HandoffFailure) as caught:
                self.run_policy(tools)
            self.assertEqual("CREATE_GREEN", caught.exception.step)
            self.assertNotIn("ROUTE_GREEN", tools.events)
            self.assertNotIn("MUTATE_CANONICAL", tools.events)

    def test_actual_stored_green_metadata_change_blocks_green_proof(self):
        def fault(tools, step, receipt):
            if step == "CREATE_GREEN":
                tools.green["greenMetadataPlan"]["pod"]["containers"][0]["env"][0]["value"] = "changed"
        tools = GreenTools(fault=fault)
        with self.assertRaises(HandoffFailure) as caught:
            self.run_policy(tools)
        self.assertEqual("VERIFY_GREEN", caught.exception.step)
        self.assertNotIn("ROUTE_GREEN", tools.events)

    def test_actual_baseline_configuration_change_blocks_before_first_selector(self):
        def fault(tools, step, receipt):
            if step == "VERIFY_IMAGE":
                tools.deployment["greenMetadata"]["podMetadata"]["automountServiceAccountToken"] = True
        tools = GreenTools(fault=fault)
        with self.assertRaises(HandoffFailure) as caught:
            self.run_policy(tools)
        self.assertEqual("READ_CURRENT", caught.exception.step)
        self.assertNotIn("ROUTE_GREEN", tools.events)
        self.assertNotIn("MUTATE_CANONICAL", tools.events)

    def test_bad_metadata_during_routed_green_blocks_canonical_mutation(self):
        def fault(tools, step, receipt):
            if step == "GREEN_HEALTH":
                tools.deployment["greenMetadata"]["containerMetadata"]["ports"] = []
        tools = GreenTools(fault=fault)
        with self.assertRaises(HandoffFailure) as caught:
            self.run_policy(tools)
        self.assertEqual("READ_CURRENT", caught.exception.step)
        self.assertNotIn("MUTATE_CANONICAL", tools.events)
        self.assertTrue(caught.exception.fallback_blocked)

    def test_failed_mutation_keeps_owned_green_fallback_with_canonical_metadata_missing(self):
        def fault(tools, step, receipt):
            if step == "MUTATE_CANONICAL":
                del tools.deployment["greenMetadata"]
                tools.deployment.update(ready=0, available=0)
        tools = GreenTools(fail="MUTATE_CANONICAL", fault=fault)
        with self.assertRaises(HandoffFailure) as caught:
            self.run_policy(tools)
        self.assertEqual(73, caught.exception.exit_code)
        self.assertFalse(caught.exception.fallback_blocked)
        self.assertEqual("green", tools.service["selector"])
        self.assertIn("VERIFY_FALLBACK", tools.events)

    def test_actual_green_metadata_change_after_canonical_route_blocks_fallback(self):
        def fault(tools, step, receipt):
            if step == "ROUTE_CANONICAL":
                tools.green["greenMetadataPlan"]["pod"]["containers"][0]["env"] = []
        tools = GreenTools(fail="CANONICAL_HEALTH", fault=fault)
        with self.assertRaises(HandoffFailure) as caught:
            self.run_policy(tools)
        self.assertTrue(caught.exception.fallback_blocked)
        self.assertEqual("original", tools.service["selector"])
        self.assertNotIn("FALLBACK_SELECTOR", tools.events)

    def test_equal_image_digest_does_not_skip_new_green_metadata(self):
        tools = GreenTools()
        tools.deployment["imageDigest"] = DIGEST
        self.run_policy(tools)
        self.assertIn("greenMetadataPlan", next(request for step, request in tools.requests if step == "CREATE_GREEN"))

    def test_stored_green_change_after_public_health_blocks_before_canonical_mutation(self):
        def fault(tools, step, receipt):
            if step == "GREEN_HEALTH":
                tools.green["greenMetadataPlan"]["pod"]["containers"][0]["ports"] = []
        tools = GreenTools(fault=fault)
        with self.assertRaises(HandoffFailure) as caught:
            self.run_policy(tools)
        self.assertEqual("VERIFY_GREEN", caught.exception.step)
        self.assertNotIn("MUTATE_CANONICAL", tools.events)
        self.assertEqual("original", tools.service["selector"])

    def test_selected_metadata_callback_nonzero_propagates_exact_exit(self):
        tools = GreenTools(fail="VERIFY_GREEN")
        with self.assertRaises(HandoffFailure) as caught:
            self.run_policy(tools)
        self.assertEqual(73, caught.exception.exit_code)
        self.assertEqual("VERIFY_GREEN", caught.exception.step)
        self.assertNotIn("MUTATE_CANONICAL", tools.events)

    def test_unrelated_application_retains_default_request_shapes(self):
        tools = FakeTools()
        run_handoff("Legacy.Maliev.CountryService", COMMIT, DIGEST, tools, green_contract=copy.deepcopy(CONTRACT))
        self.assertTrue(all("greenMetadataPlan" not in request for _, request in tools.requests))

    def test_default_caller_retains_existing_wire_shapes_without_metadata(self):
        tools = FakeTools()
        run_handoff(CONTRACT["target_application"], COMMIT, DIGEST, tools)
        self.assertTrue(all("greenMetadataPlan" not in request for _, request in tools.requests))

    def test_material_caller_requires_explicit_startup_mapping_and_proof(self):
        tools = GreenTools()
        contract = dict(CONTRACT, artifact="maliev-materialservice-api")
        with self.assertRaises(HandoffFailure):
            run_handoff(CONTRACT["target_application"], COMMIT, DIGEST, tools, green_contract=contract)
        self.assertNotIn("VERIFY_IMAGE", tools.events)
        endpoint = dict(path="/source-health", port=8080, scheme="HTTP")
        probe = dict(httpGet=endpoint, failureThreshold=60, periodSeconds=5, successThreshold=1, timeoutSeconds=5)
        startup = dict(target_application=CONTRACT["target_application"], source_sha=STARTUP_SOURCE, endpoint=endpoint, source_probe=probe)
        tools = GreenTools()
        run_handoff(CONTRACT["target_application"], COMMIT, DIGEST, tools, green_contract=contract, startup_contract=startup)
        plan = next(request for step, request in tools.requests if step == "CREATE_GREEN")["greenMetadataPlan"]
        self.assertEqual(probe, plan["pod"]["containers"][0]["startupProbe"])
        self.assertEqual(dict(name="MALIEV_OBSERVABILITY_READ_ONLY_STARTUP", value="true"), plan["pod"]["containers"][0]["env"][-1])

    def test_callback_exception_with_metadata_never_echoes_diagnostics(self):
        def callback(step, request):
            raise ValueError("sensitive-provider-output")
        with self.assertRaises(HandoffFailure) as caught:
            self.run_policy(callback)
        self.assertNotIn("sensitive", str(caught.exception))

    def test_mutation_request_binds_green_uid_and_both_metadata_preconditions(self):
        tools = GreenTools()
        self.run_policy(tools)
        request = next(request for step, request in tools.requests if step == "MUTATE_CANONICAL")
        create = next(request for step, request in tools.requests if step == "CREATE_GREEN")
        self.assertEqual(create["greenMetadataPlan"], request["expectedGreenMetadataPlan"])
        self.assertEqual(METADATA, request["expectedCanonicalMetadata"])
        self.assertEqual(GREEN, request["greenDeploymentUid"])
        self.assertEqual(1, request["expectedCanonicalReplicas"])
        self.assertEqual(1, request["expectedGreenReplicas"])

    def test_actual_producer_rejects_green_metadata_race_during_mutation_callback(self):
        def fault(tools):
            tools.green["greenMetadataPlan"]["pod"]["containers"][0]["ports"] = []
        tools = GreenTools(mutation_fault=fault)
        original = tools.deployment["imageDigest"]
        with self.assertRaises(HandoffFailure) as caught:
            self.run_policy(tools)
        self.assertEqual(91, caught.exception.exit_code)
        self.assertEqual(original, tools.deployment["imageDigest"])
        self.assertTrue(caught.exception.fallback_blocked)

    def test_actual_producer_rejects_canonical_metadata_race_without_image_mutation(self):
        def fault(tools):
            tools.deployment["greenMetadata"]["podMetadata"]["automountServiceAccountToken"] = True
        tools = GreenTools(mutation_fault=fault)
        original = tools.deployment["imageDigest"]
        with self.assertRaises(HandoffFailure) as caught:
            self.run_policy(tools)
        self.assertEqual(91, caught.exception.exit_code)
        self.assertEqual(original, tools.deployment["imageDigest"])
        self.assertFalse(caught.exception.fallback_blocked)
        self.assertEqual("green", tools.service["selector"])

    def test_actual_producer_rejects_canonical_uid_replacement_during_callback(self):
        def fault(tools):
            tools.deployment["uid"] = "99999999-9999-9999-9999-999999999999"
        tools = GreenTools(mutation_fault=fault)
        original = tools.deployment["imageDigest"]
        with self.assertRaises(HandoffFailure) as caught:
            self.run_policy(tools)
        self.assertEqual(91, caught.exception.exit_code)
        self.assertEqual(original, tools.deployment["imageDigest"])
        self.assertTrue(caught.exception.fallback_blocked)

    def test_actual_producer_rejects_green_uid_replacement_during_callback(self):
        def fault(tools):
            tools.green["uid"] = "99999999-9999-9999-9999-999999999999"
        tools = GreenTools(mutation_fault=fault)
        original = tools.deployment["imageDigest"]
        with self.assertRaises(HandoffFailure) as caught:
            self.run_policy(tools)
        self.assertEqual(91, caught.exception.exit_code)
        self.assertEqual(original, tools.deployment["imageDigest"])
        self.assertTrue(caught.exception.fallback_blocked)

    def test_actual_producer_rejects_replica_change_during_callback(self):
        for target in ("deployment", "green"):
            def fault(tools):
                getattr(tools, target)["replicas"] = 2
            tools = GreenTools(mutation_fault=fault)
            original = tools.deployment["imageDigest"]
            with self.assertRaises(HandoffFailure) as caught:
                self.run_policy(tools)
            self.assertEqual(91, caught.exception.exit_code)
            self.assertEqual(original, tools.deployment["imageDigest"])
            self.assertTrue(caught.exception.fallback_blocked)

    def test_actual_producer_rejects_service_change_during_callback(self):
        def fault(tools):
            tools.service["uid"] = "99999999-9999-9999-9999-999999999999"
        tools = GreenTools(mutation_fault=fault)
        original = tools.deployment["imageDigest"]
        with self.assertRaises(HandoffFailure) as caught:
            self.run_policy(tools)
        self.assertEqual(91, caught.exception.exit_code)
        self.assertEqual(original, tools.deployment["imageDigest"])
        self.assertTrue(caught.exception.fallback_blocked)


if __name__ == "__main__":
    unittest.main()
