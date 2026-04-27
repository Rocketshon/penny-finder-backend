# Inline rate-limit helper (copy/paste into each Anthropic-backed edge fn)

Supabase Management API doesn't bundle multi-file deploys, so each
function inlines this helper rather than importing it. Keep the bodies
in sync.

```ts
// Per-IP daily rate limit. Buckets are 24h windows starting from the
// first call. Caller passes a per-fn key like 'categorize' so quotas
// don't cross-contaminate.
async function checkRateLimit(
  ip: string,
  fn: string,
  perDayCap: number
): Promise<{ ok: true } | { ok: false; resetIn: number }> {
  const SUPABASE_URL = Deno.env.get('SUPABASE_URL') ?? '';
  const SERVICE_ROLE = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? '';
  if (!SUPABASE_URL || !SERVICE_ROLE) return { ok: true }; // fail-open
  const bucket = `${fn}:${ip}`;
  const headers = {
    apikey: SERVICE_ROLE,
    Authorization: `Bearer ${SERVICE_ROLE}`,
    'Content-Type': 'application/json',
    Prefer: 'resolution=merge-duplicates,return=representation',
  };
  try {
    // Read existing row
    const r = await fetch(
      `${SUPABASE_URL}/rest/v1/edge_rate_limits?bucket=eq.${encodeURIComponent(bucket)}&select=count,window_start`,
      { headers: { apikey: SERVICE_ROLE, Authorization: `Bearer ${SERVICE_ROLE}` } }
    );
    const arr = r.ok ? await r.json() : [];
    const now = Date.now();
    const dayMs = 24 * 60 * 60 * 1000;

    if (arr[0]) {
      const ageMs = now - new Date(arr[0].window_start).getTime();
      if (ageMs < dayMs) {
        if (arr[0].count >= perDayCap) {
          return { ok: false, resetIn: Math.ceil((dayMs - ageMs) / 1000) };
        }
        // Increment
        await fetch(`${SUPABASE_URL}/rest/v1/edge_rate_limits?bucket=eq.${encodeURIComponent(bucket)}`, {
          method: 'PATCH',
          headers,
          body: JSON.stringify({ count: arr[0].count + 1 }),
        });
        return { ok: true };
      }
    }
    // New window
    await fetch(`${SUPABASE_URL}/rest/v1/edge_rate_limits`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ bucket, count: 1, window_start: new Date().toISOString() }),
    });
    return { ok: true };
  } catch {
    return { ok: true }; // fail-open on error — never block legitimate users
  }
}

function clientIp(req: Request): string {
  return (
    req.headers.get('cf-connecting-ip') ||
    req.headers.get('x-forwarded-for')?.split(',')[0]?.trim() ||
    'unknown'
  );
}
```

Usage at top of `Deno.serve`:

```ts
const rl = await checkRateLimit(clientIp(req), 'categorize', 100);
if (!rl.ok) {
  return j({ error: 'rate limit', retry_after: rl.resetIn }, 429);
}
```

Per-fn caps (per-IP per-day):
- categorize: 100 calls/day → max ~25K items/day per IP
- resale-estimate: 200 calls/day
- receipt-ocr: 30 calls/day (vision is expensive)
