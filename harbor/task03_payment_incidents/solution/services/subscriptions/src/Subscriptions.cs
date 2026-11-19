using System.Globalization;
using System.Text.Json;

namespace Seedco.Subscriptions;

/// <summary>Money as Core writes it: a decimal amount in major units and a currency.</summary>
public record Money(decimal Amount, string Currency = "USD");
public record Plan(string Sku, string Name, Money UnitPrice);
public record Address(string FirstName, string LastName, string StreetAddress1, string City, string PostalCode, string Country, string CountryArea);
public record Subscription(string SubscriptionId, string OrderId, string Email, Address ShippingAddress, string Sku, string Name, int Qty,
    Money UnitPrice, string Status, string CurrentPeriodStart, string CurrentPeriodEnd, string PaymentMethod,
    string? PendingSku = null, string? PendingName = null, bool CancelAtPeriodEnd = false, int FailedAttempts = 0, string? NextAttempt = null);
public record ChangePlanRequest(string? Sku, string? AsOf = null);
public record RenewalRequest(string? AsOf = null);
public record PaymentMethodRequest(string? Email, string? PaymentMethod);
public record RenewalRun(string AsOf, int Renewed, int Failed, int Ended);

/// <summary>What billing an order through Core came to.</summary>
public record Billed(string OrderId, bool Paid, decimal Total, string FailureReason);

/// <summary>Core and the payments app, as this app uses them.</summary>
public interface ICommerce
{
    /// <summary>The card a paid order was charged to, read from the payments app by the transaction's pspReference.</summary>
    string PaymentMethodOf(string pspReference);

    /// <summary>
    /// Creates an order in Core for one line at a net unit price, marks it as ours, and charges the card. Core adds
    /// the tax. If the charge fails the order is cancelled. The key makes a repeat of the same bill charge once.
    /// </summary>
    Billed Bill(Subscription s, string sku, int qty, decimal unitPrice, string reason, string idempotencyKey);

    /// <summary>Puts a note on an order in Core, for the people who pack it.</summary>
    void Annotate(string orderId, string key, string? value);
}

/// <summary>The email app, as this app uses it.</summary>
public interface INotifier
{
    void Notify(string notifyEvent, object payload);
}

/// <summary>A request we refuse (400).</summary>
public class BadRequest(string message) : Exception(message);
/// <summary>The request is fine but the customer's payment did not go through (402).</summary>
public class PaymentDeclined(string message) : Exception(message);
public class NotFound(string message) : Exception(message);

/// <summary>
/// Monthly subscriptions on top of Core. Core has no subscriptions: a subscription starts when an order with a plan
/// on it is paid, and every renewal or plan change is a new order this app creates in Core and charges.
/// </summary>
public class SubscriptionsApp(Store store, ICommerce commerce, INotifier notifier)
{
    public const string DefaultPaymentMethod = "pm_card_ok";
    public const int MaxRenewalAttempts = 3;     // dunning: a renewal is tried this many times,
    public const int RetryDelayDays = 3;         // this many days apart, then the subscription is terminated
    public const string MetadataKey = "subscription_id";   // on every order this app creates, so it is not taken for a new sale

    /// <summary>Plans that renew monthly. The price is net, per unit and per month; Core adds tax when it is charged.</summary>
    public static readonly IReadOnlyDictionary<string, Plan> Plans = new Dictionary<string, Plan>
    {
        ["BOX-S"] = new("BOX-S", "Small monthly box", new Money(24.99m)),
        ["BOX-L"] = new("BOX-L", "Large monthly box", new Money(39.50m)),
    };

    private readonly object _lock = new();

    public static decimal Round(decimal amount) => Math.Round(amount, 2, MidpointRounding.AwayFromZero);

    /// <summary>The share of a period's price for <paramref name="days"/> of its <paramref name="periodDays"/> days.</summary>
    public static decimal Prorate(decimal amount, int days, int periodDays) => Round(amount * days / periodDays);

    public static DateOnly Day(string? value) => string.IsNullOrEmpty(value)
        ? DateOnly.FromDateTime(DateTime.UtcNow)
        : DateOnly.TryParseExact(value.Length >= 10 ? value[..10] : value, "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out var d)
            ? d : throw new BadRequest("dates are YYYY-MM-DD");

    private static string Text(DateOnly d) => d.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture);

    public IReadOnlyList<Subscription> Subscriptions(string? email = null) => store.List<Subscription>("subscriptions", email);
    private Subscription Sub(string id) => store.Get<Subscription>("subscriptions", id) ?? throw new NotFound("no subscription " + id);
    private void Save(Subscription s) => store.Put("subscriptions", s.SubscriptionId, s.Email, s);

