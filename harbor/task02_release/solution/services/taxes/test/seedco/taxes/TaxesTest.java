package seedco.taxes;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.math.BigDecimal;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class TaxesTest {
    Taxes taxes = new Taxes("jdbc:h2:mem:");

    static Map<String, Object> money(String amount) {
        return Map.of("amount", new BigDecimal(amount));
    }

    static Map<String, Object> line(int quantity, String total) {
        return Map.of("quantity", quantity, "chargeTaxes", true, "productSku", "BOX-S", "totalPrice", money(total));
    }

    static Map<String, Object> payload(boolean withTax, String postalCode, String country, String shipping, Map<String, Object>... lines) {
        Map<String, Object> base = new HashMap<>();
        base.put("pricesEnteredWithTax", withTax);
        base.put("currency", "USD");
        base.put("shippingPrice", money(shipping));
        base.put("address", Map.of("postalCode", postalCode, "country", Map.of("code", country)));
        base.put("lines", List.of(lines));
        base.put("sourceObject", Map.of("__typename", "Checkout", "id", "Q2hlY2tvdXQ6MQ=="));
        return Map.of("taxBase", base);
    }

    @SuppressWarnings("unchecked")
    static List<Map<String, Object>> lines(Map<String, Object> answer) {
        return (List<Map<String, Object>>) answer.get("lines");
    }

    @Test
    void addsTaxOnTopOfNetPricesLineByLine() {
        Map<String, Object> a = taxes.calculate(payload(false, "94105", "US", "5.00", line(2, "49.98"), line(1, "6.25")));
        assertEquals(new BigDecimal("8.75"), lines(a).get(0).get("tax_rate"));           // a percentage, not a fraction
        assertEquals(new BigDecimal("49.98"), lines(a).get(0).get("total_net_amount"));
        assertEquals(new BigDecimal("54.35"), lines(a).get(0).get("total_gross_amount")); // 49.98 * 1.0875 = 54.353...
        assertEquals(new BigDecimal("6.80"), lines(a).get(1).get("total_gross_amount"));  // 6.25 * 1.0875 = 6.796...
        assertEquals(new BigDecimal("5.00"), a.get("shipping_price_gross_amount"));       // shipping is not taxed
        assertEquals(new BigDecimal("0"), a.get("shipping_tax_rate"));
    }

    @Test
    void takesTaxOutOfPricesEnteredWithTax() {
        Map<String, Object> a = taxes.calculate(payload(true, "10001", "US", "5.00", line(1, "106.00")));
        assertEquals(new BigDecimal("6.00"), lines(a).get(0).get("tax_rate"));
        assertEquals(new BigDecimal("100.00"), lines(a).get(0).get("total_net_amount"));
        assertEquals(new BigDecimal("106.00"), lines(a).get(0).get("total_gross_amount"));
    }

    @Test
    void roundsHalfUpAndChargesNothingAbroad() {
        // 162.25 at 6% is 9.735 of tax: the gross rounds up to 171.99
        assertEquals(new BigDecimal("171.99"), lines(taxes.calculate(payload(false, "10001", "US", "0", line(1, "162.25")))).get(0).get("total_gross_amount"));
        Map<String, Object> abroad = taxes.calculate(payload(false, "M5V 2T6", "CA", "5.00", line(1, "10.00")));
        assertEquals(new BigDecimal("10.00"), lines(abroad).get(0).get("total_gross_amount"));
        Map<String, Object> exempt = new HashMap<>(line(1, "10.00"));
        exempt.put("chargeTaxes", false);
        assertEquals(new BigDecimal("10.00"), lines(taxes.calculate(payload(false, "94105", "US", "0", exempt))).get(0).get("total_gross_amount"));
    }

    @Test
    void refusesAPayloadWithoutWhatItNeeds() {
        assertThrows(Taxes.BadPayload.class, () -> taxes.calculate(Map.of()));
        Map<String, Object> noAmount = Map.of("quantity", 1, "totalPrice", Map.of("amount", "49.98"));
        assertThrows(Taxes.BadPayload.class, () -> taxes.calculate(payload(false, "94105", "US", "5.00", noAmount)));
    }

    @Test
    void commitsOneTaxDocumentPerOrderAndVoidsItOnCancel() {
        Map<String, Object> order = Map.of("id", "T3JkZXI6MQ==", "number", "1",
                "total", Map.of("gross", money("66.15"), "tax", money("4.92")),
                "shippingAddress", Map.of("postalCode", "94105", "country", Map.of("code", "US")));
        taxes.orderEvent(Map.of("__typename", "OrderConfirmed", "order", order));
        taxes.orderEvent(Map.of("__typename", "OrderConfirmed", "order", order));           // a delivery can arrive twice
        assertEquals(1, taxes.documents().size());
        assertEquals(new BigDecimal("4.92"), taxes.documents().get(0).get("tax"));
        assertEquals("committed", taxes.documents().get(0).get("status"));
        taxes.orderEvent(Map.of("__typename", "OrderCancelled", "order", Map.of("id", "T3JkZXI6MQ==", "number", "1")));
        assertEquals("voided", taxes.documents().get(0).get("status"));
    }

    @Test
    void theManifestCarriesTheQueriesFromTheGraphqlFiles() throws Exception {
        Map<String, Object> m = Main.manifest("http://taxes.test", Path.of("graphql"));
        assertEquals("seedco.taxes", m.get("id"));
        assertEquals("http://taxes.test/api/register", m.get("tokenTargetUrl"));
        @SuppressWarnings("unchecked")
        Map<String, Object> webhook = ((List<Map<String, Object>>) m.get("webhooks")).get(0);
        assertEquals(List.of("CHECKOUT_CALCULATE_TAXES", "ORDER_CALCULATE_TAXES"), webhook.get("syncEvents"));
        assertTrue(webhook.get("query").toString().contains("pricesEnteredWithTax"));
    }
}
