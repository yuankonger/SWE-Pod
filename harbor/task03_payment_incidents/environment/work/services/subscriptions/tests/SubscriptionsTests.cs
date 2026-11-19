using System.Text.Json;
using Seedco.Subscriptions;
using Xunit;

public class SubscriptionsTests
{
    /// <summary>Core and payments, without tax: an order's total is its net price, and one card always declines.</summary>
    private class FakeCommerce : ICommerce
    {
        public List<(string Sku, int Qty, decimal UnitPrice, string Reason, string Key)> Bills = new();
        public string CardOnFile = "pm_card_ok";
        public string PaymentMethodOf(string pspReference) => CardOnFile;
        public List<(string Order, string Key, string? Value)> Notes = new();
        public void Annotate(string orderId, string key, string? value) => Notes.Add((orderId, key, value));

        public Billed Bill(Subscription s, string sku, int qty, decimal unitPrice, string reason, string idempotencyKey)
        {
            Bills.Add((sku, qty, unitPrice, reason, idempotencyKey));
            var declined = s.PaymentMethod == "pm_card_declined";
            return new Billed("order_" + Bills.Count, !declined, unitPrice * qty, declined ? "card_declined" : "");
        }
    }

    private class Recorder : INotifier
    {
        public List<(string Event, string Payload)> Sent = new();
        public void Notify(string notifyEvent, object payload) => Sent.Add((notifyEvent, JsonSerializer.Serialize(payload)));
        public IEnumerable<string> Events => Sent.Select(s => s.Event);
    }

    private static JsonElement Event(string type, string orderId = "T3JkZXI6MQ==", string metadata = "[]", string issuedAt = "2026-01-01T00:00:00Z") =>
        JsonDocument.Parse($$"""
            {"__typename":"{{type}}","issuedAt":"{{issuedAt}}","order":{"id":"{{orderId}}","userEmail":"pat@example.com","metadata":{{metadata}},
              "shippingAddress":{"firstName":"Pat","lastName":"Lee","streetAddress1":"1 Main St","city":"San Francisco","postalCode":"94105",
                "countryArea":"CA","country":{"code":"US"} },
              "lines":[{"productSku":"BOX-S","quantity":2},{"productSku":"ADD-TEA","quantity":1}],
              "transactions":[{"pspReference":"pi_1"}] } }
            """).RootElement;

    /// <summary>The app after one paid order placed on 1 January: one BOX-S subscription for two boxes.</summary>
    private static (SubscriptionsApp app, FakeCommerce commerce, Recorder mail, Subscription sub) WithOrder(Store? store = null)
    {
        var commerce = new FakeCommerce();
        var mail = new Recorder();
        var app = new SubscriptionsApp(store ?? new Store(null, "subscriptions"), commerce, mail);
        app.Handle(Event("OrderFullyPaid"));
        return (app, commerce, mail, app.Subscriptions("pat@example.com").Single());
    }

    [Fact]
    public void APaidOrderStartsOneSubscriptionPerPlanLine()
    {
        var (app, _, _, sub) = WithOrder();
        Assert.Equal(("BOX-S", 2, "active", "2026-01-01", "2026-02-01", "pm_card_ok"),
            (sub.Sku, sub.Qty, sub.Status, sub.CurrentPeriodStart, sub.CurrentPeriodEnd, sub.PaymentMethod));
        Assert.Equal(24.99m, sub.UnitPrice.Amount);
        Assert.Equal("94105", sub.ShippingAddress.PostalCode);
        Assert.Empty(app.Handle(Event("OrderFullyPaid")));                       // a delivery can arrive twice
        Assert.Single(app.Subscriptions());
    }

    [Fact]
    public void AnOrderThisAppCreatedIsNotANewSale()
    {
        var (app, _, _, _) = WithOrder();
        Assert.Empty(app.Handle(Event("OrderFullyPaid", "T3JkZXI6Mg==", """[{"key":"subscription_id","value":"sub_1"}]""")));
        Assert.Single(app.Subscriptions());
    }

    [Fact]
    public void ProrationSplitsAPeriodByDays()
    {
        // 100 a month upgraded to 200 on 15 January: 14 of 31 days used, 17 left.
        Assert.Equal(109.68m, SubscriptionsApp.Prorate(200m, 17, 31));
        Assert.Equal(54.84m, SubscriptionsApp.Prorate(100m, 17, 31));
        Assert.Equal(45.16m, 100m - SubscriptionsApp.Prorate(100m, 17, 31));
    }

    [Fact]
    public void AnUpgradeStartsNowAndBillsTheProratedDifference()
    {
        var (app, commerce, mail, sub) = WithOrder();
        var changed = app.ChangePlan(sub.SubscriptionId, new ChangePlanRequest("BOX-L", "2026-01-15"));
        Assert.Equal(("BOX-L", 39.50m, (string?)null), (changed.Sku, changed.UnitPrice.Amount, changed.PendingSku));
        // 2 boxes, 17 of 31 days: new 79.00 * 17/31 = 43.32, old 49.98 * 17/31 = 27.41, due 15.91 before tax
        Assert.Equal(("BOX-L", 1, 15.91m, "plan_change"), (commerce.Bills[0].Sku, commerce.Bills[0].Qty, commerce.Bills[0].UnitPrice, commerce.Bills[0].Reason));
        Assert.Equal(new[] { "SUBSCRIPTION_PLAN_CHANGED" }, mail.Events);
        Assert.Contains("\"plan_name\":\"Large monthly box\"", mail.Sent[0].Payload);
    }

