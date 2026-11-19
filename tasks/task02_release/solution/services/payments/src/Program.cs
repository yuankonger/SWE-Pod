using System.Collections.Concurrent;
using System.Text;
using System.Text.Json;
using Seedco.Payments;

var port = Environment.GetEnvironmentVariable("PORT") ?? "7003";
var appUrl = Environment.GetEnvironmentVariable("APP_URL") ?? $"http://127.0.0.1:{port}";
var graphql = Environment.GetEnvironmentVariable("SEEDCO_GRAPHQL_DIR") ?? "graphql";

var builder = WebApplication.CreateBuilder(args);
builder.Logging.ClearProviders();
var store = new Store(Store.DefaultPath("payments.db"), "payment_intents", "refunds");
var provider = new Provider(store);
var payments = new PaymentsApp(provider);
var app = builder.Build();
// BIND is the address to listen on: this machine only by default, 0.0.0.0 when each service has its own container
app.Urls.Add($"http://{Environment.GetEnvironmentVariable("BIND") ?? "127.0.0.1"}:{port}");

// Core's payloads and answers are camelCase; the provider's own records are snake_case.
var wire = new JsonSerializerOptions { PropertyNamingPolicy = JsonNamingPolicy.CamelCase, PropertyNameCaseInsensitive = true };

async Task<IResult> Webhook<T>(HttpRequest http, string route, Func<T, TransactionResponse> handle)
{
    try
    {
        var payload = await JsonSerializer.DeserializeAsync<T>(http.Body, wire) ?? throw new MalformedRequest("the payload is empty");
        var answer = handle(payload);
        Telemetry.Count("seedco_payment_results_total", ("result", answer.Result));
        if (answer.Result.EndsWith("FAILURE")) Telemetry.Log("warning", $"{route}: {answer.Result} {answer.Message}");
        return Results.Json(answer, wire);
    }
    catch (Exception e) when (e is MalformedRequest or JsonException)
    {
        Telemetry.Log("error", $"{route}: malformed request: {e.Message}");
        return Results.Json(new { error = "malformed_request", message = e.Message }, wire, statusCode: 400);
    }
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
    id = "seedco.payments",
    name = "Payments",
    version = "1.0.0",
    permissions = new[] { "HANDLE_PAYMENTS" },
    tokenTargetUrl = $"{appUrl}/api/register",
    webhooks = new object[]
    {
        new { name = "transaction-initialize-session", syncEvents = new[] { "TRANSACTION_INITIALIZE_SESSION" },
              query = File.ReadAllText(Path.Combine(graphql, "transaction-initialize-session.graphql")),
              targetUrl = $"{appUrl}/api/webhooks/saleor/transaction-initialize-session" },
        new { name = "transaction-refund-requested", syncEvents = new[] { "TRANSACTION_REFUND_REQUESTED" },
              query = File.ReadAllText(Path.Combine(graphql, "transaction-refund-requested.graphql")),
              targetUrl = $"{appUrl}/api/webhooks/saleor/transaction-refund-requested" },
    },
}, wire));
app.MapPost("/api/register", async (HttpRequest http) =>
{
    var body = await JsonSerializer.DeserializeAsync<JsonElement>(http.Body);
    store.SetSetting("auth_token", body.GetProperty("auth_token").GetString()!);
    return Results.Json(new { success = true });
});
app.MapPost("/api/webhooks/saleor/transaction-initialize-session", (HttpRequest http) =>
    Webhook<InitializePayload>(http, "transaction-initialize-session", payments.Initialize));
app.MapPost("/api/webhooks/saleor/transaction-refund-requested", (HttpRequest http) =>
    Webhook<RefundPayload>(http, "transaction-refund-requested", payments.Refund));
// The provider's records, for reconciliation: what was actually charged and refunded, in minor units.
// The lists are paged (PAY-21). To find one payment, read it by id: it may not be on the first page.
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
app.MapGet("/api/refunds", (int? limit, string? starting_after) => Paged(provider.Refunds(), r => r.Id, "refunds", limit, starting_after));
Telemetry.Log("info", $"payments listening on {port}");
app.Run();

/// <summary>Counters in the Prometheus text format, and one JSON object per log line.</summary>
public static class Telemetry
{
    private static readonly ConcurrentDictionary<string, long> Counters = new();

    public static void Count(string name, params (string Key, string Value)[] labels) =>
        Counters.AddOrUpdate(name + "{" + string.Join(",", labels.Select(l => $"{l.Key}=\"{l.Value}\"")) + "}", 1, (_, n) => n + 1);

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
        Console.WriteLine(JsonSerializer.Serialize(new { timestamp = DateTime.UtcNow.ToString("o"), level, service = "payments", message }));
}
