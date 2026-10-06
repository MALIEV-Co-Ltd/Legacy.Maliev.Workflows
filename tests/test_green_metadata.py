import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from green_metadata import ARTIFACTS, MetadataRejected, SOURCE_SHA, bounded, contract_shape, plan_green_metadata, verify_green_metadata

DIGEST = "sha256:" + "a" * 64
CONTRACT = dict(source_sha=SOURCE_SHA, target_application="Legacy.Maliev.NotificationService", artifact="maliev-emailservice-api", container="legacy-maliev-notification-service", namespace="maliev-legacy")
PROBE = dict(httpGet=dict(path="/health", port=8080), periodSeconds=5, failureThreshold=3)
METADATA = dict(containerNames=[CONTRACT["container"]], unsafeFields=[],
    environment=[dict(name="DOTNET_ENVIRONMENT", value="Production"), dict(name="CONNECTION", valueFrom=dict(secretKeyRef=dict(name="owned-config", key="connection")))],
    containerMetadata=dict(readinessProbe=PROBE, livenessProbe=PROBE, ports=[dict(containerPort=8080)], envFrom=[dict(configMapRef=dict(name="owned-config"))], resources=dict(requests=dict(cpu="100m"))),
    podMetadata=dict(imagePullSecrets=[dict(name="existing-pull")], automountServiceAccountToken=False))


