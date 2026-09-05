"""Aggregate-only source wire, privacy, cohort, and availability tests."""

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FROM = "2026-08-25T17:00:00Z"
TO = "2026-09-01T17:00:00Z"
NOW = "2026-09-02T10:00:00Z"


def load_outcomes():
    path = ROOT / "outcome_receipts.py"
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location("outcomes", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


outcomes = load_outcomes()


def fixture(source, variant="mixed"):
    return outcomes.load_json((ROOT / "fixtures" / f"{source}-{variant}.json").read_text())


def receipt(source, variant="mixed"):
    return {
        "source": source,
        "capturedAtUtc": NOW,
        "httpStatus": 200,
        "payload": fixture(source, variant),
    }


class OutcomeReceiptTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(outcomes, "outcome_receipts.py must implement the receipt consumer")

    def consume(self, value, source="quotation", **kwargs):
        return outcomes.consume(value, source, FROM, TO, NOW, **kwargs)

    def assert_unavailable(self, value, source="quotation"):
        result = self.consume(value, source)
        self.assertEqual("unavailable", result["availability"])
        self.assertIsNone(result["counts"])
        self.assertIsNone(result["days"])
        return result

    def test_real_wire_empty_and_explicit_zero_are_available(self):
        for source in ("quotation", "invoice"):
            for variant in ("empty", "zero"):
                with self.subTest(source=source, variant=variant):
                    result = self.consume(receipt(source, variant), source)
                    self.assertEqual("available", result["availability"])
                    self.assertTrue(all(value == 0 for value in result["counts"].values()))
                    self.assertEqual(0 if variant == "empty" else 1, len(result["days"]))

    def test_mixed_attribution_preserves_stages_and_precise_currencies(self):
        result = self.consume(receipt("quotation"))
        self.assertEqual({"persistedQuotation": 3, "acceptedQuotation": 2}, result["counts"])
        amounts = result["days"][0]["AcceptedQuotedAmountsByCurrency"]
        self.assertEqual(Decimal("9876543210.12345678"), amounts[1]["QuotedAmount"])
        self.assertIn("9876543210.12345678", outcomes.json_text(result))
        self.assertIsNone(result["qualifiedCustomer"]["count"])
        self.assertEqual("unavailable", result["channelEvidenceAvailability"])
        invoice = self.consume(receipt("invoice"), "invoice")
        self.assertEqual({"paidInvoice": 3}, invoice["counts"])
        self.assertEqual(
            ["THB", "USD"],
            [item["Currency"] for item in invoice["days"][0]["PaidInvoiceAmountsByCurrency"]],
        )

    def test_missing_and_http_failures_never_become_zero_or_leak_body(self):
        self.assertEqual("missing_receipt", self.assert_unavailable(None)["reason"])
        for status in (400, 401, 403, 500):
            value = receipt("quotation")
            value.update(httpStatus=status, payload={"CustomerId": "private"})
            result = self.assert_unavailable(value)
            self.assertNotIn("private", outcomes.json_text(result))
            self.assertEqual("access_denied" if status in (401, 403) else "http_failure", result["reason"])

    def test_omitted_null_and_wrong_types_are_rejected(self):
        for replacement in (None, True, "0", -1, Decimal("1.0")):
            value = receipt("quotation")
            value["payload"]["Days"][0]["PersistedQuotationCount"] = replacement
            self.assert_unavailable(value)
        value = receipt("quotation")
        del value["payload"]["Days"][0]["PersistedQuotationCount"]
        self.assert_unavailable(value)
        self.assert_unavailable(receipt("invoice", "null-currency"), "invoice")

    def test_unknown_fields_are_rejected_at_every_boundary(self):
        for path in ((), ("payload",), ("payload", "Days", 0),
                     ("payload", "Days", 0, "AcceptedQuotedAmountsByCurrency", 0)):
            value = receipt("quotation")
            target = value
            for key in path:
                target = target[key]
            target["JourneyId"] = "private"
            result = self.assert_unavailable(value)
            self.assertNotIn("private", outcomes.json_text(result))

    def test_inconsistent_counts_and_duplicate_days_or_currencies_are_rejected(self):
        value = receipt("quotation")
        value["payload"]["Days"][0]["UnattributedPersistedQuotationCount"] = 0
        self.assert_unavailable(value)
        for source in ("quotation", "invoice"):
            value = receipt(source)
            value["payload"]["Days"] *= 2
            self.assert_unavailable(value, source)
            value = receipt(source)
            amount_key = "AcceptedQuotedAmountsByCurrency" if source == "quotation" else "PaidInvoiceAmountsByCurrency"
            value["payload"]["Days"][0][amount_key].reverse()
            self.assert_unavailable(value, source)

    def test_null_quote_amounts_can_be_absent_without_fabricating_money(self):
        value = receipt("quotation")
        value["payload"]["Days"][0]["AcceptedQuotedAmountsByCurrency"] = []
        self.assertEqual("available", self.consume(value)["availability"])
        value = receipt("invoice")
        value["payload"]["Days"][0]["PaidInvoiceAmountsByCurrency"] = []
        self.assert_unavailable(value, "invoice")

    def test_exact_window_31_day_limit_and_utc_are_required(self):
        value = fixture("quotation", "empty")
        value.update(FromUtc="2026-08-01T00:00:00Z", ToUtc="2026-09-01T00:00:00Z")
        outcomes.validate_payload(value, "quotation", value["FromUtc"], value["ToUtc"])
        for start, end in ((TO, FROM), (FROM[:-1], TO), ("2026-07-31T00:00:00Z", TO)):
            with self.assertRaises(outcomes.InvalidReceipt):
                outcomes.validate_payload(value, "quotation", start, end)
        value = receipt("quotation")
        value["payload"]["FromUtc"] = "2026-08-25T00:00:00Z"
        self.assert_unavailable(value)

    def test_half_open_days_and_utc_day_labels_are_preserved(self):
        for day in ("2026-08-25T00:00:00", "2026-08-26T00:00:00Z"):
            value = receipt("quotation")
            value["payload"]["Days"][0]["DayUtc"] = day
            self.assertEqual("available", self.consume(value)["availability"])
        for day in ("2026-08-24T00:00:00", "2026-09-02T00:00:00", "2026-08-26T00:00:00+07:00"):
            value = receipt("quotation")
            value["payload"]["Days"][0]["DayUtc"] = day
            self.assert_unavailable(value)

    def test_stale_future_or_incomplete_receipts_are_unavailable(self):
        for captured in ("2026-08-31T10:00:00Z", "2026-09-03T10:00:00Z", "2026-09-01T16:00:00Z"):
            value = receipt("quotation")
            value["capturedAtUtc"] = captured
            self.assert_unavailable(value)

    def test_qualification_claims_and_wrong_case_are_rejected(self):
        value = receipt("quotation")
        value["payload"]["QualifiedCustomerAvailability"] = "available"
        self.assert_unavailable(value)
        value = receipt("quotation")
        value["payload"]["days"] = value["payload"].pop("Days")
        self.assert_unavailable(value)

    def test_duplicate_fields_and_nonfinite_json_are_rejected(self):
        for raw in ('{"Days":[],"Days":[]}', '{"Amount":NaN}', '{"Amount":Infinity}'):
            with self.assertRaises(outcomes.InvalidReceipt):
                outcomes.load_json(raw)

    def test_cli_missing_receipts_outputs_unavailable_with_nonzero_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            run = subprocess.run(
                [sys.executable, str(ROOT / "outcome_receipts.py"), "--from-utc", FROM,
                 "--to-utc", TO, "--output", str(output)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(2, run.returncode, run.stderr)
            self.assertTrue(
                all(item["counts"] is None for item in outcomes.load_json(output.read_text())["sources"])
            )


if __name__ == "__main__":
    unittest.main()
