using System.Net.Http.Json;
using System.Text.Json;
using Seedco.Billing;

var port = Environment.GetEnvironmentVariable("PORT") ?? "7003";
var brokerUrl = Environment.GetEnvironmentVariable("BROKER_URL") ?? "http://127.0.0.1:7000";

var builder = WebApplication.CreateBuilder(args);
builder.Logging.ClearProviders();
builder.Services.ConfigureHttpJsonOptions(o => o.SerializerOptions.PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower);
var billing = new BillingService(new HttpPublisher(brokerUrl), new Store(Store.DefaultPath()));
builder.Services.AddSingleton(billing);
builder.Services.AddHostedService(_ => new OrdersConsumer(billing, brokerUrl));
var app = builder.Build();
app.Urls.Add($"http://127.0.0.1:{port}");

static IResult Guard(Func<object> f)
{
    static IResult Error(int status, string error, string message) => Results.Json(new { error, message }, Json.Options, statusCode: status);
    try { return Results.Json(f(), Json.Options); }
    catch (BillingException e) { return Error(400, "bad_request", e.Message); }
    catch (PaymentDeclined e) { return Error(402, "payment_declined", e.Message); }
    catch (NotFound e) { return Error(404, "not_found", e.Message); }
    catch (IdempotencyConflict e) { return Error(409, "idempotency_conflict", e.Message); }
}

app.MapGet("/health", () => Results.Json(new { ok = true }));
app.MapPost("/quotes", (QuoteRequest req, BillingService b) => Guard(() => b.Quote(req)));
app.MapPost("/charges", (ChargeRequest req, HttpRequest http, BillingService b) =>
    Guard(() => b.Charge(req, http.Headers.TryGetValue("Idempotency-Key", out var key) ? key.ToString() : null)));
app.MapGet("/payments", (string? order_id, BillingService b) => Guard(() => new { payments = b.Payments(order_id) }));
app.MapGet("/refunds", (string? order_id, BillingService b) => Guard(() => new { refunds = b.Refunds(order_id) }));
app.MapGet("/invoices", (string? order_id, string? customer_id, BillingService b) => Guard(() => new { invoices = b.Invoices(order_id, customer_id) }));
app.MapGet("/plans", () => Results.Json(new { plans = BillingService.Plans.Values }, Json.Options));
app.MapGet("/subscriptions", (string? customer_id, BillingService b) => Guard(() => new { subscriptions = b.Subscriptions(customer_id) }));
app.MapPost("/subscriptions/{id}/plan", (string id, ChangePlanRequest req, BillingService b) => Guard(() => b.ChangePlan(id, req)));
app.MapPost("/subscriptions/{id}/cancel", (string id, BillingService b) => Guard(() => b.Cancel(id)));
app.MapPut("/customers/{id}/payment-method", (string id, PaymentMethodRequest req, BillingService b) =>
    Guard(() => new { subscriptions = b.SetPaymentMethod(id, req.PaymentMethod) }));
app.MapPost("/renewals/run", (RenewalRequest req, BillingService b) => Guard(() => b.RunRenewals(req.AsOf)));
Console.WriteLine($"billing listening on {port}");
app.Run();

public static class Json
{
    public static readonly JsonSerializerOptions Options = Store.Json;
}

public class HttpPublisher(string brokerUrl) : IEventPublisher
{
    private readonly HttpClient _http = new();

    public void Publish(string topic, object envelope)
    {
        // A string body, so the request carries a Content-Length (the broker does not read chunked bodies).
        var body = new StringContent(JsonSerializer.Serialize(envelope, Json.Options), System.Text.Encoding.UTF8, "application/json");
        _http.PostAsync($"{brokerUrl}/topics/{topic}", body).GetAwaiter().GetResult().EnsureSuccessStatusCode();
    }
}

/// <summary>Polls the orders topic from the offset Billing last stored and hands each event to Billing.</summary>
public class OrdersConsumer(BillingService billing, string brokerUrl) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stop)
    {
        using var http = new HttpClient();
        while (!stop.IsCancellationRequested)
        {
            try
            {
                var offset = billing.Store.Offset(BillingService.OrdersTopic);
                var page = await http.GetFromJsonAsync<JsonElement>($"{brokerUrl}/topics/{BillingService.OrdersTopic}?offset={offset}", stop);
                foreach (var e in page.GetProperty("events").EnumerateArray())
                {
                    try { billing.Handle(e); }
                    catch (Exception ex) { Console.Error.WriteLine($"billing: dropped an event it could not read: {ex.Message}"); }
                }
                var next = page.GetProperty("next_offset").GetInt32();
                if (next != offset) billing.Store.SetOffset(BillingService.OrdersTopic, next);
            }
            catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException or JsonException) { }
            await Task.Delay(100, stop).ContinueWith(_ => { });
        }
    }
}
