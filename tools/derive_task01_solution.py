"""Derives the task 1 reference solution (money as Money objects in minor units) from the base services.

Every edit is an exact replacement that must match the expected number of times, so a change to a base file that
this script does not know about fails loudly instead of producing a stale solution.
Usage: python3 tools/derive_task01_solution.py .   (run tools/write_contracts.py first)
"""
import os
import re
import sys

REPO = sys.argv[1]
SOL = os.path.join(REPO, "tasks", "task01_money", "solution")


def derive(rel, edits, regexes=()):
    text = open(os.path.join(REPO, rel)).read()
    for old, new, *count in edits:
        want = count[0] if count else 1
        assert text.count(old) == want, "{}: {!r} occurs {} times, expected {}".format(rel, old[:70], text.count(old), want)
        text = text.replace(old, new)
    for pattern, fn in regexes:
        text, n = re.subn(pattern, fn, text)
        assert n, "{}: /{}/ matched nothing".format(rel, pattern)
    out = os.path.join(SOL, rel)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w").write(text)


def between(rel, start, end):
    text = open(os.path.join(REPO, rel)).read()
    a = text.index(start)
    return text[a:text.index(end, a) + len(end)]


def cents(s):
    return str(round(float(s) * 100))


USD_JSON = lambda m: '{"currency": "USD", "minor": %s}' % cents(m.group(2))  # noqa: E731

# ---------------- notifications ----------------
derive("services/notifications/src/payload.py", [
    ("MONEY = NUM  # money on the wire is a plain number of dollars",
     'MONEY = obj(["currency", "minor"], currency={"enum": ["USD"]}, minor=INT)  # a Money object: integer minor units'),
])
derive("services/notifications/src/notifications.py", [
    ('''def money(amount) -> str:
    value = float(amount)
    return ("-" if value < 0 else "") + "${:,.2f}".format(abs(value))''',
     '''def money(amount: dict) -> str:
    """A Money object ({"currency", "minor"}) as dollars. Only USD exists today."""
    minor = amount["minor"]
    return ("-" if minor < 0 else "") + "${:,.2f}".format(abs(minor) / 100)'''),
])
derive("services/notifications/test/test_notifications.py", [
    ('money(54.35)', 'money(usd(5435))'), ('money(1234.5)', 'money(usd(123450))'), ('money(-54.84)', 'money(usd(-5484))'),
    ('subtotal=7.96, tax=0.70, total=8.66', 'subtotal=usd(796), tax=usd(70), total=usd(866)'),
    ('def event(event_id, event_type, **data):', 'def usd(minor):\n    return {"currency": "USD", "minor": minor}\n\n\ndef event(event_id, event_type, **data):'),
    ('with self.assertRaises(PayloadError):   # total must be a number', 'with self.assertRaises(PayloadError):   # total must be a Money object'),
], [(r'"(unit_price|amount|subtotal|tax|total)": (-?\d+(?:\.\d+)?)', lambda m: '"%s": %s' % (m.group(1), USD_JSON(m)))])

