// Supabase Edge Function: receipt-ocr
// Claude Vision parses a receipt photo into structured items.
// POST /functions/v1/receipt-ocr  body: { image_base64: "...", media_type?: "image/jpeg" }
// Returns: { storeName, total, items: [{name, price, qty?}], date?, raw }

const HEADERS = {
  'Content-Type': 'application/json; charset=utf-8',
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

const ANTHROPIC_URL = 'https://api.anthropic.com/v1/messages';
const ANTHROPIC_VERSION = '2023-06-01';
const MODEL = 'claude-sonnet-4-5';

const SYSTEM = `You are a receipt parser. Given a photo of a retail receipt, extract structured data and return ONLY a JSON object — no prose, no code fences:

{
  "storeName": "<retailer name as printed>",
  "total": <number, the receipt total>,
  "items": [{ "name": "<item name>", "price": <number>, "qty": <number, default 1> }],
  "date": "<YYYY-MM-DD if visible, otherwise null>"
}

Rules:
- Prices in USD as decimal numbers, no symbols (e.g. 4.99 not "$4.99")
- Skip non-item lines (subtotal, tax, total, discount lines unless they're per-item)
- Item names: short, what's printed (don't expand abbreviations)
- If you can't read the receipt at all, return: { "error": "unreadable" }
- Quantity defaults to 1 if not shown
- Total = the final amount paid, including tax`;

Deno.serve(async (req: Request) => {
  if (req.method === 'OPTIONS') return new Response(null, { headers: HEADERS, status: 204 });
  if (req.method !== 'POST') return j({ error: 'POST required' }, 405);

  // Receipt OCR is the most expensive call (Sonnet Vision). Lower per-day cap.
  const rl = await checkRateLimit(clientIp(req), 'receipt-ocr', 30);
  if (!rl.ok) return j({ error: 'rate limit exceeded', retry_after_sec: rl.resetIn }, 429);

  let body: any;
  try {
    body = await req.json();
  } catch {
    return j({ error: 'invalid JSON' }, 400);
  }

  const image_base64 = String(body?.image_base64 ?? '');
  const media_type = String(body?.media_type ?? 'image/jpeg');
  if (!image_base64 || image_base64.length < 100) {
    return j({ error: 'image_base64 required (full base64 string, no data: prefix)' }, 400);
  }
  // Hard cap to keep costs predictable + avoid attacking the API
  if (image_base64.length > 7_000_000) {
    return j({ error: 'image too large — max ~5MB base64' }, 413);
  }

  const key = Deno.env.get('ANTHROPIC_API_KEY') ?? '';
  if (!key) return j({ error: 'ANTHROPIC_API_KEY not set' }, 503);

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
        max_tokens: 1500,
        system: SYSTEM,
        temperature: 0,
        messages: [
          {
            role: 'user',
            content: [
              {
                type: 'image',
                source: { type: 'base64', media_type, data: image_base64 },
              },
              { type: 'text', text: 'Parse this receipt.' },
            ],
          },
        ],
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

  let parsed: any;
  try {
    parsed = JSON.parse(cleaned);
  } catch {
    return j({ error: 'Claude returned non-JSON', raw: text.slice(0, 200) }, 502);
  }

  if (parsed?.error) return j({ error: parsed.error }, 422);

  // Sanitize
  const items = Array.isArray(parsed?.items)
    ? parsed.items.map((it: any) => ({
        name: String(it?.name ?? '').slice(0, 100),
        price: Number.isFinite(it?.price) ? Math.max(0, Number(it.price)) : 0,
        qty: Number.isFinite(it?.qty) && it.qty > 0 ? Math.floor(it.qty) : 1,
      })).filter((it: any) => it.name)
    : [];

  return j({
    storeName: String(parsed?.storeName ?? '').slice(0, 100),
    total: Number.isFinite(parsed?.total) ? Math.max(0, Number(parsed.total)) : 0,
    items,
    date: typeof parsed?.date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(parsed.date) ? parsed.date : null,
    usage: json?.usage,
  });
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
  const SUPABASE_URL = Deno.env.get('SUPABASE_URL') ?? '';
  const SERVICE_ROLE = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? '';
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
