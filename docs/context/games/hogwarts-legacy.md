## Hogwarts Legacy Hebrew — Phase-1 groundwork DONE, GO (likely easy tier) (2026-07-04)

New game scaffolded at `games/hogwarts_legacy/` (RECON.md / FEASIBILITY.md / PIPELINE.md +
`work/`/`tools/`/`extract/`). **Verdict 🟢 GO — ALL GATES CLOSED (in-game menu proof PASSED
2026-07-04). One of the easiest games in the project.** Both remaining gates — **bidi mode** and
**font** — were closed by one user screenshot: with the game set to Arabic, the deployed override
pak's patched `כתוביות` rendered as **clean, correctly-ordered Hebrew** (no tofu) in the Arabic
settings menu → override-load + native ICU bidi (store LOGICAL) + vanilla-font Hebrew coverage all
confirmed at once. Memory [[hogwarts-legacy-groundwork-go]]. Ready for Phase 2 (delegate
translation → build via `hl_bin.encode` (LOGICAL) → pack V11 → `~mods` deploy → publish).

- **Install:** `E:\SteamLibrary\steamapps\common\Hogwarts Legacy` (Steam). Engine = **Unreal
  Engine 4** (internal codename **"Phoenix"** — the project folder is literally named `Phoenix/`),
  likely UE 4.27. Main exe `Phoenix\Binaries\Win64\HogwartsLegacy.exe` (450MB); root
  `HogwartsLegacy.exe` (289KB) = a small EOS-bootstrap stub. **Denuvo on the exe only** (doesn't
  checksum assets — confirmed by the existing Nexus mod scene); **no EAC/BattlEye**; single-player
  only → zero ban/enforcement risk from asset mods.
- **Archive = hybrid legacy-pak + IoStore.** `Phoenix\Content\Paks\pakchunk0-WindowsNoEditor.pak`
  (5.6GB, classic UE4 container) + matching `.ucas/.utoc` IoStore pair (13.7GB, big streaming
  assets). **All the localization text lives in the LEGACY pak** — confirmed via direct byte-level
  footer parse: `FPakInfo` version **11** ("Fnv64BugFix"), mount `../../../`, **NOT AES-encrypted**
  (all-zero encryption GUID), compression methods Zlib+Oodle, 26,546 file entries. No standalone
  `oo2core_*.dll` ships (Oodle statically linked into the exe).
- **🟢 Container already has a mature open-source tool — no reader/writer had to be hand-cracked
  (a first for this project).** **`repak`** (Rust CLI, MIT/Apache, `trumank/repak` v0.2.3) fully
  reads AND writes this exact pak version with no AES key. Downloaded, SHA-256-verified, vendored
  at `games/hogwarts_legacy/tools/repak.exe`. Proven: `repak list`/`get` extracted the 4 target
  locale files directly from the live pak; `repak pack --version V11` built a fresh override pak
  whose extracted content is **byte-identical** to a plain copy — the write path round-trips clean.
