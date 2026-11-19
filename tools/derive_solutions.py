"""Derives each task's reference solution from the base services.

A ticket is a set of exact edits to base files. A task's solution is its tickets applied together. Every edit must
match the expected number of times, so a change to a base file that this script does not know about fails loudly
instead of producing a stale solution.
Usage: python3 tools/derive_solutions.py .
"""
import os
import shutil
import sys

REPO = sys.argv[1]
TICKETS = {}       # ticket -> [(file, [(old, new, count?)...])]
NEW_FILES = {}     # ticket -> {file: content}


def ticket(name):
    TICKETS[name], NEW_FILES[name] = [], {}

    def derive(rel, edits):
        TICKETS[name].append((rel, edits))
    return derive


def build(task, tickets, pinned_schema_readers=(), after=None):
    """Writes tasks/<task>/solution: every file a ticket edits or adds, plus the readers' pinned copies of Core's schema."""
    sol = os.path.join(REPO, "tasks", task, "solution")
    shutil.rmtree(sol, ignore_errors=True)
    texts = {}
    for name in tickets:
        for rel, edits in TICKETS[name]:
            text = texts[rel] if rel in texts else open(os.path.join(REPO, rel)).read()
            for old, new, *count in edits:
                want = count[0] if count else 1
                assert text.count(old) == want, "{} {}: {!r} occurs {} times, expected {}".format(name, rel, old[:70], text.count(old), want)
                text = text.replace(old, new)
            texts[rel] = text
        texts.update(NEW_FILES[name])
    for rel, text in texts.items():
        out = os.path.join(sol, rel)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, "w").write(text)
    for reader in pinned_schema_readers:
        pinned = os.path.join(sol, "services", reader, "pinned")
        os.makedirs(pinned, exist_ok=True)
        shutil.copy(os.path.join(sol, "services/core/contracts/schema.graphql"), os.path.join(pinned, "schema.graphql"))
    if after:
        after(sol)
    print("{}: {} files from {}".format(task, sum(len(f) for _, _, f in os.walk(sol)), ", ".join(tickets)))


# ======================= OPS-7: staff confirm orders before they are fulfilled =======================
derive = ticket("OPS-7")