# ---------------- storefront ----------------
derive("services/storefront/src/clients/orders.ts", [
    ("export interface Product {", "// Money on every contract: integer minor units (cents) with a currency. Only USD exists today.\n"
                                   "export interface Money { currency: string; minor: number }\nexport interface Product {"),
    ("unit_price: number", "unit_price: Money", 2),
    ("items: CartItem[]; subtotal: number }", "items: CartItem[]; subtotal: Money }"),
    ("subtotal: number; tax: number; total: number;", "subtotal: Money; tax: Money; total: Money;"),
])
derive("services/storefront/src/clients/billing.ts", [
    ('import { call } from "./http.ts";', 'import { call } from "./http.ts";\nimport type { Money } from "./orders.ts";'),
    ("total: number; status: string; reason?: string", "total: Money; status: string; reason?: string"),
    ("unit_price: number", "unit_price: Money", 2),
])
derive("services/storefront/src/views.ts", [
    ('import type { Cart, Order, OrderLine, Product } from "./clients/orders.ts";',
     'import type { Cart, Money, Order, OrderLine, Product } from "./clients/orders.ts";'),
    ("export type { Invoice, Order, OrderLine };", "export type { Invoice, Money, Order, OrderLine };"),
    ('''export function money(amount: number): string {
  return (amount < 0 ? "-" : "") + "$" + Math.abs(amount).toFixed(2).replace(/\\B(?=(\\d{3})+(?!\\d))/g, ",");
}''',
     '''// Money arrives as integer minor units (cents). Only USD exists today.
export function money(amount: Money): string {
  return (amount.minor < 0 ? "-" : "") + "$" + (Math.abs(amount.minor) / 100).toFixed(2).replace(/\\B(?=(\\d{3})+(?!\\d))/g, ",");
}

const times = (amount: Money, qty: number): Money => ({ currency: amount.currency, minor: amount.minor * qty });'''),
    ("money(l.unit_price * l.qty)", "money(times(l.unit_price, l.qty))"),
    ("money(i.unit_price * i.qty)", "money(times(i.unit_price, i.qty))"),
    ("money(s.unit_price * s.qty)", "money(times(s.unit_price, s.qty))"),
    ("p.unit_price > s.unit_price", "p.unit_price.minor > s.unit_price.minor"),
])
TS_USD = lambda m: "%s: usd(%s)" % (m.group(1), cents(m.group(2)))  # noqa: E731
derive("services/storefront/test/views.test.ts", [
    ('import { cartPage, catalogPage, money, orderPage, subscriptionPage, validateCheckout, type Order } from "../src/views.ts";',
     'import { cartPage, catalogPage, money, orderPage, subscriptionPage, validateCheckout, type Money, type Order } from "../src/views.ts";\n\n'
     'const usd = (minor: number): Money => ({ currency: "USD", minor });'),
    ('money(54.35)', 'money(usd(5435))'), ('money(6)', 'money(usd(600))'), ('money(1234.5)', 'money(usd(123450))'),
    ('money(-13.7)', 'money(usd(-1370))'),
], [(r'\b(unit_price|subtotal|tax|total): (-?\d+(?:\.\d+)?)', TS_USD)])
derive("services/storefront/test/app.test.ts", [
    ('import type { Cart, Order, OrdersClient } from "../src/clients/orders.ts";',
     'import type { Cart, Money, Order, OrdersClient } from "../src/clients/orders.ts";'),
    ('const PRODUCTS = [', 'const usd = (minor: number): Money => ({ currency: "USD", minor });\nconst PRODUCTS = ['),
    ('subtotal: items.reduce((n, i) => n + i.unit_price * i.qty, 0) };', 'subtotal: usd(items.reduce((n, i) => n + i.unit_price.minor * i.qty, 0)) };'),
    ('lines: cart.items, subtotal: cart.subtotal, tax: 1, total: cart.subtotal + 1,',
     'lines: cart.items, subtotal: cart.subtotal, tax: usd(100), total: usd(cart.subtotal.minor + 100),'),
], [(r'\b(unit_price|subtotal|tax|total): (-?\d+(?:\.\d+)?)(?=[ ,}])', TS_USD)])

