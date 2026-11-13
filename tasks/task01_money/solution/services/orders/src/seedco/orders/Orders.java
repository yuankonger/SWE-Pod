package seedco.orders;

import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/** Carts become orders here. Owns the order state machine and the catalogue of what can be bought. */
public class Orders {
    /** Billing, as Orders sees it (contracts pinned under pinned/billing-api.yaml). */
    public interface Billing {
        Map<String, Object> quote(int postalCode, List<Map<String, Object>> lines);

        Map<String, Object> charge(String orderId, String customerId, Map<String, Object> amount);
    }

    /** The event bus, as Orders sees it. */
    public interface Publisher {
        void publish(String topic, Map<String, Object> event);
    }

    public static class BadRequest extends RuntimeException {
        public BadRequest(String message) {
            super(message);
        }
    }

    public static class NotFound extends RuntimeException {
        public NotFound(String message) {
            super(message);
        }
    }

    public static final String TOPIC = "orders";

    // sku -> {name, unit price in cents}
    static final Map<String, Object[]> CATALOG = Map.of(
            "BOX-S", new Object[] {"Small monthly box", 2499L},
            "BOX-L", new Object[] {"Large monthly box", 3950L},
            "ADD-TEA", new Object[] {"Tea add-on", 625L});

    private final Billing billing;
    private final Publisher publisher;
    private final Map<String, Map<String, Object>> orders = new ConcurrentHashMap<>();
    private final List<String> order = new ArrayList<>();

    public Orders(Billing billing, Publisher publisher) {
        this.billing = billing;
        this.publisher = publisher;
    }

    @SuppressWarnings("unchecked")
    public synchronized Map<String, Object> place(Map<String, Object> req) {
        String customerId = str(req, "customer_id");
        String email = str(req, "email");
        if (!(req.get("postal_code") instanceof Number)) {
            throw new BadRequest("postal_code must be an integer");
        }
        int postalCode = ((Number) req.get("postal_code")).intValue();
        Object rawItems = req.get("items");
        if (!(rawItems instanceof List) || ((List<?>) rawItems).isEmpty()) {
            throw new BadRequest("items must be a non-empty list");
        }
        List<Map<String, Object>> lines = new ArrayList<>();
        for (Object o : (List<?>) rawItems) {
            Map<String, Object> item = (Map<String, Object>) o;
            String sku = str(item, "sku");
            Object[] entry = CATALOG.get(sku);
            if (entry == null) {
                throw new BadRequest("unknown sku " + sku);
            }
            int qty = item.get("qty") instanceof Number ? ((Number) item.get("qty")).intValue() : 0;
            if (qty < 1) {
                throw new BadRequest("qty must be at least 1");
            }
            Map<String, Object> line = new LinkedHashMap<>();
            line.put("sku", sku);
            line.put("name", entry[0]);
            line.put("qty", qty);
            line.put("unit_price", money((Long) entry[1]));
            lines.add(line);
        }
        Map<String, Object> quote = billing.quote(postalCode, lines);
        Map<String, Object> o = new LinkedHashMap<>();
        String id = "ord_" + UUID.randomUUID().toString().substring(0, 8);
        o.put("order_id", id);
        o.put("customer_id", customerId);
        o.put("email", email);
        o.put("postal_code", postalCode);
        o.put("status", "placed");
        o.put("lines", lines);
        o.put("subtotal", quote.get("subtotal"));
        o.put("tax", quote.get("tax"));
        o.put("total", quote.get("total"));
        o.put("created_at", Instant.now().toString());
        Map<String, Object> charge = billing.charge(id, customerId, (Map<String, Object>) quote.get("total"));
        o.put("status", "succeeded".equals(charge.get("status")) ? "paid" : "payment_failed");
        o.put("payment_id", charge.get("payment_id"));
        orders.put(id, o);
        order.add(id);
        if ("paid".equals(o.get("status"))) {
            publisher.publish(TOPIC, envelope("order.placed", Map.of("order", o)));
        }
        return o;
    }

    public Map<String, Object> get(String id) {
        Map<String, Object> o = orders.get(id);
        if (o == null) {
            throw new NotFound("no order " + id);
        }
        return o;
    }

    public synchronized List<Map<String, Object>> list(String customerId) {
        List<Map<String, Object>> out = new ArrayList<>();
        for (String id : order) {
            Map<String, Object> o = orders.get(id);
            if (customerId == null || customerId.equals(o.get("customer_id"))) {
                out.add(o);
            }
        }
        return out;
    }

    public synchronized Map<String, Object> cancel(String id) {
        Map<String, Object> o = get(id);
        if ("cancelled".equals(o.get("status"))) {
            return o;
        }
        if (!"paid".equals(o.get("status")) && !"placed".equals(o.get("status"))) {
            throw new BadRequest("an order in status " + o.get("status") + " cannot be cancelled");
        }
        o.put("status", "cancelled");
        publisher.publish(TOPIC, envelope("order.cancelled", Map.of("order", o)));
        return o;
    }

    /** Money on every contract: integer minor units (cents) with a currency. Only USD exists today. */
    static Map<String, Object> money(long minor) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("currency", "USD");
        m.put("minor", minor);
        return m;
    }

    static Map<String, Object> envelope(String type, Map<String, Object> data) {
        Map<String, Object> e = new LinkedHashMap<>();
        e.put("event_id", "evt_" + UUID.randomUUID());
        e.put("event_type", type);
        e.put("occurred_at", Instant.now().toString());
        e.put("data", data);
        return e;
    }

    private static String str(Map<String, Object> m, String key) {
        Object v = m.get(key);
        if (!(v instanceof String) || ((String) v).isBlank()) {
            throw new BadRequest(key + " is required");
        }
        return (String) v;
    }
}
