"""Validate aggregate-only Legacy API receipts; never infer qualification or Ads attribution."""

import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path


class InvalidReceipt(ValueError):
    """A receipt cannot safely be used as available aggregate evidence."""


def require(condition, message):
    if not condition:
        raise InvalidReceipt(message)


def keys(value, expected):
    require(isinstance(value, dict) and set(value) == set(expected), "Unexpected or missing fields")


def utc(value):
    require(isinstance(value, str) and value.endswith("Z"), "UTC timestamp required")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise InvalidReceipt("Invalid UTC timestamp") from None


def count(value):
    require(type(value) is int and 0 <= value <= 2147483647, "Invalid count")
    return value


def decimal_amount(value):
    require(type(value) in (int, Decimal), "Decimal JSON number required")
    require(Decimal(value).is_finite(), "Finite amount required")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON field")
        result[key] = value
    return result


def load_json(text):
    try:
        return json.loads(
            text,
            parse_float=Decimal,
            object_pairs_hook=unique_object,
            parse_constant=lambda _: require(False, "Invalid JSON number"),
        )
    except (ValueError, TypeError):
        raise InvalidReceipt("Invalid aggregate JSON") from None


def validate_payload(payload, source, from_utc, to_utc):
    """Allowlist the exact Legacy PascalCase wire contract before retaining source data."""
    start, end = utc(from_utc), utc(to_utc)
    require(start < end and end - start <= timedelta(days=31), "Invalid reporting window")
    require(source in ("quotation", "invoice"), "Unknown aggregate source")
    availability = [
        "TechnicalConversionAvailability",
        "QualifiedCustomerAvailability",
        "RevenueAvailability",
    ]
    keys(payload, ["FromUtc", "ToUtc", "Days"] + (availability if source == "quotation" else []))
    require(utc(payload["FromUtc"]) == start and utc(payload["ToUtc"]) == end, "Source window mismatch")
    if source == "quotation":
        require(all(payload[key] == "unavailable" for key in availability), "Unsupported availability claim")
    require(isinstance(payload["Days"], list), "Days array required")
    previous_day = None
    stages = ["persistedQuotation", "acceptedQuotation"] if source == "quotation" else ["paidInvoice"]
    amount_key = "AcceptedQuotedAmountsByCurrency" if source == "quotation" else "PaidInvoiceAmountsByCurrency"
    totals = {stage: 0 for stage in stages}
    for day in payload["Days"]:
        fields = ["DayUtc", amount_key]
        for stage in stages:
            pascal_stage = stage[0].upper() + stage[1:]
            fields.extend([
                pascal_stage + "Count",
                "SourceAttributed" + pascal_stage + "Count",
                "Unattributed" + pascal_stage + "Count",
            ])
        keys(day, fields)
        require(
            isinstance(day["DayUtc"], str)
            and re.fullmatch(r"\d{4}-\d{2}-\d{2}T00:00:00(?:Z)?", day["DayUtc"]),
            "Invalid UTC day label",
        )
        current = utc(day["DayUtc"].removesuffix("Z") + "Z")
        require(current < end and current + timedelta(days=1) > start, "Day outside window")
        require(previous_day is None or previous_day < current, "Days not uniquely ordered")
        previous_day = current
        for stage in stages:
            pascal_stage = stage[0].upper() + stage[1:]
            total = count(day[pascal_stage + "Count"])
            require(
                count(day["SourceAttributed" + pascal_stage + "Count"])
                + count(day["Unattributed" + pascal_stage + "Count"])
                == total,
                "Attribution counts do not reconcile",
            )
            totals[stage] += total
        require(isinstance(day[amount_key], list), "Currency array required")
        previous_currency = None
        represented = 0
        for amount in day[amount_key]:
            if source == "quotation":
                keys(amount, ["CurrencyId", "QuotedAmount", "AcceptedQuotationCount"])
                currency = count(amount["CurrencyId"])
                decimal_amount(amount["QuotedAmount"])
                represented += count(amount["AcceptedQuotationCount"])
            else:
                keys(amount, ["Currency", "PaidInvoiceTotal", "PaidInvoiceCount"])
                currency = amount["Currency"]
                require(
                    isinstance(currency, str) and re.fullmatch(r"[A-Z]{3}|UNSPECIFIED", currency),
                    "Unsupported currency code",
                )
                decimal_amount(amount["PaidInvoiceTotal"])
                represented += count(amount["PaidInvoiceCount"])
            require(previous_currency is None or previous_currency < currency, "Currencies not uniquely ordered")
            previous_currency = currency
        if source == "invoice":
            require(represented == day["PaidInvoiceCount"], "Currency counts do not reconcile")
        else:
            require(represented <= day["AcceptedQuotationCount"], "Currency counts exceed accepted count")
    return totals


