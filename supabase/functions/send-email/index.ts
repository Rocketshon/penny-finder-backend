// Supabase Edge Function: send-email
// Tiny Resend wrapper. Used for transactional emails (welcome, watchlist
// hit alerts, weekly digest). Caller specifies recipient + subject + body.
// Authenticated by SUPABASE_SERVICE_ROLE_KEY in the Authorization header
// — DO NOT expose this function with verify_jwt=false unless you also
// add per-recipient rate limiting; otherwise it's a spam vector.
//
// POST /functions/v1/send-email
// Headers: Authorization: Bearer <service_role_key>
// Body: { to: string|string[], subject: string, html: string, text?: string, from?: string }

const HEADERS = {
  'Content-Type': 'application/json; charset=utf-8',
};

const FROM_DEFAULT = 'Penny Hunter <noreply@pennyhunter.store>';

Deno.serve(async (req: Request) => {
  if (req.method !== 'POST') return j({ error: 'POST required' }, 405);

  // Service-role gate. Without it, anyone with the anon key could spam
  // arbitrary emails. The function is deployed with verify_jwt=true so
  // Supabase's gateway already requires a valid JWT, but we double-check
  // it's the service role specifically — exact match, not endsWith,
  // since endsWith would accept any token that happens to share the
  // suffix.
  const auth = req.headers.get('Authorization') ?? '';
  const serviceRole = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? '';
  const expected = `Bearer ${serviceRole}`;
  if (!serviceRole || auth !== expected) {
    return j({ error: 'service-role auth required' }, 403);
  }

  let body: any;
  try {
    body = await req.json();
  } catch {
    return j({ error: 'invalid JSON' }, 400);
  }

  const to = Array.isArray(body?.to) ? body.to : body?.to ? [body.to] : [];
  const subject = String(body?.subject ?? '').slice(0, 200);
  const html = String(body?.html ?? '');
  const text = body?.text ? String(body.text) : undefined;
  const from = String(body?.from ?? FROM_DEFAULT).slice(0, 200);

  if (to.length === 0 || !subject || !html) {
    return j({ error: 'to, subject, html required' }, 400);
  }
  if (to.length > 50) return j({ error: 'max 50 recipients per call' }, 400);

  const key = Deno.env.get('RESEND_API_KEY') ?? '';
  if (!key) return j({ error: 'RESEND_API_KEY not set' }, 503);

  let res: Response;
  try {
    res = await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${key}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ from, to, subject, html, text }),
    });
  } catch (e) {
    return j({ error: 'resend fetch failed', detail: String(e) }, 502);
  }

  const json: any = await res.json();
  if (!res.ok) return j({ error: json?.message ?? `HTTP ${res.status}` }, 502);

  return j({ id: json?.id, sent: to.length });
});

function j(body: any, status = 200): Response {
  return new Response(JSON.stringify(body), { headers: HEADERS, status });
}
