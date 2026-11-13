using System.Text.Json;
using Microsoft.Data.Sqlite;

namespace Seedco.Billing;

/// <summary>
/// The Billing database (SQLite). Each table holds one kind of record as JSON, with the columns we look records
/// up by. With SEEDCO_DATA_DIR set the database is a file there and survives a restart; without it, it is in memory.
/// </summary>
public class Store : IDisposable
{
    public static readonly JsonSerializerOptions Json = new() { PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower };
    private static readonly string[] Tables = ["payments", "invoices", "refunds", "subscriptions"];
    private readonly SqliteConnection _db;
    private readonly object _lock = new();

    public Store(string? path = null)
    {
        _db = new SqliteConnection(path is null ? "Data Source=:memory:" : $"Data Source={path}");
        _db.Open();
        foreach (var t in Tables)
            Run($"CREATE TABLE IF NOT EXISTS {t} (seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE, " +
                "order_id TEXT, customer_id TEXT, body TEXT NOT NULL)");
        Run("CREATE TABLE IF NOT EXISTS seen_events (event_id TEXT PRIMARY KEY)");
        Run("CREATE TABLE IF NOT EXISTS idempotency (key TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, payment_id TEXT NOT NULL)");
        Run("CREATE TABLE IF NOT EXISTS offsets (topic TEXT PRIMARY KEY, next_offset INTEGER NOT NULL)");
    }

    public static string? DefaultPath()
    {
        var dir = Environment.GetEnvironmentVariable("SEEDCO_DATA_DIR");
        if (string.IsNullOrEmpty(dir)) return null;
        Directory.CreateDirectory(dir);
        return Path.Combine(dir, "billing.db");
    }

    private SqliteCommand Command(string sql, params object?[] args)
    {
        var c = _db.CreateCommand();
        c.CommandText = sql;
        for (var i = 0; i < args.Length; i++) c.Parameters.AddWithValue("$" + i, args[i] ?? DBNull.Value);
        return c;
    }

    private void Run(string sql, params object?[] args)
    {
        lock (_lock) { using var c = Command(sql, args); c.ExecuteNonQuery(); }
    }

    private List<string> Column(string sql, params object?[] args)
    {
        lock (_lock)
        {
            using var c = Command(sql, args);
            using var r = c.ExecuteReader();
            var rows = new List<string>();
            while (r.Read()) rows.Add(r.GetString(0));
            return rows;
        }
    }

    /// <summary>Inserts the record, or replaces the one with the same id.</summary>
    public void Put<T>(string table, string id, string? orderId, string? customerId, T record) =>
        Run($"INSERT INTO {table} (id, order_id, customer_id, body) VALUES ($0, $1, $2, $3) " +
            "ON CONFLICT(id) DO UPDATE SET body = $3", id, orderId, customerId, JsonSerializer.Serialize(record, Json));

    public T? Get<T>(string table, string id) where T : class =>
        Column($"SELECT body FROM {table} WHERE id = $0", id).Select(b => JsonSerializer.Deserialize<T>(b, Json)).FirstOrDefault();

    /// <summary>Records in the order they were first written, optionally for one order or one customer.</summary>
    public List<T> List<T>(string table, string? orderId = null, string? customerId = null) =>
        Column($"SELECT body FROM {table} WHERE ($0 IS NULL OR order_id = $0) AND ($1 IS NULL OR customer_id = $1) ORDER BY seq",
            orderId, customerId).Select(b => JsonSerializer.Deserialize<T>(b, Json)!).ToList();

    /// <summary>True the first time an event id is seen.</summary>
    public bool FirstSight(string eventId)
    {
        lock (_lock)
        {
            using var c = Command("INSERT OR IGNORE INTO seen_events VALUES ($0)", eventId);
            return c.ExecuteNonQuery() == 1;
        }
    }

    public (string Fingerprint, string PaymentId)? Idempotent(string key)
    {
        var row = Column("SELECT fingerprint || '|' || payment_id FROM idempotency WHERE key = $0", key).FirstOrDefault();
        if (row is null) return null;
        var cut = row.LastIndexOf('|');
        return (row[..cut], row[(cut + 1)..]);
    }

    public void RememberIdempotent(string key, string fingerprint, string paymentId) =>
        Run("INSERT OR REPLACE INTO idempotency VALUES ($0, $1, $2)", key, fingerprint, paymentId);

    public int Offset(string topic) =>
        Column("SELECT CAST(next_offset AS TEXT) FROM offsets WHERE topic = $0", topic).Select(int.Parse).FirstOrDefault();

    public void SetOffset(string topic, int next) => Run("INSERT OR REPLACE INTO offsets VALUES ($0, $1)", topic, next);

    public void Dispose() => _db.Dispose();
}
