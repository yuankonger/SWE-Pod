"""Builds task03_payment_incidents from the base services: its starting state (with the faults) and its reference fix.

    python3 tools/derive_incidents.py .

The task starts a week after a release that introduced two fault chains, each modelled on a real one:

- Refunds. Core now asks the payment app again when it does not answer a refund request, as Saleor does, but
  makes a new idempotency key for every attempt. The payment app keeps a ledger of refund requests beside the
  provider's records, written after the provider call and keyed so that a second refund of the same amount on
  one transaction collides. The app then fails after the provider has paid, Core asks again, and the provider
  pays again. (Saleor's Stripe app: duplicate refunds on redelivery, fixed by forwarding Core's idempotency key;
  an orphaned provider record after a failed store write, saleor/apps #2208.)
- Renewals. When a scheduled plan change takes effect, the renewal run now puts a note on the renewal order for
  the warehouse. It takes the plan's name from a field it has just cleared, and Core refuses the empty value.
  That happens after the charge and before the subscription is saved, so the customer gets a new paid order on
  every run and every subscription after theirs is not renewed. The owner's tests use a stand-in for Core that
  accepts anything, so they pass. (WooCommerce
  Subscriptions' plan-switch incident of April 2026; Kill Bill's payment-then-state ordering bugs.)

Both are written as exact edits of the base files, so this fails loudly when a base file changes under it.
`RELEASE` turns a base file into the faulty one; `FIX` turns the faulty one into the reference solution.
Never copy this file or its output `solution/` into an agent's workspace.
"""
import os
import shutil
import sys

REPO = os.path.abspath(sys.argv[1])
TASK = os.path.join(REPO, "tasks", "task03_payment_incidents")

CORE_OLD = '''        self._add_event(t, "REFUND_REQUEST", wanted)
        try:
            answer = self.apps.sync(app, "TRANSACTION_REFUND_REQUESTED", "TransactionRefundRequested", {
                "transaction": self.transaction_view(t), "idempotencyKey": str(uuid.uuid4()),
                "action": {"actionType": "REFUND", "amount": float(wanted), "currency": CURRENCY}})
            result = answer.get("result")
'''
CORE_RELEASED = '''        self._add_event(t, "REFUND_REQUEST", wanted)
        try:
            answer, attempt = None, 0
            while answer is None:       # the payment app may be restarting: ask again before giving up
                attempt += 1
                try:
                    answer = self.apps.sync(app, "TRANSACTION_REFUND_REQUESTED", "TransactionRefundRequested", {
                        "transaction": self.transaction_view(t), "idempotencyKey": str(uuid.uuid4()),
                        "action": {"actionType": "REFUND", "amount": float(wanted), "currency": CURRENCY}})
                except WebhookError as exc:
                    if attempt >= REFUND_REQUEST_ATTEMPTS:
                        raise
                    telemetry.log("warning", "refund request sent again", attempt=attempt, reason=str(exc),
                                  **{"saleor.app.identifier": t["app"]})
                    time.sleep(0.2 * attempt)
            result = answer.get("result")
'''
CORE_FIXED = CORE_RELEASED.replace('''            answer, attempt = None, 0
''', '''            answer, attempt, key = None, 0, str(uuid.uuid4())      # one key for the request, however often it is sent
''').replace('''"idempotencyKey": str(uuid.uuid4()),
                        "action"''', '''"idempotencyKey": key,
                        "action"''')

CORE_NOTE_OLD = '''- Cancelling an order does not refund it. A refund is a separate request to the payment app.
'''
CORE_NOTE_RELEASED = CORE_NOTE_OLD + '''- Since release 2026.11 a refund request that the payment app does not answer is sent again, three times in all,
  before the refund is recorded as failed. Saleor does the same with its transaction request webhooks.
'''
CORE_NOTE_FIXED = CORE_NOTE_RELEASED + '''  Every attempt carries the same `idempotencyKey`: the app must be able to tell a repeat from a new request.
'''

