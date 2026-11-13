package seedco.orders;

import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/** Carts become orders here. Owns the order state machine and the catalogue of what can be bought. */
public class Orders {
    /** Billing, as Orders sees it (contracts pinned under pinned/billing-api.yaml). */
    public interface Billing {
        Map<String, Object> quote(int postalCode, List<Map<String, Object>> lines);

        /** Charges the order's customer. The order id is the idempotency key: a retry never charges twice. */
        Map<String, Object> charge(Map<String, Object> order, Map<String, Object> amount);
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

    /** The order is not in a state that allows what was asked. */
    public static class Conflict extends RuntimeException {
        public Conflict(String message) {
            super(message);
        }
    }

    public static final String TOPIC = "orders";
    public static final String DEFAULT_PAYMENT_METHOD = "pm_card_ok";
    public static final int DEFAULT_PAGE = 20;
    public static final int MAX_PAGE = 100;

    /** The order state machine: from each status, the statuses it may move to. */
    static final Map<String, Set<String>> TRANSITIONS = Map.of(
            "placed", Set.of("paid", "payment_failed", "cancelled"),
            "paid", Set.of("shipped", "cancelled"),
            "shipped", Set.of("delivered"),
            "payment_failed", Set.of(),
            "delivered", Set.of(),
            "cancelled", Set.of());

    // What the catalogue starts with: sku, name, unit price in cents.
    static final Object[][] CATALOG = {
        {"BOX-S", "Small monthly box", 2499L},
        {"BOX-L", "Large monthly box", 3950L},
        {"ADD-TEA", "Tea add-on", 625L},
    };

    private final Billing billing;
    private final Publisher publisher;
    private final Db db;

    public Orders(Billing billing, Publisher publisher) {
        this(billing, publisher, Db.inMemory());
    }

    public Orders(Billing billing, Publisher publisher, Db db) {
        this.billing = billing;
        this.publisher = publisher;
        this.db = db;
        for (int i = 0; i < CATALOG.length; i++) {
            db.seedProduct(i, (String) CATALOG[i][0], (String) CATALOG[i][1], (Long) CATALOG[i][2]);
        }
    }

    // ---- catalogue ----

    public List<Map<String, Object>> catalog() {
        return db.query("SELECT sku, name, unit_price FROM products ORDER BY position",
                r -> product(r.getString(1), r.getString(2), r.getLong(3)));
    }

    private Map<String, Object> product(String sku) {
        List<Map<String, Object>> found = db.query("SELECT sku, name, unit_price FROM products WHERE sku = ?",
                r -> product(r.getString(1), r.getString(2), r.getLong(3)), sku);
        if (found.isEmpty()) {
            throw new BadRequest("unknown sku " + sku);
        }
        return found.get(0);
    }

    private static Map<String, Object> product(String sku, String name, long unitPrice) {
        Map<String, Object> p = new LinkedHashMap<>();
        p.put("sku", sku);
        p.put("name", name);
        p.put("unit_price", money(unitPrice));
        return p;
    }

    // ---- carts ----

    public Map<String, Object> cart(String customerId) {
        List<Map<String, Object>> items = db.query(
                "SELECT p.sku, p.name, p.unit_price, c.qty FROM cart_items c JOIN products p ON p.sku = c.sku "
                    + "WHERE c.customer_id = ? ORDER BY p.position",
                r -> {
                    Map<String, Object> item = product(r.getString(1), r.getString(2), r.getLong(3));
                    item.put("qty", r.getInt(4));
                    return item;
                }, customerId);
        long subtotal = 0;
        for (Map<String, Object> item : items) {
            subtotal += minor(item.get("unit_price")) * (Integer) item.get("qty");
        }
        Map<String, Object> cart = new LinkedHashMap<>();
        cart.put("customer_id", customerId);
        cart.put("items", items);
        cart.put("subtotal", money(subtotal));
        return cart;
    }

    /** Sets how many of a product are in the cart. A quantity of zero takes it out. */
    public synchronized Map<String, Object> setCartItem(String customerId, String sku, int qty) {
        if (qty < 0) {
            throw new BadRequest("qty must not be negative");
        }
        product(sku);
        if (qty == 0) {
            db.update("DELETE FROM cart_items WHERE customer_id = ? AND sku = ?", customerId, sku);
        } else {
            db.update("MERGE INTO cart_items (customer_id, sku, qty) KEY (customer_id, sku) VALUES (?, ?, ?)", customerId, sku, qty);
        }
        return cart(customerId);
    }