    private void Tell(string notifyEvent, Subscription s, string about, decimal? amount = null, string? reason = null) =>
        notifier.Notify(notifyEvent, new
        {
            notification_id = $"{s.SubscriptionId}:{about}",
            recipient_email = s.Email,
            plan_name = s.Name,
            pending_plan_name = s.PendingName ?? "",
            period_end = s.CurrentPeriodEnd,
            amount = new { amount = amount ?? 0m, currency = "USD" },
            reason = reason ?? "",
        });

    /// <summary>One order event from Core. Returns the subscriptions it started. Safe to repeat.</summary>
    public IReadOnlyList<Subscription> Handle(JsonElement payload)
    {
        var type = payload.GetProperty("__typename").GetString();
        var order = payload.GetProperty("order");
        var orderId = order.GetProperty("id").GetString()!;
        lock (_lock)
        {
            if (type == "OrderCancelled")
            {
                foreach (var s in Subscriptions().Where(s => s.OrderId == orderId && s.Status is "active" or "past_due"))
                    Save(s with { Status = "canceled", PendingSku = null, PendingName = null });
                return [];
            }
            if (type != "OrderFullyPaid") return [];
            // An order this app created (a renewal or a plan change) carries our metadata: it is not a new sale.
            if (order.GetProperty("metadata").EnumerateArray().Any(m => m.GetProperty("key").GetString() == MetadataKey)) return [];
            var started = new List<Subscription>();
            var a = order.GetProperty("shippingAddress");
            string Field(string name) => a.GetProperty(name).GetString() ?? "";
            var address = new Address(Field("firstName"), Field("lastName"), Field("streetAddress1"), Field("city"), Field("postalCode"),
                a.GetProperty("country").GetProperty("code").GetString()!, Field("countryArea"));
            var start = Day(payload.TryGetProperty("issuedAt", out var at) ? at.GetString() : null);
            string? method = null;
            foreach (var line in order.GetProperty("lines").EnumerateArray())
            {
                var sku = line.GetProperty("productSku").GetString() ?? "";
                if (!Plans.TryGetValue(sku, out var plan)) continue;
                var id = $"sub_{(uint)(orderId + "|" + sku).GetDeterministicHash():x8}";   // the same order and plan always give the same id
                if (store.Get<Subscription>("subscriptions", id) is not null) continue;   // this order was handled before
                method ??= commerce.PaymentMethodOf(order.GetProperty("transactions")[0].GetProperty("pspReference").GetString()!);
                var s = new Subscription(id, orderId, order.GetProperty("userEmail").GetString()!, address, sku, plan.Name,
                    line.GetProperty("quantity").GetInt32(), plan.UnitPrice, "active", Text(start), Text(start.AddMonths(1)), method);
                Save(s);
                started.Add(s);
            }
            return started;
        }
    }

    /// <summary>
    /// Changes a subscription's plan. A more expensive plan starts now: the customer pays the remaining days of the
    /// new plan less the unused days of the old one. A cheaper plan starts at the end of the paid period.
    /// </summary>
    public Subscription ChangePlan(string subscriptionId, ChangePlanRequest req)
    {
        lock (_lock)
        {
            var s = Sub(subscriptionId);
            if (s.Status != "active") throw new BadRequest("only an active subscription can change plan");
            if (!Plans.TryGetValue(req.Sku ?? "", out var plan)) throw new BadRequest("unknown plan " + req.Sku);
            if (plan.Sku == s.Sku)
            {
                s = s with { PendingSku = null, PendingName = null };   // back to the current plan: drop a scheduled change
                Save(s);
                return s;
            }
            if (plan.UnitPrice.Amount < s.UnitPrice.Amount)
            {
                s = s with { PendingSku = plan.Sku, PendingName = plan.Name };
                Save(s);
                Tell("SUBSCRIPTION_DOWNGRADE_SCHEDULED", s, "downgrade:" + s.CurrentPeriodEnd + ":" + plan.Sku);
                return s;
            }
            DateOnly today = Day(req.AsOf), start = Day(s.CurrentPeriodStart), end = Day(s.CurrentPeriodEnd);
            if (today < start || today >= end) throw new BadRequest("as_of must be inside the current period");
            int periodDays = end.DayNumber - start.DayNumber, left = end.DayNumber - today.DayNumber;
            var due = Prorate(plan.UnitPrice.Amount * s.Qty, left, periodDays) - Prorate(s.UnitPrice.Amount * s.Qty, left, periodDays);
            var billed = commerce.Bill(s, plan.Sku, 1, due, "plan_change", $"{s.SubscriptionId}:plan:{plan.Sku}:{Text(today)}");
            if (!billed.Paid) throw new PaymentDeclined("the plan was not changed: " + billed.FailureReason);
            s = s with { Sku = plan.Sku, Name = plan.Name, UnitPrice = plan.UnitPrice, PendingSku = null, PendingName = null };
            Save(s);
            Tell("SUBSCRIPTION_PLAN_CHANGED", s, "plan:" + plan.Sku + ":" + Text(today));
            return s;
        }
    }

