using System.Collections.Concurrent;
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
public record ChargeRequest(string OrderId, string CustomerId, Money Amount);
public record Payment(string PaymentId, string OrderId, string CustomerId, Money Amount, string Status);
public record InvoiceLine(string Sku, string Name, int Qty, Money UnitPrice, Money Amount);
public record Invoice(string InvoiceId, string OrderId, string CustomerId, string Email, List<InvoiceLine> Lines,
    Money Subtotal, Money Tax, Money Total, string Status, string IssuedAt);

public interface IEventPublisher
{
    void Publish(string topic, object envelope);
}

public class BillingException(string message) : Exception(message);

/// <summary>Prices, tax, payments and invoices. Money is integer cents; tax rounds half up to the cent.</summary>
public class BillingService(IEventPublisher publisher)
{
    public const string Topic = "billing";
    public const string OrdersTopic = "orders";

    private readonly ConcurrentDictionary<string, Payment> _payments = new();
    private readonly ConcurrentDictionary<string, Invoice> _invoices = new();
    private readonly ConcurrentDictionary<string, bool> _seenEvents = new();

    /// <summary>Sales tax by the first digit of the postal code.</summary>
    public static long TaxRateBasisPoints(int postalCode)
    {
        var first = postalCode.ToString()[0];
        return first == '9' ? 875 : 600;
    }

    /// <summary>Tax in cents on a subtotal in cents, rounded half up.</summary>
    public static long Tax(long subtotalMinor, int postalCode) => (subtotalMinor * TaxRateBasisPoints(postalCode) + 5000) / 10000;

    private static long Minor(Money? m)
    {
        if (m is null || m.Currency != "USD") throw new BillingException("money must be {currency: \"USD\", minor}");
        return m.Minor;
    }

    private static Money ReadMoney(JsonElement e) =>
        Money.Usd(e.GetProperty("currency").GetString() == "USD" ? e.GetProperty("minor").GetInt64() : throw new BillingException("unsupported currency"));

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

    public Payment Charge(ChargeRequest req)
    {
        if (Minor(req.Amount) <= 0) throw new BillingException("amount must be positive");
        var p = new Payment("pay_" + Guid.NewGuid().ToString("N")[..8], req.OrderId, req.CustomerId, req.Amount, "succeeded");
        _payments[p.PaymentId] = p;
        return p;
    }

    public IReadOnlyList<Invoice> Invoices(string? orderId) =>
        _invoices.Values.Where(i => orderId is null || i.OrderId == orderId).OrderBy(i => i.IssuedAt).ToList();

    /// <summary>Handles one event from the orders topic. Returns the invoice it issued, if any.</summary>
    public Invoice? Handle(JsonElement envelope)
    {
        var id = envelope.GetProperty("event_id").GetString()!;
        if (envelope.GetProperty("event_type").GetString() != "order.placed") return null;
        if (!_seenEvents.TryAdd(id, true)) return null;
        var order = envelope.GetProperty("data").GetProperty("order");
        var lines = new List<InvoiceLine>();
        foreach (var l in order.GetProperty("lines").EnumerateArray())
        {
            var qty = l.GetProperty("qty").GetInt32();
            var unit = ReadMoney(l.GetProperty("unit_price"));
            lines.Add(new InvoiceLine(l.GetProperty("sku").GetString()!, l.GetProperty("name").GetString()!, qty, unit, Money.Usd(unit.Minor * qty)));
        }
        var invoice = new Invoice("inv_" + Guid.NewGuid().ToString("N")[..8], order.GetProperty("order_id").GetString()!,
            order.GetProperty("customer_id").GetString()!, order.GetProperty("email").GetString()!, lines,
            ReadMoney(order.GetProperty("subtotal")), ReadMoney(order.GetProperty("tax")),
            ReadMoney(order.GetProperty("total")), "paid", DateTime.UtcNow.ToString("o"));
        _invoices[invoice.InvoiceId] = invoice;
        publisher.Publish(Topic, new
        {
            event_id = "evt_" + Guid.NewGuid(),
            event_type = "invoice.paid",
            occurred_at = DateTime.UtcNow.ToString("o"),
            data = new { invoice },
        });
        return invoice;
    }
}
