# Aggregate outcome receipt validator

This tool consumes already authorized, aggregate-only HTTP receipts from the
Legacy quotation and invoice outcome readbacks. It does not make network
requests, read credentials or browser sessions, access databases, identify a
customer, infer Ads attribution, or establish whether a customer is qualified.

The receipt envelope is an operational handoff owned by the authorized
collector. Its `payload` is the original parsed Legacy API JSON body:

```json
{
  "source": "quotation",
  "capturedAtUtc": "2026-09-03T05:00:00Z",
  "httpStatus": 200,
  "payload": {
    "FromUtc": "2026-08-25T17:00:00Z",
    "ToUtc": "2026-09-01T17:00:00Z",
    "Days": [],
    "TechnicalConversionAvailability": "unavailable",
    "QualifiedCustomerAvailability": "unavailable",
    "RevenueAvailability": "unavailable"
  }
}
```

All checked-in fixtures are synthetic. For denied or failed fetches, retain the
actual HTTP status with a null payload; never store a response body that could
contain identifiers. The validator does not authenticate file provenance.

```powershell
python tools/analytics/outcome_receipts.py --quotation <quotation-receipt.json> --invoice <invoice-receipt.json> --from-utc 2026-08-25T17:00:00Z --to-utc 2026-09-01T17:00:00Z --output <aggregate-report.json>
```

The default freshness limit is 24 hours. Windows must be complete, increasing,
UTC, at most 31 days, and exactly match each payload. Exit status is zero only
when both sources are available; otherwise it is two. Missing, denied, invalid,
future, and stale sources retain null counts and days. An explicit empty `Days`
array is available and has zero totals.

The input wire is intentionally PascalCase because Legacy service JSON options
set `PropertyNamingPolicy = null`. Unknown fields, identifiers, wrong casing,
missing fields, nulls, wrong types, duplicate fields, unsupported currencies,
and unreconciled counts fail closed without echoing source values. Decimal
amounts remain exact and are never converted through binary floating point.

`persistedQuotation` uses quotation creation date, `acceptedQuotation` uses the
first accepted timestamp, and `paidInvoice` uses paid invoice payment date.
Source-attributed means both reconciliation keys exist; it is not Ads
attribution. Quoted amounts are not revenue. Paid totals preserve the producer's
source-currency grouping without currency conversion or settlement inference.
Cross-stage funnel ratios are unsupported because the cohorts differ.

The quotation fixture shape matches the canonical .NET 10
`Legacy.Maliev.QuotationService` DTO and System.Text.Json settings. The invoice
fixture preserves the approved source contract, but
`Legacy.Maliev.AccountingService` does not yet expose the corresponding
paid-invoice outcome DTO or route. The fixture harness therefore owns an
explicit local contract model and must be updated when that producer boundary
lands; passing fixture verification is not deployed invoice-readback evidence.

## Validation

```powershell
dotnet build tools/analytics/WireFixtures/WireFixtures.csproj -c Release --nologo -v minimal
dotnet run --no-build -c Release --project tools/analytics/WireFixtures -- --verify tools/analytics/fixtures
python -W error -m py_compile tools/analytics/outcome_receipts.py tools/analytics/tests/test_outcome_receipts.py
python -W error -m unittest discover -s tools/analytics/tests -p 'test_*.py' -v
git diff --check
```

Use `--write` only for a reviewed producer-wire change. No collection,
deployment, qualification, or campaign-performance claim is configured here.
