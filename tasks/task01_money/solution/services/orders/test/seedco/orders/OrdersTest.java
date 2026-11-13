package seedco.orders;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class OrdersTest {
    List<Map<String, Object>> published;
    List<Map<String, Object>> charged;
    boolean brokerDown;
    Orders.Billing billing;
    Orders orders;

    @BeforeEach
    void setUp() {
        published = new ArrayList<>();
        charged = new ArrayList<>();
        brokerDown = false;
        billing = new Orders.Billing() {
            public Map<String, Object> quote(int postalCode, List<Map<String, Object>> lines) {
                long subtotal = 0;
                for (Map<String, Object> l : lines) {
                    subtotal += Orders.minor(l.get("unit_price")) * (Integer) l.get("qty");
                }
                return Map.of("subtotal", Orders.money(subtotal), "tax", Orders.money(100), "total", Orders.money(subtotal + 100));
            }

            public Map<String, Object> charge(Map<String, Object> order, Map<String, Object> amount) {
                charged.add(amount);
                boolean declined = "pm_card_declined".equals(order.get("payment_method"));
                return Map.of("payment_id", "pay_" + charged.size(), "status", declined ? "failed" : "succeeded");
            }
        };
        orders = new Orders(billing, this::publish);
    }

    void publish(String topic, Map<String, Object> event) {
        if (brokerDown) {
            throw new IllegalStateException("broker down");
        }
        published.add(event);
    }

    Map<String, Object> request() {
        return Map.of("customer_id", "c1", "email", "a@example.com", "postal_code", 94105,
                "items", List.of(Map.of("sku", "BOX-S", "qty", 2)));
    }

    String place() {
        return (String) orders.place(request()).get("order_id");
    }

    @Test
    void placesAnOrderChargesTheQuotedTotalAndPublishes() {
        Map<String, Object> o = orders.place(request());
        assertEquals("paid", o.get("status"));
        assertEquals(Orders.money(5098), o.get("total"));
        assertEquals("pm_card_ok", o.get("payment_method"));
        assertEquals(List.of(Orders.money(5098)), charged);
        assertEquals(1, published.size());
        assertEquals("order.placed", published.get(0).get("event_type"));
        assertTrue(published.get(0).get("event_id").toString().startsWith("evt_"));
        assertEquals(Orders.money(5098), orders.get((String) o.get("order_id")).get("total"));
    }

    @Test
    void rejectsUnknownSkuAndMissingFields() {
        assertThrows(Orders.BadRequest.class, () -> orders.place(Map.of("customer_id", "c1", "email", "a@example.com",
                "postal_code", 94105, "items", List.of(Map.of("sku", "NOPE", "qty", 1)))));
        assertThrows(Orders.BadRequest.class, () -> orders.place(Map.of("email", "a@example.com", "postal_code", 94105,
                "items", List.of(Map.of("sku", "BOX-S", "qty", 1)))));
    }

    @Test
    void aDeclinedPaymentLeavesAFailedOrderAndPublishesNothing() {
        Map<String, Object> req = new java.util.HashMap<>(request());
        req.put("payment_method", "pm_card_declined");
        Map<String, Object> o = orders.place(req);
        assertEquals("payment_failed", o.get("status"));
        assertEquals(0, published.size());
        assertThrows(Orders.Conflict.class, () -> orders.cancel((String) o.get("order_id")));
    }

    @Test
    void aRepeatedIdempotencyKeyPlacesOneOrder() {
        Map<String, Object> first = orders.place(request(), "key-1");
        assertEquals(first.get("order_id"), orders.place(request(), "key-1").get("order_id"));
        assertEquals(1, charged.size());
        assertEquals(1, orders.list("c1").size());
    }

    @Test
    void cancelPublishesOnceAndIsIdempotent() {
        String id = place();
        orders.cancel(id);
        orders.cancel(id);
        assertEquals("cancelled", orders.get(id).get("status"));
        assertEquals(2, published.size());
        assertEquals("order.cancelled", published.get(1).get("event_type"));
    }

    @Test
    void anOrderMovesThroughTheStateMachine() {
        String id = place();
        assertThrows(Orders.Conflict.class, () -> orders.deliver(id));     // paid -> delivered is not allowed
        assertEquals("shipped", orders.ship(id).get("status"));
        orders.ship(id);
        assertEquals("order.shipped", published.get(published.size() - 1).get("event_type"));
        assertEquals(2, published.size());
        assertThrows(Orders.Conflict.class, () -> orders.cancel(id));      // too late to cancel
        assertEquals("delivered", orders.deliver(id).get("status"));
    }

    @Test
    void listsOrdersByCustomerInPages() {
        List<String> ids = List.of(place(), place(), place());
        assertEquals(3, orders.list("c1").size());
        assertEquals(0, orders.list("c2").size());
        assertThrows(Orders.NotFound.class, () -> orders.get("ord_missing"));
        Map<String, Object> first = orders.page("c1", 2, null);
        assertEquals(2, ((List<?>) first.get("orders")).size());
        assertEquals(ids.get(1), first.get("next"));
        Map<String, Object> second = orders.page("c1", 2, (String) first.get("next"));
        assertEquals(1, ((List<?>) second.get("orders")).size());
        assertNull(second.get("next"));
        assertThrows(Orders.BadRequest.class, () -> orders.page("c1", 0, null));
    }

    @Test
    void aCartIsPricedFromTheCatalogueAndBecomesAnOrder() {
        assertEquals(3, orders.catalog().size());
        orders.setCartItem("c1", "BOX-S", 2);
        orders.setCartItem("c1", "ADD-TEA", 3);
        Map<String, Object> cart = orders.setCartItem("c1", "ADD-TEA", 1);
        assertEquals(Orders.money(5623), cart.get("subtotal"));
        assertThrows(Orders.BadRequest.class, () -> orders.setCartItem("c1", "NOPE", 1));
        Map<String, Object> o = orders.checkoutCart("c1", Map.of("email", "a@example.com", "postal_code", 94105), null);
        assertEquals(Orders.money(5723), o.get("total"));
        assertEquals(0, ((List<?>) orders.cart("c1").get("items")).size());
        assertThrows(Orders.BadRequest.class, () -> orders.checkoutCart("c1", Map.of(), null));
    }

    @Test
    void anEventTheBrokerRefusedIsSentLaterWithTheSameId() {
        brokerDown = true;
        String id = place();
        orders.cancel(id);
        assertEquals(0, published.size());
        assertEquals(2, orders.flushOutbox());
        brokerDown = false;
        assertEquals(0, orders.flushOutbox());
        assertEquals(List.of("order.placed", "order.cancelled"), published.stream().map(e -> e.get("event_type")).toList());
        assertEquals(0, orders.flushOutbox());
        assertEquals(2, published.size());
    }

    @Test
    void ordersSurviveARestart() throws Exception {
        Path dir = Files.createTempDirectory("seedco-orders-");
        String id;
        try (Db db = Db.file(dir.resolve("orders"))) {
            id = (String) new Orders(billing, this::publish, db).place(request()).get("order_id");
        }
        try (Db db = Db.file(dir.resolve("orders"))) {
            Orders again = new Orders(billing, this::publish, db);
            assertEquals(Orders.money(5098), again.get(id).get("total"));
            assertEquals(3, again.catalog().size());
        }
    }
}