    [Fact]
    public void ADeclinedUpgradeLeavesThePlanAsItWas()
    {
        var (app, _, _, sub) = WithOrder();
        app.SetPaymentMethod(new PaymentMethodRequest("pat@example.com", "pm_card_declined"));
        Assert.Throws<PaymentDeclined>(() => app.ChangePlan(sub.SubscriptionId, new ChangePlanRequest("BOX-L", "2026-01-15")));
        Assert.Equal("BOX-S", app.Subscriptions().Single().Sku);
        Assert.Throws<BadRequest>(() => app.ChangePlan(sub.SubscriptionId, new ChangePlanRequest("NOPE")));
        Assert.Throws<NotFound>(() => app.Cancel("sub_missing"));
    }

    [Fact]
    public void ADowngradeWaitsForThePeriodToEnd()
    {
        var (app, commerce, mail, sub) = WithOrder();
        var large = app.ChangePlan(sub.SubscriptionId, new ChangePlanRequest("BOX-L", "2026-01-15"));
        var pending = app.ChangePlan(large.SubscriptionId, new ChangePlanRequest("BOX-S", "2026-01-20"));
        Assert.Equal(("BOX-L", "BOX-S"), (pending.Sku, pending.PendingSku));
        Assert.Equal("SUBSCRIPTION_DOWNGRADE_SCHEDULED", mail.Events.Last());
        Assert.Equal(0, app.RunRenewals("2026-01-31").Renewed);                 // not due yet
        Assert.Equal(1, app.RunRenewals("2026-02-01").Renewed);
        var s = app.Subscriptions().Single();
        Assert.Equal(("BOX-S", (string?)null, "2026-02-01", "2026-03-01"), (s.Sku, s.PendingSku, s.CurrentPeriodStart, s.CurrentPeriodEnd));
        Assert.Equal(("BOX-S", 2, 24.99m, "renewal"), (commerce.Bills.Last().Sku, commerce.Bills.Last().Qty, commerce.Bills.Last().UnitPrice, commerce.Bills.Last().Reason));
        Assert.Equal(0, app.RunRenewals("2026-02-01").Renewed);                 // running twice on one day renews once
    }

    [Fact]
    public void AFailingRenewalIsRetriedThenTheSubscriptionIsTerminated()
    {
        var (app, commerce, mail, _) = WithOrder();
        app.SetPaymentMethod(new PaymentMethodRequest("pat@example.com", "pm_card_declined"));
        Assert.Equal(1, app.RunRenewals("2026-02-01").Failed);
        var s = app.Subscriptions().Single();
        Assert.Equal(("past_due", 1, "2026-02-04"), (s.Status, s.FailedAttempts, s.NextAttempt));
        Assert.Equal(0, app.RunRenewals("2026-02-03").Failed);                  // the retry is not due yet
        Assert.Equal(1, app.RunRenewals("2026-02-04").Failed);
        Assert.Equal(1, app.RunRenewals("2026-02-07").Ended);
        Assert.Equal("terminated", app.Subscriptions().Single().Status);
        Assert.Equal(3, mail.Events.Count(e => e == "SUBSCRIPTION_PAYMENT_FAILED"));
        Assert.Equal("SUBSCRIPTION_TERMINATED", mail.Events.Last());
        Assert.Contains("\"reason\":\"card_declined\"", mail.Sent[0].Payload);
        Assert.Equal(3, commerce.Bills.Select(b => b.Key).Distinct().Count());  // each attempt is its own charge
    }

    [Fact]
    public void ARetrySucceedsOnceThePaymentMethodIsReplaced()
    {
        var (app, _, _, _) = WithOrder();
        app.SetPaymentMethod(new PaymentMethodRequest("pat@example.com", "pm_card_declined"));
        app.RunRenewals("2026-02-01");
        app.SetPaymentMethod(new PaymentMethodRequest("pat@example.com", "pm_card_new"));
        Assert.Equal(1, app.RunRenewals("2026-02-04").Renewed);
        var s = app.Subscriptions().Single();
        Assert.Equal(("active", 0, "2026-03-01"), (s.Status, s.FailedAttempts, s.CurrentPeriodEnd));
    }

    [Fact]
    public void ACancelledSubscriptionEndsAtThePeriodEndAndACancelledOrderEndsItAtOnce()
    {
        var (app, commerce, mail, sub) = WithOrder();
        Assert.True(app.Cancel(sub.SubscriptionId).CancelAtPeriodEnd);
        app.Cancel(sub.SubscriptionId);
        Assert.Equal(new[] { "SUBSCRIPTION_CANCEL_SCHEDULED" }, mail.Events);
        Assert.Equal(1, app.RunRenewals("2026-02-01").Ended);
        Assert.Equal("canceled", app.Subscriptions().Single().Status);
        Assert.Empty(commerce.Bills);

        var (other, _, _, _) = WithOrder();
        other.Handle(Event("OrderCancelled"));
        Assert.Equal("canceled", other.Subscriptions().Single().Status);
    }

    [Fact]
    public void SubscriptionsSurviveARestart()
    {
        var path = Path.Combine(Path.GetTempPath(), $"seedco-subscriptions-{Guid.NewGuid():N}.db");
        string id;
        using (var store = new Store(path, "subscriptions")) id = WithOrder(store).sub.SubscriptionId;
        using var reopened = new Store(path, "subscriptions");
        var (again, _, _, sub) = WithOrder(reopened);                            // the same order event after the restart
        Assert.Equal(id, sub.SubscriptionId);
        Assert.Single(again.Subscriptions());
    }
}
