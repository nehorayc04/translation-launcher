## The Last of Us Part II Remastered Hebrew — Phase-1 COMPLETE (menu-proof PASSED in-game), GO (medium tier) (2026-07-07)

New game scaffolded at `games/tlou2/` (RECON.md / FEASIBILITY.md / PIPELINE.md + `tools/`/`work/`/`extract/`/
`proof/`). **Verdict 🟢 GO — medium tier, deploy EASIER than Part I. ALL GATES CLOSED — in-game menu-proof
PASSED 2026-07-07.** Same Naughty Dog engine + same class as [[tlou1-groundwork-go]] (no Arabic → LTR-slot
hijack + VISUAL + font-replace) — the Part I toolkit ported with near-zero change. The proof confirmed at
once: the mod MOUNTS (CONTINUE→`ZZ-TLOU2-OK-ZZ` shown), **bidi=VISUAL** (LOGICAL `משחק חדש` rendered reversed
`שדח קחשמ`; VISUAL `טען משחק` correct), and the Heebo font renders (no tofu). **🔑 CRITICAL FIX during the proof: `tlou_loc.encode` MUST be SURGICAL.**
In-game, UNCHANGED English strings first rendered scrambled (`Downtown`→`Tntoe`). Root cause: the old `encode`
REBUILT the whole blob (dedup+reorder) → `encode(orig,{})` ≠ orig (blob 813KB→766KB, offsets shifted); our decoder
read it fine (0 mismatches) but the ENGINE relies on the ORIGINAL blob layout (`sid-lookup` references the offsets)
→ read unchanged strings from wrong offsets. Fixed BOTH `games/tlou2/tools/tlou_loc.py` AND `games/tlou1/tools/
tlou_loc.py` (identical codec, same latent bug): keep the original blob byte-identical, only APPEND override values
to the tail — `encode(orig,{})`==orig now. The FONT is perfect (A/B `iso_As`==`iso_Bs` both clean — never the font).
Final in-game screenshot confirmed everything correct together (Downtown clean + our Hebrew right). Memory
[[tlou2-groundwork-go]].

- **Install:** `F:\Games\The Last of Us - Part II Remastered` (Steam appid **2531310**, RUNE crack +
  steam-emu, **DRM-free — no Denuvo/no EAC**). exe `tlou-ii.exe`. Detector key + Supabase `games.id` =
  **`tlou2`** (already a coming-soon card since 2026-07-05). Data in `build\pc\main\*.psarc` (49 archives, ~81 GB).
- **🟢 Container = DSAR → PSARC → pak — CRACKED + pure-Python reader built** (`tools/dsar.py`). Stack:
  **DSAR** (ND "DirectStorage Archive", LZ4-block 256 KB chunks) → **inner PSARC v1.4** (zlib, 64 KB blocks) →
  `.pak`. DSAR entry 32 B LE `<qqiiB7s>` = decompOff·compOff·uSize·cSize·**compType(0=stored,else LZ4)**·7
  reserved (the recurring `03 54 55 55…` "marker" = compType 0x03 + 7 filler — NOT bit-packing). Header:
  `numEntries@8`·`dataStart@0xC`·`u64 innerSize@0x10`, entries at 0x20. Validated end-to-end: reconstructed
  bin.psarc (8005 files) + parsed common (2461) + **core (13,967)**. Cross-checked vs UnPSARC `Decompressor.cs`.
  External tools also exist (**ndarc**, **UnPSARC** open-source C#, **TLOU_PSARC_Tool**, **NaughtyDogLocalizationTool**).
- **🟢 Text = `core.psarc/text2/<lang>.{common,subtitles,subtitles-systemic}` + `sid-lookup`** — **ND loc-v2,
  IDENTICAL to Part I** → Part I's `tools/tlou_loc.py` decodes/encodes all `eng.*` UNCHANGED (roundtrip=True,
  real English decodes clean). SID shared across languages → map/edit by SID; dup values share one offset; grows
  freely (no delta-0 constraint). **Scope (measured, unique):** eng.common **12,781** (UI/menus/accessibility) +
  eng.subtitles **21,266** (story dialogue) + eng.subtitles-systemic **9,739** (barks; 104k records deduped) ≈
  **43,786 translatable**. Tokens: `<font…>…</font>`/`<br>`/`<break/>`/`<hang>`; `|gen:interact|`/`[A]`/`%d`/`{value}`; `\n`.
