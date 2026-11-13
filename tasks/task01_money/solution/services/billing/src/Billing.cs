using System.Globalization;
using System.Text.Json;

namespace Seedco.Billing;

/// <summary>Money on every contract: integer minor units (cents) with a currency. Only USD exists today.</summary>
public record Money(string Currency, long Minor)
{
    public static Money Usd(long minor) => new("USD", minor);
}

public record QuoteLine(string Sku, int Qty, Money UnitPrice);
public record QuoteRequest(int PostalCode, List<QuoteLine> Lines);
public record Quote(Money Subtotal, Money Tax, Money Total);
public record ChargeRequest(string OrderId, string CustomerId, Money Amount, string? Email = null, string? PaymentMethod = null);
public record Payment(string PaymentId, string OrderId, string CustomerId, Money Amount, string Status,
    string? Email = null, string? PaymentMethod = null, string? FailureReason = null, string? SubscriptionId = null);
public record Refund(string RefundId, string PaymentId, string OrderId, string CustomerId, Money Amount, string CreatedAt);
/// <summary>Line types follow the invoice: RECURRING (a plan period), FIXED (one-off), PRORATION and CREDIT (plan changes).</summary>
public record InvoiceLine(string Type, string Sku, string Name, int Qty, Money UnitPrice, Money Amount);
public record Invoice(string InvoiceId, string OrderId, string? SubscriptionId, string CustomerId, string Email, string Reason,
    List<InvoiceLine> Lines, Money Subtotal, Money Tax, Money Total, string Status, string IssuedAt);
public record Plan(string Sku, string Name, Money UnitPrice);
public record Subscription(string SubscriptionId, string OrderId, string CustomerId, string Email, int PostalCode,
    string Sku, string Name, int Qty, Money UnitPrice, string Status, string CurrentPeriodStart, string CurrentPeriodEnd,
    string PaymentMethod, string? PendingSku = null, string? PendingName = null, bool CancelAtPeriodEnd = false,
    int FailedAttempts = 0, string? NextAttempt = null);
public record ChangePlanRequest(string Sku, string? AsOf = null);
public record RenewalRequest(string? AsOf = null);
public record PaymentMethodRequest(string PaymentMethod);
public record RenewalRun(string AsOf, int Renewed, int Failed, int Ended);

public interface IEventPublisher
{
    void Publish(string topic, object envelope);
}

/// <summary>A request Billing refuses (400).</summary>
public class BillingException(string message) : Exception(message);
/// <summary>The request is fine but the customer's payment did not go through (402).</summary>
public class PaymentDeclined(string message) : Exception(message);
/// <summary>An Idempotency-Key reused with different parameters (409).</summary>
public class IdempotencyConflict(string message) : Exception(message);
public class NotFound(string message) : Exception(message);

/// <summary>Prices, tax, payments, invoices and subscriptions. Money is integer cents; tax and proration round half up to the cent.</summary>
public class BillingService(IEventPublisher publisher, Store? store = null)
{
    public const string Topic = "billing";
    public const string OrdersTopic = "orders";
    public const string DefaultPaymentMethod = "pm_card_ok";
    public const string DecliningPaymentMethod = "pm_card_declined";   // the test card that always declines
    public const int MaxRenewalAttempts = 3;     // dunning: a renewal is tried this many times,
    public const int RetryDelayDays = 3;         // this many days apart, then the subscription is terminated

    /// <summary>Plans that renew monthly. The price here is what a renewal charges.</summary>
    public static readonly IReadOnlyDictionary<string, Plan> Plans = new Dictionary<string, Plan>
    {
        ["BOX-S"] = new("BOX-S", "Small monthly box", Money.Usd(2499)),
        ["BOX-L"] = new("BOX-L", "Large monthly box", Money.Usd(3950)),
    };

    private readonly Store _store = store ?? new Store();
    private readonly object _lock = new();

    public Store Store => _store;

    /// <summary>Sales tax by the first digit of the postal code, in basis points.</summary>
    public static long TaxRateBasisPoints(int postalCode)
    {
        var first = postalCode.ToString()[0];
        return first == '9' ? 875 : 600;
    }

    /// <summary>Tax in cents on a subtotal in cents, rounded half up.</summary>
    public static long Tax(long subtotalMinor, int postalCode) => (subtotalMinor * TaxRateBasisPoints(postalCode) + 5000) / 10000;

