using System.Text.Json;
using System.Text.Json.Serialization;

JsonSerializerOptions settings = new()
{
    DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    PropertyNamingPolicy = null,
    DictionaryKeyPolicy = null,
};
DateTime from = new(2026, 8, 25, 17, 0, 0, DateTimeKind.Utc);
DateTime to = from.AddDays(7);
DateTime day = new(2026, 8, 26, 0, 0, 0, DateTimeKind.Unspecified);
QuotationOutcomeReadback quote = new(from, to, []);
PaidInvoiceOutcomeReadback invoice = new(from, to, []);
SortedDictionary<string, string> fixtures = [];

void Add(string name, object value) =>
    fixtures.Add(name, JsonSerializer.Serialize(value, settings) + "\n");

Add("quotation-empty.json", quote);
Add("invoice-empty.json", invoice);
quote = quote with { Days = [new(day, 0, 0, 0, 0, 0, 0, [])] };
invoice = invoice with { Days = [new(day, 0, 0, 0, [])] };
Add("quotation-zero.json", quote);
Add("invoice-zero.json", invoice);
quote = quote with
{
    Days =
    [
        new(
            day,
            3,
            2,
            1,
            1,
            2,
            1,
            [new(1, 123.4500m, 1), new(2, 9876543210.12345678m, 1)]),
    ],
};
invoice = invoice with
{
    Days =
    [
        new(day, 3, 1, 2, [new("THB", 120.5000m, 2), new("USD", 25.01m, 1)]),
    ],
};
Add("quotation-mixed.json", quote);
Add("invoice-mixed.json", invoice);
invoice = invoice with
{
    Days = [new(day, 1, 0, 1, [new(null, 0.0m, 1)])],
};
Add("invoice-null-currency.json", invoice);

if (args.Length != 2 || (args[0] != "--write" && args[0] != "--verify"))
{
    throw new ArgumentException("Use --write or --verify followed by the fixture directory.");
}

Directory.CreateDirectory(args[1]);
foreach ((string name, string value) in fixtures)
{
    string path = Path.Combine(args[1], name);
    if (args[0] == "--write")
    {
        File.WriteAllText(path, value);
    }
    else if (!File.Exists(path) || File.ReadAllText(path) != value)
    {
        throw new InvalidOperationException("Wire fixture differs: " + name);
    }
}

Console.WriteLine($"{fixtures.Count} Legacy aggregate DTO wire fixtures {args[0][2..]} passed.");

internal sealed record QuotationOutcomeReadback(
    DateTime FromUtc,
    DateTime ToUtc,
    IReadOnlyList<QuotationOutcomeReadbackDay> Days)
{
    public string TechnicalConversionAvailability { get; } = "unavailable";

    public string QualifiedCustomerAvailability { get; } = "unavailable";

    public string RevenueAvailability { get; } = "unavailable";
}

internal sealed record QuotationOutcomeReadbackDay(
    DateTime DayUtc,
    int PersistedQuotationCount,
    int AcceptedQuotationCount,
    int SourceAttributedPersistedQuotationCount,
    int SourceAttributedAcceptedQuotationCount,
    int UnattributedPersistedQuotationCount,
    int UnattributedAcceptedQuotationCount,
    IReadOnlyList<AcceptedQuotedAmountByCurrency> AcceptedQuotedAmountsByCurrency);

internal sealed record AcceptedQuotedAmountByCurrency(
    int CurrencyId,
    decimal QuotedAmount,
    int AcceptedQuotationCount);

internal sealed record PaidInvoiceOutcomeReadback(
    DateTime FromUtc,
    DateTime ToUtc,
    IReadOnlyList<PaidInvoiceOutcomeReadbackDay> Days);

internal sealed record PaidInvoiceOutcomeReadbackDay(
    DateTime DayUtc,
    int PaidInvoiceCount,
    int SourceAttributedPaidInvoiceCount,
    int UnattributedPaidInvoiceCount,
    IReadOnlyList<PaidInvoiceAmountByCurrency> PaidInvoiceAmountsByCurrency);

internal sealed record PaidInvoiceAmountByCurrency(
    string? Currency,
    decimal PaidInvoiceTotal,
    int PaidInvoiceCount);