# ---------------- core ----------------
derive("services/core/contracts/schema.graphql", [
    ("  orderCancel(id: ID!): OrderCancel\n",
     '  orderCancel(id: ID!): OrderCancel\n  "Requires MANAGE_ORDERS. Confirms an UNCONFIRMED order, which can then be fulfilled."\n'
     "  orderConfirm(id: ID!): OrderConfirm\n"),
    ("type OrderCreated implements Event { issuedAt: DateTime, version: String, recipient: App, order: Order }\n",
     "type OrderCreated implements Event { issuedAt: DateTime, version: String, recipient: App, order: Order }\n"
     '"Sent when staff confirm an order (ORDER_CONFIRMED)."\n'
     "type OrderConfirmed implements Event { issuedAt: DateTime, version: String, recipient: App, order: Order }\n"),
    ("type OrderCancel { order: Order, errors: [OrderError!]! }\n",
     "type OrderCancel { order: Order, errors: [OrderError!]! }\ntype OrderConfirm { order: Order, errors: [OrderError!]! }\n"),
])
derive("services/core/src/core.py", [
    ('        order = self._new_order(doc, "CHECKOUT", "UNFULFILLED")',
     '        order = self._new_order(doc, "CHECKOUT", "UNCONFIRMED")   # a shop order waits for staff to confirm it'),
    ('        if doc["status"] in ("DRAFT", "CANCELED", "FULFILLED"):', '        if doc["status"] in ("DRAFT", "UNCONFIRMED", "CANCELED", "FULFILLED"):'),
    ('        self._emit("ORDER_CREATED", "OrderCreated", doc)\n',
     '        self._emit("ORDER_CREATED", "OrderCreated", doc)\n'
     '        self._emit("ORDER_CONFIRMED", "OrderConfirmed", doc)   # an order an app creates is not held: it is confirmed at once\n'),
    ("    def order_fulfill(self, order: str, input: dict) -> dict:",
     '''    def order_confirm(self, id: str) -> dict:
        """Staff confirm an order placed in a shop. Only then can it be fulfilled."""
        doc = self._order(id)
        if doc["status"] != "UNCONFIRMED":
            raise ApiError("INVALID", "Provided order id belongs to an order with status different than unconfirmed.", "id")
        doc["status"] = "UNFULFILLED"
        result = self._save_order(doc)
        self._emit("ORDER_CONFIRMED", "OrderConfirmed", doc)
        return result

    def order_fulfill(self, order: str, input: dict) -> dict:'''),
])
derive("services/core/src/server.py", [
    ('    mutation("orderCancel", core.order_cancel, "MANAGE_ORDERS")\n',
     '    mutation("orderCancel", core.order_cancel, "MANAGE_ORDERS")\n    mutation("orderConfirm", core.order_confirm, "MANAGE_ORDERS")\n'),
])
derive("services/core/NOTES.md", [
    ("- Order numbers count up from 1. Statuses: DRAFT, UNFULFILLED, PARTIALLY_FULFILLED, FULFILLED, CANCELED.",
     "- Order numbers count up from 1. Statuses: DRAFT, UNCONFIRMED, UNFULFILLED, PARTIALLY_FULFILLED, FULFILLED, CANCELED.\n"
     "  An order from a checkout starts UNCONFIRMED and staff confirm it (`orderConfirm`, event ORDER_CONFIRMED) before it\n"
     "  can be fulfilled. An order an app creates through a draft is not held."),
])
derive("services/core/test/test_core.py", [
    ("  ... on OrderFullyPaid { order { number chargeStatus } } ", "  ... on OrderFullyPaid { order { number chargeStatus } } ... on OrderConfirmed { order { number status } } "),
    ('"asyncEvents": ["ORDER_CREATED", "ORDER_FULLY_PAID", "ORDER_CANCELLED",', '"asyncEvents": ["ORDER_CREATED", "ORDER_CONFIRMED", "ORDER_FULLY_PAID", "ORDER_CANCELLED",'),
    ('("1", "UNFULFILLED", "FULL", True))', '("1", "UNCONFIRMED", "FULL", True))'),
    ('["OrderCreated", "OrderFullyPaid"])', '["OrderCreated", "OrderConfirmed", "OrderFullyPaid"])'),
    ('        first = self.complete(self.checkout())["order"]\n',
     '        first = self.complete(self.checkout())["order"]\n        self.assertEqual(self.confirm(first["id"])["order"]["status"], "UNFULFILLED")\n'),
    ("    def deliver(self):",
     '''    def confirm(self, order_id, token=None):
        return self.gql("mutation($id: ID!) { orderConfirm(id: $id) { order { status } errors { code } } }",
                        token or self.staff(), id=order_id)["orderConfirm"]

    def test_a_shop_order_waits_for_staff_to_confirm_it(self):
        order = self.complete(self.checkout())["order"]
        line = self.gql("query($id: ID!) { order(id: $id) { lines { id } } }", id=order["id"])["order"]["lines"][0]["id"]
        fulfil = "mutation($o: ID!, $l: [OrderFulfillLineInput!]!) { orderFulfill(order: $o, input: {lines: $l}) { order { status } errors { code } } }"
        held = self.gql(fulfil, self.staff(), o=order["id"], l=[{"orderLineId": line, "quantity": 1}])["orderFulfill"]
        self.assertEqual(held["errors"], [{"code": "CANNOT_FULFILL"}])
        denied = self.api.run({"query": "mutation($id: ID!) { orderConfirm(id: $id) { errors { code } } }", "variables": {"id": order["id"]}})
        self.assertEqual(denied["errors"][0]["extensions"]["exception"]["code"], "PermissionDenied")
        self.assertEqual(self.confirm(order["id"]), {"order": {"status": "UNFULFILLED"}, "errors": []})
        self.assertEqual(self.confirm(order["id"])["errors"], [{"code": "INVALID"}])
        self.assertEqual(self.gql(fulfil, self.staff(), o=order["id"], l=[{"orderLineId": line, "quantity": 1}])["orderFulfill"]["errors"], [])
        self.deliver()
        self.assertEqual(self.listener.events("order_confirmed"), [{"__typename": "OrderConfirmed", "order": {"number": "1", "status": "UNFULFILLED"}}])

    def deliver(self):'''),
])