    /// <summary>The share of a period's price, in cents, for <paramref name="days"/> of its <paramref name="periodDays"/> days, rounded half up.</summary>
    public static long Prorate(long amountMinor, int days, int periodDays) => (2 * amountMinor * days + periodDays) / (2 * periodDays);

    private static long Minor(Money? m)
    {
        if (m is null || m.Currency != "USD") throw new BillingException("money must be {currency: \"USD\", minor}");
        return m.Minor;
    }

    private static Money ReadMoney(JsonElement e) =>
        Money.Usd(e.GetProperty("currency").GetString() == "USD" ? e.GetProperty("minor").GetInt64() : throw new BillingException("unsupported currency"));

    public static DateOnly Day(string? value) => string.IsNullOrEmpty(value)
        ? DateOnly.FromDateTime(DateTime.UtcNow)
        : DateOnly.TryParseExact(value.Length >= 10 ? value[..10] : value, "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out var d)
            ? d : throw new BillingException("dates are YYYY-MM-DD");

    private static string Text(DateOnly d) => d.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture);
    private static string Now() => DateTime.UtcNow.ToString("o");
    private static string NewId(string prefix) => prefix + "_" + Guid.NewGuid().ToString("N")[..8];

    public Quote Quote(QuoteRequest req)
    {
        if (req.Lines is null || req.Lines.Count == 0) throw new BillingException("lines must not be empty");
        if (req.PostalCode <= 0) throw new BillingException("postal_code must be positive");
        long subtotal = 0;
        foreach (var l in req.Lines)
        {
            if (l.Qty < 1 || Minor(l.UnitPrice) < 0) throw new BillingException("invalid line");
            subtotal += l.UnitPrice.Minor * l.Qty;
        }
        var tax = Tax(subtotal, req.PostalCode);
        return new Quote(Money.Usd(subtotal), Money.Usd(tax), Money.Usd(subtotal + tax));
    }

    /// <summary>
    /// Takes a payment. With an idempotency key, a repeat of the same request returns the first payment instead of
    /// charging again, and the same key with different parameters is refused.
    /// </summary>
    public Payment Charge(ChargeRequest req, string? idempotencyKey = null, string? subscriptionId = null)
    {
        if (Minor(req.Amount) <= 0) throw new BillingException("amount must be positive");
        lock (_lock)
        {
            var fingerprint = $"{req.OrderId}|{req.CustomerId}|{req.Amount.Minor}";
            if (idempotencyKey is not null && _store.Idempotent(idempotencyKey) is { } earlier)
            {
                if (earlier.Fingerprint != fingerprint) throw new IdempotencyConflict("this Idempotency-Key was used for a different charge");
                return _store.Get<Payment>("payments", earlier.PaymentId)!;
            }
            var method = string.IsNullOrEmpty(req.PaymentMethod) ? DefaultPaymentMethod : req.PaymentMethod;
            var declined = method == DecliningPaymentMethod;
            var p = new Payment(NewId("pay"), req.OrderId, req.CustomerId, req.Amount, declined ? "failed" : "succeeded",
                req.Email, method, declined ? "card_declined" : null, subscriptionId);
            _store.Put("payments", p.PaymentId, p.OrderId, p.CustomerId, p);
            if (idempotencyKey is not null) _store.RememberIdempotent(idempotencyKey, fingerprint, p.PaymentId);
            if (declined) Emit("payment.failed", new { payment = p });
            return p;
        }
    }

    public IReadOnlyList<Payment> Payments(string? orderId) => _store.List<Payment>("payments", orderId);
    public IReadOnlyList<Refund> Refunds(string? orderId) => _store.List<Refund>("refunds", orderId);
    public IReadOnlyList<Invoice> Invoices(string? orderId, string? customerId = null) => _store.List<Invoice>("invoices", orderId, customerId);
    public IReadOnlyList<Subscription> Subscriptions(string? customerId, string? orderId = null) => _store.List<Subscription>("subscriptions", orderId, customerId);

    private Subscription Sub(string id) => _store.Get<Subscription>("subscriptions", id) ?? throw new NotFound("no subscription " + id);
    private void Save(Subscription s) => _store.Put("subscriptions", s.SubscriptionId, s.OrderId, s.CustomerId, s);

    private void Emit(string type, object data) => publisher.Publish(Topic, new
    {
        event_id = "evt_" + Guid.NewGuid(),
        event_type = type,
        occurred_at = Now(),
        data,
    });

