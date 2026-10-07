"""Service wrapper regression controls; no process, provider or cluster calls."""
import copy
import hashlib
import json
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("service_wrapper", Path(__file__).resolve().parents[1] / "scripts/service_manifest_wrapper.py")
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)
COMMIT = "1" * 40
PINNED_FIXTURE_SHA256 = {
    "DocumentService.json": "c015e0557c6306715e0fc995247fc7ff960184231e1dd7d5ec23a723f798b186",
    "FileService.json": "c3d71a27cd88fded102e814dbdac910794ee60347a83281e8d94920a34ce8f70",
    "NotificationService.json": "dd7571895e7cc51c9c77bf45ce5e79db9a2e657d8734237adf113e484220153f",
}


def verified_fixture(name, raw):
    # Git checkout CRLF conversion must not change the committed canonical-LF pin.
    raw = raw.replace(b'\r\n', b'\n')
    if hashlib.sha256(raw).hexdigest() != PINNED_FIXTURE_SHA256[name]:
        raise ValueError("Historical Service fixture digest mismatch.")
    return json.loads(raw)


def manifest(application="Legacy.Maliev.DocumentService"):
    name = policy.SERVICES[application]
    return dict(apiVersion="v1", kind="Service", metadata=dict(annotations={}, labels=dict(run=name), name=name, namespace="maliev"),
                spec=dict(ports=[dict(port=8080, protocol="TCP", targetPort=8080, name="http")],
                          selector=dict(run=name), sessionAffinity="None", type="NodePort"))