# ---------------- notifications ----------------
derive("services/notifications/graphql/order-events.graphql", [
    ("    ... on OrderCreated { order { ...OrderDetails } }", "    ... on OrderConfirmed { order { ...OrderDetails } }"),
])
derive("services/notifications/src/server.py", [
    ('"asyncEvents": ["ORDER_CREATED", "ORDER_FULLY_PAID",', '"asyncEvents": ["ORDER_CONFIRMED", "ORDER_FULLY_PAID",'),
])
derive("services/notifications/src/notifications.py", [
    ('    "OrderCreated": (render_order_created, lambda o: o["id"]),', '    "OrderConfirmed": (render_order_created, lambda o: o["id"]),   # sent once staff confirm the order'),
])
derive("services/notifications/test/test_notifications.py", [("OrderCreated", "OrderConfirmed", 11)])
derive("services/notifications/NOTES.md", [
    ("- Events: ORDER_CREATED (confirmation), ORDER_FULLY_PAID (receipt)", "- Events: ORDER_CONFIRMED (confirmation, once staff confirm the order), ORDER_FULLY_PAID (receipt)"),
])

# ---------------- taxes ----------------
derive("services/taxes/graphql/order-events.graphql", [
    ("# What the tax app reads when an order is created (a tax document is committed) or cancelled (it is voided).",
     "# What the tax app reads when an order is confirmed (a tax document is committed) or cancelled (it is voided)."),
    ("    ... on OrderCreated { order { id number total", "    ... on OrderConfirmed { order { id number total"),
])
derive("services/taxes/src/seedco/taxes/Main.java", [
    ('orders.put("asyncEvents", List.of("ORDER_CREATED", "ORDER_CANCELLED"));', 'orders.put("asyncEvents", List.of("ORDER_CONFIRMED", "ORDER_CANCELLED"));'),
])
derive("services/taxes/src/seedco/taxes/Taxes.java", [
    ("/** Handles ORDER_CREATED (commit a tax document) and ORDER_CANCELLED (void it). Safe to repeat. */",
     "/** Handles ORDER_CONFIRMED (commit a tax document) and ORDER_CANCELLED (void it). Safe to repeat. */"),
])
derive("services/taxes/test/seedco/taxes/TaxesTest.java", [('Map.of("__typename", "OrderCreated", "order", order)', 'Map.of("__typename", "OrderConfirmed", "order", order)', 2)])
derive("services/taxes/NOTES.md", [
    ("- A tax document is committed when an order is created and voided when it is cancelled.",
     "- A tax document is committed when staff confirm an order and voided when it is cancelled. An order cancelled\n  before it was confirmed never has one."),
])

