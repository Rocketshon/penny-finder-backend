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
  // Cap inputs to prevent pathological URL lengths from flowing into
  // BestTime + the cache key. 80 chars is more than any chain name; 160
  // is enough for a city + state + zip.
  const chain = (url.searchParams.get('chain') || '').slice(0, 80);
  const address = (url.searchParams.get('address') || '').slice(0, 160);

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

  // ── Address resolution via OpenStreetMap Nominatim ──────────
  // BestTime needs a SPECIFIC store street address. The app sends just
  // city + state + zip, which is too coarse for chains with multiple
  // nearby stores (Walmart, Target, Kroger, etc.). We use Nominatim
  // (free, no API key) to resolve the closest store of `chain` near the
  // user's zip, then forward THAT address to BestTime.
  //
  // 2-stage geocoding:
  //   1. Nominatim resolves the user's zip to a center lat/lng + bbox
  //   2. Nominatim searches `chain` within that bbox
  // Result is cached forever per (chain, zip) in besttime_forecasts since
  // store locations don't move.
  const resolved = await resolveSpecificStore(chain, address);
  const venueAddress = resolved ?? address;

  const btUrl =
    `${BT_BASE}/forecasts?api_key_private=${encodeURIComponent(BT_KEY)}` +
    `&venue_name=${encodeURIComponent(chain)}` +
    `&venue_address=${encodeURIComponent(venueAddress)}`;

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
    // NEVER reflect upstream object keys back to the client — if BestTime
    // ever returns a payload that includes our API key (defense-in-depth),
    // we don't want to echo it.
    return j(
      {
        error: 'BestTime non-OK',
        detail: typeof btJson?.message === 'string'
          ? btJson.message.slice(0, 200)
          : 'unknown',
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

// ── Address resolver: free OpenStreetMap Nominatim ──────────────
// Two-stage: zip → bbox → chain in bbox → street address.
// Returns null on any failure; caller falls back to the original address.
const NOMINATIM = 'https://nominatim.openstreetmap.org';
const UA = 'PennyHunter/1.0 hello@pennyhunter.store';
// Per Nominatim's usage policy: max 1 req/sec, must set User-Agent.
// Edge functions are cold-started, so two sequential fetches per cache
// miss is well under their limit.

async function resolveSpecificStore(
  chain: string,
  rawAddress: string
): Promise<string | null> {
  // Pull a 5-digit zip from the address if present
  const zipMatch = rawAddress.match(/\b(\d{5})\b/);
  if (!zipMatch) return null;
  const zip = zipMatch[1];

  try {
    // Stage 1: geocode the zip
    const zipResp = await fetch(
      `${NOMINATIM}/search?postalcode=${zip}&country=us&format=json&limit=1`,
      { headers: { 'User-Agent': UA } }
    );
    if (!zipResp.ok) return null;
    const zipResults: any[] = await zipResp.json();
    if (!zipResults[0]?.lat) return null;
    const lat = parseFloat(zipResults[0].lat);
    const lng = parseFloat(zipResults[0].lon);
    if (!isFinite(lat) || !isFinite(lng)) return null;

    // Stage 2: search chain within ~30 mile bbox around that point
    // 1° lat ≈ 69 mi, 1° lng ≈ 53 mi at 42°N. 0.45/0.55 ≈ 30mi radius.
    const dLat = 0.45;
    const dLng = 0.55;
    const viewbox = `${lng - dLng},${lat - dLat},${lng + dLng},${lat + dLat}`;
    const chainResp = await fetch(
      `${NOMINATIM}/search?q=${encodeURIComponent(chain)}&viewbox=${viewbox}&bounded=1&format=json&limit=5&countrycodes=us`,
      { headers: { 'User-Agent': UA } }
    );
    if (!chainResp.ok) return null;
    const chainResults: any[] = await chainResp.json();

    // Score each result and pick the best:
    //   +100 if it's a real shop POI (vs landuse polygon)
    //   +50 if class is shop
    //   +25 if display_name starts with a street number
    //   +importance bonus from Nominatim
    //   −distance penalty: prefer the one closest to the user's zip centroid
    const ranked = chainResults
      .map((r) => {
        const rLat = parseFloat(r.lat);
        const rLng = parseFloat(r.lon);
        // Approx miles using equirectangular projection (good enough for sorting)
        const dxMi = Math.abs(rLng - lng) * 53;
        const dyMi = Math.abs(rLat - lat) * 69;
        const distMi = Math.sqrt(dxMi * dxMi + dyMi * dyMi);
        return {
          r,
          score:
            (r.addresstype === 'shop' ? 100 : 0) +
            (r.class === 'shop' ? 50 : 0) +
            (typeof r.display_name === 'string' && /^\d+,/.test(r.display_name) ? 25 : 0) +
            (r.importance ? r.importance * 10 : 0) -
            // 1pt penalty per mile — within 30mi the addresstype/shop bonus
            // can override; outside, distance dominates.
            distMi,
        };
      })
      .sort((a, b) => b.score - a.score);

    if (!ranked[0]) return null;
    const best = ranked[0].r;
    if (!best?.display_name) return null;

    // Strip the country tail (everything from "United States" onward)
    return String(best.display_name).replace(/,?\s*United States.*$/i, '').slice(0, 200);
  } catch {
    return null;
  }
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
