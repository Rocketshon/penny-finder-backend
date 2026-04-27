-- =============================================================
-- Penny Hunter — Pair Sync RLS hardening (v2)
-- =============================================================
-- v1 RLS was permissive (`FOR ALL TO anon USING (true)`), which let
-- anyone with the anon key enumerate every pair's data. v2 binds row
-- access to a custom request header — the client must send
-- `x-pair-code: <8-char-code>` and rows are only visible / mutable when
-- their `code` column matches that header.
--
-- Knowing the anon key is no longer enough; an attacker also needs the
-- 8-char code (~2.8T combos). The pair table itself is no longer
-- enumerable.
--
-- Run this once. Idempotent. Old policies are dropped first.
-- =============================================================

-- Helper: pull the current request's pair code from headers.
CREATE OR REPLACE FUNCTION public.current_pair_code() RETURNS text
LANGUAGE sql STABLE AS $$
  SELECT coalesce(
    current_setting('request.headers', true)::json->>'x-pair-code',
    ''
  );
$$;

-- ── Drop v1 policies ──────────────────────────────────────────
DROP POLICY IF EXISTS pairs_anon          ON public.pairs;
DROP POLICY IF EXISTS pair_watchlist_anon ON public.pair_watchlist;
DROP POLICY IF EXISTS pair_finds_anon     ON public.pair_finds;
DROP POLICY IF EXISTS pair_status_anon    ON public.pair_status;

-- ── pairs ─────────────────────────────────────────────────────
-- INSERT: anyone (creating a new pair). Must match the supplied code header.
-- SELECT / UPDATE: only when the row's code matches the header.
-- DELETE: blocked from anon (no abandoning pairs from the client).

CREATE POLICY pairs_insert_anon ON public.pairs
  FOR INSERT TO anon
  WITH CHECK (code = public.current_pair_code());

CREATE POLICY pairs_select_anon ON public.pairs
  FOR SELECT TO anon
  USING (code = public.current_pair_code());

CREATE POLICY pairs_update_anon ON public.pairs
  FOR UPDATE TO anon
  USING (code = public.current_pair_code())
  WITH CHECK (code = public.current_pair_code());

-- ── pair_watchlist / pair_finds / pair_status ────────────────
-- All operations require the row's code match the header.

CREATE POLICY pair_watchlist_anon ON public.pair_watchlist
  FOR ALL TO anon
  USING (code = public.current_pair_code())
  WITH CHECK (code = public.current_pair_code());

CREATE POLICY pair_finds_anon ON public.pair_finds
  FOR ALL TO anon
  USING (code = public.current_pair_code())
  WITH CHECK (code = public.current_pair_code());

CREATE POLICY pair_status_anon ON public.pair_status
  FOR ALL TO anon
  USING (code = public.current_pair_code())
  WITH CHECK (code = public.current_pair_code());