    private Invoice Issue(string orderId, string? subscriptionId, string customerId, string email, string reason,
        List<InvoiceLine> lines, long subtotal, long tax, long total)
    {
        var invoice = new Invoice(NewId("inv"), orderId, subscriptionId, customerId, email, reason, lines, Money.Usd(subtotal), Money.Usd(tax), Money.Usd(total), "paid", Now());
        _store.Put("invoices", invoice.InvoiceId, orderId, customerId, invoice);
        Emit("invoice.paid", new { invoice });
        return invoice;
    }

    /// <summary>Handles one event from the orders topic. Returns the invoice it issued, if any.</summary>
    public Invoice? Handle(JsonElement envelope)
    {
        var id = envelope.GetProperty("event_id").GetString()!;
        var type = envelope.GetProperty("event_type").GetString();
        if (type != "order.placed" && type != "order.cancelled") return null;
        lock (_lock)
        {
            if (!_store.FirstSight(id)) return null;
            var order = envelope.GetProperty("data").GetProperty("order");
            if (type == "order.cancelled")
            {
                Cancelled(order.GetProperty("order_id").GetString()!);
                return null;
            }
            return Placed(order, envelope.GetProperty("occurred_at").GetString());
        }
    }

    /// <summary>A paid order: issue its invoice, and start a subscription for each plan on it.</summary>
    private Invoice Placed(JsonElement order, string? occurredAt)
    {
        var orderId = order.GetProperty("order_id").GetString()!;
        var customerId = order.GetProperty("customer_id").GetString()!;
        var email = order.GetProperty("email").GetString()!;
        var method = order.TryGetProperty("payment_method", out var m) && m.ValueKind == JsonValueKind.String ? m.GetString()! : DefaultPaymentMethod;
        var start = Day(occurredAt);
        var lines = new List<InvoiceLine>();
        foreach (var l in order.GetProperty("lines").EnumerateArray())
        {
            var sku = l.GetProperty("sku").GetString()!;
            var qty = l.GetProperty("qty").GetInt32();
            var unit = ReadMoney(l.GetProperty("unit_price"));
            var plan = Plans.ContainsKey(sku);
            lines.Add(new InvoiceLine(plan ? "RECURRING" : "FIXED", sku, l.GetProperty("name").GetString()!, qty, unit, Money.Usd(unit.Minor * qty)));
            if (plan)
                Save(new Subscription(NewId("sub"), orderId, customerId, email, order.GetProperty("postal_code").GetInt32(), sku,
                    Plans[sku].Name, qty, Plans[sku].UnitPrice, "active", Text(start), Text(start.AddMonths(1)), method));
        }
        return Issue(orderId, null, customerId, email, "order", lines, ReadMoney(order.GetProperty("subtotal")).Minor,
            ReadMoney(order.GetProperty("tax")).Minor, ReadMoney(order.GetProperty("total")).Minor);
    }

    /// <summary>A cancelled order: refund what was paid for it, mark its invoice refunded and end its subscriptions.</summary>
    private void Cancelled(string orderId)
    {
        foreach (var p in _store.List<Payment>("payments", orderId).Where(p => p.Status == "succeeded" && p.SubscriptionId is null))
        {
            var r = new Refund(NewId("ref"), p.PaymentId, orderId, p.CustomerId, p.Amount, Now());
            _store.Put("refunds", r.RefundId, orderId, r.CustomerId, r);
            _store.Put("payments", p.PaymentId, orderId, p.CustomerId, p with { Status = "refunded" });
        }
        foreach (var i in _store.List<Invoice>("invoices", orderId).Where(i => i.Reason == "order"))
            _store.Put("invoices", i.InvoiceId, orderId, i.CustomerId, i with { Status = "refunded" });
        foreach (var s in Subscriptions(null, orderId).Where(s => s.Status is "active" or "past_due"))
            Save(s with { Status = "canceled", PendingSku = null, PendingName = null });
    }

