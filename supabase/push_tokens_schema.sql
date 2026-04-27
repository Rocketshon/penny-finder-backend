-- Push notification dispatch — one row per device.
-- Devices upsert their Expo push token + the UPCs they want notifications
-- for + fav stores (for penny-day reminders). The dispatch_push edge
-- function reads this table on schedule, never the app.

CREATE TABLE IF NOT EXISTS public.push_tokens (
  client_id text PRIMARY KEY,
  expo_token text NOT NULL,
  platform text NOT NULL CHECK (platform IN ('ios', 'android')),
  watch_upcs text[] NOT NULL DEFAULT '{}',
  fav_store_ids text[] NOT NULL DEFAULT '{}',
  notify_penny_day boolean NOT NULL DEFAULT true,
  notify_watchlist boolean NOT NULL DEFAULT true,
  last_notified_penny_run text,
  last_notified_watch_upcs text[] NOT NULL DEFAULT '{}',
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (length(expo_token) <= 200),
  CHECK (length(client_id) <= 64)
);

CREATE INDEX IF NOT EXISTS push_tokens_watch_upcs_idx
  ON public.push_tokens USING gin(watch_upcs);

ALTER TABLE public.push_tokens ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS push_tokens_insert_anon ON public.push_tokens;
DROP POLICY IF EXISTS push_tokens_update_anon ON public.push_tokens;
DROP POLICY IF EXISTS push_tokens_select_own ON public.push_tokens;

-- Anon devices can register/update their own row (anon key + their own
-- random client_id). They can never SELECT — only the dispatch fn (using
-- service-role) reads the table.
CREATE POLICY push_tokens_insert_anon ON public.push_tokens
  FOR INSERT TO anon WITH CHECK (true);

CREATE POLICY push_tokens_update_anon ON public.push_tokens
  FOR UPDATE TO anon USING (true) WITH CHECK (true);
