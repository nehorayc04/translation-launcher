## Skyrim SE / Anniversary Edition Hebrew — ✅✅ PHASE 1 COMPLETE, every gate closed IN-GAME, 🟢🟢 GO (easiest tier) (2026-07-26)

New game at `games/skyrim/` (RECON/FEASIBILITY/PIPELINE + `tools/` + `work/` + `extract/`).
Install `D:\Games\TES - Skyrim - Anniversary Edition` (Steam **489830**, CODEX crack), engine
= Bethesda **Creation Engine**, exe `SkyrimSE.exe`. `games.id` = **`skyrim`**. **All four gates
(mount · bidi · font · layout) were closed by ONE autonomously-captured main-menu screenshot** —
the game was launched, captured and closed without the user (`work/autocheck.py`). Memory
[[skyrim-groundwork-go]].

- **🔑 THE FINDING THAT REMOVES THE BIGGEST RISK: Skyrim SE stores strings as UTF-8**, not the
  per-language ANSI codepage the ORIGINAL Skyrim (LE) used (en=1252 · ru=1251 · pl=1250 · ja=932).
  Proven straight from the shipped bytes — `skyrim_russian.strings` id 1 is `\xd0\x9a\xd1\x80…`
  (UTF-8 Cyrillic), japanese is UTF-8, polish `Sk\xc5\x82adowisko`. ⇒ **Hebrew is written
  verbatim; there is no cp1255 problem and no LE tooling may be reused.**
  **UNIVERSAL: when a series has an "old" and a "remaster" edition, re-verify the text ENCODING
  from the bytes — a remaster silently switching codepage→UTF-8 is the difference between
  "impossible" and "trivial", and every community doc still describes the old behaviour.**
- **Container = BSA v105 — read-only reader built + validated on all 91 archives**
  (`tools/bsa.py`): folder record `<QIIQ>` for v105 (v10x is `<QII>`), the folder `offset`
  **includes `totalFileNameLength`**, file-size **bit 30 TOGGLES** compression against the
  archive default, v105 = **LZ4 frame** (v104 = zlib). `Skyrim - Interface.bsa` is `flags=0x3`
  = uncompressed, so the one archive that matters needs no codec at all.
