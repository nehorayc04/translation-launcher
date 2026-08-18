## Far Cry 5 Hebrew — Phase-1 groundwork DONE, proof DEPLOYED, 🟢 GO with ONE open gate (font) (2026-07-25)

New game at `games/farcry5/` (RECON/FEASIBILITY/PIPELINE + `tools/` + `work/` + `extract/`).
Install `F:\SteamLibrary\steamapps\common\FarCry5` (Steam **552521**), Ubisoft **Dunia/"Fire"**
2018, exe `bin\FarCry5.exe`, engine `bin\FC_m64.dll` (250 MB). `games.id` = **`farcry5`**.
**The menu proof is DEPLOYED and waiting on the user's screenshot.** Memory [[farcry5-groundwork-go]].

- **🔑 THE WHOLE WIN WAS CHECKING THE CONTAINER MAGIC BEFORE SCOPING ANYTHING**
  ([[engine-family-reuse-check-magic]]). `2TAF` + the FC6 header shape ⇒ `games/farcry6/tools/
  fc6_fat.py` **already had a correct `ver == 10` branch and parsed FC5 unchanged**, and the oasis
  then differed by exactly ONE field. Container + codec + deploy were reuse, not re-derivation.
- **Container = Dunia FAT2 v10** (FC6 = v11). Header identical (magic·ver·platform·0·0·count@20·
  entries@24). Entry = 20 B; the delta is the packing: **v10 `off = (e>>29)|(dd<<3)` (BYTE-granular,
  spans 35 bits), `comp = e & 0x1FFFFFFF`** vs v11's extra `<< 4`. **Proof: `max(off+comp)` equals
  the `.dat` size EXACTLY, 0 overflows, on 3 independent archives** (common 182,265,474 /
  patch_english 404,322,380 / farcry5_english 2,217,809,078); v11 overflows 16×, v9 misses. The
  35-bit offset field is *why* an 8.9 GB `patch.dat` is addressable at all. Schemes seen: 0 stored,
  2 LZ4. 42 archives; the ones that matter are `common.fat` (3,401) and **`patch.fat` (63,547,
  which OVERRIDES common)**.
