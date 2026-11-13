using System.Collections.Concurrent;
using System.Text.Json;

namespace Seedco.Billing;

public record QuoteLine(string Sku, int Qty, decimal UnitPrice);
public record QuoteRequest(int PostalCode, List<QuoteLine> Lines);
public record Quote(decimal Subtotal, decimal Tax, decimal Total);
public record ChargeRequest(string OrderId, string CustomerId, decimal Amount);
public record Payment(string PaymentId, string OrderId, string CustomerId, decimal Amount, string Status);
public record InvoiceLine(string Sku, string Name, int Qty, decimal UnitPrice, decimal Amount);
public record Invoice(string InvoiceId, string OrderId, string CustomerId, string Email, List<InvoiceLine> Lines,
    decimal Subtotal, decimal Tax, decimal Total, string Status, string IssuedAt);

public interface IEventPublisher
{
    void Publish(string topic, object envelope);
}

public class BillingException(string message) : Exception(message);

/// <summary>Prices, tax, payments and invoices. Money is decimal dollars, rounded to cents half away from zero.</summary>
public class BillingService(IEventPublisher publisher)
{
    public const string Topic = "billing";
    public const string OrdersTopic = "orders";

    private readonly ConcurrentDictionary<string, Payment> _payments = new();
    private readonly ConcurrentDictionary<string, Invoice> _invoices = new();
    private readonly ConcurrentDictionary<string, bool> _seenEvents = new();

    /// <summary>Sales tax by the first digit of the postal code.</summary>
    public static decimal TaxRate(int postalCode)
    {
        var first = postalCode.ToString()[0];
        return first == '9' ? 0.0875m : 0.06m;
    }

    public static decimal Round(decimal amount) => Math.Round(amount, 2, MidpointRounding.AwayFromZero);

    public Quote Quote(QuoteRequest req)
    {
        if (req.Lines is null || req.Lines.Count == 0) throw new BillingException("lines must not be empty");
        if (req.PostalCode <= 0) throw new BillingException("postal_code must be positive");
        var subtotal = 0m;
        foreach (var l in req.Lines)
        {
            if (l.Qty < 1 || l.UnitPrice < 0) throw new BillingException("invalid line");
            subtotal += l.UnitPrice * l.Qty;
        }
        var tax = Round(subtotal * TaxRate(req.PostalCode));
        return new Quote(Round(subtotal), tax, Round(subtotal) + tax);
    }

    public Payment Charge(ChargeRequest req)
    {
        if (req.Amount <= 0) throw new BillingException("amount must be positive");
        var p = new Payment("pay_" + Guid.NewGuid().ToString("N")[..8], req.OrderId, req.CustomerId, Round(req.Amount), "succeeded");
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
            var unit = l.GetProperty("unit_price").GetDecimal();
            lines.Add(new InvoiceLine(l.GetProperty("sku").GetString()!, l.GetProperty("name").GetString()!, qty, unit, Round(unit * qty)));
        }
        var invoice = new Invoice("inv_" + Guid.NewGuid().ToString("N")[..8], order.GetProperty("order_id").GetString()!,
            order.GetProperty("customer_id").GetString()!, order.GetProperty("email").GetString()!, lines,
            order.GetProperty("subtotal").GetDecimal(), order.GetProperty("tax").GetDecimal(),
            order.GetProperty("total").GetDecimal(), "paid", DateTime.UtcNow.ToString("o"));
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
