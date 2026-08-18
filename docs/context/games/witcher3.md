## Witcher 3 — final untranslated set on vm5 with the "New Era" worker (2026-07-12)

The last **1,596 still-showing-Arabic lines** (NOT 1,741/1,857 — those counted Latin passthroughs like
VSync/URLs that show LATIN, not Arabic) are now translating on the FREE **vm5** stream
(`vboxuser@10.0.0.49:2226`, own dir `C:\w3ut`) via the New-Era worker. **🔑 THE discovery:** 1,439/1,596
have **XOR-CORRUPT English** in `extract/en.json` (mojibake CJK/PUA) while `ar/ru/pl/es/it` are 100%
clean — W3 `.w3strings` are XOR-encrypted per-language except **keyID 0 = Arabic = cleartext**, and the EN
extraction used a wrong key for these → garbage. That is exactly why they never translated (fleet fed
corrupt English). **Fix = translate FROM the clean Arabic** (New-Era primary) with ru/es/it cross-check.
- `games/witcher3/fleet/w3ut_nim.py`: `clean_en()`→'' for garbage; `src_text()` = clean EN else bidi-
  stripped Arabic; prompt = {en,ar,ru,es,it,g} "prefer en if readable, else Arabic primary, never copy
  foreign"; `valid()` checks STRUCT tokens vs the effective source + requires Hebrew for an Arabic source;
  `consensus_target()` gender guard (ar-strict → ≥2 of ru/pl/es/it; plural ONLY from Arabic أنتم).
  **Live-verified**: gender perfect (`1063168` f→"את לא מוכנה... שולטת בכוחותיך" from لستِ; `1077836` m).
  vm5 real output QA: 33 banked, **0 gender-mismatch / 0 foreign / 0 niqqud**.
