using System.Text.Json;
using Seedco.Payments;
using Xunit;

public class PaymentsTests
{
    private static (PaymentsApp app, Provider provider, Store store) New(string? path = null)
    {
        var store = new Store(path, "payment_intents", "refunds", "refund_requests");
        var provider = new Provider(store);
        return (new PaymentsApp(provider), provider, store);
    }

    private static InitializePayload Charge(decimal amount, string method = "pm_card_ok", string key = "key-1", string currency = "USD") =>
        new(new ActionPayload(amount, currency, "CHARGE"), JsonDocument.Parse($$"""{"paymentMethod":"{{method}}"}""").RootElement,
            "Q2hlY2tvdXQ6MQ==", key, new TransactionPayload("VHJhbnNhY3Rpb246MQ==", null), new SourcePayload("Q2hlY2tvdXQ6MQ==", null));

    [Fact]
    public void MoneyIsConvertedToTheCurrencysSmallestUnitAndBack()
    {
        Assert.Equal(6615, Currencies.ToProvider(66.15m, "USD"));
        Assert.Equal(66.15m, Currencies.FromProvider(6615, "usd"));
        Assert.Equal(500, Currencies.ToProvider(500m, "JPY"));          // yen has no decimal places
        Assert.Equal(1234, Currencies.ToProvider(1.234m, "KWD"));       // dinar has three
        Assert.Equal(1, Currencies.ToProvider(0.005m, "USD"));          // half a cent rounds up
        Assert.Throws<MalformedRequest>(() => Currencies.ToProvider(1m, "XXX"));
    }

    [Fact]
    public void AChargeCreatesOneIntentInMinorUnitsAndAnswersInMajorUnits()
    {
        var (app, provider, _) = New();
        var answer = app.Initialize(Charge(66.15m));
        Assert.Equal(("CHARGE_SUCCESS", 66.15m), (answer.Result, answer.Amount));
        var intent = provider.Intents().Single();
        Assert.Equal((answer.PspReference, 6615L, "usd", "succeeded"), (intent.Id, intent.Amount, intent.Currency, intent.Status));
        Assert.Equal(answer.PspReference, app.Initialize(Charge(66.15m)).PspReference);      // the same key charges once
        Assert.Single(provider.Intents());
    }

    [Fact]
    public void ADeclinedCardIsAChargeFailureWithTheProvidersReason()
    {
        var (app, _, _) = New();
        var answer = app.Initialize(Charge(66.15m, Provider.DecliningCard));
        Assert.Equal(("CHARGE_FAILURE", "card_declined"), (answer.Result, answer.Message));
        Assert.StartsWith("pi_", answer.PspReference);
    }

    [Fact]
    public void AMalformedPayloadIsRefusedAndAMissingCardIsAFailure()
    {
        var (app, _, _) = New();
        Assert.Throws<MalformedRequest>(() => app.Initialize(Charge(66.15m) with { Action = null }));
        Assert.Throws<MalformedRequest>(() => app.Initialize(Charge(66.15m) with { Action = new ActionPayload(null, "USD", "CHARGE") }));
        Assert.Throws<MalformedRequest>(() => app.Initialize(Charge(66.15m) with { IdempotencyKey = null }));
        Assert.Equal("payment_method_missing", app.Initialize(Charge(66.15m) with { Data = null }).Message);
        Assert.Equal("CHARGE_FAILURE", app.Initialize(Charge(66.15m) with { Action = new ActionPayload(66.15m, "USD", "AUTHORIZATION") }).Result);
    }

    [Fact]
    public void RefundsAreTakenFromTheIntentUntilNothingIsLeft()
    {
        var (app, provider, _) = New();
        var paid = app.Initialize(Charge(66.15m));
        RefundPayload Refund(decimal amount) => new(new ActionPayload(amount, "USD", "REFUND"), new TransactionPayload("VHJhbnNhY3Rpb246MQ==", paid.PspReference), Guid.NewGuid().ToString());
        var first = app.Refund(Refund(16.15m));
        Assert.Equal(("REFUND_SUCCESS", 16.15m), (first.Result, first.Amount));
        Assert.Equal("REFUND_SUCCESS", app.Refund(Refund(50m)).Result);
        Assert.Equal(("REFUND_FAILURE", "amount exceeds what can be refunded"), (app.Refund(Refund(0.01m)).Result, app.Refund(Refund(0.01m)).Message));
        Assert.Equal(6615, provider.Intent(paid.PspReference)!.AmountRefunded);
        Assert.Equal(new long[] { 1615, 5000 }, provider.Refunds(paid.PspReference).Select(r => r.Amount));
        Assert.Throws<MalformedRequest>(() => app.Refund(new RefundPayload(new ActionPayload(1m, "USD", "REFUND"), new TransactionPayload("x", null), "k")));
    }

    [Fact]
    public void IntentsSurviveARestart()
    {
        var path = Path.Combine(Path.GetTempPath(), $"seedco-payments-{Guid.NewGuid():N}.db");
        string reference;
        var (app, _, store) = New(path);
        using (store) reference = app.Initialize(Charge(66.15m)).PspReference;
        var (again, provider, reopened) = New(path);
        using (reopened)
        {
            Assert.Equal(reference, again.Initialize(Charge(66.15m)).PspReference);
            Assert.Single(provider.Intents());
        }
    }
}
