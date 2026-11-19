using System.Collections.Concurrent;
using System.Text;
using System.Text.Json;
using Seedco.Subscriptions;

var port = Environment.GetEnvironmentVariable("PORT") ?? "7006";
var appUrl = Environment.GetEnvironmentVariable("APP_URL") ?? $"http://127.0.0.1:{port}";
var coreUrl = Environment.GetEnvironmentVariable("CORE_URL") ?? "http://127.0.0.1:7000/graphql/";
var paymentsUrl = Environment.GetEnvironmentVariable("PAYMENTS_URL") ?? "http://127.0.0.1:7003";
var notificationsUrl = Environment.GetEnvironmentVariable("NOTIFICATIONS_URL") ?? "http://127.0.0.1:7005";
var graphql = Environment.GetEnvironmentVariable("SEEDCO_GRAPHQL_DIR") ?? "graphql";

var builder = WebApplication.CreateBuilder(args);
builder.Logging.ClearProviders();
var store = new Store(Store.DefaultPath("subscriptions.db"), "subscriptions");
var subscriptions = new SubscriptionsApp(store, new Commerce(coreUrl, paymentsUrl, () => store.Setting("auth_token")), new Notifier(notificationsUrl));
var app = builder.Build();
// BIND is the address to listen on: this machine only by default, 0.0.0.0 when each service has its own container
app.Urls.Add($"http://{Environment.GetEnvironmentVariable("BIND") ?? "127.0.0.1"}:{port}");

static IResult Guard(Func<object> f)
{
    static IResult Error(int status, string error, string message) => Results.Json(new { error, message }, Store.Json, statusCode: status);
    try { return Results.Json(f(), Store.Json); }
    catch (BadRequest e) { return Error(400, "bad_request", e.Message); }
    catch (PaymentDeclined e) { return Error(402, "payment_declined", e.Message); }
    catch (NotFound e) { return Error(404, "not_found", e.Message); }
    catch (InvalidOperationException e)
    {
        Telemetry.Log("error", "core or payments failed: " + e.Message);
        return Error(502, "upstream_failed", e.Message);
    }
}

async Task<T> Body<T>(HttpRequest http) where T : class
{
    try { return await JsonSerializer.DeserializeAsync<T>(http.Body, Store.Json) ?? throw new BadRequest("a JSON body is required"); }
    catch (JsonException e) { throw new BadRequest("invalid JSON: " + e.Message); }
}

app.Use(async (context, next) =>
{
    await next();
    Telemetry.Count("http_server_request_count_total", ("http_route", context.Request.Path), ("http_response_status_code", context.Response.StatusCode.ToString()));
});
app.MapGet("/health", () => Results.Json(new { ok = true }));
app.MapGet("/metrics", () => Results.Text(Telemetry.Render(), "text/plain; version=0.0.4"));
app.MapGet("/api/manifest", () => Results.Json(new
{
    id = "seedco.subscriptions",
    name = "Subscriptions",
    version = "1.0.0",
    permissions = new[] { "MANAGE_ORDERS", "HANDLE_PAYMENTS" },
    tokenTargetUrl = $"{appUrl}/api/register",
    webhooks = new object[]
    {
        new { name = "order-events", asyncEvents = new[] { "ORDER_FULLY_PAID", "ORDER_CANCELLED" },
              query = File.ReadAllText(Path.Combine(graphql, "order-events.graphql")), targetUrl = $"{appUrl}/api/webhooks/order-events" },
    },
}));
app.MapPost("/api/register", async (HttpRequest http) =>
{
    var body = await JsonSerializer.DeserializeAsync<JsonElement>(http.Body);
    store.SetSetting("auth_token", body.GetProperty("auth_token").GetString()!);
    return Results.Json(new { success = true });
});
app.MapPost("/api/webhooks/order-events", async (HttpRequest http) =>
{
    try
    {
        var started = subscriptions.Handle(await JsonSerializer.DeserializeAsync<JsonElement>(http.Body));
        foreach (var s in started) Telemetry.Count("seedco_subscriptions_started_total", ("sku", s.Sku));
        return Results.Json(new { success = true });
    }
    catch (Exception e) when (e is KeyNotFoundException or InvalidOperationException or JsonException or HttpRequestException)
    {
        // 500 so that Core delivers the event again: a subscription must not be lost to a payload we could not read once.
        Telemetry.Log("error", "an order event could not be handled: " + e.Message);
        return Results.Json(new { error = "unhandled", message = e.Message }, statusCode: 500);
    }
});
app.MapGet("/api/plans", () => Results.Json(new { plans = SubscriptionsApp.Plans.Values }, Store.Json));
app.MapGet("/api/subscriptions", (string? email) => Guard(() => new { subscriptions = subscriptions.Subscriptions(email) }));
app.MapPost("/api/subscriptions/{id}/plan", async (string id, HttpRequest http) =>
{
    ChangePlanRequest req;
    try { req = await Body<ChangePlanRequest>(http); } catch (BadRequest e) { return Guard(() => throw e); }
    return Guard(() => subscriptions.ChangePlan(id, req));
});
app.MapPost("/api/subscriptions/{id}/cancel", (string id) => Guard(() => subscriptions.Cancel(id)));
app.MapPut("/api/customers/payment-method", async (HttpRequest http) =>
{
    PaymentMethodRequest req;
    try { req = await Body<PaymentMethodRequest>(http); } catch (BadRequest e) { return Guard(() => throw e); }
    return Guard(() => new { subscriptions = subscriptions.SetPaymentMethod(req) });
});
app.MapPost("/api/renewals/run", async (HttpRequest http) =>
{
    RenewalRequest req;
    try { req = await Body<RenewalRequest>(http); } catch (BadRequest e) { return Guard(() => throw e); }
    return Guard(() =>
    {
        var run = subscriptions.RunRenewals(req.AsOf);
        Telemetry.Count("seedco_renewals_total", ("outcome", "renewed"), run.Renewed);
        Telemetry.Count("seedco_renewals_total", ("outcome", "failed"), run.Failed);
        return run;
    });
});
Telemetry.Log("info", $"subscriptions listening on {port}");
app.Run();

/// <summary>Counters in the Prometheus text format, and one JSON object per log line.</summary>
public static class Telemetry
{
    private static readonly ConcurrentDictionary<string, long> Counters = new();

    public static void Count(string name, params (string Key, string Value)[] labels) => Add(name, 1, labels);
    public static void Count(string name, (string Key, string Value) label, long amount) => Add(name, amount, label);

    private static void Add(string name, long amount, params (string Key, string Value)[] labels) =>
        Counters.AddOrUpdate(name + "{" + string.Join(",", labels.Select(l => $"{l.Key}=\"{l.Value}\"")) + "}", amount, (_, n) => n + amount);

    public static string Render()
    {
        var text = new StringBuilder();
        foreach (var group in Counters.OrderBy(c => c.Key).GroupBy(c => c.Key[..c.Key.IndexOf('{')]))
        {
            text.Append($"# TYPE {group.Key} counter\n");
            foreach (var c in group) text.Append($"{c.Key} {c.Value}\n");
        }
        return text.ToString();
    }

    public static void Log(string level, string message) =>
        Console.WriteLine(JsonSerializer.Serialize(new { timestamp = DateTime.UtcNow.ToString("o"), level, service = "subscriptions", message }));
}
