-- =====================================================================
--  Community Compute — control-plane schema (Supabase / Postgres)
--  A reliable, lease-based PULL queue for a fleet of ANONYMOUS volunteer
--  worker apps (desktop EXE + Android APK).
--
--  MODEL (2026-07-30 rewrite): one row = ONE LINE (`cc_lines`).
--   * A worker CLAIMS up to N lines atomically (default/cap 50) → they go
--     'claimed' with a lease. It translates them (batched across the
--     volunteer's 3 providers) and SUBMITS a {id: hebrew} map in ONE call —
--     each id commits INDEPENDENTLY (partial-safe: a phone that drops after
--     48/50 keeps the 48; only the un-returned 2 stay claimed).
--   * HEALTH-CHECK is PASSIVE (the server never contacts the worker → its IP
--     stays private): the worker calls cc_renew (~every 60s) to extend the
--     lease on its still-claimed lines. A worker that dies/goes offline stops
--     renewing → after the lease TTL its un-returned lines return to the pool
--     for OTHER workers. A slow-but-alive worker keeps renewing → never stolen.
--   * NO reslice, ever. A new worker just claims; a closed worker's lines
--     lease-expire back to the pool. The store (this table) owns in/out.
--
--  SECURITY
--   * Volunteers call ONLY the SECURITY DEFINER RPCs with the public anon key
--     + a shared app_secret. Base tables DENY anon (RLS on, no anon policy).
--   * NO IP stored (cc_workers = random UUID + counters).
--   * The operator (service_role) seeds/collects directly; the service key
--     lives ONLY on the operator machine. Returned text is UNTRUSTED → still
--     passes the project QA gate + admin approval before it touches a corpus.
--
--  Run once (operator): apply this migration, then set the app_secret (bottom).
-- =====================================================================

create extension if not exists pgcrypto;

-- defensive: drop prior (batch-model) objects so a re-apply is clean
drop function if exists public.cc_claim(text, text, integer);
drop function if exists public.cc_submit(text, text, uuid, jsonb);
drop function if exists public.cc_submit(text, text, jsonb);
drop function if exists public.cc_renew(text, text);
drop function if exists public.cc_release(text, text);
drop function if exists public.cc_stats(text);
drop function if exists public.cc_enroll(text, text, text);

-- --------------------------------------------------------------- tables

create table if not exists public.cc_config (
  id          text primary key default 'main',
  app_secret  text not null,
  paused      boolean not null default false,   -- operator kill-switch
  lease_s     integer not null default 600      -- a claimed line returns after this if not renewed
);

create table if not exists public.cc_lines (
  id           uuid primary key default gen_random_uuid(),
  game         text,                            -- corpus label (operator)
  sys          text not null,                   -- system prompt the worker must use
  target       text,                            -- free label round-tripped to the operator
  src          text not null,                   -- the ENGLISH line
  out          text,                            -- the HEBREW line (filled on submit)
  status       text not null default 'open',    -- open | claimed | done
  worker_id    text,
  lease_until  timestamptz,
  created_at   timestamptz not null default now(),
  completed_at timestamptz,
  collected    boolean not null default false   -- operator pulled the result
);

create index if not exists cc_lines_open_idx    on public.cc_lines (status, created_at);
create index if not exists cc_lines_collect_idx on public.cc_lines (status, collected);
create index if not exists cc_lines_worker_idx  on public.cc_lines (worker_id, status);

create table if not exists public.cc_workers (
  worker_id  text primary key,                  -- app-generated random UUID (NO PII, NO IP)
  first_seen timestamptz not null default now(),
  last_seen  timestamptz not null default now(),
  lines_done bigint not null default 0,
  platform   text
);

-- --------------------------------------------------------------- RLS: deny anon on base tables
alter table public.cc_config  enable row level security;
alter table public.cc_lines   enable row level security;
alter table public.cc_workers enable row level security;
-- (no anon/authenticated policies → default-deny; service_role bypasses RLS)

-- --------------------------------------------------------------- gate: valid secret + not paused
create or replace function public._cc_gate(p_secret text)
returns void language plpgsql security definer set search_path = public as $$
declare cfg public.cc_config;
begin
  select * into cfg from public.cc_config where id = 'main';
  if cfg.id is null or cfg.app_secret <> p_secret then
    raise exception 'unauthorized' using errcode = '28000';
  end if;
  if cfg.paused then
    raise exception 'fleet paused' using errcode = 'P0001';
  end if;
end $$;

-- --------------------------------------------------------------- enroll (anonymous worker)
create or replace function public.cc_enroll(p_secret text, p_worker text, p_platform text default null)
returns void language plpgsql security definer set search_path = public as $$
begin
  perform public._cc_gate(p_secret);
  insert into public.cc_workers (worker_id, platform)
       values (p_worker, p_platform)
  on conflict (worker_id) do update set last_seen = now(),
                                        platform  = coalesce(excluded.platform, public.cc_workers.platform);
end $$;

-- --------------------------------------------------------------- claim up to N lines (atomic, leased)
create or replace function public.cc_claim(p_secret text, p_worker text, p_max integer)
returns table (id uuid, sys text, target text, src text)
language plpgsql security definer set search_path = public as $$
declare lease_s integer;
begin
  perform public._cc_gate(p_secret);
  select public.cc_config.lease_s into lease_s from public.cc_config where id = 'main';
  update public.cc_workers set last_seen = now() where worker_id = p_worker;

  return query
  update public.cc_lines j
     set status      = 'claimed',
         worker_id   = p_worker,
         lease_until = now() + make_interval(secs => coalesce(lease_s, 600))
   where j.id in (
       select c.id from public.cc_lines c
        where c.status = 'open'
           or (c.status = 'claimed' and c.lease_until < now())   -- a dead worker's line returns
        order by c.created_at
        limit greatest(1, least(coalesce(p_max, 1), 50))
        for update skip locked
   )
  returning j.id, j.sys, j.target, j.src;
end $$;

-- --------------------------------------------------------------- heartbeat: extend the lease on this worker's claimed lines
create or replace function public.cc_renew(p_secret text, p_worker text)
returns integer language plpgsql security definer set search_path = public as $$
declare lease_s integer; n integer;
begin
  perform public._cc_gate(p_secret);
  select public.cc_config.lease_s into lease_s from public.cc_config where id = 'main';
  update public.cc_lines
     set lease_until = now() + make_interval(secs => coalesce(lease_s, 600))
   where worker_id = p_worker and status = 'claimed';
  get diagnostics n = row_count;
  update public.cc_workers set last_seen = now() where worker_id = p_worker;
  return n;
end $$;

-- --------------------------------------------------------------- submit many (per-line, partial-safe) in one call
-- p_out = {"<line_id>": "<hebrew>", ...}. Each id owned+claimed by this worker
-- with a non-empty value commits to 'done'; ids NOT present stay claimed
-- (they return to the pool when the lease expires). A line re-leased to
-- someone else is silently skipped (never overwrites another worker's row).
create or replace function public.cc_submit(p_secret text, p_worker text, p_out jsonb)
returns integer language plpgsql security definer set search_path = public as $$
declare n integer;
begin
  perform public._cc_gate(p_secret);
  update public.cc_lines l
     set out          = p_out ->> (l.id::text),
         status       = 'done',
         completed_at = now()
   where l.worker_id = p_worker
     and l.status    = 'claimed'
     and p_out ? (l.id::text)
     and coalesce(btrim(p_out ->> (l.id::text)), '') <> '';
  get diagnostics n = row_count;
  if n > 0 then
    update public.cc_workers set lines_done = lines_done + n, last_seen = now()
     where worker_id = p_worker;
  end if;
  return n;
end $$;

-- --------------------------------------------------------------- graceful release (worker turned OFF): requeue its claimed lines now
create or replace function public.cc_release(p_secret text, p_worker text)
returns integer language plpgsql security definer set search_path = public as $$
declare n integer;
begin
  perform public._cc_gate(p_secret);
  update public.cc_lines
     set status = 'open', worker_id = null, lease_until = null
   where worker_id = p_worker and status = 'claimed';
  get diagnostics n = row_count;
  return n;
end $$;

-- --------------------------------------------------------------- light stats for the app UI
create or replace function public.cc_stats(p_secret text)
returns json language plpgsql security definer set search_path = public as $$
declare r json;
begin
  perform public._cc_gate(p_secret);
  select json_build_object(
           'open',    (select count(*) from public.cc_lines where status = 'open'),
           'claimed', (select count(*) from public.cc_lines where status = 'claimed'),
           'done',    (select count(*) from public.cc_lines where status = 'done' and not collected),
           'workers', (select count(*) from public.cc_workers where last_seen > now() - interval '10 min')
         ) into r;
  return r;
end $$;

-- --------------------------------------------------------------- grants: anon may ONLY execute the RPCs
grant execute on function public.cc_enroll(text, text, text) to anon, authenticated;
grant execute on function public.cc_claim(text, text, integer) to anon, authenticated;
grant execute on function public.cc_renew(text, text) to anon, authenticated;
grant execute on function public.cc_submit(text, text, jsonb) to anon, authenticated;
grant execute on function public.cc_release(text, text) to anon, authenticated;
grant execute on function public.cc_stats(text) to anon, authenticated;

notify pgrst, 'reload schema';

-- --------------------------------------------------------------- FINAL STEP (operator): set the shared secret
--   insert into public.cc_config (id, app_secret) values ('main', 'REPLACE-WITH-A-LONG-RANDOM-SECRET')
--   on conflict (id) do update set app_secret = excluded.app_secret;