class GreenMetadataTests(unittest.TestCase):
    def plan(self, metadata=None, **changes):
        return plan_green_metadata(copy.deepcopy(CONTRACT), copy.deepcopy(METADATA if metadata is None else metadata), DIGEST, **changes)

    def reject(self, metadata):
        with self.assertRaises(MetadataRejected) as caught:
            self.plan(metadata)
        self.assertEqual("Green metadata contract rejected.", str(caught.exception))

    def test_complete_selected_plan_preserves_singleton_arrays_and_references(self):
        plan = self.plan()
        self.assertEqual(1, len(plan["pod"]["containers"]))
        container = plan["pod"]["containers"][0]
        self.assertEqual(METADATA["containerMetadata"]["ports"], container["ports"])
        self.assertEqual(METADATA["containerMetadata"]["envFrom"], container["envFrom"])
        self.assertEqual(METADATA["environment"][1], container["env"][1])
        self.assertEqual(METADATA["podMetadata"]["imagePullSecrets"], plan["pod"]["imagePullSecrets"])
        self.assertFalse(plan["pod"]["automountServiceAccountToken"])
        self.assertEqual(90, plan["pod"]["terminationGracePeriodSeconds"])
        self.assertEqual(["/bin/sh", "-c", "sleep 60"], container["lifecycle"]["preStop"]["exec"]["command"])

    def test_plan_is_detached_from_both_original_and_returned_mutations(self):
        metadata = copy.deepcopy(METADATA)
        original = copy.deepcopy(metadata)
        plan = self.plan(metadata)
        plan["pod"]["containers"][0]["env"][1]["valueFrom"]["secretKeyRef"]["name"] = "changed"
        self.assertEqual(original, metadata)
        self.assertEqual(original, METADATA)

    def test_boolean_source_flags_are_lowercase_and_standby_is_owned(self):
        metadata = copy.deepcopy(METADATA)
        metadata["environment"] += [dict(name="MALIEV_OBSERVABILITY_STANDBY", value=False), dict(name="MALIEV_OBSERVABILITY_READ_ONLY_STARTUP", value=True)]
        environment = self.plan(metadata, read_only=True)["pod"]["containers"][0]["env"]
        self.assertEqual([dict(name="MALIEV_OBSERVABILITY_STANDBY", value="true"), dict(name="MALIEV_OBSERVABILITY_READ_ONLY_STARTUP", value="true")], environment[-2:])
        self.assertNotIn(False, [item.get("value") for item in environment])

    def test_all_four_configuration_reference_kinds_remain_structurally_exact(self):
        for kind in ("secretKeyRef", "configMapKeyRef", "fieldRef", "resourceFieldRef"):
            metadata = copy.deepcopy(METADATA)
            metadata["environment"] = [dict(name="CONFIG", valueFrom={kind: dict(name="owned", key="value")})]
            self.assertEqual(metadata["environment"][0], self.plan(metadata)["pod"]["containers"][0]["env"][0])

    def test_missing_null_and_present_startup_probes_are_optional(self):
        for probe in (None, PROBE):
            metadata = copy.deepcopy(METADATA)
            metadata["containerMetadata"]["startupProbe"] = copy.deepcopy(probe)
            container = self.plan(metadata)["pod"]["containers"][0]
            self.assertEqual(probe, container.get("startupProbe"))
        self.assertNotIn("startupProbe", self.plan()["pod"]["containers"][0])

    def test_http_tcp_and_grpc_handlers_are_retained(self):
        for probe in (PROBE, dict(tcpSocket=dict(port="health")), dict(grpc=dict(port=8080, service="health"))):
            metadata = copy.deepcopy(METADATA)
            metadata["containerMetadata"]["readinessProbe"] = probe
            self.assertEqual(probe, self.plan(metadata)["pod"]["containers"][0]["readinessProbe"])

    def test_exec_headers_multiple_unknown_missing_and_malformed_handlers_reject(self):
        for probe in (dict(exec=dict(command=["sensitive"])), dict(httpGet=dict(port=8080, httpHeaders=[])),
                      dict(httpGet=dict(port=8080), tcpSocket=dict(port=8080)), dict(httpGet=dict(port=8080), unknown=1),
                      dict(httpGet={}), dict(httpGet="sensitive"), dict(grpc=dict(port=True)), dict(httpGet=dict(port=8080), periodSeconds=True)):
            metadata = copy.deepcopy(METADATA)
            metadata["containerMetadata"]["readinessProbe"] = probe
            self.reject(metadata)

    def test_missing_required_readiness_or_liveness_rejects(self):
        for field in ("readinessProbe", "livenessProbe"):
            metadata = copy.deepcopy(METADATA)
            del metadata["containerMetadata"][field]
            self.reject(metadata)

    def test_every_unsafe_initial_container_shape_rejects(self):
        for field in ("initContainers", "command", "args", "volumeMounts", "volumes"):
            metadata = copy.deepcopy(METADATA)
            metadata["unsafeFields"] = [field]
            self.reject(metadata)

    def test_unknown_literal_environment_values_and_duplicate_names_reject(self):
        for entries in ([dict(name="PRIVATE_VALUE", value="sensitive")], [dict(name="DOTNET_ENVIRONMENT", value="sensitive")],
                        [dict(name="DOTNET_ENVIRONMENT", value="Production")] * 2,
                        [dict(name="MALIEV_OBSERVABILITY_STANDBY", valueFrom=dict(secretKeyRef=dict(name="owned")))],
                        [dict(name="CONFIG", valueFrom=dict(unknown=dict(name="owned")))],
                        [dict(name="CONFIG", valueFrom=dict(secretKeyRef=dict(name="owned")), value="sensitive")]):
            metadata = copy.deepcopy(METADATA)
            metadata["environment"] = entries
            self.reject(metadata)

    def test_scalar_in_place_of_singleton_arrays_and_wrong_boolean_types_reject(self):
        for field, value in (("containerNames", CONTRACT["container"]), ("environment", METADATA["environment"][0]), ("unsafeFields", False)):
            metadata = copy.deepcopy(METADATA)
            metadata[field] = value
            self.reject(metadata)
        for field, value in (("ports", dict(containerPort=8080)), ("envFrom", dict(configMapRef=dict(name="owned")))):
            metadata = copy.deepcopy(METADATA)
            metadata["containerMetadata"][field] = value
            self.reject(metadata)
        metadata = copy.deepcopy(METADATA)
        metadata["podMetadata"]["automountServiceAccountToken"] = "false"
        self.reject(metadata)

    def test_foreign_multiple_and_missing_container_identities_reject(self):
        for names in ([], ["foreign"], [CONTRACT["container"], "sidecar"]):
            metadata = copy.deepcopy(METADATA)
            metadata["containerNames"] = names
            self.reject(metadata)

    def test_historical_inventory_and_source_mapping_are_case_sensitive(self):
        self.assertEqual(23, len(ARTIFACTS))
        for field, value in (("artifact", "MALIEV-EMAILSERVICE-API"), ("artifact", "maliev-unknown"), ("artifact", []), ("source_sha", "a" * 40), ("container", "Bad_Name")):
            contract = dict(CONTRACT, **{field: value})
            with self.assertRaises(MetadataRejected):
                contract_shape(CONTRACT["target_application"], contract)
        self.assertIsNone(contract_shape("Legacy.Maliev.CountryService", CONTRACT))

    def test_depth_width_bytes_unicode_nonfinite_and_nonjson_reject_opaquely(self):
        deep = []
        for _ in range(20):
            deep = [deep]
        for value in (deep, [None] * 129, "x" * 16385, "\ud800", "ก" * 6000, float("nan"), object(), 2147483648):
            with self.assertRaises(MetadataRejected) as caught:
                bounded(value)
            self.assertEqual("Green metadata contract rejected.", str(caught.exception))

    def test_type_sensitive_readback_rejects_boolean_integer_equivalence(self):
        expected = self.plan()
        actual = copy.deepcopy(expected)
        actual["pod"]["automountServiceAccountToken"] = 0
        with self.assertRaises(MetadataRejected):
            verify_green_metadata(expected, actual)
        self.assertFalse(verify_green_metadata(expected, expected)["runtimeAccepted"])

    def test_material_mapping_requires_separately_admitted_startup_and_read_only(self):
        contract = dict(CONTRACT, artifact="maliev-materialservice-api")
        for read_only, probe in ((False, PROBE), (True, None)):
            with self.assertRaises(MetadataRejected):
                plan_green_metadata(contract, METADATA, DIGEST, startup_probe=probe, read_only=read_only)
        plan = plan_green_metadata(contract, METADATA, DIGEST, startup_probe=PROBE, read_only=True)
        self.assertEqual(PROBE, plan["pod"]["containers"][0]["startupProbe"])


if __name__ == "__main__":
    unittest.main()