# ---------------- dashboard ----------------
derive("services/dashboard/src/clients/core.ts", [
    ("  cancel(token: string, orderId: string): Promise<void>;\n", "  cancel(token: string, orderId: string): Promise<void>;\n  confirm(token: string, orderId: string): Promise<void>;\n"),
    ('    cancel: (token, orderId) => mutate(token, "orderCancel",',
     '    confirm: (token, orderId) => mutate(token, "orderConfirm", `mutation($id: ID!) { orderConfirm(id: $id) { errors { field message code } } }`, { id: orderId }),\n'
     '    cancel: (token, orderId) => mutate(token, "orderCancel",'),
])
derive("services/dashboard/src/views.ts", [
    ("    to_fulfill: open && unfulfilled.length > 0 ?", '    to_fulfill: open && o.status !== "UNCONFIRMED" && unfulfilled.length > 0 ?'),
    ("    can_cancel: open && o.lines.every((l) => l.quantityFulfilled === 0),\n",
     "    can_cancel: open && o.lines.every((l) => l.quantityFulfilled === 0),\n"
     '    can_confirm: o.status === "UNCONFIRMED",   // a shop order waits for staff before it can be fulfilled\n'),
])
derive("services/dashboard/src/pages.ts", [
    ("  const actions = [\n", '  const actions = [\n    o.can_confirm ? `<form class="inline" method="post" action="/orders/${id}/confirm"><button>Confirm order</button></form>` : "",\n'),
])
derive("services/dashboard/src/app.ts", [
    ("(?:\\/(fulfill|cancel|refund))?$/", "(?:\\/(confirm|fulfill|cancel|refund))?$/"),
    ('        if (m[2] === "cancel") await core.cancel(token, order.id);\n',
     '        if (m[2] === "cancel") await core.cancel(token, order.id);\n        if (m[2] === "confirm") await core.confirm(token, order.id);\n'),
])
derive("services/dashboard/test/app.test.ts", [
    ("  cancel: async () => { throw new Refused(\"This order can't be canceled.\"); },\n",
     "  cancel: async () => { throw new Refused(\"This order can't be canceled.\"); },\n"
     '  confirm: async (_token, id) => { calls.push("confirm " + id); order.status = "UNFULFILLED"; },\n'),
    ("  assert.equal(calls.length, 3);\n});\n",
     '''  assert.equal(calls.length, 3);
});

test("an unconfirmed order is confirmed before it can be fulfilled", async () => {
  await browse("/logout", {});
  await signIn("admin@seedco.example");
  order.status = "UNCONFIRMED";
  order.lines[0].quantityFulfilled = 0;
  const held = await browse(ORDER_PATH);
  assert.match(held.text, /<strong>Unconfirmed<\\/strong>/);
  assert.match(held.text, /<button>Confirm order<\\/button>/);
  assert.doesNotMatch(held.text, /Fulfill remaining items/);
  assert.deepEqual([orderDetail(order).can_confirm, orderDetail(order).to_fulfill], [true, []]);
  assert.equal((await browse(ORDER_PATH + "/confirm", {})).status, 303);
  assert.equal(calls[3], "confirm " + order.id);
  const confirmed = await browse(ORDER_PATH);
  assert.match(confirmed.text, /Fulfill remaining items/);
  assert.doesNotMatch(confirmed.text, /Confirm order/);
});
'''),
])
derive("services/dashboard/NOTES.md", [
    ('- "Fulfill remaining items" fulfils every unfulfilled quantity at once.',
     '- An order placed in a shop is UNCONFIRMED until a member of staff presses "Confirm order". Fulfilment is only\n  offered after that.\n'
     '- "Fulfill remaining items" fulfils every unfulfilled quantity at once.'),
])


# ======================= SHOP-31: customers can search the shop =======================
derive = ticket("SHOP-31")
derive("services/storefront/src/clients/core.ts", [
    ("  products(): Promise<Product[]>;", "  products(search?: string): Promise<Product[]>;"),
    ("    products: async () => (await gql(`query($channel: String) { products(first: 100, channel: $channel) {",
     "    products: async (search) => (await gql(`query($channel: String, $filter: ProductFilterInput) { products(first: 100, channel: $channel, filter: $filter) {"),
    ("} } } }`, { channel })).products.edges.map((e: any) => e.node),",
     "} } } }`, { channel, filter: search ? { search } : null })).products.edges.map((e: any) => e.node),"),
])
derive("services/storefront/src/pages.ts", [
    ("renews: string | null }[], cartCount: number): string {\n  const cards", "renews: string | null }[], cartCount: number, query = \"\"): string {\n  const cards"),
    ('  return layout("Shop", cards.join("\\n"), cartCount);',
     '  const search = `<form class="card" method="get" action="/"><input type="search" name="q" value="${esc(query)}" placeholder="Search products" '
     'aria-label="Search products"> <button>Search</button>${query ? ` <a href="/">Show everything</a>` : ""}</form>`;\n'
     '  const nothing = `<p class="muted">Nothing matches "${esc(query)}".</p>`;\n'
     '  return layout("Shop", search + (cards.join("\\n") || nothing), cartCount);'),
])
derive("services/storefront/src/app.ts", [
    ("      html(res, 200, shopHtml(catalogPage(await core.products(), plans), cart.count));",
     '      const q = (new URL(req.url ?? "/", "http://localhost").searchParams.get("q") ?? "").trim();     // the search box\n'
     "      html(res, 200, shopHtml(catalogPage(await core.products(q || undefined), plans), cart.count, q));"),
])
derive("services/storefront/test/fixtures.ts", [
    ("    products: async () => PRODUCTS,", "    products: async (search) => PRODUCTS.filter((p) => !search || p.name.toLowerCase().includes(search.toLowerCase())),"),
])
derive("services/storefront/test/app.test.ts", [
    ('  assert.equal((await browse("/cart/items", { variant: "v1", qty: "2" })).location, "/cart");',
     '  const found = await browse("/?q=small");\n'
     "  assert.match(found.text, /Small monthly box/);\n"
     "  assert.doesNotMatch(found.text, /Tea &lt;add-on&gt;/);\n"
     '  assert.match(found.text, /name="q" value="small"/);\n'
     '  assert.match((await browse("/?q=zzz")).text, /Nothing matches/);\n\n'
     '  assert.equal((await browse("/cart/items", { variant: "v1", qty: "2" })).location, "/cart");'),
])
derive("services/storefront/NOTES.md", [
    ("- We keep no data.", "- The shop page has a search box (`/?q=...`). The search is Core's (`products(filter: {search})`), which matches product\n  names; we do not filter anything ourselves.\n- We keep no data."),
])

