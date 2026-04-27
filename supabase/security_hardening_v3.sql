-- =============================================================
-- Penny Hunter — Security hardening v3 (post red-team findings)
-- =============================================================
-- Two real vulns surfaced from the offensive probe:
--
-- HIGH: anon_finds was wide-open for writes. An attacker with the
--   public anon key successfully INSERT-ed `<script>alert(1)</script>`
--   as a UPC, and flooded 10 junk rows in <1 second with no validation
--   and no rate limit. Could pollute the "X hunters confirmed" badges
--   that drive the app's social-proof signal.
--
-- MEDIUM: besttime_forecasts and resale_estimates had `FOR SELECT TO
--   anon USING (true)` policies. Anyone with the anon key could SELECT
--   cache_key and harvest aggregate query patterns — what addresses
--   people look up + what UPCs they're researching. Not catastrophic,
--   but contradicts our "anonymous usage" framing.
--
-- This script: tightens both. Run once. Idempotent.
-- =============================================================

-- ── 1. anon_finds: input validation ───────────────────────────

-- UPC: digits only, 8-14 chars. Blocks HTML / script injection.
ALTER TABLE public.anon_finds DROP CONSTRAINT IF EXISTS anon_finds_upc_format;
ALTER TABLE public.anon_finds ADD CONSTRAINT anon_finds_upc_format
  CHECK (upc IS NULL OR upc ~ '^[0-9]{8,14}$');

-- store_id: lowercase slug only.
ALTER TABLE public.anon_finds DROP CONSTRAINT IF EXISTS anon_finds_store_format;
ALTER TABLE public.anon_finds ADD CONSTRAINT anon_finds_store_format
  CHECK (store_id ~ '^[a-z0-9][a-z0-9-]{1,29}$');

-- paid: 0..10000 (a $10K penny is implausible)
ALTER TABLE public.anon_finds DROP CONSTRAINT IF EXISTS anon_finds_paid_range;
ALTER TABLE public.anon_finds ADD CONSTRAINT anon_finds_paid_range
  CHECK (paid >= 0 AND paid <= 10000);

-- client_id: cap length so a single attacker can't flood the column with
-- 1MB strings.
ALTER TABLE public.anon_finds DROP CONSTRAINT IF EXISTS anon_finds_client_id_len;
ALTER TABLE public.anon_finds ADD CONSTRAINT anon_finds_client_id_len
  CHECK (client_id IS NULL OR length(client_id) <= 64);

-- ── 2. anon_finds: dedupe index limits flood damage ───────────
-- A single client_id can no longer post the same (upc, store_id) at the
-- same timestamp twice. Real users insert a new find ~every few minutes;
-- attackers trying to flood get 23-error per row spam unless they vary
-- all three keys, and the UPC format check above forces real-looking digits.
DROP INDEX IF EXISTS anon_finds_dedupe;
CREATE UNIQUE INDEX anon_finds_dedupe
  ON public.anon_finds (
    coalesce(client_id, '_anon_'),
    coalesce(upc, '_no_upc_'),
    store_id,
    ts
  );

-- ── 3. Cache table SELECT lockdown ────────────────────────────
-- Edge functions use the service role for reads, so anon-readable
-- policies aren't needed. Removing them prevents query-pattern exfil.
DROP POLICY IF EXISTS besttime_anon ON public.besttime_forecasts;
DROP POLICY IF EXISTS resale_anon ON public.resale_estimates;
-- No replacement policy created → anon can SELECT only when explicit
-- policy grants. With RLS enabled and no policy, anon gets zero rows.
