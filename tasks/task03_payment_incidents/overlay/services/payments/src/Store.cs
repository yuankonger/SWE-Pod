using System.Text.Json;
using Microsoft.Data.Sqlite;

namespace Seedco.Payments;

/// <summary>
/// The payments database (SQLite). Each table holds one kind of record as JSON, with one column to look records
/// up by. With SEEDCO_DATA_DIR set the database is a file there and survives a restart; without it, it is in memory.
/// </summary>
public class Store : IDisposable
{
    public static readonly JsonSerializerOptions Json = new() { PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower };
    private readonly SqliteConnection _db;
    private readonly object _lock = new();

    public Store(string? path = null, params string[] tables)
    {
        _db = new SqliteConnection(path is null ? "Data Source=:memory:" : $"Data Source={path}");
        _db.Open();
        foreach (var t in tables)
            Run($"CREATE TABLE IF NOT EXISTS {t} (seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE, lookup TEXT, body TEXT NOT NULL)");
        Run("CREATE TABLE IF NOT EXISTS settings (name TEXT PRIMARY KEY, value TEXT NOT NULL)");
    }

    public static string? DefaultPath(string file)
    {
        var dir = Environment.GetEnvironmentVariable("SEEDCO_DATA_DIR");
        if (string.IsNullOrEmpty(dir)) return null;
        Directory.CreateDirectory(dir);
        return Path.Combine(dir, file);
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
    public void Put<T>(string table, string id, string? lookup, T record) =>
        Run($"INSERT INTO {table} (id, lookup, body) VALUES ($0, $1, $2) ON CONFLICT(id) DO UPDATE SET lookup = $1, body = $2",
            id, lookup, JsonSerializer.Serialize(record, Json));

    /// <summary>Writes a new record. The id must not be in the table yet.</summary>
    public void Add<T>(string table, string id, string? lookup, T record) =>
        Run($"INSERT INTO {table} (id, lookup, body) VALUES ($0, $1, $2)", id, lookup, JsonSerializer.Serialize(record, Json));

    public T? Get<T>(string table, string id) where T : class =>
        Column($"SELECT body FROM {table} WHERE id = $0", id).Select(b => JsonSerializer.Deserialize<T>(b, Json)).FirstOrDefault();

    /// <summary>Records in the order they were first written, optionally with one lookup value.</summary>
    public List<T> List<T>(string table, string? lookup = null) =>
        Column($"SELECT body FROM {table} WHERE ($0 IS NULL OR lookup = $0) ORDER BY seq", lookup)
            .Select(b => JsonSerializer.Deserialize<T>(b, Json)!).ToList();

    public string? Setting(string name) => Column("SELECT value FROM settings WHERE name = $0", name).FirstOrDefault();
    public void SetSetting(string name, string value) => Run("INSERT OR REPLACE INTO settings VALUES ($0, $1)", name, value);

    public void Dispose() => _db.Dispose();
}
