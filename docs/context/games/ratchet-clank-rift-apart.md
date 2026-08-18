## Ratchet & Clank: Rift Apart Hebrew — Phase-1 groundwork DONE, 🟢 GO (medium tier) (2026-07-12)

New game scaffolded at `games/ratchet_rift_apart/` (RECON/FEASIBILITY/PIPELINE + `work/` probes). Install
`F:\Game Lab\Ratchet & Clank - Rift Apart` (Steam appid **1895880**, Nixxes 2023 port). games.id =
**`ratchet-rift-apart`** (already a catalog card since 2026-07-02: planned/free, website+launcher, images
uploaded; detector pattern + `RiftApart.exe` already in `game_detector.py`). **Insomniac engine — the SAME
container+text+font+applier stack as Spider-Man 2, already cracked in this repo.** Driven by the Phase-1
Playbook + a 9-agent Workflow (6 analyze + 3 adversarial-verify, all high-confidence). Memory
[[ratchet-rift-apart-groundwork-go]].

- **✅ Container = TOC2/RCRA (`toc` magic `0x34E89035`, v202300 == VERSION_RCRA) — dat1lib reads it AS-IS**
  (147 archives, 340,665 assets, 256 spans). UI = cohtml/GameFace (`cohtml.WindowsDesktop.dll`, same as SM2).
  Benign `"Actual decompressed size…isn't equal"` warning on read — harmless.
- **✅ Text = `localization/localization_all.localization`** (aid `0xBE55D94F171BF8DE`, **32 variants**, one per
  span: variant *N* → span *N*×8). Inner = 36-byte asset header + DAT1, **STRUCTURALLY IDENTICAL to SM2** — same 9
  section tags (VALUES `0x70A382B8`, KEYS `0x4D73CEBD`, TEXT_OFFSETS `0xF80DEEB4`, KEY_OFFSETS `0xA4EA55B2`,
  ENTRY_COUNT `0xD540A903`), **24,575 entries**. ⇒ SM2 build pipeline reusable. Subtitle marker = `<ts="a;b">`.
- **🔴 THE difference from SM2 — NO Arabic slot (adversarially verified: 0 Arabic + 0 Hebrew codepoints in ALL 32
  variants, full decode).** Only an Arabic AUDIO/dev-enum (`wem.ar`/`soundbank.ar`, no text on disk). ⇒ **LTR-slot
  hijack** (AC2/Anno/GTA/TLOU class), NOT the Arabic-slot hijack. **English = the target** (v0/v1 en-US = SOURCE,
  v2/v18 en-GB). Full variant→language map in FEASIBILITY.md (ja=9, ko=10, ru=14, zh=21/22, el=26, tr=19=alt
  sacrifice slot, 4 empty stubs 23/28/29/30).
- **Scope (Playbook Stage 7): UI 7,521 · Subtitles 10,033 · Skip 7,021 → translatable 17,554.** CREDITS (3,595,
  mostly proper names) = low priority. Chars: RIVE=Rivet, RATC=Ratchet, CLANK, KIT, NEFT/PIR/T4L = NPC VO.
- **✅ Repack PROVEN: DAT1 identity round-trip = SEMANTIC-PASS** (0/24,575 key/value mismatch on re-parse, not
  byte-identical — same proven-in-game pattern as SM2/TLOU2), 1-string Hebrew read-back OK.
- **✅ Native applier `translation_manager/spiderman2_mod.py` works AS-IS** (adversarially verified, NO changes):
  `get_sizes_section()` TAG `0x65BCF461` (340,665 RCRA 16-byte `<IIIi>`), `get_archives_section()` TAG `0x398ABFF0`
  (147, 66-byte `<QQIHI>`), `get_spans_section()`=256. Hijack span 0 → size-entry index **87375** → `{archive_index=67
  (d\localization), offset=0, value=2249335, header_offset=3123756}` (value==filesize−36). Deploy = rebuilt DAT1
  (header stripped, payload=raw[36:]) → `d\mods\tm_he_0` + append archive + redirect; `.stage` entry `0/BE55D94F171BF8DE`;
  backup `toc.tm_he_backup`; revert restores. NO big-archive repack, NO Overstrike.
