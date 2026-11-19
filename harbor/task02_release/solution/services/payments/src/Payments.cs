using System.Globalization;
using System.Text.Json;

namespace Seedco.Payments;

/// <summary>What the provider holds for one payment. Amounts are integers in the currency's smallest unit.</summary>
public record PaymentIntent(string Id, long Amount, string Currency, string Status, string PaymentMethod, string? FailureCode,
    string MerchantReference, string IdempotencyKey, long AmountRefunded, string CreatedAt);
public record ProviderRefund(string Id, string PaymentIntent, long Amount, string CreatedAt);

// The webhook payloads, as this app asked for them in graphql/*.graphql.
public record ActionPayload(decimal? Amount, string? Currency, string? ActionType);
public record TransactionPayload(string? Id, string? PspReference);
public record SourcePayload(string? Id, string? Number);
public record InitializePayload(ActionPayload? Action, JsonElement? Data, string? MerchantReference, string? IdempotencyKey,
    TransactionPayload? Transaction, SourcePayload? SourceObject);
public record RefundPayload(ActionPayload? Action, TransactionPayload? Transaction);

/// <summary>The answer to a transaction webhook, in Core's format: a decimal amount in major units and a result.</summary>
public record TransactionResponse(string PspReference, string Result, decimal Amount, string Message);

/// <summary>A webhook payload without what the app needs (400).</summary>
public class MalformedRequest(string message) : Exception(message);

/// <summary>
/// Money on the two sides of this app. Core sends a decimal in major units ("66.15" USD). The provider wants an
/// integer in the smallest unit of the currency (6615), and currencies do not all have two decimal places.
/// </summary>
public static class Currencies
{
    private static readonly Dictionary<string, int> Digits = new()
    {
        ["USD"] = 2, ["EUR"] = 2, ["GBP"] = 2, ["CAD"] = 2, ["JPY"] = 0, ["KRW"] = 0, ["KWD"] = 3,
    };

    public static int DigitsOf(string currency) =>
        Digits.TryGetValue(currency.ToUpperInvariant(), out var d) ? d : throw new MalformedRequest("unsupported currency " + currency);

    public static long ToProvider(decimal amount, string currency)
    {
        if (amount < 0) throw new MalformedRequest("amount must not be negative");
        return (long)Math.Round(amount * Pow10(DigitsOf(currency)), 0, MidpointRounding.AwayFromZero);
    }

    public static decimal FromProvider(long amount, string currency) => amount / Pow10(DigitsOf(currency));

    private static decimal Pow10(int digits) => (decimal)Math.Pow(10, digits);
}

/// <summary>Stands in for the payment provider. It behaves like a card processor's API: intents, refunds, test cards.</summary>
public class Provider(Store store)
{
    public const string DecliningCard = "pm_card_declined";   // the test card that always declines

    private static string NewId(string prefix) => prefix + "_" + Guid.NewGuid().ToString("N")[..16];
    private static string Now() => DateTime.UtcNow.ToString("o", CultureInfo.InvariantCulture);

    /// <summary>Charges a card. The same idempotency key returns the first intent instead of charging again.</summary>
    public PaymentIntent CreatePaymentIntent(long amount, string currency, string paymentMethod, string merchantReference, string idempotencyKey)
    {
        var earlier = store.List<PaymentIntent>("payment_intents", idempotencyKey).FirstOrDefault();
        if (earlier is not null) return earlier;
        if (amount <= 0) throw new MalformedRequest("amount must be positive");
        var declined = paymentMethod == DecliningCard;
        var intent = new PaymentIntent(NewId("pi"), amount, currency.ToLowerInvariant(), declined ? "requires_payment_method" : "succeeded",
            paymentMethod, declined ? "card_declined" : null, merchantReference, idempotencyKey, 0, Now());
        store.Put("payment_intents", intent.Id, idempotencyKey, intent);
        return intent;
    }

    public PaymentIntent? Intent(string id) => store.Get<PaymentIntent>("payment_intents", id);
    public IReadOnlyList<PaymentIntent> Intents() => store.List<PaymentIntent>("payment_intents");
    public IReadOnlyList<ProviderRefund> Refunds(string? intentId = null) => store.List<ProviderRefund>("refunds", intentId);