- **🟢 `.locres` is a DEAD END — do not build around it.** The game ships the standard-looking
  `Content/Localization/Game/<culture>/Game.locres` tree (14 locales incl. `ar`/`ar-AE`) but these
  are boilerplate/near-empty (extracted+decoded: `en`=146B holding ONE default engine key,
  `ar`=37B empty). **The REAL, actually-read text is a custom Avalanche format:**
  `Phoenix/Content/Localization/WIN64/{MAIN,SUB}-<locale>.bin` (one flat pair per locale, not
  per-culture folders) — `MAIN`=UI, `SUB`=subtitles/dialogue (speaker-tagged keys). Format
  "AVAFDICT 2.0", reverse-engineered from the open-source `insomnious/parseltongue` (C#) and
  reimplemented as a pure-Python codec: `games/hogwarts_legacy/work/hl_bin.py` (`decode`/`encode`,
  self-tested round-trip on all 4 real files). **Trivially simple format — no compression, no
  encryption, no delta=0 size-matching needed** (unlike every other game here): 32B UTF-16LE magic
  "AVAFDICT 2.0" + 5×int64 header + entryCount×24B entry records (key/value offset+size into one
  flat UTF-8 data blob) — a fresh rebuild is always safe regardless of new size.
- **Real extracted scope (verified via repak+hl_bin.py):** `arAE` = official Arabic locale, REAL
  complete content. MAIN: EN=18,889 AR=18,889, **100% key match**. SUB: EN=34,955, AR=39,684,
  **all 34,955 EN keys have an AR counterpart** (+4,729 AR-only extras = out of scope, no EN
  source). **Total translatable = 53,844.** Tokens to preserve verbatim: `{0}`/`{1}` braces (835),
  `<img src="..."/>` icon tags (1,312), `[LT icon]`/`[...]` bracket tokens (2,429), real embedded
  newlines in multi-paragraph notes/letters (381, up to 1,735 chars). No HTML entities.
- **🔑 THE differentiating finding — Unreal Engine has NATIVE Unicode bidi (ICU) + Arabic shaping
  (HarfBuzz), unlike every custom engine in this project** (CR2W/cohtml, Disrupt, Anvil, Zouna,
  REDengine — all needed manual visual pre-reversal or logical+`&rlm;`-anchor tricks). Per Epic's
  own docs, Slate's `Auto` text-shaping mode applies full ICU bidi reordering for any RTL culture;
  Hebrew needs bidi-reordering ONLY (no letter-joining like Arabic), so it rides the simpler half
  of the same pipeline — community UE forum reports describe Hebrew "working out of the box" once
  a Hebrew-covering font exists (their failure mode was always missing glyphs/tofu, never wrong
  order). **This may be the first game in this project storable LOGICAL with zero bidi code of our
  own** — the menu-proof below tests this directly. Font mechanism if needed: UE4/5 **Composite
  Font** (per-Unicode-range fallback typeface, official Epic mechanism, Arabic-fallback precedent
  found in the community) — expected far simpler than the DXT5-atlas/embedded-TTF hacks elsewhere.
- **Deploy = non-destructive additive override pakchunk in `~mods\`** (confirmed UE4/Hogwarts-
  Legacy-community-standard mechanism via modding.wiki + GitHub guides — the same mechanism every
  published Nexus mod for this game uses): a new unused chunk ID (e.g. `111`) dropped as
  `Phoenix\Content\Paks\~mods\pakchunk111-WindowsNoEditor_P.pak` mounts at higher priority than
  `pakchunk0` for any path it contains — **`pakchunk0` itself is never touched**, so Steam/Epic/GOG
  "Verify Integrity" never reverts it.
  found in the community) — expected far simpler than the DXT5-atlas/embedded-TTF hacks elsewhere.
  **✅ CONFIRMED IN-GAME 2026-07-04: store LOGICAL, zero bidi code, zero font work** (see below).
- **✅ Menu-proof PASSED — user-confirmed in-game 2026-07-04 (BOTH remaining gates CLOSED).**
  `games/hogwarts_legacy/work/build_menu_proof.py --deploy` extracted the live `MAIN-arAE.bin`,
  patched 4 keys (`Menu_Options`→pure-Latin marker `ZZ-HL-PIPELINE-OK-ZZ` to prove the override
  loads at all; `Settings_Brightness`→בהירות, `Menu_Subtitles`→כתוביות (stored **LOGICAL**, no
  reversal/RLM); `Menu_LanguageSelect`→בחר שפה), packed via `repak pack --version V11`, deployed to
  `~mods\pakchunk111-WindowsNoEditor_P.pak` (pure additive override, `pakchunk0` untouched). **Result
  (user screenshot):** with the game set to Arabic (العربية), the Arabic settings menu showed the
  patched `כתוביות` as **clean, correctly-ordered Hebrew** (no tofu) → three things confirmed at
  once: (1) the extract→`hl_bin` patch→`repak pack V11`→`~mods` pipeline works end-to-end; (2)
  **bidi = LOGICAL** — native ICU bidi reordered our logical text correctly, so we write **zero bidi
  code** (a first for this project); (3) **font = NO WORK** — the vanilla Arabic-locale font already
  covers the Hebrew block. Revert: `python work/build_menu_proof.py --revert`.
- **✅ Community `/translate` pool LIVE (2026-07-04).** All translatable lines uploaded via
  `games/hogwarts_legacy/work/build_ct_strings.py` → `extract/ct_strings.json` →
  `universal/community_translate.py import hogwarts`. **53,810 rows** (18,855 MAIN + 34,955 SUB),
  all `current_he=''` (fresh). Verified live: `/api/translate?action=games` → hogwarts total
  53,810 / untranslated_open 53,810. The `games` row id=`hogwarts` already existed (status
  `locked`, show_on_website=true). **Non-translatable filter** (`is_translatable()` in
  `build_ct_strings.py`): dropped 28 settings VALUES identical in every language — 16 resolutions
  (`1920x1080`) + 12 FPS labels (`120 FPS`) — plus no-letter tokens (`{0}%`,`{0}/{1}`,`???`,`,`,`=`,`%`).
  **KEPT (user decision 2026-07-04):** the 194 `cbi_Keyboard_*_Pronunciation` accessibility
  key-name strings (`Backspace`/`Left arrow`) — real translatable words; and `Uncapped`, compass
  N/E/S/W, `+{0} HP`/`XP`, `{0}h`/`{0}m` templates. **⚠️ Key convention:**
  `string_key` is prefixed **`MAIN:<key>`** / **`SUB:<key>`** (MAIN/SUB keys are globally disjoint —
  0 overlap — but the prefix routes each approved line back to the right `.bin` at build). `section`
  carries the same info; `context` = the raw game key (SUB keys encode the speaker). **Phase-2 build
  MUST strip the `MAIN:`/`SUB:` prefix** before feeding `hl_bin.encode` for the two files.
- **✅✅ PHASE 2 TRANSLATED BY THE COMMUNITY-COMPUTE FLEET + QA'd (2026-08-03).** The whole 53,810-line
  corpus was seeded New-Era into `cc_lines` (`control_plane/build_hogwarts_newera.py` → `seed_jobs.py`,
  game label **`hogwarts`**, `target`=the `MAIN:`/`SUB:` string_key, `src`=`EN: …\nAR: …` panel) and
  the volunteer fleet drained all 53,810 to `done`; pulled to **`work/hebrew.json`** ([[community-compute-pull-results]]).
  **🔴🔴 "done" ≠ correct — a QA-before-ship pass (`work/qa_scan.py`) found 3,552 defective lines the fleet
  had silently committed as `done`:** **380 reference-panel LEAKS** (the worker echoed the `EN:/AR:` panel —
  71 recovered DETERMINISTICALLY [66 strip-to-pure-Hebrew + 5 strip-to-pure-token], 309 unrecoverable) +
  **2,454 UNTRANSLATED ARABIC** (the worker returned the arAE reference verbatim instead of translating —
  **and the `src` DID carry good English**, so a re-queue fixes them) + **21 untranslated English**. Result:
  OK 50,253 · deterministic-recover 71 (applied, backup `hebrew.json.bak.qa.*`) · **RE-QUEUE 2,784** ·
  legit PASSTHROUGH 768 (pure tokens / `<i>Spell</i>` names / keyboard-key labels / brands — the game's
  own Arabic keeps these Latin too, do NOT re-queue). **⚠️ `cc_submit` rejects an EMPTY output but ACCEPTS
  an Arabic/leaked-panel one as `done`** — so the fleet's own completion is not a quality signal; always run
  a content QA before it ships.
- **✅ RE-QUEUED the 2,784 to the live fleet (`work/requeue_fleet.py`, delegate-all-translation — Claude never
  translates).** Reset `cc_lines` rows (`game=hogwarts` ∩ `target IN requeue_keys.json`) to `status=open`,
  `out=null`, `worker_id=null`, `lease_until=null`, `collected=false`; the running fleet re-claimed them
  immediately (verified: 50 `claimed` within seconds, `done` 53,810→51,026). Non-destructive — the bad
  outputs stay in `work/hebrew.json` + its backup, and a future `collect` re-pulls only fresh output.
  **Recovery logic (reusable): a leaked panel is deterministically recoverable ONLY when, after stripping
  every `XX:` label line, the remainder is (a) exactly one pure-Hebrew body with no Latin/Arabic run, or
  (b) a pure token — anything with competing foreign prose or a nested label goes back to the fleet.**
- **✅✅ AUTONOMOUS CONVERGENCE LOOP — corpus now 0-defect (2026-08-04).** `work/auto_qa_loop.py` (imports
  `qa_scan`'s classifier) runs UNATTENDED in the background: wait for the queue to drain → re-pull the
  re-queued keys' fresh `out` → merge (backup) → classify + apply safe-recovers → if RETRANS==0 stop, if
  it doesn't shrink 2 rounds park `stuck_keys.json`, else re-queue and loop. Converged **RETRANS
  2,784 → 804 → 66 → 4 → 3 (stall)** across the fleet passes with ZERO manual prompting. **Final: OK
  53,029 · PASSTHROUGH 781 · RETRANS 0.** ⚠️ **The 3 "stuck" were `AMD FSR 1.0/2/3` — brands, not
  defects**; the classifier missed them, so `is_passthrough` was widened: **a Latin string with NO
  lowercase letter (ALL-CAPS acronym / brand / tech label: FSR, DLSS, XeSS, FidelityFX CAS) is
  PASSTHROUGH** — the game's own Arabic keeps these Latin. Built-in guards: 500-retry on the transient
  PostgREST schema-cache reload (hit twice), per-round backups, 10-round cap, stall-detection.
- **⚠️ END-OF-PHASE-2 GENDER QA RAN (report only, NOT applied):** `work/gender_qa.py work/hebrew.json` →
  **257 addressee-gender suspects of 832 determinable, all `ar=f he=m`** = the systematic default-to-masc
  debt (the fleet translated genderless English → masc "אתה" while the game's Arabic says fem "את").
  `gender_suspects.jsonl` is the ranked candidate list for a re-inflection pass (deterministic morphology
  via `universal/dualgender_inflect.py` or delegate — NEVER a re-translation, NEVER auto-applied).
  ⚠️ **Player-gender-variant nuance:** Hogwarts swaps `playerfemale_`/`playermale_` keys at runtime, so a
  base line addressed to the player can legitimately carry either gender — review before flipping; a blind
  masc→fem flip could be wrong on a genuinely-male-addressee line. Gated with build/publish.
- **✅ LOCAL BUILD DEPLOYED + iterated on the user's in-game testing (2026-08-04).** `work/build_hebrew.py`
  (`--revert`): extract fresh arAE skeleton → decode → merge `hebrew.json` (strip `MAIN:`/`SUB:`, keep the
  4,729 AR-only extras untouched) → **IRON-RULE dash normalize at the build gate** (`universal/text_norm.
  normalize_dashes` on EVERY value incl. the AR extras → 0 long-dashes in the baked output) → `hl_bin.encode`
  → repak V11 → `~mods\pakchunk111-WindowsNoEditor_P.pak`. Verified by reading Hebrew back OUT of the packed
  pak (100% key match). ⚠️ **The game LOCKS the pak while running** (`WinError 32`) and a pak change only
  loads on restart → close the game (`taskkill /F /IM HogwartsLegacy.exe`, TWO pids: root stub + Phoenix
  exe) before building.
- **🔴🔴 IN-GAME TESTING EXPOSED A TOKEN-PRESERVATION BUG qa_scan MISSED — `{UMG...}` input-glyph tokens
  translated (2026-08-04).** The mods-menu showed literal `{UMGלשונית תפריט ראשי של שינויים - ימין}` — the
  fleet TRANSLATED the identifier inside `{UMGModMainMenuTabRight}` (an input-glyph binding the game swaps
  for a button icon). `work/token_fix.py` compares each line's HARD-token multiset (`{..}`/`<..>`/`%spec`/
  `&ent;`, **excluding `[[dialogue choice]]` whose content IS translatable**) vs the EN source: **A** a
  token-ONLY value → HE:=EN verbatim (52, all `InputAction_*`); **B** equal per-bracket counts → positional
  swap of EN tokens back in (7); **C** else → re-queue (104 `<i>`/`<br>` drops). Token check now folded into
  `qa_scan.py` (`token_broken`). **UNIVERSAL: a content-QA that only checks script/leaks MISSES a translated
  ENGINE TOKEN — always diff the token multiset vs the source, and note `[[...]]` is a translatable dialogue
  bracket, not a token.**
- **⚠️ MULTI-SURFACE / arAE-CULTURE LIMITS the text mod CANNOT reach (measured, told the user 2026-08-04):**
  (a) **the main-menu "News of the Day" card body** (`ابحث عن بيض عيد الفصح…` = seasonal Owl-Post) is **0
  hits in our corpus** — a WB **live-service server feed** delivered per game-language, not in any `.bin`;
  (b) **the clock `م`/`ص` + Arabic-Indic digits** are the **arAE ICU CULTURE** formatting (AM/PM is NOT a
  localization key — 0 hits), baked in the Engine — the price of hijacking the only RTL locale; (c) the
  **Arabic title logo** is a baked image. **The game's own text (MAIN/SUB) IS 100% Hebrew and loads** —
  these are edge surfaces, not the bulk.
- **🔬 UE4SS TESTED IN-GAME (2026-08-09) — BOTH Lua fixes WORK, but HL's own anti-mod system kills the
  process, so UE4SS is NOT VIABLE for ongoing use. Removed.** UE keeps **LANGUAGE (text) and LOCALE
  (formatting) as INDEPENDENT settings**: our arAE hijack sets the text (→Hebrew), the clock `م`/`ص` +
  Arabic-Indic digits come from the formatting LOCALE, also arAE. `UKismetInternationalizationLibrary::
  SetCurrentLocale("en-US")` (a static BlueprintCallable UFunction) switches ONLY the formatting; a Lua mod
  can hide the news widget by name. **Both PROVEN correct in the live UE4SS log** — the persistent
  `LoopAsync(1000,…)` reapply was needed (a one-shot `RegisterInitGameStatePostHook` gets silently
  overwritten by the game's own frontend-level locale re-apply) and the news widget was found + collapsed
  on EVERY tick (`UI_BP_ScrollingTextBlock_C …WidgetTree.scrollingMOTDText`, matched by "MOTD" in
  `NEWS_NAMES`). **But ~25s after boot, HL's own "Unofficial modifications detected" dialog
  (`https://go.wbgames.com/hl-unofficial-mods`) fired and the process then exited cleanly with NO crash
  dump / NO Windows Application-Error event** — a deliberate anti-tamper close triggered by the
  dwmapi.dll proxy injection UE4SS requires, independent of what the Lua does. **We do not pursue
  bypassing it (out of scope, DRM/anti-tamper territory)** — UE4SS + all its files (dwmapi.dll, UE4SS.dll,
  UE4SS-settings.ini, `Mods\`) were REMOVED from the game folder; the safe text-only `.pak` mod
  (untouched, verified re-read after removal) is what ships. `EngineVersionOverride` needed manual
  `MajorVersion=4 MinorVersion=27` (empty by default → `[PS] Failed to find EngineVersion` → fatal scan
  timeout) — kept as a note in case UE4SS is ever revisited for a DIFFERENT purpose. **The news card
  content itself is STILL unreachable by any means** — a WB live-service server feed keyed on the text
  LANGUAGE (arAE), invisible in the corpus. **UNIVERSAL: a working Lua fix does not make a code-injection
  framework SAFE to ship — a game's own anti-modification system can silently terminate the process
  regardless of what the injected code does; verify by actually launching + waiting past the first
  ~30s, not just by confirming the mod's log shows success.** Artifact kept for reference at
  `games/hogwarts_legacy/ue4ss_locale_fix/` (README updated with this verdict) — NOT part of the
  shipped mod.
- **✅ REMAINING English words FIXED (2026-08-04) — deterministic spell/name consistency + fleet re-queue.**
  601 Hebrew lines carried a residual Latin word. `work/name_fix.py` ([[glossary-measure-then-correct]]):
  build the canonical Hebrew map from the fleet's OWN atomic single-word entries (majority vote), gated to
  genuine TRANSLITERATIONS by **(a) length-ratio 0.55-1.7, (b) a first-consonant PHONETIC match** (Accio→
  אקיו passes; the word-TRANSLATIONS `Wands→שרביטים`/`Frame→מסגרת`/`Tools→כלים` fail W≠ש etc. and are
  excluded), (c) single-word only, (d) `_Pronunciation` keyboard keys excluded, plus a post-pass Hebrew
  prefix-hyphen merge (`ה-אקיו`→`האקיו`). Result: **120 lines auto-fixed** (35 tokens — spells Accio/Protego/
  Stupefy/Descendo/Bombarda/Lumos…, creatures Kneazle/Hippogriff/Jobberknoll, characters Ranrok/Deek/Draco/
  Peeves, places Feldcroft/Irondale), **279 LEFT** (only brands/roman-numerals/ICU-`plural()` syntax — not
  defects), **331 RE-QUEUED to the fleet** (8 English-echo bugs `Honeydukes…\nמעבר…` + 230 unknown names like
  `Crossed Wands`/`Thunderbrew`/`Wind Wisps` + 101 `<tag>` token lines from `token_fix.py`). The 120 are
  BAKED + deployed (verified in the pak: `הצמד את אקיו`, `בומברדה`, `פרוטגו`). **🔴 THE PHONETIC GATE IS THE
  KEY LESSON: a real spell translit shares its initial consonant with the source; a word-translation does
  not — that single test cleanly separates "enforce the fleet's translit" from "don't inline-replace a
  common word", which length-ratio alone could not (`Frame`/`Wands` are length-plausible but W≠ש).** And a
  translit-vs-translation must NEVER touch a NON-spell single word the fleet also has a Hebrew for
  (`Hogwarts`=always the product title, `Wands`=the club "Crossed Wands") — verify each word-map entry
  IN-CONTEXT before applying.
- **✅ Typo fixed (2026-08-09, user-reported):** `Menu_Continue_desc` — "המשך את **מסעך** דרך הוגוורטס"
  (an awkward possessive-suffix form) → "המשך את **המסע שלך** דרך הוגוורטס ועולם הקוסמים" (natural
  Hebrew). Baked + deployed; verified in the pak.
- **✅✅ PUBLISHED `v1.0.0-beta.1` (2026-08-09, user said "פרסם") — ENGLISH-SLOT ONLY, per the
  user's explicit final decision ("שיהיה רק על בסיס האנגלית בלי הערבית").** `build_hebrew.py`
  was flipped: the **default now builds ONLY `enUS`** (`--also-arabic` is the opt-in testing flag
  for the old arAE-only behavior; the Arabic slot ships completely UNTOUCHED in the release —
  vanilla Arabic text, not Hebrew). A player MUST explicitly pick Settings → Text Language →
  **English** to see the translation; this was chosen over the Arabic-slot hijack because — proven
  this session with real in-game subtitle screenshots — Hebrew renders with fully correct RTL bidi
  order under `enUS` too (UE's text shaping is per-string, independent of the active culture), AND
  it fixes the clock (Latin digits/AM-PM instead of Arabic ص/م + Arabic-Indic digits) and the boot
  logo (English instead of the Arabic-calligraphy one) — both unfixable via the Arabic slot text
  file alone (see the retired-UE4SS bullet below). One caveat, documented, not chased: the "News
  of the Day" main-menu card is still a WB server feed keyed on the active text LANGUAGE, so it
  will render in whatever WB itself serves for `en-US` (not necessarily Hebrew, but not the Arabic
  it showed before either) — cosmetic, one card, not the game's text.
  - **Package:** `games/hogwarts_legacy/release_files/` (`hogwarts_hebrew.pak` — a single ADDITIVE
    UE4 override, no vanilla file touched — + `install.py` self-contained auto-detect/apply/
    `--revert` + `קרא_אותי.txt`), zipped by `games/hogwarts_legacy/pack_and_release.py [ver]
    [--pack-only]` (mirrors SM2/WD2/GoWR/Anno). `python work/build_hebrew.py` (English-only) →
    `python pack_and_release.py 1.0.0-beta.1` rebuilds + republishes end to end.
  - **GitHub** — new repo `hebrew-translation-hub/hogwarts-legacy-hebrew-mods` (seeded via the
    contents API first — §10c, "repo is empty" 422 on a bare `gh repo create`). FULL release
    `v1.0.0-beta.1` (so `releases/latest` resolves) = `hogwarts_legacy_hebrew.zip`
    **1,717,625 B, sha `bbec15d2eb87d8c272e015a4e1610af2f47f04353c5ab79875a09378f53f9020`**
    + `manifest.json`. (A first pass shipped BOTH arAE+enUS at 3,692,941 B/sha `a59718de…` —
    superseded within the same session by the user's "English only" correction; clobbered in
    place under the SAME tag, per the standing re-release rule.)
  - **Worker** — slug `hogwarts-legacy-hebrew` added to `games/steam/steam_mod_worker/src/
    index.js` `REPOS` + `npx wrangler deploy`. Verified live: `/hogwarts-legacy-hebrew/manifest`
    → the sha/version above; `/archive` → 200, Content-Length 1,717,625.
  - **Supabase `games` id=`hogwarts`** (PostgREST PATCH, service key, no browser UA — the
    `sb_secret_…`-format key rejects a browser UA): `version=1.0.0-beta.1`, `status=beta`,
    `availability=available` (was `in-progress`/`locked`), `release_stage=beta`,
    **`price_cents=5300`** (₪53, [[mod-price-53-default]] — no stated exception for this game),
    `download_url`→the GitHub asset, Hebrew `changelog` naming the English-slot activation.
    `mod_version_history` id=26, `is_current=true`, sha/size matching. 4-surface consistency
    verified (Worker manifest sha == mod_version_history sha == the live GitHub asset's
    Content-Length == 1,717,625).
  - **Bundled offline fallback synced**: `translation_manager/games_catalog.py` `CatalogGame
    "hogwarts"` → `availability="available"`, `version="1.0.0-beta.1"`, `price_cents=5300`; the
    static snapshot `games.json` likewise. `py_compile` clean.
  - **Every "Settings → Text Language" ACTIVATION MESSAGE across the stack rewritten to say
    English ONLY** (no more "Arabic also works" — that was true only for the superseded
    both-slots build): `main_eel.py` `_run_hl_install`'s done-toast, `frontend/src/views/
    GameDetailPanel.tsx` `NATIVE_DL_API.hogwarts.note`, `translation_manager/
    hogwarts_legacy_mod.py`'s docstring, `release_files/install.py` + `קרא_אותי.txt`.
    `tsc -b` clean on the frontend edit.
  - **The launcher's install/remove RPC PLUMBING (`get/install/remove_hogwarts_mod`, `_HL_ID=
    "hogwarts"`, `_HL_SLUG="hogwarts-legacy-hebrew"`) already shipped in an EARLIER launcher
    build (2026-07-05, "launcher plumbing READY-and-waiting")** — so an already-installed
    launcher can complete a real end-to-end install right now with NO rebuild; only the cosmetic
    activation-message wording (above) needs a future launcher rebuild to reach existing users.
- **🔬 UE4SS TESTED IN-GAME (2026-08-09) — BOTH Lua fixes WORK, but HL's own anti-mod system
  kills the process, so UE4SS is NOT VIABLE for ongoing use. Removed.** Built + deployed a UE4SS
  Lua mod (`games/hogwarts_legacy/ue4ss_locale_fix/`) that (1) force-reapplies
  `UKismetInternationalizationLibrary::SetCurrentLocale("en-US")` every ~1s via `LoopAsync`
  (a ONE-SHOT `RegisterInitGameStatePostHook` call gets silently overwritten by the game's own
  frontend-level locale re-apply — the persistent-loop form is required) to fix the clock/number
  FORMATTING independent of the active TEXT language, and (2) best-effort hides the main-menu
  news widget via `FindAllOf("UserWidget")` + name-matching + `SetVisibility(1)`. **Both proven
  correct live** (UE4SS.log: `SetCurrentLocale('en-US')` firing every tick;
  `hid news widget: UI_BP_ScrollingTextBlock_C …WidgetTree.scrollingMOTDText` firing every tick).
  **But ~25s after boot, HL's own "تم اكتشاف تعديلات غير رسمية" (Unofficial modifications
  detected) dialog appears** (reacting to the `dwmapi.dll` proxy injection UE4SS itself requires,
  independent of what the Lua does — even an EMPTY UE4SS mod would trigger it), **and the process
  exits cleanly shortly after — no crash dump, no Windows Application-Error event** — consistent
  with a deliberate anti-tamper kill. **We do not pursue bypassing it** (DRM/anti-tamper
  circumvention is out of scope for this project). UE4SS was fully uninstalled from the game
  install (dwmapi.dll/UE4SS.dll/UE4SS-settings.ini/UE4SS.log/Mods/); only the safe text-only
  `.pak` mod ships (see the enUS-slot publish above, which independently fixes the clock/logo
  without any code injection). **Tooling note kept for any future UE4SS work on this or another
  game:** `UE4SS-settings.ini`'s `[EngineVersionOverride]` ships EMPTY by default →
  `[PS] Failed to find EngineVersion` → `Fatal Error: PS scan timed out` (UE4SS never loads at
  all) — set `MajorVersion = 4` / `MinorVersion = 27` (this game's real UE version) to get past
  it. **UNIVERSAL: a working Lua fix does not make a code-injection modding framework SAFE TO
  SHIP — a game's own anti-tamper system can react to the LOADER regardless of what the mod code
  does, and that must be checked live before recommending the framework, not assumed clean just
  because the target is "single-player, no EAC/BattlEye".**
- **✅ Gender source PREPARED — no gender debt (`universal/GENDER_ORACLE_ROLLOUT.md` #3, 2026-07-04).**
  Hogwarts ships an official Arabic locale → the game's OWN Arabic IS the gender oracle (Arabic ≈
  Hebrew: أنتِ/أنتَ = את/אתה). `work/build_gender_source.py` → `extract/gender_source.json` =
  `{string_key:{ar,hint}}` (58,573 rows — EVERY line carries the raw Arabic gender source; 4,691
  auto-hints). Oracle = **`ar_addressee_strict`** (I ADDED it to `universal/gender_oracle.py`):
  pronouns + **vocalized** ـكِ/ـكَ + plural + a **curated 2nd-fem verb whitelist**; deliberately drops
  the generic `ت…ين` heuristic (false-fires on masdar تحسين / plural תنانين / object-suffix تسامحني).
  Also HARDENED the shared parser (masdar `{3,}`, dropped the ي object-suffix branch, fixed the
  ـكَ/ـكِ word-boundary that fired inside الكَلب/ذكَر). **The live `/translate` pool is already
  gender-hinted** — `work/enrich_pool_gender.py` appended `· נמען=נקבה/רבים/זכר` to the `context` of
  the **1,717** high-confidence pool lines (1,605 fem + 69 pl + 43 masc; `context`-only PATCH,
  `current_he` untouched, reconciles vs live on re-run). **⚠️ Player-gender variants** exist
  (`-female`/`-male`, `playerfemale_`/`playermale_` keys, like CP2077). **END-OF-PHASE-2 QA =
  `work/gender_qa.py`** (scan `he_addressee` vs `ar_addressee_strict` → `gender_suspects.jsonl`).
- **Phase 2 next:** (optional) one-line SUB proof (dialogue path); delegate the ~53.8k-string
  translation ([[delegate-all-translation]] — Claude builds tooling + agent handoff, never
  translates), **attaching `gender_source.json` per line** so the Hebrew gender is right from line 1;
  build via `hl_bin.encode` (LOGICAL, strip the section prefix) → `repak pack V11` → `~mods` deploy;
  run `gender_qa.py` as the closing QA; publish like SM2/WD2/Anno (GitHub `hogwarts-legacy-hebrew-mods`
  + Worker slug + Supabase `games` row + `mod_version_history`). Activation = in-game Text Language = Arabic.

---


