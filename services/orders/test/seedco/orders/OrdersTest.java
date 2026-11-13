package seedco.orders;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class OrdersTest {
    List<Map<String, Object>> published;
    List<BigDecimal> charged;
    Orders orders;

    @BeforeEach
    void setUp() {
        published = new ArrayList<>();
        charged = new ArrayList<>();
        Orders.Billing billing = new Orders.Billing() {
            public Map<String, Object> quote(int postalCode, List<Map<String, Object>> lines) {
                BigDecimal subtotal = BigDecimal.ZERO;
                for (Map<String, Object> l : lines) {
                    subtotal = subtotal.add(((BigDecimal) l.get("unit_price")).multiply(new BigDecimal((Integer) l.get("qty"))));
                }
                return Map.of("subtotal", subtotal, "tax", new BigDecimal("1.00"), "total", subtotal.add(new BigDecimal("1.00")));
            }

            public Map<String, Object> charge(String orderId, String customerId, BigDecimal amount) {
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
        assertEquals(new BigDecimal("50.98"), o.get("total"));
        assertEquals(List.of(new BigDecimal("50.98")), charged);
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
