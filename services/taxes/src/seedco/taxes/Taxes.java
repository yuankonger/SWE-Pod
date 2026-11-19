package seedco.taxes;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Sales tax for Core's checkouts and orders, and the tax documents we keep for reporting.
 * Core asks for taxes with a synchronous webhook; the answer format is Core's (see pinned/).
 */
public class Taxes {
    /** A payload that does not have what the calculation needs. */
    public static class BadPayload extends RuntimeException {
        public BadPayload(String message) {
            super(message);
        }
    }

    static final BigDecimal HUNDRED = new BigDecimal("100");
    static final BigDecimal ZERO_RATE = new BigDecimal("0");

    private final Connection db;

    public Taxes(String jdbcUrl) {
        try {
            db = DriverManager.getConnection(jdbcUrl);
            try (PreparedStatement s = db.prepareStatement("CREATE TABLE IF NOT EXISTS tax_documents ("
                    + "order_id VARCHAR(128) PRIMARY KEY, order_number VARCHAR(32) NOT NULL, tax DECIMAL(12,2) NOT NULL, "
                    + "gross DECIMAL(12,2) NOT NULL, postal_code VARCHAR(16), status VARCHAR(16) NOT NULL)")) {
                s.executeUpdate();
            }
        } catch (SQLException e) {
            throw new IllegalStateException("cannot open the taxes database: " + e.getMessage(), e);
        }
    }

    public static String jdbcUrl() {
        String dir = System.getenv("SEEDCO_DATA_DIR");
        return dir == null || dir.isBlank() ? "jdbc:h2:mem:" : "jdbc:h2:file:" + java.nio.file.Path.of(dir, "taxes").toAbsolutePath();
    }

    /**
     * The tax rate for a destination, as a percentage: 8.75 means 8.75%. US postal codes starting with 9 are
     * taxed at 8.75%, every other US destination at 6%. We have no nexus outside the US, so nothing is charged there.
     */
    public static BigDecimal ratePercent(String countryCode, String postalCode) {
        if (!"US".equals(countryCode) || postalCode == null || postalCode.isBlank()) {
            return ZERO_RATE;
        }
        return postalCode.trim().charAt(0) == '9' ? new BigDecimal("8.75") : new BigDecimal("6.00");
    }

    /** Rounds to cents, half up. */
    static BigDecimal cents(BigDecimal amount) {
        return amount.setScale(2, RoundingMode.HALF_UP);
    }

    /**
     * Net and gross for one amount. When prices are entered with tax the amount is the gross and the net is
     * taken out of it; otherwise the amount is the net and tax is added on top.
     */
    static BigDecimal[] split(BigDecimal amount, BigDecimal ratePercent, boolean pricesEnteredWithTax) {
        BigDecimal factor = BigDecimal.ONE.add(ratePercent.divide(HUNDRED));
        if (pricesEnteredWithTax) {
            return new BigDecimal[] {cents(amount.divide(factor, 10, RoundingMode.HALF_UP)), cents(amount)};
        }
        return new BigDecimal[] {cents(amount), cents(amount.multiply(factor))};
    }

    /** Answers a CalculateTaxes event. Each line is taxed and rounded on its own; shipping is not taxed. */
    @SuppressWarnings("unchecked")
    public Map<String, Object> calculate(Map<String, Object> payload) {
        Map<String, Object> base = (Map<String, Object>) need(payload, "taxBase");
        boolean withTax = (Boolean) need(base, "pricesEnteredWithTax");
        Map<String, Object> address = (Map<String, Object>) base.get("address");
        BigDecimal rate = address == null ? ZERO_RATE
                : ratePercent((String) ((Map<String, Object>) need(address, "country")).get("code"), (String) address.get("postalCode"));
        List<Map<String, Object>> lines = new ArrayList<>();
        for (Map<String, Object> line : (List<Map<String, Object>>) need(base, "lines")) {
            BigDecimal lineRate = Boolean.FALSE.equals(line.get("chargeTaxes")) ? ZERO_RATE : rate;
            BigDecimal[] netGross = split(amount(need(line, "totalPrice")), lineRate, withTax);
            Map<String, Object> out = new LinkedHashMap<>();
            out.put("tax_rate", lineRate);
            out.put("total_net_amount", netGross[0]);
            out.put("total_gross_amount", netGross[1]);
            lines.add(out);
        }
        BigDecimal shipping = cents(amount(need(base, "shippingPrice")));
        Map<String, Object> answer = new LinkedHashMap<>();
        answer.put("shipping_tax_rate", ZERO_RATE);
        answer.put("shipping_price_net_amount", shipping);
        answer.put("shipping_price_gross_amount", shipping);
        answer.put("lines", lines);
        return answer;
    }

    /** Handles ORDER_CREATED (commit a tax document) and ORDER_CANCELLED (void it). Safe to repeat. */
    @SuppressWarnings("unchecked")
    public synchronized void orderEvent(Map<String, Object> payload) {
        Map<String, Object> order = (Map<String, Object>) need(payload, "order");
        String id = (String) need(order, "id");
        if ("OrderCancelled".equals(payload.get("__typename"))) {
            update("UPDATE tax_documents SET status = 'voided' WHERE order_id = ?", id);
            return;
        }
        Map<String, Object> total = (Map<String, Object>) need(order, "total");
        Map<String, Object> address = (Map<String, Object>) order.get("shippingAddress");
        if (documents().stream().noneMatch(d -> d.get("order_id").equals(id))) {
            update("INSERT INTO tax_documents (order_id, order_number, tax, gross, postal_code, status) VALUES (?, ?, ?, ?, ?, 'committed')",
                    id, String.valueOf(need(order, "number")), cents(amount(need(total, "tax"))), cents(amount(need(total, "gross"))),
                    address == null ? null : address.get("postalCode"));
        }
    }

    public synchronized List<Map<String, Object>> documents() {
        try (PreparedStatement s = db.prepareStatement("SELECT order_id, order_number, tax, gross, postal_code, status "
                + "FROM tax_documents ORDER BY CAST(order_number AS INT)"); ResultSet r = s.executeQuery()) {
            List<Map<String, Object>> out = new ArrayList<>();
            while (r.next()) {
                Map<String, Object> d = new LinkedHashMap<>();
                d.put("order_id", r.getString(1));
                d.put("order_number", r.getString(2));
                d.put("tax", r.getBigDecimal(3));
                d.put("gross", r.getBigDecimal(4));
                d.put("postal_code", r.getString(5));
                d.put("status", r.getString(6));
                out.add(d);
            }
            return out;
        } catch (SQLException e) {
            throw new IllegalStateException(e.getMessage(), e);
        }
    }

    private void update(String sql, Object... args) {
        try (PreparedStatement s = db.prepareStatement(sql)) {
            for (int i = 0; i < args.length; i++) {
                s.setObject(i + 1, args[i]);
            }
            s.executeUpdate();
        } catch (SQLException e) {
            throw new IllegalStateException(e.getMessage(), e);
        }
    }

    private static Object need(Map<String, Object> map, String key) {
        Object value = map == null ? null : map.get(key);
        if (value == null) {
            throw new BadPayload(key + " is missing from the payload");
        }
        return value;
    }

    /** The `amount` of a Money object, which Core sends as a decimal number in major units. */
    @SuppressWarnings("unchecked")
    private static BigDecimal amount(Object money) {
        Object value = money instanceof Map ? ((Map<String, Object>) money).get("amount") : null;
        if (!(value instanceof Number)) {
            throw new BadPayload("a money amount is missing from the payload");
        }
        return new BigDecimal(value.toString());
    }
}