    /// <summary>
    /// Changes a subscription's plan. A more expensive plan starts now: the unused days of the old plan are credited
    /// and the remaining days of the new one are charged. A cheaper plan starts at the end of the paid period.
    /// </summary>
    public Subscription ChangePlan(string subscriptionId, ChangePlanRequest req)
    {
        lock (_lock)
        {
            var s = Sub(subscriptionId);
            if (s.Status != "active") throw new BillingException("only an active subscription can change plan");
            if (!Plans.TryGetValue(req.Sku ?? "", out var plan)) throw new BillingException("unknown plan " + req.Sku);
            if (plan.Sku == s.Sku)
            {
                s = s with { PendingSku = null, PendingName = null };   // back to the current plan: drop a scheduled change
                Save(s);
                return s;
            }
            if (plan.UnitPrice.Minor < s.UnitPrice.Minor)
            {
                s = s with { PendingSku = plan.Sku, PendingName = plan.Name };
                Save(s);
                Emit("subscription.updated", new { subscription = s, change = "downgrade_scheduled" });
                return s;
            }
            DateOnly today = Day(req.AsOf), start = Day(s.CurrentPeriodStart), end = Day(s.CurrentPeriodEnd);
            if (today < start || today >= end) throw new BillingException("as_of must be inside the current period");
            int periodDays = end.DayNumber - start.DayNumber, left = end.DayNumber - today.DayNumber;
            var credit = -Prorate(s.UnitPrice.Minor * s.Qty, left, periodDays);
            var charge = Prorate(plan.UnitPrice.Minor * s.Qty, left, periodDays);
            var lines = new List<InvoiceLine>
            {
                new("CREDIT", s.Sku, "Unused time on " + s.Name, s.Qty, s.UnitPrice, Money.Usd(credit)),
                new("PRORATION", plan.Sku, "Remaining time on " + plan.Name, s.Qty, plan.UnitPrice, Money.Usd(charge)),
            };
            var subtotal = credit + charge;
            var tax = Tax(subtotal, s.PostalCode);
            var payment = Charge(new ChargeRequest(s.OrderId, s.CustomerId, Money.Usd(subtotal + tax), s.Email, s.PaymentMethod), null, s.SubscriptionId);
            if (payment.Status != "succeeded") throw new PaymentDeclined("the plan was not changed: " + payment.FailureReason);
            s = s with { Sku = plan.Sku, Name = plan.Name, UnitPrice = plan.UnitPrice, PendingSku = null, PendingName = null };
            Save(s);
            Issue(s.OrderId, s.SubscriptionId, s.CustomerId, s.Email, "plan_change", lines, subtotal, tax, subtotal + tax);
            Emit("subscription.updated", new { subscription = s, change = "plan_changed" });
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
            Emit("subscription.updated", new { subscription = s, change = "cancel_scheduled" });
            return s;
        }
    }

    /// <summary>Replaces the payment method on every subscription the customer has.</summary>
    public IReadOnlyList<Subscription> SetPaymentMethod(string customerId, string paymentMethod)
    {
        if (string.IsNullOrWhiteSpace(paymentMethod)) throw new BillingException("payment_method is required");
        lock (_lock)
        {
            foreach (var s in Subscriptions(customerId)) Save(s with { PaymentMethod = paymentMethod });
            return Subscriptions(customerId);
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
            foreach (var current in Subscriptions(null))
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
                var subtotal = s.UnitPrice.Minor * s.Qty;
                var tax = Tax(subtotal, s.PostalCode);
                var payment = Charge(new ChargeRequest(s.OrderId, s.CustomerId, Money.Usd(subtotal + tax), s.Email, s.PaymentMethod), null, s.SubscriptionId);
                if (payment.Status == "succeeded")
                {
                    var start = Day(s.CurrentPeriodEnd);
                    s = s with { Status = "active", CurrentPeriodStart = Text(start), CurrentPeriodEnd = Text(start.AddMonths(1)), FailedAttempts = 0, NextAttempt = null };
                    Save(s);
                    Issue(s.OrderId, s.SubscriptionId, s.CustomerId, s.Email, "renewal",
                        [new InvoiceLine("RECURRING", s.Sku, s.Name, s.Qty, s.UnitPrice, Money.Usd(subtotal))], subtotal, tax, subtotal + tax);
                    Emit("subscription.updated", new { subscription = s, change = "renewed" });
                    renewed++;
                }
                else if (s.FailedAttempts + 1 >= MaxRenewalAttempts)
                {
                    s = s with { Status = "terminated", FailedAttempts = s.FailedAttempts + 1, NextAttempt = null };
                    Save(s);
                    Emit("subscription.updated", new { subscription = s, change = "terminated" });
                    ended++;
                }
                else
                {
                    Save(s with { Status = "past_due", FailedAttempts = s.FailedAttempts + 1, NextAttempt = Text(today.AddDays(RetryDelayDays)) });
                    failed++;
                }
            }
        }
        return new RenewalRun(Text(today), renewed, failed, ended);
    }
}
