using System.Text.Json;
using Seedco.Billing;
using Xunit;

public class BillingTests
{
    private class Recorder : IEventPublisher
    {
        public List<string> Events = new();
        public void Publish(string topic, object envelope) => Events.Add(JsonSerializer.Serialize(envelope, Json.Options));
        public int Count(string type) => Events.Count(e => e.Contains($"\"event_type\":\"{type}\""));
    }

    private static QuoteRequest Request(int postal, params (decimal price, int qty)[] lines) =>
        new(postal, lines.Select(l => new QuoteLine("BOX-S", l.qty, l.price)).ToList());

    private static JsonElement OrderEvent(string eventId, string type, string orderId = "ord_1", string occurredAt = "2026-01-01T00:00:00Z") =>
        JsonDocument.Parse($$"""
            {"event_id":"{{eventId}}","event_type":"{{type}}","occurred_at":"{{occurredAt}}","data":{"order":{
              "order_id":"{{orderId}}","customer_id":"c1","email":"a@example.com","postal_code":94105,"status":"paid",
              "payment_method":"pm_card_ok",
              "lines":[{"sku":"BOX-S","name":"Small monthly box","qty":2,"unit_price":24.99},
                       {"sku":"ADD-TEA","name":"Tea add-on","qty":1,"unit_price":6.25}],
              "subtotal":56.23,"tax":4.92,"total":61.15} } }
            """).RootElement;

    /// <summary>Billing with one paid order (ord_1) placed on 1 January: one invoice, one BOX-S subscription.</summary>
    private static (BillingService b, Recorder rec, Subscription sub) WithOrder()
    {
        var rec = new Recorder();
        var b = new BillingService(rec);
        b.Charge(new ChargeRequest("ord_1", "c1", 61.15m, "a@example.com"), "ord_1");
        b.Handle(OrderEvent("evt_1", "order.placed"));
        return (b, rec, b.Subscriptions("c1").Single());
    }

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
    public void ARepeatedIdempotencyKeyChargesOnce()
    {
        var b = new BillingService(new Recorder());
        var first = b.Charge(new ChargeRequest("ord_1", "c1", 54.35m), "key-1");
        Assert.Equal(first.PaymentId, b.Charge(new ChargeRequest("ord_1", "c1", 54.35m), "key-1").PaymentId);
        Assert.Single(b.Payments("ord_1"));
        Assert.Throws<IdempotencyConflict>(() => b.Charge(new ChargeRequest("ord_1", "c1", 99m), "key-1"));
    }

    [Fact]
    public void ADeclinedCardFailsThePaymentAndPublishesIt()
    {
        var rec = new Recorder();
        var p = new BillingService(rec).Charge(new ChargeRequest("ord_1", "c1", 54.35m, "a@example.com", BillingService.DecliningPaymentMethod));
        Assert.Equal(("failed", "card_declined"), (p.Status, p.FailureReason));
        Assert.Equal(1, rec.Count("payment.failed"));
        Assert.Contains("\"email\":\"a@example.com\"", rec.Events[0]);
    }

    [Fact]
    public void OrderPlacedIssuesOneInvoiceAndPublishesIt()
    {
        var (b, rec, sub) = WithOrder();
        var inv = b.Invoices("ord_1").Single();
        Assert.Equal(61.15m, inv.Total);
        Assert.Equal(new[] { ("RECURRING", 49.98m), ("FIXED", 6.25m) }, inv.Lines.Select(l => (l.Type, l.Amount)));
        Assert.Null(b.Handle(OrderEvent("evt_1", "order.placed")));                       // the same event again issues nothing
        Assert.Single(b.Invoices("ord_1"));
        Assert.Equal(1, rec.Count("invoice.paid"));
        Assert.Contains("\"invoice_id\"", rec.Events[0]);
        Assert.Equal(("BOX-S", 2, "active", "2026-01-01", "2026-02-01"), (sub.Sku, sub.Qty, sub.Status, sub.CurrentPeriodStart, sub.CurrentPeriodEnd));
    }

    [Fact]
    public void ProrationSplitsAPeriodByDays()
    {
        // 100 a month upgraded to 200 on 15 January: 14 of 31 days used, 17 left.
        Assert.Equal(109.68m, BillingService.Prorate(200m, 17, 31));
        Assert.Equal(54.84m, BillingService.Prorate(100m, 17, 31));
        Assert.Equal(45.16m, 100m - BillingService.Prorate(100m, 17, 31));
    }

    [Fact]
    public void AnUpgradeStartsNowWithACreditAndAProratedCharge()
    {
        var (b, rec, sub) = WithOrder();
        var changed = b.ChangePlan(sub.SubscriptionId, new ChangePlanRequest("BOX-L", "2026-01-15"));
        Assert.Equal(("BOX-L", 39.50m, (string?)null), (changed.Sku, changed.UnitPrice, changed.PendingSku));
        var inv = b.Invoices("ord_1").Single(i => i.Reason == "plan_change");
        // 2 boxes, 17 of 31 days: credit 49.98 * 17/31 = 27.41, charge 79.00 * 17/31 = 43.32; tax 8.75% of 15.91 = 1.39
        Assert.Equal(new[] { ("CREDIT", -27.41m), ("PRORATION", 43.32m) }, inv.Lines.Select(l => (l.Type, l.Amount)));
        Assert.Equal((15.91m, 1.39m, 17.30m), (inv.Subtotal, inv.Tax, inv.Total));
        Assert.Equal(17.30m, b.Payments("ord_1").Last().Amount);
        Assert.Contains("\"change\":\"plan_changed\"", rec.Events.Last());
    }