# ======================= SUP-12: an agent lists one customer's conversations =======================
derive = ticket("SUP-12")
derive("services/support/src/desk.rb", [
    ("    # Conversations, newest first, optionally of one status.\n    def conversations(status: nil)\n",
     "    # Conversations, newest first, optionally of one status and of one customer (by email, in any case).\n    def conversations(status: nil, email: nil)\n"),
    ('      ids = query("SELECT id FROM conversations WHERE (?1 IS NULL OR status = ?1) ORDER BY id DESC", [status]).map(&:first)',
     '      ids = query("SELECT c.id FROM conversations c JOIN contacts k ON k.id = c.contact_id " \\\n'
     '                  "WHERE (?1 IS NULL OR c.status = ?1) AND (?2 IS NULL OR k.email = ?2) ORDER BY c.id DESC", [status, email&.downcase]).map(&:first)'),
])
derive("services/support/src/server.rb", [
    ("      list = DESK.conversations(status: status)",
     '      email = params["email"] && String.new(params["email"]).force_encoding("UTF-8")\n      list = DESK.conversations(status: status, email: email)'),
])
derive("services/support/test/test_support.rb", [
    ("  def test_the_side_panel_shows_the_customers_orders_from_core",
     '''  def test_conversations_can_be_listed_for_one_customer
    mine = @desk.create_conversation(@pat["id"], "Hello")["id"]
    sam = @desk.create_contact(name: "Sam", email: "sam@example.com")
    @desk.create_conversation(sam["id"], "Hi")
    assert_equal [mine], @desk.conversations(email: "PAT@example.com").map { |c| c["id"] }
    assert_equal 2, @desk.conversations.size
    assert_equal [], @desk.conversations(email: "nobody@example.com")
    assert_equal [], @desk.conversations(status: "resolved", email: "pat@example.com")
  end

  def test_the_side_panel_shows_the_customers_orders_from_core'''),
])
derive("services/support/contracts/support-api.yaml", [
    ("Optional ?status=open|pending|resolved.'", "Optional ?status=open|pending|resolved and ?email=<address> for one customer''s conversations.'"),
])

