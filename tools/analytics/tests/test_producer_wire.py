"""Synthetic controls for exact producer identity, byte binding and fail-closed CLI."""

import copy
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
try:
    spec = importlib.util.spec_from_file_location("producer_wire", ROOT / "verify_producer_wire.py")
    wire = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(wire)
finally:
    sys.path.pop(0)


class ProducerWireTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="synthetic-producer-wire-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.receipts = self.root / "receipts"
        self.fixtures = self.root / "fixtures"
        self.receipts.mkdir()
        shutil.copytree(ROOT / "fixtures", self.fixtures)
        self.approval_path = self.root / "approval.json"
        self.approval = {"schemaVersion": 1, "producers": []}
        self.values = {}
        for index, (repository, fixture_names) in enumerate(wire.PRODUCERS.items(), 1):
            receipt = {
                "schemaVersion": 1,
                "producerRepository": repository,
                "producerCommit": str(index) * 40,
                "nativeRunUrl": f"https://github.com/MALIEV-Co-Ltd/{repository}/actions/runs/{index}",
                "synthetic": True,
                "productionDtoAndSerializer": True,
                "dtoSourceSha256": {"Synthetic/Model.cs": "a" * 64},
                "serializerSourceSha256": {"Synthetic/Serializer.cs": "b" * 64},
                "fixtures": {name: wire.sha256((self.fixtures / name).read_bytes()) for name in fixture_names},
            }
            name = f"producer-{index}.json"
            self.values[name] = receipt
            self.write_json(self.receipts / name, receipt)
            pin = {key: copy.deepcopy(receipt[key]) for key in
                   ("producerRepository", "producerCommit", "nativeRunUrl", "dtoSourceSha256", "serializerSourceSha256")}
            pin.update(receiptFile=name, receiptSha256=wire.sha256((self.receipts / name).read_bytes()))
            self.approval["producers"].append(pin)
        self.save_approval()

    @staticmethod
    def write_json(path, value):
        path.write_text(json.dumps(value, separators=(",", ":")) + "\n", encoding="utf-8")

    def save_approval(self):
        self.write_json(self.approval_path, self.approval)
        self.approval_hash = wire.sha256(self.approval_path.read_bytes())

    def rebind_receipt(self, index=0):
        pin = self.approval["producers"][index]
        self.write_json(self.receipts / pin["receiptFile"], self.values[pin["receiptFile"]])
        pin["receiptSha256"] = wire.sha256((self.receipts / pin["receiptFile"]).read_bytes())
        self.save_approval()

    def verify(self):
        return wire.verify(self.approval_path, self.approval_hash, self.receipts, self.fixtures)

    def rejected(self):
        with self.assertRaises((wire.InvalidWireProof, OSError, ValueError, TypeError)):
            self.verify()

    def test_nine_exact_synthetic_fixture_bytes_preserve_negative_control(self):
        result = self.verify()
        self.assertEqual(9, result["fixtureCount"])
        self.assertEqual([5, 4], [p["fixtureCount"] for p in result["producers"]])
        self.assertFalse(result["networkChecked"])
        self.assertFalse(result["liveReadbackVerified"])
        self.assertFalse(result["wholeSourceClosure"])

    def test_approval_cannot_be_redefined_without_the_external_digest(self):
        self.approval["producers"][0]["producerCommit"] = "c" * 40
        self.write_json(self.approval_path, self.approval)
        self.rejected()

    def test_receipt_cannot_change_even_when_its_metadata_stays_equal(self):
        path = self.receipts / "producer-1.json"
        path.write_bytes(path.read_bytes() + b"\n")
        self.rejected()

    def test_missing_approval_receipt_and_fixture_fail_closed(self):
        for path in (self.approval_path, self.receipts / "producer-1.json", self.fixtures / "qualification-empty.json"):
            with self.subTest(path=path.name):
                original = path.read_bytes()
                path.unlink()
                try:
                    self.rejected()
                finally:
                    path.write_bytes(original)

    def test_every_producer_metadata_field_is_bound_after_receipt_hash_review(self):
        changes = {
            "producerRepository": "Legacy.Maliev.AccountingService",
            "producerCommit": "c" * 40,
            "nativeRunUrl": "https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.QuotationService/actions/runs/999",
            "dtoSourceSha256": {"Synthetic/Other.cs": "a" * 64},
            "serializerSourceSha256": {"Synthetic/Serializer.cs": "c" * 64},
        }
        original_receipt = copy.deepcopy(self.values["producer-1.json"])
        original_pin = copy.deepcopy(self.approval["producers"][0])
        for key, value in changes.items():
            with self.subTest(field=key):
                self.values["producer-1.json"] = copy.deepcopy(original_receipt)
                self.values["producer-1.json"][key] = value
                self.approval["producers"][0] = copy.deepcopy(original_pin)
                self.rebind_receipt()
                self.rejected()

    def test_origin_and_schema_are_strict_not_truthy(self):
        original = copy.deepcopy(self.values["producer-1.json"])
        for key, value in (("synthetic", False), ("synthetic", 1),
                           ("productionDtoAndSerializer", False), ("productionDtoAndSerializer", "true"),
                           ("schemaVersion", True), ("schemaVersion", 2)):
            with self.subTest(field=key, value=value):
                self.values["producer-1.json"] = copy.deepcopy(original)
                self.values["producer-1.json"][key] = value
                self.rebind_receipt()
                self.rejected()

    def test_duplicate_unknown_missing_and_extra_producers_are_rejected(self):
        original = copy.deepcopy(self.approval)
        for kind in ("duplicate", "unknown", "missing", "extra"):
            with self.subTest(kind=kind):
                self.approval = copy.deepcopy(original)
                if kind == "duplicate":
                    self.approval["producers"][1] = copy.deepcopy(self.approval["producers"][0])
                elif kind == "unknown":
                    self.approval["producers"][0]["producerRepository"] = "Other.Repository"
                elif kind == "missing":
                    self.approval["producers"].pop()
                else:
                    self.approval["producers"].append(copy.deepcopy(self.approval["producers"][0]))
                self.save_approval()
                self.rejected()

    def test_wrong_run_repository_commit_hash_and_source_paths_are_rejected(self):
        original = copy.deepcopy(self.approval)
        cases = [
            ("nativeRunUrl", "https://github.com/MALIEV-Co-Ltd/Other/actions/runs/1"),
            ("producerCommit", "c" * 39), ("producerCommit", "C" * 40),
            ("receiptSha256", "A" * 64),
            ("dtoSourceSha256", {}), ("dtoSourceSha256", {"../Model.cs": "a" * 64}),
            ("serializerSourceSha256", {"C:/private.cs": "a" * 64}),
        ]
        for key, value in cases:
            with self.subTest(field=key, value=value):
                self.approval = copy.deepcopy(original)
                self.approval["producers"][0][key] = value
                self.save_approval()
                self.rejected()

    def test_extra_and_missing_receipt_keys_fail(self):
        self.values["producer-1.json"]["privateField"] = "never-output"
        self.rebind_receipt()
        self.rejected()
        del self.values["producer-1.json"]["privateField"]
        del self.values["producer-1.json"]["synthetic"]
        self.rebind_receipt()
        self.rejected()

    def test_every_fixture_is_hash_bound_including_qualification_and_negative(self):
        for path in self.fixtures.glob("*.json"):
            with self.subTest(fixture=path.name):
                original = path.read_bytes()
                path.write_bytes(original + b"\n")
                try:
                    self.rejected()
                finally:
                    path.write_bytes(original)

    def test_missing_extra_and_cross_producer_fixture_entries_fail(self):
        original = copy.deepcopy(self.values["producer-1.json"])
        for kind in ("missing", "extra", "cross-owner"):
            with self.subTest(kind=kind):
                self.values["producer-1.json"] = copy.deepcopy(original)
                hashes = self.values["producer-1.json"]["fixtures"]
                if kind == "missing":
                    hashes.pop("qualification-empty.json")
                else:
                    hashes["invoice-empty.json" if kind == "cross-owner" else "unknown.json"] = "a" * 64
                self.rebind_receipt()
                self.rejected()

    def test_duplicate_json_fields_fail_even_with_matching_receipt_hash(self):
        pin = self.approval["producers"][0]
        path = self.receipts / pin["receiptFile"]
        path.write_bytes(path.read_bytes().replace(b'{"schemaVersion":1,', b'{"schemaVersion":1,"schemaVersion":1,', 1))
        pin["receiptSha256"] = wire.sha256(path.read_bytes())
        self.save_approval()
        self.rejected()

    def test_pinned_unknown_payload_fields_and_changed_negative_control_fail(self):
        for name, payload in (("qualification-empty.json", {"fromUtc": wire.FROM, "toUtc": wire.TO, "requests": [], "Email": "never-output"}),
                              ("invoice-null-currency.json", wire.outcomes.load_json((self.fixtures / "invoice-empty.json").read_text()))):
            with self.subTest(fixture=name):
                path = self.fixtures / name
                self.write_json(path, payload)
                index = 0 if name.startswith("qualification") else 1
                receipt = self.values[self.approval["producers"][index]["receiptFile"]]
                receipt["fixtures"][name] = wire.sha256(path.read_bytes())
                self.rebind_receipt(index)
                self.rejected()

    def test_oversized_approval_receipt_and_fixture_are_bounded(self):
        for path, limit in ((self.approval_path, 131072), (self.receipts / "producer-1.json", 65536),
                            (self.fixtures / "qualification-empty.json", 262144)):
            with self.subTest(file=path.name):
                original = path.read_bytes()
                path.write_bytes(b" " * (limit + 1))
                try:
                    if path == self.approval_path:
                        self.approval_hash = wire.sha256(path.read_bytes())
                    self.rejected()
                finally:
                    path.write_bytes(original)
                    self.approval_hash = wire.sha256(self.approval_path.read_bytes())

    def test_receipt_path_traversal_is_rejected(self):
        self.approval["producers"][0]["receiptFile"] = "../outside.json"
        self.save_approval()
        self.rejected()

    def test_symlinked_input_is_rejected_before_reading(self):
        with patch.object(Path, "is_symlink", return_value=True):
            self.rejected()

    def test_unknown_approval_fields_and_boolean_schema_fail(self):
        original = copy.deepcopy(self.approval)
        for key, value in (("extraApproval", True), ("schemaVersion", True)):
            with self.subTest(field=key):
                self.approval = copy.deepcopy(original)
                self.approval[key] = value
                self.save_approval()
                self.rejected()

    def test_invoice_actual_utc_is_required_even_after_receipt_rebinding(self):
        for name in ("invoice-zero.json", "invoice-mixed.json", "invoice-null-currency.json"):
            with self.subTest(fixture=name):
                path = self.fixtures / name
                original = path.read_bytes()
                path.write_bytes(original.replace(b'T00:00:00Z', b'T00:00:00'))
                receipt = self.values["producer-2.json"]
                receipt["fixtures"][name] = wire.sha256(path.read_bytes())
                self.rebind_receipt(1)
                self.rejected()
                path.write_bytes(original)
                receipt["fixtures"][name] = wire.sha256(original)
                self.rebind_receipt(1)

    def test_null_currency_control_rejects_every_other_shape_count_and_type_defect(self):
        name = "invoice-null-currency.json"
        original = wire.outcomes.load_json((self.fixtures / name).read_text())
        cases = [
            ("root-private", lambda p: p.update(Email="never-output")),
            ("day-private", lambda p: p["Days"][0].update(CustomerId=1)),
            ("amount-private", lambda p: p["Days"][0]["PaidInvoiceAmountsByCurrency"][0].update(Account="never-output")),
            ("root-unknown", lambda p: p.update(Unknown=True)),
            ("amount-extra-currency", lambda p: p["Days"][0]["PaidInvoiceAmountsByCurrency"][0].update(Currency=None)),
            ("day-negative-count", lambda p: p["Days"][0].update(PaidInvoiceCount=-1)),
            ("attribution-mismatch", lambda p: p["Days"][0].update(UnattributedPaidInvoiceCount=2)),
            ("represented-mismatch", lambda p: p["Days"][0]["PaidInvoiceAmountsByCurrency"][0].update(PaidInvoiceCount=2)),
            ("boolean-count", lambda p: p["Days"][0].update(PaidInvoiceCount=True)),
            ("string-count", lambda p: p["Days"][0].update(PaidInvoiceCount="1")),
            ("amount-string", lambda p: p["Days"][0]["PaidInvoiceAmountsByCurrency"][0].update(PaidInvoiceTotal="0.0")),
            ("amount-null", lambda p: p["Days"][0]["PaidInvoiceAmountsByCurrency"][0].update(PaidInvoiceTotal=None)),
            ("missing-total", lambda p: p["Days"][0]["PaidInvoiceAmountsByCurrency"][0].pop("PaidInvoiceTotal")),
            ("out-of-window", lambda p: p["Days"][0].update(DayUtc="2026-09-05T00:00:00Z")),
            ("changed-window", lambda p: p.update(ToUtc="2026-09-02T17:00:00Z")),
            ("extra-day", lambda p: p["Days"].append(copy.deepcopy(p["Days"][0]))),
            ("extra-amount", lambda p: p["Days"][0]["PaidInvoiceAmountsByCurrency"].append(copy.deepcopy(p["Days"][0]["PaidInvoiceAmountsByCurrency"][0]))),
            ("amount-object", lambda p: p["Days"][0].update(PaidInvoiceAmountsByCurrency={})),
        ]
        for label, mutate in cases:
            with self.subTest(defect=label):
                payload = copy.deepcopy(original)
                mutate(payload)
                path = self.fixtures / name
                path.write_text(wire.outcomes.json_text(payload) + "\n", encoding="utf-8")
                self.values["producer-2.json"]["fixtures"][name] = wire.sha256(path.read_bytes())
                self.rebind_receipt(1)
                self.rejected()

    def test_null_currency_validation_preserves_original_payload_and_bytes(self):
        path = self.fixtures / "invoice-null-currency.json"
        before = path.read_bytes()
        payload = wire.outcomes.load_json(before.decode())
        original = copy.deepcopy(payload)
        wire.validate_null_currency_control(payload)
        self.assertEqual(original, payload)
        self.assertEqual(before, path.read_bytes())

    def test_cli_unavailable_is_opaque_and_nonzero(self):
        self.values["producer-1.json"]["privateField"] = "never-output"
        self.rebind_receipt()
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(sys, "argv", ["verify_producer_wire.py", "--approval", str(self.approval_path),
                                         "--approval-sha256", self.approval_hash, "--receipts", str(self.receipts),
                                         "--fixtures", str(self.fixtures)]), redirect_stdout(stdout), redirect_stderr(stderr):
            self.assertEqual(2, wire.main())
        self.assertEqual("", stdout.getvalue())
        self.assertNotIn("never-output", stderr.getvalue())
        self.assertNotIn(str(self.root), stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
