// Supabase Edge Function: categorize
// Bulk-categorizes item names into Penny Hunter's category taxonomy
// using Claude Haiku. Designed for the daily backend briefing pipeline.
// POST /functions/v1/categorize  body: { items: string[] }

const HEADERS = {
  'Content-Type': 'application/json; charset=utf-8',
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

const ANTHROPIC_URL = 'https://api.anthropic.com/v1/messages';
const ANTHROPIC_VERSION = '2023-06-01';
const MODEL = 'claude-haiku-4-5';

const CATEGORIES = [
  'tools', 'beauty', 'food', 'pet', 'home', 'tech',
  'apparel', 'toys', 'seasonal', 'books', 'garden', 'health',
];

const SYSTEM = `You are a retail product categorizer. For each product name, output ONE category from this list:
${CATEGORIES.join(', ')}

Output rules:
- Return ONLY a JSON array of category strings, same length and order as input.
- No prose, no code fences, no explanations.
- Default to "home" when unsure.

Hints:
- tools: drills, hammers, wrenches, fasteners
- beauty: cosmetics, fragrance, hair, skin, deodorant
- food: snacks, drinks, candy, pantry
- pet: pet food, toys, supplies (overrides "food")
- home: cleaning, decor, kitchen, bedding (DEFAULT)
- tech: cables, chargers, audio, gadgets, batteries
- apparel: clothing, shoes, hats
- toys: kids' toys, games, puzzles
- seasonal: holiday, party, summer/winter
- books: books, paper, office
- garden: plants, lawn, patio, outdoor
- health: vitamins, OTC, first-aid`;

Deno.serve(async (req: Request) => {
  if (req.method === 'OPTIONS') return new Response(null, { headers: HEADERS, status: 204 });
  if (req.method !== 'POST') return j({ error: 'POST required' }, 405);

  // Rate limit: 100 calls/day per IP (max ~25K items/day per caller).
  // Protects the Anthropic budget from runaway clients with the anon key.
  const rl = await checkRateLimit(clientIp(req), 'categorize', 100);
  if (!rl.ok) return j({ error: 'rate limit exceeded', retry_after_sec: rl.resetIn }, 429);

  let body: any;
  try {
    body = await req.json();
  } catch {
    return j({ error: 'invalid JSON' }, 400);
  }
  const items: string[] = Array.isArray(body?.items) ? body.items.map(String) : [];
  if (items.length === 0) return j({ categories: [], usage: null });
  if (items.length > 250) return j({ error: 'max 250 items per call' }, 400);

  const key = Deno.env.get('ANTHROPIC_API_KEY') ?? '';
  if (!key) return j({ error: 'ANTHROPIC_API_KEY not set' }, 503);

  const prompt = `Categorize these ${items.length} products. Return a JSON array of exactly ${items.length} category strings, in input order:\n\n${items
    .map((it, i) => `${i + 1}. ${it.slice(0, 200)}`)
    .join('\n')}`;

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
        max_tokens: Math.min(4096, 50 + items.length * 8),
        system: SYSTEM,
        temperature: 0,
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

  let categories: string[];
  try {
    categories = JSON.parse(cleaned);
  } catch {
    return j({ error: 'Claude returned non-JSON', raw: text.slice(0, 200) }, 502);
  }

  const valid = new Set(CATEGORIES);
  categories = categories.map((c) => (typeof c === 'string' && valid.has(c) ? c : 'home'));
  while (categories.length < items.length) categories.push('home');
  if (categories.length > items.length) categories = categories.slice(0, items.length);

  return j({ categories, usage: json?.usage });
});

function j(body: any, status = 200): Response {
  return new Response(JSON.stringify(body), { headers: HEADERS, status });
}

// ── Rate limit helper (inlined; see _shared/rate_limit_inline.md) ──
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
        if (arr[0].count >= perDayCap) {
          return { ok: false, resetIn: Math.ceil((dayMs - age) / 1000) };
        }
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