    [Fact]
    public void ADowngradeWaitsForThePeriodToEnd()
    {
        var (b, rec, _) = WithOrder();
        var large = b.ChangePlan(b.Subscriptions("c1").Single().SubscriptionId, new ChangePlanRequest("BOX-L", "2026-01-15"));
        var pending = b.ChangePlan(large.SubscriptionId, new ChangePlanRequest("BOX-S", "2026-01-20"));
        Assert.Equal(("BOX-L", "BOX-S"), (pending.Sku, pending.PendingSku));
        Assert.Contains("\"change\":\"downgrade_scheduled\"", rec.Events.Last());
        Assert.Equal(0, b.RunRenewals("2026-01-31").Renewed);                 // not due yet
        Assert.Equal(1, b.RunRenewals("2026-02-01").Renewed);
        var s = b.Subscriptions("c1").Single();
        Assert.Equal(("BOX-S", (string?)null, "2026-02-01", "2026-03-01"), (s.Sku, s.PendingSku, s.CurrentPeriodStart, s.CurrentPeriodEnd));
        var renewal = b.Invoices("ord_1").Single(i => i.Reason == "renewal");
        Assert.Equal((49.98m, 4.37m, 54.35m), (renewal.Subtotal, renewal.Tax, renewal.Total));
        Assert.Equal(s.SubscriptionId, renewal.SubscriptionId);
    }

    [Fact]
    public void AFailingRenewalIsRetriedThenTheSubscriptionIsTerminated()
    {
        var (b, rec, sub) = WithOrder();
        b.SetPaymentMethod("c1", BillingService.DecliningPaymentMethod);
        Assert.Equal(1, b.RunRenewals("2026-02-01").Failed);
        Assert.Equal(("past_due", 1, "2026-02-04"), Dunning(b));
        Assert.Equal(0, b.RunRenewals("2026-02-03").Failed);                  // the retry is not due yet
        Assert.Equal(1, b.RunRenewals("2026-02-04").Failed);
        Assert.Equal(1, b.RunRenewals("2026-02-07").Ended);
        Assert.Equal("terminated", b.Subscriptions("c1").Single().Status);
        Assert.Equal(3, rec.Count("payment.failed"));
        Assert.Contains("\"change\":\"terminated\"", rec.Events.Last());

        static (string, int, string?) Dunning(BillingService b)
        {
            var s = b.Subscriptions("c1").Single();
            return (s.Status, s.FailedAttempts, s.NextAttempt);
        }
    }

    [Fact]
    public void ARetrySucceedsOnceThePaymentMethodIsReplaced()
    {
        var (b, _, _) = WithOrder();
        b.SetPaymentMethod("c1", BillingService.DecliningPaymentMethod);
        b.RunRenewals("2026-02-01");
        b.SetPaymentMethod("c1", "pm_card_new");
        Assert.Equal(1, b.RunRenewals("2026-02-04").Renewed);
        var s = b.Subscriptions("c1").Single();
        Assert.Equal(("active", 0, "2026-03-01"), (s.Status, s.FailedAttempts, s.CurrentPeriodEnd));
    }

    [Fact]
    public void ACancelledSubscriptionEndsAtThePeriodEnd()
    {
        var (b, rec, sub) = WithOrder();
        Assert.True(b.Cancel(sub.SubscriptionId).CancelAtPeriodEnd);
        b.Cancel(sub.SubscriptionId);
        Assert.Equal(1, rec.Count("subscription.updated"));
        Assert.Equal(1, b.RunRenewals("2026-02-01").Ended);
        Assert.Equal("canceled", b.Subscriptions("c1").Single().Status);
        Assert.DoesNotContain(b.Invoices("ord_1"), i => i.Reason == "renewal");
    }

    [Fact]
    public void ACancelledOrderIsRefundedOnce()
    {
        var (b, _, _) = WithOrder();
        b.Handle(OrderEvent("evt_2", "order.cancelled"));
        b.Handle(OrderEvent("evt_2", "order.cancelled"));
        Assert.Equal(61.15m, b.Refunds("ord_1").Single().Amount);
        Assert.Equal("refunded", b.Invoices("ord_1").Single().Status);
        Assert.Equal("canceled", b.Subscriptions("c1").Single().Status);
    }

    [Fact]
    public void RecordsSurviveARestart()
    {
        var path = Path.Combine(Path.GetTempPath(), $"seedco-billing-{Guid.NewGuid():N}.db");
        using (var store = new Store(path))
        {
            var b = new BillingService(new Recorder(), store);
            b.Charge(new ChargeRequest("ord_1", "c1", 61.15m), "ord_1");
            b.Handle(OrderEvent("evt_1", "order.placed"));
            store.SetOffset("orders", 5);
        }
        using var reopened = new Store(path);
        var again = new BillingService(new Recorder(), reopened);
        Assert.Null(again.Handle(OrderEvent("evt_1", "order.placed")));
        Assert.Single(again.Invoices("ord_1"));
        Assert.Single(again.Subscriptions("c1"));
        Assert.Equal(5, reopened.Offset("orders"));
        Assert.Single(again.Payments("ord_1"));
    }
}