- **🔴 NO Arabic / NO RTL locale** (26 langs, all LTR/CJK: bra chi chs cze dan dut eng fin fre ger gre hrv hun ita
  jpn kor nor pol por rus **sas**=LATAM-Spanish spa swe th tur uke) → **LTR-slot hijack (English) + VISUAL bake**
  via Part I's `work/tlou_rtl.py` `to_visual` (unchanged, selftest 9/9). bidi expected VISUAL (same engine as Part
  I, which CONFIRMED VISUAL in-game) → menu-proof decides. **False positive:** `*-rtl-only*.pak` = level-lighting
  variants, not right-to-left.
- **🟢 Font = REPLACE with Heebo** — `seriffont-Regular/Medium.otf` are literally **DINPro** (CFF/PostScript, no
  Hebrew/Arabic — identical to Part I) → glyf-inject is a no-op → REPLACE. Built `extract/_he_seriffont-*.otf` from
  **Heebo** (Latin 58/58 + Hebrew 27/27) masquerading as the DINPro `name` (`work/tlou_font.py`, unchanged). All
  fonts loose OTF/TTF (easy class). Part I proved the replace renders in-game.
- **🟢 Deploy = plain PSARC with STORED blocks in `mods\` via ndmodloader — NO core.psarc repack, NO DSAR wrapper
  (PROVEN in-game 2026-07-07; EASIER than Part I).** **⚠️⚠️ THE decisive crack: the mod PSARC's inner blocks MUST be
  STORED (raw), NOT zlib.** `core.psarc` is a DSAR — its LZ4 outer does the compression, so the inner PSARC holds
  every file RAW (`eng.common` block-table = `[0×16, 38282]`, first bytes `c7420000` not `0x78`). If the mod's inner
  blocks are zlib-compressed, the TLOU2R engine MIS-DECODES them and the menu shows **"UNKNOWN STRING!!!"** on every
  line — the override MOUNTS (path/hash correct) but the content is garbage (and it's flaky: sometimes crashes). Fix
  = `tools/psarc_write.py build(files, compress=False)` (STORED, mirrors how core holds the file). A DSAR-wrapped mod
  (`tools/dsar_write.py`) ALSO crashed; **plain STORED PSARC is the ONE working format.** (ndarc research confirmed
  the engine reads plain zlib/oodle/LZ4 too — it is NOT DSAR-only — so the earlier "must ship DSAR" note was wrong;
  the real problem was always the zlib INNER blocks.) ndmodloader auto-loads ALL `.psarc` in `ModFolder` (empty
  `MountOrder` fine) above `core.psarc`; override is by exact internal PATH (`text2/eng.common`, `fonts/seriffont-*`).
  Community text mods (Better-Arabic-Localisation #279 / Indonesian #49) prove the path. **✅ ndmodloader IS installed**
  (user: `winmm.dll` + `modloader.asi` build 1727 in the game root; `modloader.log` shows it mounts `F:/…/mods`; no
  `winmm.dll` crack-conflict — RUNE uses steam-emu). `modloader.ini` fixed (ModFolder→`F:\…/mods`, ShowConsole=true;
  backup `.bak-claude`). The earlier "עדיין אנגלית" = ndml not yet installed; then DSAR + zlib-plain crashed until the
  STORED fix. Activation = Options → Language → Text+Subtitles = **English**. **Plan B (if a loader-free path is ever
  needed) = direct core.psarc repack** (like Part I; heavier — surgical inner rebuild, STORED).
- **✅ Menu proof PASSED in-game** (`work/build_menu_proof.py` now builds plain STORED; `--deploy`/`--revert`): 6 SIDs
  (CONTINUE→`ZZ-TLOU2-OK-ZZ`, NEW GAME/options→LOGICAL, LOAD GAME/Settings/Extras→VISUAL) + Heebo. Diagnosis tool
  `work/build_isolation.py` (`build`; `set A|As|C|Cs|full|fulls`) split the mod into zlib vs STORED × content pieces
  and proved STORED (`iso_fulls`) works while zlib (`iso_A`) → "UNKNOWN STRING"/crash. **Reader/writer `psarc_write`
  gained `compress=` (default True; the mod path uses False=STORED).**
- **Gender (Phase-2, per universal/GENDER_ORACLE_ROLLOUT.md — build NO gender debt):** no Arabic → derive gender
  from the game's own gendered locs joined on SID via `dsar`+`tlou_loc`: `text2/rus.subtitles` (addressee/speaker,
  past -л/-ла) + `text2/spa`/`fre`.subtitles (referent -o/-a). Attach RU/ES beside EN in the Phase-2 handoff → correct
  gender from line 1; `gender_oracle scan` as closing QA.
- **Tooling built (`games/tlou2/`):** `tools/dsar.py` (reader — `info`/`list`/`extract`, validated) · `tools/psarc_write.py`
  (override builder, `build(files, compress=False)`=STORED — the mod path — / `verify`/`selftest`, round-trip OK) ·
  **`tools/tlou_loc.py` (SURGICAL encode — see the critical fix above)** · `work/tlou_rtl.py` · `work/tlou_font.py` ·
  `work/build_menu_proof.py` (builds plain STORED) · `work/build_isolation.py` (A/B diagnosis). Run with the repo
  `.venv` python (fontTools+lz4). Deploy env overrides `TLOU2_GAME`/`TLOU2_MODS`.
- **✅ Phase 2 KICKED OFF (2026-07-07) — proof CONFIRMED in-game ("עובד"), all local tooling built + community pool LIVE:**
  - **Community `/translate` pool UPLOADED** (user-authorized): `work/build_ct_strings.py` (models tlou1) →
    `extract/ct_upload.json` (**42,246 unique**, dedup-by-EN; 3 Hebrew cats: ממשק ותפריטים 12,341 · כתוביות עלילה 21,206 ·
    דיבורי רקע 8,699; **5,360 with a gender hint** in `context`) → `universal/community_translate.py import tlou2`. Live:
    stats total 42,246 / open 42,246. **The 3 Hebrew categories were INVISIBLE on the site until 2026-07-07** — see §17.5b: `ts_category_for` bucketed Hebrew to `other`, the API hardcoded the 4 English category keys, and the `sections` distinct was 1000-row capped. All three fixed (DB live + indexed; the API half needs a user-run `vercel --prod`).
  - **Gender source** (no Arabic → the game's OWN gendered locs): extracted rus/spa/fre × 3 → `extract/lang/`;
    `build_ct_strings` joins by SID via `gender_oracle.{ru_addressee,ru_speaker,es_referent}` → `agent_handoff/gender_source.json`.
  - **Agent handoff READY** `games/tlou2/agent_handoff/` (copied from tlou1 — same codec/tokens): `get_batch.py` (joins
    gender per line), `merge_batch.py`+`_tokens.py` (anti-cheat), `qa_scan.py`, `INSTRUCTIONS.md` (Part II glossary +
    gender-from-RU rule). [[delegate-all-translation]] — Claude never translates. Loop + anti-cheat verified.
  - **`work/build_mod.py` BUILT + validated** — reads `agent_handoff/hebrew.json` {md5(EN):LOGICAL}, maps back to EVERY
    SID with that EN, `to_visual` (VISUAL bake) + surgical `tlou_loc.encode` all 3 loc files + 2 Heebo fonts,
    `psarc_write`(STORED) → `mods\zzz-hebrew.psarc`. `--deploy`/`--revert`/`--logical`. Font-only smoke round-trips;
    override unit-test proven.
  - **`work/gender_qa.py`** (from tlou1; FIXED a latent `f"{sid:016x}"`-on-hex-string bug in BOTH games) → `gender_suspects.jsonl`.
  - **`pack_and_release.py` + `release_files/{install.py, קרא_אותי.txt}`** (clone GoWR single-artifact; additive `mods\`
    drop, `--revert` deletes; REPO `hebrew-translation-hub/tlou2-hebrew-mods`). `--pack-only` verified.
- **NEXT (gated — needs the ~42.2k translation done + explicit "פרסם"):** Google agents run the handoff loop → `qa_scan`/
  `gender_qa` → `build_mod.py --deploy` → publish: `gh repo create hebrew-translation-hub/tlou2-hebrew-mods --private`; add slug
  `tlou2-hebrew` to the Worker `REPOS` (`games/steam/steam_mod_worker/src/index.js`) + `wrangler deploy`; `pack_and_release.py`;
  `publish_version.py tlou2 1.0.0 --stage beta --sha … --size … --archive-url … --apply` (flips the live `games` row
  coming-soon→available); optional launcher `translation_manager/tlou2_mod.py` (additive drop/delete applier).

---


## The Last of Us Part I Hebrew — Phase-1 COMPLETE (proof PASSED), GO (medium tier) (2026-07-06)

New game scaffolded at `games/tlou1/` (RECON.md / FEASIBILITY.md / PIPELINE.md + `tools/` + `work/` +
`extract/` + `proof/`). **Verdict 🟢 GO — ALL GATES CLOSED (in-game menu proof PASSED 2026-07-06).**
"LTR-hijack + VISUAL + font-replace" class (like AC2/Anno/GTA/Witcher-menu — NOT the free-bidi
Arabic-slot class). Container + text codec built in pure Python and roundtrip-verified. ONE user
screenshot closed both remaining gates at once: **bidi = VISUAL** (NEW GAME stored LOGICAL rendered
reversed `שדח קחשמ`; LOAD GAME/EXTRAS stored VISUAL rendered correct) and **font renders** (no tofu),
while the `ZZ-TLOU-OK-ZZ` marker confirmed the **PSARC repack loads**. Now in Phase 2 (Heebo font +
delegate translation). Memory [[tlou1-groundwork-go]].

- **Install:** `D:\Games\The Last of Us - Part I` (FitGirl repack, cracked — `steam_api64.rne` +
  `steam_emu.ini`, Denuvo removed). Engine = **Naughty Dog proprietary** (TLOU2 / Uncharted-LoT PC
  lineage). exe `tlou-i.exe`; ships `oo2core_9_win64.dll` (Oodle 2.9) + `bink2w64.dll`. Steam appid
  **1888930** (NOT `2531310` = TLOU Part II Remastered, which later got Arabic — do not conflate).
  Detector key + Supabase `games.id` = **`tlou1`** (already a coming-soon/locked catalog row).
- **🟢 Container = PSARC v1.4 Oodle — CRACKED, pure-Python reader built** (`tools/psarc.py` +
  `tools/oodle.py`; the game ships its own Oodle DLL, no borrowing). header 32B (u32 BE) + TOC entry 30B
  (`16 md5(path) + u32 blockStart + u40 origSize + u40 offset`) + block-table u16 BE (0=full raw block);
  manifest (entry 0) NUL-separated. **⚠️ THE bug that cost the most: TOC entries are ordered by
  `md5(path)` ASCENDING, NOT manifest order** — a naive positional `manifest[i]→entry[i+1]` map resolves
  a `text2/*` path to a random `sfx1` audio entry (the "XVAG audio" red herring that nearly derailed
  recon). Map by `entry.name_hash == md5(path).digest()`. External repackers also exist (**ndarc**,
  UnPSARC, TLOU_PSARC_Tool, NaughtyDogLocalizationTool).
- **🟢 Text = `core.psarc/text2/<lang>.{common,subtitles,subtitles-systemic}` + `sid-lookup`** (26 LTR
  language codes). ND **loc "version 2"** (LE): `u32 count; count×{u64 SID, u64 offset}; UTF-8
  NUL-terminated blob (blob_start = 4 + count*16)`. Codec `tools/tlou_loc.py` (decode+encode,
  **roundtrip-verified**; real English decodes cleanly). **SID identical across languages → map EN→HE by
  SID, edit in place** (never invent IDs). Encoding UTF-8 → Hebrew stores directly; duplicate values share
  one offset. **No gender split** (one string per SID → no femaleVariant/maleVariant backfill trap, unlike
  CP2077). loc can grow freely (self-describing offsets, no downstream stream → **no delta-0 padding**).
  - **Scope (measured, unique):** `eng.common` 13,049 (UI/HUD/menus/accessibility) + `eng.subtitles`
    10,970 (story dialogue) + `eng.subtitles-systemic` 9,814 (barks) ≈ **33,800 translatable**.
  - **Tokens (preserve verbatim):** MARKUP `<font …>…</font>`/`<br>`/`<break/>`/`<hang>`; ISLAND glyph/var
    `|gen:interact|`/`|menu:select|`/`|l3|`/`|@01|`/`[A]`/`[TEXT]`; literal `\n`.
- **🔴 NO Arabic / NO RTL locale at all** (25-language table, all LTR: Latin/Cyrillic/Greek/CJK/Thai) →
  **LTR-slot hijack + VISUAL bake.** Engine does **NO bidi / NO shaping** (draws raw byte order, honors
  literal line breaks) → store Hebrew **VISUAL (pre-reversed)** via `work/tlou_rtl.py` `to_visual` (Hebrew
  runs reversed, Latin/number/token islands kept forward, brackets mirrored, markup **pairs kept LOGICAL**
  so `<open>…</open>` still wraps the reversed text, split on `\n`; **9/9 selftest**). **✅ CONFIRMED
  VISUAL in-game 2026-07-06** — the proof's LOGICAL items rendered reversed, the VISUAL items correct.
  Slot hijacked = **English** (simplest activation).
- **🟡 Font: NO shipped face has Hebrew** (cmap-verified 0/26 in U+05D0–05EA across all 16 faces).
  `DINPro-Regular/Medium.otf` = main UI (FF DIN grotesque), but **CFF/PostScript** → Anno-style
  glyf-injection is a no-op → **REPLACE** with a Latin+Hebrew face (`work/tlou_font.py`, loose OTF/TTF, no
  atlas, **no byte-length constraint**). **✅ Replace mechanism PROVEN in-game (no tofu).** **DECISION
  (user 2026-07-06): Heebo** (Latin+Hebrew, closest to the DINPro grotesque; static faces in
  `games/spiderman2/extracted/_heebo/` + Heebo-Regular). The proof's temporary Arial confirmed the path;
  Heebo is the shipping face.
- **⚠️ Deploy = PSARC REPACK (loose-file override does NOT work here — CONFIRMED 2026-07-06):** dropping
  the modified `text2/*`+`fonts/*` loose into `build\pc\main\` was IGNORED; the engine reads only
  `core.psarc`. Built a pure-Python **surgical PSARC writer `tools/psarc_write.py`**: stream-copies the
  ~14k unchanged entries verbatim + recompresses only our files, rebuilds TOC/block-table/offsets.
  Validated (identity round-trips content-identical on steam.psarc + the 4,821-file bin.psarc; a replace
  keeps every other file byte-identical) AND proven in-game (the proof repack loaded). `build_menu_proof.py
  --deploy` backs up `core.psarc → core.psarc.he_backup` then repacks; `--revert` restores. **Game must be
  CLOSED — it locks core.psarc, and taskkill is denied, so the USER closes it.** **No Denuvo / no EAC / no
  anti-cheat** (single-player; PSARC has no whole-archive checksum, name-hashes are md5(PATH) → content
  edits load; Arabic/Japanese fan-translations precedent). Activation = Options → Language → **Text +
  Subtitles = English** (the hijacked slot), Speech = English.
- **✅ Menu proof PASSED (user-confirmed in-game 2026-07-06)** (`work/build_menu_proof.py --deploy` /
  `--revert`): patched 6 main-menu SIDs — CONTINUE→`ZZ-TLOU-OK-ZZ` (proved the repack loads), NEW GAME/
  Options→LOGICAL, LOAD GAME/SETTINGS/EXTRAS→VISUAL — + swapped DINPro to a Hebrew font. Result: VISUAL
  correct, LOGICAL reversed, zero tofu → **bidi=VISUAL + font-works + repack-loads confirmed together.**
  Phase 2 (IN PROGRESS) = swap font to Heebo → delegate the ~33.8k-string translation
  ([[delegate-all-translation]]) → build via `tlou_loc.encode` + `tlou_rtl.to_visual` + Heebo → repack via
  `psarc_write` → publish like SM2/WD2/GoWR (GitHub `tlou1-hebrew-mods` + Worker slug `tlou1-hebrew` +
  Supabase `games`/`mod_version_history` + optional launcher applier `tlou1_mod.py`).
- **✅ Community `/translate` pool LIVE (2026-07-07):** all clean lines uploaded via
  `work/build_ct_strings.py` (dedup-by-EN + `is_translatable` filter) → `extract/ct_upload.json`
  (categorized) → `universal/community_translate.py import tlou1`. **32,881 unique rows** in **3 Hebrew
  categories**: ממשק ותפריטים 12,585 · כתוביות עלילה 10,926 · דיבורי רקע 9,370, all `current_he=''`
  (fresh). `string_key` = the md5(EN) key (== `to_translate.json` keys) so an approved export maps
  straight into `build_mod.py`. **3,623 rows carry a gender hint in `context`** (`מגדר: נמען=רבים…`,
  derived from the game's own RU/ES). Verified live: `/api/translate?action=games` → tlou1 total 32,881 /
  untranslated_open 32,881. The `games` row id=`tlou1` already existed (availability planned, locked,
  show_on_website=true). **⚠️ The import wrote `category='other'` on ALL 32,881 rows** (Hebrew `section`
  is NOT auto-mapped — see §17.5b) → the site showed ONE hidden `other` chip; fixed by a chunked PATCH
  `category := section` (16 md5-prefix buckets; a single bulk PATCH 500s). Live now:
  ממשק ותפריטים 12,585 · כתוביות עלילה 10,926 · דיבורי רקע 9,370.
  **Handoff serves by VISIBILITY** ([[community-pool-by-category]]): `build_ct_strings.py` also emits
  `agent_handoff/categories.json`, `get_batch.py` sorts by `CAT_ORDER` (ממשק→כתוביות→רקע) and puts `cat`
  on every row as a register hint (verified: first batch = 250/250 ממשק ותפריטים).
- **🔑 Gender oracle (no Arabic → the game's OWN gendered locales, [[gender-oracle-from-game-langs]] /
  `universal/GENDER_ORACLE_ROLLOUT.md`):** English drops gender → the Phase-2 handoff attaches to EVERY
  line the parallel **Russian** (`text2/rus.*` — addressee/speaker via past `-л`/`-ла` + short adjectives)
  + **Spanish/French** (referent, `listo`/`lista`) text as the gender source (`build_ct_strings.py` →
  `agent_handoff/gender_source.json`, join by SID — perfect 13,672=13,672; 3,623 of 32,881 get an
  auto-derived hint like `נמען=רבים`, ALL get the raw text so the translator reads gender instead of
  guessing). Parsers `ru_addressee`/`ru_speaker`/`es_referent` added to `universal/gender_oracle.py`
  (my 8/8 selftest; fixed a `-л` exclusion bug that killed common verb endings вернул/видел/говорил).
  QA = `work/gender_qa.py` (Russian-vs-Hebrew addressee mismatch → `gender_suspects.jsonl`).
  **Dedup-by-EN measured gender-SAFE** (of 6,376 duplicate ENs only ~6 conflict, all parser noise → no
  split needed). 18 gendered-lang loc files cached in `extract/lang/`.
- **Tooling built (all self-tested, `games/tlou1/`):** `tools/oodle.py` · `tools/psarc.py`
  (`info`/`list`/`extract`) · **`tools/psarc_write.py` (surgical repack — identity+replace round-trips +
  proven in-game)** · `tools/tlou_loc.py` (`decode`/`dump`/`stats`) · `work/tlou_rtl.py`
  (`to_visual`) · `work/tlou_font.py` (`check`/`make`) · `work/build_menu_proof.py`. Run with the repo
  `.venv` python (fontTools needed for `tlou_font`). Deploy target env override `TLOU_MAIN`.

---


## The Last of Us Part II added to site + launcher (DB-only, NO rebuild) (2026-07-05)

User: add The Last of Us Part II to the website AND the launcher WITHOUT a new launcher version/deploy.
Done purely via the live Supabase `games` row + image uploads (both the website `/api/games` and the
launcher's `_try_supabase_catalog` read `games` with `select=*` LIVE, so a new row shows on both with
zero rebuild).

- **Images** (3 PNGs from Downloads) processed to sibling-matching targets + uploaded to the public
  `covers` bucket: cover `af8a70e5…`→`covers/tlou2.webp` (300x450 RGB webp q82), banner `a23156ab…`
  (Ellie+guitar forest scene)→`covers/banners/tlou2.webp` (1600x517 webp q82), logo `edd407e7…`
  (white wordmark, 56.6% transparent)→`covers/logos/tlou2.png` (360x138 RGBA). All HEAD 200.
- **Supabase `games` row** id=`tlou2` (mirrors `tlou1`): title_en "The Last of Us Part II", title_he
  "דה לאסט אוף אס · חלק II", availability `coming-soon`, status `locked`, price 0, release_stage stable,
  show_on_website+show_on_launcher true, sort_order 27 (adjacent to tlou1), cover/banner/logo URLs.
  Verified live: anon REST (launcher path) + `hebrew-translation-hub.com/api/games` both return tlou2.
- **Offline/bundled parity** (future builds / cold-boot; NOT shipped): added a `tlou2` CatalogGame to
  `translation_manager/games_catalog.py` + a `tlou2` entry to `games.json` (both `coming-soon`,
  mirror tlou1). NO `game_detector.py` pattern + NO applier (no translation/mod yet - it's a catalog
  card until a mod exists, like witcher3/hogwarts before wiring). 1 news draft pushed.