- **⚠️ Font = injection REQUIRED (adversarially verified 0/27 Hebrew on all 10 shipped fonts).** UI+subtitle font =
  **Proxima Nova** Reg (aid `0xA2197874D2B7B1AC`) + Bold (`0xB5F411285669C55D`), archive 109 `d\userinterface`.
  **CLEAN sfnt TTF at offset 0, no wrapper** (simpler than SM2's +36/8-byte-prefix). Inject 27 Hebrew glyphs via
  fontTools glyph-merge (solved class, GoWR/Anno/W3) + EMPTY the U+200F/U+200E glyphs. `configs/uiconfig/uifontmap.config`
  = per-lang FontsToReplace (optional secondary lever). **Atmosphere font = Rubik** (bilingual, rounded, fits R&C's
  playful sci-fi; alts Varela Round/Fredoka).
- **⚠️ bidi = MENU-PROOF DECIDES (do NOT assume).** cohtml runs the UBA (honors Unicode bidi controls, ignores CSS
  dir) → **prior is LOGICAL + leading `&rlm;`** (U+200F, NOT RLE — SM2 tofu lesson); VISUAL would double-reverse.
  But the English-slot base direction is LTR (unlike SM2's Arabic-flipped container) → build BOTH (LOGICAL+RLM and
  VISUAL) and let the screenshot pick (HL landed LOGICAL; TLOU/GoT/007 landed VISUAL).
- **✅ DRM/precedent GREEN:** no Denuvo, no EAC/BattlEye (single-player); Overstrike + dat1lib/ALERT support R&C;
  translation tools (Nexus mod 37/50); **RTL proven on this engine** = Arabic mod for Spider-Man Remastered PC (Nexus
  mod 361). Activation = Settings → Game Settings → Text Language = English (default; VO independent → English voice free).
- **✅ FONT INJECTED + MENU-PROOF BUILT + DEPLOYED (2026-07-12, awaiting user's in-game screenshot).** Proxima Nova
  Reg+Bold extracted via dat1lib (`work/20_font_extract.py`; both in span 0, header_offset=-1 = raw TTF, value==size),
  Hebrew injected from Heebo via `anno_font._add_hebrew` (`work/21_inject_font.py`: **27/27 Hebrew, 26/26 Latin kept**,
  + a zero-width empty glyph mapped for U+200F/E/202A-E so `&rlm;` anchors render INVISIBLE). Menu-proof
  `work/23_build_menu_proof.py` patches the **PAUSE menu** (one screen: Resume/Settings/Manual-Save/Restart/Controller-
  Layout/Photo-Mode/Quit + tabs + settings labels) with a MIX of **LOGICAL / LOGICAL+RLM / VISUAL** + a Latin marker
  `ZZ-RC-OK-ZZ` (mount proof) + digit (`שלב 12`) & Latin-island (`מצב Ratchet`) diagnostics → rebuilds the loc DAT1
  (18/18 keys verified on re-parse) + bundles the 2 injected fonts into `.stage` entries `0/BE55D94F171BF8DE`,
  `0/A2197874D2B7B1AC`, `0/B5F411285669C55D`. **Deployed via `spiderman2_mod.apply` AS-IS** — offline-validated on a
  temp toc copy first (`work/24_validate_deploy_offline.py` PASS), then applied to the live game: backup
  `toc.tm_he_backup` created, `d\mods\tm_he_{0,1,2}` written, live toc redirects all 3 assets, `is_applied=True`,
  150 archives. **User: launch → pause menu (+ Settings → Text Language screen), screenshot.** The `ZZ-RC-OK-ZZ`
  marker proves mount+font; LOGICAL-correct vs VISUAL-correct decides the bidi mode; no-tofu confirms font coverage.
  **Revert:** `python games/ratchet_rift_apart/work/23_build_menu_proof.py --revert` (restores `toc.tm_he_backup`).
- **✅ Community `/translate` pool LIVE — 17,624 rows (2026-07-12).** `work/30_build_ct_strings.py` reuses the
  count report's `classify()` for the skip filter, then buckets by **VISIBILITY** ([[community-pool-by-category]]):
  **ממשק ותפריטים 5,157 → כתוביות עלילה 9,891 → קרדיטים 2,576** (contiguous `order_index` blocks, so a partial pass
  covers what players see first). `string_key` = **the RAW loc key** (unique per entry → an approved export maps
  straight back onto the build, no md5 indirection); `source_en` + `current_he` BOTH from **variant_00 (en-US)** —
  the same mapping the build consumes, so the WD2 mis-pairing trap can't occur; `current_he=''` (fresh game).
  `context` = the **speaker name for 9,862 subtitle lines**, resolved from the game's own `NAME_SUBTITLE_<PREFIX>`
  table (a real closed set — NO auto-derived gender hint, per [[gender-hint-needs-closed-set]]).
  Verified live on the PUBLIC API: `/api/translate?action=games` → total 17,624 / open 17,624; rows carry
  `category=ממשק ותפריטים` (the Hebrew section flows to `category` automatically) and the first batch served is UI.
  **⚠️ TWO things this round corrected — do not regress:** (a) the pool is built from **variant_00 (en-US)**, the
  hijack/source target, NOT variant_18 (en-GB) which the count report used → 17,624 rows here vs the 17,554 reported
  (a 70-row en-US/en-GB delta, both internally correct); (b) the count report's **length heuristic mis-routes long UI
  prose** (legal notices, card/settings descriptions) into "subtitles" — the pool instead uses a STRICTER rule:
  subtitle ⇔ the `<ts="a;b">` tag **OR** a prefix in the game's own speaker table. Uses the game's data, not a guess.
  **⚠️ Supabase auth gotcha (cost a 401):** the service key is the NEW `sb_secret_…` format and PostgREST **rejects it
  from a browser User-Agent** — send NO browser UA for PostgREST (the opposite of the Management API, which requires one).
- **✅✅ ALL PHASE-1 GATES CLOSED IN-GAME (2026-07-12) — mount · live variant · font · bidi.** Three deploy rounds:
  1. **The first proof showed NOTHING** — not even the Latin marker — while `MENU_LOADGAME_TITLE` (the ONLY key whose
     English value is "LOAD GAME", visible on the CONTINUE GAME screen) stayed English. So the mod was not being read.
  2. **VARIANT LADDER** (`work/25_build_variant_ladder.py`, the [[measure-with-a-ladder]] method): patch ALL 32 variants,
     variant *N* gets the unique marker `ZZ-NN-ZZ` in that key → **ONE screenshot named the live slot: `ZZ-01-ZZ` =
     variant_01 / span 8** (the en-US DUPLICATE, not span 0 which the activation analysis recommended). **🔑 UNIVERSAL:
     when several slots can serve the same asset, do NOT guess which one the engine picks — ladder them all and let one
     launch name it.** The same shot also proved the **font works: Hebrew rendered clean, ZERO tofu** (Proxima Nova +
     Heebo injection + the zero-width bidi-control glyph).
  3. **BIDI A/B + TRANSCRIPTION CONTROL** (`work/26_build_bidi_ab.py`): the ladder's LOGICAL sample looked "reversed" to
     the user while MY reading of the same screenshot said it was correct — so the mode was NOT locked on that. Instead
     the SAME word was shipped in BOTH modes on adjacent rows + a 4-distinct-letter control (`אבגד`). Result, all three
     consistent: LOGICAL `שלום`→`םולש` ✗ · **VISUAL `םולש`→`שלום` ✓** · LOGICAL `אבגד`→`דגבא` ✗ ⇒
     **bidi = NONE. The engine draws in STORAGE order → STORE VISUAL (pre-reversed), same class as AC2/Anno/GTA/TLOU/WD2-UI.**
- **🔴 UNIVERSAL LESSON — an image's Hebrew transcription reflects READING order (RTL), not pixel order.** That is why a
  single LOGICAL sample was read as "correct" by me and "reversed" by the user, and why the first proof round could not
  settle the mode. **The reliable instrument is an A/B PAIR of the SAME word stored both ways on one screen** (exactly one
  can be the readable word) plus a control string of 4 non-confusable letters — never one sample, and never a
  final-form letter like `ם` (it reads as `ס` at menu size, which is what made `קרדיטים` ambiguous).
- **Ship strategy: patch ALL 32 variants** (proven, 23 MB stage, `apply` handles 34 assets) — then ANY in-game language
  selection shows Hebrew and the mod cannot miss the slot. Game left CLEAN after the proofs (`--revert`, is_applied=False).
### ✅✅ PHASE 2 COMPLETE — full Hebrew translated (community-compute fleet), QA'd, built VISUAL, DEPLOYED (2026-07-22)

**The translation was done by the COMMUNITY-COMPUTE fleet (volunteer phones, BYOK), NOT the /translate
pool.** The 17,624 New-Era lines were seeded into the Supabase hub `cc_lines` queue (project
`mfudkftrluabqlrpkvtj`) and the phones finished all of them — `cc_stats` = **done 17,624 / open 0 /
claimed 0**, and `work/cc_progress_hist.json` plateaued at 17,624. **"התרגום נגמר" for a CC-seeded game
means the answer is in `cc_lines.out`, not the /translate pool (which still reads 0 translated).**
- **🔑 PULL PATH: `cc_lines.target`=the R&C loc `string_key`, `cc_lines.out`=the Hebrew** (seed_jobs sets
  `target=k`). Read it via the **Management API query endpoint** (sbp token in `website/.env` +
  browser UA) — `collect_results.py` reads the OLD `cc_jobs` batch-table and does NOT see the
  line-model `cc_lines`. `cc_stats` (done count) is readable via the anon key `sb_publishable_…` +
  the soft `cc_06950e1d…` secret. Pulled `{target:out}` → `work/hebrew.json` (17,624, 0 empty).
- **✅ QA — `work/31_normalize_hebrew.py` (UNTRUSTED community output → clean, "repair-don't-reject").**
  Deterministic repairs against the EN source: **192 niqqud** stripped · **1,171** dropped/un-escaped
  `<ts>`/`<name>` structural prefixes restored (& re-escaped `&quot;`/`&amp;` to the loc-native form) ·
  **17** "English-echoed-then-Hebrew" lines (drop the echo) · **6** invented `<ts>`/`<name>` a worker
  added to a plain lyric line (strip them) · **1** leaked New-Era panel (cut at `\nFR:`) · **900**
  legit passthroughs (781 credits names / tech labels / URLs kept Latin). Only **3** genuine content
  failures (garbled Devanagari in "ray-tracing", a spurious `%d` on a counter, one misaligned ad
  subtitle) — **re-queued to the fleet** (reset those 3 `cc_lines` rows to `open`), all 3 came back
  fixed in ~2 min → **final clean = 17,624 / redo = 0** (0 niqqud, 0 foreign, 0 prefix drift, 0
  printf drift). ⚠️ The QA heuristics false-flagged good HTML-`<span>`/brand-preserving lines and
  mis-parsed `%%` (escaped percent) as a conversion — **relaxed both**; measure a redo set before
  trusting a "N defects" count.
- **🔴 §8b APPLIES TO THE FULL BUILD, not just the proof — `work/rc_rtl.py` (real UBA).** The menu proof
  proved bidi=VISUAL with a HAND-ROLLED `visual()`, but that mis-places a comma between two Hebrew words
  (`שלום, עולם!` → wrong side). For the real corpus (punctuation, mixed Latin, inline `<span>`) the
  shipping transform runs **`python-bidi` `get_display(base_dir='R')`** with engine markers protected:
  order-bearing STRUCT markers (`<ts="a;b">`/`<name>`/`<br>`) split the string into independent chunks
  (segment order never flips), inline tokens (`<span>`/`[TOKEN]`/`{VALUE}`/printf) stashed as atomic PUA
  during the UBA. selftest 8/8. Works on the escaped loc-native form (unesc → UBA → re-esc).
- **✅ BUILT + DEPLOYED — `work/40_build_full.py`.** Applies `rc_rtl.to_visual` to all 17,624, patches
  **ALL 32 variants** (span N×8, 563,968 key-hits) + bundles the 2 Hebrew-injected Proxima Nova fonts →
  a 24.8 MB `.stage`. Offline-validated (32 spans + 2 fonts, all loc blobs re-parse, a menu line's
  VISUAL form present in the live span-8 blob). Deployed via `spiderman2_mod.apply` (index-redirect, no
  repack): **`{ok:True, count:34}`**, is_applied=True, backup `toc.tm_he_backup`, 34 `d\mods\tm_he_*`.
  Revert: `python games/ratchet_rift_apart/work/40_build_full.py --revert`.
- **STATE: the FULL Hebrew mod is DEPLOYED and awaiting the user's in-game look.** Nothing published
  (no "פרסם"). Tools: `work/31_normalize_hebrew.py` (QA) · `work/rc_rtl.py` (UBA VISUAL) ·
  `work/40_build_full.py` (build/validate/deploy/revert) · source `work/hebrew_clean.json` (17,624).
- **NEXT:** user launches → Settings → Text Language = English → screenshots the menu + a subtitle
  scene to confirm the full-corpus VISUAL (punctuation/mixed-script/wrapping) reads correctly. Then
  (optional) atmosphere-font swap to Rubik, and publish like SM2/GoWR **only on "פרסם"** (GitHub
  `ratchet-rift-apart-hebrew-mods` + Worker slug + Supabase `games` id flip + `mod_version_history`).

### 🔑🔑 R&C round 2/3 — the launcher-vs-game bug SOLVED: they read DIFFERENT KEYS, split by suffix (2026-08-09)

In-game review found real bugs beyond the Phase-2 build: word-by-word garbage on system screens
(save/profile/dialogs), wrong words (`PCGRAPHICSSETTINGS_HIGH`→"גובה" instead of "גבוה"), tofu
boxes (41× U+2011 non-breaking hyphen — the font has no glyph for it), and — the one that mattered —
**the pre-game Nixxes launcher's PC-settings tabs render REVERSED while the in-game settings menu
reads correctly, or vice versa, no matter which bidi mode was chosen.**

- **Fix 1 — the missing font.** Save/profile/system dialogs render with **`SIE-TBGoStd R/B`**
  (Sony platform Gothic, in `d\userinterface`, 0 Hebrew), NOT Proxima Nova. `work/
  41_inject_sie_fonts.py` merges Heebo Hebrew into it via `anno_font._add_hebrew` +
  `add_empty_controls` (bidi glyphs zeroed) → bundled as a 3rd/4th font in the `.stage`
  ([[font-inject-every-face]]). Fixed the save-slot/profile tofu.
- **Fix 2 — deterministic word/hyphen fixes** in `hebrew_clean.json` (LAUNCHER_PLAY→"הפעל",
  UI_MENU_CONFIRM/ANALYTICS_ACCEPT→"אישור", PCGRAPHICSSETTINGS_HIGH→"גבוה", 41× U+2011→regular `-`).
- **🔑🔑 Fix 3 — THE root cause of the launcher/game conflict (found from the user's OWN
  differential report, not guessed): the SAME setting is stored under TWO DISTINCT KEYS — a
  BASE key and a `_UPPERCASE`-suffixed twin — and each renderer reads a DIFFERENT one.**
  Proof: the user reported the launcher showed "שלושה קווים" (reversed) for Trilinear while
  the in-game menu showed "טריליניארי" (correct) for the SAME setting. Grepping the corpus
  found `PCGRAPHICSSETTINGS_TRILINEAR='שלושה קווים'` (base) vs
  `PCGRAPHICSSETTINGS_TRILINEAR_UPPERCASE='טריליניארי'` (uppercase twin) — **two separate loc
  entries for one UI control.** Confirmed the pattern holds broadly: 76 of 85 `_UPPERCASE`
  keys have a real base twin; a scan of the launcher's own settings-page UI-DOC
  (`0x8B875EC96CB13E41` in `d\config`) showed it references ONLY `_UPPERCASE` value-keys
  (HIGH/MEDIUM/LOW/OFF…) plus 2 bare base titles (`PC_AUDIO_COMPLEXITY`,
  `PC_LISTENINGMODE_TITLE`) — i.e. **the launcher (Qt, does its own bidi) reads the BASE key
  → needs LOGICAL; the in-game cohtml menu (no bidi) reads the `_UPPERCASE` twin → needs
  VISUAL.** Since they are LITERALLY DIFFERENT STRING KEYS (not the same key read from two
  spans — an earlier `GAME_SPAN`-based hypothesis was tested and disproven: all 32 loc
  variants carry every key), the two renderers can be satisfied **simultaneously** with **one
  build**, by encoding **per key** instead of per surface. **Round 4 (same day) GENERALIZED
  the rule** after the user reported a SECOND instance — `PCDISPLAYSETTINGS_AUTO='אוטומטי'`
  (a dropdown VALUE with **no** `_UPPERCASE` twin at all) also rendered reversed on the
  launcher, proving the narrow `LAUNCHER_ONLY_EXACT`-set version of the fix (round 3) was
  incomplete: it only fixed twin-having keys + 2 hand-picked exceptions, so any OTHER
  twin-less base key in the same prefix family still defaulted to VISUAL and broke on the
  launcher. **`store_value` now applies ONE rule to the WHOLE prefix family, twin or not:**
  any key starting with `SHARED_PCSETTINGS = ("PCGRAPHICSSETTINGS_", "PCDISPLAYSETTINGS_",
  "PC_", "PCAUDIO")` that does NOT end `_UPPERCASE`/`_DESC` → **always LOGICAL** (the
  launcher is the only reader of a bare base key in this family); the `_UPPERCASE`/`_DESC`
  twin → **always VISUAL** (in-game only). A twin-less pure-Latin value (DLSS/FSR/TAA) is
  bidi-invariant either way, so defaulting the whole class to LOGICAL is safe with no
  per-key enumeration. The old `LAUNCHER_ONLY_EXACT` 2-item allowlist was deleted —
  superseded by the general rule. `games/ratchet_rift_apart/work/40_build_full.py`
  `SHARED_PCSETTINGS` / `LAUNCHER_ONLY` / `store_value`. Offline-validated (`TRILINEAR`=
  LOGICAL, `TRILINEAR_UPPERCASE`=VISUAL in the built span-8 blob) + deployed.
  **UNIVERSAL — the general form of [[bidi-per-surface-not-per-product]]: when two renderers
  in the SAME product need opposite bidi for what LOOKS like one setting, check whether the
  engine actually stores it as two keys (a `_UPPERCASE`/console-style twin is a common Nixxes/
  PC-port pattern) before assuming a per-span or per-surface tradeoff is unavoidable — a
  differential user report naming the SAME setting rendering two different ways on two screens
  is the tell. AND: once you find the split, apply it to the whole PREFIX FAMILY, not just the
  one key the user happened to screenshot — a twin-less sibling in the same family fails the
  identical way and the user will report it next.**
- **Config-doc mapped exhaustively (528 identifiers, `work/_full_cfg_scan.py` +
  `_full_cfg_diff.py`) — only 7 real gaps, now 4.** The shared launcher+pause-menu UI-DOC
  (`0x8B875EC96CB13E41` in `d\config`) references 528 distinct string keys total. Diffed
  against `hebrew_clean.json`: only **7 were genuinely missing** (`BKWAN` and bare `SETTINGS`
  are byte-scanner false positives, not real keys). Of the real 5 — **3 were a safe,
  non-translation deterministic fill**: `HUD_WIDESCREEN_SCALING_16_9/_21_9/_32_9` are
  dropdown-option TITLE keys sitting alongside an existing translated `_FULL`='רחב' sibling
  and existing `_DESC` siblings that already reference `16:9`/`21:9`/`32:9` literally in
  Hebrew prose — so these are universal numeric aspect-ratio NOTATION, not linguistic content,
  and were filled in directly (`16:9`/`21:9`/`32:9`) without violating
  [[delegate-all-translation]] (same class as filling a resolution or FPS number). The
  remaining **2 genuinely need translation and were deliberately left untranslated**
  (English fallback, per policy): `HUD_WIDESCREEN_SCALING_DESC`, `TEXTLANGUAGE_DESC`.
- **⚠️ UNRESOLVED — tab/category-header/breadcrumb garbling, root cause NOT found despite
  deep investigation.** `SETTINGS_DISPLAY_GRAPHICS_TAB`, `SETTINGS_KEY_BINDING_TAB`,
  `SETTINGS_MOUSE_TAB` render as the literal English key name in-game; `SETTINGS_GAMEPAD_TAB`
  (structurally the most similar sibling) renders correctly ("בקר"). **This is NOT simply
  "unreachable via any loc file" as round 3 concluded** — byte-level inspection of the
  config-doc (`work/_cfg_bytes_compare.py`) shows all four keys ARE referenced by name inside
  the SAME binary structure, each preceded by an internal widget-type-name string: the
  working one is preceded by `"PageControls"` (widget class `UIOptionTypePage`); the three
  broken ones are preceded by `"PageVisual"` / `"PageKeyBindings"` (also `UIOptionTypePage`)
  and, for `SETTINGS_MOUSE_TAB`, an entirely different widget class `"TypeHeader"`/
  `"OptionType_Header"`. So the failure correlates with the internal page-type-name / widget
  class, not with the loc data itself (both `hebrew_clean.json` values are present and
  valid). **No fix applied — this needs either a deeper structural dump of what
  `"PageVisual"`/`"PageKeyBindings"`/`"TypeHeader"` actually control, or accepting it as an
  engine limitation.** Font-glyph-loss was independently ruled out as a contributing cause
  (`work/_font_glyph_diff.py`: SIE-Gothic-Reg 8204→8261 glyphs / ProximaNova-Reg 1034→1091
  glyphs, **0 glyphs lost** in either injected font vs the pristine originals).
- **⚠️ SELECT PROFILE (save-slot) screen — still garbled, pattern changes between builds,
  not yet explained.** Reported garbled sequences have differed across rounds (`{□V°` /
  `*□□q3~{□V°` in one screenshot round, `F¶` / `wùA` / `ĆF¶` / `4~ĆF¶` in a later one) —
  consistent with the same "reads from elsewhere, not `localization_all`" class as the tab
  headers above, but not confirmed via the same byte-level method yet.
- **Corpus + font integrity re-verified clean** (2026-08-09 sweep, in response to garbled-text
  reports that turned out to be the chrome above, not corpus defects): 0 control chars, 0
  malformed HTML entities across all 17,627 lines; all 4 injected fonts (Proxima Nova R/B +
  SIE-Gothic R/B) have complete ASCII+Hebrew+bidi-control glyph coverage, 0 glyphs lost vs
  the pristine originals.
- **STATE: full mod DEPLOYED with the GENERALIZED key-split fix + the 3 aspect-ratio fills**
  (`40_build_full.py --deploy`, offline key-split validation PASS, `count:36` assets applied
  clean). Nothing published (no "פרסם"). Revert:
  `python games/ratchet_rift_apart/work/40_build_full.py --revert`. **Still open for a future
  round:** the tab/breadcrumb garbling and the profile-screen garbling above — genuinely
  unsolved, do not claim they are fixed.

### 🔴🔴 R&C round 5 — the "generalize ALL base keys → LOGICAL" rule was ITSELF wrong for a
  SUBSET of keys; the real fix is COMPLETING THE MISSING TWIN (2026-08-09, same day)

Round 4's blanket generalization (every `SHARED_PCSETTINGS` base key → LOGICAL, twin or not)
broke `PCDISPLAYSETTINGS_AUTO` in the OPPOSITE direction from what it fixed — user screenshots
of the live IN-GAME Display & Graphics menu (native cyan cohtml UI, unmistakably NOT the
pre-game launcher) showed the aspect-ratio VALUE rendering as **`יטמוטוא`** — the EXACT
letter-mirror of `אוטומטי` (Automatic), the textbook signature of LOGICAL-stored text drawn by
a NO-BIDI renderer. This directly falsified the blanket rule for this key.

- **The two "bare key" bugs are of DIFFERENT NATURES — do not conflate them.** TRILINEAR's
  bug (round 3) was two DIFFERENT translated Hebrew WORDS for one concept (שלושה קווים vs
  טריליניארי) — a genuine two-surface split, correctly fixed by the base/twin LOGICAL/VISUAL
  rule. AUTO's bug is a single WORD rendered as its own MIRROR IMAGE — proof of a bidi
  encoding conflict on ONE SHARED KEY, not two different strings.
- **🔑 ROOT CAUSE, confirmed by grepping the whole corpus for the `_UPPERCASE` twin
  convention: `PCDISPLAYSETTINGS_AUTO` was the ONLY twin-less dropdown VALUE in the entire
  family with real Hebrew content** — every sibling option value (`_HIGH`, `_MEDIUM`, `_LOW`,
  `_OFF`, `_VERYLOW`, `_TRILINEAR`…) already has an `_UPPERCASE` twin; the only OTHER
  twin-less bare keys are pure-Latin acronyms (DLSS/FSR/TAA/SSAO/…, bidi-invariant) or genuine
  launcher-only TITLES (`PC_AUDIO_COMPLEXITY`). The engine's in-game ALL-CAPS-style value
  widget evidently PREFERS a key's `_UPPERCASE` twin when one exists and FALLS BACK to the
  bare key when it doesn't — so AUTO's bare key was being read SIMULTANEOUSLY by that in-game
  widget (needs VISUAL) and by the launcher/whatever else reads the bare form (needs LOGICAL),
  with no way to satisfy both from one stored value.
- **THE FIX: complete the missing twin, don't change the rule.** Added
  `PCDISPLAYSETTINGS_AUTO_UPPERCASE = 'אוטומטי'` to `hebrew_clean.json` — the IDENTICAL
  already-approved Hebrew word, just creating the twin STRUCTURE every sibling option already
  has (not a new translation — [[delegate-all-translation]] is not implicated any more than
  copying an existing approved string ever is). No code change to `store_value` was needed:
  the EXISTING generalized rule already treats any `_UPPERCASE`-suffixed key as VISUAL.
- **🔴🔴 …AND THAT FIX SHIPPED AS A SILENT NO-OP — see round 6. `rebuild()` can only patch keys
  the SHIPPED table already contains, and `PCDISPLAYSETTINGS_AUTO_UPPERCASE` does not exist in
  it, so the new key was dropped without a word and the build still reported success.** The
  "verification" quoted here is itself the cautionary tale: `VISUAL(AUTO_UPPERCASE) present ×56`
  proved nothing — that Hebrew word legitimately appears in 56 OTHER entries, so a plain
  substring search over the blob could never distinguish "my key landed" from "this word exists
  somewhere". **Never verify a key-addressed change with a byte-substring search; simulate the
  CONSUMER'S OWN LOOKUP** ([[verify-a-transform-by-counting-its-effect]]).
- **A comprehensive corpus-wide sweep confirms AUTO was the ONLY gap of this class** — the
  `_UPPERCASE` twin convention is used EXCLUSIVELY by the `LAUNCHER_`/`PC_`/
  `PCDISPLAYSETTINGS_`/`PCGRAPHICSSETTINGS_`/`SETTINGSCATEGORY_` prefix families (89 twins
  total, all already governed by `store_value`'s existing family logic) — no other prefix
  family (`HUD_`, `MENU_`, `AUDIO_`…) uses this pattern at all, so there is no undiscovered
  sibling bug of this same shape lurking elsewhere in the corpus.
  **UNIVERSAL: when a "generalize the whole family to one bidi mode" fix breaks a DIFFERENT
  key in the OPPOSITE direction, the fix usually isn't "pick a different blanket rule" — it's
  that the broken key is missing the STRUCTURAL TWIN its siblings all have. Grep the corpus
  for every OTHER member of the same convention (here: every twin-less bare value in the
  family) before touching the rule again; a targeted one-key completion beats another
  blanket flip.**
- **Deep investigation of the tab/breadcrumb garbling — went further, still unresolved,
  documented so it is NOT re-attempted blindly.** Decoded the EXACT binary layout around
  the working (`SETTINGS_GAMEPAD_TAB`) vs broken (`SETTINGS_DISPLAY_GRAPHICS_TAB` /
  `_KEY_BINDING_TAB` / `_MOUSE_TAB`) config-doc entries: the format is a chain of
  `[u32 len(next string)][12-byte hash][next string]\0*<pad-to-4>` records. For GAMEPAD the
  chain reads `PageControls → UIOptionTypePage → SETTINGS_GAMEPAD_TAB → MENU_GAMEPAD_DESC`;
  for DISPLAY_GRAPHICS it reads `PageVisual → UIOptionTypePage (SAME hash as gamepad's) →
  SETTINGS_DISPLAY_GRAPHICS_TAB → SETTINGS_DISPLAY_GRAPHICS_DESC`. **Checked the obvious
  "missing twin" theory here too and it does NOT apply**: `SETTINGS_GAMEPAD_TAB` (works) has
  **no** `_UPPERCASE` twin, `SETTINGSCATEGORY_DISPLAY`/`SETTINGSCATEGORY_GRAPHICS` (the
  LAUNCHER's own tab headers, screenshot showing literal `SETTINGSCATEGORY_DISPLAY` text)
  **already have BOTH base and twin filled with correct Hebrew content**, and still show the
  raw key name — ruling out both "missing translation" and "missing twin" as the cause. The
  launcher showing the LITERAL ASCII KEY NAME (not garbage bytes) is the classic
  "string-not-found, fall back to the key itself" behavior of many localization frameworks —
  combined with round 3's marker test (patching these exact keys with unique markers made
  NOTHING appear on screen, across all 32 variants) this confirms these specific widget
  classes (`PageVisual`/`PageKeyBindings`/`TypeHeader`) genuinely do NOT read
  `localization_all` at all — they must pull from a separate, not-yet-located resource
  (plausibly hardcoded string tables baked into the compiled cohtml UI bundle in
  `d\userinterface`, which this dat1lib-based toolchain has no fast/safe way to full-text
  search across its ~340K assets). **No patch attempted — a wrong edit to this doc's binary
  structure risks breaking the MANY currently-correct entries that share it, for an unproven
  guess.** This is a harder, more deeply-verified negative than round 3's; treat it as an
  engine-level limitation unless a genuinely new lead surfaces.

### 🔑🔑 R&C round 6 — the loc KEY-HASH is cracked, so keys can now be ADDED; and the round-5 fix was a SILENT NO-OP (2026-08-09)

The user pushed back a third time ("תמצא פתרון"). Instead of another bidi-rule guess, the
localization CONTAINER was decoded properly — which both explained why round 5 changed nothing
and unlocked a capability the project never had on this engine.

- **🔑 THE LOC TABLE HAS NINE SECTIONS, NOT FIVE — four per-entry arrays were never decoded.**
  Beyond `ENTRY_COUNT`/`KEYS`/`VALUES`/`KEY_OFFSETS`/`TEXT_OFFSETS` there are
  **`0x06A58050` u32[cnt] = hash in ENTRY order**, **`0xC43731B5` u32[cnt] = the SAME hashes
  SORTED**, **`0x0CD2CFE9` u16[cnt] = a permutation mapping sorted-position → entry index**, and
  **`0xB0653243` u32[cnt] = flags (almost all 0)**. ⇒ **the engine never looks a string up by its
  key STRING — it hashes, binary-searches the sorted array, and follows the index map.** Verified
  end-to-end: the map round-trips for **24,575/24,575** entries.
- **🔑 THE HASH IS ALREADY IN THIS REPO: `dat1lib.crc32.hash(key, normalize=False)`** (Insomniac
  CRC32, init `0xEDB88320`) — **24,575/24,575 exact, zero duplicates**. `normalize=True`
  (lowercasing) matches 0, and adding a trailing NUL matches 0. **Look for the hash in the
  toolchain before brute-forcing it** — crc32/crc32c/fnv1/fnv1a/djb2 all scored 0/25, and the
  answer was sitting in `dat1lib/crc32.py` the whole time.
- **⇒ KEYS CAN NOW BE ADDED to a shipped Insomniac loc table**, not merely patched: append to
  KEYS/KEY_OFFSETS/VALUES/TEXT_OFFSETS + the hash-by-entry + flags arrays, and **insert** the new
  hash into the sorted array with its index-map slot at the same position. `rebuild()` in
  `40_build_full.py` does this (`add_keys=`), asserts no hash collision, and refuses past 65,535
  entries (the index map is u16). This is the mechanism the AUTO fix actually needed.
- **🔴🔴 THE FAILURE THAT MADE ROUND 5 A NO-OP, and it is a whole CLASS: `rebuild()` patched only
  keys it found while walking the EXISTING entries (`if k in patches`), so a key absent from the
  table was skipped SILENTLY — no warning, no count, build reports success.** Exactly one of the
  17,628 corpus keys was in that state: `PCDISPLAYSETTINGS_AUTO_UPPERCASE`, i.e. the entire
  round-5 fix. Now every absent corpus key is ADDED and listed, and the build **asserts**
  `added == len(add_keys) * 32`.
- **🔴 AND THE VERIFICATION WAS WORSE THAN THE BUG.** Round 5 "confirmed" the fix by counting the
  Hebrew word's bytes in the blob (`×56`) — but that word legitimately occurs in 56 unrelated
  entries, so the check could never fail and never proved the key existed. `validate_offline` now
  **simulates the engine's own lookup**: every entry must satisfy
  `hash(key) → bisect(sorted) → index_map == itself`, and **every corpus key must resolve through
  that path to the exact bytes `store_value` intended**. **UNIVERSAL: to verify a key-addressed
  change, run the CONSUMER'S OWN RESOLUTION — a substring search over the container proves
  nothing when the value is not unique.**
- **🔎 THE TABS: three more hypotheses KILLED with evidence, leaving exactly one route.**
  (a) *the keys are missing* — **false**, all four exist with real English values
  (`DISPLAY AND GRAPHICS` / `KEY MAPPING` / `MOUSE` / `CONTROLLER`);
  (b) *the config-doc supplies a hash that misses* — **false**, the doc's per-string hash equals
  the loc's hash **exactly** for every broken key (and the record layout is
  `[u32 len][u32 hash][string]\0`, so the round-5 "12-byte hash" was a misparse);
  (c) *they read a different localization asset* — **false**: Insomniac asset ids are
  `crc64(path)` (`dat1lib.crc64`, confirmed against `localization/localization_all.localization`
  → `0xBE55D94F171BF8DE`), and probing ~300 plausible localization paths against the toc's
  282,343 asset ids finds **exactly ONE** localization asset in the entire game.
  ⇒ the lookup cannot be failing. **Those widget classes draw the config-doc's own string RAW
  instead of localizing it** — so the only surface that can carry their Hebrew is the config doc.
  **UNIVERSAL: `crc64(path)`-probing a name list against the asset table is a cheap way to prove
  a resource does or does not exist, without enumerating 340K assets.**
- **THE ROUTE TAKEN — a delta-0 patch of the UI config-doc** (`work/rc_cfgpatch.py`): overwrite
  the label string in place with UTF-8 Hebrew **space-padded to the exact original byte length**,
  leaving `len` and `hash` untouched, so **no offset in the 129 KB document moves**. It ships
  through the identical index-redirect path already proven for the loc (`header_offset != -1`,
  `value = len(blob)`, blob = `asset[36:]`; verified `value + 36 == extracted length` for both
  the config asset and the loc). The patcher refuses any replacement longer than its slot,
  requires exactly one matching record per key, and `verify()` asserts **no byte outside the
  patched slots changed**. The raw-draw path's bidi mode is unknown, so the three tabs ship as an
  **A/B — DISPLAY+MOUSE VISUAL, KEY_BINDING LOGICAL**: whichever group reads correctly names the
  mode, and either way at least two tabs stop showing an ASCII key name.

---


