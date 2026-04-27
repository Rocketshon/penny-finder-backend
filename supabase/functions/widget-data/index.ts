// Supabase Edge Function: widget-data
//
// Tiny JSON feed for the iOS Home Screen widget. Returns the minimum
// data the widget needs to render — countdown to next penny day, item
// count, headline. Cached aggressively (5 min) since the widget polls
// every ~hour and we don't need precision.
//
// Endpoint:
//   GET /functions/v1/widget-data
// Returns:
//   {
//     "next_penny_day_in_days": 0|1|2…,
//     "next_penny_day_label": "TODAY"|"TOMORROW"|"SAT" etc,
//     "is_penny_day": boolean,
//     "confirmed_upcs": <number>,
//     "store_name": "Dollar General",
//     "headline": "<short string>",
//     "fetched_at": "<iso>"
//   }

const HEADERS: Record<string, string> = {
  'Cache-Control': 'public, max-age=300, stale-while-revalidate=3600',
  'Content-Type': 'application/json; charset=utf-8',
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

// We pull the briefing through our own briefing edge function rather than
// hitting GitHub Pages directly so this fn stays inside Supabase egress
// (free tier). The briefing fn caches in besttime_forecasts equivalent.
const BRIEFING_URL = 'https://rocketshon.github.io/penny-finder-backend/briefings/latest.json';

const DAYS_SHORT = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'];
// Penny day = Tuesday for Dollar General (the canonical penny chain)
const PENNY_DAY_INDEX = 2;

Deno.serve(async (req: Request) => {
  if (req.method === 'OPTIONS') return new Response(null, { headers: HEADERS, status: 204 });

  let briefing: any;
  try {
    const r = await fetch(BRIEFING_URL);
    briefing = await r.json();
  } catch {
    // Soft fallback so the widget never shows broken state.
    return j({
      next_penny_day_in_days: 0,
      next_penny_day_label: '—',
      is_penny_day: false,
      confirmed_upcs: 0,
      store_name: 'Dollar General',
      headline: 'Penny list temporarily unavailable',
      fetched_at: new Date().toISOString(),
    });
  }

  const pennyList: any[] = briefing?.penny_list ?? [];
  const dgUpcs = pennyList.filter((p) => p.store_id === 'dg' || p.store_id === 'dollar-general');
  const confirmedUpcs = dgUpcs.length || pennyList.length;

  const now = new Date();
  const todayIdx = now.getUTCDay();
  let daysUntil = (PENNY_DAY_INDEX - todayIdx + 7) % 7;
  const isPennyDay = daysUntil === 0;

  let label: string;
  if (isPennyDay) label = 'TODAY';
  else if (daysUntil === 1) label = 'TOMORROW';
  else label = DAYS_SHORT[(todayIdx + daysUntil) % 7];

  return j({
    next_penny_day_in_days: daysUntil,
    next_penny_day_label: label,
    is_penny_day: isPennyDay,
    confirmed_upcs: confirmedUpcs,
    store_name: 'Dollar General',
    headline: briefing?.headline?.slice(0, 120) ?? 'Tap to open Penny Hunter',
    fetched_at: new Date().toISOString(),
  });
});

function j(body: any, status = 200): Response {
  return new Response(JSON.stringify(body), { headers: HEADERS, status });
}
