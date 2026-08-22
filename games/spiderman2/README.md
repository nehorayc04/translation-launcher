# Spider-Man 2 Hebrew translation — pipeline scaffold

Mirrors the structure of `games/cyberpunk2077/` and `games/steam/`.
**Status:** scaffold + working end-to-end test mod for the main menu.
Ready for, but not yet running, the LM-based mass translation pass.

## Engine background

Marvel's Spider-Man 2 uses Insomniac's `1TAD` (DAT1) asset pipeline + `DSAR`
container archives. Localization data sits in `d/localization` — a 103 MB
DSAR archive — with **31 variants** of the same logical asset
`localization/localization_all.localization` (asset id
`0xBE55D94F171BF8DE`). Each variant covers one shipped locale.

We identified the variants by parsing every variant's `ValuesSection` and
classifying the dominant Unicode script — script-frequency on the actual
strings, not byte-sniffing the noise floor. Result table is in
`work/06_classify_languages.py` output. **Variant 18 (entry index 1,276,510)
is the Arabic locale.** In the TOC's span table it lives in **span 144**,
position 1348.

The translation strategy is the same Arabic-slot hijack that worked for
Cyberpunk 2077: write Hebrew strings into the Arabic slot, ship it as a
mod, and have the user pick Arabic in `language.changer.exe`. The engine's
RTL/bidi pipeline (already validated for Arabic) renders Hebrew correctly.

## What was built

```
games/spiderman2/
├── README.md                          (this file)
├── tools/
│   ├── ALERT/                         ← Tkachov's dat1lib + dsar_codec (git clone)
│   └── Overstrike/                    ← Overstrike source (sparse: DAT1, LocalizationTool, OverstrikeShared)
├── extracted/
│   └── loc_variants/                  ← 31 raw .localization variants, dumped from d/localization
│       └── variant_18_idx1276510.localization   ← the Arabic one
├── work/
│   ├── 01..15_*.py                    ← step-by-step build pipeline (research → patch → pack)
│   ├── arabic.json                    ← 94,733 Arabic key→value pairs (full SM2 string table)
│   ├── arabic_patched_hebrew_menu.localization  ← Arabic file with 18 Hebrew strings injected
│   └── main_menu_candidates.tsv       ← candidates surfaced during the menu hunt
└── mod/
    ├── hebrew_main_menu_test.stage    ← Overstrike .stage (raw asset replacement)
    └── hebrew_main_menu_test.modular  ← Overstrike .modular wrapper (enables UI toggle)
```

The `.modular` was also copied into
`Game Lab/Marvel's Spider-Man 2/Mods Library/` so Overstrike picks it up.

### The 18 strings translated for the test

| Key | Hebrew |
|---|---|
| MENU_LOBBY_CONTINUEGAME_HEADER | המשך משחק |
| MENU_LOBBY_NEWGAME_HEADER | לפני שמתחילים |
| MENU_LOBBY_INITIALSETUP_HEADER | הגדרה ראשונית |
| MENU_LOBBY_ACCESSIBILITY_TITLE | ערכות נגישות |
| MENU_LOBBY_AUDIOCALIBRATION_HEADER | כיוון שמע |
| MENU_LOBBY_IMAGECALIBRATION_HEADER | כיוון תמונה |
| MENU_LOBBY_COMMONSETTINGS_HEADER | הגדרות נפוצות |
| MENU_LOBBY_ALLSETTINGS_HEADER | כל ההגדרות |
| MENU_AUDIO_HEADER | הגדרות שמע |
| MENU_LOBBY_APPLYPREORDER_TITLE | החל בונוסי הזמנה מוקדמת |
| BTN_ACCEPT | אישור |
| BTN_CANCEL | ביטול |
| BTN_CLOSE | סגירה |
| BTN_CONTINUE | המשך |
| BTN_MENU_BACK | חזרה |
| BTN_MENU_SELECT | בחירה |
| BTN_APPLY_CHANGES | החל שינויים |
| BTN_APPLYANDRELOAD | החל וטען מחדש |

All 18 verified by reading back the patched binary (`work/10_*.py`'s
`[OK]` rows).

