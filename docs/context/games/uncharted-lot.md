## UNCHARTED: Legacy of Thieves Collection Hebrew — Phase-1 groundwork DONE, 🟢 GO (easy/medium) (2026-07-24)

New game scaffolded at `games/uncharted_lot/` (RECON/FEASIBILITY/PIPELINE + `tools/unc_loc.py` +
`extract/`). Install `F:\Game Lab\UNCHARTED - Legacy of Thieves Collection` (Steam appid **1659420**,
Nixxes 2022 PC port of Uncharted 4 + The Lost Legacy, Goldberg-cracked). Proposed `games.id` =
**`uncharted-lot`**, detector exes `u4.exe` + `tll.exe`, marker dir `Uncharted4_data`.
**Read-only recon — the game folder was left pristine** (every mtime original, 0 artifacts).
Memory [[uncharted-lot-groundwork-go]].

- **🟢 Container = PSARC v1.4 + `oodl` — IDENTICAL to TLOU Part I** (NOT TLOU2's DSAR wrapper), so
  `games/tlou1/tools/{oodle,psarc,psarc_write}.py` read AND write it **unchanged** (set
  `TLOU_OODLE_DLL` to the game's own `oo2core_9_win64.dll`; it ships one, no borrowing).
  **Repack proven on the real 24 MB `text2.psarc`:** identity rebuild = same size + all 48 entries
  content-identical; a Hebrew edit round-trips with **all 47 other entries byte-identical** — in
  **0.1 s** (unchanged entries are stream-copied). Checking the container magic FIRST is what
  collapsed the whole container workstream into "reuse" ([[engine-family-reuse-check-magic]]).
- **🔴 THE ONE FORMAT DIFFERENCE — the ND string table's RECORD WIDTH IS NOT FIXED, and getting it
  wrong FAILS SILENTLY.** `tlou_loc.py` returns **empty strings** (not an exception) on
  `<lang>.common` / `<lang>.subtitles`, which reads like "the file has no text" rather than "the
  parser is wrong". Layout is `u32 count; count*{sid, offset}; blob` with **REC = 8 (`<II>`, u32/u32)
  for `.common` + `.subtitles`** but **REC = 16 (`<QQ>`) for `.subtitles-systemic`**. The tell is
  that the blob begins at exactly `4 + count*REC`, so the width is **validatable, never guessed** —
  `tools/unc_loc.py` `detect_rec()` requires every offset in range and a decodable NUL-terminated
  first string. Selftest PASSes **byte-identical identity** on all three; `encode()` is **surgical**
  (original blob verbatim, overrides appended) per the TLOU2R scrambled-text lesson.
  **UNIVERSAL: when a reused codec returns blank/empty instead of failing, suspect a FIELD WIDTH
  before suspecting the data.**
- **🔑 ONE archive ships BOTH games.** `uncharted4/text2.psarc` and `thelostlegacy/text2.psarc` are
  byte-identical (md5 `5002993429da7fe3b2abccad7b39ff2e`, 24,919,578 B) and hold Uncharted 4 *and*
  Lost Legacy text (Chloe/Nadine/Asav beside Sully/Elena/Rafe/Sam). **One translation = two games**;
  patch both paths. (`sid1.psarc` is likewise identical; `main/text2.psarc` holds only
  `trophy-definitions.json`.)
- **Scope = 36,610 unique strings / 1,148,831 chars** (UI `eng.common` 5,261 · story `eng.subtitles`
  30,415 · systemic barks 11,687; 99,401 records; subs∩systemic overlap 10,737). **The corpus is
  exceptionally clean: 0 `{...}`, 0 `<tag>`, 0 `&entity;`** — only **252 `[TOKEN]`** (62 distinct:
  `[A]` `[B]` `[TEXT]` `[TEXT2]` `[GAME]` `[crossed out]`…), **8 printf specs**, 175 `\n`, one `$H`,
  plus a literal `\` line separator inside the 119 long UI blocks (patch notes / privacy policy, max
  2,526 chars).
- **🟢 100 % sid parity across ALL 23 languages** in both files ⇒ EN→HE maps by sid unambiguously
  **and the New-Era panel is free** — 22 reference languages per line. **Gender oracle is rich**
  (no Arabic ships, so use the game's own gendered locales): **rus/pol/cze** give speaker AND
  addressee from the past tense, **fre/ita/spa/sas/por/bra/gre** give referent gender.
  ⚠️ **`uke` is `LANGUAGE_UKENGLISH` = en-GB, NOT Ukrainian** — its text is essentially the English
  text, which makes it the cheapest sacrifice slot in the game.
- **🔴🔴 THE HIGH-VALUE UNKNOWN — a DORMANT `ara` SLOT.** The exe's language table is triplets
  *loc code · `*hud-flash-keys-XX-XX-array*` · font-asset name*, and `rus`→`russian`, `chi`→`chinese`,
  `kor`→`korean`, `jpn`→`japanese` are **exactly the `.fnt` files in `fonts.psarc`** — proving the
  third field IS the font name. That table contains a full **`ara` / `*hud-flash-keys-ar-ae-array*`
  / `arabic`** row plus `LANGUAGE_ARABIC` and tag `ar`; **UC4 shipped Arabic subtitles on PS4** in
  MENA, and availability is data-driven (`LanguageManager::FindPlayGoAvailableLanguage`,
  `IsTextSupported()`). So ADDING `ara.common`+`ara.subtitles` + `arabic.fnt`+`arabic_00.tga` could
  light up a **real RTL locale** instead of an LTR hijack. **Do NOT assume it** — the exe's only
  `rightToLeft` string belongs to a **focus-navigation** enum (`topDown/bottomUp`,
  `pressed/released`), so text bidi is unconfirmed. PIPELINE Proof B settles it in one launch;
  fallback is the `eng` hijack (zero user action) or `rus` (dedicated atlas, guaranteed room).
- **🟡 Font = injection required, TWO surfaces, 0/27 Hebrew in both.** (a) Native **plain-text
  AngelCode BMFont `.fnt` + uncompressed 32-bit RGBA TGA** (type 2, top-down, 18 B header + 26 B
  footer) — **the easiest font format met in this project**: no BC7 (AC Mirage), no SDF (AC Shadows),
  no DXT5 (Plague Tale), no binary glyph records (GoWR). `main.fnt` = Adelon-Serial DB 42px, 204
  glyphs, 256×128, `packed=1` (channel-packed `chnl` 1/2/4/8 = B/G/R/A); **measured occupancy: chnl
  1/2/4 are 95-98 % full but chnl 8 (alpha) is only 47.9 % used with rows 69→128 entirely free**
  (~15 k px). Per-language variants exist (`russian.fnt` Myriad Pro Light w/ 63 Cyrillic,
  korean/japanese/chinese Arial Unicode/FOT-Seurat). (b) **Iggy/Flash** (`fontlib.iggy`,
  `fmenu.iggy`; `.swf` sources in `flash1.psarc`) — **17 `DefineFont3` faces parsed, ALL 0/27
  Hebrew** (Cyrillic 65, CJK up to 4,775). Iggy is the one genuinely new RE surface, needed only if
  the proof shows the menus render there. Curiosity: `fontlib.swf` id=13 is a one-glyph font whose
  only codepoint is **U+200E (LRM)**.
- **🟢 Activation = ONE WORD IN ONE TEXT FILE** — `steam_settings/force_language.txt` (`english`)
  with 22 Steam names in `supported_languages.txt` (english→eng, koreana→kor, schinese→chs,
  latam→sas, tchinese→chi, brazilian→bra…). Cleanest lever in the project alongside Borderless
  Gaming's JSON key and FL Studio's registry value → a `kind:"textfile"` `game_language.py` entry.
- **🟢 ZERO DRM** — 0 hits for Denuvo / VMProtect / `.vmp` / EAC / BattlEye in **both** exes;
  `.reloc` 314 KB against a 38 MB `.text` ⇒ **unpacked and statically analyzable** (that string
  mining is exactly what surfaced the `ara` row). 2022 title, no longer patched.
- **✅ PROOF A BUILT + DEPLOYED (2026-07-24) — awaiting the user's launch.**
  `work/unc_font.py` (Hebrew injector) + `work/build_menu_proof.py` (`--deploy`/`--revert`/
  `--verify`). Live in the game: `fonts.psarc` with 27/27 Hebrew glyphs in `main.fnt`/`main_00.tga`
  (atlas grown 256×128 → 256×256, existing Latin untouched at its original coordinates) + both
  `text2.psarc` with **26 sid overrides** on `eng.common`. Backups `*.he_backup` beside each;
  language stays `english` (**zero user action**).
  **The proof bundles every open question into one launch:** a pure-Latin `ZZ-UNC-OK-ZZ` marker on
  `Press Any Button`/`START` (mount, independent of fonts) · the SAME word stored **LOGICAL**
  (`Continue`) vs **VISUAL** (`New Game`) with an `אבגד` 4-letter control (bidi mode) · all 27
  letters on `Credits` (glyph coverage) · a Hebrew paragraph with punctuation/parens/quotes/digits/
  a Latin island in **both** modes on the two Quit dialogs (layout) · and `LOADING` patched so the
  **native renderer** is exercised alongside the Flash menu (which surface is which). Every target
  is patched on **all** its sids, because several menu items exist under 2-3 sids.
  **🔑 The font work was measure-driven, not guessed** ([[bitmap-font-size-is-engine-side]]): channel
  mapping and top-down row order were confirmed by decoding shipped glyphs; Hebrew body = 0.85 ×
  the measured Latin cap ink (22 vs 26 px); and the **edge profile was matched conditional on ink**
  to the shipped Latin (5.8/16.8/77.4 % faint/mid/solid → 4.9/16.9/78.2 %). **LANCZOS was the wrong
  resampler** — its ringing gave 20.5 % faint pixels, a 4× halo = exactly the "dots/noise around the
  letters" failure from GoWR/Plague Tale; **`Image.BOX` + a contrast stretch to 0.75** fixed it.
- **✅✅ PROOF #1 CAME BACK (2026-07-24, user screenshots) — TWO gates closed, and it re-aimed the
  whole font effort.**
  - **MOUNT ✅** — the glyph COUNT on screen matched exactly (4 boxes for `אבגד`, 8 for
    `אפשרויות`, 2+2 on the `כן`/`לא` buttons). The text reaches the screen; only the glyphs are
    missing.
  - **🔑 BIDI = NONE ⇒ STORE VISUAL — and it was read off a screen with ZERO renderable glyphs.**
    The stored LOGICAL `בדיקת עברית: שלום, זהו משפט` rendered as `□□□□□ □□□□□ : □□□□ , □□□ □□□□`:
    colon after 5+5, comma after 4, `12345.` opening a line and `Uncharted 4.` closing it — exact
    STORAGE order. RTL reordering would have inverted it. **UNIVERSAL: PUNCTUATION AND DIGIT
    PLACEMENT SETTLE BIDI EVEN WHEN EVERY LETTER IS TOFU** — a tofu screenshot is not a failed
    experiment, it still carries the ordering answer, so always include punctuation + digits +
    a Latin island in a proof string.
  - **FONT ✗ — `main.fnt` is NOT the shipping text path.** Latin rendered perfectly while Hebrew
    was tofu, so the atlas injection (however correct) was aimed at the wrong renderer.
- **🔴 CORRECTION to the recon above: the exe's language-table third field is NOT the font name.**
  `rus`→`russian` / `chi`→`chinese` looked like the `.fnt` names, but the same table has
  `nor`→`norwegian`, `swe`→`swedish`, `pol`→`polish`, and **no such `.fnt` exists**. The match was
  coincidence for the four languages that happen to need a special font. It is the locale display
  name. **UNIVERSAL: a 4-of-N correlation is not a mapping — check the entries that DON'T fit.**
- **✅✅ THE FONT IS IDENTIFIED — `fontlib.swf` id5 **Albertus Medium** — by CHARSET FINGERPRINT
  (2026-07-24), after four rounds of file-guessing failed.** Four sources had been patched and
  ruled out in-game, so I stopped asking *which file* and asked **what can the ACTIVE font already
  draw** — `work/build_charset_probe.py`, a 13-rung numbered ladder that touches **no font file at
  all** (every font archive reverted to pristine first, so exactly one variable moves). In-game:
  `1é 2ü 3ñ 4ć`=YES · `5ˆ 6˜ 7–`=NO · `8" 9• 10€ 11™`=YES · `12ё 13א`=NO ⇒ **`YYYYNNNYYYYNN`**.
  Computed offline against **every font the game ships**, that pattern matches **exactly four
  faces and nothing else**: `fontlib.swf id5 Albertus Medium (255)` · `fontlib-sceasia.swf id5
  (256)` · `fontlib-universal.swf id5 HeiT ASC (3,178)` · `fontlib-scej.swf id4 (2,245)`.
  **UNIVERSAL: character coverage IS a fingerprint — one text-only probe names the live font, it
  cannot break anything, and a null result ("only plain ASCII renders") is equally decisive because
  it proves the game restricts the charset in its own code and no font work will ever help.**
  [[charset-fingerprint-finds-the-font]]
- **🔑 `hud-fonts.bin` (inside `dc1.psarc`) is the FONT ROUTING TABLE, and it confirms the answer.**
  A ND `00CD` container: u64 pointers into a string blob, with **`Albertus Medium` FIRST (@0x00a0)**
  = the default UI face, then per-language rows pointing at `Arial Unicode MS` / `DFHeiW5-A-V-SONY`,
  plus the four library names (`fontlib`, `-sceasia`, `-scej`, `-universal`).
  ⚠️ **`fonts.psarc` lives in `Uncharted4_data/data/`, OUTSIDE the `build/pc` tree** — a sweep
  scoped to `build/pc` misses it entirely (that is why the `.fnt` set went unlisted for a round).
- **🔴 CORRECTION to the note below: `fontlib.iggy` is NOT a compiled `fontlib.swf`.** They ship
  completely different face sets — Iggy: IM FELL English PRO / Alte Haas Grotesk / Avant Garde,
  117 glyphs, **zero Latin-1**; SWF: Cast / Arial Unicode / Albertus, 255-5,176 glyphs. So the
  `.swf` files are a separate, richer font system rather than stale sources, and the Iggy negative
  was a correct result, not a failed patch. Its fingerprint `NNNYYYYYYYYNN` alone excludes it.
- **🔴🔴 THE BLANK-DONOR TRAP — why the SWF round patched the RIGHT file and still showed nothing.**
  `plan_slot` picks any ORDER-SAFE index, which in all these faces is **U+058F**, whose outline is
  **35 B — the exact size of `U+FEFF` (ZWNBSP) in the same font**. So 35 B *is* the blank glyph
  (2 B in the CJK faces): the lookup very likely succeeded while drawing nothing.
  **UNIVERSAL: a blank donor glyph and a missing codepoint are indistinguishable from outside the
  game. Before believing a font-remap negative, measure the donor slot's shape length against a
  glyph you KNOW renders** (here € = 150-190 B, ™ = 76-91 B, • = 57-82 B — anything at the floor of
  that distribution is blank). [[blank-donor-glyph-trap]]
- **🔴🔴 THE ALIAS FIX WAS WRONG AND BLACK-SCREENED THE GAME (2026-07-24, after the logo/intro).**
  `unc_swf.repoint()` gave a blank slot a real outline by pointing its glyph-offset ENTRY at the
  Euro glyph's offset — "two entries sharing one offset is legal, a SWF shape record is
  self-terminating, the reader never needs the length." **True of a spec reader, FALSE of this
  engine.** The glyph offset table is MONOTONIC, and aliasing a LOW slot to a LATER glyph's offset
  makes the implied length `offs[i+1] - offs[i]` **NEGATIVE** (measured −1,230 on `fontlib.swf
  id5`) → a length-by-subtraction reader dies and the UI never comes up, with no crash log. An
  identity repack of the same archive was proven SOUND (17/17), so the fault was `repoint` alone.
  I had literally documented this risk in the function's own docstring and shipped it on a proof
  anyway — a bad call; a one-line monotonicity check would have caught it offline.
  [[aliased-offset-black-screens]]
- **✅ THE REAL FIX = `unc_swf.insert_glyph()` — COPY the shape, don't alias the offset.** Splice
  the donor's shape bytes IN PLACE over the destination slot's own (blank) shape — dst's START
  offset never moves, so monotonicity is preserved — then shift every offset strictly after dst,
  AND the code-table offset, by the length delta, and grow the tag RECORDLENGTH to match. ⚠️ **The
  fontlib offset tables are u16, not u32** — guard that `code_table_offset + delta` still fits 16
  bits or the field wraps. `repoint()` now RAISES. Added `unc_swf.validate()` (offset monotonic +
  code table ascending/unique + last-offset-in-bounds), run on EVERY modified body before repack —
  the black-screen guard, now a build-time exception. `fonts()` exposes `offs`/`sizes`/`off_base`/
  `off_w`/`off_fmt`; `index_of()`, `free_code_above()`.
- **✅✅ PROOF #6 CAME BACK DECISIVE (2026-07-24, user screenshot) — the live UI font is
  `fontlib-universal.swf` **id7 Albertus Medium**, NOT `fontlib.swf` as I had inferred.** The Quit
  dialog read `1□ 2□ 3□ 4□ 5□  6€ 7□ 8□ 9□   11™ ZZ-UNC-OK-ZZ`: **rung 6 (fontlib-universal id7)
  rendered €**, and the vanish control on `fontlib.swf id5` did NOT fire (™ still present). Two
  independent signals agree — the English menu loads the **-universal** library (the wide-charset
  one that also covers JP/KO/ZH), and `hud-fonts.bin` had told me the face NAME (Albertus Medium)
  but not the LIBRARY. And `insert_glyph` works: the injected € renders, no black screen.
- **✅✅ REAL HEBREW INJECTED + MENU PROOF DEPLOYED (`work/unc_font_swf.py` + `build_hebrew_proof.py`,
  awaiting the user's in-game look).** 27 letters need 27 NEW code-table entries (only ONE order-safe
  gap exists), so this is a full DefineFont3 EXTEND via the proven Witcher 3 codec
  (`swf_font.parse/serialize_definefont3` — verified BYTE-IDENTICAL round-trip on all 7 fonts in
  `fontlib-universal.swf`) + `swf_glyphgen.glyph_to_shape` (TTF→SWF shape, NumFillBits=1). Parse id7
  → generate 27 David-Libre-Bold outlines at scale 11.545 (EM 20480 / David 2048, target ≈0.63 EM) →
  insert (code, shape, advance, bounds=`\x08\x00` empty RECT matching the font) at the sorted
  position → serialize (offsets recomputed in glyph order ⇒ monotonic by construction) → splice, fix
  the tag RECORDLENGTH AND the SWF FileLength. id7 grew 459→486 glyphs. **Offline-tested 16/16**:
  all 459 original glyphs byte-identical, 27 Hebrew sorted, 6 sibling fonts untouched, validate
  clean, FileLength fixed, full psarc repack sound with 16 other entries untouched. Deployed with the
  standing recipe stored VISUAL (`get_display(base_dir="R")`): a Latin MARKER, the full 27-letter
  ALPHABET on Credits (glyph coverage), real Hebrew menu labels, a TEST PARAGRAPH (punctuation/
  digits/parens/quotes/Latin island), and a bidi A/B (`שלום` VISUAL | LOGICAL | `אבגד` control) on
  the Quit dialog. Revert: `build_hebrew_proof.py --revert`.
- **📁 The euro-identify probe stays as a regression template.** `build_font_probe3.py` (9 rungs +
  vanish control, `insert_glyph`-based) identified the face; keep it for any future "which face draws
  this surface" question. Offline-tested 72/72 across 9 faces.
- **🔴🔴 GAME UPDATE MID-PROJECT (2026-07-24) — no damage, but it exposed a real footgun.**
  The user updated the game while proof #6 was deployed. The updater overwrote
  `flash1.psarc` + both `text2.psarc` + `dc1.psarc` with a newer build (2023-07-06), so the
  patches were simply gone — **but the `.he_backup` files were then copies of the PREVIOUS
  GAME VERSION**, and `shutil.copy2(backup, live)` cannot tell "restore my patch" from
  "downgrade the game". A later `--revert` would have put 2022 archives onto a 2023 install,
  desynced from the updated `dc1.psarc`, visible only in-game. Stale backups deleted.
  **Integrity proven objectively via the repack's OWN manifest `_Redist/fitgirl.md5`**
  (542 entries): the updated archives mismatch (expected), and **`fonts.psarc` + `iggy1.psarc`
  — the two I had patched and reverted in earlier rounds — match it EXACTLY**, i.e. the revert
  path is byte-exact. Live archives re-verified clean (0 Hebrew, 45/45 code tables sorted, no
  marker), and **the font verdict survived the update** (same 4 exact fingerprint matches,
  corpus +18 records only). **FIX: `work/unc_backup.py`** — records `original_md5` AND
  `deployed_md5` in a `<file>.he_backup.json` sidecar; `restore()` restores only when the live
  file is still what we deployed, **REFUSES** when the game changed underneath (`--force`
  deletes the stale backup and leaves the newer file alone), and `backup()` never overwrites an
  existing backup (on a re-deploy the live file is our own patch). Wired into all 5 probe
  scripts; 13/13 selftest including the exact real-world scenario.
  **UNIVERSAL: any deploy that keeps a backup must record what it WROTE, not just what it
  saved — otherwise a vendor update silently converts your safety net into a downgrade.**
  [[game-update-makes-backups-stale]]
- **🔑 THE UI IS IGGY (RAD's compiled-Flash runtime), AND IT NARROWS TO ONE FILE.** Established by
  static analysis: (a) the game loads `.iggy`, not the shipped `.swf` — `iggy1.psarc` has 47 entries
  vs `flash1.psarc`'s 17, UI pieces like `controller-movie`/`interactables`/`menu-dynamic-window`
  exist ONLY as `.iggy`, and **the font sets differ entirely** (SWF = Cast/Comic Sans/Arial Unicode;
  iggy = Alte Haas Grotesk/IM FELL English PRO/Avant Garde/Albertus Medium) ⇒ the shipped SWFs are
  stale sources from another build; (b) `u4.exe` imports `IggyFontSetIndirectUTF8` but **NOT**
  `IggyFontInstallTruetype*`, so there is no data-driven hook to install an external TTF;
  (c) **only `fontlib.iggy` contains glyphs** — all 23 other UI libraries reference fonts by NAME
  (`DrakeFont`, `DescFont`, `DescFontBold`, `PromptFont`, `DefaultLabelAltFont`) with **zero** code
  tables, including `sp-hud.iggy` (subtitles). **One file covers the entire game's text.**
- **Iggy format, as far as needed:** 64-byte header + block1 + block2 (`fontlib.iggy` =
  64 + 1,446,712 + 3,859 = the exact file size). Each of the 6 fonts owns an **ascending u16 code
  table of 116 glyphs** (95 ASCII + U+00A0, U+0107, U+02C6, U+02DC, U+2013, U+2014, U+2018..U+201E,
  U+2020, U+2021, U+2022, U+2026, U+2030, U+2039, U+203A, U+20AC, U+2122) followed by the UTF-16
  face name; glyph outlines are **f32 vector paths**, which is why ADDING glyphs is real RE work.
  ⚠️ Face names must be filtered by "contains a space + has a vowel" — the f32 path data throws off
  plenty of accidental printable UTF-16 runs (`xAxzA`, `VidWixYi`).
- **✅ PROOF #2 BUILT + DEPLOYED (`work/unc_iggy.py` + `work/build_font_probe.py`) — awaiting the
  user's launch.** The code table is a plain u16 array, so **remapping a codepoint is a delta-0
  two-byte edit** with no glyph data, offsets or pointer fix-ups. The ordering constraint is the
  catch: the table is ascending and the ONLY gap that can host U+05D0..U+05EA is between
  **U+02DC (index 98) and U+2013 (index 99)** — indices 99..115 are 17 usable slots.
  The probe is a **LADDER**: each of the 6 fonts gets index 99 (`U+2013`, the en-dash) remapped to a
  DIFFERENT Hebrew letter (font 0→א … font 5→ו), and 19 reachable surfaces are set to `אבגדהו`.
  Whichever POSITION draws an en-dash names that surface's font, and two surfaces differing means
  they use different fonts. If nothing changes at all, the code table is not the engine's lookup —
  equally decisive. Deployed delta-0 (`iggy1.psarc` + both `text2.psarc`, `.he_backup` beside each).
- **NEXT after the user reports:** inject Hebrew outlines into the identified font(s) in
  `fontlib.iggy` (the 17 order-safe tail slots take 17 of 27 letters; the remaining 10 need either
  a second gap or real glyph-array surgery) · **Proof B** = the `ara` gamble (needs an **add-entry**
  path in `psarc_write` — today it only replaces) · then delegate the 36,610 lines
  ([[delegate-all-translation]], [[new-era-doctrine]], name registry for Drake/Sully/Elena/Sam/
  Rafe/Chloe/Nadine/Asav per [[name-registry-and-internet-check]]), order by visibility for the
  `/translate` pool ([[community-pool-by-category]]), publish only on "פרסם".

---