# ---------------- orders ----------------
derive("services/orders/src/seedco/orders/Db.java", [
    ("import java.math.BigDecimal;\n", ""),
    ("            .enable(DeserializationFeature.USE_BIG_DECIMAL_FOR_FLOATS)\n",
     "            .enable(DeserializationFeature.USE_BIG_DECIMAL_FOR_FLOATS)\n            .enable(DeserializationFeature.USE_LONG_FOR_INTS)\n"),
    ("unit_price DECIMAL(10,2) NOT NULL)", "unit_price BIGINT NOT NULL)"),   # cents
    ("String name, BigDecimal unitPrice) {", "String name, long unitPrice) {"),
])
derive("services/orders/src/seedco/orders/Main.java", [
    ("import java.math.BigDecimal;\n", ""),
    ("public Map<String, Object> charge(Map<String, Object> order, BigDecimal amount) {",
     "public Map<String, Object> charge(Map<String, Object> order, Map<String, Object> amount) {"),
])
derive("services/orders/src/seedco/orders/Orders.java", [
    ("import java.math.BigDecimal;\n", ""),
    ("Map<String, Object> charge(Map<String, Object> order, BigDecimal amount);",
     "Map<String, Object> charge(Map<String, Object> order, Map<String, Object> amount);"),
    ("// What the catalogue starts with: sku, name, unit price in dollars.", "// What the catalogue starts with: sku, name, unit price in cents."),
    ('new BigDecimal("24.99")', "2499L"), ('new BigDecimal("39.50")', "3950L"), ('new BigDecimal("6.25")', "625L"),
    ("(String) CATALOG[i][1], (BigDecimal) CATALOG[i][2]);", "(String) CATALOG[i][1], (Long) CATALOG[i][2]);"),
    ("product(r.getString(1), r.getString(2), r.getBigDecimal(3))", "product(r.getString(1), r.getString(2), r.getLong(3))", 3),
    ("private static Map<String, Object> product(String sku, String name, BigDecimal unitPrice) {",
     "private static Map<String, Object> product(String sku, String name, long unitPrice) {"),
    ('        p.put("unit_price", unitPrice);', '        p.put("unit_price", money(unitPrice));'),
    ('''        BigDecimal subtotal = BigDecimal.ZERO;
        for (Map<String, Object> item : items) {
            subtotal = subtotal.add(((BigDecimal) item.get("unit_price")).multiply(new BigDecimal((Integer) item.get("qty"))));
        }''',
     '''        long subtotal = 0;
        for (Map<String, Object> item : items) {
            subtotal += minor(item.get("unit_price")) * (Integer) item.get("qty");
        }'''),
    ('        cart.put("subtotal", subtotal);', '        cart.put("subtotal", money(subtotal));'),
    ('billing.charge(o, new BigDecimal(quote.get("total").toString()));', 'billing.charge(o, (Map<String, Object>) quote.get("total"));'),
    ("    private static String str(Map<String, Object> m, String key) {",
     '''    /** Money on every contract: integer minor units (cents) with a currency. Only USD exists today. */
    static Map<String, Object> money(long minor) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("currency", "USD");
        m.put("minor", minor);
        return m;
    }

    /** The cents in a Money object. */
    static long minor(Object money) {
        return ((Number) ((Map<?, ?>) money).get("minor")).longValue();
    }

    private static String str(Map<String, Object> m, String key) {'''),
])
derive("services/orders/test/seedco/orders/OrdersTest.java", [
    ("import java.math.BigDecimal;\n", ""),
    ("    List<BigDecimal> charged;", "    List<Map<String, Object>> charged;"),
    ('''                BigDecimal subtotal = BigDecimal.ZERO;
                for (Map<String, Object> l : lines) {
                    subtotal = subtotal.add(((BigDecimal) l.get("unit_price")).multiply(new BigDecimal((Integer) l.get("qty"))));
                }
                return Map.of("subtotal", subtotal, "tax", new BigDecimal("1.00"), "total", subtotal.add(new BigDecimal("1.00")));''',
     '''                long subtotal = 0;
                for (Map<String, Object> l : lines) {
                    subtotal += Orders.minor(l.get("unit_price")) * (Integer) l.get("qty");
                }
                return Map.of("subtotal", Orders.money(subtotal), "tax", Orders.money(100), "total", Orders.money(subtotal + 100));'''),
    ("public Map<String, Object> charge(Map<String, Object> order, BigDecimal amount) {",
     "public Map<String, Object> charge(Map<String, Object> order, Map<String, Object> amount) {"),
    ('new BigDecimal("50.98")', "Orders.money(5098)", 4),
    ('new BigDecimal("56.23")', "Orders.money(5623)"), ('new BigDecimal("57.23")', "Orders.money(5723)"),
])

