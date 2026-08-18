## Community translation system — crowdsourced EN→He lines (STAGE 3 LIVE 2026-06-18)

A platform feature so users don't translate every game alone: the team builds the
per-game **skeleton** (Arabic-slot RTL + font + repack + deploy — the existing
`games/<game>/FEASIBILITY.md`/`PIPELINE.md`), and the only remaining heavy work —
translating the lines — is **crowdsourced**. Logged-in users claim a batch, translate
EN→He, submit back; an **auto structural-QA gate** rejects bad ones; the admin (user)
reviews + approves; approved Hebrew exports back into the existing apply/bake/deploy
keyed by the exact spine key. Works for BOTH untranslated games (fresh) AND
already-translated games (`current_he` set → contributors propose IMPROVEMENTS).

**User decisions (2026-06-18):** input model = **both** (in-site editor primary +
file download/upload for power users); approval = **admin approves everything** for
the MVP (trust-levels later); scope = **all games**, including already-translated.

**Stage 1 — DB schema (DONE + LIVE + verified).**
`website/supabase/community_translation_migration.sql` (applied via
`python c:/tmp/run_ct_migration.py`, the SUPABASE_DB_URL psycopg2 method). Two tables +
2 views, RLS like `reviews`/`votes`:
- `translation_strings` — source-of-truth lines per game: `game_id`(FK), `string_key`
  (EXACT spine pk/stringId — export maps back on it), `source_en`, `current_he`
  (''=untranslated, non-empty=improve mode), `context`, `char_limit`, `section`,
  `order_index`, `status`(open/translated/approved), soft claim (`claimed_by`,
  `claim_expires_at`), `approved_text`. unique(game_id,string_key). **Public read**;
  writes service-role only.
- `translation_submissions` — `string_id`(FK), `game_id`, `user_id`, `hebrew_text`,
  `author_name`(denormalized like reviews), `status`(pending/approved/rejected/
  superseded), `reviewer_note`, `auto_qa`(jsonb), review fields. unique(string_id,
  user_id) — a user revises via upsert, others add their own. **Self-read only**;
  writes service-role only.
- Views: `translation_progress` (per-game counts) + `translation_contributors`
  (leaderboard, aggregate only — author_name not email). **Grant the views to
  service_role too** (RLS bypass ≠ view grant — first apply missed it → 403; fixed).
- Claims are a SOFT lock; expired claims are treated as free LAZILY by the API (no cron).

**Stage 2 — pipeline bridge (DONE + round-trip verified).**
`universal/community_translate.py` (urllib only, reads `website/.env` service key) —
game-agnostic. Contract = a NORMALIZED strings file (JSON array of
`{string_key, source_en, current_he?, context?, section?, char_limit?, order_index?}`);
each game makes it with a tiny adapter over its existing extractor. Commands:
`import <game_id> <strings.json>` (bulk upsert on game_id+string_key, chunks of 500,
merge-duplicates so a re-extract refreshes the pool without losing claims/approvals),
`export <game_id> [--out]` (approved rows → `{string_key: approved_text}` JSON for the
apply script), `stats <game_id>`. Verified: import 2 → stats (total/had_existing/
untranslated_open correct) → export → cleanup, all good.

**Stage 3 — web layer (LIVE 2026-06-18).** Deployed `vercel --prod` (dpl_FV2oBxbb…).
- `website/api/translate.ts` — full endpoint: GET list/stats/download/admin-queue/my-submissions, POST submit+upload (auto-QA gate inline), PATCH approve/reject/edit. Rate-limited (60 submissions/min/user). Service-role bypasses RLS; admin actions via `requireAdmin`.
- `website/src/pages/TranslatePage.tsx` — public `/translate` route (login-gated), game selector, batch-size 10/25/50, row-by-row table (EN | HE textarea | actions, RTL via `dir="rtl"`), status colors, inline QA errors, file download (fetch+blob) + upload (CSV/JSON parser).
- `website/src/components/admin/TranslationsTab.tsx` — admin review queue under "תרגומים" tab in AdminLayout "אתר" group: game+status filter, per-card approve/edit/reject with inline edit+note.
- `website/src/pages/ProfilePage.tsx` — "התרגומים שלי" tab added (🌐 icon): loads `/api/translate?action=my-submissions`, shows status-colored rows (pending/approved/rejected).
- `website/src/components/Navbar.tsx` — "תרגמו איתנו" link added after "משחקים".
- `website/src/App.tsx` — lazy `/translate` route behind ProtectedRoute.
- `api/software.ts` DELETED (dormant, was the 12th→13th function on Hobby plan); ProgressTab made resilient to 404.
- **Auto-QA gate** (server-side, shares Playbook §7 name/code rule): niqqud, foreign script, placeholder multisets [UPPER]/{VALUE}, not-identical-to-source, must-have-Hebrew (unless name/code).
- **Next**: per-game adapter to import strings (`universal/community_translate.py import <game> <strings.json>`), then contributors can start. Start with WD2 or GoWR EN source.
- 4 news suggestions pushed to admin queue (`universal/claude_suggest.py`).

