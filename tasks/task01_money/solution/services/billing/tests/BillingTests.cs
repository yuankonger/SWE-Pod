using System.Text.Json;
using Seedco.Billing;
using Xunit;

public class BillingTests
{
    private class Recorder : IEventPublisher
    {
        public List<string> Events = new();
        public void Publish(string topic, object envelope) => Events.Add(JsonSerializer.Serialize(envelope, Json.Options));
    }

    private static QuoteRequest Request(int postal, params (long cents, int qty)[] lines) =>
        new(postal, lines.Select(l => new QuoteLine("BOX-S", l.qty, Money.Usd(l.cents))).ToList());

    [Fact]
    public void QuoteAddsTaxRoundedToCents()
    {
        var b = new BillingService(new Recorder());
        var q = b.Quote(Request(94105, (2499, 2)));
        Assert.Equal(Money.Usd(4998), q.Subtotal);
        Assert.Equal(Money.Usd(437), q.Tax);          // 4998 * 8.75% = 437.325
        Assert.Equal(Money.Usd(5435), q.Total);
        Assert.Equal(Money.Usd(150), b.Quote(Request(10001, (2499, 1))).Tax);   // 2499 * 6% = 149.94
        Assert.Equal(Money.Usd(974), b.Quote(Request(10001, (16225, 1))).Tax);  // 16225 * 6% = 973.5, half up
    }

    [Fact]
    public void QuoteRejectsEmptyAndInvalidLines()
    {
        var b = new BillingService(new Recorder());
        Assert.Throws<BillingException>(() => b.Quote(new QuoteRequest(94105, new())));
        Assert.Throws<BillingException>(() => b.Quote(Request(94105, (500, 0))));
    }

    [Fact]
    public void ChargeRequiresAPositiveAmount()
    {
        var b = new BillingService(new Recorder());
        Assert.Equal("succeeded", b.Charge(new ChargeRequest("ord_1", "c1", Money.Usd(5435))).Status);
        Assert.Throws<BillingException>(() => b.Charge(new ChargeRequest("ord_1", "c1", Money.Usd(0))));
    }

    [Fact]
    public void OrderPlacedIssuesOneInvoiceAndPublishesIt()
    {
        var rec = new Recorder();
        var b = new BillingService(rec);
        var e = JsonDocument.Parse("""
            {"event_id":"evt_1","event_type":"order.placed","occurred_at":"2026-01-01T00:00:00Z","data":{"order":{
              "order_id":"ord_1","customer_id":"c1","email":"a@example.com","postal_code":94105,"status":"paid",
              "lines":[{"sku":"BOX-S","name":"Small monthly box","qty":2,"unit_price":{"currency":"USD","minor":2499}}],
              "subtotal":{"currency":"USD","minor":4998},"tax":{"currency":"USD","minor":437},"total":{"currency":"USD","minor":5435}}}}
            """).RootElement;
        var inv = b.Handle(e);
        Assert.NotNull(inv);
        Assert.Equal(Money.Usd(5435), inv!.Total);
        Assert.Equal(Money.Usd(4998), inv.Lines[0].Amount);
        Assert.Null(b.Handle(e));                       // the same event again issues nothing
        Assert.Single(b.Invoices("ord_1"));
        Assert.Single(rec.Events);
        Assert.Contains("\"event_type\":\"invoice.paid\"", rec.Events[0]);
        Assert.Contains("\"invoice_id\"", rec.Events[0]);
    }
}