- **Deploy:** `fleet/w3ut_deploy.sh` (scp worker+corpus+selfheal, copy `C:\w3w\key.txt`, W3utWorker(5min)+
  W3utWorkerBoot(onstart) SYSTEM auto-resume, launch). Pull **W3utFleetPull** (3 min, hidden via
  `hidden.vbs pull_w3ut.bat`) = `fleet/pull_w3ut.sh`: folds vm5 out.json → `fleet/hebrew.json` + records
  each folded id into **`fleet/w3_newera_passed.json`** ("עבר עידן חדש" marker → the later multi-lang
  REVIEW pass `w3qa_nim` must EXCLUDE these ids so they're never re-reviewed). vm5 also has an IDLE
  `pt_nim` (PT 100%, 75h stale) + `w3_nim` reglue (2h stale) on the same key — drained, harmless. NOT
  built into the .w3strings mod, NOT published (only on explicit "פרסם"). [[w3-untranslated-newera]]


## Witcher 3 — PUBLISHED v1.0.0-beta.1 (website) + the pre-launch audit that overturned "100%" (2026-07-18/20)

The user was launching "within hours" on a mod reported 100% translated. A real readiness audit
said **not ready as a stable release** — shipped as a declared BETA after a deterministic fix pass.
Everything below generalizes to every future game. [[pre-launch-glossary-audit]]

- **🔴🔴 "100% translated" is a COVERAGE number, not a QUALITY verdict — audit the CORE UI TERMS
  before any launch.** Every line had Hebrew, and the most-seen screens were still wrong:
  `Potions→תחליבים` (emulsions), `Oils→שומנים` (body fat), `Stamina→אינסטנט`, `Vitality→חיוות`,
  `Mutagens→מטוגנים` (fried), `Meditation→השתקעות`, `Toxicity→טוקסיציות`, `Trophy→טרופי`. A
  translator that never sees the game happily renders an inventory tab as a cooking term. **The
  4-step audit: (1) grep the ~20 core nouns the player reads every session, (2) count how many
  Hebrew renderings each English label has, (3) scan for stray bidi controls, (4) check the spelling
  of the game's own proper nouns.** All four are deterministic and take minutes.
- **Measured, not guessed:** 3,739 strings mention "witcher" and only **725 (19%)** used the
  intended מכשף — the rest were 53 different transliterations. **1,758 English labels had 2-9
  different Hebrew renderings across 6,366 strings.** New-Era review coverage was **1,554/94,167
  (1.7%)**. Those three numbers are what turned "ready" into "beta".
- **✅ The fix that IS safe for Claude to do: ENGLISH-GUARDED deterministic replacement**
  (`work/fix_glossary_a.py`) — a wrong Hebrew word is swapped **only where the EN source really uses
  that term** (`if bad in he and guard in en.lower()`). Without the guard, `מטען→ציוד` would rewrite
  an electric *charge* as *equipment*. 1,038 strings fixed (glossary 159 · bidi-strip 138 · witcher
  spelling 799), zero dialogue semantics touched. This does NOT violate
  [[delegate-all-translation]] — it is morphology/terminology, not translation.
- **🔴 THE HEBREW-PREFIX TRAP (universal for any Hebrew normalization): `ו` is BOTH a prefix
  ("and") AND a stem letter.** A naive prefix regex re-prefixed already-correct tokens →
  `ווויטצ'ר` / `וווויטצ'ר` (3-4 vavs). **Fix: build an explicit reviewable token→token map**
  (`canon_token`) instead of an in-place regex — strip a known suffix, match the stem, parse only
  UNAMBIGUOUS prefix letters (`הלבמכש`, never bare `ו`), skip anything starting `וו`. And note the
  orthography rule the map encodes: a word-initial vav DOUBLES after a prefix
  (`ויטצ'ר` → `הוויטצ'ר`). The map immediately exposed 2 false positives a regex would have shipped
  silently (`הבומבוטצ'ר` = the EN insult "bumbotcher", and `מייטשרים`).
- **🔴🔴 THE PACKAGING TRAP THAT ALMOST SHIPPED STALE TEXT: the packer packs STAGING, not the
  game.** `pack_release.py` zips `release/data/`, but the fix pass wrote into the GAME folder — so
  the "fixed" zip still contained תחליבים ×15 / השתקעות ×11 / אינסטנט ×2. Caught only by **decoding
  the PACKAGED file** and re-grepping. Fix: `work/sync_release_data.py` (game → staging, flat name
  `content__content0__ar.w3strings` ⇄ `content/content0/ar.w3strings`) runs before every pack.
  **UNIVERSAL: verify the ARTIFACT, never the source tree — "I fixed it" and "the zip contains the
  fix" are different claims, and only the second one ships.**
- **⚠️ Decode gotcha:** the `.w3strings` decoder returns a dict with `entries`/`block2`/`count1..3`;
  iterating `d.values()` finds 0 strings. Use `d['entries']` → `e['text']`.
- **⚠️ A transient `PermissionError WinError 5` on the temp pack dir is AV/indexer, not a bug** —
  `rm -rf` the temp dir, sleep, retry.

### Publish state + the one command that enables the launcher
Published `publish_version.py witcher3 1.0.0-beta.1 --stage beta --sha 38d7db64…
--size 3842202 --archive-url …/v1.0.0-beta.1/witcher3_hebrew.zip --apply` + a `games` PATCH.
- **⚠️ LIVE STATE (checked 2026-07-21) is PAID + launcher-live — the user changed it AFTER my
  publish:** `price_cents=5300` (₪53, now follows [[mod-price-53-default]] — NOT the free exception
  I first set), `show_on_launcher=true`, `availability=available`, and the user **deployed the
  Worker** (`wrangler deploy`) so `/witcher3-hebrew/manifest` = **HTTP 200**. So W3 is a real paid
  launcher product and a paying reviewer (Maor, ₪53) installed via the launcher AND hit the reversed
  bug. **Both surfaces point at the SAME release asset** (`v1.0.0-beta.1/witcher3_hebrew.zip`): the
  website `download_url` and the Worker `archive`. So one `gh release upload v1.0.0-beta.1 --clobber`
  of the LOGICAL zip fixes both — **but you MUST also clobber `manifest.json` with the NEW sha** and
  update `mod_version_history.sha256`, or the launcher's SHA-256 verify fails on the re-downloaded
  zip ([[launcher-release-checklist]] hash trap). Verify after: Worker manifest returns the new sha.
- **⚠️ A freshly-PATCHed field can read back EMPTY — that is the EDGE CACHE, not a failed write.**
  The history endpoint showed `changelog: 0 chars` right after a successful 661-char PATCH.
  Diagnose by querying the DB directly, then re-fetch with `Cache-Control: no-cache` + a
  cache-buster before declaring a publish broken.
- **Re-release rule:** clobber the assets of the SAME tag `v1.0.0-beta.1` (a Full Release, so
  `releases/latest` resolves) — never mint a new beta tag.

### 🔴🔴 FIELD REPORT: "Hebrew fully reversed on the user's machine, correct on mine" — engine bidi is VERSION-DEPENDENT (2026-07-21)
A reviewer (Maor) installed beta.1 (manual download) and reported **the Hebrew renders completely
reversed**, while the SAME mod files render perfectly on the dev machine. Same files → same-order
bytes → the ONLY variable is the **engine's bidi behavior**, and that is **game-version-dependent**.
- **The mechanism** (verified model): W3 stores Hebrew **VISUAL** (pre-reversed) because the tested
  engine bidi's **only Arabic SCRIPT**, not Hebrew — it leaves U+05xx in memory order, so a
  pre-reversed string looks right. An engine that ALSO treats Hebrew script as RTL reverses our
  VISUAL string a second time → back to logical → reads reversed. There is **no single stored order
  correct on both** (RLO/U+202E was already proven to mirror on the VISUAL engine), so the two
  versions are a genuine fork: non-bidi-Hebrew engine → VISUAL; bidi-Hebrew engine → LOGICAL.
- **🔴 THE STALE-TEST-RIG TRAP (the real lesson):** the dev exe is dated **2022-12-13 = patch 4.00**,
  the FIRST Next-Gen build (Arabic RTL was buggy at launch and refined through 4.01/4.02/**4.04**).
  So "VISUAL renders correct" was validated on the OLDEST possible engine, and a later patch that
  started bidi-ing Hebrew would make the shipped mod **reversed for the entire updated majority** —
  Maor is likely the canary, not an edge case. **UNIVERSAL: a bidi/render proof is only valid on the
  version the USERS run — validate on the CURRENT patch (or the oldest AND newest), never on a
  years-old build, or you can certify a mod-wide bug as "correct".**
- **What it is NOT** (ruled out by the symptom): a font problem (reversed ≠ tofu), the install path
  (manual and launcher both write the same `ar.w3strings`), or the wrong slot (Hebrew appearing at
  all proves the Arabic slot is active). Reversed = ORDER only = bidi = engine version.
- **⚠️ CANNOT get a local 4.04 rig by patching the FitGirl 4.00 repack (attempted 2026-07-21).** The
  cs.rin.ru hpatchz `_AiO-CS` update pack (4.00→4.04) is a binary diff built against CLEAN-SOURCE
  vanilla bytes; a FitGirl repack recompresses/reorders the heavy `.cache`/`.bundle` files, so
  **194 of 547 files fail to patch** (content0 matched by luck, content1-12+dlc+the cracked exe do
  not). Pressing "N" would commit a Frankenstein 4.00/4.04 install → crash; press **"Y"** to abort
  (nothing is written to the game until N — the patcher works in `FilesNEW\`, so Y leaves the game
  untouched vanilla). **UNIVERSAL: a clean-source binary-diff update pack does NOT apply to a
  repack.** The only local-4.04 rig is a fresh download of a repack that is ALREADY 4.04 (current
  FitGirl W3 Complete Edition is 4.04a) — a full re-install, not an update pack. Decide that only
  after Maor's version is known. To attempt any such patch: first restore ALL mod files to vanilla
  (every `*.he_backup` → its base) so the diff sees pristine bytes.
- **✅ CONFIRMED 2026-07-21: patch 4.04 REVERSES the VISUAL Hebrew** — the reviewer (Maor) reported
  he is on **4.04** and sees it reversed, while the dev rig (4.00) shows it correct. So the shipped
  VISUAL beta.1 is WRONG for the 4.04 majority (nearly everyone — current Steam/GOG/FitGirl/DODI all
  install 4.04; 4.00 is a stale-install outlier). **The mod must be LOGICAL.**
- **Fix path READY:** `work/build_mod.py --logical` (added this session — skips `visual_line`, stores
  logical order, `logical_line()` only strips stray bidi controls). **Ship plan (verify before
  publishing, never blind):** get a 4.04 rig → `build_mod.py --logical --deploy` + font → confirm
  in-game it renders correct on 4.04 → rebuild the release LOGICAL → `sync_release_data.py` →
  `pack_release.py` → `gh release upload v1.0.0-beta.1 --clobber` → beta.1a.
- **⚠️ Getting a local 4.04 rig: the cs.rin.ru update packs DO NOT apply to a FitGirl repack** (see
  the bullet below); the working path is a **fresh download of the current repack, which is baked
  4.04a** (FitGirl/DODI W3 CE = v4.04 build 13463743). ⚠️ `fg-selective-english` = VOICE only; the
  TEXT (all `w3strings`, incl. Arabic) always ships in the base, so English-VO install is exactly
  right (Text=Arabic + Speech=English).

### ✅✅ beta.2 SHIPPED — LOGICAL + 15,137 QA + cinematics fix, live on all surfaces (2026-07-21)
The LOGICAL fix is BUILT, verified on a real 4.04a rig, and **published to GitHub + Worker + Supabase**.
- **Content:** LOGICAL text (fixes the 4.04+ reversal) + **15,137 QA-review fixes** + 349 restored
  `<<GI_...>>` keybind tokens (31 non-deterministic tokens + the final QA part deferred to the next
  version, per the user) + David font (6 faces) + fixed cinematics + langname "Hebrew" + DLC banners.
- **Publish state (LIVE, verified):** GitHub `v1.0.0-beta.1` assets CLOBBERED (kept the tag — it is the
  only release + Full Release = `releases/latest`) with `witcher3_hebrew.zip` **3,863,261 B, sha
  `3e1985c9367f830deb783d9b1a9335f95c29bae994d5723357cb7e1003c7ff07`** + `manifest.json` (version
  `1.0.0-beta.2`). Worker `/witcher3-hebrew/manifest` → beta.2 + that sha; `/archive` → 200. Supabase
  `games` version→beta.2 + changelog (the "what fixed" text), `mod_version_history` beta.2 is_current
  (beta.1 kept as history). `/api/games` + public history verified beta.2. The launcher self-updates
  via the Worker manifest (SHA-256 re-verify passes = 3e1985c9). Description unchanged (already good).
- **Local package saved + F: reverted:** the manual-download package = `games/witcher3/witcher3_hebrew.zip`
  (+ `manifest.json`); the "saved aside" source tree = `games/witcher3/release/` (install.py + lib/ +
  data/). The F: 4.04a rig was reverted to pristine vanilla via `install.py "<F:>" --revert` (57 items
  restored, 0 leftover `.he_backup`, state removed — verified).
- **🔴🔴 THE CINEMATICS DOUBLE-COMPRESSION BUG (the LOGICAL "crashes at launch" root cause) — UNIVERSAL
  for any bundle repack with pre-compressed inputs.** `build_hebrew_subs()` returns a **zlib-compressed**
  payload for `pack==1` files (the recap `recap_wip_ar.subs`), but `install.install_cinematics._repack`
  ALSO compresses `pack==1` entries (`raw = zlib.compress(payload, 9) if pack == 1 else payload`). So a
  pre-compressed `.subs` shipped in `release/data/subs/` gets **double-zlib'd** on the user's machine →
  the movies.bundle entry is a zlib stream wrapping another zlib stream → the engine's decode yields
  garbage → **crash the moment the game loads the boot recap.** It was invisible on the menu-proof (only
  the recap uses pack==1) and only the RECAP crashed, not the 71 pack==0 storybook subs. **FIX: the
  shipped `.subs` must hold the RAW (un-compressed) payload for `pack==1` files** (`zlib.decompress`
  before writing to `release/data/subs/`), so the installer compresses exactly ONCE. Guard: a pack==1
  `.subs` whose bytes decompress to something that ITSELF starts with the zlib magic `0x78` is
  double-compressed. **UNIVERSAL: when a repacker re-compresses entries by pack-mode, the staged input
  for those entries must be RAW — shipping already-compressed bytes double-compresses; verify each staged
  file's compression state against the repacker's per-mode behavior, not just its size.** Isolation is
  what found it: the recap USM patch alone worked ("לא קורס"), the `.subs` repack alone crashed ("קרס"),
  and both the VISUAL and the 4.00-built LOGICAL `.subs` crashed identically → the bug was the repack
  path, not the bidi mode.
- **🔑 Supabase publish auth gotcha (this project uses the NEW API-key format):**
  `SUPABASE_SERVICE_ROLE_KEY` is now an `sb_secret_...` key (NOT a JWT), and PostgREST **rejects it from a
  browser User-Agent** with `401 "Forbidden use of secret API key in browser"` — while the Cloudflare
  1010 trap on the Management API REQUIRES a browser UA. And `publish_version.py` uses psycopg2 on
  `SUPABASE_DB_URL`, whose Postgres ports are blocked here. **So the reliable DB-write path for a publish
  is the Management API query endpoint** (`POST api.supabase.com/v1/projects/<ref>/database/query`,
  `Authorization: Bearer <SUPABASE_ACCESS_TOKEN=sbp_...>`, browser UA) — the same channel used for DDL.
  Use PostgreSQL dollar-quoting (`$CL$…$CL$`) for the Hebrew changelog to avoid all quote-escaping. The
  `games`+`mod_version_history` update was done this way (publish_version's SQL, run via the Management
  API instead of psycopg2). Reusable runner: `scratchpad/mgmt.py`.
- **NEXT version (deferred, per the user):** the 31 non-deterministic `<<GI_...>>` tokens + the final
  New-Era QA part (the ~92.6k-line review below, isolated from `hebrew.json`). 2 `news_drafts` (kind=mod,
  source=claude) were pushed for admin approval.

### ✅✅ beta.2 RE-PUBLISHED IN PLACE — in-game review found 3 defect classes, all fixed (2026-07-21)
User reviewed the first beta.2 in-game (F: 4.04a rig) and found real defects; each was fixed, verified
in-game, and re-published. **⚠️ VERSION STAYS `1.0.0-beta.2`** — I first bumped to beta.3, but the user
explicitly wanted it kept at beta.2 ("לא 3 אלא 2"), so the corrected content ships UNDER beta.2 (the
beta.3 `mod_version_history` row was deleted; the beta.2 row updated in place). Final state: GitHub
v1.0.0-beta.1 assets clobbered, manifest→**1.0.0-beta.2**, sha
**`c6f39627085e8f6573bafd075105b383f650020e0753f1c4247a976d1db7b9b4`**, 3,862,320 B; Supabase games +
mod_version_history (beta.2 is_current) + Worker + `/api/games` all beta.2. The beta.2 changelog = the
original beta.2 text with the new fix APPENDED at the end (per the user). The /translate pool was synced
to the final `hebrew.json` (**21,911 changed rows**, surgical `current_he`-only UPDATE via the Management
API). ⚠️ Keeping the same version means a launcher user already on the FIRST beta.2 (sha 3e1985c9) is not
auto-offered the corrected build (same version → not "newer"); acceptable here (first beta.2 was minutes
old, ~0 downloads; beta.1 users like the reviewer DO get it since beta.2 > beta.1).
- **🔴 51 Arabic-only leaks translated (0 left).** These had NO clean English source (`en=none`/mojibake)
  so `build_mod`'s English fallback couldn't cover them → they fell back to the vanilla Arabic and rendered
  Arabic in-game (settings: `שימון חרבות אוטומטי`, `יחס גובה-רוחב`, motion-blur; the Blood&Wine IT-security
  job-title easter-egg list; a few dialogue lines with `(names)`). Translated **from the game's own CDPR
  Arabic** (NFKC-normalize the presentation forms first — `unicodedata.normalize("NFKC", …)` — the stored
  Arabic is shaped/presentation-form, unreadable raw), user-authorized ("תעשה הכל"). Detected by decoding
  the vanilla `ar.w3strings` and classifying each id: not-in-`hebrew.json` AND not-in-clean-`en` AND
  has-Arabic-script = a visible leak. **UNIVERSAL: "remaining Arabic = N" in the build log counts per-file
  non-Hebrew-non-English entries (incl. duplicates/symbols); the real leak count is UNIQUE ids with
  Arabic-script — verify that, not the build number** (build said 18, the true unique count was 0 after
  the fix).
- **🔴🔴 THE `<heb>-<Latin>` HYPHEN BIDI FIX — the full solution took a font edit (universal for W3, and any
  bidi engine).** `ה-NPC` / `ל-GWENT` / `ב-nits` (90 lines) rendered the ASCII hyphen on the visual LEFT
  (`הNPC-`) on the 4.04 engine — the neutral hyphen mis-resolves against the trailing Latin LTR island.
  The candidates, each PROVEN in-game (never guessed — [[bidi-is-version-dependent]]):
  - **Candidate B — RLM (U+200F) after the hyphen** (`ה-‏NPC`): POSITION correct ✅, but a **thin vertical
    bar** appeared — `fonts_ar.redswf` font 1 (Arial, the UI font) ships a **visible 43-byte glyph for
    U+200F** (advance 0 but a real shape). So the RLM is not invisible in this font.
  - **Candidate C — Hebrew maqaf (U+05BE)** (`ה־NPC`): POSITION correct ✅ (maqaf is strong-RTL, needs no
    control char), but the maqaf glyph **sits too high** (Hebrew maqaf is a raised bar) — reads wrong next
    to Latin.
  - **✅ FINAL — RLM + EMPTY its font glyph.** Keep the normal ASCII hyphen (mid-height, familiar) + the RLM
    anchor, and blank the RLM's glyph shape in the font so it is truly invisible. `work/empty_rlm_glyph.py`:
    CR2W→CFX(zlib)→GFx, set font 1's U+200F shape `43B → \x10\x00` (the empty `.notdef` shape) + advance 0,
    `rebuild_gfx`→CFX→CR2W delta-0 splice + patch the CR2W CFX diskSize (same proven pipeline as
    `build_font.py`; CFX SHRINKS so it always fits). `build_mod.logical_line` gained `_fix_prefix_hyphen`
    with `HYPHEN_FIX = rlm(default)|maqaf|none` env toggle. **UNIVERSAL: to anchor a `<RTL-prefix>-<LTR-word>`
    hyphen on a bidi engine, insert an RTL-strong control after the hyphen — and if that control has a
    visible glyph in the font (check the CodeTable + shape length!), empty the glyph rather than switch to
    a strong-RTL punctuation char that renders at the wrong height.** Font facts: font 1 also has a visible
    U+200E LRM glyph; `.notdef` (glyph 0) is the empty shape `\x10\x00`; U+061C/U+2067 are absent (an absent
    control would draw the empty .notdef, but its non-zero advance risks a gap — emptying the present glyph
    is safer).
- **🔴 THE QA-REVIEW REGRESSION LESSON — an automated review DEGRADES some already-correct lines.** The
  15,137 New-Era QA fixes applied for beta.2 included real regressions the user caught in-game: `מדיטציה עד`
  ("Meditate until") was "fixed" to **`התמדו עד`** (persist!), and a systematic error where **"meditation"
  was rendered `התייעצות` (=consult)** across several tooltips. Fixed **14 meditation lines** to the correct
  term `מדיטציה` (English-guarded: only where `en` contains "meditat"; per-id targeted values, excluding a
  false positive where `התבודד` was a clan legend, not meditation) + one `תריסים`(shutters)→`שיקויים`(potions).
  Compared current `hebrew.json` vs the pre-QA backup `hebrew.json.bak.qarev.*` to isolate what the QA
  changed. **UNIVERSAL: a monotonic-guarded automated QA review is NOT net-zero-risk — it can turn a correct
  line wrong; spot-check the highest-visibility recurring TERMS in-game after applying it, and keep the
  pre-QA backup so a regression can be diffed and reverted per-id.** The comprehensive fix for the rest is
  the isolated 2nd-update New-Era QA (below), reviewed against all the game's professional translations.
- **W3 dashboard reset (user: the progress data is stale now that it's published).** The homepage progress
  dashboard still showed W3 as "QA 28%" (the live 2nd-update pusher). Set the `progress_snapshots` row
  `show_dashboard=false` **AND `source='manual'`** — the `/api/admin/progress` endpoint returns **409
  source-locked-manual** to a MONITOR_TOKEN caller, so the still-running fleet pusher can no longer re-enable
  it (verified: the row's `updated_at` stayed frozen across pusher ticks). The dashboard filters
  `show_dashboard !== false`, so W3 drops off immediately. Reversible (flip the flags). The 2nd-update QA
  keeps running/pushing; it is just 409'd (harmless) and hidden.

### New-Era QA over ALL 94,167 lines — running for the SECOND update
User scoped it explicitly: **"וזה יהיה לעדכון השני למוד ולא מה שיפורסם כמוד עכשיו"**. So the
pipeline is deliberately **isolated from the published build — it never writes `hebrew.json`.**
- `fleet/build_qa_corpus.py` → **92,613** lines (excludes ids already in `w3_newera_passed.json`,
  drops mojibake EN), each with its ar/ru/pl/es/it parallel; ordered by VISIBILITY
  (tier 0 base-short 10,982 → 3 DLC-long 1,968); split by `md5(k)%n` into 46,233 / 46,380
  (disjointness + completeness asserted).
- `w3qa_nim.py` reviews with a **monotonic guard** (a review may only FIX: gender flips must be
  oracle-confirmed, STRUCT tokens preserved, similarity floor 0.45, else keep the original).
  `fold_qa_review.py` banks only `iss != "ok"` into `fleet/qa_reviewed.json`;
  `apply_qa_review.py` (for beta.2) applies a fix ONLY if the spine still equals the reviewed
  `old` AND a host-side `safe()` re-check passes.
- Deployed to `C:\w3qa` on 2 streams via `w3qa_deploy.sh`; `selfheal_w3qa.ps1` matches **`w3qa_nim`
  only** so it can never kill the co-resident `w3_nim`/`w3ut_nim`/`pt_nim`. `W3qaFleetPull` every
  20 min. Early yield confirms the method: `Elf→אלף` (the number) should be `אלפית`, the NAME
  `Suzy` was translated as `סופי`.
- **⚠️ A stream that never writes `out.json` while its twin does is usually a STALE LOCK, not a bad
  key.** Rule out the key first (fingerprints differed; a probe returned HTTP 200 in 0.7 s), then
  kill the process, delete `C:\w3qa\w3qa.lock`, relaunch.
- **⚠️ Inline multi-line `python -c` over SSH gets mangled by quoting (returns empty output);
  `scp` a script file and run it.** Same class: the Bash tool rejects a command containing a
  Hebrew regex literal — write it to a scratchpad file instead.


## The Witcher 3: Wild Hunt Hebrew — groundwork DONE, GO (easy tier) (2026-07-01)

New game scaffolded at `games/witcher3/` (RECON.md / FEASIBILITY.md / PIPELINE.md + `work/`). Phase-1
groundwork complete; **verdict 🟢 GO — easy tier** (like Anno 1800). No game file modified (read-only +
a codec verified against the game's own files). Memory [[witcher3-groundwork-go]].

- **Install:** `D:\Games\The Witcher 3 - Complete Edition` (GOG, next-gen 4.x, patched 2026-06-30).
  Engine = **REDengine 3** (NOT CR2W/REDengine 4 — the CP2077 WolvenKit 8.x can't read TW3). exe =
  `bin\x64\witcher3.exe`, launcher `gameId="witcher3"`. **No anti-cheat.**
- **Text = `.w3strings`** (magic **"RTSW"**, version **163**/0xA3) in `content\content0..12\<lang>.w3strings`
  + `dlc\<name>\content\<lang>.w3strings` (ep1=Hearts of Stone, bob=Blood and Wine, dlc1..20). **17 langs
  incl. official `ar` (RTL, added next-gen 4.0).** No UI-vs-subtitle file split — all intermixed, keyed by
  numeric `str_id`; the human-readable key is NOT stored (only a `key_hash`).
- **Format FULLY CRACKED + pure-Python read/write codec `work/w3strings.py`** (from
  `hhrhhr/Lua-utils-for-Witcher-3`, verified byte-for-byte): magic+version+key1 → block1
  `{str_id^encKey, offset, strlen}×N` → block2 `{key_hash, str_id^encKey}×N` → block3 UTF-16LE blob
  (0x0000-terminated) → footer key2; `keyID=key1<<16|key2` → language-key table → encKey; custom `bit6`
  varint (`emit_bit6` proven vs the game's own count bytes). **Strings XOR-encrypted per-language EXCEPT
  keyID 0 = cleartext.**
- **🔑 KEY WINS:** (1) **Arabic slot = CLEARTEXT (keyID 0)** → Hebrew = plain UTF-16LE, no encryption.
  (2) **`str_id` SHARED across languages** after `^encKey` (verified `0x7923498e^0x79321793=0x00115e1d`=AR
  id) → map EN→HE by id. (3) **Bidi = VISUAL (pre-reversed `visual_line`, NO RLO)** — CONFIRMED in-game: the
  Arabic ships logical+U+202E RLO but the engine only bidi's Arabic, NOT Hebrew (menu v1 logical+RLO=mirrored,
  v2 VISUAL=correct). Translator writes LOGICAL; `visual_line` applied at BUILD only. (4) **Font ALREADY covers
  Hebrew** — the menu proof rendered Hebrew with zero tofu → no SWF/font work. (5) **Identity round-trip:**
  MD5-identical small files, semantic-identical (valid) large — AND **the game LOADED our Python-built
  27,601-string `ar.w3strings`.**
- **Scope:** ~**94,377 unique str_ids** / ~6.5M EN source chars. Corpus dumped (gitignored) via
  `work/dump_corpus.py` → `extract/{en,ar,index}.json`. Only 86 ids untranslated in the AR slot. Length
  heuristic: ~52k short (UI-ish) / ~42k mid+long (dialogue-ish).
- **Deploy:** `<game>\Mods\modHebrew\content\<mirror>\ar.w3strings` (+ per-DLC), or overwrite base
  `content\*\ar.w3strings` (reversible via backup). **NO bundle repack for text, NO anti-cheat.** Activation =
  Options → Text Language=Arabic (العربية), Speech=English (independent; `user.settings [Localization]
  TextLanguage=AR`). Next-gen RTL precedent: Nexus "Community Patch — Menu Strings — Arabic" (11005).
- **✅ ALL GATES CLOSED (in-game menu proof PASSED 2026-07-01):** font=no-work, bidi=VISUAL, encoder loads
  in-game. Proof tooling `work/build_menu_proof.py` (`--deploy`/`--revert`, backup `content0/ar.w3strings.he_backup`).
  **Phase 2 = delegate translation** of the ~94k ids ([[delegate-all-translation]]) → build via
  `w3strings.encode` + `visual_line` → deploy → publish like SM2/WD2/Anno (GitHub `witcher3-hebrew-mods` +
  Worker slug `witcher3-hebrew` + Supabase games row id=`witcher3` + mod_version_history). First Phase-2 step:
  a quick in-game DIALOGUE proof to confirm subtitles are also VISUAL (likely).
- **✅ COMMUNITY /translate POOL LIVE (2026-07-01):** all clean W3 lines imported — **92,829 rows**
  (`games/witcher3/extract/ct_strings.json` → `universal/community_translate.py import witcher3`). From
  `extract/en.json` (94,377): dropped 1,548 junk (numbers/symbols/keybind F1/M/R&D), `<br>`→newline
  (reversible on build), stray tags stripped, `[...]` editorial brackets kept (prose). current_he='' (no
  existing Hebrew). Live on `hebrew-translation-hub.com/translate` (`api/translate?action=games` → witcher3
  92,829 open; DB read, no deploy). games row id=`witcher3` already existed (status=final,
  show_on_website=true — pre-existing). Future build: map contributor `\n`→`<br>`.
- **✅ DAVID font WORKS in-game (2026-07-01, user-confirmed "עובד"):** a full pure-Python font pipeline in
  `work/` swaps the Hebrew glyphs to **David** and renders correct RTL Hebrew in the main menu (no tofu, no
  crash). Pipeline: `potato_bundle.py` (POTATO70 + Snappy reader) · `gfx_inspect.py` (CR2W→CFX(zlib)→GFx) ·
  `swf_font.py` (DefineFont3 parse/serialize) · `swf_glyphgen.py` (TTF→SWF glyph shapes, ×10 EM, Y-negated) ·
  `build_font.py` (replace 56 Arial Hebrew glyphs with David + **lossless** `rebuild_gfx` + patch the CR2W
  CFX-buffer `diskSize` @cfx_off-4) · **`repack_bundle.py`** (the KEY fix). **ROOT CAUSE of the ~5
  black-screen crashes was the bundle SPLICE, not the font:** the old `deploy_font_bundle.py` used a delta-0
  in-place splice with my WEAK RLE-only `snappy_compress` + ZERO-padding the snappy stream to the entry
  zsize → the game's bundle loader choked → corrupt GUI bundle → black screen. The
  glyph/winding/GFx-rebuild/diskSize were correct all along (proven: my David 'א' ≈ ffdec's byte-for-byte;
  winding matches Arial; `rebuild_gfx({})`==original; ffdec CAN author these glyphs). **Fix = a proper
  POTATO70 repack** (`repack_bundle.py deploy`): re-encode the fonts_ar entry as **pack=1 zlib** (standard —
  like the game's own `fonts_en.redswf`) at natural size, rewrite the 16-byte-aligned data section, shift
  later entries' offsets, update the header (filesize@8, data-size@12). `deploy-orig` = isolation test,
  `revert` = restore (game must be CLOSED — locks the bundle; a hung black-screen `witcher3.exe` must be
  `Stop-Process`'d first). **LESSON: never ship a delta-0 zero-padded splice with a home-rolled compressor
  into a game bundle — do a proper repack with a standard codec the game already uses (here pack=1 zlib).**
  Font is bonus polish; translation groundwork + the 92,829-line /translate pool DONE.