- **🔴 BUG FOUND IN THE FC6 TOOLING: `fc6_crc64.name_hash()` normalizes BACKWARDS.** It does
  `path.lower().replace("\\","/")`; the real Dunia name hash is **CRC64 over lowercase + BACKSLASH
  separators** — only that reproduces FC6's own documented oasis hash `0x14f790b7fb9610c2`.
  Latent-only (FC6's deploy uses a hardcoded constant and nothing else calls it), fixed in
  `games/farcry5/tools/fc5_crc64.py`. **UNIVERSAL: validate a hash function against a KNOWN hash
  from an already-cracked sibling before trusting a "no hits" result — a wrong normalization and a
  genuinely absent file look identical.**
- **Text = TWO oases per language, in BOTH `common.fat` AND `patch.fat`** (patch wins):
  `languages/<lang>/oasisstrings.oasis.bin` (UI) + **`languages/<lang>/oasisstrings_subtitles.oasis.bin`**
  (dialogue — found by suffix-guessing after the first probe returned only UI). **9 text languages
  incl. arabic.** Format = FC6's, except the string record is **12 B `{Id, SectionCRC, EnumCRC}`
  vs FC6's 16 B** (FC5 has no `Extra=0xFFFFFFFF` field) — visible in one 64-byte hexdump.
  `tools/fc5_oasis.py` **identity-rebuilds BYTE-IDENTICAL on all 9 languages** with a hard
  "0 leftover bytes" assert.
- **Scope: 31,664 records · 25,095 unique EN strings · 2,320,899 chars** (UI 18,889 + subtitles
  12,775, **0 key overlap**). Subtitles median 106 ch = real dialogue. **Single pass, no fleet.**
  **100 % key parity across ALL 9 languages ⇒ 8 oracle languages free** (ar/fr/de/it/es/ru/br/ja).
  Tokens: `[STYLE_*]`/`[Quest_*]` 9,004 (1,191 distinct) · `{0}`/`{TX_PCButton_*}` 1,545 · `\n`
  2,338 · `%i/%d/%l/%u` 120 · `<br>`/`<GLITCH>` 109 · `&#xA;` 28. ⚠️ **A content scan finds MORE
  oasis blobs than the 18 named** (52 in common, 172 in patch, 40 per story DLC) — fold them in
  before calling the corpus complete.
- **🟢 Arabic is FIRST-CLASS (gate 0 closed).** The engine enum in `FC_m64.dll` lists 22 languages
  ending `…turkish, arabic, invalid_language`; the DLL exports a dedicated **`IsArabicUILanguage`**
  check (a real Arabic UI path, likely RTL layout); and the UI oasis itself carries the selector
  label `'Arabic'` (`sec=82c1dced id=874045`) plus separate **`'Game language'` / `'Audio Language'`
  / subtitle-language** settings ⇒ the user can pick Arabic in-game and **English VO is preserved
  for free**. Arabic TEXT ships in common/patch (always installed); Arabic audio does not — irrelevant.
- **bidi PREDICTED VISUAL (the proof decides).** The game's own Arabic is stored **LOGICAL** with
  **0 presentation forms and 0 bidi control chars** (463,531 standard-block chars; 4,198 lines end
  with `.!?` vs 10 that start with one) ⇒ the engine shapes AND reorders Arabic itself. That is the
  **AC-Mirage / Witcher-3-4.00 signature**, where the RTL pipeline turned out gated to the ARABIC
  SCRIPT and left Hebrew in storage order — exactly why FC6 ended up VISUAL. [[bidi-is-version-dependent]]
- **🟡 THE ONE OPEN GATE — FONT. FC5 has NO raw TTF anywhere.** sfnt magic (`\x00\x01\x00\x00`/
  `OTTO`/`true`/`ttcf`) searched anywhere in the first 4 KB of **~360,000 entries across 6 archives**
  (patch · common · ige · igepatch · worlds/installpkg · worlds/farcry5), each hit gated on a
  table-directory sanity check + a real fontTools load ⇒ **0 fonts**. `FC_m64.dll` embeds **0** and
  contains **no** `.ttf`/`.otf`/`.ffd`/`.fnt` string. It DOES ship `fire\private\common\src\
  FontDescriptor.cpp`, `DynamicFontContent.cpp`, `CFont`, `CFontBank`, and `.xbt` ×41 (the Dunia
  texture container) ⇒ a proprietary descriptor + glyph atlas. **Strongest lead: Watch Dogs 2 —
  the SAME Ubisoft Dunia lineage — uses `.ffd` metrics + `.xbt` (TBX + DXT5) SDF atlas, already
  solved in this repo at `games/watchdogs2/work/wd2_font.py`.** Arabic renders in-game today, so an
  Arabic-capable font exists; only Hebrew coverage is unknown, and **the proof answers it.**
- **Deploy = append-relocate scheme-0** (`tools/fc5_deploy.py`): append at the `.dat` EOF (original
  bytes never overwritten) + repoint that entry, `.he_backup` + `.he_journal.json` per archive.
  `pack_entry_v10` **self-tested byte-identical against 4,000 real entries**. **Offline-validated on
  a real COPY of common.fat/.dat before touching the game**: exactly 1 entry changed, 16/16 edits
  survive a full write→re-read round-trip, 17,815 strings intact, 600 other resources still
  readable, and revert restores the `.fat` **BYTE-IDENTICALLY** with the `.dat` truncated back.
- **✅ PROOF DEPLOYED to BOTH archives** (`work/build_proof.py --deploy`; verified by reading back
  from disk, 16/16 in each): **CONTINUE = `ZZ-FC5-OK-ZZ`** (Latin marker = MOUNT, font-independent)
  · **NEW GAME `שלום` LOGICAL vs LOAD GAME `םולש` VISUAL** (bidi A/B — exactly one can read as
  שלום) · **OPTIONS `אבגד`** (4 non-confusable letters = direction control) · **QUIT = all 27
  letters** (font coverage) · **SETTINGS/RESUME** = the same punctuation/parens/digits/Latin-island
  sentence in both modes (layout) · the language-menu `Arabic` label → `עברית`.
  **User step: launch → Options → Language = Arabic (العربية) → main menu → screenshot.**
  Revert: `python work/build_proof.py --revert`.
- **⚠️ Two environment traps hit this session:** (a) a bash heredoc **mangles a `\\` escape** inside
  a Python string (`crc64(p.replace('/','\\'))` became an unterminated literal) — write the script
  to a file instead; (b) **`timeout N python script.py | tail` loses ALL output** when the script
  isn't run with `-u` — the kill discards the block buffer and it looks like a clean empty result.
  Always `-u` + redirect to a log for any long scan.

### ✅✅ IN-GAME PROOF CAME BACK — mount CONFIRMED, font is the ONLY gate (2026-07-25, autonomous)

Ran the whole cycle autonomously (`work/fc5_autocheck.py`: set language → launch → wait for the
menu → dxcam grab → close) with the user away from the keyboard. **The main-menu screenshot shows
`ZZ-FC5-OK-ZZ` rendered in the first row** ⇒ the patched oasis MOUNTS and the whole
FAT2-v10 → OASIS → append-relocate chain works end-to-end in the real game. Untouched Arabic
(`آركيد` · `متجر` · `خروج إلى سطح المكتب`) renders perfectly beside it. **Every Hebrew row renders
as tofu boxes — and the BOX COUNT matches the string length exactly (4 boxes for the 4-letter
`אבגד`)**, so the text reaches the renderer and only the glyphs are missing
([[tofu-still-answers-bidi]]). bidi is still undetermined (all-tofu rows carry no letter order).

- **🔑 ACTIVATION IS A PLAIN XML ATTRIBUTE — no menu navigation, ever.**
  `%USERPROFILE%\Documents\My Games\Far Cry 5\gamerprofile.xml` carries `UILanguage`,
  `SubtitlesLanguage`, `LastUPlayLanguage` (and a SEPARATE `SoundProfile Language` for audio),
  indexed by the engine's own enum ⇒ **`UILanguage="22"` = arabic, audio left at 0 = English VO**.
  Verified the game does NOT overwrite it on launch. This is the cleanest activation lever in the
  project alongside Borderless Gaming's JSON key — a `kind:"xmlattr"` `game_language.py` entry.
  ⚠️ **Steam's per-game Language dropdown does NOT list Arabic** and is irrelevant — it only picks
  which audio packs download; the in-game UI language is this XML attribute.
- **🔴🔴 THE LAUNCH TRAP THAT COST THE MOST — a force-killed game leaves Ubisoft Connect holding a
  stale session, and EVERY later launch then exits ~7 s in: silently, with no window, no crash
  dialog, and NO Windows event-log entry.** It reads exactly like "the mod broke the game".
  **Isolation settled it in one step: reverting to PRISTINE archives reproduced the identical
  failure** ⇒ the mod was exonerated and the launcher stack was the culprit. Fix = kill
  `upc.exe`/`UplayWebCore.exe` before each launch (`restart_connect()`); Connect relaunches itself.
  **UNIVERSAL: when a game stops launching mid-session, revert to pristine and try again BEFORE
  debugging your payload — and a clean exit with no event-log entry means the game DECIDED to quit
  (DRM/launcher handshake), it did not crash.**
  ⚠️ Also: `FarCry5.exe` is a **215 KB Steam stub** — launched directly it hands off and exits by
  design, so the process legitimately disappears and reappears under a NEW pid. A wait loop that
  gives up on the first disappearance concludes "the game exited on its own" and is wrong.
- **⚠️ Capture gotchas:** FC5's menu background is ANIMATED, so an "N identical frames" settle
  never fires; and "any non-black frame" grabs the BRIGHT intro logos instead. Match the measured
  **menu signature (mean ≈46, std ≈32)** for N consecutive frames. DXGI duplication is EXCLUSIVE —
  a second dxcam instance fails while the capture loop holds it.
- **🔴 THE FONT GATE IS REAL AND HARD — FC5 contains NO sfnt font ANYWHERE.** Searched the sfnt
  magic **byte-by-byte through the entire decompressed payload** of every entry (not just the first
  4 KB) across `common` · `patch` · `installpkg` · `farcry5` · `ige` · `igepatch` · the language
  packs · the DLCs ≈ **700,000 entries** ⇒ **0 fonts**. `FC_m64.dll` embeds 0 and contains no
  `.ttf`/`.otf`/`.ffd`/`.fnt` string; it ships `fire\private\common\src\FontDescriptor.cpp`,
  `DynamicFontContent.cpp`, `CFont`, `CFontBank`, `.xbt` ×41. Name-guessing 26,620 candidate font
  paths → 0 hits. A codepoint-array content scan found only oases (**the ascending "codepoints"
  were the oasis StringOffsets array, +6 per entry — a textbook false positive**).
  **Next step = the Watch Dogs 2 route** (same Ubisoft "Fire"/Dunia engine, whose font IS `.ffd`
  metrics + `.xbt` TBX/DXT5 SDF atlas, already solved at `games/watchdogs2/work/wd2_font.py`):
  identify the atlas by DECODING `.xbt` textures and looking for a glyph sheet, since neither the
  name nor the sfnt magic can find it.
- **Game left FULLY RESTORED**: archives reverted (scheme back to 2, 0 markers, no `.he_backup`),
  `UILanguage` back to `0` (English).

### ✅✅ FONT GATE CLOSED — the font is a `.ffd`+`.xbt` pair and FFDConverter supports FC5 natively (2026-07-25)

The whole font chain is solved, built, verified offline and **DEPLOYED to all 5 archives**. The only
thing left is one launch (blocked on a Steam sign-in, see below).

- **🔑 THE FIND WAS BY CONTENT, NOT BY NAME — and the signature is reusable.** Name-based and
  sfnt-magic searches were exhausted (0 hits over ~700,000 entries). What worked: decode EVERY
  texture and keep the ones whose **RGB channels are perfectly flat white (`std == 0`) while ALL the
  information sits in ALPHA** — the Watch Dogs 2 atlas signature. Out of 1,979 textures in
  `common.fat` that filter returned exactly **10 glyph atlases** (7×2048×1024 CJK, 2×1024×1024
  = Arabic + Latin/Cyrillic, plus 1024×512 helpers). ⚠️ Getting there needed the `TBX` container
  first: `TBX\0` + a 36-byte header whose **`+8` field IS the offset of the DDS header**.
- **🔑 THE ROUTE FROM AN ATLAS TO ITS OWNER — search for the u64 hash, not for a name.** In Dunia
  every resource points at another by its CRC64 name hash, so the owner of a texture is simply
  whichever resource CONTAINS those 8 bytes. One scan found `cf402ed3ebb8872f` referencing BOTH
  1024×1024 atlases; it decodes as a dependency manifest — `u32 recordCount`, `recordCount ×
  {u32 firstIndex, u32 count, u64 ownerHash}`, `u32 arrayCount`, then the hash array (validated:
  **0 records overflow the array**). All 12 atlases sit in ONE contiguous index block (223-235)
  owned by a single 4,404-byte Scaleform resource.
  ⚠️ The array is length-prefixed by its OWN `u32` right after the record table — being 4 bytes off
  makes every hash "NOT in array", which reads exactly like a wrong theory.
- **🎯 `d27eb425d5b53ec6` = the FONT MAP**, a per-locale table (tag 251 ×3, one per font bank):
  `DIN Mittelschrift LT W1G` · `FCZ Bold` · `FCZ Title`, each mapping every locale to a `.ffd`.
  **All three banks map `arabic` → the SAME single file**
  `UI\Common\fonts\Fire\DIN_Mittelschrift_LT_W1G_Arabic.ffd` (`236295edc3a3045b`) → **one font
  covers the entire hijacked UI.** Its atlas is `..._Arabic_1.xbt` (`4121034366bd73a3`) — the
  page path in the `.fnt` says `.png`, but re-hashing the same stem with `.xbt` matches the
  content-found atlas EXACTLY.
- **🟢 NO reverse-engineering of the `.ffd` was needed — FFDConverter ships FC5 support** (its own
  usage example is literally `-v FC5`). `--ffd2fnt` / `--fnt2ffd` round-trip the metrics as text.
  ⚠️ Its reader **splits on SPACES** (tabs → `FormatException`), and `xadvance` is stored on a
  **1/1.3 px grid** (fitted over all 1,094 glyphs, residual 0.006) whose own 2-decimal export sits
  just under a step — so a naive re-import rounds every wide glyph DOWN by one. Snap to the grid and
  nudge past the boundary → **max metric drift over all 1,094 shipped glyphs = 0.000**.
- **🔴🔴 THE BASE+PATCH TRAP FIRED, EXACTLY AS §8e WARNS.** `common.fat` and `patch.fat` carry
  **DIFFERENT FONTS**: common = 953 glyphs + a BC3 atlas with no mips; **patch = 1,094 glyphs +
  an R8_UNORM (dxgi 61) atlas with an 11-level mip chain** — and patch is the copy the engine wins
  with. A first build made from common's copy verified perfectly and the game would never have read
  it. `pull_font.py` exists solely to pull the winning copy.
- **Injection**: the atlas was FULL (lowest glyph bottom y=1023.9), so it grows **1024×1024 →
  1024×2048** (power of two, like every other atlas the game ships). R8 is uncompressed, so the
  original 1,048,576 bytes of level 0 are spliced in **byte-for-byte** and only the new lower half
  is generated; the mip chain is regenerated (its dimensions necessarily change with the base).
  Both the **SDF encoding** (`alpha = 31.149*d + 98.89`, fitted over 44,980 edge px — very
  different from WD2's `17.29*d + 127.57`, so never reuse another game's constants) and the
  **advance unit** (`K = 1.4336 units/px`, median over the shipped Latin at matched cap height)
  are FITTED from the game's own glyphs. Hebrew body = 25 px = the midpoint of cap 27.5 and
  x-height 21.5 ([[bitmap-font-size-is-engine-side]] — Hebrew is all cap-height, so matching the
  Latin CAP reads oversized beside mostly-lowercase English).
- **VERIFIED IN THE LIVE ARCHIVES** (`verify_deployed.py`, reading back OUT of the game files):
  text 16/16 in common+patch · `.ffd` 1,121 glyphs with **27/27 Hebrew rects** · atlas 1024×2048
  with the **original 1024 rows byte-identical** and 15,514 px of Hebrew ink — in all 5 archives
  (common · patch · installpkg · dlc_mars · dlc_vietnam).
- **⚠️ `revert_all()` must list the DLC archives** — the story DLCs carry their own copy of the
  font, so a revert that only knows the 4 main archives leaves them patched.
- **🔴 THE LAUNCH CHAIN, mapped the hard way (every one of these silently does NOTHING):**
  the Steam appid is **552520** — `552521` is not the game and the protocol no-ops;
  `uplay://launch/...` answers *"We couldn't verify your access to this game"* (ownership is via
  Steam); setting `SteamAppId` + passing `-uplay_steam_mode` ourselves does not skip Steam — the
  215 KB stub bounces through it regardless. **What actually blocks: `FarCry5.exe` re-invokes
  `steam://run/552520//-uplay_steam_mode`, and Steam then BLOCKS on a "run with these options?"
  prompt** (`LaunchApp waiting for user response to ShowGameArgs` in
  `Steam\logs\console_log.txt`). Clicking its blue **Continue** launches the game instantly;
  `fc5_autocheck.dismiss_steam_dialog()` finds that button by its colour (46,121,217) and clicks it.
  **Read `console_log.txt` first whenever a Steam game won't start — it names the blocking state.**
- **⏸ THE ONE HUMAN STEP LEFT: Steam restarted itself mid-session and came back at its
  "Who's playing?" account picker.** Nothing can launch until it is clicked, and a Chromium surface
  ignores BOTH a synthetic click (focus-stealing prevention wins `SetForegroundWindow`, even with
  `AttachThreadInput`) AND a posted `WM_LBUTTONDOWN`. `fc5_autocheck` now detects this and says so
  in one second instead of burning the 400 s launch timeout. **Click the saved Steam account once,
  then `python fc5_autocheck.py shot ../extract/proof2.png` runs the whole cycle unattended.**
- **A vanilla Arabic menu capture is banked** at `extract/vanilla_arabic.png` — the same engine, same
  screen, same scale, so it is the calibrated ruler for judging the Hebrew size
  ([[screenshot-is-a-calibrated-ruler]]).
### ✅✅ HEBREW RENDERS IN-GAME, and the font/size now MATCH FAR CRY 6 (2026-07-25, user-confirmed)

The whole main menu is Hebrew — המשך משחק · משחק חדש · ארקייד · תוספים · אפשרויות · חנות ·
יציאה לשולחן העבודה — in the same face and at the same size as FC6.

- **🔑 bidi = NONE ⇒ STORE VISUAL, and it was settled by MATCHING GLYPHS, not by reading the
  screenshot.** `work/read_glyphs.py` correlates each rendered glyph against the 27 atlas bitmaps
  and prints them in strict LEFT-TO-RIGHT pixel order. Both LOGICAL test strings came back in
  exact STORAGE order (`שלום` → starts ש ends ם; `אבגד` → starts א ends ד) ⇒ the engine does not
  reorder Hebrew (its RTL pipeline is gated to the ARABIC script — the AC-Mirage / Witcher-4.00
  signature, exactly as predicted). **UNIVERSAL: transcribing Hebrew from an image reports READING
  order, not pixel order — the one question a bidi proof asks. Correlate against the atlas instead
  and the answer is data, not judgement** ([[hebrew-screenshot-transcription-trap]]).
- **🔴🔴 THE SPACING BUG — never derive a format's advance unit by comparing to a reference TTF.**
  `calibrate()` originally computed "game units per pixel" as `median(game_latin_advance /
  heebo_latin_advance at matched cap)`. Heebo is WIDER than the game's condensed DIN Mittelschrift,
  so that ratio (1.4336) folded the width difference into the constant and **drew Hebrew at 73% of
  its natural width** — visibly squished, which is what the user spotted against FC6.
  **Fix: recover the unit GEOMETRICALLY from the game's own metrics** — the SDF margin is `A`'s
  `-xoffset` (DIN's A has ~0 left bearing), `ink = rect − 2·margin`, `lsb = xoffset + margin`, and
  for well-behaved letters the bearings are symmetric ⇒ `U = adv / (ink + 2·lsb)`. Measured over 12
  Latin glyphs: **U = 1.978** (cluster 1.94-1.99). With that, Heebo keeps its natural advances,
  which is exactly what FC6 gets by merging Heebo's `hmtx` scaled to the target upem.
- **🔑 SIZE MATCHED TO FC6 VIA THE ARABIC ANCHOR — no guessing, no Latin cap/em assumption.** FC6
  merges Heebo OUTLINES into **Noto Kufi Arabic** (measured `alef = 0.7598 em`) and Heebo-Medium's
  Hebrew body is `0.5850 em`, so FC6 draws **hebrew : arabic-alef = 0.770**. FC5's own alef is
  27.63 atlas px ⇒ Hebrew body **21.3 px** (was a guessed 25). Result: 21.3/27.63 = **0.771**, an
  exact match. **Anchor on the script BOTH games actually render beside the Hebrew (here Arabic —
  both hijack the Arabic slot); anchoring on Latin would have been wrong, because FC6's Latin font
  (TT Commons, cap 0.63 em) is much shorter than its Arabic while FC5's DIN cap 27.5 px ≈ its alef
  27.63 px, so the two anchors disagree by 20%.**
- **The face was already identical** — both games use `Heebo-Medium.ttf` from
  `games/spiderman2/extracted/_heebo/` (FC6 `fc6_font.DONOR`).
- **Judge it OFFLINE first.** `work/preview_menu.py` lays the real menu lines out from the BUILT
  atlas + the new metrics, so a size/spacing change costs a message instead of a game restart
  ([[minimize-game-restarts]]).
- **⚠️ A menu label can live under several ids and the first guess can be the wrong one** — STORE
  kept rendering `متجر` until the key was found by searching the oasis for its Arabic VALUE
  (6 ids carry `متجر`; patch them all).
- **⚠️ `restart_connect()` reported "up after 1s" while Connect never started** — it polled
  `upc.exe` before the killed one had exited, so it saw the dying process. Wait for the old one to
  DISAPPEAR, then launch, then wait for the new one. A false "up" here presents as the game
  silently refusing to launch.

- **Tools** (`games/farcry5/work/`, run with the repo `.venv` python):
  `find_font_refs.py` (u64-hash reference search) · `dump_fontbank.py` + `parse_fontbank.py`
  (the manifest) · `find_atlas_owner.py` (atlas → owning resource) · `dump_fontswf.py` (the locale→
  .ffd map) · `dump_ffd.py` · `pull_font.py` (**pull the WINNING copy**) · `check_font.py` (linkage,
  coverage, free space, SDF profile) · **`fc5_font.py`** (the injector: `Atlas` R8+mips I/O,
  `calibrate()`, build) · `verify_font.py` (offline round-trip + a rendered preview) ·
  `verify_deployed.py` (read-back from the live archives) · `build_proof.py --deploy|--revert`
  (the gate-closing proof) · **`build_menu_he.py --deploy|--revert`** (the real Hebrew menu,
  stored VISUAL) · `read_glyphs.py` (read a screenshot's Hebrew by atlas correlation) ·
  `match_fc6_size.py` (measure FC6's fonts) · `preview_menu.py` (offline menu render) ·
  `upload_images.py` + `publish_catalog.py` (the catalog card) · `build_ct_strings.py` (the pool).

### ✅ LISTED on the site + launcher, and 30,042 lines LIVE on `/translate` (2026-07-25)

DB-only (both surfaces read the `games` row live) — no `vercel --prod`, no launcher rebuild.
Artwork → the public `covers` bucket (cover 600×900 webp · banner ≤1600w webp · logo ≤360w
**contain**-fitted png, never stretched); row `farcry5` = `planned` / `locked` / free /
sort 10009, right after Far Cry 6. ⚠️ **`availability` is ADMIN-OWNED** — the user flipped Far
Cry 6 `in-progress`→`planned` from the admin panel WHILE this was being written, and my write
briefly clobbered it; a publish script must MATCH the sibling and never re-assert that column
on a re-run. (`paused` is also in live use — tsushima/acunity/ac2.) Bundled/offline parity in
the usual trio
(`games_catalog.py` · `games.json` · `game_detector.py`, key == `games.id`; verified
`FarCry5`→`farcry5` against the real install). ⚠️ The `games` row must exist BEFORE the pool
import or the FK rejects the whole batch (hit it, exactly as §17.7 warns).

- **🔴🔴 DEDUP BY ENGLISH IS UNSAFE HERE — and it was MEASURED, not assumed.** 31,664 records /
  25,095 unique EN / 2,300 duplicate-EN groups, and **27% of those groups get DIFFERENT
  translations in the game's OWN professional Arabic AND French (35% in Russian)**. The
  divergence is contextual and real: `US Auto` → `Garage US Auto` on the map but `US Auto` in
  the shop; `Gardenview Packing Facility` → a shortened form where the label is width-limited;
  `Use Medkit` → two lengths. So `string_key` = **`{sectionCRC:08x}:{id}`** — the exact pair
  `fc5_oasis.flat()` returns and `build_menu_he.PLAN` addresses, so an approved export drops
  onto the build with no remapping. **UNIVERSAL: run the dedup-safety measurement against the
  game's own localizations — three independent languages agreeing at ~30% is proof, and a
  dedup would have collapsed a quarter of them onto one wrong Hebrew.**
- **4 Hebrew categories in VISIBILITY order** (verified live, exact counts): **ממשק ותפריטים
  11,433 → משימות ויעדים 1,143 → כתוביות עלילה 12,774 → תיאורים ופריטים 4,692** = 30,042.
  Quest objectives are split by the engine's OWN `[Quest_*]` token, subtitles by the oasis
  FILE; only the short-vs-long UI split is a length heuristic (≤40 stripped chars), which is
  safe because it sub-divides WITHIN one surface instead of routing between UI and subtitles.
- **🔑 Every row carries the game's own ARABIC in `context` (29,185 of 30,042)** —
  [[gender-oracle-from-game-langs]]. FC5's Arabic is stored LOGICAL with **0 presentation
  forms and 0 bidi controls**, so it is readable as-is (no NFKC + per-segment reversal, unlike
  RDR2). **Same-key alignment was PROVEN before trusting it**: EN/AR engine-token multisets
  match on **29,078/29,185 (99.63%)** and the AR/EN length ratio is a tight 0.87 median — i.e.
  the two really are the same line (the GoWR trap, where an id-join was NOT a line-join, does
  not apply). Only **71 auto-hints**: the Arabic is just 21.6% vocalized and has 46 explicit
  2nd-person pronouns, so `ar_addressee_strict` correctly refuses to guess
  ([[gender-hint-needs-closed-set]]) — the RAW sentence is the value, the hint is a bonus.
- **1,622 rows dropped, both classes evidence-based:** 675 `(PH) …` dev placeholders (**the
  pro Arabic leaves 94% of them byte-identical to the English** — that is the signal they are
  not content) + 947 with no real word once tokens are stripped (weapon model codes `M60`,
  `A.J.M.9`, `P226`, icon rows, empties).
- **⚠️ A bracket is a TOKEN only if it has no spaces.** FC5 overloads `[...]`: 7,699 token
  occurrences (`[ACTION_PLANE_SHOOT]`, `[STYLE_ZETA_{0}]`, `[Quest_Generic]`) but also **1,321
  prose occurrences** — stage directions the player reads (`[heavy sigh]`, `[uncontrollable
  laughter]`, `[coughing while getting up in the middle of debris]`). Stripping every bracket
  reports those lines as EMPTY and silently drops them (the AC2 lesson). The token shape must
  allow `{}` too, or `[STYLE_ZETA_{0}]` misclassifies as prose.
- Verified through the PUBLIC API, not the importer's message: `action=games` → total 30,042 /
  open 30,042; `?game=farcry5` → the 4 Hebrew chips with the exact counts (the trigger's Hebrew
  passthrough sets `category` on import — no manual PATCH needed); the first served batch is
  25/25 ממשק ותפריטים. 4 news drafts pushed.