    /// <summary>Refunds part or all of a succeeded intent. Throws when there is not that much left to refund.</summary>
    public ProviderRefund Refund(string intentId, long amount)
    {
        var intent = Intent(intentId) ?? throw new InvalidOperationException("no such payment intent " + intentId);
        if (intent.Status != "succeeded") throw new InvalidOperationException("the payment did not succeed");
        if (amount <= 0 || amount > intent.Amount - intent.AmountRefunded) throw new InvalidOperationException("amount exceeds what can be refunded");
        var refund = new ProviderRefund(NewId("re"), intentId, amount, Now());
        store.Put("refunds", refund.Id, intentId, refund);
        store.Put("payment_intents", intent.Id, intent.IdempotencyKey, intent with { AmountRefunded = intent.AmountRefunded + amount });
        return refund;
    }
}

/// <summary>One page of a list (PAY-21): oldest first, 20 records unless asked otherwise, 100 at most.</summary>
public static class Paging
{
    public const int DefaultLimit = 20;
    public const int MaxLimit = 100;

    /// <summary>`startingAfter` is the id of the last record of the previous page. HasMore says whether another page follows.</summary>
    public static (List<T> Items, bool HasMore) Page<T>(IReadOnlyList<T> all, Func<T, string> id, int? limit, string? startingAfter)
    {
        var size = limit ?? DefaultLimit;
        if (size < 1 || size > MaxLimit) throw new MalformedRequest($"limit must be between 1 and {MaxLimit}");
        var start = 0;
        if (!string.IsNullOrEmpty(startingAfter))
        {
            var index = all.ToList().FindIndex(x => id(x) == startingAfter);
            if (index < 0) throw new MalformedRequest("starting_after is not the id of a record");
            start = index + 1;
        }
        return (all.Skip(start).Take(size).ToList(), start + size < all.Count);
    }
}

/// <summary>The app itself: turns Core's transaction webhooks into provider calls and the provider's answers into Core's.</summary>
public class PaymentsApp(Provider provider)
{
    private static T Need<T>(T? value, string name) where T : class => value ?? throw new MalformedRequest(name + " is missing from the payload");

    private static (decimal Amount, string Currency) Money(ActionPayload? action)
    {
        var a = Need(action, "action");
        return (a.Amount ?? throw new MalformedRequest("action.amount is missing from the payload"), Need(a.Currency, "action.currency"));
    }

    /// <summary>TRANSACTION_INITIALIZE_SESSION: charge the card named in `data.paymentMethod`.</summary>
    public TransactionResponse Initialize(InitializePayload payload)
    {
        var (amount, currency) = Money(payload.Action);
        var key = Need(payload.IdempotencyKey, "idempotencyKey");
        var reference = Need(payload.MerchantReference, "merchantReference");
        if (payload.Action!.ActionType != "CHARGE")
            return new TransactionResponse("", "CHARGE_FAILURE", amount, "only CHARGE is supported");
        var method = payload.Data is { ValueKind: JsonValueKind.Object } data && data.TryGetProperty("paymentMethod", out var m)
            && m.ValueKind == JsonValueKind.String ? m.GetString()! : null;
        if (string.IsNullOrEmpty(method))
            return new TransactionResponse("", "CHARGE_FAILURE", amount, "payment_method_missing");
        var intent = provider.CreatePaymentIntent(Currencies.ToProvider(amount, currency), currency, method, reference, key);
        var charged = Currencies.FromProvider(intent.Amount, intent.Currency);
        return intent.Status == "succeeded"
            ? new TransactionResponse(intent.Id, "CHARGE_SUCCESS", charged, "")
            : new TransactionResponse(intent.Id, "CHARGE_FAILURE", charged, intent.FailureCode ?? "payment_failed");
    }

    /// <summary>TRANSACTION_REFUND_REQUESTED: refund against the intent Core knows as the transaction's pspReference.</summary>
    public TransactionResponse Refund(RefundPayload payload)
    {
        var (amount, currency) = Money(payload.Action);
        var intentId = Need(Need(payload.Transaction, "transaction").PspReference, "transaction.pspReference");
        try
        {
            var refund = provider.Refund(intentId, Currencies.ToProvider(amount, currency));
            return new TransactionResponse(refund.Id, "REFUND_SUCCESS", Currencies.FromProvider(refund.Amount, currency), "");
        }
        catch (InvalidOperationException e)
        {
            return new TransactionResponse("", "REFUND_FAILURE", amount, e.Message);
        }
    }
}
