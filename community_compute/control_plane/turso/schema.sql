-- ============================================================================
-- Community-Compute queue on TURSO (libSQL/SQLite) — SEPARATE from the site.
-- The site's AUTH/Supabase is NEVER touched. Reached only through the Worker's
-- secret-gated /cc/* routes (no anon, no client SQL). BYOK 3 providers unchanged.
--
-- DESIGN: per-WORKER lease + a LIVE config, so the heartbeat is CHEAP.
--   * cc_renew updates ONE row (cc_workers.last_seen) -> 1 write / heartbeat.
--   * a claimed line is RECLAIMABLE iff its worker is stale/gone/blocked
--     (worker.last_seen < now - ttl), NOT by the line's own lease -> a
--     slow-but-alive worker keeps its lines. lease_until is a belt-and-braces
--     fallback for an orphaned line (worker row vanished).
--   * heartbeat/ttl/batch/cap live in cc_config -> the operator changes ONE
--     number and every device adapts within a cycle, NO app rebuild.
-- ============================================================================

CREATE TABLE IF NOT EXISTS cc_config (
  k TEXT PRIMARY KEY,
  v INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS cc_workers (
  id          TEXT PRIMARY KEY,             -- random device uuid (NO PII, NO IP, NO key)
  platform    TEXT,
  last_seen   INTEGER NOT NULL,             -- epoch s; the heartbeat updates THIS (1 write)
  done        INTEGER NOT NULL DEFAULT 0,   -- total lines contributed (stats)
  blocked     INTEGER NOT NULL DEFAULT 0,   -- operator kill-switch for a rogue device
  enrolled_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS cc_lines (
  id          TEXT PRIMARY KEY,             -- '<game>|<string_key>' (globally unique)
  game        TEXT NOT NULL,
  target      TEXT NOT NULL,                -- the string_key to map back on collect
  sys         TEXT NOT NULL,                -- the system prompt (translate OR review mode)
  src         TEXT NOT NULL,                -- New-Era panel (EN + refs); +CURRENT for review
  out         TEXT,                         -- the returned Hebrew (untrusted -> QA at collect)
  status      TEXT NOT NULL DEFAULT 'open', -- open | claimed | done
  worker_id   TEXT,
  lease_until INTEGER,                      -- absolute epoch; fallback only (orphaned line)
  collected   INTEGER NOT NULL DEFAULT 0,   -- operator pulled + QA'd it
  created_at  INTEGER NOT NULL,
  updated_at  INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS cc_lines_pick_idx   ON cc_lines (status, collected, created_at);
CREATE INDEX IF NOT EXISTS cc_lines_worker_idx ON cc_lines (worker_id, status);
CREATE INDEX IF NOT EXISTS cc_lines_game_idx   ON cc_lines (game, status);
CREATE INDEX IF NOT EXISTS cc_workers_seen_idx ON cc_workers (last_seen);

-- Live-tunable defaults (5-minute heartbeat as requested; ttl MUST exceed heartbeat).
INSERT INTO cc_config (k, v) VALUES
  ('heartbeat_seconds', 300),    -- 5 min  (raise this if the device count climbs)
  ('lease_ttl_seconds', 1200),   -- 20 min (a dead device's batch returns after this)
  ('batch_size',        50),     -- lines handed out per claim
  ('max_inflight',      300)     -- hard cap on lines one device may hold (anti-hoard)
ON CONFLICT(k) DO NOTHING;
