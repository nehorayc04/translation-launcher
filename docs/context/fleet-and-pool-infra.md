## 🏠 דור 3 — the pool moves to the self-hosted server (2026-08-13, IN PROGRESS: one DNS record from cutover)

⚠️ **NAME COLLISION, on purpose:** "דור 3" now means TWO different things in this project — the
**translation** generation (Crimson Desert's New-Era-2 engine, already shipped) and, from today, this
**infrastructure** generation. Write which one you mean: *דור 3 (תשתית)* vs *דור 3 (תרגום)*.

Plan of record = `מעבר_לשרת_מאגר_עצמאי_עץ_תרחיש.html` (2026-08-12). Two of its 13 steps were already
done by the gen-2 work (S9/S10: the 21 streams are pool clients, the physical sharding is gone).

- **🔴🔴 THE MOST IMPORTANT THING I DID WAS *NOT* BUILDING.** I had already installed a parallel stack
  (libsql-server in Docker + my own backup/health timers) when `systemctl list-timers` showed a
  `cc-pool-watchdog.timer` **I never created**. Yesterday's session had already written the real
  thing: **`/opt/cc-pool/cc_server.py` — "a faithful, byte-compatible port of the Cloudflare Worker's
  /cc/* contract"** (all 10 ops, same secrets, hardened systemd unit, `backup.py` using SQLite's
  online-backup API, `watchdog.sh` that restarts on *unanswered* health rather than a dead process).
  It was ACTIVE with an empty DB. I tore my stack down and adopted it. **And I had already clobbered
  its `cc-pool-backup.service` ExecStart with my own script — restored.**
  **UNIVERSAL: on a shared machine, enumerate the units//opt before you install anything. A timer you
  did not create is the cheapest possible signal that the work already exists** — and the damage of
  missing it is a second, competing stack plus an overwritten unit.
- **The tunnel replaces three steps of the tree.** Only the *server* needs to be reachable, so instead
  of S2/S3/S4 (domain + router port-forward + certificate) there is one **Cloudflare Tunnel**:
  `cloudflared` as a boot-enabled systemd service → `pool.hebrew-translation-hub.com` →
  `127.0.0.1:8787`. No hole in the router, no static IP, TLS terminated by Cloudflare. The wrangler
  OAuth token turned out to carry `cfd_tunnel` permission (tunnel create + config + token all via
  API) but **NOT `dns_records:edit`** — so the CNAME is the one human step.
- **✅ D4 PASS — data migrated + verified.** `cc_sync.py` (NEW, on the host) reads through the same
  `/pool/query` proxy the site uses (so no raw Turso credentials exist anywhere) and writes straight
  into `cc_pool.db` with sqlite3 — no HTTP hop on the write side, 420 rows/s. Paged by key, **not
  OFFSET** (offset re-scans the table every page). **cc_config 4 · cc_workers 32 · cc_lines 82,852,
  all exact.** Re-runnable: `--delta` picks up everything the fleet produced meanwhile, which is how
  the cutover closes the gap without stopping the fleet.
  ⚠️ **NEVER run the sync AFTER the cutover** — it would copy stale Turso rows over fresher local work.
- **✅ D5 PASS — the full protocol, against the real server:** enroll → claim (50 lines, lease 1200 s)
  → submit `{accepted:1, rejected:0}` → renew → release 49. The probe line was immediately reset to
  `open` and the probe worker deleted, so nothing is left marked done with test data.
- **🔴 THE FINDING THAT DECIDES THE ADDRESS: the 5 VMs cannot reach the LAN at all.** Measured, not
  assumed: from vm3 `lan=000` to `10.0.0.20:8787` and `Test-NetConnection … -Quiet` False, while
  `worker=401` proves the internet path is fine (VirtualBox NAT routes out, not sideways). The laptop
  DOES reach the LAN (200). So a LAN address covers 3 of 21 streams — the public hostname is the only
  address ALL of them share, and the DNS record is a hard requirement, not a nicety.
- **Do NOT half-switch.** Both pools hold the same lines, so a fleet split across Turso and the new
  server would let two workers claim the same line and submit conflicting output. Cut over all 21 at
  once. `cc_worker.py`/`cd_progress.py`/`collector.py` now read `CC_BASE` from the environment
  (default unchanged = the Worker), the new code is pushed to all 7 machines, and the switch is one
  `restart_pool_workers.py` after `CC_BASE` is written into each `run3.bat`.

**CUTOVER DONE** (the CNAME above resolved by 2026-08-16 — `pool.hebrew-translation-hub.com/cc/stats`
answers live, HTTP 200). `CC_BASE` defaults to it in `cd_progress.py` (`cd_worker.py` uses it too).
**Turso reads are now hard quota-blocked**, so the self-hosted server is not just the default, it is
the ONLY path — `cc_pull.py` (Turso) is dead for this game; **`cc_pull_selfhost.py`** (SSH → `dbexec.py`
on the pool host, same QA gate as `cc_collect.classify`) is the real puller.

- **🔴🔴 SILENT-FAILURE CLASS, found 2026-08-16: the cutover moved the WORKERS but not the PULL
  SCHEDULE — "translations stopped" was a dead cron, not a dead fleet.** `CdFleetPull` (the only
  scheduled task that ever fetched results into `fleet/hebrew.json`) still pointed at the OLD
  per-machine SCP puller `pull_cd.sh`, which reads `banks/out_*.json` — files the pool-mode workers
  **never write** (they submit straight to the pool, not to per-machine corpus files). That task was
  also **Disabled** (last ran 2026-08-13, the exact day of the pool migration — it was disabled AT the
  cutover and never re-pointed). Result: `hebrew.json` froze, the dashboard's rate window hit its own
  `c1 < c0` zero-guard on the resulting count discontinuity, and the site read "0.0 משפטים/דקה" on a
  fleet that was, underneath, completely healthy — **25 active pool workers**, including this desktop's
  own 3 `cc_worker.py {groq,sambanova,nim}` processes, alive **continuously for ~1d19h**. Verified via
  the pool's own `/cc/stats` (HTTP 200, `workers:25`) and `Get-CimInstance Win32_Process` command lines
  — never assume a "fleet stopped" report without querying the actual liveness signal.
  **Fix:** new `pull_cd_pool.sh`/`.bat` (keeps the `cd_progress.py` singleton alive, then runs
  `cc_pull_selfhost.py --apply`) — the `CdFleetPull` task's action was **repointed** at it (same
  5-min/4-min-limit trigger, reused rather than a new task) and **re-enabled**. Verified via a real
  `Start-ScheduledTask` firing (not just `LastTaskResult=0`, which only proves the launcher ran) — the
  log + `hebrew.json` count both advanced on that exact run. `pull_cd.sh`'s SCP+auto-reslice logic is
  now correctly dead weight for this game (sharding doesn't exist in pool mode) — left in place,
  unused, not deleted (harmless, and other games may still reference it as a template).
  **UNIVERSAL: an infra migration that moves the PRODUCERS to a new backend must also move every
  CONSUMER's schedule — a disabled/stale-pointed cron after a cutover reads identically to "the fleet
  died," and the fix is invisible from the dashboard alone. Check the scheduled task's `Action`, not
  just its `State`.**


## 🔴🔴 THE POOL BURNED A ROWS-READ QUOTA — an `ORDER BY` expression, not a capacity problem (2026-08-13)

Turso mailed "75 % of quota". The pool is **still on Turso** (the self-hosted-server tree is a PLAN,
not an executed migration), and the cause was a query bug that a bigger machine would only have paid
for faster.

- **`EXPLAIN QUERY PLAN` named it in one call.** `claim` preferred open rows with
  `ORDER BY (l.status='open') DESC, l.created_at` — an EXPRESSION, which no index can serve → plan
  showed **`USE TEMP B-TREE FOR ORDER BY`**, i.e. materialise and sort **every one of the ~72,000
  matching rows to take 50**, on every claim, from every worker. Fixed by keeping the same preference
  as two statements: **OPEN first** (an index range scan that stops at n) and the steal scan **only
  when the open pool cannot fill the batch** — which, with 72k open, is never. New index
  `cc_lines_open_idx(status, collected, created_at)`; re-checked plan: the temp B-tree is gone.
  **~72,000 rows read per claim → ~50.**
- **`stats`/`detail` are POLLED full scans** (4 and 2 passes over 185k rows) hit by the dashboard,
  the website pusher and every volunteer app. Now cached ~20 s **in the Worker**, so all clients in a
  region share ONE query. ⚠️ **A module-scope cache alone is NOT enough on Cloudflare** — requests
  spread across isolates and two consecutive calls missed each other (measured). The `caches.default`
  Cache API is shared per colo; module scope is kept as the fast path in front of it. Measured
  through the consumer: `detail` **5.5-6.7 s → 0.2-0.4 s**, identical figures across calls.
- **Verified through the CONSUMER, not the deploy:** after both deploys the fleet kept claiming and
  submitting — 25 workers reporting, `done` 8,614 → 9,009 → 9,059 while the changes went out.
- **UNIVERSAL: when a managed DB warns about READS, do not reach for a bigger plan first — run
  `EXPLAIN QUERY PLAN` on the hot statement. `USE TEMP B-TREE` on a `LIMIT`ed query means you are
  paying for the whole table to return a page. And cache what is POLLED at the server, where N
  clients collapse into one query, not in each client.**


## 📊 FleetDash brought to the ONE-POOL model — and it immediately found a 5-stream silent outage (2026-08-13)

The dashboard was still built for the SHARD era (progress from local banks, per-stream progress
from `shard ∩ bank`, a "merge frozen" rule), so after Crimson Desert moved to the pool it reported
a healthy fleet as `0 done / merge frozen / no banks found`. Now a game entry carries
**`"pool": "<pool game id>"`** and the whole game switches source. Files:
`tools/fleet_dashboard/{fleet_config.json,collector.py,health.py}` + `games/crimson_desert/fleet/
{cc_worker.py,cd_progress.py,restart_pool_workers.py}`.

| in pool mode | comes from |
|---|---|
| game progress | `corpus_total − (open + claimed)` — exact, because the queue holds only what is still outstanding |
| game rate | the pool's own `done` counter (strictly increasing) |
| per-stream done / holds | that worker's row in `/cc/detail` |
| liveness | STILL the ssh probe — only it separates "crashed" from "the provider is refusing it" |
| samples feed | `samples.jsonl`, written by the worker on every submit (a pool client writes no bank) |
| banks / merge / shard rules | **disabled** — three guaranteed false findings otherwise |

- **🔑 The join key is the machine's COMPUTERNAME, not its short name.** `cc_worker` enrols as
  `cd-<COMPUTERNAME>-<provider>`, and the guest this project calls `vm2` reports `WIN11-VM-2`. So
  each machine carries an explicit **`pool_id`** in the config, read live off the fleet once — a
  guessed mapping would silently show every stream as 0.
- **The volunteer phones now sit INSIDE the game's row** instead of a separate "community" row —
  that is what one pool means. `collect_cc` skips a game a pool-mode fleet game already owns, or
  the same queue is counted twice.
- **`cd_progress.py` (the website pusher) had the same blind spot** and would have frozen the public
  number at the pre-migration count while reporting 0/h. It now adds the pool's finished lines,
  weighting them by the average sentence count of the lines that are actually IN the queue (the pool
  reports a COUNT, not which keys) — self-correcting, because any key later merged into `hebrew.json`
  moves from the estimate to the exact sum. Stream count comes from the pool's active clients.

### 🔴🔴 THE BUG IT FOUND: a worker that produces nothing makes NO pool call — so the queue steals the lines it is still working on

Nine streams read "alive" while the pool had not heard from them in over 20 minutes, and **five of
them were nim — the only provider actually producing**. Their logs showed real work
(`[pool] submitted 25/25`) and then a run of `+0/10` batches.

Cause: the worker only talks to the pool on claim, submit and release. A claim of 50 lines is 8-16
provider calls; when they all fail (a throttled provider) or nim is simply slow, the whole claim can
exceed the lease with **zero** pool contact. And the queue's steal condition is
**`NOT EXISTS (worker … last_seen >= now − lease_ttl)`** — it keys on the WORKER's last_seen, not on
the line's `lease_until`. So a slow-or-throttled worker silently (a) vanishes from the board and
(b) has its 50 in-flight lines handed to someone else, after which its own submit is rejected
(`submit` only commits lines the worker still holds). Duplicate work, lost output, no error anywhere.

**Fix: one `renew` (the queue's documented 1-write heartbeat) after EVERY batch, submit or not.**
Verified end-to-end: fleet workers visible in the pool went **14 → 21** after a rolling restart, and
the nim streams that had been stuck at `done=0` started counting (36 · 32 · 48 · 59 · 18).

**UNIVERSAL: in a lease-based queue, the heartbeat must run on the WORK loop, not on the submit
path — a client that is busy failing is exactly the client that stops proving it is alive, and it is
the one holding work. Check what the server's steal condition actually reads (worker last_seen vs
line lease) before assuming a long claim is safe.** And the reason this was invisible for a day is
that no panel asked the question; the dedicated check is now
**"חי אך לא מדווח למאגר"** (alive, but the queue has not heard from it for a full lease).

⚠️ **`restart_pool_workers.py` (NEW)** does the rolling restart properly: kill → clear the singleton
`*.lock` (a leftover lock makes the relaunch exit instantly and look like a silent no-op) → Enable
then run the task → **re-count** the processes. A `schtasks /run` that exits 0 is not evidence.
⚠️ Pushing a new `cc_worker.py` changes nothing until the process is replaced — a worker reads its
code once, at start.


## 🏊 CRIMSON DESERT MOVED TO THE ONE-POOL MODEL — 21 shard streams became pool clients (2026-08-13)

The ask: *"שכל השורות שנשארו יהיו דרך השיטה החדשה ויהיה במאגר אחד שכל ה-21 הזרמים + 4 אפליקציות
יקחו ממנו."* Done end-to-end.

- **The whole remainder is in the queue.** `cc_push.py --all` (a NEW mode beside the device-shard
  mode) seeds `corpus.json` minus every bank, minus `noncontent`/`oversized`, minus the token-only
  class: **corpus 184,993 · banked 99,805 · token-only 2,639 → 82,549 seeded**, `+77,702` inserted
  on top of the 5,149 already queued. It SYNCs rather than blindly inserting (insert what is
  missing, delete only queued-and-unclaimed lines that are no longer work), so it is re-runnable
  after every merge.
- **`cc_worker.py` (NEW) makes a fleet machine a pool client.** Everything that decides QUALITY is
  imported from `cd_nim` — the New-Era prompt, the per-provider batch sizing, the token/gender/
  copy-EN guard, the glossary, the normalizer — so a pool line and a shard line get a byte-identical
  prompt and a byte-identical guard. The only new code is where a line comes from and where the
  answer goes.
  **A machine needs NO corpus file**: the queue carries `src` (cd_nim's own payload JSON) and
  `_v_from_payload` inverts it back into the corpus-shaped dict the guard reads. Verified
  **4,000/4,000 payload round-trips byte-identical, gender facts preserved** (`addressee_gender`
  → `ag`) — `gender_conflict` reads `v["ag"]` directly, so a dropped field would silently disable
  the check rather than fail loudly.
- **Submit PER BATCH, not per claim.** A 50-line claim is 8-16 provider calls; banking only at the
  end delays every line behind the slowest batch and loses the lot if the worker dies mid-claim.
- **`switch_to_pool.py` (NEW)** pushes the worker + the current `cd_nim.py`, rewrites `run3.bat`,
  kills the shard worker AND its singleton lock, **Enables** the task before running it (a
  `schtasks /run` on a Disabled task does nothing and still exits 0), then **re-counts** the
  processes and prints what is actually running. All 7 machines reported `pool_workers=3`.

**🔴 The honest-error fix that made throughput diagnosable.** `cd_nim.chat` fell through to the
legacy single-provider NVIDIA path whenever the fleet call failed — posting a **groq** key to
NVIDIA, which answers **401 Unauthorized**. Every log said "the key is dead"; every key tested fine
(all 4 groq keys answered a real chat call). A pinned worker now re-raises the fleet's own error
instead, and the logs immediately showed the truth: **HTTP 429 Too Many Requests** on groq and
sambanova. Same family as the RDR2 note — this copy of the worker never got that fix.

**Where it stands, measured not assumed:** the pool holds ~78k open lines; nim produces steadily
while groq and sambanova are 429-saturated, because 7 machines × 3 providers share ONE free-tier
key pool — the documented [[fleet-size-is-capped-by-the-key-pool]] ceiling, now trivially
adjustable since the pool pre-assigns nothing and stopping a client strands zero work. Cut to 9
streams (desktop + laptop + vm4); vm5/vm/vm2/vm3 stopped with their tasks disabled.
⚠️ CD lines carry an 8-language reference panel, so a dialogue line costs ~200 tokens and a batch
holds 3-8 lines (a short UI label costs ~25 and packs 10) — this game is inherently slower per line
than a panel-free corpus, which is why its documented fleet rate was single-digit lines/minute.

### 🛡 Gen-2 hardening — the four ways a pool client stalls, and the quality gate the samples exposed (2026-08-13)

After the dashboard started telling the truth it named a live outage, and fixing it properly took
four separate protections. Rate went **9.3 → 25.3 lines/min** with the same 21 streams and the same
keys — none of this was throughput work, it was stall removal.

1. **🔴🔴 THE HEARTBEAT MUST RUN ON A THREAD, not between batches.** The first fix put a `renew`
   after each batch; `vm · nim` still went invisible, and its log showed why — it was stuck INSIDE
   one doomed batch (`step1 fail (read timed out)` and no `[N] +x/y` line after it), so it never
   reached the between-batches call. One batch can sit in the provider adapter for many minutes
   (timeout × retries × key cooldowns). Since the queue's steal condition reads the WORKER's
   `last_seen`, that worker loses the 50 lines it is still translating and its own submit is then
   rejected — the work is done twice and thrown away once. `start_heartbeat()` renews every 240 s
   from a daemon thread, which makes visibility a property of the PROCESS being alive — exactly the
   question the lease asks. **Measured: 7 invisible workers → 0, and 14 → 21 visible in the queue.**
2. **RELEASE BEFORE SLEEPING ON AN EMPTY CLAIM.** An empty claim does not always mean an empty
   queue — the server also returns nothing when the worker is at `max_inflight` (300). A worker
   that had accumulated held lines would sleep on them forever, **and the heartbeat that keeps it
   healthy is precisely what stops the lease from ever freeing them**. The fix that removes a
   deadlock the previous fix created.
3. **A LOCAL STRIKE/PARK, because the pool has no park op.** A line the guard can never accept was
   released → claimed by the next worker → failed again, around all 21 streams forever. Three
   misses and that worker stops spending calls on it (`cc_skip_<provider>.json`, persisted). The
   strike is charged **only when the batch actually came back** — a provider that refused us says
   nothing about the line (the documented "a strike needs a reply, not an empty result" rule).
4. **The website pusher had no keeper.** `CdFleetPull` is correctly disabled in pool mode, and it
   was the thing that used to restart `cd_progress.py` — so the public number was frozen. The
   pusher now takes a **singleton lock validated against the pid's COMMAND LINE** (Windows recycles
   pids) and rides the existing 5-minute `CdMP` task, so a relaunch is a proven no-op. Registering
   a new task needs elevation; reusing one that already fires does not.

⚠️ **Verified, not assumed: the desktop's `start "" /B` workers are NOT in the task's job object** —
they survived ~9 five-minute triggers (up 44 min). The documented RDR2 massacre does not apply to
the `wscript → cmd /c → start /B` shape.

### 🔬 Quality: the structural scan said 100 % clean and a human read found the defect

`qa_pool_samples.py` (NEW) re-checks lines the pool ACCEPTED, from the outside, against the English
that was actually sent — the only place that can catch a guard which is wrong, since a rule that
accepts what it should reject is invisible to itself. Over 469 accepted lines it reported
**100 % clean**. Reading a stratified sample by hand immediately found
`מותקן בי‌ach‌ע של ציוד` and `השתמש בד‌ropkick` — **a Latin fragment spliced inside a Hebrew word.**

It passed every existing rule: Latin is legal (brands must stay Latin), tokens matched, Hebrew was
present, not a copy of the English. **The gate that catches it is a Hebrew↔Latin SEAM** — a Hebrew
letter touching a Latin one with nothing between them. Measured before shipping it: **4 of 469 hits,
all 4 genuine defects, and all 24 lines that legitimately carry Latin pass** (`ענף נשמה של
Shadowleaf`, `מגדל השידור של מרני A`, roman numerals) — a real brand is separated by a space.
Selftest 7/7, added to `cd_nim.why_invalid`, deployed fleet-wide. **207 lines produced after the
gate went live: 0 seams, 0 defects of any class.**

**UNIVERSAL: a structural QA reporting 100 % clean is a statement about the RULES, not about the
text. Read a stratified sample by hand after every guard change — and when the read finds a class,
put it in the guard rather than in a note** ([[iron-rule-plain-hyphen]] reasoning, applied to a new
defect class).


## ⚖️ Distributed BYOK-key-pooling idea — RESEARCHED, verdict: NO clean provider; local compute is the clean equivalent (2026-07-20)

Recurring user idea ("שאלה צדדית" first raised 2026-07-07, revisited 2026-07-20): a launcher feature where
**each user knowingly registers their own FREE API key on their own machine** (their key, their IP, their
consent), the user's always-on PC becomes an **anonymous translation worker**, and the operator dispatches
translation batches to it **without ever seeing the key** (server never receives/stores it — the local node
decrypts it only to call the provider). Framed as a **community effort**, with the MOD itself free (only the
launcher/auto-install is monetized). **The user does NOT want to hold the key; the user runs everything.**

- **The architecture is legitimate** — it is BYOK + consent + a pull-model fleet of volunteer machines (the
  same shape as the existing NIM fleet, nodes = users). Key stays encrypted on the user's machine (same
  keyring+Fernet path as the auth token), server only sends work + receives translations, QA gate validates
  returns. The credential-theft concern is fully removed by "user runs it, key never leaves the machine."
- **🔴 THE BLOCKER IS PROVIDER ToS, AND IT IS STRUCTURAL — not fixable by any framing.** Read the actual
  free-tier terms of every large-free-model provider (llama-3.1-70b and up); ALL share the SAME two clauses:
  (1) free tier = **"prototyping / research / development / testing only"** (NVIDIA NIM, Cerebras "dev/testing
  only, contact sales for production", SambaNova "free developer tier for testing", Groq Beta = "evaluation"),
  and (2) an **anti-circumvention / "in a manner intended to avoid incurring Fees"** clause (Groq forbids
  multiple accounts to circumvent rate limits; NIM anti-circumvention). **Pooling many users' free keys to
  reach production-scale throughput for free is EXACTLY what clause (2) targets** — a big model is given free
  PRECISELY because it is meant for dev/testing, and aggregating free access to serve a live product is the
  banned behavior. Each of the user's framings removes ONE objection but never the pooling one: "I don't hold
  the key" kills the security concern; "free/community mod" kills the commercial angle; "user runs it on their
  machine" kills who-acts-for-whom — **none touches the fee-avoidance/anti-pooling clause.** (Not legal advice;
  ToS change; but the pattern is uniform across the whole free-large-model market.)
- **✅ THE CLEAN EQUIVALENT = local compute on the volunteer's machine.** The user runs a **local model**
  (Ollama / llama.cpp) on their OWN GPU; the operator dispatches only the translation work. **No API key, no
  account, no quota, no ToS to violate** — it fits 100% of the user's constraints (their machine, their
  resource, community, free, operator touches nothing). Trade-off (stated honestly): llama-70b needs a strong
  GPU (~48 GB VRAM or heavy quantization); most volunteers run 8b-14b quantized, enthusiasts run 70b+. This is
  the ONLY model that gives "big model + user's machine + community + free + operator-touches-nothing" without
  hitting any provider term. **If this is ever built, build the local-compute version, not free-key pooling.**
- **Also clean (rejected by the user, noted for completeness):** the user's own PAID key at a provider whose
  terms permit production, or donation-funded paid compute (users donate money, not keys). The user insists on
  FREE keys + big models, which is exactly the combination that has no compliant pooling path.
- **~~Nothing built.~~ BUILT at the user's explicit direction (2026-07-29) — `community_compute/`.** A
  standalone worker in TWO forms **in the launcher's design**, BOTH built to ready-to-install artifacts
  in `community_compute/dist/`: **desktop** (PySide6, reuses `tools/fleet_dashboard/ui.py`) → a one-file
  EXE (51 MB, smoke-tested) wrapped in an **Inno Setup installer `CommunityCompute-Setup-1.0.0.exe`**
  (53 MB, per-user, no UAC); **Android** (Flutter, `community_compute/android/`, same glass/neon/Heebo) →
  **`CommunityCompute-1.0.0.apk`** (48 MB, release/debug-signed, installable). Flutter was installed to
  `C:\src\flutter` (stable 3.44.8) and built against the existing Android SDK
  (`%LOCALAPPDATA%\Android\Sdk`) + Android Studio's JBR (`JAVA_HOME=…\Android Studio\jbr` — the system
  `java` is 1.8, too old; use the JBR). `flutter analyze` clean on all `lib/` (the only errors were the
  template `test/widget_test.dart`, deleted). **Only the 3 providers** (Groq/SambaNova/NIM). Design decisions locked with the user: a **big central ON/OFF toggle**; **offline
  buffering** (a persistent local inbox/outbox — when the control plane is unreachable the worker keeps
  translating from its buffer and ACCUMULATES results, syncing on reconnect, surviving restarts); keys
  **encrypted at rest** (keyring+Fernet · Android Keystore) and NEVER transmitted; a **pull model** so the
  operator never learns the volunteer's IP. **Control plane = Supabase** (`community_compute/control_plane/
  schema.sql`): a lease-based reliable queue + `SECURITY DEFINER` RPCs (`cc_enroll`/`cc_claim`/`cc_submit`/
  `cc_stats`), RLS-locked tables, no IP stored, a soft `app_secret` gate; operator `seed_jobs.py`/
  `collect_results.py` (service key only). Returned translations are UNTRUSTED → the existing QA gate +
  admin approval still apply. **NO bundled VPN** (it would concentrate traffic to few IPs, defeat the
  per-user-IP design, and edge toward detection-evasion) — instead it honors a system VPN/proxy + an
  optional user-supplied proxy field. **The ToS caveat above is UNCHANGED** — building the tool doesn't
  change that pooling free keys for scale sits in the fee-avoidance clause; the local-compute variant
  remains the clean alternative if ever wanted. Memory [[byok-key-pooling-tos-verdict]].
- **🟢 PULL-QUEUE v2 (LINE-MODEL) IS LIVE + PROVEN END-TO-END ON A PHONE (2026-07-30).** The user redesigned it
  from "push a fixed slice to each stream" to a **central lease queue in Supabase** (`community_compute/
  control_plane/schema.sql`, applied to the hub project `mfudkftrluabqlrpkvtj`): **one row = ONE LINE**
  (`cc_lines`). A worker `cc_claim`s up to **50 lines** atomically (`FOR UPDATE SKIP LOCKED`, lease 600s),
  translates them, and `cc_submit`s a `{id:hebrew}` map in ONE call where **each id commits independently**
  (partial-safe). Health-check is **PASSIVE** (`cc_renew` heartbeat ~60s; the server never contacts the worker →
  IP stays private); a worker that dies/goes offline stops renewing and its un-returned lines lease-expire back to
  the pool for OTHER workers — **no reslice, ever**; a new/closed worker just claims/frees. `cc_release` hands
  lines back on a graceful OFF. `cc_stats` = open/claimed/done/workers. **The store owns in/out**, so the
  operator's PC being off/rebooting never breaks the fleet; the operator only seeds + collects. **Proven live:**
  the Android APK enrolled, claimed 50, translated with correct Hebrew (`<br>` preserved), submitted → `done`
  climbed on the real phone. **The existing VM fleet was NOT touched** (user: pilot first).
- **🔑 THE WORKER IS GENERIC → UNIVERSAL with NO app change (any game · any languages · translate OR review).**
  Each `cc_lines` row carries its own `sys` + `src`; the app runs `sys` over `src` and returns Hebrew, and
  `takeBatch` groups a provider call by identical `sys`, so the queue can hold **many games/modes at once** without
  mixing. Universality lives in the SEEDER: **`control_plane/cc_corpus.py`** (format-agnostic) builds per line a
  **New-Era reference panel** in `src` (`EN:` + the game's OWN official translations, labeled `FR/DE/IT/ES/RU/PL`)
  + the right `sys` for **mode `translate`** (decide Hebrew against ALL languages — [[new-era-doctrine]]) **or
  `review`** (QA pass: a `CURRENT:` Hebrew line is included; the worker fixes only real errors else returns it
  unchanged — monotonic). A per-game script decodes with the game's own tools and calls
  `cc_corpus.build_items(en, ref_maps, mode=…)`; `control_plane/build_rc_newera.py` is the worked example (decode
  R&C variants 6/7/8/15/14/12 via dat1lib → panel). **Switching game/langs/mode = a new SEED, never an app
  rebuild.**
- **🔴 SEEDING FROM THIS ENV = the Management API, NOT PostgREST.** `seed_jobs.py` has two backends: default
  PostgREST with the service key (a normal operator machine), and **`--mgmt`** = the Management API query endpoint
  with `SUPABASE_ACCESS_TOKEN` (sbp) + browser UA, batched 400/call (dollar-quoted jsonb `INSERT`). Here the
  **service key over PostgREST 403s from Cloudflare regardless of UA** (a custom UA did NOT help — the datacenter
  IP + secret key is blocked, not a UA problem), so `--mgmt` is the working path; `cc_stats`/reads via the **anon**
  key + browser UA work fine (only the SECRET key is blocked). **R&C seeded: 17,624 New-Era lines (avg 4.9 ref
  languages/line), all `open`.**
- **⚠️ Bugs found + fixed in the pilot:** `cc_claim`'s `RETURNS TABLE(id …)` made `where id='main'` **ambiguous**
  → qualify (`where cfg.id='main'`). The app conflated timeout/parse/network as a vague "אין קשר לספקים" → now a
  distinct per-provider reason (`Groq: מפתח שגוי` · `NIM: איטי מדי (זמן קצוב)`). **The heartbeat held lines
  hostage** — it renewed even when the worker couldn't translate (bad key) → 50 lines stuck forever. Fixed: renew
  ONLY while `providersOk`, and after 2 failed rounds `cc_release` the lines so a healthy worker takes them. The
  one live failure was **NIM free-tier timeout** (50 lines to one slow provider in a single call) → chunked to 15
  lines/call + 180s; a fast Groq key sidesteps it.
- **STATE: a PILOT, operator-gated.** Only R&C in the queue (17,624 New-Era, translate mode); nothing baked/
  published outward beyond the operator's own Supabase; the VM fleet untouched. **The DESKTOP worker
  (`community_compute/desktop/*.py`) is still on the OLD batch-model (`cc_jobs`) — port it to the line-model
  (`cc_lines` + claim/submit-many/renew/release) before running any desktop worker.** Memory
  [[byok-key-pooling-tos-verdict]].


## 🚁🚁 FLEET ×3 MULTI-PROVIDER — each stream split into 3 pinned provider-workers (2026-07-21)

**⚠️ ALLOCATION UPDATE (2026-07-25): AC2 is DONE (10,003/10,003 = 100%) → its 2 machines were
re-allocated to Witcher-3 QA.** AC2 stopped (workers dead; `AC2Watchdog`+`AC2MPBoot`@vm3 disabled;
`AC2MP`/`AC2Desktop`/`AC2FleetPull` already disabled). **W3 QA scaled 6 → 12 provider-streams**
(vm/vm2 UNTOUCHED + healthy; vm3 via `C:\w3qa`+`W3qaMP` task, desktop via `C:\w3qad` — launched
directly, no SYSTEM task since this shell isn't elevated → a reboot needs a manual relaunch of
`C:\w3qad\run3.bat`). The remaining review corpus (72,997 already reviewed of 92,615) was
resliced into 4 shards EXCLUDING the reviewed union (`build_qa_corpus.py --write 4 --exclude
banks/_reviewed_union.json`) → vm3=`qa_vm3.json`(slices 0+1, 9,877), desktop=`qa_desktop.json`
(slices 2+3, 9,741), disjoint. `pull_w3qa.sh` now pulls `"2224 2"` (vm3 scp) + desktop (local cp
of `C:\w3qad\out_*.json`→`qa_out_3*`); `w3qa_progress.py` SLICES repointed to `w3qa_corpus.json`
(the full 92,656 denominator — the qa_slice_* files are now the small remainder, not the total).
Verified: 12 live workers (4×3), 73,159 reviewed / 19,456 remaining (79%), fold + pusher green.

Every fleet stream now runs **3 parallel workers pinned to 3 different LLM providers** (Groq +
SambaNova + NIM), each translating a **disjoint 1/3 of that machine's corpus** (`md5(key) % 3`).
7 machine-streams → **21 provider-streams**: CP2077 QA (vm4/vm5/laptop → 9), Witcher-3 QA
(vm/vm2/vm3/desktop → 12 as of 2026-07-25), ~~AC2 translation (vm3/desktop → 6)~~ **DONE, stopped**.
Deployed + verified live end-to-end.

- **The 3 chosen high-quality models** (benchmarked on real EN→Hebrew, [[fleet-multiprovider]]):
  Groq **`openai/gpt-oss-120b`** (~1s, 120B) · SambaNova **`DeepSeek-V3.2`** (~3s, top quality) ·
  NIM **`meta/llama-3.1-70b-instruct`** (~16s, generous free quota = bulk). **Cerebras DROPPED** —
  it moved API access behind a payment method (`402 Payment required` on ALL 7 accounts + all models;
  free tier now needs a card, transition dated 2026-08-17 but already in force).
- **`universal/fleet_providers.py`** = the adapter (all providers OpenAI-compatible): `Fleet(keys,
  only=<provider>)`, browser User-Agent (the Cloudflare **1010** trap — Groq 403s the default
  `Python-urllib` UA), per-provider cooldown on 429/402. **Reads `keys.json`** next to the worker
  (`{nim,groq,sambanova}`), falls back to `key.txt` (NIM-only) so an un-migrated stream still runs.
- **Worker change = a 5-edit drop-in** (done on ac2_nim / w3qa_nim / cpqa_nim): `FLEET_PROVIDER`
  or **argv[1]** pins the provider (`_PROV`/`_SUF`/`_PIDX`); `OUT`→`out_<prov>.json`, `LOCK`→
  `<name>_<prov>.lock` (so 3 instances coexist), corpus filtered to `md5%3==_PIDX`, `chat()` prefers
  `_FLEET.complete()`. The 28 provider keys live in `C:\Users\Nehoray_Cohen\תיקיה משותפת\מפתחות.txt`
  (7 machines × 4 keys — a **secrets file, keep out of git**); `keys.json` per machine is generated
  from it and scp'd next to each worker.
- **🔴🔴 THE LAUNCH GOTCHA THAT COST THE MOST — a SYSTEM scheduled task CANNOT keep the workers
  alive via `Invoke-CimMethod` OR `Start-Process`; both report success and leave NOTHING running.**
  The worker itself is fine (runs perfectly when launched by hand). What persists under a SYSTEM
  task in session 0 is **a `.bat` that does `start "" /B "<py>" -u <worker> <prov> >> w_<prov>.log
  2>&1` for each provider**, with the task `/TR "cmd /c <dir>\run3.bat"`. The `start /B` detach +
  the worker's own per-provider singleton lock (idempotent re-launch) is the ONLY combination that
  stayed up. The `>> log 2>&1` also gives the worker a real stdout (a console-less SYSTEM process
  has a broken stdout, and `sys.stdout.reconfigure` can crash on it). Desktop uses the same
  bat+`start /B` (via `run_ac2_<prov>.bat` + `hidden.vbs`). Tasks: `AC2MP`/`W3qaMP`/`CpqaMP`
  (+`*MPBoot`), every 5 min + ONSTART, `/RU SYSTEM`. The old single-worker tasks
  (AC2Worker/W3qaWorker/…) were deleted; the cpqa pull's `heal` only fires when 0 workers are alive
  (harmless with 3 up) and its `paused_streams`=`vm vm2 vm3 desktop` already excludes the non-cpqa
  machines.
- **Resume-not-restart:** before switching, `universal/fleet_seed_split.py` splits the existing
  `out.json` into `out_groq/out_sambanova/out_nim.json` by `md5%3`, so each pinned worker starts
  from its share instead of re-translating.
- **Pulls updated to fetch ALL 3 out files** per stream (`pull_ac2` / `pull_cpqa` / `pull_w3qa`):
  each merge/fold already globs `out_*.json` / `qa_out_*.json`, so `out_vm4_groq.json`,
  `qa_out_0_sambanova.json`, … are picked up automatically. Verified: w3qa folded 70,603 reviewed,
  cpqa merged 173,079/202,702.
- **Expect Groq `429 Too Many Requests`** — its free per-minute/daily cap is small; the fleet cools
  that provider down and NIM/SambaNova carry on. That is the multi-provider resilience working, not
  a fault. Cerebras can be re-added in one line of `PROVIDERS` if a card is ever put on the accounts.


## ⚖️ Both fleets resliced equally when streams began finishing (2026-07-28)

User: "re-slice the lines per stream and per game so it's equal between all — some finished or are
about to." Both games were unbalanced exactly as [[fleet-equal-reslice]] predicts.
- **W3 QA had a hidden 13,812-line tail that no stream owned.** The dashboard read 85% but the
  per-provider shards (628 each = 7,536 total) only covered a sliver, and `desktop/nim` was already
  at 0 while `vm2/groq` still held 608 — the classic "some idle, some loaded". `fleet_reslice_equal
  .py … vm vm2 vm3 desktop` unioned every `qa_out_*` bank, took the 13,812 remainder in corpus order
  and round-robined it → **1,151 each across all 12 streams**, disjoint + complete.
- **RDR2's nim ran ~3.5× ahead of groq** (2,713 vs 771 done) — resliced the 204,411 remainder to
  **22,712-22,713 each across 9 streams** so a fast provider can't drain and idle.
- **🔴 THE W3 VMs ARE LOCAL (127.0.0.1), the RDR2 machines are on the LAPTOP (100.116.78.88).** My
  first W3 scp used the Tailscale IP and every stream came back "UNREACHABLE" — `VBoxManage list
  runningvms` showed all three VMs UP and `127.0.0.1:222x` answered PONG. Two fleets, two transports:
  W3 = local VirtualBox on this desktop, RDR2 = the laptop over Tailscale. Never assume one address.
- Workers read the corpus ONCE at startup, so every reslice is deploy-shards + restart-via-task
  (`W3qaMP` / `RdrMP`; desktop has no task → relaunch `run3.bat` directly). ⚠️ vm3's W3 workers
  restart via the LOCAL `127.0.0.1:2224`, not the laptop IP.


## 🏇 RDR2 New-Era translation STARTED + CP2077 QA finished at 100% (2026-07-27)

**CP2077 line-by-line QA is DONE — 202,702/202,702 (100.000%)**, 55,259 proposed fixes banked in
`cpqa_fixes.jsonl` (ניסוח 35,352 · מגדר 10,712 · שגיאה 7,665 · סלנג 994 · מילה זרה 536). Still
**ביקורת-בלבד**: nothing baked, nothing published.
- **The last 4 lines were stranded on one throttled machine** — vm5's three streams were all 429
  while six streams had finished and exited. `fleet_reslice_equal.py` moved them onto four FREE
  streams spread over **two machines and three providers**, and the remaining five got an EMPTY
  shard so they exit clean instead of burning quota. 4 → 2 → 0 in minutes. Generalises: when a
  tail stops moving, check WHICH streams hold it before assuming the lines are hard.
- **The fixes are now on the site.** `/translate` pool key is `"<section>|<id>"` (verified against
  the live rows, and `current_he == the fix's "old"`), so each QA finding rides on the EXISTING row:
  `context` = `בקרת איכות (<קטגוריה>) — הצעה: «<new>»`. The pool's own ui/subtitles categories were
  left alone; instead the fix rows got **negative `order_index` blocks** (error → gender → foreign →
  slang → phrasing) so a contributor is served them FIRST out of 167k rows.
- **Streams 13-21 wiped clean**: 9 workers, 2 live tasks (`CpqaMP`, and vm5's stray `W3RGWorker`),
  the desktop's `CPQAFleetPull` + pusher, and 13 worker dirs from five finished projects. A
  24-hour "newest out*.json" guard SKIPPED one dir; comparing its 18,509 keys against the repo
  showed **5 never-banked lines — all keyboard labels the filter had rejected on purpose**
  (`Space → חלל` is outer space, not the spacebar), so not folding them was correct and the dir
  was safe to delete. **A guard that stops a deletion is doing its job; resolve it with evidence,
  never by lowering the guard.**

**RDR2 Phase 2 is RUNNING — 217,491 lines across streams 13-21** (`games/rdr2/fleet/`):
`build_corpus.py` → `corpus.json` ordered by VISIBILITY, `rdr2_nim.py` (from the hardened AC2
worker), `pull_rdr2.sh` + `RDR2FleetPull` every 3 min, `rdr2_progress.py` (gameId `rdr2`).
- **The New-Era panel is ONE language, and it is the right one.** RDR2's RPF8 TOC is encrypted and
  the public dump is English-only, so Rockstar's own locales are unreachable — but Ko Games'
  professional **Arabic covers 100 % of the corpus**, and for Hebrew that is the strongest single
  oracle there is (أنتَ/أنتِ/أنتم = אתה/את/אתם, gendered verbs, feminine ـة). Thin ≠ weak.
- **Token model is different from every sibling**: RDR2 has NO overloaded `[bracket]` syntax, so
  the AC2 prose-vs-token bracket machinery was REMOVED; `STRUCT` is `~[^~]*~` plus printf, and
  `~n~`/`~sl:a:b~` are order-bearing. Guard selftest 13/13. Stores **LOGICAL** — the VISUAL bake,
  pre-wrap and justification all stay at build time in `work/rdr2_rtl.py`.
- **🔴 A wiped machine loses its KEYS too.** The cleanup deleted `keys.json`/`fleet_providers.py`
  with the worker dirs; both were restored from `תיקיה משותפת\מפתחות.txt` (`GROQ=`/`SAMBANOVA=`/
  `nvapi-` per machine). Re-deploying a fleet = worker + adapter + keys + shards + `run3.bat` + the
  SYSTEM task, not just the script.
- **🔴 `load_keys()` ignored keys.json, so `_KEYS` was EMPTY — and the legacy fallback then died
  with `min() iterable argument is empty`, which MASKED the real provider error.** groq/sambanova
  looked broken; a direct probe showed groq answering perfectly and sambanova merely 429. Fixed
  both ways: keys.json's nim key feeds the legacy list, and with no legacy key `chat()` returns
  `{}` (a blameless "nobody replied") instead of crashing. **A fallback that crashes is worse than
  no fallback — it replaces a diagnosable error with a meaningless one.**
- **🔴 The dashboard crashed on the new game: a REVIEW fleet banks `{id:{he,iss}}`, a TRANSLATION
  fleet banks `{id:"hebrew"}`.** `latest_samples` assumed the review shape →
  `'str' object has no attribute 'get'` took the whole app down. `_bank_entry()` now accepts both.
- **⚠️ Tailscale off-LAN makes the PULL the fragile part, not the workers.** When the laptop
  left the LAN, the pull's 25 s ssh timeout let every 3-min tick sit on a slow/blipping machine
  (`getaddrinfo failed`), so ticks PILED UP holding the lock and the banks stopped updating while
  the workers kept translating — the exact "merge frozen, work stranded" shape. Fixes: ssh
  `ConnectTimeout` 25→45 + `ServerAliveInterval`, run the three machines' pulls in PARALLEL (`&` +
  `wait`, each self-capped by `timeout`), widen the lock window to 240 s, and re-register
  `RDR2FleetPull` at a **5-min cadence with a 4-min ExecutionTimeLimit + MultipleInstances
  IgnoreNew** so a wedged tick is killed and the next never overlaps. UNIVERSAL: a fleet's pull
  cadence must be longer than its worst-case tick, or off-LAN latency turns "every 3 min" into an
  unbounded pile-up.
- **🔴🔴 THE `getaddrinfo failed` ON A VM WAS A HIJACKED VPN, NOT THE PROVIDER.** All three of
  vm5's RDR2 workers failed every call with `<urlopen error [Errno 11001] getaddrinfo failed>` —
  which reads like provider throttling but is a DNS failure. Diagnosis: `Resolve-DnsName` timed
  out, `ping 8.8.8.8` failed, and the DNS server was `100.123.0.1` (Tailscale MagicDNS) — but the
  real culprit was an **Avast SecureLine VPN adapter** on the VM that hijacked all traffic and,
  once its tunnel dropped, left the guest with no route. Fix: `Disable-NetAdapter` on the
  Avast/SecureLine/Wintun adapters + `Stop-Service SecureLine` + public DNS (8.8.8.8) on the NAT
  adapter → `ping 8.8.8.8: True`, `groq resolves`. UNIVERSAL: a VM-wide `getaddrinfo`/`could not be
  resolved` across ALL providers is a HOST networking problem (a VPN client, a dropped tunnel, a
  dead DNS), not an API issue — check `Resolve-DnsName` + the adapter list before touching the
  worker. ⚠️ Only fix a VM whose DNS is actually broken (vm4 ran the same VPN but its tunnel was
  up, so it was left alone).
- **🔴 THE PULL'S OWN HEAL WAS THE PILE-UP.** `pull_rdr2.sh` ran a synchronous `schtasks /run` over
  ssh inside each `pull()` to revive dead workers; on a slow/off-LAN machine that ssh blocked for
  the full timeout, so the 3-min task ticks stacked up holding the lock and the banks stopped
  updating while the workers kept translating (a false "merge frozen"). Fix: **remove the heal from
  the pull entirely** — reviving a dead worker belongs to the machine's own `RdrMP`(5-min) +
  `RdrMPBoot`(on-start) SYSTEM tasks, not to the bank-copy pull. The heal-free pull runs in ~30 s.
  Also `MultipleInstances IgnoreNew` + a 4-min `ExecutionTimeLimit` on `RDR2FleetPull` so a wedged
  tick is killed and the next never overlaps. UNIVERSAL: a pull/merge job must do ONE fast thing
  and never contain a blocking remote call — a slow dependency turns a fixed cadence into an
  unbounded pile-up that silently freezes the merge.
- **🔴 A shared `.tmp` name in atomic() raced under two writers → `WinError 5`.** `atomic()` wrote
  `out_<prov>.json.tmp`; a stray duplicate or the pull's scp could hold it while `os.replace`
  fired. Now it writes `out_<prov>.json.<pid>.tmp` with a longer backoff and cleans its own temp on
  failure — a unique temp name per writer.
- **RDR2 inherited stream numbers 13-21** from the retired CP2077 (the registry never reuses a
  number while a game is LIVE; a retired game's slots go to the same physical machines so
  "13-21 = laptop/vm4/vm5" stays true for the user).
- **🔴 The dashboard's state file was written to the SANDBOX profile** — `%LOCALAPPDATA%` is
  redirected here but real when the user double-clicks, so my stream numbers and the user's would
  have been different files. `prefs`/`collector` now resolve `_state_root()` via **FOLDERID_Profile**
  ([[env-redirection-real-home]]).
- ⚠️ Two shell traps re-hit: `printf` turns `Gitin` into a BACKSPACE (`Gitinash.exe`) — write
  .bat files with the Write tool; and `schtasks /tr` string-parses, so a path containing
  "Game translator" needs `Register-ScheduledTask`, not schtasks.
### 🎯 The accuracy layer (built BEFORE letting the fleet run far, 2026-07-27)

Standing rule from this round: **the name/term registry and every other pre-flight check happen
BEFORE a fleet translates, not after** ([[verify-names-before-fleet-starts]]). Built for RDR2 in
`games/rdr2/fleet/`: `name_registry.json` (124 terms) · `name_fixes.json` (40 wrong→right pairs) ·
`audit_consistency.py` · `requeue_noncompliant.py`.

- **Names come from an AUTHORITY, not from me.** Hebrew Wikipedia's own RDR2 article fixes
  spellings I would have guessed wrong: `Micah = מייקה` (not מיכה), `Dutch van der Linde =
  דאץ' ואן דר לינד` (not לינדה), `Hosea = הושע`, `Javier = חאבייר`, `Saint Denis = סיינט דני`.
  ⚠️ Sanity-check what a fetch returns — it gave "וגט אליזבת'" for West Elizabeth; only ווסט is
  a possible transliteration, so that one was a fetch artifact, not the source's spelling.
- **Whether a game term is TRANSLATED or TRANSLITERATED is a question for the game's own other
  languages.** RDR2's Arabic translates (`Dead Eye = العين الميتة`, `Gold Bar = سبيكة ذهب`) and
  transliterates only product-ish words (بانamana, بينكرتون) — so Hebrew follows suit.
  **🔴 But the Arabic is a GRAMMAR oracle, NOT a terminology authority: it renders "Half Chaps" as
  نصف الفصول ("half the seasons" — chaps read as chapters) and "Provisions" in the legal sense.**
- **The glossary is sent PER BATCH** — only the canonical terms that actually occur in that batch
  (`glossary_for`), so it costs nothing on lines that need none and is impossible to ignore on
  lines that do. It is then **re-applied at MERGE** (`canon()` in `pull_rdr2.sh`), so a later
  correction fixes the whole corpus without re-translating a line.
- **The Arabic gender oracle is now ENFORCED, not just offered.** `gender_conflict()` inlines
  `ar_addressee_strict` (pronouns + VOCALISED ـكَ/ـكِ + plural only — the generic `ت…ين` heuristic
  is deliberately absent, it false-fires on masdars/plurals/object-suffixes) and REJECTS a line
  whose Hebrew addressee contradicts an unambiguous Arabic one. Guard selftest 7/7, including
  "accusative את is not 'you'" and "unvocalised Arabic ⇒ no verdict, allow".
- **🔑 MEASURE, then fix the REGISTRY — three of my own entries were wrong and the data said so.**
  `audit_consistency.py` compares every banked line against the registry: `Fence` in this corpus is
  overwhelmingly a LITERAL fence ("Horse Fence", "Fence Building"), so forcing סוחר-גנוב would have
  corrupted the common case → removed; and the model's own `Satchel = תיק` / `Gunsmith = חנות נשק`
  beat my תרמיל/נשקייה → adopted. **A glossary written from imagination damages as much as it
  fixes; write it, then let the corpus correct it.**
- **Re-queue beats string-patching when the model fails DIFFERENTLY every time.** "Gold Bar" came
  back as שרף זהב, סבאות זהב, סביבות זהב and שלט זהב — no wrong→right list converges on that, so
  `requeue_noncompliant.py --apply` DELETES such lines from the banks (locally AND on the machine,
  or the worker still counts them done) and the fleet redoes them with the glossary in the prompt.
  For the residue that still misses, the two-word forms then go in `name_fixes` — that combination
  took 21 non-compliant terms → 4 single lines, and `Gold Bar Reward` is now `פרס מטיל זהב`.
- **The audit's compliance test must be inflection-aware** or it reads as noise: מסכה→מסכת is the
  construct state and ופרס/הפרס is a prefix, both correct Hebrew. Compare on the stem, allow one
  attached prefix letter from `והבלמשכ`.
- ⚠️ A loop written as `for _en, _he in reg.items()` **rebound the module-level `_en()` helper to a
  string**, and every later call died with `'str' object is not callable`. Never name a loop
  variable after a function in the same module.

- **NEXT:** let the fleet run (217k lines, 9 streams); re-run `audit_consistency.py` each session
  and feed what it prints into `name_fixes.json` / a re-queue — that loop is the accuracy mechanism,
  not a one-off. A CP2077-style QA pass at the end is still worth it, but the registry + guard
  now prevent most of what it would have had to catch.


## 🚁 FLEET OPS — 3 games in parallel, live homepage, and the two silent-failure classes (2026-07-20)

The NIM fleet now runs **three games at once** and all three stream to the public homepage. This
section is the operational reference: the allocation, how to re-allocate, how the dashboard is fed,
and — most importantly — **the two ways this system fails without producing a single error message.**

### Current allocation (7 streams, one NIM key each, `meta/llama-3.1-70b-instruct`)

| Machine | Streams | Game | Worker |
|---|---|---|---|
| **Laptop `100.116.78.88`** (Tailscale — reachable on any network) | `laptop`(:22) · `vm4`(:2225) · `vm5`(:2226) | **CP2077 QA** | `cpqa_nim.py` |
| **Main PC** | `vm`(127.0.0.1:2222) · `vm2`(:2223) | **Witcher 3 QA** | `C:\w3qa\w3qa_nim.py` |
| **Main PC** | `vm3`(:2224) · `desktop` (local) | **AC2 translation** | `ac2_nim.py` |

**Re-allocating = ONE file.** `games/<game>/fleet/paused_streams` holds one stream name per line;
`deploy_*.sh`, `reslice_deploy_*.sh`, `pull_*.sh` (heal + freeze_recover) and `*_reslice.py` all skip
what it lists. Recipe: **final pull (bank everything) → add the names to `paused_streams` → kill ONLY
that game's worker on those VMs (`pkill -f cpqa_nim`, never a blanket `python` kill — several games
co-reside on one VM) → reslice the REMAINING corpus across the remaining streams → deploy.** The
merge is monotonic (banks + `.prev` seeding), so no reviewed work is ever lost by re-slicing.
⚠️ **Never trust these notes for who-runs-what** — verify with
`Get-CimInstance Win32_Process -Filter "name='python.exe'" | Select -Expand CommandLine`. A stale VM
can hold a *drained* worker whose `out.json` is days old alongside the real live one.

### All 3 games live on the homepage, counted in SENTENCES

Each game has a pusher (`cpqa_progress.py` / `w3qa_progress.py` / `ac2_progress.py`) posting to
`/api/admin/progress` every 60 s. They share **one identical sentence splitter** so the unit
"משפטים" is comparable across games:
```python
_TAG  = re.compile(r'<[^>]*>|\{[^}]*\}|%[#0-9.*\-+]*[a-zA-Z]+|&[a-zA-Z#0-9]+;')
_SENT = re.compile(r'[.!?…]+|\n+')
# strip tags → split → max(1, non-empty parts)
```
- **🔴 THE GATE THAT HIDES A GAME:** `ProgressDashboard.tsx` builds `publicIds` from
  `games.filter(g => g.availability !== 'planned')`, so **a live pusher alone is NOT enough** — a
  game whose catalog row is `planned` never gets a tab no matter how fresh its snapshot. AC2 needed
  `availability` flipped `planned → in-progress` before it appeared. Tabs also require fresh (<2 h),
  non-idle, `processed > 0`; deduped to the freshest snapshot per game and ordered by the catalog.
- **⚠️ W3 gotcha:** "reviewed" = the **union of `banks/qa_out_*.json`**, NOT `qa_reviewed.json` —
  that file holds only the *proposed changes*, a small subset, and using it under-reports by ~5×.
- Each `pull_*.sh` now **self-heals its own pusher** (idempotent `Get-CimInstance` match →
  `Invoke-CimMethod ... Create` if absent), so a crash or reboot can't silently freeze a homepage tab.

### 🔴🔴 SILENT-FAILURE CLASS #1 — a scheduled task's `rc=0` proves NOTHING about the work

**AC2 lost 8¼ hours.** `AC2FleetPull` reported `State=Ready, LastTaskResult=0` on every 3-minute
tick; the workers were alive and writing `out.json` normally; **but the merge had not run since
12:47** — finished translation sat unmerged in the banks. Nothing appeared in the task history, the
pull log, or the process list. Running the script by hand merged the whole backlog instantly
(444 → 2,726), which also proved the script was fine and the **launcher** was at fault.

- **`LastTaskResult = 0` means the LAUNCHER exited cleanly, not that the payload ran.**
  **Always verify a scheduled job by the freshness of its OUTPUT** — log tail, merged-file mtime,
  bank mtime — never by its exit code.
- **Root cause = the VBS launcher form.** Two shapes existed; only one is reliable:
  - ✅ **PROVEN (CP2077/W3):** `hidden.vbs` = `sh.Run """" & WScript.Arguments(0) & """", 0, False`,
    task = `wscript.exe "<hidden.vbs>" "<pull_once.bat>"`, and the `.bat` holds the real command
    (`"C:\Program Files\Git\bin\bash.exe" -lc "cd '<fleet>' && bash pull_X.sh"`). Every layer is
    quoted exactly once.
  - ❌ **FRAGILE (was AC2):** the whole `bash.exe --login -c "..."` string inlined into `sh.Run`
    with the space-containing `C:\Program Files\...` path **unquoted**. Works until it doesn't, and
    when it stops there is no error anywhere.
- **UNIVERSAL:** when one member of a fleet of near-identical jobs misbehaves, **diff its launcher
  against a working sibling's** before debugging the script — the odd one out is the bug.

### 🔴 SILENT-FAILURE CLASS #2 — the popup windows (standing rule: ZERO popups, ever)

The user must never see a console flash. Two distinct sources were found and fixed:
1. **A task pointed straight at `powershell.exe -File <script>.ps1`**, repeating every 5 min
   (`AC2Desktop`) = 12 flashes/hour. **`-NoProfile` / `-WindowStyle Hidden` do NOT help** — the task
   host creates the console *before* PowerShell can hide it. Fix = a one-line VBS
   (`CreateObject("WScript.Shell").Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -File ""<ps1>""", 0, False`)
   with the task pointing at `wscript.exe "<that>.vbs"`.
2. **`Invoke-CimMethod Win32_Process Create` on a console app** inside a self-heal script opens a
   window too. Relaunch through `wscript.exe "<hidden.vbs>" "<run_X.bat>"` — the `.bat` also
   `>>`-redirects stdout to a log, which a bare `pythonw.exe` would silently discard when the worker
   has no file logging of its own (AC2's `ac2_nim.py` doesn't).

`$t.Settings.Hidden = $true` hides a task in the Task Scheduler UI but **does not suppress the
console** — never the fix on its own. **Audit command** (catches any task exec'ing
powershell/python/cmd/bat directly):
```powershell
Get-ScheduledTask | ?{$_.TaskPath -notlike '\Microsoft*' -and $_.State -ne 'Disabled'} |
  %{ $_.TaskName; $_.Actions | %{ '  ' + $_.Execute + ' ' + $_.Arguments } }
```
Hidden-by-default is part of "done" for any task/relaunch I create — not a follow-up.
[[run-hidden-no-popups]]

### ⚠️ A "missing" worker on a NEARLY-DONE fleet is FINISHED, not dead — read the log BEFORE resetting (2026-07-26)
A fleet-status check found low live-worker counts (W3 QA 8/12, CP2077 QA 4/9) and I reset the "degraded"
machines — WRONG on two counts. (1) **CP2077 QA was 98.3% done, so most provider-slices had legitimately
drained**: each worker prints `ALL DONE — N reviewed` and EXITS when its `md5%3` slice is complete, so
`vm4=1, vm5=1, laptop=2` was CORRECT (the rest were done, not crashed) — the worker logs said so plainly
(`ALL DONE` vs `remaining 254 | done 10950`). (2) The reset **killed vm's two WORKING providers** (groq+nim,
merely 429-throttled) whose slices still had work, and the relaunch did not persist. **THE ONLY genuine
failure was the W3 desktop slice-3 (0 workers, out files frozen ~20 h) — a real dead slice, revived to 3/3
and producing again.** Two universal rules, both already latent in the classes below: **(a) before resetting
a "degraded" stream, read its worker log — `ALL DONE` = finished (leave it), a stale/short tail or a
traceback = dead (fix it); a low count on a nearly-complete fleet is expected.** **(b) A worker relaunched
by an ssh command does NOT persist (it dies with the session) — only the `run3.bat` run BY the machine's
SYSTEM scheduled task survives in session 0, so relaunch a VM's workers with `schtasks /run /tn W3qaMP`
(or `CpqaMP`), NEVER `ssh … cmd /c run3.bat`. A LOCAL `Start-Process` (this desktop) does persist.** The
`.lock`+kill reset is for a genuinely stuck singleton (PID-reuse) — do NOT apply it to a fleet that is
simply winding down.

### 🔴🔴 SILENT-FAILURE CLASS #3 — a HUNG GUEST reads as a healthy VM (20 h of W3 QA lost, 2026-07-21)

Half the Witcher-3 QA fleet (slice 0 = the local VM `Win11 - 1`, 3 provider-streams) was **dead
for 20 hours** and nothing reported it: VirtualBox said `VMState=running` the whole time, the
host-side `FleetVMWatchdog` ran every 3 min at `rc=0`, and the dashboard kept showing
`streams=6` — because **`count_streams()` counts BANK FILES, not live processes** (a count of
past work, not current capacity). The only honest signal was a bank mtime frozen at 03:00.
**A hypervisor "running" state is NOT a liveness check — probe the GUEST** (an ssh `echo PONG`),
and require N consecutive failures before acting so a booting/busy VM is never killed.
`~\fleet_vm_watchdog.ps1` now does both: not-running → `startvm`; running-but-unreachable ×3
ticks (~9 min) → `poweroff` + `startvm` (ACPI is useless on a hung guest — it is the guest that
must honour it). Verified end-to-end with a stubbed copy: WARN 1/2 → HANG → power-cycle, with
the healthy VMs untouched. Recovery in the field took **54 s** to ssh + the VM's own boot task
brought all 3 workers back automatically.

**Three PowerShell traps that each made a watchdog silently blind — all found in ONE script:**
1. **`$array -notmatch $x` is a FILTER, not a boolean.** `VBoxManage list runningvms` returns an
   array of lines, so `if ($running -notmatch $vm)` is TRUE whenever ANY OTHER line doesn't match
   — i.e. always, once ≥2 VMs run. The old watchdog therefore called `startvm` on all three VMs
   every 3 minutes forever (64 KB of bogus "RECOVER started" log) while detecting nothing. Join to
   a single string before testing: `($running | Out-String) -match [regex]::Escape('"' + $name + '"')`.
2. **Variable names are CASE-INSENSITIVE** — `$STATE` (a path) and `$state` (a hashtable) are the
   SAME variable, so `Set-Content $STATE` got a hashtable and the write died inside `catch {}`.
   Already documented for `ac2_watchdog.ps1` and reproduced verbatim here — **keep path names
   lexically distinct from data names** (`$StatePath`).
3. **`[double]::Parse((Get-Date -UFormat %s))` throws under Windows PowerShell 5.1 + he-IL**
   (5.1 emits a fractional epoch; he-IL expects `,`). With `$ErrorActionPreference='SilentlyContinue'`
   that left `$now = $null`, so the boot-grace test `$null - 0 = 0 -lt 240` was TRUE and **every
   probe was skipped in total silence**. Use `[DateTimeOffset]::UtcNow.ToUnixTimeSeconds()`.
   ⚠️ **This bug is invisible in pwsh 7** — a scheduled task launched via `.vbs` runs
   `powershell.exe` **5.1**, so always test with the runtime the task actually uses.

**UNIVERSAL: instrument before theorising.** Three rounds of reasoning failed to explain "no log,
no state file"; a 3-line `Write-Host` trace through the loop found it in one run.

### 🔴🔴 SILENT-FAILURE CLASS #4 — a STRIKE that cannot tell "no reply" from "rejected" (2026-07-22)

AC2 showed **0.0 sentences/min** at 97%. Not a stall: 5 of 6 slices had legitimately drained and
the last one was pinned to **SambaNova, which was returning HTTP 429**, so a single-line batch took
minutes. But digging into *why* only 16 lines were left exposed a far worse bug in the strike/park
mechanism itself — **107 lines had been parked as "untranslatable" and 55 of them are trivial
dialogue** (`Ha, awesome.` · `Um... Nobody.` · `Ah! There you are. Is it done?`).

**Root cause:** `do_batch` returned a bare `{}` for BOTH "the model answered and the guard refused"
and "the provider never answered (429/timeout)". The caller struck every line in the batch either
way, so **3 rate-limited batches in a row permanently discarded perfectly good content.** The park
mechanism — added precisely to stop an infinite re-serve loop — turned a transient infrastructure
failure into silent data loss.
**Fix:** `do_batch` returns `(res, answered, seen)`; only a key the model actually **produced a
candidate for** (`seen`) can earn a strike. There are THREE outcomes, not two, and the first two are
both blameless:
| outcome | meaning | strike? |
|---|---|---|
| transport failed (429/timeout) | nobody replied | **no** — retry next pass |
| replied but the key is MISSING from its JSON | model dropout | **no** — re-ask that key alone |
| replied WITH a value the guard refused | real content failure | yes |
Conflating the middle row with the last one is what parked **82 lines of ordinary dialogue**
(`Access Lorenzo's secret hideout.`, `Ah, Ezio! I was hoping you might return.`) — the model simply
omitted them from its JSON three times. The recovery now re-asks every omitted key on its own
(highest hit-rate) *before* any strike, which also subsumes the old "whole batch empty" special case.
**UNIVERSAL: a retry/strike/park counter must be driven by a RESPONSE ABOUT THAT ITEM. An empty
result, and an item missing from a non-empty result, are both "unreachable", not "wrong".**

### 🔴 NOT every `[bracket]` is an engine token — a gloss is TEXT THE PLAYER READS

The same AC2 guard compared **every** `[...]` verbatim. But AC2's script overloads that syntax:
- **ENGINE TOKEN** — `[X] [Y] [LS] [RT] [Start] [Back] [LAUGH]`: controller/nav buttons and audio
  cues. Must survive verbatim or the in-game prompt breaks.
- **TRANSLATOR PROSE** — `[sigh] [realizing] [sound of pain] [Whores!] [Home sweet home.]
  [A hand drawn map of Cyprus.]`: stage directions and the English gloss of an Italian line. These
  are **displayed**, so a faithful Hebrew translation MUST change them — and the guard rejected
  every one, striking out 38 real dialogue/codex lines.
Measured over the corpus the split is clean and mechanical: **685 token occurrences (64 distinct,
all buttons/cues) vs 111 prose occurrences (94 distinct, zero buttons)** — a bracket is a TOKEN
only when its content is a single Capitalised/CamelCase word or an ALL-CAPS cue. Shipped as
`_BR_TOKEN` + a `_prose_brackets()` COUNT check (so a gloss must be translated, never *dropped*).
**Verified before deploying: 11/11 guard self-tests, and 0 of the 9,809 already-banked lines
regress.** Net effect: **124 of 178 parked lines unparked**, 54 kept as genuinely token-only.
**UNIVERSAL: before treating a bracket/brace/tag as an untouchable token, count how the corpus
actually uses it — an overloaded syntax makes a structural guard silently delete content.**

### 🔴🔴 SILENT-FAILURE CLASS #5 — a DETERMINISTIC defect must be FIXED, not rejected (2026-07-22)

AC2 sat at **0.0 sentences/min for an hour** with 87 lines left, and the guard's own log said why:
**46 of 59 rejections (78%) were `niqqud`** — the model returning perfectly good Ezio dialogue
*with vowel points*. Three strikes then **parked 78 ordinary lines** (`Access Lorenzo's secret
hideout.`, `Ah, Ezio! I was hoping you might return.`). The guard was right that the text was
wrong and **wrong about whose problem it was**: stripping niqqud is a pure string operation with
exactly one correct answer — it is not a translation decision. Fix = a `normalize()` applied to
the model's output BEFORE validation (`NIQ.sub("", s).strip()`), with the niqqud check kept only
as an unreachable safety net. Recovery was immediate: 9,779 → 9,792 banked, 87 → 74 remaining.
**UNIVERSAL: split every guard rule into DETERMINISTICALLY-REPAIRABLE (niqqud, stray whitespace,
zero-width marks, a dropped leading control byte) vs GENUINE CONTENT FAILURE (token multiset,
dropped gloss, copy-EN). Repair the first class silently; only the second may earn a strike. A
rule that rejects what it could have fixed is data loss wearing a validation badge.**
This is the third instance of the same root shape (429 → strike, model-dropout → strike,
now repairable-defect → strike) — when a line will not translate, **ask what the guard did with
the answer**, not whether the model tried.

### 🔴🔴 PID REUSE MAKES A SINGLETON LOCK PERMANENT — match the COMMAND LINE (2026-07-22)

The same investigation found vm3 running only **2 of its 3** provider-streams. `w_nim.log` was a
tidy, reassuring loop of *"another worker is already running (pid 3672) — exiting."* — and pid
3672 was **`svchost`**. Windows had recycled the dead worker's pid, so `_alive(pid)` (a bare
`tasklist /FI "PID eq N"`) answered TRUE forever and that slice could never restart. A third of
the machine's capacity was gone with no error anywhere, and the 5-minute relaunch task dutifully
re-created the message every tick. Fix: resolve the pid's **CommandLine** and require it to
contain the worker's own script name. **UNIVERSAL: a pid is not an identity. Any lock/liveness
check keyed on a bare pid must also match the command line (or the process start time), or a
recycled pid turns a transient lock into a permanent outage — and the log will read as healthy.**
Same family as [[hung-guest-reads-as-healthy-vm]]: the check answered a question adjacent to the
one that mattered.

### 🔴🔴 SILENT-FAILURE CLASS #6 — the HANG RECOVERY corrupts the file it was protecting (2026-07-22)

The VM watchdog from class #3 works — it power-cycled a hung `Win11-VM-2` twice in 15 minutes.
But `poweroff` is a **hard** stop, and NTFS can leave an in-flight write **allocated at full size
and filled with NULs**: `out_nim.json` on `Win11 - 1` was 549,444 bytes of `\0`. Two failures
followed, neither of which announced itself:
1. **The worker crash-looped.** `json.load(open(OUT))` at startup threw `JSONDecodeError` before
   anything was logged, so the stream was down for hours behind a log that ended mid-traceback.
2. **The pull PROPAGATED the corruption.** `scp` copied the NUL file straight over
   `banks/qa_out_0_nim.json`, destroying ~2.5k already-reviewed lines, and reported success.
**Fixes (both belong in every game's fleet):** the worker's `_load_out()` moves an unreadable
bank to `out_*.json.corrupt-<ts>` and starts from `{}` (the review is monotonic, so the slice is
merely re-done); the pull scp's to a **temp file, parses it, and only then replaces the bank** —
a bank is never overwritten by anything that is not valid JSON.
**UNIVERSAL: a recovery action that force-kills a process or a machine WILL eventually truncate
whatever it was writing. Every consumer of that file needs (a) a corrupt-input path that
degrades instead of crashing, and (b) a validate-before-replace step at every copy hop —
otherwise the automation that repairs the outage is also the thing that spreads the damage.**
Signature to recognise instantly: a file whose SIZE looks right but whose first bytes are all
`\0`, and a `JSONDecodeError: Expecting value: line 1 column 1 (char 0)`.

### 🔴🔴 SILENT-FAILURE CLASS #7 — a FIXED hash partition strands the work on the slowest provider, and re-cut slices silently DUPLICATE it (2026-07-26)

The user asked "can the lines be spread so everyone keeps translating equally?" — measuring it
exposed two structural leaks that had been running for days with every stream reporting healthy.

- **🔴 `md5(key) % 3 == provider_index` is a FIXED assignment, so a rate-limited provider becomes
  a bottleneck the fleet cannot route around.** groq 429s constantly; its third fell behind while
  sambanova/nim finished theirs and their workers EXITED with `ALL DONE`. Measured remainder by
  residue — **W3: groq 5,160 / sambanova 733 / nim 1,674** (68 % of the work on the slowest
  stream), **CP2077: nim's third 100 % done, groq+sambanova holding all 1,414 left → 6 of 9
  streams idle.** Nothing in the logs says "idle": a finished worker prints `ALL DONE` and exits,
  which is indistinguishable from healthy completion ([[fleet-guard-park-and-productivity-watchdog]]).
- **🔴 Re-cutting ONE machine's slice while the others keep their older, wider slices makes the
  same key live in two corpora.** Bank rows vs distinct keys: **W3 124,847 → 85,091 = 39,756
  duplicate reviews (32 %)**; **CP2077 277,424 → 201,288 = 76,136 (27 %)**. A third of the fleet's
  output was work already done by another machine — invisible in every per-stream metric.
- **✅ THE FIX = a per-provider corpus file that OVERRIDES the hash split.** `w3qa_nim.py` /
  `cpqa_nim.py` now prefer `corpus_<prov>.json` next to the worker (and skip the md5 filter when it
  exists; `corpus.json` + md5%3 remains the fallback). **`universal/fleet_reslice_equal.py`** unions
  every bank, takes the remainder **in corpus order** (the corpus is visibility-ordered, so no shard
  is "all the boring tail"), and round-robins it across the given streams → disjoint, equal, same
  visibility mix. Re-runnable: it recomputes from the banks, so a stream dying mid-shard loses
  nothing. Applied: W3 **12 × 628**, CP2077 **9 × 156-157** — verified from each worker's own log
  (`corpus=628 (per-provider file)`).
- **🔴🔴 THE ARITHMETIC TRAP: the number of MACHINE slices must NOT be a multiple of 3.** With
  `md5 % 12`, `md5 % 3` is fully determined by the shard index (`12q+s ⇒ s mod 3`), so 2 of every 3
  providers on a machine get **ZERO** keys. `--write 4` is correct for 4 machines; `--write 3`/`6`/
  `12` would silently idle two-thirds of the fleet. (For 3 machines, split into 9 and group 3
  consecutive shards per machine.)
- **🔴 The CP2077 `heal` was RESURRECTING the duplication.** It counted *any* `cpqa_nim` and fired
  only at 0, then spawned **`cpqa_nim.py` with NO provider argument** — the legacy round-robin form
  that reads the machine's WHOLE corpus unpartitioned and writes `out.json` (no suffix). So every
  time the 3 pinned workers finished, heal replaced them with one duplicating worker (found live on
  vm4 + vm5). Now: count only `cpqa_nim.py (groq|sambanova|nim)`, require **3**, and relaunch via
  the guest's SYSTEM task (`schtasks /run /tn CpqaMP` → `run3.bat`) — the only launcher proven to
  persist in session 0; the per-provider PID-lock makes it idempotent.
- **🔴 `pull_w3qa.sh` had NO worker heal at all** (only a pusher heal), so a dead provider-stream
  stayed dead and its share just waited. Added: per-VM `schtasks /run /tn W3qaMP` when <3 pinned,
  and for the desktop a LOCAL detached `run3.bat` (an ssh-launched worker dies with the session; a
  local `Start-Process` persists).
- **⚠️ Drained workers of FINISHED projects were still burning the same 28 provider keys** — PT
  (`pt_nim`) on vm2, W3 translation (`w3_nim`) on vm3 **and on the laptop since 07-10 (16 days)**,
  plus `W3RGWorker`. Killed + their boot tasks disabled. **Whenever a project reaches 100 %, kill
  its workers AND disable its `*Boot` tasks — otherwise it keeps competing for the live fleet's
  quota, and the only symptom is more 429s.** ('w3_nim' is not a substring of 'w3qa_nim', so a
  command-line match on it is safe.)
- **🔴 `ConnectTimeout=10` in `~\fleet_vm_watchdog.ps1` produced a FALSE hang.** A healthy guest
  running 3 LLM workers answered `PONG` after >10 s but <60 s ("Connection timed out during banner
  exchange" ×3 in a row) — and the recovery for a "hang" is a **hard poweroff**, which is exactly
  what NUL-truncates `out_*.json` (class #6). Raised to **45 s**: a genuinely hung guest never
  answers at all, so the generous timeout costs nothing. **Before power-cycling a "hung" VM, re-probe
  with a long timeout — slow ≠ hung, and the cure is destructive.**
- **⚠️ Fighting ssh quoting is a waste — send PowerShell as `-EncodedCommand`.** Write the script to
  a `.ps1`, base64 it as UTF-16LE, and run `powershell -NoProfile -EncodedCommand <b64>`: no
  quoting, no backslash mangling, works identically on every guest. A bare `Get-ChildItem C:\` over
  ssh silently loses its path argument and lists the HOME dir instead — a wrong answer, not an error.
- **⚠️ `python -m …_progress.py --status` is NOT a status flag** — the pusher ignores argv and
  starts a SECOND pusher, which is exactly the false-0/h trap below. Read the progress numbers from
  the pull log or compute the union yourself.

### 🎨 The dashboard is DESIGN-MATCHED to the launcher (2026-07-27, second pass)

The user asked for "exactly the launcher's design and behaviour — glass menus, animation, settings,
options, what's shown and what's hidden — but a SEPARATE program". So `ui.py` is a port of the
launcher's design system rather than a lookalike: every token is lifted from
`frontend/src/index.css` + `tailwind.config.js` (the table at the top of `ui.py` names each one) and
the **Heebo TTFs from `games/spiderman2/extracted/_heebo/` are bundled into the EXE**, so it is the
same typeface, not a substitute.
- **Ported**: `.glass` / `.sidebar-glass` fills, the 72↔230 rail at `width .46s cubic-bezier(.34,
  1.35,.5,1)` with hover-expand, the travelling indicator (accent pill + top sheen + a 4 px rounded
  glowing edge bar + outward bloom, `top/height .44s`, same curve), the view transition, `.stagger`
  at 40 ms/child, the SegmentedControl with a sliding glowing thumb, the click ripple, the
  accent-tinted static-radial ambient background, the frameless title bar whose glyph-only controls
  recolor on hover with no square box, brand yellow/cyan, and the per-nav accents.
- **Where Qt beats the CSS**: the launcher had to DROP `backdrop-filter` for performance
  (QtWebEngine CPU-composites it), so its "glass" is a solid translucent fill. This app asks
  **DWM for a real system backdrop** (`DWMWA_SYSTEMBACKDROP_TYPE` 38: acrylic/mica) plus rounded
  corners and a dark frame — genuine blur behind the window, selectable in Settings.
- **Six views** behind the rail (סקירה · זרמים · אזהרות · תרגומים · ביצועים · הגדרות), each with its
  own segmented filter, plus `--view <key>` to deep-link (which is also how each screen was
  screenshot-verified). Settings mirror the launcher's own: animation LEVEL (מלאה/רגילה/מופחתת/כבויה
  — a factor that multiplies every duration, 0 = off), backdrop, accent swatches, text size 75-125 %
  on a 5 % grid, sidebar mode, ripple, plus this tool's own show/hide (games · table columns ·
  overview panels · hide-INFO · hide-finished) and the three refresh cadences. Persisted in
  `%LOCALAPPDATA%\FleetDash\prefs.json` (with the window geometry).
- **🔴 THE QT LESSON THAT BROKE THE FIRST LAYOUT: never animate `pos`/`geometry` of a widget a layout
  manages.** The CSS `transform` in `.view-transition`/`.stagger` does not disturb layout, so porting
  it literally seemed right — but Qt's layout re-places the widget mid-animation, and the result was
  overlapping text and one of two cards vanishing entirely. The rise is now the layout's own TOP
  MARGIN relaxing 18px→0 (`QVariantAnimation` → `setContentsMargins`) and the fade is a
  `QGraphicsOpacityEffect`; both are layout-safe, and the stagger uses only the fade.
- **⚠️ A collapsed 72 px rail with text-only buttons renders BLANK** — the launcher has SVG icons in
  that slot, so each view carries a glyph (◈ ≡ ⚠ ✎ ⚡ ⚙) that is what the narrow rail shows.
- **⚠️ The rail's edge must be a painted INSET highlight, not a `border`** — exactly as the
  launcher's CSS comment warns, a border shows a 1 px white seam while the width animates.
- **🔑 The sample feed is seeded from the TAIL of each bank** (a worker appends keys as it banks and
  Python dicts keep insertion order ⇒ the last keys are the newest reviewed lines), so the pane is
  useful the moment the app opens instead of blank until the next merge — 20 minutes on W3.

### 🖥 "מצב הצי" — the personal fleet dashboard EXE (`tools/fleet_dashboard/`, 2026-07-27)

A single-file Qt EXE (`dist/FleetDash.exe`, 50 MB, no console, desktop shortcut "מצב הצי") that shows
every provider-stream live: per-stream shard progress, rate, out-file age, PID, state; per-game
percent/remaining/rate/ETA/merge-age/duplicates; a feed of the newest banked lines (English + Hebrew
before→after, or "אושר ללא שינוי"); per-provider throughput; and per-machine disk/task/VM. **Every
finding names its REASON and what to do** — the full rule set is in `health.py` and covers dead ·
stalled · throttled-and-stalled · duplicated process · **missing `corpus_<prov>.json`** (the stream
silently fell back to the old md5%3 split) · zero-output-in-window · unreachable machine (with a
consecutive-strike count) · **legacy no-arg worker** · drained zombies · low disk · disabled launch
task · VM down · corrupt (NUL) bank · frozen merge · missing/duplicate pusher. Full docs:
`tools/fleet_dashboard/README.md`. `python dash.py --once` prints the same collection as text.
- **Design rule it enforces: every pane shows the AGE of what it displays.** Local banks refresh
  every 15 s, the 6-machine ssh sweep every 90 s — without the age a 90-second-old probe reads as
  live. The per-stream "progress in shard" is the intersection of that stream's own shard file with
  its own bank, so it is that stream's work, not a global number.
- ⚠️ **The sample feed only moves when a MERGE runs** (the banks are what the pull produces): CP2077
  merges every 3 min, W3 every 20 — hence the per-game "מיזוג" button in the header.
- **🔴 A THROTTLE RULE THAT COUNTS LINES RAISES FALSE RED ALARMS (fixed 2026-07-27).** The worker
  prints ONE `HTTP Error 429` line per refused batch, so a stream that was just refused has a single
  429 in its tail — the rule required **two** and therefore classified it `תקוע` with the reason
  *"no evidence of 429 — kill it and relaunch"*, i.e. an ERROR advising a destructive action on the
  most common state in the fleet. `health._throttled()` now also accepts "the LAST line is a 429".
  **UNIVERSAL: a severity rule built on a repetition COUNT misfires on the first occurrence — make
  the most recent line sufficient on its own, and re-read your own advice text: if a warning tells
  you to kill something, it had better be right.**
- **✅ The tool proved itself on its first real run** — it flagged vm3's three W3 workers dead
  (verified: they really were, and `W3qaMP` revived them 90 s later), then vm as unreachable, which a
  90 s re-probe showed was merely **loaded** (`PONG`, 0 workers) — so the answer was
  `schtasks /run /tn W3qaMP`, not the power-cycle a naive watchdog would have done
  ([[hung-guest-reads-as-healthy-vm]]). It also caught **C: at 1.3 GB of 3,720** while an 82 GB
  qBittorrent download was writing to the system drive — the exact condition that freezes a merge and
  publishes zeros (it resolved on its own to 165 GB when the file moved).
- **Every stream carries a FIXED number (#1-#21)** — a persisted registry in
  `%LOCALAPPDATA%\FleetDash\stream_ids.json`, not a row index, so filtering/sorting never moves
  it and a number is never reused. It leads the table, every finding's scope and every sample,
  so the user can say "stream 7" instead of `witcher3 · vm3 · groq`.
- **A failed ssh probe does NOT mean a stopped stream — the BANK outranks it.** If a stream
  banked lines inside the rate window it is reported as working, with the probe failure as the
  note ("the machine is just loaded"). Same lesson as the hung-guest trap, applied to the UI.
- **🔴 A PROGRESS FIGURE MUST ROUND DOWN, AND 100% IS RESERVED FOR remaining == 0.**
  `f"{202611/202702*100:.1f}%"` prints **100.0%** — the panel announced Cyberpunk finished while
  **91 lines were still queued**, which is exactly the false "done" this tool exists to prevent.
  `dash.fmt_pct(done, total, remaining)` floors to one decimal and caps at 99.9 % until nothing is
  left. **UNIVERSAL: a percentage shown to a human is a CLAIM ABOUT STATE — never let rounding
  make it stronger than the data; the same applies to every "done"/"complete" badge and to the
  homepage progress dashboard.**
- **⚠️ Two capture/build traps, both re-hit here:** `CreateCompatibleBitmap` must take the **window**
  DC — from a fresh memory DC it returns a **1-bpp monochrome** bitmap and every screenshot is
  solid black; and a rebuild fails `PermissionError WinError 5` while a previous copy of the EXE is
  still running, so kill it before `pyinstaller`.
- **🔴🔴 THREE build traps, each of which silently produced WRONG data (all now fixed in code):**
  1. **PowerShell can corrupt its own JSON in two independent ways.** `Get-Content` returns
     *decorated* strings, so `ConvertTo-Json` serialises `PSPath/PSDrive/PSProvider/...` — the probe
     came back as **449 KB** of provider metadata instead of six log lines. And stdout in the console
     codepage **best-fit-maps** the em-dash in the workers' logs to a bare ASCII `"` — INSIDE a JSON
     string, so every probe returned unparseable JSON while ssh reported success. Fix:
     `[string]$_` + `-replace '[^\x20-\x7E]'` + `[Console]::OutputEncoding = UTF8`.
     **UNIVERSAL: never let a PowerShell-produced JSON carry raw file content; flatten to ASCII and
     force UTF-8, or a codepage silently invalidates the payload.**
  2. **`expanduser("~")` is not the real home here** ([[env-redirection-real-home]]) — the ssh key
     "did not exist", `-i` was dropped and every remote probe failed with nothing but ssh's banner.
     Resolve `FOLDERID_Profile`.
  3. **A window screenshot needs `PrintWindow`, not `ImageGrab`** — ImageGrab grabs a SCREEN RECT, so
     when `SetForegroundWindow` lost to focus-stealing prevention I photographed the IDE sitting at
     those coordinates and "verified" the wrong window. Also: a PyInstaller **onefile** EXE's window
     belongs to the CHILD process, so enumerating windows by the launched pid finds nothing.
- ⚠️ A tool's own diagnostics can lie: `python dash.py --once` first printed NOTHING and exited 1 —
  the classic cp1255 stdout (`sys.stdout.reconfigure("utf-8")` is now the first thing `main()` does).

### ⚠️ Two pushers = a false 0/h on the homepage
Two overlapping `pull_*.sh` runs once raced the "start the pusher if absent" check and left
**two** `cpqa_progress.py` alive. Both append to `*_progress_hist.json`, and the duplicated
samples make the rate window compute **0/h on a perfectly healthy fleet** — which reads exactly
like a stall and sent me hunting twice. The self-heal is now start-if-absent **AND
kill-the-extras** (sort by `CreationDate`, keep the first). Whenever a rate looks impossible,
count the pushers before suspecting the workers.

### ⚠️ Probe the RIGHT host before declaring an outage
`vm4`/`vm5` are VirtualBox guests **on the laptop** (`100.116.78.88:2225/2226`), NOT local. A test
against `127.0.0.1:2225` returns *connection refused*, and an empty `tasklist | wc -l` reads as
"0 workers" — which looked exactly like a 6-stream CP2077 outage that did not exist. Only
`vm/vm2/vm3` (2222/2223/2224) are local. Same rule as the Worker/GitHub false alarms: **never call
an outage off a single negative probe.**

### Standing gate + cadence

**🔒 ביקורת-בלבד monotonic — אל תאפה ואל תפרסם.** QA fixes accumulate in `cpqa_fixes.jsonl`
(~48k: phrasing/gender/error/slang/foreign) for a **manual audit BEFORE any bake**. Bake only
audited batches; publish ONLY on an explicit "פרסם".
Pull cadence: `CPQAFleetPull` 3 min · `AC2FleetPull` 3 min · `W3qaFleetPull` 20 min · pushers 60 s.
⚠️ Harness: chained `sleep` in Bash is blocked — use `run_in_background: true` or an
`until <check>; do sleep 2; done` loop.

---