    /** Places an order for what is in the cart. The cart is emptied once the order is paid. */
    @SuppressWarnings("unchecked")
    public synchronized Map<String, Object> checkoutCart(String customerId, Map<String, Object> details, String idempotencyKey) {
        List<Map<String, Object>> items = (List<Map<String, Object>>) cart(customerId).get("items");
        if (items.isEmpty()) {
            throw new BadRequest("the cart is empty");
        }
        Map<String, Object> req = new LinkedHashMap<>(details == null ? Map.of() : details);
        req.put("customer_id", customerId);
        req.put("items", items);
        Map<String, Object> order = place(req, idempotencyKey);
        if ("paid".equals(order.get("status"))) {
            db.update("DELETE FROM cart_items WHERE customer_id = ?", customerId);
        }
        return order;
    }

    // ---- orders ----

    public Map<String, Object> place(Map<String, Object> req) {
        return place(req, null);
    }

    /** Places an order. With an idempotency key, a repeat of the request returns the first order. */
    @SuppressWarnings("unchecked")
    public synchronized Map<String, Object> place(Map<String, Object> req, String idempotencyKey) {
        if (idempotencyKey != null) {
            List<String> earlier = db.query("SELECT order_id FROM idempotency WHERE idem_key = ?", r -> r.getString(1), idempotencyKey);
            if (!earlier.isEmpty()) {
                return get(earlier.get(0));
            }
        }
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
            Map<String, Object> product = product(str(item, "sku"));
            int qty = item.get("qty") instanceof Number ? ((Number) item.get("qty")).intValue() : 0;
            if (qty < 1) {
                throw new BadRequest("qty must be at least 1");
            }
            Map<String, Object> line = new LinkedHashMap<>();
            line.put("sku", product.get("sku"));
            line.put("name", product.get("name"));
            line.put("qty", qty);
            line.put("unit_price", product.get("unit_price"));
            lines.add(line);
        }
        Object method = req.get("payment_method");
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
        o.put("payment_method", method instanceof String && !((String) method).isBlank() ? method : DEFAULT_PAYMENT_METHOD);
        o.put("created_at", Instant.now().toString());
        Map<String, Object> charge = billing.charge(o, (Map<String, Object>) quote.get("total"));
        move(o, "succeeded".equals(charge.get("status")) ? "paid" : "payment_failed");
        o.put("payment_id", charge.get("payment_id"));
        db.update("INSERT INTO orders (id, customer_id, body) VALUES (?, ?, ?)", id, customerId, Db.json(o));
        if (idempotencyKey != null) {
            db.update("INSERT INTO idempotency (idem_key, order_id) VALUES (?, ?)", idempotencyKey, id);
        }
        if ("paid".equals(o.get("status"))) {
            publish("order.placed", o);
        }
        return o;
    }

    public Map<String, Object> get(String id) {
        List<Map<String, Object>> found = db.query("SELECT body FROM orders WHERE id = ?", r -> Db.map(r.getString(1)), id);
        if (found.isEmpty()) {
            throw new NotFound("no order " + id);
        }
        return found.get(0);
    }

    /** Every order of one customer (or of everyone), oldest first. */
    public List<Map<String, Object>> list(String customerId) {
        return db.query("SELECT body FROM orders WHERE (CAST(? AS VARCHAR) IS NULL OR customer_id = ?) ORDER BY seq",
                r -> Db.map(r.getString(1)), customerId, customerId);
    }

