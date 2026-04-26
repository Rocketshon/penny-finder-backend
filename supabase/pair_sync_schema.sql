-- =============================================================
-- Penny Hunter — Pair Sync schema (own project: ojfhdbeatbfuiofykopl)
-- =============================================================
-- Security model: a pair_code is an 8-char alphanumeric shared
-- secret (~2.8 trillion combos). Anon users can read/write any
-- row; the client always filters by their pair_code. This is
-- "security through unguessability" — appropriate for a hobby
-- watchlist/find-sharing feature, NOT for sensitive data.
--
-- Run this once in the Supabase SQL Editor. Idempotent.
-- =============================================================

-- ── Tables ────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.pairs (
  code        text PRIMARY KEY,
  created_at  timestamptz NOT NULL DEFAULT now(),
  last_seen   timestamptz NOT NULL DEFAULT now(),
  label       text
);

CREATE TABLE IF NOT EXISTS public.pair_watchlist (
  code         text NOT NULL,
  id           text NOT NULL,
  item         text NOT NULL,
  upc          text,
  added_at     timestamptz NOT NULL DEFAULT now(),
  added_by     text,
  target_cycle text,
  PRIMARY KEY (code, id)
);

CREATE TABLE IF NOT EXISTS public.pair_finds (
  code        text NOT NULL,
  id          text NOT NULL,
  store       text NOT NULL,
  item        text NOT NULL,
  upc         text,
  paid        numeric NOT NULL,
  est_resale  numeric,
  is_penny    boolean NOT NULL DEFAULT false,
  note        text,
  added_at    timestamptz NOT NULL DEFAULT now(),
  added_by    text,
  PRIMARY KEY (code, id)
);

CREATE TABLE IF NOT EXISTS public.pair_status (
  code        text NOT NULL,
  device_id   text NOT NULL,
  device_name text,
  store_id    text,
  status      text NOT NULL DEFAULT 'idle',
  updated_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (code, device_id)
);

CREATE INDEX IF NOT EXISTS pair_watchlist_code_idx ON public.pair_watchlist(code);
CREATE INDEX IF NOT EXISTS pair_finds_code_idx     ON public.pair_finds(code);
CREATE INDEX IF NOT EXISTS pair_status_code_idx    ON public.pair_status(code);

-- ── Realtime subscriptions ─────────────────────────────────────

ALTER PUBLICATION supabase_realtime ADD TABLE public.pair_watchlist;
ALTER PUBLICATION supabase_realtime ADD TABLE public.pair_finds;
ALTER PUBLICATION supabase_realtime ADD TABLE public.pair_status;

-- ── RLS — permissive policies for the anon role ───────────────

ALTER TABLE public.pairs          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pair_watchlist ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pair_finds     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pair_status    ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS pairs_anon          ON public.pairs;
DROP POLICY IF EXISTS pair_watchlist_anon ON public.pair_watchlist;
DROP POLICY IF EXISTS pair_finds_anon     ON public.pair_finds;
DROP POLICY IF EXISTS pair_status_anon    ON public.pair_status;

CREATE POLICY pairs_anon          ON public.pairs          FOR ALL TO anon USING (true) WITH CHECK (true);
CREATE POLICY pair_watchlist_anon ON public.pair_watchlist FOR ALL TO anon USING (true) WITH CHECK (true);
CREATE POLICY pair_finds_anon     ON public.pair_finds     FOR ALL TO anon USING (true) WITH CHECK (true);
CREATE POLICY pair_status_anon    ON public.pair_status    FOR ALL TO anon USING (true) WITH CHECK (true);