def consume(receipt, source, from_utc, to_utc, now_utc, max_age_hours=24):
    """Invalid, failed, missing, or stale receipts carry no numerical facts."""
    unavailable = {"availability": "unavailable", "count": None}
    result = {
        "source": source,
        "availability": "unavailable",
        "reason": "missing_receipt",
        "fromUtc": from_utc,
        "toUtc": to_utc,
        "capturedAtUtc": None,
        "days": None,
        "counts": None,
        "qualifiedCustomer": unavailable.copy(),
        "technicalConversion": unavailable.copy(),
        "channelEvidenceAvailability": "unavailable",
    }
    if receipt is None:
        return result
    try:
        keys(receipt, ["source", "capturedAtUtc", "httpStatus", "payload"])
        require(receipt["source"] == source, "Source mismatch")
        captured, now = utc(receipt["capturedAtUtc"]), utc(now_utc)
        require(type(receipt["httpStatus"]) is int and 100 <= receipt["httpStatus"] <= 599, "Invalid HTTP status")
        if receipt["httpStatus"] != 200:
            result["reason"] = "access_denied" if receipt["httpStatus"] in (401, 403) else "http_failure"
            return result
        require(max_age_hours > 0, "Positive freshness limit required")
        totals = validate_payload(receipt["payload"], source, from_utc, to_utc)
        if captured > now or now - captured > timedelta(hours=max_age_hours):
            result["reason"] = "stale_or_future_receipt"
            return result
        require(captured >= utc(to_utc), "Reporting window is not complete")
        result.update(
            availability="available",
            reason=None,
            capturedAtUtc=receipt["capturedAtUtc"],
            days=receipt["payload"]["Days"],
            counts=totals,
        )
    except (InvalidReceipt, TypeError, OverflowError):
        result["reason"] = "invalid_receipt"
    return result


def json_text(value):
    """Serialize Decimal exactly as JSON numbers without binary float conversion."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return "{" + ",".join(json.dumps(key) + ":" + json_text(item) for key, item in value.items()) + "}"
    if isinstance(value, list):
        return "[" + ",".join(json_text(item) for item in value) + "]"
    return json.dumps(value, allow_nan=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quotation", type=Path)
    parser.add_argument("--invoice", type=Path)
    parser.add_argument("--from-utc", required=True)
    parser.add_argument("--to-utc", required=True)
    parser.add_argument("--max-age-hours", type=int, default=24)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    try:
        require(
            timedelta(0) < utc(args.to_utc) - utc(args.from_utc) <= timedelta(days=31),
            "Invalid reporting window",
        )
        require(args.max_age_hours > 0, "Positive freshness limit required")
    except (InvalidReceipt, TypeError):
        parser.error("Use an increasing UTC window up to 31 days and positive freshness limit")
    results = []
    for source in ("quotation", "invoice"):
        path = getattr(args, source)
        try:
            value = load_json(path.read_text(encoding="utf-8-sig")) if path else None
        except (OSError, UnicodeError, InvalidReceipt):
            value = {}
        results.append(consume(value, source, args.from_utc, args.to_utc, now, args.max_age_hours))
    args.output.write_text(json_text({"capturedAtUtc": now, "sources": results}) + "\n", encoding="utf-8")
    return 0 if all(item["availability"] == "available" for item in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
