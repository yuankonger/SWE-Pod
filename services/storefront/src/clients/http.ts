// One way to call another service: JSON in, JSON out, a timeout, and an error that keeps the upstream status.

export class Upstream extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown) {
    super("upstream " + status);
    this.status = status;
    this.body = body;
  }
}

const TIMEOUT_MS = 10_000;

export async function call<T = any>(url: string, method = "GET", body?: unknown, headers: Record<string, string> = {}): Promise<T> {
  const res = await fetch(url, {
    method,
    headers: body === undefined ? headers : { "Content-Type": "application/json", ...headers },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });
  const parsed = await res.json().catch(() => null);
  if (!res.ok) throw new Upstream(res.status, parsed);
  return parsed as T;
}
