package seedco.orders;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Executors;

/** HTTP wiring for Orders: the server, the Billing client and the event publisher. */
public class Main {
    static final ObjectMapper JSON = new ObjectMapper().enable(DeserializationFeature.USE_BIG_DECIMAL_FOR_FLOATS);
    static final HttpClient HTTP = HttpClient.newHttpClient();
    static final TypeReference<Map<String, Object>> MAP = new TypeReference<>() { };

    static Map<String, Object> post(String url, Object body) {
        try {
            HttpRequest req = HttpRequest.newBuilder(URI.create(url))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(JSON.writeValueAsString(body))).build();
            HttpResponse<String> res = HTTP.send(req, HttpResponse.BodyHandlers.ofString());
            if (res.statusCode() >= 400) {
                throw new IllegalStateException("POST " + url + " -> " + res.statusCode() + " " + res.body());
            }
            return JSON.readValue(res.body(), MAP);
        } catch (IOException | InterruptedException e) {
            throw new IllegalStateException("POST " + url + " failed: " + e.getMessage(), e);
        }
    }

    public static void main(String[] args) throws IOException {
        int port = Integer.parseInt(env("PORT", "7002"));
        String billingUrl = env("BILLING_URL", "http://127.0.0.1:7003");
        String brokerUrl = env("BROKER_URL", "http://127.0.0.1:7000");

        Orders.Billing billing = new Orders.Billing() {
            public Map<String, Object> quote(int postalCode, List<Map<String, Object>> lines) {
                Map<String, Object> body = new LinkedHashMap<>();
                body.put("postal_code", postalCode);
                body.put("lines", lines);
                return post(billingUrl + "/quotes", body);
            }

            public Map<String, Object> charge(String orderId, String customerId, Map<String, Object> amount) {
                Map<String, Object> body = new LinkedHashMap<>();
                body.put("order_id", orderId);
                body.put("customer_id", customerId);
                body.put("amount", amount);
                return post(billingUrl + "/charges", body);
            }
        };
        Orders orders = new Orders(billing, (topic, event) -> post(brokerUrl + "/topics/" + topic, event));

        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", port), 0);
        server.setExecutor(Executors.newFixedThreadPool(8));
        server.createContext("/", ex -> handle(orders, ex));
        server.start();
        System.out.println("orders listening on " + port);
    }

    static void handle(Orders orders, HttpExchange ex) throws IOException {
        String method = ex.getRequestMethod();
        String path = ex.getRequestURI().getPath();
        String query = ex.getRequestURI().getQuery();
        try {
            if (path.equals("/health")) {
                send(ex, 200, Map.of("ok", true));
            } else if (path.equals("/orders") && method.equals("POST")) {
                send(ex, 201, orders.place(JSON.readValue(ex.getRequestBody(), MAP)));
            } else if (path.equals("/orders") && method.equals("GET")) {
                String customer = query != null && query.startsWith("customer_id=") ? query.substring(12) : null;
                send(ex, 200, Map.of("orders", orders.list(customer)));
            } else if (path.matches("/orders/[^/]+/cancel") && method.equals("POST")) {
                send(ex, 200, orders.cancel(path.split("/")[2]));
            } else if (path.matches("/orders/[^/]+") && method.equals("GET")) {
                send(ex, 200, orders.get(path.split("/")[2]));
            } else {
                send(ex, 404, Map.of("error", "not_found"));
            }
        } catch (Orders.BadRequest e) {
            send(ex, 400, Map.of("error", "bad_request", "message", e.getMessage()));
        } catch (Orders.NotFound e) {
            send(ex, 404, Map.of("error", "not_found", "message", e.getMessage()));
        } catch (com.fasterxml.jackson.core.JsonProcessingException e) {
            send(ex, 400, Map.of("error", "invalid_json"));
        } catch (RuntimeException e) {
            send(ex, 502, Map.of("error", "upstream_failed", "message", String.valueOf(e.getMessage())));
        }
    }

    static void send(HttpExchange ex, int code, Object body) throws IOException {
        byte[] bytes = JSON.writeValueAsString(body).getBytes(StandardCharsets.UTF_8);
        ex.getResponseHeaders().add("Content-Type", "application/json");
        ex.sendResponseHeaders(code, bytes.length);
        ex.getResponseBody().write(bytes);
        ex.close();
    }

    static String env(String key, String fallback) {
        String v = System.getenv(key);
        return v == null || v.isBlank() ? fallback : v;
    }
}