RELEASE = {
    "core/src/core.py": [
        (CORE_OLD, CORE_RELEASED),
        ('''import uuid
''', '''import time
import uuid
'''),
        ('''class ApiError(''', '''REFUND_REQUEST_ATTEMPTS = 3     # how often a refund request is sent to a payment app that does not answer


class ApiError('''),
    ],
    "core/NOTES.md": [(CORE_NOTE_OLD, CORE_NOTE_RELEASED)],
    "payments/src/Payments.cs": [
        ('''public record ProviderRefund(string Id, string PaymentIntent, long Amount, string CreatedAt);
''', '''public record ProviderRefund(string Id, string PaymentIntent, long Amount, string CreatedAt);
/// <summary>What Core asked for, beside what the provider did: one row per refund request, for reconciliation.</summary>
public record RefundRequest(string Transaction, string PaymentIntent, long Amount, string Refund, string CreatedAt);
'''),
        ('''    public PaymentIntent? Intent(string id) => store.Get<PaymentIntent>("payment_intents", id);
''', '''    public PaymentIntent? Intent(string id) => store.Get<PaymentIntent>("payment_intents", id);
    public IReadOnlyList<RefundRequest> RefundRequests() => store.List<RefundRequest>("refund_requests");

    /// <summary>Notes a refund request in the ledger. A request is known by its transaction and its amount.</summary>
    public void Record(string transaction, ProviderRefund refund) =>
        store.Add("refund_requests", $"{transaction}:{refund.Amount}", refund.PaymentIntent,
            new RefundRequest(transaction, refund.PaymentIntent, refund.Amount, refund.Id, refund.CreatedAt));
'''),
        ('''            var refund = provider.Refund(intentId, Currencies.ToProvider(amount, currency));
            return new TransactionResponse(''', '''            var refund = provider.Refund(intentId, Currencies.ToProvider(amount, currency));
            provider.Record(Need(payload.Transaction!.Id, "transaction.id"), refund);
            return new TransactionResponse('''),
    ],
    "payments/src/Store.cs": [
        ('''    public T? Get<T>(string table, string id) where T : class =>''', '''    /// <summary>Writes a new record. The id must not be in the table yet.</summary>
    public void Add<T>(string table, string id, string? lookup, T record) =>
        Run($"INSERT INTO {table} (id, lookup, body) VALUES ($0, $1, $2)", id, lookup, JsonSerializer.Serialize(record, Json));

    public T? Get<T>(string table, string id) where T : class =>'''),
    ],
    "payments/src/Program.cs": [
        ('''var store = new Store(Store.DefaultPath("payments.db"), "payment_intents", "refunds");''',
         '''var store = new Store(Store.DefaultPath("payments.db"), "payment_intents", "refunds", "refund_requests");'''),
        ('''app.MapGet("/api/refunds", () => Results.Json(new { refunds = provider.Refunds() }, Store.Json));
''', '''app.MapGet("/api/refunds", () => Results.Json(new { refunds = provider.Refunds() }, Store.Json));
app.MapGet("/api/refund-requests", () => Results.Json(new { refund_requests = provider.RefundRequests() }, Store.Json));
'''),
    ],
    "payments/tests/PaymentsTests.cs": [
        ('''        var store = new Store(path, "payment_intents", "refunds");''', '''        var store = new Store(path, "payment_intents", "refunds", "refund_requests");'''),
    ],
    "payments/NOTES.md": [
        ('''- `GET /api/payment-intents` and `/api/refunds` show the provider's records, in minor units.
''', '''- `GET /api/payment-intents` and `/api/refunds` show the provider's records, in minor units.
- Since release 2026.11 we keep a ledger of the refund requests Core sent us (`refund_requests`,
  `GET /api/refund-requests`), so finance can set what was asked for beside what the provider paid.
'''),
    ],
    "subscriptions/src/Subscriptions.cs": [
        ('''                if (billed.Paid)
                {
                    var start = Day(s.CurrentPeriodEnd);
''', '''                if (billed.Paid)
                {
                    if (current.PendingSku is not null)     // the box changes with this order: tell the warehouse which one to pack
                        commerce.Annotate(billed.OrderId, "subscription_plan_change", s.PendingName);
                    var start = Day(s.CurrentPeriodEnd);
'''),
        ('''    Billed Bill(Subscription s, string sku, int qty, decimal unitPrice, string reason, string idempotencyKey);
''', '''    Billed Bill(Subscription s, string sku, int qty, decimal unitPrice, string reason, string idempotencyKey);

    /// <summary>Puts a note on an order in Core, for the people who pack it.</summary>
    void Annotate(string orderId, string key, string? value);
'''),
    ],
    "subscriptions/src/Clients.cs": [
        ('''        return new Billed(orderId, false, total, payment.GetProperty("message").GetString() is { Length: > 0 } m ? m : "payment_failed");
    }
''', '''        return new Billed(orderId, false, total, payment.GetProperty("message").GetString() is { Length: > 0 } m ? m : "payment_failed");
    }

    public void Annotate(string orderId, string key, string? value) =>
        Mutate("updateMetadata", "mutation($id: ID!, $input: [MetadataInput!]!) { updateMetadata(id: $id, input: $input) { errors { code message } } }",
            new { id = orderId, input = new[] { new { key, value } } });
'''),
    ],
    "subscriptions/tests/SubscriptionsTests.cs": [
        ('''        public string PaymentMethodOf(string pspReference) => CardOnFile;
''', '''        public string PaymentMethodOf(string pspReference) => CardOnFile;
        public List<(string Order, string Key, string? Value)> Notes = new();
        public void Annotate(string orderId, string key, string? value) => Notes.Add((orderId, key, value));
'''),
    ],
    "subscriptions/NOTES.md": [
        (None, '''- Since release 2026.11, when a scheduled plan change takes effect the renewal order carries the metadata
  `subscription_plan_change` with the new plan's name, so the warehouse packs the right box.
'''),
    ],
}