## How to test (next step — handed to user)

1. **Set Spider-Man 2 to Arabic** with `language.changer.exe` (run it from
   the game folder, choose `1 arabic`). This swaps `steam_emu.ini` to ask
   the game for the Arabic locale.
2. **Open Overstrike** (`Overstrike.exe` next to the game). It auto-scans
   `Mods Library/`. You should see
   *Hebrew Translation — Main Menu Test* in the list.
3. Check its checkbox and press **Install mods**. Overstrike will rewrite
   `toc` and inject our DAT1 chunk into a new archive slot.
4. **Launch the game** (either via the Overstrike right-click menu or
   `Spider-Man2.exe` / `language.changer.exe`).
5. The Lobby header buttons + the universal Accept/Cancel/Close should now
   read Hebrew. The remaining 94,700+ strings stay Arabic (and untranslated
   from our perspective) until the mass-translation pass runs.

If the launcher crashes immediately or the strings stay Arabic, see
*Troubleshooting* below — we have known suspects.

## Known unknowns / things to confirm during the test

1. **Will Overstrike accept `format_version: 2`?** The
   `Spider-Gore.modular` example we cracked open uses
   `format_version: 1` at the `.modular` level and `format_version: 2`
   at the inner `.stage` level. We matched that.
2. **Will Overstrike's I29_V2 installer accept a raw DAT1 file without
   a `STG\0` magic wrapper?** Likely yes — the magic is conditional on
   asset type (textures wrap; bytecode/localization don't), but only the
   in-game test will prove it.
3. **Span 144 selection.** The mapping from the user's chosen locale
   ("arabic" in `languages.conf` / `steam_emu.ini`) to span 144 is what
   the engine does internally. If the game uses a different span for
   "arabic" on PC (vs. a console build's), our mod won't apply. The
   fallback is to ship the same patched file across multiple spans.
4. **Layout assumptions.** We rebuild the DAT1 file by:
   - Keeping the original section ORDER (not just tags).
   - Keeping the original section OFFSETS' alignment (16-byte) and the
     leading strings-table bytes verbatim.
   - Re-deduping the ValuesSection (45,103 unique values vs. however many
     the original had). If the game cares about a specific offset shape
     beyond the section headers, our file could be invalid. Symptom would
     be a crash on launch — verifiable by toggling the mod off.

## What's NOT in this commit (intentionally — handed off to the LM pass)

- The remaining ~94,715 strings are still Arabic. The next step would be
  to translate them via LM Studio + the CP2077 pipeline (same Gemma-2-27B
  + system prompt, adapted to Marvel/Spidey register).
- ~~No font swap.~~ **SOLVED — see "Font breakthrough" below.**

## Font breakthrough (2026-06-02)

Hebrew rendered as squares (▢) because **not one bundled font has a single
Hebrew glyph**. The fonts the UI actually uses are declared in a `UIFontMap`
config inside `d/config` (anchor string `fontmap`):

| Font asset (under `ui/loaded/authored/_common/fonts/`) | Role | HEB | ARA | LAT |
|---|---|---:|---:|---:|
| `AzbukaPro-Medium/-Bold/-Black.ttf` | primary menu face (CSS `font-family`) | 0/112 | 0/256 | 58/58 |
| `NeueFrutigerArabic-Regular.ttf` | RTL/Arabic-script fallback | **0/112** | 103/256 | 58/58 |
| `MagicSpellJF.otf` | decorative | 0/112 | 0/256 | 58/58 |

Arabic works (NeueFrutigerArabic covers it); Hebrew has no glyph anywhere →
tofu. **cohtml does NOT use DirectWrite** (no `DWrite` / `IDWriteFontFallback`
/ `AddFontMemResourceEx` strings); `RenoirCore` loads every face from a bundled
asset. The earlier v1–v4 swaps failed because they hit the **CJK fallback
fonts** (Arial Unicode MS + 2 Chinese, idx 15610/298871/396876/422626), not
these UIFontMap faces.

Each fontmap asset is located by **path-CRC64** (`crc64.hash(path)` →
`toc.get_asset_entries_by_path`); all live in `d\userinterface` (archive 185)
as **standard sfnt** (not the +36 Insomniac custom format the big fallback
fonts use). E.g. `NeueFrutigerArabic-Regular.ttf` = asset_id
`0x917B5481C0450B0F`, span 0, offset 59,955,392, size 95,744.

### The fix — `hebrew_font_v5.modular`

`work/59_build_hebrew_font_mod.py` builds an Overstrike `.stage`/`.modular`
replacing the primary + fallback faces with **Arial** (HEB 88/112, ARA
256/256, full LAT+CYR), so Hebrew renders via either the primary face or the
Arabic-script fallback chain:

| target asset | replacement |
|---|---|
| `AzbukaPro.ttf` (= family `AzbukaPro-Regular`, draws the **lobby header**) | `arial.ttf` |
| `AzbukaPro-Medium.ttf` | `arial.ttf` |
| `AzbukaPro-Bold.ttf` / `-Black.ttf` | `arialbd.ttf` |
| `NeueFrutigerArabic-Regular.ttf` | `arial.ttf` |

**First in-game confirmation (2026-06-02):** body text (`כל ההגדרות`,
`בחירה`) rendered in correct Hebrew; only the header was tofu because the
`@font-face` for family `AzbukaPro-Regular` points at file `AzbukaPro.ttf`
(no suffix) — initially missed. Adding that 5th face fixes the header.

### The header saga — duplicate Azbuka Pro + the full inventory

Even after swapping all 6 `_common/fonts/` faces (verified installed:
`64_verify_install.py` shows them remapped to `d\mods\mod0`), the lobby header
`המשך משחק` stayed tofu. `68_enumerate_all_fonts.py` extracted EVERY sfnt asset
in `d\userinterface` (33 fonts) and revealed why: there are **duplicate
"Azbuka Pro" copies at different asset paths** (idx 413228 / 8423 / 218848,
the lowercase `azbukapro_regular_normal.ttf` referenced by separate `@font-face`
blocks in docs 331186/414413) — the header uses one of THOSE, not the `_common`
copy. The 33 fonts also include CJK (`M 盈黑`), Korean (`Yoon Gothic`), DIN Next
CYR, Myriad Pro, Avenir Next Thai, and — notably — **`Aguda … for Insomniac`**,
a Hebrew-named face Insomniac already ships (but its cmap maps Hebrew glyphs to
ASCII slots, so it's unusable for Unicode Hebrew text).

`69_build_comprehensive_font_mod.py` swaps every non-Hebrew Latin/Cyrillic UI
face (21 assets, incl. all Azbuka Pro copies) — this finally made the header
Hebrew in-game (confirmed 2026-06-02).

### Final font — Heebo (v7)

Plain Arial looked too basic for SM2's UI. `71_build_heebo_font_mod.py` swaps
the same 21 faces with **Heebo** (clean modern geometric Hebrew family,
weight-matched Regular/Medium/Bold/Black), instanced from the Google Fonts
variable `Heebo[wght].ttf` via fontTools `instantiateVariableFont`. Output:
`hebrew_font_v7.modular` (~719 KB). The skip-list keeps CJK/Korean/Japanese
fallbacks, Arial Unicode MS, and Aguda untouched.

Stage key = `{span}/{asset_id:016X}` (all span 0). Deployed to
`Mods Library/hebrew_font_v5.modular`; stale `font_swap_all.modular` (v4,
wrong targets) removed.

**Test:** in Overstrike enable BOTH *Hebrew Translation — Main Menu Test*
**and** *Hebrew Font Swap v5*, Install mods, set Arabic via
`language.changer.exe`, launch. Lobby headers should read Hebrew, not squares.

Recon scripts: `52_full_font_inventory.py`, `53_cohtml_fallback_recon.py`,
`55_azbuka_context.py`, `56_dump_fontmap.py`, `57_locate_arabic_font.py`,
`58_verify_coverage.py`, `59_build_hebrew_font_mod.py`.

## Launcher / Settings localization (2026-06-02)

Hand-translated strings added to `10_build_patched_localization.py` (now 31
keys) so the boot launcher + the in-game language label read Hebrew:

| key | Hebrew | where |
|---|---|---|
| `LAUNCHER_PLAY` / `LAUNCHER_OPTIONS` / `LAUNCHER_QUIT` | שחק / הגדרות / יציאה | boot launcher window |
| `LAUNCHER_ENABLED(_UPPERCASE)` | הצג משגר | boot "show launcher" checkbox |
| `LANGUAGE_ARABIC`, `SETTING_LANG_TEXT_OPTION_ARABIC` | עברית | in-game Settings → Language label (the CP2077-style menu-name patch) |
| `TEXT_CONTINUE` / `TEXT_LOAD_GAME` / `MENU_LOBBY_PROLOGUEVIDEO_TITLE` / `MENU_LOBBY_VIEWCREDITS_TITLE` / `TEXT_QUIT_GAME` | המשך / טען משחק / בפרקים הקודמים… / רשימת יוצרים / צא מהמשחק | main lobby items |

`SETTING_LANG_VO_OPTION_ARABIC` (voice-over) left Arabic — audio isn't Hebrew.

### The native pre-game graphics config dialog reads our mod (confirmed)

Clicking "Settings" in the boot launcher opens a **native Win32 config dialog**
("…تهيئة" / Configure) — not cohtml. Its labels are localization keys
(`PCDISPLAYSETTINGS_*`, `PCGRAPHICSSETTINGS_*`, `SETTINGSCATEGORY_*`,
`LAUNCHER_OPTIONS_*`). We translated the ~28 visible ones as a probe and they
ALL rendered Hebrew in-dialog (2026-06-02) — proving **the native config tool
reads the Overstrike-modded localization archive**, and (being native Win32) it
renders Hebrew with the OS font, no font-mod needed. So every localization-backed
surface — in-game cohtml UI, boot launcher, AND the native config tool — is
translatable through the same `localization_all.localization` patch. The full
settings panel is ~1,159 keys (`SETTING_*` alone = 899); finishing it is the
LM mass-translation pass, not hand work.

### `language.changer.exe` must stay "arabic" — hard constraint

The RUNE `language.changer` reads `languages.conf` (dropdown list) and writes
the picked string verbatim to `steam_emu.ini` `Language=`. `Spider-Man2.exe`
holds a **hard-coded Steam-locale list** (`english…arabic,brazilian,greek,
latam…`); "hebrew" appears in the exe ONLY as a charset name (`ISO-8859-8`),
never as a language. So writing `Language=hebrew` makes `GetCurrentGameLanguage`
return an unrecognised value → the game drops to English and our Arabic-slot mod
never loads. The changer dropdown therefore MUST stay `arabic`; relabeling it is
not possible without patching the exe's locale table. Everything *inside* the
game is Hebrew regardless.

## Full settings-screen translation (2026-06-02, hand-translated, no LM)

Per the user's choice ("only the settings screens, no LM"), all visible
settings/config labels were hand-translated. Infrastructure:
`10_build_patched_localization.py` now merges an external
`work/settings_he.json` into the `HEBREW` dict and auto-derives every
`_UPPERCASE` sibling (Hebrew is caseless → identical text; non-existent ones
are safely skipped by the builder).

`settings_he.json` holds **480 keys** → **628 applied** (incl. the inline
config strings) across `SETTING_*`, `PCDISPLAYSETTINGS_*`,
`PCGRAPHICSSETTINGS_*`, `SETTINGSCATEGORY_*`, `SETTINGS_*`, `LAUNCHER_OPTIONS_*`
— every label/option/tab/header visible in the in-game Settings menu AND the
native config dialog. Placeholders/tags preserved verbatim (`%s`, `%d`,
`<span>`, `<br>`, `&rlm;`, `[ACTION_*]`). Latin tokens (HDR/DLSS/FSR/NVIDIA)
placed at the START of the logical string so the LTR-base native dialog renders
them at the visual END (correct RTL reading).

## RTL bidi root-cause fix — in-game descriptions (2026-06-04)

**Symptom:** multi-line Hebrew descriptions (PC Display/Graphics settings, etc.)
rendered with wrong bidi — Latin words jumped at line-wrap, spaces vanished at
HE/Latin seams, punctuation on the wrong side. Single-line labels were fine;
Arabic rendered fine (Arabic letters are strong-RTL and force the base
direction themselves).

**Root cause (proven by dumping all 1,321 textual UI assets → `extracted/ui_dump/`):**
the UI is **Prysm** scenes (`prysm.MovieClip` JS) styled by per-scene generated
CSS + shared `_common/css/Shared.css`. The description element is a
`<p class="…_2_3_0 alignNormalForLang settingsDescription">` with
`text-align:left` and **no text-direction**. The game's only RTL hook —
`SharedScript.js` (asset **350558**, `assetID B40AFA7568AA4412`, span 0),
function `UpdateViewForLangDirChange` — on an RTL locale sets
`--languageNormalAlignment:right` and stamps `cohinline` on every
`.alignNormalForLang` `<p>`, **but never sets `dir='rtl'`** (there's even a dev
TODO "may not catch everything"). So ICU (`cohtml_icuuc.dll`) computes the
paragraph base direction as **LTR** for Hebrew → wrong reorder.

**Key engine fact (proven in-game, 2026-06-04):** cohtml does **NOT** honor the
CSS `direction` / `unicode-bidi` properties (absent from the cohtml DLL
CSS-property table) **NOR the HTML `dir` attribute** for paragraph base
direction. A JS patch that stamped `dir='rtl'` on every `.alignNormalForLang`
`<p>` had **zero** in-game effect — mixed Hebrew/Latin runs still ordered
left-to-right (LTR base), the trailing period still landed on the right. What
cohtml's ICU engine **does** process is **Unicode bidi CONTROL characters** in
the text stream. So the base direction can only be set from inside the string,
not from markup.

**The fix that works — RLE..PDF embedding on every description:**
- `work/apply_rle_descriptions.py` wraps each of the **1,438** description
  values in **RLE … PDF** (`U+202B … U+202C`). RLE *raises the bidi embedding
  level to RTL* for the whole string, so the runs order right-to-left and the
  fix **survives soft line-wraps**. This is the decisive difference from a bare
  leading **RLM** (`U+200F`), which is only a *mark*: it nudges adjacent
  neutrals but never changes the embedding level, so with RLM the runs stayed
  LTR-ordered (the visible bug). Labels keep their own RLE wrap (single-line).
  Pure-Hebrew strings are unaffected either way.
- The JS `SharedScript.js` (350558) `dir='rtl'` patch is retained but is
  **inert** for base direction (kept only as a harmless belt-and-suspenders /
  re-layout nudge). The real lever is the RLE control char in the localization
  value. `work/css_rtl_patches.json` + `work/80_build_css_rtl_mod.py` still
  bundle it; it does no harm.
- Earlier dead ends (all ineffective or worse, in-game): `<span dir='rtl'>` /
  `<div dir='rtl'>` (tripped the Prysm `InnerHTMLInlineSpan` NBSP quirk
  I30-73231; markup `dir` ignored anyway), `unicode-bidi:plaintext`/`direction`
  CSS (unsupported), LRI/PDI isolates (ignored), bare RLM prefix (mark only),
  ALM `U+061C`.

**Packaging:** `work/80_build_css_rtl_mod.py` bundles the JS stage
(`0/B40AFA7568AA4412`) + the localization stage (`144/BE55D94F171BF8DE`) into
one `mod/hebrew_full.modular` (deployed to the Mods Library). Span/assetID format
matches the known-working `hebrew_font_v7.modular` (`0/<HEXID>`).

**Verification (offline, before enabling):** UBA simulation (`python-bidi`) over
all 1,434 descriptions — `work/90_bidi_sim.py` (paragraph) +
`work/91_bidi_linewrap.py` (line-wrap): **0 Latin-word failures**, correct
multi-line RTL output. DAT1 integrity `work/92_dat1_integrity.py`: 94,733
entries, 0 decode failures, 0 double-RLM, 0 leftover wrappers, 0 markup lost.
A 6-agent adversarial panel (`work/wf_verify.js`) independently re-derived every
fact from raw bytes → **GO, 0 blockers, 93%**. The one offline-unprovable item:
UBA rule **L4** bracket-mirroring on 22 Hebrew-content parentheticals
(`(שונה ממצב צילום)` …) — ICU applies L4 by default, worst case a cosmetic
bracket flip, no text loss.

**Activation:** in-game **Settings → Language = العربية (Arabic)** is a hard
precondition — the mod writes only the Arabic span (144); any other language
shows no Hebrew. Re-verify span/assetID after any game update (a TOC change can
shift indices).

**Not yet translated** (deferred): the 330 `_DESC` tooltip paragraphs and the
`_TOK_` templated control-hint fragments (button-glyph splits). These are
help/tooltip text, not the primary visible labels.

### Full menu translation (hand-translated, batched, no LM) — 2026-06-02

Per the user's "translate every menu, not the subtitles" directive, the whole
menu/UI surface is being hand-translated in batches, each merged into the build
via `10_build_patched_localization.py` (loads `settings_he.json` +
`menus*_he.json` and auto-derives `_UPPERCASE`). Placeholders preserved
verbatim: `[ACTION_*]`/`[BTN_*]` button glyphs, `<span class='emphasis'>`,
`<br>`, `&rlm;`, `&nbsp;`, `%s`/`%d`/`%u`. Dialogue/subtitles, text-message
threads (`TEXTMSG_*`), and long lore documents are intentionally skipped (LM
phase).

| file | scope | strings |
|---|---|---|
| `settings_he.json` | all Settings + native config dialog | 480 |
| `menus_he.json` | pause-menu tabs, map, buttons, save slots, PSN | 534 |
| `menus2_he.json` | HUD, moves list, photo mode, interaction prompts | 885 |
| `menus3_he.json` | tutorials (`TUT_*`) + combat help (`HELP_*`) | 648 |
| `menus4_he.json` | photo-mode stickers (`STICKERS_*`) | 577 |
| `menus5_he.json` | mission objectives (`OBJ_*`) | 879 |
| `menus6_he.json` | inventory names — suits/gadgets/skills/items/trophies/benchmarks/UI/setting-tooltips | 1,130 |
| `menus7_he.json` | long descriptions — gadget/skill/suit-mod/accessibility/setting/trophy/UI-help | 336 |
| `menus8_he.json` | lobby (`MENU_LOBBY_*`), Steam↔PSN linking (`PSPC_*`), photo collectibles, save/load menu | 109 |

**MENU TRANSLATION COMPLETE (2026-06-02).** Applied **5,658 keys**; a fresh
coverage scan confirms **0 remaining menu-prefix strings** (`SUIT/GADGET/SKILL/
ITEM/TROPHY/BENCHMARK/UI/STICKER/PAUSE/SETTING/MENU/BTN/HUD/TUT/HELP/MOVES/
PROMPT/PHOTO/OBJ/MAP/PSPC/TECHBOX` all done). Note: the `INV_*` prefix turned
out to be **empty** basketball-minigame voice-callout stubs, not inventory —
the real suit/gadget/skill content lives under `SUIT_/GADGET_/SKILL_/ITEM_`,
all now translated.

## What's NOT in this commit — the LM pass

- The remaining **~36,682** non-empty strings are all **dialogue / subtitles**
  (SPID, SPIM, character conversations, `TEXTMSG_*` phone SMS, and the long
  in-world lore documents — Harlem-exhibit bios, Kraven's journal, the Book of
  Flame, dossiers, legal splash). These are reserved for the LM pass, per the
  user's instruction "translate the menus, leave the subtitles for LM Studio".
  Next step: translate via LM Studio + the CP2077 pipeline (Gemma-2-27B,
  adapted to Spidey register).

## Re-running any step

Every step is an idempotent Python script under `work/`. From there:

```powershell
python -X utf8 01_probe_toc.py            # sanity-check the toc
python -X utf8 04_extract_all_locs.py     # re-extract all 31 variants
python -X utf8 06_classify_languages.py   # re-prove which is Arabic
python -X utf8 07_dump_arabic.py          # rebuild arabic.json
python -X utf8 10_build_patched_localization.py  # rebuild the .localization
python -X utf8 15_build_stage.py          # rebuild the .stage / .modular
```