# ======================= PAY-21: the payment lists are paged, and an intent can be read by id =======================
derive = ticket("PAY-21")
derive("services/payments/src/Payments.cs", [
    ("/// <summary>The app itself: turns Core's transaction webhooks",
     '''/// <summary>One page of a list (PAY-21): oldest first, 20 records unless asked otherwise, 100 at most.</summary>
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

/// <summary>The app itself: turns Core's transaction webhooks'''),
])
derive("services/payments/src/Program.cs", [
    ('''app.MapGet("/api/payment-intents", () => Results.Json(new { payment_intents = provider.Intents() }, Store.Json));
app.MapGet("/api/refunds", () => Results.Json(new { refunds = provider.Refunds() }, Store.Json));''',
     '''// The lists are paged (PAY-21). To find one payment, read it by id: it may not be on the first page.
IResult Paged<T>(IReadOnlyList<T> all, Func<T, string> id, string name, int? limit, string? startingAfter)
{
    try
    {
        var (items, more) = Paging.Page(all, id, limit, startingAfter);
        return Results.Json(new Dictionary<string, object> { [name] = items, ["has_more"] = more }, Store.Json);
    }
    catch (MalformedRequest e) { return Results.Json(new { error = "bad_request", message = e.Message }, Store.Json, statusCode: 400); }
}
app.MapGet("/api/payment-intents", (int? limit, string? starting_after) => Paged(provider.Intents(), i => i.Id, "payment_intents", limit, starting_after));
app.MapGet("/api/payment-intents/{id}", (string id) => provider.Intent(id) is { } intent
    ? Results.Json(intent, Store.Json)
    : Results.Json(new { error = "not_found", message = "no payment intent " + id }, Store.Json, statusCode: 404));
app.MapGet("/api/refunds", (int? limit, string? starting_after) => Paged(provider.Refunds(), r => r.Id, "refunds", limit, starting_after));'''),
])
derive("services/payments/tests/PaymentsTests.cs", [
    ("    [Fact]\n    public void IntentsSurviveARestart()",
     '''    [Fact]
    public void ListsArePagedOldestFirst()
    {
        var all = Enumerable.Range(1, 45).Select(i => "pi_" + i).ToList();
        var (first, more) = Paging.Page(all, x => x, null, null);
        Assert.Equal((20, "pi_1", "pi_20", true), (first.Count, first[0], first[^1], more));
        var (last, moreAfter) = Paging.Page(all, x => x, 100, "pi_40");
        Assert.Equal(new[] { "pi_41", "pi_42", "pi_43", "pi_44", "pi_45" }, last);
        Assert.False(moreAfter);
        Assert.Equal((5, false), (Paging.Page(all, x => x, 5, "pi_40").Items.Count, Paging.Page(all, x => x, 5, "pi_40").HasMore));
        Assert.Throws<MalformedRequest>(() => Paging.Page(all, x => x, 101, null));
        Assert.Throws<MalformedRequest>(() => Paging.Page(all, x => x, 0, null));
        Assert.Throws<MalformedRequest>(() => Paging.Page(all, x => x, 5, "pi_nope"));
    }

    [Fact]
    public void IntentsSurviveARestart()'''),
])
derive("services/payments/contracts/payments-api.yaml", [
    ("info: {title: Payments API, version: 1.0.0}", "info: {title: Payments API, version: 2.0.0}"),
    ('''      summary: Every payment the provider holds, oldest first.
      responses:
        '200': {description: Payment intents, content: {application/json: {schema: {type: object, properties: {payment_intents: {type: array, items: {$ref: '#/components/schemas/PaymentIntent'}}}}}}}''',
     '''      summary: One page of the payments the provider holds, oldest first. To find one payment, read it by id.
      parameters:
        - {name: limit, in: query, schema: {type: integer, minimum: 1, maximum: 100, default: 20}}
        - {name: starting_after, in: query, schema: {type: string}, description: The id of the last record of the previous page.}
      responses:
        '200': {description: Payment intents, content: {application/json: {schema: {type: object, properties: {payment_intents: {type: array, items: {$ref: '#/components/schemas/PaymentIntent'}}, has_more: {type: boolean, description: True when another page follows.}}}}}}
        '400': {description: limit out of range, or starting_after is not the id of a record}
  /api/payment-intents/{id}:
    get:
      summary: One payment intent by its id (the `pspReference` of the transaction in Core).
      parameters: [{name: id, in: path, required: true, schema: {type: string}}]
      responses:
        '200': {description: The payment intent, content: {application/json: {schema: {$ref: '#/components/schemas/PaymentIntent'}}}}
        '404': {description: No such payment intent}'''),
    ('''      summary: Every refund the provider holds, oldest first.
      responses:
        '200': {description: Refunds, content: {application/json: {schema: {type: object, properties: {refunds: {type: array, items: {$ref: '#/components/schemas/Refund'}}}}}}}''',
     '''      summary: One page of the refunds the provider holds, oldest first.
      parameters:
        - {name: limit, in: query, schema: {type: integer, minimum: 1, maximum: 100, default: 20}}
        - {name: starting_after, in: query, schema: {type: string}, description: The id of the last record of the previous page.}
      responses:
        '200': {description: Refunds, content: {application/json: {schema: {type: object, properties: {refunds: {type: array, items: {$ref: '#/components/schemas/Refund'}}, has_more: {type: boolean}}}}}}
        '400': {description: limit out of range, or starting_after is not the id of a record}'''),
])
derive("services/payments/NOTES.md", [
    ("- `GET /api/payment-intents` and `/api/refunds` show the provider's records, in minor units.",
     "- `GET /api/payment-intents` and `/api/refunds` show the provider's records, in minor units, a page at a time: 20 by\n"
     "  default, 100 at most, oldest first, with `has_more` and `starting_after`. `GET /api/payment-intents/{id}` reads one."),
])