class ServiceWrapperTests(unittest.TestCase):
    def invoke(self, document=None, tool=None, application="Legacy.Maliev.DocumentService", commit=COMMIT):
        self.calls = []
        def boundary(step, request):
            self.calls.append((step, copy.deepcopy(request)))
            if tool:
                return tool(step, request)
            return dict(exitCode=0, receipt={key: request[key] for key in ("sourceCommit", "manifestSha256")})
        return policy.run_service_wrapper(application, commit, manifest(application) if document is None else document, boundary)

    def test_all_three_historical_services_are_separate_single_calls(self):
        for application in policy.SERVICES:
            with self.subTest(application=application):
                document = manifest(application)
                before = copy.deepcopy(document)
                receipt = self.invoke(document, application=application)
                self.assertEqual(document, before)
                self.assertEqual(len(self.calls), 1)
                step, request = self.calls[0]
                self.assertEqual(step, "APPLY_SERVICE_MANIFEST")
                self.assertEqual(request["manifest"], document)
                self.assertEqual(receipt["manifestSha256"], request["manifestSha256"])
                for field in ("deploymentAllowed", "runtimeAccepted", "consumerAdoptionAccepted"):
                    self.assertIs(receipt[field], False)

    def test_exact_historical_service_fixtures_preserve_all_manifest_values(self):
        paths = sorted((Path(__file__).parent / 'fixtures/service-wrapper').glob('*.json'))
        self.assertEqual(len(paths), 3)
        applications = set()
        for path in paths:
            fixture = verified_fixture(path.name, path.read_bytes())
            applications.add(fixture['application'])
            self.assertEqual(fixture['separationSource'], policy.SEPARATION_SOURCE)
            self.assertEqual(fixture['checkpoint'], policy.CHECKPOINT)
            with self.subTest(application=fixture['application']):
                result = self.invoke(fixture['manifest'], application=fixture['application'], commit=fixture['checkpoint'])
                self.assertEqual(self.calls[0][1]['manifest'], fixture['manifest'])
                self.assertEqual(result['sourceCommit'], fixture['checkpoint'])
        self.assertEqual(applications, set(policy.SERVICES))

    def test_fixture_provenance_and_non_identity_manifest_drift_is_rejected(self):
        for name in PINNED_FIXTURE_SHA256:
            raw = (Path(__file__).parent / 'fixtures/service-wrapper' / name).read_bytes()
            original = verified_fixture(name, raw)
            self.assertEqual((json.dumps(original, indent=2) + '\n').encode(), raw.replace(b'\r\n', b'\n'))
            for field in ('sourceYamlPath', 'sourceYamlSha256', 'wrapperPath', 'checkpointWrapperSha256', 'manifestPort'):
                changed = copy.deepcopy(original)
                if field == 'manifestPort':
                    changed['manifest']['spec']['ports'][0]['targetPort'] = 9999
                else:
                    changed[field] = 'foreign'
                with self.subTest(fixture=name, field=field), self.assertRaises(ValueError):
                    verified_fixture(name, (json.dumps(changed, indent=2) + '\n').encode())

    def test_fixture_pin_verifies_raw_bytes_independently(self):
        for name in PINNED_FIXTURE_SHA256:
            raw = (Path(__file__).parent / 'fixtures/service-wrapper' / name).read_bytes()
            with self.subTest(fixture=name), self.assertRaises(ValueError):
                verified_fixture(name, raw + b' ')

    def test_deployment_ingress_and_list_are_rejected_before_callback(self):
        for kind in ("Deployment", "Ingress", "List", "service"):
            with self.subTest(kind=kind):
                document = manifest()
                document["kind"] = kind
                with self.assertRaises(policy.ServiceWrapperFailure):
                    self.invoke(document)
                self.assertEqual(self.calls, [])

    def test_hidden_resource_list_is_rejected_before_callback(self):
        document = manifest()
        document["items"] = [dict(kind="Deployment")]
        with self.assertRaises(policy.ServiceWrapperFailure):
            self.invoke(document)
        self.assertEqual(self.calls, [])

    def test_foreign_namespace_name_and_selector_reject_before_callback(self):
        for field in ("namespace", "name", "selector"):
            document = manifest()
            if field == "selector":
                document["spec"][field] = {"run": "other"}
            else:
                document["metadata"][field] = "other"
            with self.subTest(field=field), self.assertRaises(policy.ServiceWrapperFailure):
                self.invoke(document)
            self.assertEqual(self.calls, [])

    def test_source_identity_is_exact_and_checked_before_callback(self):
        for commit in ("a" * 39, "A" * 40, True, COMMIT + "\n"):
            with self.subTest(commit=commit), self.assertRaises(policy.ServiceWrapperFailure):
                self.invoke(commit=commit)
            self.assertEqual(self.calls, [])

    def test_unknown_application_has_no_dispatch(self):
        self.calls = []
        with self.assertRaises(policy.ServiceWrapperFailure):
            policy.run_service_wrapper("Legacy.Maliev.Auth", COMMIT, manifest(), lambda *args: self.calls.append(args))
        self.assertEqual(self.calls, [])

    def test_native_exit_status_is_preserved_without_second_call(self):
        for code in (1, 17, 3010, 2147483647):
            with self.subTest(code=code):
                with self.assertRaises(policy.ServiceWrapperFailure) as caught:
                    self.invoke(tool=lambda *_: dict(exitCode=code, receipt=None))
                self.assertEqual(caught.exception.exit_code, code)
                self.assertEqual(len(self.calls), 1)

    def test_invalid_exit_status_cannot_be_trusted(self):
        for code in (True, "17", -1, 2147483648, 0.0):
            with self.subTest(code=code):
                with self.assertRaises(policy.ServiceWrapperFailure) as caught:
                    self.invoke(tool=lambda *_: dict(exitCode=code, receipt={}))
                self.assertEqual(caught.exception.exit_code, 1)

    def test_callback_exceptions_and_public_failure_objects_are_redacted(self):
        for error in (RuntimeError("private-provider-marker"), policy.ServiceWrapperFailure(17)):
            def broken(*_):
                raise error
            with self.assertRaises(policy.ServiceWrapperFailure) as caught:
                self.invoke(tool=broken)
            self.assertEqual(caught.exception.exit_code, 1)
            self.assertNotIn("private-provider-marker", str(caught.exception))
            self.assertIsNone(caught.exception.__cause__)

    def test_callback_mutation_rejects_and_caller_input_is_preserved(self):
        document = manifest()
        before = copy.deepcopy(document)
        def mutate(_, request):
            request["manifest"]["spec"]["ports"][0]["port"] = 9999
            return dict(exitCode=0, receipt={key: request[key] for key in ("sourceCommit", "manifestSha256")})
        with self.assertRaises(policy.ServiceWrapperFailure):
            self.invoke(document, tool=mutate)
        self.assertEqual(document, before)

    def test_foreign_or_extra_receipt_is_rejected(self):
        for field in ("sourceCommit", "manifestSha256", "extra"):
            def mismatch(_, request):
                receipt = {key: request[key] for key in ("sourceCommit", "manifestSha256")}
                receipt[field] = "foreign"
                return dict(exitCode=0, receipt=receipt)
            with self.subTest(field=field), self.assertRaises(policy.ServiceWrapperFailure):
                self.invoke(tool=mismatch)

    def test_malformed_boundary_envelope_rejects(self):
        for response in (None, [], {}, dict(exitCode=0, receipt={}, extra=True)):
            with self.subTest(response=response), self.assertRaises(policy.ServiceWrapperFailure):
                self.invoke(tool=lambda *_: response)

    def test_oversized_input_never_dispatches(self):
        document = manifest()
        document["metadata"]["annotations"]["large"] = "x" * 16384
        with self.assertRaises(policy.ServiceWrapperFailure):
            self.invoke(document)
        self.assertEqual(self.calls, [])

    def test_non_json_and_nonfinite_input_never_dispatches(self):
        for value in (float("nan"), object(), (1, 2), {1: "numeric-key"}):
            document = manifest()
            document["metadata"]["annotations"]["invalid"] = value
            with self.assertRaises(policy.ServiceWrapperFailure):
                self.invoke(document)
            self.assertEqual(self.calls, [])

    def test_empty_or_malformed_ports_never_dispatch(self):
        for ports in ([], {}, [None]):
            document = manifest()
            document["spec"]["ports"] = ports
            with self.assertRaises(policy.ServiceWrapperFailure):
                self.invoke(document)
            self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