The auto-QA gate MUST reuse the translator's name/code passthrough rule (Playbook §7) —
accept no-Hebrew when the source is a name/code — or it churns on proper nouns.

### Stage 3 UX polish (2026-06-18) — covers, background, hidden reference, token-free editing

Four fixes to `TranslatePage.tsx` after the user reviewed the live page (all
deployed `vercel --prod`, aliased to hebrew-translation-hub.com):
- **Game-card covers were empty boxes.** `/api/games` shapes the cover field as
  **`cover`** (see `api/games.ts` `shape()` → `cover: row.cover_url`), but the
  page read `g.coverUrl || g.cover_url` (neither exists). Fixed → `resolveCoverUrl(g.cover, g.id)`
  (the canonical `src/lib/coverUrl.ts` helper: absolute / public / bucket / `<id>.jpg`
  fallback). The 4 games hold full `…/covers/<id>.webp` URLs.
- **Site starfield/video background was blocked** by a `bg-zinc-950/80` blanket on
  the content wrapper → removed it (cards keep their own translucent bg, so the
  background shows through the gaps). Hero is `bg-black/60 backdrop-blur-sm`.
- **`current_he` hidden from contributors** (admin-only reference): stripped from
  the `/api/translate` GET list response (`safeStrings` omit) AND not rendered in
  `StringCard`. Still in the DB + admin-queue join + download endpoint.
- **Contributors translate token-FREE.** Measured the real string pool (4,000
  sampled): **~84% clean** (no tokens), ~7% boundary-only, ~9% inline
  (cyberpunk 99.9% clean; SM2 the outlier at 59.5% clean / 19.5% inline `%d`).
  So `TranslatePage` now decomposes each `source_en` via `analyzeSource()` into
  **prefix / core / suffix + inlineTokens** (PRESERVE_RE = tags, `&ent;`,
  `[[cue]]`, `[TOKEN]`/`[LF]`/`[style]`, `{val}`, `%d`-specs, `\n\t`):
  - **Boundary tokens** (start/end + adjacent ws) are PEELED off — the editor
    shows only the clean `core`; on submit `reconstructFull` re-attaches
    `prefix+editable+suffix` (the FULL structured string is what's stored/exported
    keyed by `string_key`). A saved submission is peeled back via `stripToEditable`
    on reload. Round-trip + `prefix+core+suffix===src` verified 0-fail over all 4,000.
  - **Inline tokens** can't be auto-placed (Hebrew reorders) → shown as amber
    chips in the source + a **one-click "+ %d" palette** under the textarea that
    inserts the exact token at the caret (contributor never types the code); a
    multiset `missingInline` check colors un-placed chips amber.
  - The standalone explanatory legend banner was removed (noise for the 84% clean).
  This mirrors Playbook §3/§7 token rules on the contributor side — the server
  auto-QA still validates placeholder multisets, so a missing inline token is
  rejected regardless.

### Stage 3 — clean fragments + repair guard-dogs (2026-06-18)

User feedback: a row showed a stray leading `". Be"`, and the request was to
NEVER tell a contributor "what you wrote is an error" — instead repair it.

- **Clean-fragment display.** Game dialogue is split into fragments, so a
  `source_en` can start with `". "` / `"... "` / a space after a `<ts>` timing
  tag. `analyzeSource()` now also peels leading/trailing **whitespace** and a
  leading **fragment marker** (`/^(?:[.,;…]+\s+|[.…]{2,})/`) into prefix/suffix
  (re-attached on submit). Dropped "dirty cores" 63→11 over 4,000 (the rest are
  `!OBSOLETE` dev-codes + `'Scuse`-style word-attached apostrophes, correctly
  left). `prefix+core+suffix===src` and the strip/reconstruct round-trip stay
  0-fail.
- **TWO repair guard-dogs replace hard rejection** (the user's "כלבי שמירה"):
  - **Guard dog #1 — server, deterministic (`api/translate.ts`).** Submit/upload
    no longer 422-reject on QA failure. `cleanHe()` strips niqqud + zero-width
    (NOT trimmed — boundary prefix/suffix must survive); the row is ACCEPTED as
    `pending` with `auto_qa = {ok, flags, needs_repair, niqqud_fixed, repaired}`.
    The ONLY hard stop is a truly-empty cell. Submit returns `needsRepair` →
    the UI shows a sky-blue "נשלח! נסדר את הניסוח והמבנה אוטומטית" note (not a red
    error). Upload reports `accepted`/`flagged`/`skipped` (no `rejected`).
  - **Guard dog #2 — local LM watchdog (`universal/community_qa_watchdog.py`,
    NEW).** Pulls `status=pending & auto_qa->>needs_repair=true` submissions
    (joins `translation_strings(source_en)`), rewrites each via LM Studio
    (gemma-4, env `CT_QA_MODEL`/`CT_QA_LM_URL`) into a valid structured Hebrew
    line, **deterministically re-validates** (`validate()` MIRRORS the server
    autoQa — niqqud/foreign/placeholder-multiset/has-Hebrew-or-name, unit-tested
    9/9), then PATCHes `hebrew_text` + `auto_qa{repaired:true,needs_repair:false}`
    back as `pending` for admin approval. Strike/park at 3 fails
    (`repair_strikes` → `unrepairable`). Trio discipline: UTF-8 stdout, singleton
    lock, crash-proof loop, `--once`/`--status`/`--game`/`--limit`. **It is LOW
    priority on the SHARED LM** — if the model is unresponsive it WAITS (does NOT
    reload, which would disrupt a running SM2/WD2 translator) unless `--manage-lm`.
  - `auto_qa` jsonb shape extended (no migration — jsonb). Admin still approves
    everything; the guard-dogs just make sure what reaches the admin is clean.
  Run it (when contributions exist + LM loaded): `python
  universal/community_qa_watchdog.py` (loop) or `--once`. `--status` = flagged count.

