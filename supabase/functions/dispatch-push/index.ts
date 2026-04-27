// Supabase Edge Function: dispatch-push
//
// Fires on schedule (currently invoked manually or via GitHub Actions cron).
// Reads push_tokens, intersects each device's watch_upcs with today's
// penny list, and sends Expo push notifications.
//
// Two notification types:
//   1) Watchlist hit  — "Your watched item just hit penny day at DG."
//   2) Penny day      — fired at 6am ET on Tuesday for users with
//                       notify_penny_day=true who haven't been notified
//                       this week (tracked via last_notified_penny_run).
//
// Auth: service-role required. Caller (cron / GitHub Action) must send
//   Authorization: Bearer <SUPABASE_SERVICE_ROLE_KEY>
// in the request to invoke this function.

const HEADERS = {
  'Content-Type': 'application/json; charset=utf-8',
};

const SUPABASE_URL = Deno.env.get('SUPABASE_URL') ?? '';
const SERVICE_ROLE = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? '';
const BRIEFING_URL = 'https://rocketshon.github.io/penny-finder-backend/briefings/latest.json';
const EXPO_PUSH = 'https://exp.host/--/api/v2/push/send';

Deno.serve(async (req: Request) => {
  if (req.method !== 'POST') return j({ error: 'POST required' }, 405);

  // Service-role gate. Same exact-match check as send-email.
  const auth = req.headers.get('Authorization') ?? '';
  if (!SERVICE_ROLE || auth !== `Bearer ${SERVICE_ROLE}`) {
    return j({ error: 'service-role auth required' }, 403);
  }

  // 1. Pull today's briefing (penny list)
  let briefing: any;
  try {
    const r = await fetch(BRIEFING_URL);
    briefing = await r.json();
  } catch (e) {
    return j({ error: 'briefing fetch failed', detail: String(e) }, 502);
  }
  const pennyList: any[] = briefing?.penny_list ?? [];
  const pennyUpcs = new Set<string>(pennyList.map((p) => p.upc).filter(Boolean));
  const briefingId = briefing?.week_id ?? new Date().toISOString().slice(0, 10);

  // 2. Pull all push tokens
  const tokensRes = await fetch(`${SUPABASE_URL}/rest/v1/push_tokens?select=*`, {
    headers: { apikey: SERVICE_ROLE, Authorization: `Bearer ${SERVICE_ROLE}` },
  });
  if (!tokensRes.ok) {
    return j({ error: 'token fetch failed', status: tokensRes.status }, 502);
  }
  const tokens: any[] = await tokensRes.json();

  // 3. Build push messages
  const messages: any[] = [];
  const dbUpdates: Array<{ client_id: string; patch: any }> = [];
  const now = new Date();
  const isTuesday = now.getUTCDay() === 2; // 0=Sun..6=Sat (Tuesday in UTC roughly = Tue ET)

  for (const t of tokens) {
    if (!t.expo_token || !t.expo_token.startsWith('ExponentPushToken[')) continue;

    // Watchlist hits
    if (t.notify_watchlist && Array.isArray(t.watch_upcs) && t.watch_upcs.length > 0) {
      const lastNotified = new Set<string>(t.last_notified_watch_upcs ?? []);
      const newHits = (t.watch_upcs as string[]).filter(
        (upc) => pennyUpcs.has(upc) && !lastNotified.has(upc)
      );
      if (newHits.length > 0) {
        const item = pennyList.find((p) => p.upc === newHits[0]);
        const title = newHits.length === 1
          ? `🎯 Your watched item just hit penny day`
          : `🎯 ${newHits.length} watched items just hit penny day`;
        const body = item?.item
          ? `${item.item.slice(0, 80)}${newHits.length > 1 ? ` +${newHits.length - 1} more` : ''}`
          : `Open Penny Hunter to see them all.`;
        messages.push({
          to: t.expo_token,
          title,
          body,
          data: { type: 'watchlist_hit', upcs: newHits },
          sound: 'default',
          priority: 'high',
        });
        dbUpdates.push({
          client_id: t.client_id,
          patch: { last_notified_watch_upcs: [...lastNotified, ...newHits].slice(-200) },
        });
      }
    }

    // Penny day reminder
    if (
      t.notify_penny_day &&
      isTuesday &&
      t.last_notified_penny_run !== briefingId
    ) {
      messages.push({
        to: t.expo_token,
        title: '1¢ Penny Day is now',
        body: `${pennyList.length} confirmed UPCs at Dollar General. Tap to open the list.`,
        data: { type: 'penny_day' },
        sound: 'default',
        priority: 'high',
      });
      dbUpdates.push({
        client_id: t.client_id,
        patch: { last_notified_penny_run: briefingId },
      });
    }
  }

  // 4. Send to Expo (batches of 100 max)
  let sent = 0;
  for (let i = 0; i < messages.length; i += 100) {
    const batch = messages.slice(i, i + 100);
    try {
      const r = await fetch(EXPO_PUSH, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
          'Accept-Encoding': 'gzip, deflate',
        },
        body: JSON.stringify(batch),
      });
      if (r.ok) sent += batch.length;
    } catch {
      // Continue — partial failures are acceptable; we'll retry tomorrow
    }
  }

  // 5. Persist last-notified state (best-effort)
  for (const u of dbUpdates) {
    await fetch(
      `${SUPABASE_URL}/rest/v1/push_tokens?client_id=eq.${encodeURIComponent(u.client_id)}`,
      {
        method: 'PATCH',
        headers: {
          apikey: SERVICE_ROLE,
          Authorization: `Bearer ${SERVICE_ROLE}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(u.patch),
      }
    ).catch(() => {});
  }

  return j({
    candidates: tokens.length,
    messages: messages.length,
    sent,
    briefing_id: briefingId,
    is_tuesday: isTuesday,
  });
});

function j(body: any, status = 200): Response {
  return new Response(JSON.stringify(body), { headers: HEADERS, status });
}
