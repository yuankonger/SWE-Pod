package seedco.orders;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class OrdersTest {
    List<Map<String, Object>> published;
    List<Map<String, Object>> charged;
    Orders orders;

    @BeforeEach
    void setUp() {
        published = new ArrayList<>();
        charged = new ArrayList<>();
        Orders.Billing billing = new Orders.Billing() {
            @SuppressWarnings("unchecked")
            public Map<String, Object> quote(int postalCode, List<Map<String, Object>> lines) {
                long subtotal = 0;
                for (Map<String, Object> l : lines) {
                    Map<String, Object> unit = (Map<String, Object>) l.get("unit_price");
                    subtotal += (Long) unit.get("minor") * (Integer) l.get("qty");
                }
                return Map.of("subtotal", Orders.money(subtotal), "tax", Orders.money(100), "total", Orders.money(subtotal + 100));
            }

            public Map<String, Object> charge(String orderId, String customerId, Map<String, Object> amount) {
                charged.add(amount);
                return Map.of("payment_id", "pay_1", "status", "succeeded");
            }
        };
        orders = new Orders(billing, (topic, event) -> published.add(event));
    }

    Map<String, Object> request() {
        return Map.of("customer_id", "c1", "email", "a@example.com", "postal_code", 94105,
                "items", List.of(Map.of("sku", "BOX-S", "qty", 2)));
    }

    @Test
    void placesAnOrderChargesTheQuotedTotalAndPublishes() {
        Map<String, Object> o = orders.place(request());
        assertEquals("paid", o.get("status"));
        assertEquals(Orders.money(5098), o.get("total"));
        assertEquals(List.of(Orders.money(5098)), charged);
        assertEquals(1, published.size());
        assertEquals("order.placed", published.get(0).get("event_type"));
        assertTrue(published.get(0).get("event_id").toString().startsWith("evt_"));
    }

    @Test
    void rejectsUnknownSkuAndMissingFields() {
        assertThrows(Orders.BadRequest.class, () -> orders.place(Map.of("customer_id", "c1", "email", "a@example.com",
                "postal_code", 94105, "items", List.of(Map.of("sku", "NOPE", "qty", 1)))));
        assertThrows(Orders.BadRequest.class, () -> orders.place(Map.of("email", "a@example.com", "postal_code", 94105,
                "items", List.of(Map.of("sku", "BOX-S", "qty", 1)))));
    }

    @Test
    void cancelPublishesOnceAndIsIdempotent() {
        String id = (String) orders.place(request()).get("order_id");
        orders.cancel(id);
        orders.cancel(id);
        assertEquals("cancelled", orders.get(id).get("status"));
        assertEquals(2, published.size());
        assertEquals("order.cancelled", published.get(1).get("event_type"));
    }

    @Test
    void listsOrdersByCustomer() {
        orders.place(request());
        assertEquals(1, orders.list("c1").size());
        assertEquals(0, orders.list("c2").size());
        assertThrows(Orders.NotFound.class, () -> orders.get("ord_missing"));
    }
}