### Stage 3 — collaborative + versioned (public attribution + history) (2026-06-18)

The contributor flow became a transparent wiki-style model (user decision via
AskUserQuestion: **edits are admin-gated**, NOT auto-publish). All `vercel --prod`.

- **Translations are PUBLIC + attributed (reverses the 2026-06-18 "hide current_he").**
  The GET list now returns, per string: `currentText` (`approved_text` > `current_he`
  seed > ''), `currentAuthor` ({name, avatar} of the approved submission's author —
  **never email**), `hasHistory`, `status`. `current_he` is no longer stripped.
- **`StringCard` has VIEW / EDIT / HISTORY states.** A string with a live translation
  opens read-only (current text + `Avatar`+name + "✏ שנה" + "🕘 היסטוריה"); "שנה"
  pre-fills the editor via `stripToEditable(currentText)` → submit = a pending
  PROPOSAL (admin approves → new current, old → history). Untranslated rows open
  straight into the editor. Button flips to "↑ שלח הצעת שינוי" when a current exists.
- **Public per-string history** — `GET /api/translate?action=history&string=<id>` →
  `{sourceEn, seedHe, versions[]}`; each version = {hebrewText, status, author
  {name,avatar}, createdAt, reviewedBy, note}. Lazy on expand; shows the team seed
  (`seedHe`) as the "before" baseline. Uses `fetchAuthors()` (service-role read of
  `profiles` for name+avatar, bypassing self-read RLS; email only derives a fallback
  handle, never returned).
- **Show-everything filter** — list no longer excludes approved. New `filter` param:
  `all` (default) / `open` (`current_he=''` AND not approved = genuinely untranslated)
  / `translated` (`or(current_he.neq.,status.eq.approved)` = has a seed OR approved).
  3-way toggle (`הכל/לתרגום/מתורגמות`) reloads on click. NOTE: seeded strings keep
  `status='open'` (approval is a community state), so "translated" keys off `current_he`
  non-empty, NOT `status=approved`. (cyberpunk: 44,482 translated / 148 open.)
- **Privacy (stated to user):** name + avatar are public; **email is NOT** exposed
  publicly — admin-only via the admin-queue. Avatars from `profiles.avatar_url`
  (Google `picture`); `Avatar` falls back to an initial bubble.
- No DB migration (the `translation_submissions` chain — approved→superseded as new
  ones land — IS the history; `profiles` already has `avatar_url`). Admin approve/
  edit/reject (PATCH) unchanged — the gate that promotes a proposal to current.

### WD2 community pool — corrupt source_en re-aligned to game truth (2026-06-18)

A contributor flagged a `/translate` WD2 card showing "Take" → "זום". Root cause was
NOT the translation: `games/watchdogs2/work/build_ct_strings.py` joined `source_en`
from `extract/ui_strings_english.txt` (a **misaligned/garbled** English extraction)
while `current_he` came from the checkpoint `C:/tmp/wd2_ui_he.json` (keyed by the
game's real oasis ids). The two English id-mappings disagreed — **21,601 of 29,521
WD2 rows (73%) had wrong/scrambled `source_en`** (e.g. id 4567 = "Take" in the bad
file but "ZOOM" in the game; weapon descriptions were word-salad). The game's own
`main_english.loc` (decode: `tools/loctool/loctool.exe <loc>` → `.loc.txt`) is the
authoritative English and agreed with the Hebrew per id.
- **Fix:** bulk-upserted (`on_conflict=game_id,string_key`, merge-duplicates → only
  `source_en` written, `current_he`/status untouched) every WD2 row's `source_en` to
  `main_english.loc[id]`. Verified **0 mismatches** across all 29,521 rows; the flagged
  card now reads "ZOOM" = זום, the real "Take" ids (293453/316477) = "קח". No website
  deploy needed (reads the DB live).
- Also **rewrote `extract/ui_strings_english.txt` clean** from `main_english.loc` so a
  future `build_ct_strings.py` + re-import reproduces correct data.
- **LESSON (memory [[community-translation-model]]):** when seeding a community pool,
  `source_en` and `current_he` MUST come from the SAME id-mapping (the game's
  authoritative loc), never two independent extractions — or every row is silently
  mis-paired. Extract char note: decode in Node (`Buffer.toString`) or Python with the
  RIGHT encoding; a wrong `errors="replace"` turned `–`/`•` into `�` on 2 rows (fixed).