    /**
     * One page of orders, oldest first. {@code after} is the last order id of the previous page; {@code next} in the
     * result is the id to pass for the following page, or null when this is the last one.
     */
    public Map<String, Object> page(String customerId, Integer limit, String after) {
        int size = limit == null ? DEFAULT_PAGE : limit;
        if (size < 1 || size > MAX_PAGE) {
            throw new BadRequest("limit must be between 1 and " + MAX_PAGE);
        }
        long from = 0;
        if (after != null) {
            List<Long> seq = db.query("SELECT seq FROM orders WHERE id = ?", r -> r.getLong(1), after);
            if (seq.isEmpty()) {
                throw new BadRequest("unknown cursor " + after);
            }
            from = seq.get(0);
        }
        List<Map<String, Object>> rows = db.query(
                "SELECT body FROM orders WHERE seq > ? AND (CAST(? AS VARCHAR) IS NULL OR customer_id = ?) ORDER BY seq LIMIT ?",
                r -> Db.map(r.getString(1)), from, customerId, customerId, size + 1);
        boolean more = rows.size() > size;
        List<Map<String, Object>> orders = more ? rows.subList(0, size) : rows;
        Map<String, Object> page = new LinkedHashMap<>();
        page.put("orders", orders);
        page.put("next", more ? orders.get(orders.size() - 1).get("order_id") : null);
        return page;
    }

    public synchronized Map<String, Object> cancel(String id) {
        Map<String, Object> o = get(id);
        if ("cancelled".equals(o.get("status"))) {
            return o;
        }
        return change(o, "cancelled", "order.cancelled");
    }

    public synchronized Map<String, Object> ship(String id) {
        Map<String, Object> o = get(id);
        if ("shipped".equals(o.get("status"))) {
            return o;
        }
        o.put("shipped_at", Instant.now().toString());
        return change(o, "shipped", "order.shipped");
    }

    public synchronized Map<String, Object> deliver(String id) {
        return change(get(id), "delivered", null);
    }

    private Map<String, Object> change(Map<String, Object> o, String status, String eventType) {
        move(o, status);
        db.update("UPDATE orders SET body = ? WHERE id = ?", Db.json(o), o.get("order_id"));
        if (eventType != null) {
            publish(eventType, o);
        }
        return o;
    }

    private static void move(Map<String, Object> o, String to) {
        Object from = o.get("status");
        if (!TRANSITIONS.getOrDefault(from, Set.of()).contains(to)) {
            throw new Conflict("an order in status " + from + " cannot become " + to);
        }
        o.put("status", to);
        o.put("updated_at", Instant.now().toString());
    }

    // ---- events ----

    /**
     * Events go through an outbox: the event is stored with the order, then sent. If the broker is down the event
     * stays in the outbox and is sent later, with the same event id.
     */
    private void publish(String type, Map<String, Object> order) {
        db.update("INSERT INTO outbox (topic, body) VALUES (?, ?)", TOPIC, Db.json(envelope(type, Map.of("order", order))));
        flushOutbox();
    }

    /** Sends every stored event that has not been sent yet, oldest first. Returns how many are still waiting. */
    public synchronized int flushOutbox() {
        List<Object[]> waiting = db.query("SELECT seq, topic, body FROM outbox WHERE published = FALSE ORDER BY seq",
                r -> new Object[] {r.getLong(1), r.getString(2), r.getString(3)});
        int sent = 0;
        for (Object[] row : waiting) {
            try {
                publisher.publish((String) row[1], Db.map((String) row[2]));
            } catch (RuntimeException e) {
                break;   // keep the order of events: nothing later is sent before this one
            }
            db.update("UPDATE outbox SET published = TRUE WHERE seq = ?", row[0]);
            sent++;
        }
        return waiting.size() - sent;
    }

    static Map<String, Object> envelope(String type, Map<String, Object> data) {
        Map<String, Object> e = new LinkedHashMap<>();
        e.put("event_id", "evt_" + UUID.randomUUID());
        e.put("event_type", type);
        e.put("occurred_at", Instant.now().toString());
        e.put("data", data);
        return e;
    }

    /** Money on every contract: integer minor units (cents) with a currency. Only USD exists today. */
    static Map<String, Object> money(long minor) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("currency", "USD");
        m.put("minor", minor);
        return m;
    }

    /** The cents in a Money object. */
    static long minor(Object money) {
        return ((Number) ((Map<?, ?>) money).get("minor")).longValue();
    }

    private static String str(Map<String, Object> m, String key) {
        Object v = m.get(key);
        if (!(v instanceof String) || ((String) v).isBlank()) {
            throw new BadRequest(key + " is required");
        }
        return (String) v;
    }
}
