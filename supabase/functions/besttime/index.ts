// Supabase Edge Function: besttime
//
// Proxies BestTime API calls so the private API key stays server-side.
// The app sends chain name + user location; we return a simplified
// busyness forecast for the nearest venue.
//
// Endpoint:
//   GET /functions/v1/besttime?chain=Dollar+General&address=Mount+Clemens+MI
//
// Caches successful responses in `besttime_forecasts` table for 7 days
// via Supabase REST (no SDK import — keeps cold-start fast and avoids
// dep-resolution flakiness on edge runtime).

const BT_BASE = 'https://besttime.app/api/v1';
const BT_KEY = Deno.env.get('BESTTIME_API_KEY_PRIVATE') ?? '';
const SUPABASE_URL = Deno.env.get('SUPABASE_URL') ?? '';
const SERVICE_ROLE = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? '';

const HEADERS: Record<string, string> = {
  'Cache-Control': 'public, max-age=3600, stale-while-revalidate=86400',
  'Content-Type': 'application/json; charset=utf-8',
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

const CACHE_TTL_MS = 7 * 24 * 60 * 60 * 1000;

Deno.serve(async (req: Request) => {
  if (req.method === 'OPTIONS') return new Response(null, { headers: HEADERS, status: 204 });

  const url = new URL(req.url);
  const chain = url.searchParams.get('chain') || '';
  const address = url.searchParams.get('address') || '';

  if (!chain || !address) return j({ error: 'chain and address are required' }, 400);
  if (!BT_KEY) return j({ error: 'BestTime not configured' }, 503);

  const cacheKey = `${chain.toLowerCase()}|${address.toLowerCase()}`.slice(0, 255);

  // Cache lookup via PostgREST. Treat null/empty forecasts as misses so
  // a transient upstream blip doesn't poison the cache for 7 days. We
  // also cache permanent-failure sentinels separately (see below) with
  // a shorter TTL so unhuntable chains don't burn quota every request.
  const cached = await getCached(cacheKey);
  if (cached) {
    const age = Date.now() - new Date(cached.fetched_at).getTime();
    const f: any = cached.forecast;
    const isFailureSentinel = f && f.error === 'no_forecast';
    const isEmpty =
      !f || (Array.isArray(f.hourlyBusyness) &&
             f.hourlyBusyness.every((row: any) => !Array.isArray(row) || row.every((v: any) => v == null)));
    const failTtl = 24 * 60 * 60 * 1000; // 24h for known-bad chains
    if (isFailureSentinel && age < failTtl) {
      return j({ error: 'no_forecast', cache: 'hit' }, 200);
    }
    if (!isEmpty && !isFailureSentinel && age < CACHE_TTL_MS) {
      return j({ ...cached.forecast, cache: 'hit' });
    }
  }

  // Fetch fresh
  const btUrl =
    `${BT_BASE}/forecasts?api_key_private=${encodeURIComponent(BT_KEY)}` +
    `&venue_name=${encodeURIComponent(chain)}` +
    `&venue_address=${encodeURIComponent(address)}`;

  let btJson: any;
  let httpStatus = 0;
  try {
    const r = await fetch(btUrl, { method: 'POST' });
    httpStatus = r.status;
    btJson = await r.json();
  } catch (e) {
    return j({ error: 'upstream fetch failed', detail: String(e) }, 502);
  }

  if (btJson?.status !== 'OK') {
    // Cache the failure sentinel so unhuntable chains don't burn
    // BestTime quota on every request.
    await putCached(cacheKey, { error: 'no_forecast' }).catch(() => {});
    return j(
      {
        error: 'BestTime non-OK',
        detail: btJson?.message ?? 'unknown',
        upstreamStatus: btJson?.status,
        httpStatus,
        topKeys: Object.keys(btJson ?? {}),
      },
      502
    );
  }

  const forecast = simplify(btJson);
  await putCached(cacheKey, forecast).catch(() => {});

  return j({ ...forecast, cache: 'miss' });
});

function j(body: any, status = 200): Response {
  return new Response(JSON.stringify(body), { headers: HEADERS, status });
}

type CachedRow = { forecast: any; fetched_at: string };

async function getCached(cacheKey: string): Promise<CachedRow | null> {
  if (!SUPABASE_URL || !SERVICE_ROLE) return null;
  try {
    const r = await fetch(
      `${SUPABASE_URL}/rest/v1/besttime_forecasts?cache_key=eq.${encodeURIComponent(cacheKey)}&select=forecast,fetched_at`,
      {
        headers: {
          apikey: SERVICE_ROLE,
          Authorization: `Bearer ${SERVICE_ROLE}`,
        },
      }
    );
    if (!r.ok) return null;
    const arr = (await r.json()) as CachedRow[];
    return arr[0] ?? null;
  } catch {
    return null;
  }
}

async function putCached(cacheKey: string, forecast: any): Promise<void> {
  if (!SUPABASE_URL || !SERVICE_ROLE) return;
  await fetch(`${SUPABASE_URL}/rest/v1/besttime_forecasts`, {
    method: 'POST',
    headers: {
      apikey: SERVICE_ROLE,
      Authorization: `Bearer ${SERVICE_ROLE}`,
      'Content-Type': 'application/json',
      Prefer: 'resolution=merge-duplicates',
    },
    body: JSON.stringify({
      cache_key: cacheKey,
      forecast,
      fetched_at: new Date().toISOString(),
    }),
  });
}

type Forecast = {
  venueName: string;
  venueAddress: string;
  hourlyBusyness: (number | null)[][];
  bestTime: { dayOfWeek: number; hour: number; busyness: number } | null;
};

function simplify(bt: any): Forecast {
  const info = bt?.venue_info ?? {};
  const analysis: any[] = Array.isArray(bt?.analysis) ? bt.analysis : [];

  const grid: (number | null)[][] = [];
  for (let d = 0; d < 7; d++) {
    const day = analysis[d];
    const row: (number | null)[] = new Array(24).fill(null);
    if (day?.hour_analysis && Array.isArray(day.hour_analysis)) {
      for (const h of day.hour_analysis) {
        const idx = typeof h?.hour === 'number' ? h.hour : null;
        const intensity = typeof h?.intensity_nr === 'number' ? h.intensity_nr : null;
        if (idx != null && idx >= 0 && idx < 24 && intensity != null) {
          // intensity_nr is -2 (closed/empty) to 5 (insanely busy)
          // Map -2..5 → 0..100 busyness scale
          row[idx] = Math.max(0, Math.min(100, Math.round(((intensity + 2) / 7) * 100)));
        }
      }
    }
    grid.push(row);
  }

  // Best time = lowest busyness during reasonable shopping hours (7am–9pm)
  let best: Forecast['bestTime'] = null;
  let lowest = 101;
  for (let d = 0; d < 7; d++) {
    for (let h = 7; h <= 21; h++) {
      const v = grid[d]?.[h];
      if (v != null && v < lowest) {
        lowest = v;
        best = { dayOfWeek: d, hour: h, busyness: v };
      }
    }
  }

  return {
    venueName: info?.venue_name ?? '',
    venueAddress: info?.venue_address ?? '',
    hourlyBusyness: grid,
    bestTime: best,
  };
}
