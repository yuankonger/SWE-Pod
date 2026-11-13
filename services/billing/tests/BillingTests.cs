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

    private static QuoteRequest Request(int postal, params (decimal price, int qty)[] lines) =>
        new(postal, lines.Select(l => new QuoteLine("BOX-S", l.qty, l.price)).ToList());

    [Fact]
    public void QuoteAddsTaxRoundedToCents()
    {
        var b = new BillingService(new Recorder());
        var q = b.Quote(Request(94105, (24.99m, 2)));
        Assert.Equal(49.98m, q.Subtotal);
        Assert.Equal(4.37m, q.Tax);          // 49.98 * 0.0875 = 4.37325
        Assert.Equal(54.35m, q.Total);
        Assert.Equal(1.50m, b.Quote(Request(10001, (24.99m, 1))).Tax);   // 24.99 * 0.06 = 1.4994
    }

    [Fact]
    public void QuoteRejectsEmptyAndInvalidLines()
    {
        var b = new BillingService(new Recorder());
        Assert.Throws<BillingException>(() => b.Quote(new QuoteRequest(94105, new())));
        Assert.Throws<BillingException>(() => b.Quote(Request(94105, (5m, 0))));
    }

    [Fact]
    public void ChargeRequiresAPositiveAmount()
    {
        var b = new BillingService(new Recorder());
        Assert.Equal("succeeded", b.Charge(new ChargeRequest("ord_1", "c1", 54.35m)).Status);
        Assert.Throws<BillingException>(() => b.Charge(new ChargeRequest("ord_1", "c1", 0m)));
    }

    [Fact]
    public void OrderPlacedIssuesOneInvoiceAndPublishesIt()
    {
        var rec = new Recorder();
        var b = new BillingService(rec);
        var e = JsonDocument.Parse("""
            {"event_id":"evt_1","event_type":"order.placed","occurred_at":"2026-01-01T00:00:00Z","data":{"order":{
              "order_id":"ord_1","customer_id":"c1","email":"a@example.com","postal_code":94105,"status":"paid",
              "lines":[{"sku":"BOX-S","name":"Small monthly box","qty":2,"unit_price":24.99}],
              "subtotal":49.98,"tax":4.37,"total":54.35}}}
            """).RootElement;
        var inv = b.Handle(e);
        Assert.NotNull(inv);
        Assert.Equal(54.35m, inv!.Total);
        Assert.Equal(49.98m, inv.Lines[0].Amount);
        Assert.Null(b.Handle(e));                       // the same event again issues nothing
        Assert.Single(b.Invoices("ord_1"));
        Assert.Single(rec.Events);
        Assert.Contains("\"event_type\":\"invoice.paid\"", rec.Events[0]);
        Assert.Contains("\"invoice_id\"", rec.Events[0]);
    }
}