FIX = {
    "core/src/core.py": [(CORE_RELEASED, CORE_FIXED)],
    "core/NOTES.md": [(CORE_NOTE_RELEASED, CORE_NOTE_FIXED)],
    "payments/graphql/transaction-refund-requested.graphql": [
        ('''      action { amount currency actionType }
      transaction { id pspReference }
''', '''      action { amount currency actionType }
      transaction { id pspReference }
      idempotencyKey
'''),
    ],
    "payments/src/Payments.cs": [
        ('''public record RefundPayload(ActionPayload? Action, TransactionPayload? Transaction);''',
         '''public record RefundPayload(ActionPayload? Action, TransactionPayload? Transaction, string? IdempotencyKey = null);'''),
        ('''    /// <summary>Notes a refund request in the ledger. A request is known by its transaction and its amount.</summary>
    public void Record(string transaction, ProviderRefund refund) =>
        store.Add("refund_requests", $"{transaction}:{refund.Amount}", refund.PaymentIntent,
            new RefundRequest(transaction, refund.PaymentIntent, refund.Amount, refund.Id, refund.CreatedAt));
''', '''    private readonly object _refunds = new();

    /// <summary>
    /// Refunds once per request. A request is known by Core's idempotency key, which Core repeats when it sends the
    /// same request again: a repeat returns the refund made the first time. The ledger row is written with the
    /// refund, under the same lock, so the provider never holds a refund the ledger does not know.
    /// </summary>
    public ProviderRefund RefundOnce(string key, string transaction, string intentId, long amount)
    {
        lock (_refunds)
        {
            var earlier = store.Get<RefundRequest>("refund_requests", key);
            if (earlier is not null) return Refunds(earlier.PaymentIntent).First(r => r.Id == earlier.Refund);
            var refund = Refund(intentId, amount);
            store.Put("refund_requests", key, refund.PaymentIntent, new RefundRequest(transaction, refund.PaymentIntent, refund.Amount, refund.Id, refund.CreatedAt));
            return refund;
        }
    }
'''),
        ('''            var refund = provider.Refund(intentId, Currencies.ToProvider(amount, currency));
            provider.Record(Need(payload.Transaction!.Id, "transaction.id"), refund);
''', '''            var refund = provider.RefundOnce(Need(payload.IdempotencyKey, "idempotencyKey"), payload.Transaction!.Id ?? "",
                intentId, Currencies.ToProvider(amount, currency));
'''),
    ],
    "payments/tests/PaymentsTests.cs": [
        ('''        RefundPayload Refund(decimal amount) => new(new ActionPayload(amount, "USD", "REFUND"), new TransactionPayload("VHJhbnNhY3Rpb246MQ==", paid.PspReference));''',
         '''        RefundPayload Refund(decimal amount) => new(new ActionPayload(amount, "USD", "REFUND"), new TransactionPayload("VHJhbnNhY3Rpb246MQ==", paid.PspReference), Guid.NewGuid().ToString());'''),
        ('''new RefundPayload(new ActionPayload(1m, "USD", "REFUND"), new TransactionPayload("x", null))''',
         '''new RefundPayload(new ActionPayload(1m, "USD", "REFUND"), new TransactionPayload("x", null), "k")'''),
    ],
    "payments/NOTES.md": [
        ('''  `GET /api/refund-requests`), so finance can set what was asked for beside what the provider paid.
''', '''  `GET /api/refund-requests`), so finance can set what was asked for beside what the provider paid.
- A refund request is known by Core's `idempotencyKey`. Core sends a request again when we do not answer, with
  the same key, and we answer a repeat with the refund we made the first time.
'''),
    ],
    "subscriptions/src/Subscriptions.cs": [
        ('''                if (billed.Paid)
                {
                    if (current.PendingSku is not null)     // the box changes with this order: tell the warehouse which one to pack
                        commerce.Annotate(billed.OrderId, "subscription_plan_change", s.PendingName);
                    var start = Day(s.CurrentPeriodEnd);
                    Save(s with { Status = "active", CurrentPeriodStart = Text(start), CurrentPeriodEnd = Text(start.AddMonths(1)), FailedAttempts = 0, NextAttempt = null });
''', '''                if (billed.Paid)
                {
                    // The charge is taken: the new period is saved before anything else is done, so that nothing
                    // that goes wrong afterwards can leave a paid subscription due again.
                    var start = Day(s.CurrentPeriodEnd);
                    Save(s with { Status = "active", CurrentPeriodStart = Text(start), CurrentPeriodEnd = Text(start.AddMonths(1)), FailedAttempts = 0, NextAttempt = null });
                    if (current.PendingSku is not null)     // the box changes with this order: tell the warehouse which one to pack
                        commerce.Annotate(billed.OrderId, "subscription_plan_change", s.Name);
'''),
    ],
    "subscriptions/tests/SubscriptionsTests.cs": [
        ('''        Assert.Equal(0, app.RunRenewals("2026-02-01").Renewed);                 // running twice on one day renews once
''', '''        Assert.Equal(0, app.RunRenewals("2026-02-01").Renewed);                 // running twice on one day renews once
        Assert.Equal(("subscription_plan_change", "Small monthly box"), (commerce.Notes.Single().Key, commerce.Notes.Single().Value));
'''),
    ],
}


