package seedco.taxes;

import com.fasterxml.jackson.core.JsonGenerator;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicLong;

/** HTTP wiring for the tax app: the manifest Core installs it from, its webhooks, health and metrics. */
public class Main {
    static final ObjectMapper JSON = new ObjectMapper()
            .enable(DeserializationFeature.USE_BIG_DECIMAL_FOR_FLOATS)
            .enable(JsonGenerator.Feature.WRITE_BIGDECIMAL_AS_PLAIN);
    static final TypeReference<Map<String, Object>> MAP = new TypeReference<>() { };
    static final Map<String, AtomicLong> COUNTERS = new TreeMap<>();
    static volatile String token;

    /** The app manifest, in Saleor's format. The webhook queries are the files under graphql/. */
    static Map<String, Object> manifest(String appUrl, Path graphql) throws IOException {
        Map<String, Object> taxes = new LinkedHashMap<>();
        taxes.put("name", "calculate-taxes");
        taxes.put("syncEvents", List.of("CHECKOUT_CALCULATE_TAXES", "ORDER_CALCULATE_TAXES"));
        taxes.put("query", Files.readString(graphql.resolve("calculate-taxes.graphql")));
        taxes.put("targetUrl", appUrl + "/api/webhooks/calculate-taxes");
        Map<String, Object> orders = new LinkedHashMap<>();
        orders.put("name", "order-events");
        orders.put("asyncEvents", List.of("ORDER_CREATED", "ORDER_CANCELLED"));
        orders.put("query", Files.readString(graphql.resolve("order-events.graphql")));
        orders.put("targetUrl", appUrl + "/api/webhooks/order-events");
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("id", "seedco.taxes");
        m.put("name", "Taxes");
        m.put("version", "1.0.0");
        m.put("permissions", List.of("HANDLE_TAXES", "MANAGE_ORDERS"));
        m.put("tokenTargetUrl", appUrl + "/api/register");
        m.put("webhooks", List.of(taxes, orders));
        return m;
    }

    public static void main(String[] args) throws IOException {
        int port = Integer.parseInt(env("PORT", "7004"));
        String appUrl = env("APP_URL", "http://127.0.0.1:" + port);
        Path graphql = Path.of(env("SEEDCO_GRAPHQL_DIR", "graphql"));
        Taxes taxes = new Taxes(Taxes.jdbcUrl());
        // BIND is the address to listen on: this machine only by default, 0.0.0.0 when each service has its own container
        HttpServer server = HttpServer.create(new InetSocketAddress(env("BIND", "127.0.0.1"), port), 0);
        server.setExecutor(Executors.newFixedThreadPool(8));
        server.createContext("/", ex -> handle(taxes, appUrl, graphql, ex));
        server.start();
        log("info", "taxes listening on " + port);
    }

    static void handle(Taxes taxes, String appUrl, Path graphql, HttpExchange ex) throws IOException {
        String path = ex.getRequestURI().getPath();
        String route = path;
        int status = 200;
        Object body;
        try {
            if (path.equals("/health")) {
                body = Map.of("ok", true);
            } else if (path.equals("/metrics")) {
                send(ex, 200, metrics().getBytes(StandardCharsets.UTF_8), "text/plain; version=0.0.4");
                return;
            } else if (path.equals("/api/manifest")) {
                body = manifest(appUrl, graphql);
            } else if (path.equals("/api/register") && ex.getRequestMethod().equals("POST")) {
                token = (String) JSON.readValue(ex.getRequestBody(), MAP).get("auth_token");
                body = Map.of("success", true);
            } else if (path.equals("/api/webhooks/calculate-taxes") && ex.getRequestMethod().equals("POST")) {
                body = taxes.calculate(JSON.readValue(ex.getRequestBody(), MAP));
            } else if (path.equals("/api/webhooks/order-events") && ex.getRequestMethod().equals("POST")) {
                taxes.orderEvent(JSON.readValue(ex.getRequestBody(), MAP));
                body = Map.of("success", true);
            } else if (path.equals("/api/tax-documents")) {
                body = Map.of("documents", taxes.documents());
            } else {
                route = "unmatched";
                status = 404;
                body = Map.of("error", "not_found");
            }
        } catch (Taxes.BadPayload | JsonProcessingException | ClassCastException e) {
            status = 400;
            body = Map.of("error", "bad_payload", "message", String.valueOf(e.getMessage()));
            log("error", "a webhook payload could not be used: " + e.getMessage());
        } catch (RuntimeException e) {
            status = 500;
            body = Map.of("error", "internal", "message", String.valueOf(e.getMessage()));
            log("error", "unhandled error: " + e);
        }
        count("http_server_request_count_total{http_route=\"" + route + "\",http_response_status_code=\"" + status + "\"}");
        send(ex, status, JSON.writeValueAsBytes(body), "application/json");
    }

    static void count(String series) {
        synchronized (COUNTERS) {
            COUNTERS.computeIfAbsent(series, k -> new AtomicLong()).incrementAndGet();
        }
    }

    static String metrics() {
        StringBuilder out = new StringBuilder("# TYPE http_server_request_count_total counter\n");
        synchronized (COUNTERS) {
            COUNTERS.forEach((series, n) -> out.append(series).append(' ').append(n.get()).append('\n'));
        }
        return out.toString();
    }

    static void log(String level, String message) {
        Map<String, Object> record = new LinkedHashMap<>();
        record.put("timestamp", Instant.now().toString());
        record.put("level", level);
        record.put("service", "taxes");
        record.put("message", message);
        try {
            System.out.println(JSON.writeValueAsString(record));
        } catch (JsonProcessingException e) {
            System.out.println(message);
        }
    }

    static void send(HttpExchange ex, int code, byte[] bytes, String type) throws IOException {
        ex.getResponseHeaders().add("Content-Type", type);
        ex.sendResponseHeaders(code, bytes.length);
        ex.getResponseBody().write(bytes);
        ex.close();
    }

    static String env(String key, String fallback) {
        String v = System.getenv(key);
        return v == null || v.isBlank() ? fallback : v;
    }
}
