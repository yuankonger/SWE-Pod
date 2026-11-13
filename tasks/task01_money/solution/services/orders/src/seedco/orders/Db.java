package seedco.orders;

import com.fasterxml.jackson.core.JsonGenerator;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * The Orders database (H2, embedded). Orders and outbox events are stored as JSON with the columns we look them up
 * by; the catalogue and carts are plain tables. With SEEDCO_DATA_DIR set the database is a file there and survives
 * a restart; without it, it lives in memory.
 */
public class Db implements AutoCloseable {
    public static final ObjectMapper JSON = new ObjectMapper()
            .enable(DeserializationFeature.USE_BIG_DECIMAL_FOR_FLOATS)
            .enable(DeserializationFeature.USE_LONG_FOR_INTS)
            .enable(JsonGenerator.Feature.WRITE_BIGDECIMAL_AS_PLAIN);
    static final TypeReference<Map<String, Object>> MAP = new TypeReference<>() { };

    private static final String[] SCHEMA = {
        "CREATE TABLE IF NOT EXISTS products (position INT PRIMARY KEY, sku VARCHAR(32) UNIQUE NOT NULL, "
            + "name VARCHAR(128) NOT NULL, unit_price BIGINT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS orders (seq BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, "
            + "id VARCHAR(64) UNIQUE NOT NULL, customer_id VARCHAR(128) NOT NULL, body CLOB NOT NULL)",
        "CREATE TABLE IF NOT EXISTS cart_items (customer_id VARCHAR(128) NOT NULL, sku VARCHAR(32) NOT NULL, "
            + "qty INT NOT NULL, PRIMARY KEY (customer_id, sku))",
        "CREATE TABLE IF NOT EXISTS idempotency (idem_key VARCHAR(128) PRIMARY KEY, order_id VARCHAR(64) NOT NULL)",
        "CREATE TABLE IF NOT EXISTS outbox (seq BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, "
            + "topic VARCHAR(64) NOT NULL, body CLOB NOT NULL, published BOOLEAN DEFAULT FALSE NOT NULL)",
    };

    /** One row of a result set, by column position (1-based). */
    public interface Row<T> {
        T read(ResultSet r) throws SQLException;
    }

    private final Connection connection;

    public Db(String url) {
        try {
            connection = DriverManager.getConnection(url);
            for (String sql : SCHEMA) {
                update(sql);
            }
        } catch (SQLException e) {
            throw new IllegalStateException("cannot open the orders database: " + e.getMessage(), e);
        }
    }

    public static Db inMemory() {
        return new Db("jdbc:h2:mem:");
    }

    public static Db fromEnvironment() {
        String dir = System.getenv("SEEDCO_DATA_DIR");
        return dir == null || dir.isBlank() ? inMemory() : file(Path.of(dir, "orders"));
    }

    public static Db file(Path path) {
        return new Db("jdbc:h2:file:" + path.toAbsolutePath());
    }

    public synchronized int update(String sql, Object... args) {
        try (PreparedStatement s = prepare(sql, args)) {
            return s.executeUpdate();
        } catch (SQLException e) {
            throw new IllegalStateException(e.getMessage(), e);
        }
    }

    public synchronized <T> List<T> query(String sql, Row<T> row, Object... args) {
        try (PreparedStatement s = prepare(sql, args); ResultSet r = s.executeQuery()) {
            List<T> out = new ArrayList<>();
            while (r.next()) {
                out.add(row.read(r));
            }
            return out;
        } catch (SQLException e) {
            throw new IllegalStateException(e.getMessage(), e);
        }
    }

    private PreparedStatement prepare(String sql, Object... args) throws SQLException {
        PreparedStatement s = connection.prepareStatement(sql);
        for (int i = 0; i < args.length; i++) {
            s.setObject(i + 1, args[i]);
        }
        return s;
    }

    public static String json(Object value) {
        try {
            return JSON.writeValueAsString(value);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException(e);
        }
    }

    public static Map<String, Object> map(String json) {
        try {
            return JSON.readValue(json, MAP);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException(e);
        }
    }

    public void seedProduct(int position, String sku, String name, long unitPrice) {
        if (query("SELECT 1 FROM products WHERE sku = ?", r -> 1, sku).isEmpty()) {
            update("INSERT INTO products (position, sku, name, unit_price) VALUES (?, ?, ?, ?)", position, sku, name, unitPrice);
        }
    }

    @Override
    public synchronized void close() {
        try {
            connection.close();
        } catch (SQLException e) {
            throw new IllegalStateException(e);
        }
    }
}