# ======================= SUB-18: a new subscription still finds its card =======================
derive = ticket("SUB-18")
derive("services/subscriptions/src/Clients.cs", [
    ('''        var intents = _http.GetFromJsonAsync<JsonElement>($"{paymentsUrl}/api/payment-intents").GetAwaiter().GetResult().GetProperty("payment_intents");
        return intents.EnumerateArray().Where(i => i.GetProperty("id").GetString() == pspReference)
            .Select(i => i.GetProperty("payment_method").GetString()).FirstOrDefault() ?? SubscriptionsApp.DefaultPaymentMethod;''',
     '''        // One intent by id. The list is paged, so the payment being looked for may not be on its first page.
        var response = _http.GetAsync($"{paymentsUrl}/api/payment-intents/{Uri.EscapeDataString(pspReference)}").GetAwaiter().GetResult();
        if (!response.IsSuccessStatusCode)
            throw new InvalidOperationException($"payments has no payment intent {pspReference} ({(int)response.StatusCode})");   // Core sends the event again
        var intent = response.Content.ReadFromJsonAsync<JsonElement>().GetAwaiter().GetResult();
        return intent.GetProperty("payment_method").GetString() ?? SubscriptionsApp.DefaultPaymentMethod;'''),
])
derive("services/subscriptions/NOTES.md", [
    ("We read that card\n  from the Payments API by the order's `pspReference`; Core does not hold it.",
     "We read that card\n  from the Payments API by the order's `pspReference` (`GET /api/payment-intents/{id}`); Core does not hold it."),
])

# ======================= OPS-9: on-call hears when renewals fail =======================
derive = ticket("OPS-9")
derive("services/ops/prometheus/rules/alerts.rules.yml", [
    ('''          summary: "Customers are not getting emails for {{ $labels.event_type }}"
          runbook: runbooks/emails-missing.md
''', '''          summary: "Customers are not getting emails for {{ $labels.event_type }}"
          runbook: runbooks/emails-missing.md

  - name: subscriptions
    rules:
      - alert: RenewalsFailing
        # The subscriptions app counts every renewal attempt by outcome. A failed renewal is a customer whose card
        # was declined and who loses the subscription after the third failure.
        expr: sum(seedco_renewals_total{outcome="failed"}) > 0
        labels: {severity: ticket}
        annotations:
          summary: "{{ $value }} subscription renewals have failed"
          runbook: runbooks/renewals-failing.md
'''),
])
derive("services/ops/prometheus/rules/alerts_test.yml", [
    ('''            exp_annotations: {summary: "More payments are failing than succeeding", runbook: runbooks/payment-failures.md}
''', '''            exp_annotations: {summary: "More payments are failing than succeeding", runbook: runbooks/payment-failures.md}

  - interval: 1s
    input_series:
      - series: 'seedco_renewals_total{outcome="failed"}'
        values: '0 0 2 2'
      - series: 'seedco_renewals_total{outcome="renewed"}'
        values: '0 5 5 5'
    alert_rule_test:
      - eval_time: 1s
        alertname: RenewalsFailing
        exp_alerts: []                 # renewals ran and none failed
      - eval_time: 3s
        alertname: RenewalsFailing
        exp_alerts:
          - exp_labels: {severity: ticket}
            exp_annotations: {summary: "2 subscription renewals have failed", runbook: runbooks/renewals-failing.md}
'''),
])
NEW_FILES["OPS-9"]["services/ops/runbooks/renewals-failing.md"] = '''# RenewalsFailing

The subscriptions app tried to renew a subscription and the charge failed.

1. One failure is usually one customer's card. The customer is emailed, the renewal is retried three days later,
   and the subscription ends at the third failure. Nothing to do.
2. Many failures in one run are rarely the customers. Check `PaymentFailuresHigh` and the payments app's log.
3. The unpaid renewal order is cancelled in Core. If it was not, it shows in the dashboard as unpaid and must not ship.
'''

