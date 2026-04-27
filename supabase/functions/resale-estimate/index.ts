// Supabase Edge Function: resale-estimate
// Given a product name + UPC, asks Claude Sonnet to estimate the eBay
// sold-listings price range. Caches per-UPC for 30 days.

const HEADERS = {
  'Content-Type': 'application/json; charset=utf-8',
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

const ANTHROPIC_URL = 'https://api.anthropic.com/v1/messages';
const ANTHROPIC_VERSION = '2023-06-01';
const MODEL = 'claude-sonnet-4-5';

const SUPABASE_URL = Deno.env.get('SUPABASE_URL') ?? '';
const SERVICE_ROLE = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? '';
const TTL_MS = 30 * 24 * 60 * 60 * 1000;

const SYSTEM = `You are a retail-arbitrage analyst. Estimate the typical eBay sold-listings price range for a consumer product. Use general retail knowledge — don't invent specific listings.

Return ONLY a JSON object:
{ "avg": <number>, "low": <number>, "high": <number>, "currency": "USD", "take": "<one short sentence>" }

Rules:
- USD numbers, no symbols
- avg = realistic median sold price; low/high = typical range, not outliers
- take = 8-15 words, plain English: "is this worth flipping?"
- Items with near-zero resale value (consumables, food, hygiene): all 0 + take "Not worth flipping"
- Unidentifiable: all 0 + take "Unable to identify this item"`;

Deno.serve(async (req: Request) => {
  if (req.method === 'OPTIONS') return new Response(null, { headers: HEADERS, status: 204 });
  if (req.method !== 'POST') return j({ error: 'POST required' }, 405);

  const rl = await checkRateLimit(clientIp(req), 'resale-estimate', 200);
  if (!rl.ok) return j({ error: 'rate limit exceeded', retry_after_sec: rl.resetIn }, 429);

  let body: any;
  try {
    body = await req.json();
  } catch {
    return j({ error: 'invalid JSON' }, 400);
  }
  const name = String(body?.name ?? '').slice(0, 200);
  const upc = String(body?.upc ?? '').slice(0, 14);
  if (!name && !upc) return j({ error: 'name or upc required' }, 400);

  const cacheKey = (upc || `name:${name.toLowerCase()}`).slice(0, 255);
  const cached = await getCached(cacheKey);
  if (cached && Date.now() - new Date(cached.fetched_at).getTime() < TTL_MS) {
    return j({ ...cached.estimate, cache: 'hit' });
  }

  const key = Deno.env.get('ANTHROPIC_API_KEY') ?? '';
  if (!key) return j({ error: 'ANTHROPIC_API_KEY not set' }, 503);

  const prompt = `Product: ${name}${upc ? ` (UPC ${upc})` : ''}\n\nWhat's the typical eBay sold range?`;

  let res: Response;
  try {
    res = await fetch(ANTHROPIC_URL, {
      method: 'POST',
      headers: {
        'x-api-key': key,
        'anthropic-version': ANTHROPIC_VERSION,
        'content-type': 'application/json',
      },
      body: JSON.stringify({
        model: MODEL,
        max_tokens: 200,
        system: SYSTEM,
        temperature: 0.3,
        messages: [{ role: 'user', content: prompt }],
      }),
    });
  } catch (e) {
    return j({ error: 'anthropic fetch failed', detail: String(e) }, 502);
  }

  const json: any = await res.json();
  if (!res.ok) return j({ error: json?.error?.message ?? `HTTP ${res.status}` }, 502);

  const text: string =
    (json?.content || []).map((c: any) => (c?.type === 'text' ? c.text : '')).join('') ?? '';
  const cleaned = text.trim().replace(/^```(?:json)?\s*|\s*```$/g, '');

  let estimate: any;
  try {
    estimate = JSON.parse(cleaned);
  } catch {
    return j({ error: 'Claude returned non-JSON', raw: text.slice(0, 200) }, 502);
  }

  const safe = {
    avg: Number.isFinite(estimate?.avg) ? Math.max(0, Number(estimate.avg)) : 0,
    low: Number.isFinite(estimate?.low) ? Math.max(0, Number(estimate.low)) : 0,
    high: Number.isFinite(estimate?.high) ? Math.max(0, Number(estimate.high)) : 0,
    currency: 'USD',
    take: typeof estimate?.take === 'string' ? estimate.take.slice(0, 200) : '',
  };

  await putCached(cacheKey, safe).catch(() => {});
  return j({ ...safe, cache: 'miss' });
});

function j(body: any, status = 200): Response {
  return new Response(JSON.stringify(body), { headers: HEADERS, status });
}

// ── Rate limit (inlined; see _shared/rate_limit_inline.md) ──
async function checkRateLimit(
  ip: string,
  fn: string,
  perDayCap: number
): Promise<{ ok: true } | { ok: false; resetIn: number }> {
  if (!SUPABASE_URL || !SERVICE_ROLE) return { ok: true };
  const bucket = `${fn}:${ip}`;
  const auth = { apikey: SERVICE_ROLE, Authorization: `Bearer ${SERVICE_ROLE}` };
  try {
    const r = await fetch(
      `${SUPABASE_URL}/rest/v1/edge_rate_limits?bucket=eq.${encodeURIComponent(bucket)}&select=count,window_start`,
      { headers: auth }
    );
    const arr = r.ok ? await r.json() : [];
    const now = Date.now();
    const dayMs = 86400000;
    if (arr[0]) {
      const age = now - new Date(arr[0].window_start).getTime();
      if (age < dayMs) {
        if (arr[0].count >= perDayCap) return { ok: false, resetIn: Math.ceil((dayMs - age) / 1000) };
        await fetch(`${SUPABASE_URL}/rest/v1/edge_rate_limits?bucket=eq.${encodeURIComponent(bucket)}`, {
          method: 'PATCH',
          headers: { ...auth, 'Content-Type': 'application/json' },
          body: JSON.stringify({ count: arr[0].count + 1 }),
        });
        return { ok: true };
      }
    }
    await fetch(`${SUPABASE_URL}/rest/v1/edge_rate_limits`, {
      method: 'POST',
      headers: { ...auth, 'Content-Type': 'application/json', Prefer: 'resolution=merge-duplicates' },
      body: JSON.stringify({ bucket, count: 1, window_start: new Date().toISOString() }),
    });
    return { ok: true };
  } catch {
    return { ok: true };
  }
}

function clientIp(req: Request): string {
  return (
    req.headers.get('cf-connecting-ip') ||
    req.headers.get('x-forwarded-for')?.split(',')[0]?.trim() ||
    'unknown'
  );
}

async function getCached(cacheKey: string): Promise<{ estimate: any; fetched_at: string } | null> {
  if (!SUPABASE_URL || !SERVICE_ROLE) return null;
  try {
    const r = await fetch(
      `${SUPABASE_URL}/rest/v1/resale_estimates?cache_key=eq.${encodeURIComponent(cacheKey)}&select=estimate,fetched_at`,
      { headers: { apikey: SERVICE_ROLE, Authorization: `Bearer ${SERVICE_ROLE}` } }
    );
    if (!r.ok) return null;
    const arr = await r.json();
    return arr[0] ?? null;
  } catch {
    return null;
  }
}

async function putCached(cacheKey: string, estimate: any): Promise<void> {
  if (!SUPABASE_URL || !SERVICE_ROLE) return;
  await fetch(`${SUPABASE_URL}/rest/v1/resale_estimates`, {
    method: 'POST',
    headers: {
      apikey: SERVICE_ROLE,
      Authorization: `Bearer ${SERVICE_ROLE}`,
      'Content-Type': 'application/json',
      Prefer: 'resolution=merge-duplicates',
    },
    body: JSON.stringify({ cache_key: cacheKey, estimate, fetched_at: new Date().toISOString() }),
  });
}