# ---------------- billing ----------------
B = "services/billing/src/Billing.cs"
derive(B, [
    ("public record QuoteLine(string Sku, int Qty, decimal UnitPrice);",
     '''/// <summary>Money on every contract: integer minor units (cents) with a currency. Only USD exists today.</summary>
public record Money(string Currency, long Minor)
{
    public static Money Usd(long minor) => new("USD", minor);
}

public record QuoteLine(string Sku, int Qty, Money UnitPrice);'''),
    ("public record Quote(decimal Subtotal, decimal Tax, decimal Total);", "public record Quote(Money Subtotal, Money Tax, Money Total);"),
    ("string CustomerId, decimal Amount, string? Email = null, string? PaymentMethod = null);",
     "string CustomerId, Money Amount, string? Email = null, string? PaymentMethod = null);"),
    ("string CustomerId, decimal Amount, string Status,", "string CustomerId, Money Amount, string Status,"),
    ("string CustomerId, decimal Amount, string CreatedAt);", "string CustomerId, Money Amount, string CreatedAt);"),
    ("int Qty, decimal UnitPrice, decimal Amount);", "int Qty, Money UnitPrice, Money Amount);"),
    ("List<InvoiceLine> Lines, decimal Subtotal, decimal Tax, decimal Total, string Status, string IssuedAt);",
     "List<InvoiceLine> Lines, Money Subtotal, Money Tax, Money Total, string Status, string IssuedAt);"),
    ("public record Plan(string Sku, string Name, decimal UnitPrice);", "public record Plan(string Sku, string Name, Money UnitPrice);"),
    ("string Sku, string Name, int Qty, decimal UnitPrice, string Status, string CurrentPeriodStart",
     "string Sku, string Name, int Qty, Money UnitPrice, string Status, string CurrentPeriodStart"),
    ("Money is decimal dollars, rounded to cents half away from zero.", "Money is integer cents; tax and proration round half up to the cent."),
    ('"Small monthly box", 24.99m)', '"Small monthly box", Money.Usd(2499))'),
    ('"Large monthly box", 39.50m)', '"Large monthly box", Money.Usd(3950))'),
    (between(B, "    /// <summary>Sales tax by the first digit of the postal code.</summary>", "=> Round(amount * days / periodDays);"),
     '''    /// <summary>Sales tax by the first digit of the postal code, in basis points.</summary>
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
        if (m is null || m.Currency != "USD") throw new BillingException("money must be {currency: \\"USD\\", minor}");
        return m.Minor;
    }

    private static Money ReadMoney(JsonElement e) =>
        Money.Usd(e.GetProperty("currency").GetString() == "USD" ? e.GetProperty("minor").GetInt64() : throw new BillingException("unsupported currency"));'''),
    (between(B, "        var subtotal = 0m;", "return new Quote(Round(subtotal), tax, Round(subtotal) + tax);"),
     '''        long subtotal = 0;
        foreach (var l in req.Lines)
        {
            if (l.Qty < 1 || Minor(l.UnitPrice) < 0) throw new BillingException("invalid line");
            subtotal += l.UnitPrice.Minor * l.Qty;
        }
        var tax = Tax(subtotal, req.PostalCode);
        return new Quote(Money.Usd(subtotal), Money.Usd(tax), Money.Usd(subtotal + tax));'''),
    ("if (req.Amount <= 0) throw", "if (Minor(req.Amount) <= 0) throw"),
    ("{Round(req.Amount).ToString(CultureInfo.InvariantCulture)}", "{req.Amount.Minor}"),
    ('Round(req.Amount), declined ? "failed"', 'req.Amount, declined ? "failed"'),
    ("List<InvoiceLine> lines, decimal subtotal, decimal tax, decimal total)", "List<InvoiceLine> lines, long subtotal, long tax, long total)"),
    ('reason, lines, subtotal, tax, total, "paid", Now());', 'reason, lines, Money.Usd(subtotal), Money.Usd(tax), Money.Usd(total), "paid", Now());'),
    ('var unit = l.GetProperty("unit_price").GetDecimal();', 'var unit = ReadMoney(l.GetProperty("unit_price"));'),
    ("qty, unit, Round(unit * qty)));", "qty, unit, Money.Usd(unit.Minor * qty)));"),
    ('''order.GetProperty("subtotal").GetDecimal(),
            order.GetProperty("tax").GetDecimal(), order.GetProperty("total").GetDecimal());''',
     '''ReadMoney(order.GetProperty("subtotal")).Minor,
            ReadMoney(order.GetProperty("tax")).Minor, ReadMoney(order.GetProperty("total")).Minor);'''),
    ("if (plan.UnitPrice < s.UnitPrice)", "if (plan.UnitPrice.Minor < s.UnitPrice.Minor)"),
    ("var credit = -Prorate(s.UnitPrice * s.Qty, left, periodDays);", "var credit = -Prorate(s.UnitPrice.Minor * s.Qty, left, periodDays);"),
    ("var charge = Prorate(plan.UnitPrice * s.Qty, left, periodDays);", "var charge = Prorate(plan.UnitPrice.Minor * s.Qty, left, periodDays);"),
    ("s.Qty, s.UnitPrice, credit),", "s.Qty, s.UnitPrice, Money.Usd(credit)),"),
    ("s.Qty, plan.UnitPrice, charge),", "s.Qty, plan.UnitPrice, Money.Usd(charge)),"),
    ("var tax = Round(subtotal * TaxRate(s.PostalCode));", "var tax = Tax(subtotal, s.PostalCode);", 2),
    ("new ChargeRequest(s.OrderId, s.CustomerId, subtotal + tax, s.Email, s.PaymentMethod)",
     "new ChargeRequest(s.OrderId, s.CustomerId, Money.Usd(subtotal + tax), s.Email, s.PaymentMethod)", 2),
    ("var subtotal = Round(s.UnitPrice * s.Qty);", "var subtotal = s.UnitPrice.Minor * s.Qty;"),
    ('[new InvoiceLine("RECURRING", s.Sku, s.Name, s.Qty, s.UnitPrice, subtotal)]', '[new InvoiceLine("RECURRING", s.Sku, s.Name, s.Qty, s.UnitPrice, Money.Usd(subtotal))]'),
])
T = "services/billing/tests/BillingTests.cs"
CS_USD = lambda m: "Money.Usd(%s)" % cents(m.group(1))  # noqa: E731
derive(T, [
    ("params (decimal price, int qty)[] lines)", "params (Money price, int qty)[] lines)"),
    ('"unit_price":24.99},', '"unit_price":{"currency":"USD","minor":2499} },'),
    ('"unit_price":6.25}],', '"unit_price":{"currency":"USD","minor":625} }],'),
    ('"subtotal":56.23,"tax":4.92,"total":61.15} } }',
     '"subtotal":{"currency":"USD","minor":5623},"tax":{"currency":"USD","minor":492},"total":{"currency":"USD","minor":6115} } } }'),
    (between(T, "        // 100 a month upgraded to 200 on 15 January", "100m - BillingService.Prorate(100m, 17, 31));"),
     '''        // 100.00 a month upgraded to 200.00 on 15 January: 14 of 31 days used, 17 left.
        Assert.Equal(10968, BillingService.Prorate(20000, 17, 31));
        Assert.Equal(5484, BillingService.Prorate(10000, 17, 31));
        Assert.Equal(4516, 10000 - BillingService.Prorate(10000, 17, 31));'''),
    ("        Assert.Equal(1.50m, b.Quote(Request(10001, (24.99m, 1))).Tax);   // 24.99 * 0.06 = 1.4994",
     "        Assert.Equal(1.50m, b.Quote(Request(10001, (24.99m, 1))).Tax);   // 24.99 * 0.06 = 1.4994\n"
     "        Assert.Equal(9.74m, b.Quote(Request(10001, (162.25m, 1))).Tax);  // 162.25 * 0.06 = 9.735, half up"),
], [(r"(-?\d+(?:\.\d+)?)m\b", CS_USD)])
print("solution derived")
