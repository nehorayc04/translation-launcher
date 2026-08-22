# Community-Compute on TURSO — separate from the site, live-tunable, QA-gated

The volunteer queue no longer lives on the site's Supabase. It is **isolated
`cc_*` tables on Turso**, reached only through the mod Worker's secret-gated
`/cc/*` routes. **The site's AUTH/Supabase is never touched → the volunteer fleet
can never break login again** (the 500MB wall that caused the outage is gone:
Turso free = 5GB storage + 10M writes/month + 500M reads/month).
BYOK is unchanged — devices still translate with their own **Groq / SambaNova /
NIM** keys, which are stored ONLY on the device and never transmitted.

## Why this scales to hundreds of devices — the cheap heartbeat

The old design renewed the lease on **50 line-rows every 60s per worker**
(~2.16M writes/month/device → ~5 devices exhausted the quota). Here the lease is
**per-WORKER**: `cc_renew` updates **one row** (`cc_workers.last_seen`), and a
claimed line is reclaimable only when *its worker* is stale/blocked/gone.

| heartbeat | writes/device/month | max devices 24/7 |
|---|---|---|
| 60s | 43,200 | ~208 |
| **300s (5 min — the shipped default)** | **8,640** | **~1,040** |
| 600s | 4,320 | ~1,600 |

Work writes (claim+submit ≈ 2/line) are driven by the CORPUS, not the device
count: a 100K-line game ≈ 200K writes whether 5 or 500 devices do it.

## Live tuning — no rebuild, ever

`cc_config` is returned on every `enroll`/`claim`/`renew`, so devices obey the
server. Change one number and the whole fleet adapts within a cycle:

```bash
python cc_ops.py config --get                     # read
python -c "import cc_ops; print(cc_ops.set_config(heartbeat_seconds=600))"   # device count climbing? raise it
python -c "import cc_ops; print(cc_ops.set_config(batch_size=100))"
```
Keys + bounds: `heartbeat_seconds` 60-3600 · `lease_ttl_seconds` 120-86400
(**keep it ≥ 3× the heartbeat**) · `batch_size` 1-200 · `max_inflight` 10-5000.

## Operating one game at a time

```bash
python cc_seed.py <corpus.json> --game skyrim        # seed (idempotent, multi-row)
python cc_ops.py stats                               # open/claimed/done/workers
python cc_collect.py --game skyrim --out hebrew.json          # dry-run: see the QA verdicts
python cc_collect.py --game skyrim --out hebrew.json --apply  # write + mark collected + re-queue bad
```
When a game finishes: collect with `--apply`, then
`DELETE FROM cc_lines WHERE game='<g>' AND collected=1` to free space, and seed
the next game. Corpus input = `cc_corpus.build_items` output + a game name.

## The quality + stability protections (all tested)

- **Atomic claim** — one `UPDATE … WHERE id IN (SELECT … LIMIT n) RETURNING`, so
  two devices can never get the same line (verified disjoint).
- **Submit only what you HOLD** — `WHERE id=? AND worker_id=? AND status='claimed'`;
  a device cannot write a line it doesn't own (verified rejected).
- **Dead device → work returns** — its lines are reclaimable once `last_seen` is
  older than `lease_ttl_seconds`; open lines are served first, so nothing is lost.
- **`max_inflight` cap** — one device can't hoard/drain the queue.
- **Block switch** — `cc_ops.block(<worker>)` stops a rogue device AND instantly
  releases its lines.
- **QA gate at collect (12/12 tested)** — `done` is NOT a quality signal. Every
  line is classified: `ok` / `passthrough` (pure token or ALL-CAPS brand) /
  `recover` (a leaked reference panel that strips deterministically to one clean
  Hebrew body) / `requeue` (panel leak, untranslated Arabic/English echo, engine
  **token drift**, niqqud-only, CJK, empty) → defective lines go back to `open`
  and are re-translated, never silently shipped. Output still goes through the
  game's own build QA + admin approval.
- **Privacy** — no PII, no IP, no API key server-side; a device is a random UUID.

## Files

`schema.sql` (tables + defaults) · `turso_client.py` (HTTP /v2/pipeline) ·
`cc_ops.py` (device + operator client = the reference for the apps) ·
`cc_seed.py` · `cc_collect.py` (QA gate) · `cc_smoke.py` (11-check end-to-end,
ALL PASS) · `.cc_env` (secrets, gitignored).

## App repoint (the remaining step)

The Android/desktop apps still call the old Supabase RPCs. Point them at
`https://steam-hebrew-mods.nc52885.workers.dev/cc/<op>`, header
`x-cc-secret: <CC_SECRET>`, JSON body — `cc_ops.py` is the exact contract:

| old RPC | new | body | returns |
|---|---|---|---|
| `cc_enroll` | `POST /cc/enroll` | `{worker, platform}` | `{worker, blocked, config}` |
| `cc_claim` | `POST /cc/claim` | `{worker}` | `{lines:[{id,target,sys,src}], config}` |
| `cc_renew` | `POST /cc/renew` | `{worker}` | `{ok, blocked, config}` |
| `cc_submit` | `POST /cc/submit` | `{worker, out:{id:hebrew}}` | `{accepted, rejected}` |
| `cc_release` | `POST /cc/release` | `{worker}` | `{released}` |
| `cc_stats` | `POST /cc/stats` | `{}` | `{open,claimed,done,workers,games,config}` |

**The app must use `config.heartbeat_seconds` from the response as its renew
interval** (that is what makes the frequency tunable without a rebuild), and
re-enroll if a renew returns `reenroll:true`.
