"""Verify synthetic wire fixtures against externally approved producer receipts."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

import outcome_receipts as outcomes


PRODUCERS = {
    "Legacy.Maliev.QuotationService": {
        "quotation-empty.json", "quotation-zero.json", "quotation-mixed.json",
        "qualification-empty.json", "qualification-mixed.json",
    },
    "Legacy.Maliev.AccountingService": {
        "invoice-empty.json", "invoice-zero.json", "invoice-mixed.json",
        "invoice-null-currency.json",
    },
}
APPROVAL_KEYS = {"schemaVersion", "producers"}
PIN_KEYS = {
    "producerRepository", "producerCommit", "nativeRunUrl", "receiptFile",
    "receiptSha256", "dtoSourceSha256", "serializerSourceSha256",
}
RECEIPT_KEYS = {
    "schemaVersion", "producerRepository", "producerCommit", "nativeRunUrl",
    "synthetic", "productionDtoAndSerializer", "dtoSourceSha256",
    "serializerSourceSha256", "fixtures",
}
FROM = "2026-08-25T17:00:00Z"
TO = "2026-09-01T17:00:00Z"


class InvalidWireProof(ValueError):
    """A producer proof is absent, changed or outside the approved contract."""


def require(condition):
    if not condition:
        raise InvalidWireProof("Approved synthetic producer wire evidence required.")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def digest(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def bounded_read(path, maximum):
    with path.open("rb") as stream:
        data = stream.read(maximum + 1)
    require(len(data) <= maximum)
    return data


def exact_keys(value, expected):
    require(type(value) is dict and set(value) == expected)


def parse(data):
    try:
        return outcomes.load_json(data.decode("utf-8"))
    except (UnicodeError, outcomes.InvalidReceipt):
        raise InvalidWireProof("Approved synthetic producer wire evidence required.") from None


def source_hashes(value):
    require(type(value) is dict and 1 <= len(value) <= 8)
    for path, expected in value.items():
        require(isinstance(path, str) and 0 < len(path) <= 256 and digest(expected))
        require(not path.startswith(("/", "\\")) and "\\" not in path and ":" not in path)
        require(all(part not in ("", ".", "..") for part in path.split("/")))
        require(path.endswith(".cs"))


def local_file(directory, name):
    require(isinstance(name, str) and re.fullmatch(r"[a-z][a-z0-9-]{0,95}\.json", name) is not None)
    root = Path(directory).resolve(strict=True)
    path = root / name
    require(not path.is_symlink() and path.resolve(strict=True).parent == root)
    return path


def validate_null_currency_control(payload):
    """Prove omitted Currency is the only defect; never change emitted bytes."""
    exact_keys(payload, {"FromUtc", "ToUtc", "Days"})
    days = payload["Days"]
    require(type(days) is list and len(days) == 1 and type(days[0]) is dict)
    day = days[0]
    exact_keys(day, {"DayUtc", "PaidInvoiceCount", "SourceAttributedPaidInvoiceCount",
                     "UnattributedPaidInvoiceCount", "PaidInvoiceAmountsByCurrency"})
    amounts = day["PaidInvoiceAmountsByCurrency"]
    require(type(amounts) is list and len(amounts) == 1)
    exact_keys(amounts[0], {"PaidInvoiceTotal", "PaidInvoiceCount"})
    # A separate in-memory validation projection supplies the one omitted key.
    # The original payload, fixture bytes and producer digest remain untouched.
    valid_projection = {**payload, "Days": [{**day, "PaidInvoiceAmountsByCurrency":
                        [{"Currency": "UNSPECIFIED", **amounts[0]}]}]}
    try:
        outcomes.validate_payload(valid_projection, "invoice", FROM, TO)
    except (outcomes.InvalidReceipt, TypeError, OverflowError):
        raise InvalidWireProof("Approved synthetic producer wire evidence required.") from None


def verify(approval_path, approval_sha256, receipt_directory, fixture_directory):
    """The caller supplies the trusted approval digest; no network/auth inference."""
    require(digest(approval_sha256))
    approval_bytes = bounded_read(Path(approval_path), 131072)
    require(sha256(approval_bytes) == approval_sha256)
    approval = parse(approval_bytes)
    exact_keys(approval, APPROVAL_KEYS)
    require(type(approval["schemaVersion"]) is int and approval["schemaVersion"] == 1)
    pins = approval["producers"]
    require(type(pins) is list and len(pins) == 2)
    seen_producers = set()
    seen_receipts = set()
    verified = []
    for pin in pins:
        exact_keys(pin, PIN_KEYS)
        repository = pin["producerRepository"]
        require(isinstance(repository, str) and repository in PRODUCERS and repository not in seen_producers)
        seen_producers.add(repository)
        require(isinstance(pin["producerCommit"], str) and re.fullmatch(r"[0-9a-f]{40}", pin["producerCommit"]) is not None)
        require(isinstance(pin["nativeRunUrl"], str) and re.fullmatch(
            r"https://github\.com/MALIEV-Co-Ltd/" + re.escape(repository) + r"/actions/runs/[1-9][0-9]*",
            pin["nativeRunUrl"],
        ) is not None)
        source_hashes(pin["dtoSourceSha256"])
        source_hashes(pin["serializerSourceSha256"])
        require(digest(pin["receiptSha256"]))
        receipt_path = local_file(receipt_directory, pin["receiptFile"])
        require(receipt_path.name not in seen_receipts)
        seen_receipts.add(receipt_path.name)
        receipt_bytes = bounded_read(receipt_path, 65536)
        require(sha256(receipt_bytes) == pin["receiptSha256"])
        receipt = parse(receipt_bytes)
        exact_keys(receipt, RECEIPT_KEYS)
        require(type(receipt["schemaVersion"]) is int and receipt["schemaVersion"] == 1)
        require(receipt["synthetic"] is True and receipt["productionDtoAndSerializer"] is True)
        for key in ("producerRepository", "producerCommit", "nativeRunUrl", "dtoSourceSha256", "serializerSourceSha256"):
            require(receipt[key] == pin[key])
        hashes = receipt["fixtures"]
        exact_keys(hashes, PRODUCERS[repository])
        for name, expected_hash in hashes.items():
            require(digest(expected_hash))
            actual_bytes = bounded_read(local_file(fixture_directory, name), 262144)
            require(sha256(actual_bytes) == expected_hash)
            payload = parse(actual_bytes)
            source = name.split("-", 1)[0]
            if source == "invoice":
                require(type(payload) is dict and type(payload.get("Days")) is list)
                for day in payload["Days"]:
                    require(type(day) is dict and isinstance(day.get("DayUtc"), str))
                    require(re.fullmatch(r"\d{4}-\d{2}-\d{2}T00:00:00Z", day["DayUtc"]) is not None)
            if name == "invoice-null-currency.json":
                validate_null_currency_control(payload)
                continue
            try:
                outcomes.validate_payload(payload, source, FROM, TO)
            except (outcomes.InvalidReceipt, TypeError, OverflowError):
                raise InvalidWireProof("Approved synthetic producer wire evidence required.") from None
        verified.append({"producerRepository": repository, "producerCommit": pin["producerCommit"],
                         "receiptSha256": pin["receiptSha256"], "fixtureCount": len(hashes)})
    require(seen_producers == set(PRODUCERS))
    return {"status": "verified-against-approved-producer-receipts", "fixtureCount": 9,
            "producers": verified, "networkChecked": False, "liveReadbackVerified": False,
            "wholeSourceClosure": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--approval-sha256", required=True)
    parser.add_argument("--receipts", type=Path, required=True)
    parser.add_argument("--fixtures", type=Path, default=Path(__file__).resolve().parent / "fixtures")
    args = parser.parse_args()
    try:
        result = verify(args.approval, args.approval_sha256, args.receipts, args.fixtures)
    except (InvalidWireProof, OSError, ValueError, TypeError, OverflowError):
        print("[producer-wire] unavailable: approved synthetic evidence is absent or invalid.", file=sys.stderr)
        return 2
    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