def apply(text: str, edits: list, rel: str) -> str:
    for old, new in edits:
        if old is None:         # something added at the end of the file
            text = text.rstrip("\n") + "\n" + new
            continue
        if text.count(old) != 1:
            raise SystemExit("{}: expected this once, found it {} times:\n{}".format(rel, text.count(old), old[:300]))
        text = text.replace(old, new)
    return text


def write(root: str, rel: str, text: str):
    path = os.path.join(root, "services", rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


for part in ("overlay", "solution"):
    shutil.rmtree(os.path.join(TASK, part), ignore_errors=True)
released = {}
for rel, edits in RELEASE.items():
    with open(os.path.join(REPO, "services", rel)) as f:
        released[rel] = apply(f.read(), edits, rel)
    if edits:
        write(os.path.join(TASK, "overlay"), rel, released[rel])
for rel, edits in FIX.items():
    if rel not in released:
        with open(os.path.join(REPO, "services", rel)) as f:
            released[rel] = f.read()
    write(os.path.join(TASK, "solution"), rel, apply(released[rel], edits, rel))
# The list finance asked for is part of the reference fix. It follows from the task's history, so it is worked out
# from the seed by the function the verifier itself uses, and can only be written once the seed has been built.
seed = os.path.join(TASK, "seed")
report = "no over-refund report (build the seed, then run this again)"
if os.path.isdir(seed):
    import importlib.util
    spec = importlib.util.spec_from_file_location("incident_checks", os.path.join(TASK, "hidden", "incident_checks.py"))
    checks = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checks)
    over = checks.over_refunds(seed)
    write(os.path.join(TASK, "solution"), "payments/docs/over-refunds.csv",
          "order_number,overpaid\n" + "".join("{},{:.2f}\n".format(n, a) for n, a in sorted(over.items(), key=lambda x: int(x[0]))))
    report = "over-refund report for orders {}".format(", ".join(sorted(over, key=int)))
print("task03_payment_incidents: {} files in the starting state, {} in the reference fix; {}".format(
    sum(1 for e in RELEASE.values() if e), len(FIX), report))