    /// <summary>Ends a subscription at the end of the period already paid for.</summary>
    public Subscription Cancel(string subscriptionId)
    {
        lock (_lock)
        {
            var s = Sub(subscriptionId);
            if (s.Status is "canceled" or "terminated" || s.CancelAtPeriodEnd) return s;
            s = s with { CancelAtPeriodEnd = true, PendingSku = null, PendingName = null };
            Save(s);
            Tell("SUBSCRIPTION_CANCEL_SCHEDULED", s, "cancel:" + s.CurrentPeriodEnd);
            return s;
        }
    }

    /// <summary>Replaces the payment method on every subscription the customer has.</summary>
    public IReadOnlyList<Subscription> SetPaymentMethod(PaymentMethodRequest req)
    {
        if (string.IsNullOrWhiteSpace(req.Email) || string.IsNullOrWhiteSpace(req.PaymentMethod)) throw new BadRequest("email and payment_method are required");
        lock (_lock)
        {
            foreach (var s in Subscriptions(req.Email)) Save(s with { PaymentMethod = req.PaymentMethod });
            return Subscriptions(req.Email);
        }
    }

    /// <summary>
    /// Renews every subscription whose paid period has ended by <paramref name="asOf"/>, and retries the ones whose
    /// last attempt failed. A scheduled plan change or cancellation takes effect here, at the period boundary.
    /// </summary>
    public RenewalRun RunRenewals(string? asOf)
    {
        var today = Day(asOf);
        int renewed = 0, failed = 0, ended = 0;
        lock (_lock)
        {
            foreach (var current in Subscriptions())
            {
                var s = current;
                var due = s.Status == "active" ? Day(s.CurrentPeriodEnd) <= today
                    : s.Status == "past_due" && Day(s.NextAttempt) <= today;
                if (!due) continue;
                if (s.CancelAtPeriodEnd)
                {
                    Save(s with { Status = "canceled" });
                    ended++;
                    continue;
                }
                if (s.PendingSku is not null)
                    s = s with { Sku = s.PendingSku, Name = Plans[s.PendingSku].Name, UnitPrice = Plans[s.PendingSku].UnitPrice, PendingSku = null, PendingName = null };
                var attempt = s.FailedAttempts + 1;
                var billed = commerce.Bill(s, s.Sku, s.Qty, s.UnitPrice.Amount, "renewal", $"{s.SubscriptionId}:renewal:{s.CurrentPeriodEnd}:{attempt}");
                if (billed.Paid)
                {
                    // The charge is taken: the new period is saved before anything else is done, so that nothing
                    // that goes wrong afterwards can leave a paid subscription due again.
                    var start = Day(s.CurrentPeriodEnd);
                    Save(s with { Status = "active", CurrentPeriodStart = Text(start), CurrentPeriodEnd = Text(start.AddMonths(1)), FailedAttempts = 0, NextAttempt = null });
                    if (current.PendingSku is not null)     // the box changes with this order: tell the warehouse which one to pack
                        commerce.Annotate(billed.OrderId, "subscription_plan_change", s.Name);
                    renewed++;
                    continue;
                }
                Tell("SUBSCRIPTION_PAYMENT_FAILED", s, $"failed:{s.CurrentPeriodEnd}:{attempt}", billed.Total, billed.FailureReason);
                if (attempt >= MaxRenewalAttempts)
                {
                    s = s with { Status = "terminated", FailedAttempts = attempt, NextAttempt = null };
                    Save(s);
                    Tell("SUBSCRIPTION_TERMINATED", s, "terminated:" + s.CurrentPeriodEnd);
                    ended++;
                }
                else
                {
                    Save(s with { Status = "past_due", FailedAttempts = attempt, NextAttempt = Text(today.AddDays(RetryDelayDays)) });
                    failed++;
                }
            }
        }
        return new RenewalRun(Text(today), renewed, failed, ended);
    }
}

public static class Hashing
{
    /// <summary>A hash that is the same in every process, unlike string.GetHashCode.</summary>
    public static int GetDeterministicHash(this string text)
    {
        unchecked
        {
            var hash = 23;
            foreach (var c in text) hash = hash * 31 + c;
            return hash;
        }
    }
}