# ======================= MOB-8: the app names variants, shipped as release 1.1.0 =======================
derive = ticket("MOB-8")
derive("services/mobile/src/operations.ts", [
    ("lines { quantity variant { id sku product { name } } totalPrice ${TAXED} }", "lines { quantity variant { id sku name product { name } } totalPrice ${TAXED} }"),
    ("lines { productName quantity totalPrice ${TAXED} }", "lines { productName variantName quantity totalPrice ${TAXED} }"),
    ("variants { id sku pricing { price ${TAXED} } }", "variants { id sku name pricing { price ${TAXED} } }"),
])
derive("services/mobile/src/screens.ts", [
    ("const shown = (price: Taxed, displayGross: boolean) => (displayGross ? price.gross : price.net);",
     "const shown = (price: Taxed, displayGross: boolean) => (displayGross ? price.gross : price.net);\n\n"
     "/** What a line is called: the product, and which variant of it when the product has more than one. */\n"
     "export const lineName = (product: string, variant?: string | null) => (variant ? `${product} (${variant})` : product);"),
    ("      variantId: v.id, sku: v.sku, name: e.node.name, price: money(v.pricing.price.net),",
     "      variantId: v.id, sku: v.sku, name: lineName(e.node.name, v.name), price: money(v.pricing.price.net),"),
    ("name: l.productName ?? l.variant.product.name, quantity", "name: lineName(l.productName ?? l.variant.product.name, l.variantName ?? l.variant?.name), quantity"),
])
derive("services/mobile/test/app.test.ts", [
    ('import { money, orderScreen } from "../src/screens.ts";', 'import { lineName, money, orderScreen, productListScreen } from "../src/screens.ts";'),
    ('test("every operation is a single named document", () => {',
     '''test("a product with several variants is named with its variant", () => {
  assert.equal(lineName("Assam Breakfast", "100 g"), "Assam Breakfast (100 g)");
  assert.equal(lineName("Small monthly box", ""), "Small monthly box");
  const list = productListScreen({ products: { edges: [{ node: { id: "p4", name: "Assam Breakfast", variants: [
    { id: "v4", sku: "TEA-ASM-50", name: "50 g", pricing: { price: taxed(7.5, 7.5) } }] } }] } });
  assert.equal(list.products[0].name, "Assam Breakfast (50 g)");
  assert.equal(orderScreen({ ...order, lines: [{ productName: "Assam Breakfast", variantName: "50 g", quantity: 1, totalPrice: taxed(7.5, 8.16) }] }).lines[0].name,
    "Assam Breakfast (50 g)");
});

test("every operation is a single named document", () => {'''),
])
derive("services/mobile/releases/supported.json", [('{"supported": ["1.0.0"]}', '{"supported": ["1.0.0", "1.1.0"]}')])
derive("services/mobile/NOTES.md", [
    ("- Money is Core's `Money`", "- From release 1.1.0 a product with several variants is shown with its variant, as the web shop does:\n  \"Assam Breakfast (100 g)\". Release 1.0.0 shows the product name alone and stays supported.\n- Money is Core's `Money`"),
])


def release_mobile(sol):
    """Release 1.1.0 is the solution's source, frozen, exactly as `./run release 1.1.0` would make it."""
    release = os.path.join(sol, "services", "mobile", "releases", "1.1.0")
    os.makedirs(release)
    for f in ("operations.ts", "screens.ts", "client.ts"):
        src = os.path.join(sol, "services", "mobile", "src", f)
        shutil.copy(src if os.path.isfile(src) else os.path.join(REPO, "services", "mobile", "src", f), os.path.join(release, f))
    # Subscriptions keeps a pinned copy of the Payments API, which PAY-21 changes.
    pinned = os.path.join(sol, "services", "subscriptions", "pinned")
    os.makedirs(pinned, exist_ok=True)
    shutil.copy(os.path.join(sol, "services/payments/contracts/payments-api.yaml"), os.path.join(pinned, "payments-api.yaml"))


build("task01_order_confirmation", ["OPS-7"], ("dashboard", "notifications", "taxes"))
build("task02_release", ["OPS-7", "SHOP-31", "SUP-12", "PAY-21", "SUB-18", "OPS-9", "MOB-8"], ("dashboard", "notifications", "taxes"), release_mobile)
