// Supabase Edge Function: briefing
//
// Thin proxy in front of the GitHub Pages-hosted briefing JSON. Adds:
//   1. Cache-Control headers (CDN-edge cache for 30 min, stale-while-revalidate
//      for 24h) — cuts cold-fetch latency for users dramatically vs. raw
//      GitHub Pages which sets a short TTL.
//   2. Optional ?region=XX param that filters store_weeks + highlights to a
//      single US region (planned future use; today we pass through).
//   3. Robust failure mode: if upstream is down, returns the last-known
//      cached body via the CDN's stale serving.
//
// Endpoint:
//   GET https://ojfhdbeatbfuiofykopl.supabase.co/functions/v1/briefing
//   GET https://ojfhdbeatbfuiofykopl.supabase.co/functions/v1/briefing?region=MI
//
// No auth required — verify_jwt is set to false at deploy time. The anon
// key in the Authorization header is fine but not enforced for this resource.

const UPSTREAM = 'https://rocketshon.github.io/penny-finder-backend/briefings/latest.json';

// Edge cache: 30 min fresh, 24h stale-while-revalidate. Means most users get
// an instant CDN-cached response and we only hit the origin a few times/hr.
const CACHE_HEADERS: Record<string, string> = {
  'Cache-Control': 'public, max-age=1800, stale-while-revalidate=86400',
  'Content-Type': 'application/json; charset=utf-8',
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

Deno.serve(async (req: Request) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: CACHE_HEADERS, status: 204 });
  }

  const url = new URL(req.url);
  const region = url.searchParams.get('region')?.toUpperCase().slice(0, 2) ?? null;

  let upstream: Response;
  try {
    upstream = await fetch(UPSTREAM, {
      // Hit origin at most once per cache window
      headers: { 'User-Agent': 'penny-hunter-edge/1.0' },
    });
  } catch (e) {
    return new Response(
      JSON.stringify({ error: 'upstream fetch failed', detail: String(e) }),
      { headers: CACHE_HEADERS, status: 502 }
    );
  }

  if (!upstream.ok) {
    return new Response(
      JSON.stringify({ error: 'upstream not ok', status: upstream.status }),
      { headers: CACHE_HEADERS, status: upstream.status }
    );
  }

  let body: any;
  try {
    body = await upstream.json();
  } catch (e) {
    return new Response(
      JSON.stringify({ error: 'upstream JSON invalid', detail: String(e) }),
      { headers: CACHE_HEADERS, status: 502 }
    );
  }

  // Region filter — currently no-op since briefing schema doesn't carry
  // region tags. Wired so the app can start sending region without a
  // breaking change here later. When stores grow region metadata we'll
  // filter highlights[] + stores[] to that region's chains only.
  if (region) {
    body._filtered_region = region;
    body._filtered_note = 'region filter scaffolded; pass-through until stores carry region';
  }

  body._served_by = 'supabase-edge-briefing';
  body._served_at = new Date().toISOString();

  return new Response(JSON.stringify(body), {
    headers: CACHE_HEADERS,
    status: 200,
  });
});
