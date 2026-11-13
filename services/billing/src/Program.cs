using System.Net.Http.Json;
using System.Text.Json;
using Seedco.Billing;

var port = Environment.GetEnvironmentVariable("PORT") ?? "7003";
var brokerUrl = Environment.GetEnvironmentVariable("BROKER_URL") ?? "http://127.0.0.1:7000";

var builder = WebApplication.CreateBuilder(args);
builder.Logging.ClearProviders();
builder.Services.ConfigureHttpJsonOptions(o => o.SerializerOptions.PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower);
builder.Services.AddSingleton<IEventPublisher>(new HttpPublisher(brokerUrl));
builder.Services.AddSingleton<BillingService>();
builder.Services.AddHostedService(sp => new OrdersConsumer(sp.GetRequiredService<BillingService>(), brokerUrl));
var app = builder.Build();
app.Urls.Add($"http://127.0.0.1:{port}");

static IResult Guard(Func<object> f)
{
    try { return Results.Json(f(), Json.Options); }
    catch (BillingException e) { return Results.Json(new { error = "bad_request", message = e.Message }, Json.Options, statusCode: 400); }
}

app.MapGet("/health", () => Results.Json(new { ok = true }));
app.MapPost("/quotes", (QuoteRequest req, BillingService b) => Guard(() => b.Quote(req)));
app.MapPost("/charges", (ChargeRequest req, BillingService b) => Guard(() => b.Charge(req)));
app.MapGet("/invoices", (string? order_id, BillingService b) => Guard(() => new { invoices = b.Invoices(order_id) }));
Console.WriteLine($"billing listening on {port}");
app.Run();

public static class Json
{
    public static readonly JsonSerializerOptions Options = new() { PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower };
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

/// <summary>Polls the orders topic from the start of the log and hands each event to Billing.</summary>
public class OrdersConsumer(BillingService billing, string brokerUrl) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stop)
    {
        using var http = new HttpClient();
        var offset = 0;
        while (!stop.IsCancellationRequested)
        {
            try
            {
                var page = await http.GetFromJsonAsync<JsonElement>($"{brokerUrl}/topics/{BillingService.OrdersTopic}?offset={offset}", stop);
                foreach (var e in page.GetProperty("events").EnumerateArray())
                {
                    try { billing.Handle(e); }
                    catch (Exception ex) { Console.Error.WriteLine($"billing: dropped an event it could not read: {ex.Message}"); }
                }
                offset = page.GetProperty("next_offset").GetInt32();
            }
            catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException or JsonException) { }
            await Task.Delay(100, stop).ContinueWith(_ => { });
        }
    }
}
