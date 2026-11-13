package seedco.orders;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.URLDecoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

/** HTTP wiring for Orders: the server, the Billing client and the event publisher. */
public class Main {
    static final HttpClient HTTP = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).build();
    static final int ATTEMPTS = 3;   // a call that cannot reach the other side is tried this many times

    /** POSTs JSON. A connection failure is retried; an HTTP error is not. */
    static Map<String, Object> post(String url, Object body, String idempotencyKey) {
        HttpRequest.Builder req = HttpRequest.newBuilder(URI.create(url)).timeout(Duration.ofSeconds(10))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(Db.json(body)));
        if (idempotencyKey != null) {
            req.header("Idempotency-Key", idempotencyKey);
        }
        IOException last = null;
        for (int attempt = 1; attempt <= ATTEMPTS; attempt++) {
            try {
                HttpResponse<String> res = HTTP.send(req.build(), HttpResponse.BodyHandlers.ofString());
                if (res.statusCode() >= 400) {
                    throw new IllegalStateException("POST " + url + " -> " + res.statusCode() + " " + res.body());
                }
                return Db.map(res.body());
            } catch (IOException e) {
                last = e;
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new IllegalStateException("POST " + url + " interrupted", e);
            }
        }
        throw new IllegalStateException("POST " + url + " failed: " + last.getMessage(), last);
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
                return post(billingUrl + "/quotes", body, null);
            }

            public Map<String, Object> charge(Map<String, Object> order, Map<String, Object> amount) {
                Map<String, Object> body = new LinkedHashMap<>();
                body.put("order_id", order.get("order_id"));
                body.put("customer_id", order.get("customer_id"));
                body.put("email", order.get("email"));
                body.put("payment_method", order.get("payment_method"));
                body.put("amount", amount);
                return post(billingUrl + "/charges", body, (String) order.get("order_id"));
            }
        };
        Orders orders = new Orders(billing, (topic, event) -> post(brokerUrl + "/topics/" + topic, event, null),
                Db.fromEnvironment());
        // Events the broker did not take the first time are sent again from the outbox.
        Executors.newSingleThreadScheduledExecutor(r -> {
            Thread t = new Thread(r, "outbox");
            t.setDaemon(true);
            return t;
        }).scheduleWithFixedDelay(() -> {
            try {
                orders.flushOutbox();
            } catch (RuntimeException e) {
                System.err.println("orders: outbox flush failed: " + e.getMessage());
            }
        }, 1, 1, TimeUnit.SECONDS);

        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", port), 0);
        server.setExecutor(Executors.newFixedThreadPool(8));
        server.createContext("/", ex -> handle(orders, ex));
        server.start();
        System.out.println("orders listening on " + port);
    }

    static void handle(Orders orders, HttpExchange ex) throws IOException {
        String method = ex.getRequestMethod();
        String[] p = ex.getRequestURI().getPath().split("/");   // "", "orders", id, action
        String root = p.length > 1 ? p[1] : "";
        Map<String, String> query = query(ex.getRequestURI().getRawQuery());
        String key = ex.getRequestHeaders().getFirst("Idempotency-Key");
        try {
            if (root.equals("health") && p.length == 2) {
                send(ex, 200, Map.of("ok", true));
            } else if (root.equals("catalog") && p.length == 2 && method.equals("GET")) {
                send(ex, 200, Map.of("products", orders.catalog()));
            } else if (root.equals("orders") && p.length == 2 && method.equals("POST")) {
                send(ex, 201, orders.place(body(ex), key));
            } else if (root.equals("orders") && p.length == 2 && method.equals("GET")) {
                Integer limit = query.containsKey("limit") ? Integer.valueOf(query.get("limit")) : null;
                send(ex, 200, orders.page(query.get("customer_id"), limit, query.get("after")));
            } else if (root.equals("orders") && p.length == 3 && method.equals("GET")) {
                send(ex, 200, orders.get(p[2]));
            } else if (root.equals("orders") && p.length == 4 && method.equals("POST") && p[3].equals("cancel")) {
                send(ex, 200, orders.cancel(p[2]));
            } else if (root.equals("orders") && p.length == 4 && method.equals("POST") && p[3].equals("ship")) {
                send(ex, 200, orders.ship(p[2]));
            } else if (root.equals("orders") && p.length == 4 && method.equals("POST") && p[3].equals("deliver")) {
                send(ex, 200, orders.deliver(p[2]));
            } else if (root.equals("carts") && p.length == 3 && method.equals("GET")) {
                send(ex, 200, orders.cart(p[2]));
            } else if (root.equals("carts") && p.length == 5 && p[3].equals("items") && method.equals("PUT")) {
                Object qty = body(ex).get("qty");
                send(ex, 200, orders.setCartItem(p[2], p[4], qty instanceof Number ? ((Number) qty).intValue() : -1));
            } else if (root.equals("carts") && p.length == 5 && p[3].equals("items") && method.equals("DELETE")) {
                send(ex, 200, orders.setCartItem(p[2], p[4], 0));
            } else if (root.equals("carts") && p.length == 4 && p[3].equals("checkout") && method.equals("POST")) {
                send(ex, 201, orders.checkoutCart(p[2], body(ex), key));
            } else {
                send(ex, 404, Map.of("error", "not_found"));
            }
        } catch (Orders.BadRequest | NumberFormatException e) {
            send(ex, 400, Map.of("error", "bad_request", "message", String.valueOf(e.getMessage())));
        } catch (Orders.NotFound e) {
            send(ex, 404, Map.of("error", "not_found", "message", e.getMessage()));
        } catch (Orders.Conflict e) {
            send(ex, 409, Map.of("error", "conflict", "message", e.getMessage()));
        } catch (com.fasterxml.jackson.core.JsonProcessingException e) {
            send(ex, 400, Map.of("error", "invalid_json"));
        } catch (RuntimeException e) {
            send(ex, 502, Map.of("error", "upstream_failed", "message", String.valueOf(e.getMessage())));
        }
    }

    static Map<String, Object> body(HttpExchange ex) throws IOException {
        Map<String, Object> body = Db.JSON.readValue(ex.getRequestBody(), Db.MAP);
        if (body == null) {
            throw new Orders.BadRequest("a JSON object is required");
        }
        return body;
    }

    static Map<String, String> query(String raw) {
        Map<String, String> out = new HashMap<>();
        if (raw != null) {
            for (String pair : raw.split("&")) {
                int eq = pair.indexOf('=');
                if (eq > 0) {
                    out.put(URLDecoder.decode(pair.substring(0, eq), StandardCharsets.UTF_8),
                            URLDecoder.decode(pair.substring(eq + 1), StandardCharsets.UTF_8));
                }
            }
        }
        return out;
    }

    static void send(HttpExchange ex, int code, Object body) throws IOException {
        byte[] bytes = Db.json(body).getBytes(StandardCharsets.UTF_8);
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