- **🟢 NO REPACK IS EVER NEEDED — deploy is 5 LOOSE FILES.** Loose files under `Data\` override
  the BSAs in SSE, so nothing inside an archive is opened for writing: `Data\Interface\
  {fonts_en.swf,fonts_console.swf,gfxfontlib.swf,translate_english.txt}` + `Data\Strings\
  skyrim_english.STRINGS`. No admin, no archive-invalidation, and **Steam "verify files" cannot
  revert it** (the BSAs are byte-untouched). Revert = delete (`build_proof.py --revert`).
- **TWO text surfaces, and the menu is NOT in the string tables.** `strings/<plugin>_english.
  {STRINGS,DLSTRINGS,ILSTRINGS}` = game content (99,229 records); `interface/translate_english.txt`
  = UI chrome (649 entries, UTF-16LE + BOM, CRLF, `$key<TAB>value`). The main menu / settings /
  HUD labels live ONLY in the second one — patching the string tables alone leaves the whole
  menu English. Both codecs (`tools/strings.py`, `tools/translate_txt.py`) **round-trip
  BYTE-IDENTICAL** (5/5 tables incl. the 34,427-entry `skyrim_english.ilstrings`).
- **Scope = 99,229 records / 78,042 GLOBAL unique / 7.16M chars** across **79 plugins**
  (skyrim 67,414 · dragonborn 11,070 · dawnguard 8,182 · hearthfires 2,273 · update 1,393 + the
  64 Creation-Club plugins) — a FLEET job, comparable to Witcher 3. By kind: `.STRINGS` 32,226
  unique (names/UI) · `.ILSTRINGS` 41,166 (dialogue/subtitles) · `.DLSTRINGS` 4,960 (books,
  **max 40,131 chars**). Tokens: `\r\n` 34,073 · `<...>` 8,801 (`<Alias=City>` `<mag>` `<dur>`
  `<br>` `<font face='$HandwrittenFont'>` `<p align="center">`) · `[...]` 1,946 (`[Activate]`
  control-name substitutions) · `%d/%s/%i` 42.
- **🔑 THE GENDER ORACLE IS FREE AND UNUSUALLY RICH — 7 languages at 100% key parity.**
  fr/de/it/es/pl all 99,305 rows at **100.0%** parity with English, ru 99,304 at **100.0%**,
  ja 89,870 at 90.6%. **Russian + Polish give SPEAKER *and* ADDRESSEE gender** (past tense
  -л/-ла, -łem/-łam) — exactly what English drops — with fr/es/it for referent gender and de for
  register. Dumped per language to `extract/langs/*.json`, same `plugin|id|kind` key. Phase 2
  must attach them per line so the Hebrew is gendered from line 1 (no-Arabic scenario of
  `universal/GENDER_ORACLE_ROLLOUT.md`).
- **🔴 NO Arabic locale** (english/french/german/italian/spanish/polish/russian/japanese, all
  LTR) → **English-slot hijack**, which costs the user **zero actions** (`Skyrim.INI`
  `[General] sLanguage=ENGLISH` is already the default).
- **✅ bidi = VISUAL, settled by an A/B PAIR on the live main menu.** The same word was stored
  both ways on adjacent rows; exactly one can read correctly: `שלום` (VISUAL) rendered
  CORRECTLY, `םולש` (LOGICAL) rendered reversed, and the `אבגד`/`דגבא` control pair agreed.
  ⇒ Scaleform GFx 4.0 does NO bidi → **store VISUAL** (`tools/skyrim_rtl.py` runs the REAL UBA
  with `python-bidi`, RTL base, engine tokens stashed as atomic PUA placeholders, `\r\n`
  order-preserving, per-segment edge-whitespace stripped; selftest 6/6 + token/multiset checks).
  Corroborated independently: the community's own **xTranslator ships an "Arabic RTL → LTR
  conversion"** tool for this exact game.
- **✅ FONT: 27/27 in 13 faces, ZERO tofu.** Skyrim's UI fonts are **real SWF DefineFont3** (not
  GFX/CFX) — `fonts_en.swf` (CWS v15, 16 faces), `fonts_console.swf`, `gfxfontlib.swf` — routed
  by `interface/fontconfig.txt` (`$EverywhereFont` → "Futura CondensedLight" etc.). Both the SWF
  container and `swf_font.serialize_definefont3` **round-trip byte-identical on every shipped
  face**, so the 007/Witcher-3 codec transferred unchanged.
  **🔴 The faces carry ALL-ZERO bounds RECTs, so they cannot be measured from their metadata** —
  `tools/shape.py` walks the glyph SHAPE records instead (**parses 2,041/2,041 shipped glyphs**)
  and that is what produced the real numbers: cap 15,440 and **H aspect 0.415** for
  Futura CondensedLight (extremely condensed) vs ~0.75 for every Hebrew font. So
  `skyrim_font.plan_face()` derives per face `body = 0.86 × THAT face's own cap` and a
  horizontal condensation pulled toward that face's own H aspect but **floored at 0.72** so the
  letterforms never collapse. Donors: **Heebo** Light/Regular/Medium (geometric UI, matches
  Futura), **Frank Ruhl Libre** (`$SkyrimBooks`), **David Libre** (`$HandwrittenFont`).
  Three structural rules the injector enforces, each of which silently corrupts a font if
  missed: **`DefineFontAlignZones` (tag 73) carries exactly 10 bytes per glyph** and must be
  padded in lockstep (verified 206 glyphs → 2,060 B → 236 → 2,360); **the code table must stay
  ASCENDING** (Hebrew U+05D0 lands MID-table, above Latin and below U+2122 — appending would
  break Scaleform's binary search); and **u16 offsets overflow past 0xFFFF**, so the injector
  PROMOTES the font to wide offsets (flag 0x08) rather than corrupt it (fired on ids 3/4/15).
  New glyphs get **empty bounds**, matching all 2,041 shipped ones.
- **🔑 `work/preview.py` renders the injected glyphs OFFLINE to a PNG** (decodes the shapes back
  out of the BUILT swf) so size/weight/letterform are judged in a chat message instead of a game
  launch ([[minimize-game-restarts]]). ⚠️ It initially drew **filled black boxes for ם and ס** —
  a **preview-only** bug (missing EVEN-ODD fill: a counter is a second contour that must
  SUBTRACT), which reads exactly like a broken glyph. **UNIVERSAL: any home-made glyph preview
  must XOR its contours, or every letter with an enclosed counter looks like tofu and you will
  "fix" a font that was never broken.**
- **🤖 AUTONOMOUS in-game verification worked first try** (`work/autocheck.py shot`): forces
  windowed 1280×720 in `SkyrimPrefs.ini`, launches detached with `__COMPAT_LAYER=RUNASINVOKER`,
  finds the window **by PID**, captures with **dxcam** (DX11 flip-model → GDI/ImageGrab returns
  black), then kills the game. ⚠️ **The first capture grabbed the BETHESDA INTRO LOGO** — a
  bright frame that passes every "is it rendering yet" heuristic. Two fixes: write
  `[General] sIntroSequence=` into `Skyrim.INI` (kills the logo outright) **and** refuse any
  frame before a `warmup` deadline. Same trap as FC5; now solved for Creation Engine too.
  ⚠️ `%USERPROFILE%` is redirected in this sandbox → the ini path is resolved via
  **`FOLDERID_Profile`** ([[env-redirection-real-home]]).
- **🟢 DRM/integrity: none.** No Denuvo, no EAC/BattlEye, no content hashing, and the largest
  asset-mod scene in PC gaming — the "do modified files load" question is answered by the
  ecosystem itself.
- **✅ THE LAUNCHER (`SkyrimSELauncher.exe`) IS A THIRD SURFACE — also cracked, translated and
  verified (2026-07-26).** It keeps 100 % of its text in PE resources: **576 RT_STRINGs in nine
  1000-wide ID blocks** (10xxx EN · 11 FR · 12 IT · 13 DE · 14 ES · 15 PL · 16 RU · 17 zh-TW ·
  18 JA — the block is picked at runtime from `sLanguage`, so hijacking the ENGLISH block again
  costs zero user actions) **plus 72 pre-rendered 275×50 menu BITMAPS** (PLAY/OPTIONS/SUPPORT/
  EXIT × 9 languages × 2 states). `tools/launcher_res.py` reads + patches both via
  **`Begin/Update/EndUpdateResource`** (so a replacement may be longer or shorter than the
  original) — **no-op round-trip verified byte-identical on 576 strings + 75 bitmaps**;
  `work/build_launcher_he.py` (`--preview`/`--deploy`/`--verify`/`--revert`/`--measure`) and
  `work/launcher_check.py` (launch → screenshot menu + Options dialog → close).
  **The launcher is 100 % Hebrew** — all 64 English strings + all 8 menu bitmaps. Verified by
  screenshot on three surfaces: the main menu (שחק / אפשרויות / תמיכה / יציאה), the Options
  dialog (כרטיס מסך ורזולוציה · יחס גובה-רוחב · החלקת קצוות · רמת פירוט · נמוכה/בינונית/גבוהה/
  אולטרה · מצב חלון · ללא מסגרת · אישור/ביטול) and the Advanced dialog (איכות צללים · כמות
  דקאלים · השתקפויות מסך · הצללת סביבה · יעדי רינדור 64 סיביות …). Pristine exe at
  `SkyrimSELauncher.exe.he_backup`.
  **Translated by the New-Era method against the panel of the eight languages the launcher already
  ships** (`extract/launcher_panel.json`) — which repeatedly beat the English: "Adapters" is
  Karten / Cartes graphiques / Адаптер = the graphics CARD (→ כרטיס מסך), and "Object Fade" is
  Дальность отрисовки = a draw DISTANCE, not a fade (→ טווח עצמים). **German is the free length
  budget**: if DE fits the control, Hebrew of similar length fits.
  Gated by `build_launcher_he.qa()` (PASS 64/64), which refuses to deploy on a defect: niqqud,
  foreign script, no-Hebrew, still-English, **a dropped LEADING SPACE** (10024 " Samples" /
  10026 " [Letterbox]" are appended to a number — the space is load-bearing), newline-count drift
  (10033 is two lines), a dropped brand (Skyrim Special Edition / FXAA / TAA / SSAO / INI /
  DVD-ROM / setup.exe), a lost NUMBER, and over-budget length vs German.
- **🔴🔴 THE LAUNCHER'S DIALOGS NEED THE **OPPOSITE** BIDI MODE FROM THE GAME — proven, not
  assumed.** The same A/B trick on the Options dialog: `שלום` stored **LOGICAL read CORRECTLY**
  while the VISUAL copy on the adjacent checkbox read reversed ⇒ **Win32/Uniscribe DOES run the
  bidi algorithm** for dialog controls, while Scaleform does none. So one product has THREE
  surfaces with three different answers: **game = VISUAL · launcher dialogs = LOGICAL · launcher
  menu = bitmaps (no bidi at all, we rasterise the pixels)**. The Latin marker `ZZ-SKYL-OK-ZZ`
  rendered, all 27 letters rendered with zero tofu in Windows' own dialog font (**no font work
  on this surface**), and every label sat correctly beside its control.
  **UNIVERSAL: the bidi answer belongs to a RENDERER, not to a product — never carry a game's
  answer into its own launcher/updater/embedded browser; re-prove each surface with its own A/B
  pair. Carrying VISUAL across would have reversed every dialog label, and that failure looks
  like a font bug rather than a storage bug** ([[bidi-per-surface-not-per-product]]).
- **Menu-bitmap rules, all MEASURED off the shipped English (`--measure`):** right-aligned with a
  **29 px right margin**, cap 23-26, ink peak **85 dim / 168 bright** (the two states are exactly
  0.5×), near-black background erased per column. Two bugs worth remembering: **size the Hebrew
  from a FLAT letter (`ה`)** — measuring the whole alphabet inflates the reference by lamed's
  ascender and the final letters' descenders and silently under-sized every word by ~40 % — and
  **align the BASELINE, not the glyph-run bottom**, or any word containing `ק ך ן ף ץ` floats
  upward (the English is ALL-CAPS, so its ink bottom IS the baseline).
- **⚠️ The launcher's manifest demands admin** → a plain `Popen` dies with **WinError 740**;
  launch it with `__COMPAT_LAYER=RUNASINVOKER` for an unattended capture. And **`ImageGrab`
  captures a SCREEN RECT, not a window** — the Options dialog must be brought FOREGROUND first or
  you photograph whatever sits at those coordinates (it grabbed the IDE once).
- **🔴 "No sound device detected. Skyrim Special Edition cannot run." is a LAUNCHER-ONLY check and
  has nothing to do with the mod** (diagnosed 2026-07-26). The string exists **only in
  `SkyrimSELauncher.exe`**, never in `SkyrimSE.exe` — which is why the game itself runs fine. The
  launcher imports `DSOUND.dll` and gates on `DirectSoundEnumerate`; reproducing that exact call
  returned **only "Primary Sound Driver" (NULL guid) = 0 real devices**, and `waveOutGetNumDevs()`
  returned **0**, i.e. Windows genuinely had no playback endpoint (every render endpoint was
  UNPLUGGED/NOT-PRESENT; only a Realtek *microphone* was active). Fix = connect/enable any
  playback device. **UNIVERSAL: when only one of two executables errors, find which binary
  CONTAINS the message and reproduce its exact API call — that turns "the game is broken" into a
  one-line environment fact in minutes.**
- **✅ COMMUNITY `/translate` POOL LIVE — 99,367 rows in 5 Hebrew categories (2026-07-26).**
  `work/build_ct_strings.py` → `extract/ct_upload.json` → `universal/community_translate.py import
  skyrim`. Ordered by VISIBILITY [[community-pool-by-category]]: **ממשק המשגר 63 → ממשק ותפריטים
  646 → שמות ופריטים 48,862 → כתוביות עלילה 44,247 → תיאורים וספרים 5,549.** The categories are
  the engine's OWN surface metadata (the launcher, `translate_english.txt`, and the `.STRINGS` /
  `.ILSTRINGS` / `.DLSTRINGS` file KIND) — never a length heuristic. Only **573 dropped** (no
  letter survives once tokens/digits/punctuation are stripped); a bare proper noun stays, because
  a name passthrough is a TRANSLATOR decision.
- **🔴 NO DEDUP BY ENGLISH — and it was MEASURED, not assumed.** 8,004 duplicate-English groups
  exist, and against the game's OWN professional locales **6.8-18.6 % of them get DIFFERENT
  translations** (pl 18.6 % · ru 14.9 % · fr 8.5 % · de 6.8 %) — e.g. `Reduced Health` is
  predicative in one place and attributive in another. Collapsing them would silently put one
  wrong Hebrew on ~1,200 groups, so the 21 % row redundancy is the cheaper mistake. **Run this
  measurement against the game's own localizations before ever keying a pool by English.**
- **`string_key` carries its TARGET SURFACE** — `"<plugin>|<id>|<kind>"` (string tables) ·
  `"ui:<$key>"` (translate_english.txt) · `"launcher:<id>"` (the exe's RT_STRING). Three build
  surfaces keyed differently, so a bare key could not say where an approved line goes.
  **Verified before importing: all 99,367 keys resolve back onto the real build files with 0
  unresolvable keys and 0 `source_en` mismatches**, and each category is a contiguous
  `order_index` block. The 63 launcher rows arrive with `current_he` filled (improve mode).
- **Gender: `context` carries the game's own RUSSIAN line on 94,376 rows** (100 % key parity;
  Russian past tense marks SPEAKER *and* ADDRESSEE gender, which English drops) plus an
  auto-derived hint on the **10,439** where `gender_oracle.ru_addressee`/`ru_speaker` is
  unambiguous — the raw sentence is the value, the hint is a bonus
  ([[gender-hint-needs-closed-set]]).
  ⚠️ The `games` row `skyrim` ALREADY EXISTED (planned/locked, cover uploaded, sort 2600,
  `show_on_launcher=false`), so the §17.7 FK trap did not fire — check before assuming.
- **STATE: the proof is DEPLOYED** (5 loose files; menu shows the Hebrew A/B). Revert with
  `python games/skyrim/work/build_proof.py --revert`. Display settings were restored to
  fullscreen 1920×1080 after the capture; `Skyrim.INI` keeps the harmless `sIntroSequence=`.
  The launcher is fully translated and deployed (64/64 strings + 8 bitmaps); the gate-proof
  scaffolding strings are NOT shipped (`--deploy --proof` re-adds them). Revert with
  `python games/skyrim/work/build_launcher_he.py --revert`.
- **NEXT (Phase 2, all gates closed):** delegate the 78,042 lines
  ([[delegate-all-translation]], fleet + the 7-language New-Era panel + ru/pl gender) → build
  per-plugin loose `Strings/*` + the UI table through `skyrim_rtl.to_visual` → publish like
  Borderless Gaming / GoWR (a zip of loose files + a self-contained `install.py`) only on an
  explicit "פרסם". **First Phase-2 step: a RULER pass on the BOOK page** — `.DLSTRINGS` run to
  40k chars with `<p align>` markup, and the menu proof only cleared short strings. Note that a
  string too long for its box is **auto-shrunk, not clipped** (seen on the 27-letter line).

- **✅ New-Era 2 corpus PREPARED (2026-08-04) — infrastructure only, NO fleet dispatched** (user:
  "just prepare, I'll say which streams later"). `games/skyrim/fleet/build_multilang.py` is a
  thin adapter for the universal `multilang_review.py` engine ([[new-era-doctrine]],
  `universal/MULTILANG_REVIEW.md`) → `games/skyrim/fleet/review_corpus/{strings,dlstrings,
  ilstrings,ui}.final.jsonl`, **99,876 rows** (strings 48,994 · ilstrings 44,570 · dlstrings 5,665
  · ui 647; the launcher — already 100% — is excluded). **Skyrim has ONE string per (id,lang)**,
  unlike CP2077's femaleVariant/maleVariant pairs, so the engine's automatic gender-split flag
  never fires for it (same as any single-string game); the adapter instead attaches a
  deterministic `gender_hint` per row from the Russian reference via `gender_oracle.
  ru_addressee/ru_speaker` — the same mechanism the `/translate` pool already used. Seeded
  `games/skyrim/fleet/brain_glossary.json` (the New-Era-2 "brain", `universal/brain.py` /
  `universal/BRAIN.md`) with the 6 already-verified-in-game proof terms (Whiterun→וייטראן,
  Dragonborn→בן דרקון, Iron Sword, Lockpick, Gold, Health Potion) + 3 game-scope rules;
  `brain.Brain.for_game()` merges it with the universal layer, verified end-to-end.
  **🔴🔴 Two real bugs found + fixed while building this — the second one already-published:**
  (1) flattening `{plugin:{sid:...}}` into a flat dict keyed by the BARE `sid` silently
  collapsed 48,994→34,855 "strings" rows via **cross-plugin id collisions** (Bethesda string ids
  are small per-plugin sequential integers, so a bare `sid` is NOT globally unique) — fixed by
  keying the flat panel/spine `"<plugin>|<sid>"` while `section` still carries the bare plugin
  name for grouping. **UNIVERSAL: when flattening a nested `{outer_key: {inner_key: ...}}` into
  one flat dict for a downstream tool, the flat key must be the FULL composite — a bare
  inner_key is only safe if you've actually checked it's globally unique.**
  (2) `gender_oracle.ru_addressee`/`ru_speaker` return `"pl"` for plural, not `"p"` — BOTH this
  new adapter's first draft AND the already-shipped `build_ct_strings.py.gender_bits()` mapped
  `{"p": "רבים"}`, so the fallback silently emitted the literal `"נמען=pl"` instead of
  `"נמען=רבים"`. **5,379 already-live `/translate` pool rows carried this in their `context`
  field.** Fixed both call sites, rebuilt `ct_upload.json`, re-imported (idempotent
  upsert-by-string_key — safe to re-run, never wipes contributor claims/approvals), verified
  **0 remaining** via the public API (not the import script's own success message).
  **Nothing dispatched to any fleet/provider — awaiting the user's stream assignment.**

- **🚁 FLEET LATER DISPATCHED + recovered from two silent stalls (2026-08-06).** The New-Era 2
  corpus (99,875 lines) IS running on the full 21-stream fleet (7 machines × groq/sambanova/nim:
  desktop · laptop `10.0.0.49:22` · vm4/vm5 `10.0.0.49:2225-6` · vm/vm2/vm3 local VirtualBox
  `127.0.0.1:2222-4`, all `C:/skyrimw` except laptop). Tasks `SkyrimMP` (5-min relaunch) +
  `SkyrimFleetPull` (5-min merge/heal via `hidden.vbs` — no popup). Two root causes fixed, both
  now durable lessons ([[vm-nat-ipv6-timeout]]):
  1. **vm/vm3 "תקוע" was IPv6, not the provider.** VirtualBox NAT doesn't route IPv6; the
     providers (Cloudflare) resolve to an IPv6 AAAA (`2a06:…`), so every call — incl. groq —
     read-timed-out (`+0/1` on ALL providers) while DNS resolved fine. Fix:
     `Disable-NetAdapterBinding -ComponentID ms_tcpip6` on the guests (no reboot) → python resolves
     IPv4-only. **Confirm at the PYTHON layer** (`socket.getaddrinfo`), NOT `Invoke-WebRequest`
     (.NET Happy-Eyeballs hides it), and **restart the worker** (a pooled v6 connection survives).
  2. **An equal reslice that kept CORPUS ORDER stranded a book cluster at every shard's FRONT →
     the whole fleet crawled at ~0/min although the remainder was 98% plain.** The earliest-
     remaining lines were `<font face='$HandwrittenFont'>` Creation-Club books (heavy `\r\n`) that
     the guard rejects on `newline-count`, and round-robin put them at batches 2-7 of all 21
     shards. **MEASURE the remainder composition** (98% / 36,089 was plain short content, 0.6%
     books) → reslice **EASY-FIRST** (stable sort by a `_hardness()` key before the round-robin).
     Result: **0 → 39 → 108 lines/min, 2 → 7 → 15 of 21 streams producing**, done climbing 63% → 64%.
  Reusable tools now in `games/skyrim/fleet/`: **`reslice_equal.py`** (union banks → remainder →
  easy-first stable sort → equal round-robin into 21 shards; re-runnable) + **`push_shards_restart.py`**
  (scp each `shards/corpus_<machine>_<prov>.json` → the machine's `corpus_<prov>.json`, kill the
  workers [they hold the singleton lock + old shard], ensure IPv6-off on the VMs, relaunch via
  `schtasks /run SkyrimMP`). The reslice is EQUAL by machine×provider (21 ≠ a multiple that zeroes
  the md5%3 split — each worker reads its own `corpus_<prov>.json`, overriding the hash split).

### 🔴🔴 THE SKYRIM TAIL — the guard was INVERTED on 3 classes, and "696 left" was 57 % non-work (2026-08-09)

Skyrim sat at 99.3 % adding **~7 lines/hour**. It was not throttling and not a dead stream: the
tail is **book pages**, and three separate mechanisms made a correct answer impossible.
`games/skyrim/fleet/drain_books.py` (a SEPARATE process — the 3 desktop streams never stop, the
RDR2 `drain_tokenheavy.py` precedent) fixes all of it. Memory
[[guard-accept-set-must-contain-a-correct-answer]].

**FIRST, the remainder was measured, not counted.** Of 696 unbanked lines: **391 have no
translatable letter at all once the engine tokens are stripped** (`<p align='center'>\r\n</p>`,
a page that is a single `<img>`) — they can never satisfy `no-hebrew`, so they were re-served to
a stream on every pass forever. Real work was **~300**. Against the 99,484 genuinely translatable
lines the honest figure was **99.69 %**, not 99.31 %. `empty.json` now carries them and
`reslice_equal.py` + `pull_skyrim.sh` exclude them exactly like `oversized.json`.

**Rejection census from the three worker logs (last 125), which is what named the causes:**
token-mismatch 50 (40 %) · no-hebrew 33 (26 %) · newline-count 23 (18 %, and **19 of 23 were
|Δ|≤2 blank lines on pages with up to 216 of them**) · empty 14 · copy-EN 4 · foreign 1.

**The drain: MASK · SPLIT · ALIGN.**
- **MASK** — every engine token becomes `⟦0⟧ ⟦1⟧` before the call and is restored after; the
  model cannot mangle what it never saw. ⚠️ **`[pagebreak]` is NOT in the worker's `STRUCT`**
  (that regex was measured on the UI corpus, where brackets are prose) yet it occurs **712 times**
  in this tail — so page structure was neither masked NOR checked. It is both, here.
- **SPLIT** — cut on `[pagebreak]`, then paragraph breaks, then single newlines: 190 monsters
  become segments with a **685-char median and a hard 2,500 cap**, translated independently and
  rejoined with the ORIGINAL delimiters (`"".join` is asserted lossless on every line).
- **ALIGN** — if English and Hebrew have the same number of NON-EMPTY lines, the Hebrew is
  rebuilt onto the English's blank-line skeleton. Deterministic, and it kills the 18 %.

**🔴🔴 AN ADVERSARIAL AUDIT (3 attackers + independent refuters, 5.9 M tokens) CONFIRMED THREE
SILENT CORRUPTIONS — outputs that were WRONG and that the guard ACCEPTED. Each was fixed before
a single line was banked; each generalises:**

1. **A LENGTH CAP IN A TOKEN REGEX DISABLES EVERY GUARD BUILT ON IT, ALL IN THE SAME DIRECTION.**
   `<[^<>]{1,80}>` missed **47 `<img src='img://…'>` tags on 26 lines** (81-110 inner chars), so
   `mask()` showed the raw path to the model, the token multiset compared `[] == []`, and
   `is_markup_only()` kept `img/Textures/png/width/height` as "words". On all **24 pure-image
   pages the guard was INVERTED**: the honest echo → `no-hebrew` (rejected), Hebrew that DELETED
   the image → accepted. Fix: bound 80 → **400** (`[^<>]` still cannot cross a tag boundary, so
   it never over-matches). Verified: markup-only 367 → **391**, deleting an image now
   `token-mismatch`, 0 unmaskable tags left.
2. **A FILTER ON WHOLE LINES MUST BE RE-APPLIED TO WHATEVER A SPLITTER CARVES OUT OF THEM.** The
   split re-created the markup-only class one level down: **52 content-free segments on 51 pages**,
   49 of them a bare `[pagebreak]\r\n` from a doubled `[pagebreak]` — *a deliberately blank page*.
   There the echo trips `copy-EN`, so **the only accepted answers were invented Hebrew on a page
   that is empty in English**, and the whole-line gate could not see it (the join is byte-exact,
   the token multiset unchanged, `normalize` even restores the trailing newline: 77 → 77). Fix:
   `is_markup_only` per SEGMENT → echo verbatim, never send (also saves the calls).
3. **EQUAL COUNTS DO NOT IMPLY THE RIGHT MAPPING.** A model that MERGES one pair of lines and
   SPLITS another keeps the content-line count identical, so align's only test passed and it
   re-laid the text onto the wrong lines — **turning a `newline-count` REJECTION into an
   ACCEPTANCE** (737 of 1,096 eligible segments accepted a provably wrong mapping). Fix: after
   rebuilding, require **each line's STRUCT multiset to match the English line it landed on** —
   blank-line drift, the only case the repair exists for, never moves a token off its line.
   Verified both ways: the benign drift is still repaired, the merge+split goes back to rejected.
   Residual, disclosed: pure-prose merge/swap with no tokens stays unguarded.

**🔑 THE REFUTED CLAIM CARRIED THE BEST LESSON.** A 4th finding — "the token check should be
order-strict" — was REFUTED with data: of 99,743 banked lines only 4 have a different token
ORDER, and **all 4 are correct Hebrew** (`<Alias=QuestGiver>'s <BaseName>` → `<BaseName> של
<Alias=QuestGiver>`). The multiset compare is deliberate and load-bearing; an order-strict guard
would reject correct translations. **Always pair an attacker with an independent refuter.**

**⚠️ A single client is GENERATION-bound, so parallelise by PROCESS, partitioned by LINE.** One
drain measured **~2 min/batch → 29 h**. `--slot i/n` runs N processes (each `md5(line)%n`), and
the partition is by **LINE, not segment**, so every segment of a page stays in the process that
must reassemble it. Banks are `out_zzdrain_x<slot>.json` — `zz` sorts last, so the merge in
`pull_skyrim.sh` gives the drain the final word. Run from the WORKER dir (`keys.json` lives
there and never in the repo): `cd C:/skyrimw && SKYRIM_FLEET=<repo fleet> python -u
drain_books.py --apply --slot 0/6`.

**🔴🔴 THE ID THE MODEL ECHOES MUST BE SHORT AND SAFE — a control character in a key reads as a
model dropout.** The segment key is `skyrim:skyrim|1994\x1f3`; `json.dumps` emits that 0x1F as
`\u001f`, and no model reliably echoes it back, so **every id came back unmatched and the batch
scored `+0/N`** — indistinguishable from a rate limit or a real dropout, and it burns a whole
retry pass each time. Send `s0, s1, …` and map back locally: acceptance went **30 % → 57-80 %
with zero "parsed 0" events**. Two supporting rules: call the fleet DIRECTLY rather than through
`chat()` so the RAW reply length is printable (`[raw 173ch parsed 0]` names a truncated or
wrong-shaped answer instantly, which `+0/6` never can), and never put the internal key in the
prompt when a short alias will do — it also stops the ids eating output tokens.

**🔴 SEGMENT SIZE DECIDES WHICH PROVIDERS CAN SERVE THE JOB.** `max_tokens` scales with the
segment, and groq charges the **reservation** against its per-minute budget: at a 2,500-char
segment (~6 k reserved) groq returns 429 and only nim answers, so the whole drain funnels through
one provider at ~15 min/batch. Dropping `SEG_MAX` 2,500 → **900** puts the reservation near 3 k,
the window groq is documented to answer in, and all three providers become usable. It costs
nothing in quality **because the book lines are PARAGRAPHS, not hard wraps — measured: 94 % of
lines over 60 chars end in sentence punctuation** — so a cut on a line boundary never splits a
sentence. Always measure that before shrinking a text segment.

**🔑 A MACHINE'S KEY COUNT IS A HARD CEILING ON HOW MANY CLIENTS IT CAN RUN.** The desktop held
**one key per provider**, so 9 clients (3 workers + 6 drain slots) on 3 keys returned batches with
**zero ids**. The shared pool has 10 keys per provider and the seven machines use one each, so
three per provider were idle — verified by reading **every** SM2 machine's own `keys.json` before
touching anything (`/c/tmp/keyaudit.py`), never by assuming. `games/skyrim/fleet/fleet_providers.py`
gained the RDR2 multi-key rotation (a bare string still works) with cooling keyed on
**(provider, KEY)** — cooling the whole provider on one 429 throws away the other keys, which is
the entire point of having them. Desktop now runs `groqx4 sambanovax4 nimx4`.

**🔴🔴 …AND MORE KEYS DID NOT MEAN MORE CLIENTS — RIGHT-SIZE BY MEASURING, THE CURVE IS STEEP.**
Even on 12 keys, 9 clients produced **HTTP 429 on 5 of 6 drain slots**; the same code at **4
clients** (drains only, workers stood down) measured **9/9 accepted, 0 rate limits**. So a single
machine's share of a free tier supports ~4 concurrent callers regardless of how many keys it
holds — the per-key per-minute limit, not the key count, is the ceiling.
🔑 **The 429s were only VISIBLE after the retry budget was capped.** With the adapter's default
(never fewer attempts than providers/keys) one doomed batch burned 4 × (timeout + 15 s) ≈ 21 min
of silence that reads as a hang; `Fleet.complete(max_attempts=…)` lets a caller that re-serves
its work later fail fast, and the failure reason then appears in the log immediately.
⚠️ Standing the workers down means **`SkyrimMP` + `SkyrimWatchdog` are DISABLED** — the drain is a
strict superset of their remaining work, but **re-enable both when it finishes** or the machine
has no fleet at all.

### 🔁 FLEET HANDOVER — Skyrim ⇒ SM2 New-Era-2 review, built + staged, **MANUAL ONLY** (2026-08-07)

⚠️ **The automatic trigger was built and then REMOVED at the user's instruction: "שלא יהיה
אוטומטי אלא שיגמור את המשחק skyrim בוודאות בלי מעבר למשחק השני לביקורת".** Skyrim must finish
to certainty, and the 21 streams must never move to another game on a script's judgement of
"finished". `pull_skyrim.sh` no longer calls the handover (a comment there says so and says not
to re-add it); **no scheduled task can fire it**; the SM2 tasks stay `Disabled` on all 7
machines. It runs ONLY when a human runs:
`python universal/fleet_handover.py --from skyrim --to spiderman2 --apply`
(no flag = decide + report only, changes nothing).

**A handover is FIVE things, not one, and skipping any of them is a silent regression:**
(1) stop the outgoing game **everywhere** — its workers AND its tasks; (2) deploy the incoming
worker + shards to all 7 machines; (3) enable + start the incoming tasks; (4) repoint
`fleet_config.json` **and** the stream-id registry; (5) start the incoming pull, website pusher
and watchdog. It is ONE-SHOT by construction: `.handover_done` is stamped **before** the first
destructive step, so even a repeated invocation can never run it twice.

**🔑 THE DECISION ITSELF IS THE PART THAT SHOULD NOT BE AUTOMATED.** Everything above is
mechanical and safe to script; "is this game finished?" is not. A threshold on the remaining
count cannot tell a genuine finish from a stalled tail, a mis-scoped corpus, or a parked set
that is still worth another pass — and the cost of being wrong is 21 streams walking away from
a game mid-run. Build the handover so it CAN run unattended, then let a human pull the trigger.

- **🔴 Stopping a game means killing its PUSHER and disabling its WATCHDOG, not just its
  workers.** A retired pusher keeps publishing that game's progress to the public dashboard
  forever, and — far worse — the retired game's watchdog re-enables its own tasks and relaunches
  its workers within 5 minutes, so a handover that only kills processes is quietly UNDONE and
  the two fleets then share one 30-key pool (the documented "more 429s, no other symptom"
  failure). `stop_game()` matches `worker|pusher_match` and disables every `^<Task>` task.
- **🔴 `schtasks /run` on a DISABLED task does nothing and still exits 0.** The incoming tasks
  are deliberately created disabled by `prep_machines.py` (so the next game can be fully staged
  while the current one still owns the keys), so the handover MUST `Enable-ScheduledTask` before
  `/run` — otherwise every step reports success and 21 streams sit idle.
- **🔑 STAGE THE NEXT GAME WHILE THE CURRENT ONE RUNS.** `games/spiderman2/fleet/prep_machines.py`
  creates the dir, writes `run3.bat` (+ the desktop's `launch_workers.vbs`), registers
  `Sm2MP`/`Sm2MPBoot` **disabled**, and `push_shards_restart.py --no-restart` stages the worker
  code + the 21 shards. Verified `--check` on all 7: `dir=1 keys=1 bat=1 worker=1 task=Disabled`.
  Without this the handover's first act is a first-time deploy into a non-existent directory —
  scp fails, the task points at a missing `run3.bat`, and nothing errors anywhere.
- **🔴 `keys.json` is copied from THAT MACHINE'S OWN outgoing worker dir, never pushed from the
  repo.** Each machine holds a different key set and a different rotation offset; one shared
  keys.json collapses 21 streams onto one key and 429s everything.
- **The incoming game gets its own watchdog** (`make_watchdog.py` derives `sm2ne2_watchdog.ps1`
  from the Skyrim one with 12 asserted replacements). Its `$ZOMBIE` list stays a
  never-matching PLACEHOLDER — a janitor may only ever kill ITS OWN workers.
- **State at handoff:** Skyrim 21/21 streams live, SM2 staged + disabled on all 7, the SM2
  NE2 review corpus is 41,309 rows (subtitles 29,415 → dialogue 11,894, all `mode=review`,
  gender_hint on 1,152, 11-language panel), worker guards 15/15.
  Decision check: `python universal/fleet_handover.py` (no flag = decide only).

### ⚖️ SPLIT FLEET — two games at once, 3 streams + 18 (2026-08-08)

Instead of a handover the user split the 21 streams: **Skyrim finishes on the desktop (3
streams, ~914 lines left) while the other six machines run the SM2 New-Era-2 review (18
streams, 41,309 rows)**. Verified live: `Skyrim 3/3 · SM2 18/18 · total 21/21`, and both games
render on the public dashboard.

- **🔑 SPLIT BY MACHINE, NEVER BY PROVIDER WITHIN A MACHINE.** Each box holds its own key set
  and its own rotation offset, so one game per machine means the two fleets can never contend
  for the same keys — the documented "more 429s and no other symptom" failure is impossible by
  construction. Splitting a machine's 3 providers between two games would reintroduce it.
- **🔴 ONE SOURCE OF TRUTH: `games/<game>/fleet/machines.json`.** The reslice, the push, the
  pull, the watchdog and `fleet_config.json` all read it (absent ⇒ all 7, backward-compatible).
  Five scripts each carrying their own machine list is how one of them keeps a retired
  machine — and a WATCHDOG with a stale list is the worst of them: it relaunches its game's
  task wherever it looks, so pointed at a machine that moved it **resurrects the fleet that
  left**, on that machine's keys, silently. Same class as
  [[a-janitor-may-only-kill-its-own-workers]], one level up.
- Retiring a game on a machine = kill its workers **and disable its tasks** there
  (`skyrim killed=3 tasks_disabled=2` × 6); starting the other = **Enable then Run** (a
  `schtasks /run` on a Disabled task does nothing and still exits 0).
- **🔴 A FINISHED GAME'S PROGRESS ROW IS LOCKED, and the lock reads as a broken pusher.** SM2's
  `progress_snapshots` row was `source='manual'` + `show_dashboard=false` (the deliberate freeze
  applied when its previous run ended), so `/api/admin/progress` answered **409 Conflict** to
  every MONITOR_TOKEN push. Unlock with `source='auto', show_dashboard=true, processed=0` before
  a new run on an already-published game.
- **🔴 The NE2 corpus stores every language as a [fv, mv] PAIR, so `he` is a LIST** — the pusher
  inherited from the NE1 era crashed at startup with `TypeError: expected string, got 'list'`,
  and because the pull launches it detached that crash was **completely silent**: fleet running,
  website empty, only a missing process as the clue. `_text()` now accepts both shapes.
  **UNIVERSAL: when a corpus format changes shape, re-run every consumer in the FOREGROUND
  once — a detached crash-on-import is invisible.**
- Dashboard: `fleet_config.games` holds BOTH entries, each with only its own machines; stream
  numbers renamed (never re-allocated) to **skyrim #1-3 · spiderman2 #4-21**, the 30 community
  keys untouched. Verified via an isolated `collector.collect(cfg, remote=None, hist={})`
  (`dash.py --once` blocks on the ssh probes).

- **✅✅ FULL BUILD DEPLOYED LOCALLY (2026-08-11).** The New-Era-2 corpus (`fleet/corpus.json`,
  99,875 rows, built from `fleet/build_multilang.py`'s `review_corpus/*.final.jsonl`) finished the
  fleet at **99,472/99,875 Hebrew (99.6%)** — the 403 unfilled are content-free markup-only
  book-page fragments (`<p align='center'>\r\n</p>`), nothing left to translate. QA-swept clean:
  0 niqqud, 0 foreign-script leaks, 0 leftover long-dashes; the 1,329 no-Hebrew rows are all
  legitimate name/asset-code passthroughs. **New `games/skyrim/work/build_full.py`** merges it into
  the actual game: loads the COMPLETE English base (`extract/langs/english.json`, 99,229 entries /
  79 plugins / 174 (plugin,kind) groups) so every plugin's `.STRINGS`/`.DLSTRINGS`/`.ILSTRINGS` is
  written IN FULL (never a blank id — untranslated ids keep the original English), overrides with
  `skyrim_rtl.to_visual(hebrew)` where translated, and rebuilds the UI table + all 3 font SWFs
  (same donors/body_ratio=0.86 as the accepted Phase-1 proof, which it supersedes). **Deployed to
  the live game as 178 loose files** (`D:\Games\TES - Skyrim - Anniversary Edition\Data\`) —
  nothing inside a `.bsa` touched. Verified by reading back OFF DISK (never trust the builder):
  178/178 present, sample plugins 100% Hebrew, `$CONTINUE`/`$NEW`/`$LOAD` correctly VISUAL-stored,
  all 13 font faces 27/27 Hebrew. Manifest `work/_full_deployed.json` drives `--revert`.
  **LOCAL ONLY — NOT published** (no GitHub release, Worker manifest, or Supabase `games` row
  change); publish only on an explicit "פרסם".


