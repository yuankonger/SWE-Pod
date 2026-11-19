using System.Net.Http.Json;
using System.Text;
using System.Text.Json;

namespace Seedco.Subscriptions;

/// <summary>Core over GraphQL and the payments app over HTTP. The token is the one Core gave this app when it installed it.</summary>
public class Commerce(string coreUrl, string paymentsUrl, Func<string?> token) : ICommerce
{
    public const string PaymentGateway = "seedco.payments";
    private readonly HttpClient _http = new() { Timeout = TimeSpan.FromSeconds(60) };
    private Dictionary<string, string>? _variants;

    /// <summary>Runs one GraphQL operation and returns `data`. A top-level error is an exception.</summary>
    private JsonElement Gql(string query, object variables)
    {
        var request = new HttpRequestMessage(HttpMethod.Post, coreUrl)
        {
            Content = new StringContent(JsonSerializer.Serialize(new { query, variables }), Encoding.UTF8, "application/json"),
        };
        request.Headers.Add("Authorization", "Bearer " + (token() ?? throw new InvalidOperationException("Core has not installed this app yet")));
        var body = _http.Send(request).Content.ReadFromJsonAsync<JsonElement>().GetAwaiter().GetResult();
        if (body.TryGetProperty("errors", out var errors) && errors.GetArrayLength() > 0)
            throw new InvalidOperationException("core: " + errors[0].GetProperty("message").GetString());
        return body.GetProperty("data");
    }

    /// <summary>The result of a mutation, or an exception carrying what the mutation refused.</summary>
    private JsonElement Mutate(string name, string query, object variables)
    {
        var result = Gql(query, variables).GetProperty(name);
        var errors = result.GetProperty("errors");
        if (errors.GetArrayLength() > 0)
            throw new InvalidOperationException($"core refused {name}: {errors[0].GetProperty("code").GetString()} {errors[0].GetProperty("message").GetString()}");
        return result;
    }

    private string VariantId(string sku)
    {
        _variants ??= Gql("{ products(first: 100) { edges { node { variants { id sku } } } } }", new { })
            .GetProperty("products").GetProperty("edges").EnumerateArray()
            .SelectMany(e => e.GetProperty("node").GetProperty("variants").EnumerateArray())
            .Where(v => v.GetProperty("sku").ValueKind == JsonValueKind.String)     // a variant may have no SKU
            .ToDictionary(v => v.GetProperty("sku").GetString()!, v => v.GetProperty("id").GetString()!);
        return _variants.TryGetValue(sku, out var id) ? id : throw new InvalidOperationException("Core has no product with sku " + sku);
    }

    public string PaymentMethodOf(string pspReference)
    {
        var intents = _http.GetFromJsonAsync<JsonElement>($"{paymentsUrl}/api/payment-intents").GetAwaiter().GetResult().GetProperty("payment_intents");
        return intents.EnumerateArray().Where(i => i.GetProperty("id").GetString() == pspReference)
            .Select(i => i.GetProperty("payment_method").GetString()).FirstOrDefault() ?? SubscriptionsApp.DefaultPaymentMethod;
    }

    public Billed Bill(Subscription s, string sku, int qty, decimal unitPrice, string reason, string idempotencyKey)
    {
        var a = s.ShippingAddress;
        var address = new { firstName = a.FirstName, lastName = a.LastName, streetAddress1 = a.StreetAddress1, city = a.City, postalCode = a.PostalCode, country = a.Country, countryArea = a.CountryArea };
        var draft = Mutate("draftOrderCreate",
            "mutation($input: DraftOrderCreateInput!) { draftOrderCreate(input: $input) { order { id } errors { code message } } }",
            new { input = new { userEmail = s.Email, shippingAddress = address, lines = new[] { new { variantId = VariantId(sku), quantity = qty, price = unitPrice } } } });
        var orderId = draft.GetProperty("order").GetProperty("id").GetString()!;
        Mutate("updateMetadata", "mutation($id: ID!, $input: [MetadataInput!]!) { updateMetadata(id: $id, input: $input) { errors { code message } } }",
            new { id = orderId, input = new[] { new { key = SubscriptionsApp.MetadataKey, value = s.SubscriptionId }, new { key = "subscription_reason", value = reason } } });
        var order = Mutate("draftOrderComplete", "mutation($id: ID!) { draftOrderComplete(id: $id) { order { total { gross { amount } } } errors { code message } } }",
            new { id = orderId }).GetProperty("order");
        var total = order.GetProperty("total").GetProperty("gross").GetProperty("amount").GetDecimal();
        var payment = Mutate("transactionInitialize",
            "mutation($id: ID!, $gateway: String!, $data: JSON, $key: String) { transactionInitialize(id: $id, idempotencyKey: $key, paymentGateway: {id: $gateway, data: $data}) { transactionEvent { type message } errors { code message } } }",
            new { id = orderId, gateway = PaymentGateway, data = new { paymentMethod = s.PaymentMethod }, key = idempotencyKey }).GetProperty("transactionEvent");
        if (payment.GetProperty("type").GetString() == "CHARGE_SUCCESS") return new Billed(orderId, true, total, "");
        // An order nobody paid for must not be shipped: cancel it.
        Mutate("orderCancel", "mutation($id: ID!) { orderCancel(id: $id) { errors { code message } } }", new { id = orderId });
        return new Billed(orderId, false, total, payment.GetProperty("message").GetString() is { Length: > 0 } m ? m : "payment_failed");
    }

    public void Annotate(string orderId, string key, string? value) =>
        Mutate("updateMetadata", "mutation($id: ID!, $input: [MetadataInput!]!) { updateMetadata(id: $id, input: $input) { errors { code message } } }",
            new { id = orderId, input = new[] { new { key, value } } });
}

public class Notifier(string notificationsUrl) : INotifier
{
    private readonly HttpClient _http = new() { Timeout = TimeSpan.FromSeconds(10) };

    public void Notify(string notifyEvent, object payload)
    {
        var body = new StringContent(JsonSerializer.Serialize(new { notify_event = notifyEvent, payload }), Encoding.UTF8, "application/json");
        try
        {
            var response = _http.PostAsync($"{notificationsUrl}/api/notify", body).GetAwaiter().GetResult();
            if (!response.IsSuccessStatusCode) Telemetry.Log("error", $"notifications refused {notifyEvent}: {(int)response.StatusCode}");
        }
        catch (HttpRequestException e)
        {
            Telemetry.Log("error", $"notifications could not be reached for {notifyEvent}: {e.Message}");   // the change itself still stands
        }
    }
}
