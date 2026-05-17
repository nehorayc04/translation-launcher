### Current Status

**Cyberpunk 2077 Hebrew Translation Project — WORKING (2026-05-10)**

Hebrew rendering achieved via the **Arabic-slot approach**: Hebrew CR2W files placed under
`base/localization/ar-ar/` instead of `en-us/`, with the Arabic font replaced by Heebo.
Game language must be set to **Arabic** in settings — the game then routes Hebrew text
through CDPR's tested Arabic RTL/bidi pipeline.

Direct font replacement in en-us/raj path crashes the engine. Arabic-slot routing works.

**Deployed mod:**
- Path: `Cyberpunk 2077\archive\pc\mod\z_hebrew_translation.archive` (3.82 MB)
- MD5: `dc7e6a9e564435558e281653a0f771a8`
- Contents: ar-ar/onscreens (2 files, Hebrew CR2W) + Heebo Arabic font replacement

**User-side requirement:** Settings → Language → set Interface to Arabic (العربית) → restart game.

### Working pipeline (replay any time)

1. **Extract pristine Arabic CR2W skeleton:**
   ```
   WolvenKit.CLI.exe extract <game>/archive/pc/content/lang_ar_text.archive -o <work>/ar_pristine -w "*onscreens.json"
   WolvenKit.CLI.exe extract <game>/archive/pc/content/lang_ar_text.archive -o <work>/ar_pristine -w "*onscreens_final.json"
   ```

2. **Serialize CR2W → text JSON:**
   ```
   WolvenKit.CLI.exe convert serialize <work>/ar_pristine/base/localization/ar-ar/onscreens/onscreens.json -o <work>/text
   ```

3. **Apply Hebrew translations** (modifies femaleVariant/maleVariant by primaryKey lookup):
   ```
   python cp2077_apply_translations_to_wkit_json.py <work>/text/onscreens.json.json onscreens/onscreens.json
   ```

4. **Deserialize text JSON → CR2W:**
   ```
   WolvenKit.CLI.exe convert deserialize <work>/text/onscreens.json.json -o <work>/encoded
   ```

5. **Build project:**
   ```
   <project>/source/archive/base/localization/ar-ar/onscreens/onscreens.json   ← from <work>/encoded
   <project>/source/archive/base/gameplay/gui/fonts/foreign/arabic/ara_es_nawar/araesnawar-regular.fnt
   ```
   The Arabic font .fnt is built by importing a stripped-Heebo TTF via WolvenKit `import -k`.

6. **Pack and deploy:**
   ```
   WolvenKit.CLI.exe pack <project>/source/archive -o <project>/packed/archive/pc/mod
   cp packed/archive.archive → Cyberpunk 2077/archive/pc/mod/z_hebrew_translation.archive
   ```

### Current scope

- ✅ Onscreens (UI text, settings, menus): 88,839 + 252 = ~89k Hebrew translations live
- ⚠ Subtitles (3,083 files): still vanilla English — the same pipeline applies if extended

### Working files

- `cp2077_apply_translations_to_wkit_json.py` — applies Hebrew text to a WolvenKit-decoded JSON skeleton
- `make_static_heebo.py` — extracts static TTFs from variable Heebo
- `fix_heebo_tables.py` — strips OpenType layout tables from Heebo (avoids shaper crashes)
- `localization_translated.json` (32 MB) — source Hebrew translations, keyed by primaryKey
- `cp2077_extract.py`, `cp2077_translate.py`, `cp2077_fix_missing_translations.py` — original translation pipeline
- `cp2077_lqa_check.py`, `verify_translation.py` — QA scripts

### Failed scripts (don't use)

- `cp2077_inject.py` — the original Python CR2W injector. Produces files that load but crash the engine. The WolvenKit canonical pipeline replaced it.
- `cp2077_font_pipeline.py` — has a contamination bug; just use the per-font import logic shown in the working pipeline above.

### Why the Arabic-slot approach works

CDPR's engine has a hardcoded language-aware text pipeline. Setting Interface=Arabic activates:
1. Loading text from `base/localization/ar-ar/` (where we placed Hebrew strings)
2. RTL bidi processing (works for Hebrew chars too — same Unicode bidi class)
3. Loading the Arabic font (`foreign/arabic/...`) — where we put Hebrew Heebo glyphs
4. The shaping/rendering path that doesn't crash on RTL non-Latin glyphs

Putting Hebrew CR2W files in en-us/ + Heebo as raj font does NOT trigger this pipeline →
the engine tries to render Hebrew through the Latin path → crash.

### Backup

Final working files preserved at `backup_translation_2026-05-10\final_arabic_slot\`:
- `z_hebrew_translation.archive` (deployed mod)
- `Heebo-Regular.ttf` (stripped, used for font import)
- `cp2077_apply_translations_to_wkit_json.py` (working applier)
- `README.txt` — restore + language-switch instructions

### History

- 2026-05-01 — extraction complete (cp2077_extract.py)
- 2026-05-02 — cp2077_inject.py v4 — produced loadable files but crashed at runtime (later replaced)
- 2026-05-09 — translation complete; LQA pass; multiple inject failures; identified the en-us/raj path crashes
- 2026-05-10 — switched to WolvenKit canonical encode/decode (`convert serialize/deserialize`), then to Arabic-slot routing — Hebrew rendering finally working
- 2026-05-17 — Empty settings footer buttons (RESET/DEFAULTS/APPLY) fixed. Root cause: LocKey#23204/5/6 missing from both sections of `localization_translated.json`. Vanilla Arabic strings from `lang_ar_text.archive/onscreens_final.json` were passing through to the widget; Hebrew Heebo font has no Arabic letter glyphs → invisible. Added 3 entries (`ברירות מחדל` / `איפוס` / `שמור שינויים`). NOT a font, widget-layout, or RTL bug — pure translation gap. Lesson: when a string is missing from our translations, the engine falls back to the vanilla locale text, NOT to nothing — debugging in this project must distinguish "rendered as invisible" (font/glyph) from "rendered as wrong-locale-text-that-our-font-can't-render" (translation gap).

### Open tasks (future)

- [ ] (Optional) Extend coverage to subtitles via same Arabic-slot pipeline (~12 hours of CLI batch processing)
- [ ] (Optional) Handle Phantom Liberty DLC text in `archive/pc/ep1/lang_ar_text.archive`

### Technical Decisions

- **Localization slot**: `base/localization/ar-ar/` (NOT `en-us/`) — only Arabic pipeline accepts Hebrew without crash
- **Font slot**: `base/gameplay/gui/fonts/foreign/arabic/ara_es_nawar/araesnawar-regular.fnt` — Arabic font replaced by Heebo
- **Heebo TTF prep**: must be static (no `fvar`/`gvar`/`STAT`) and stripped of OpenType layout (`GSUB`/`GPOS`/`GDEF`) to avoid shaper edge cases
- **CR2W workflow**: WolvenKit's `convert serialize/deserialize` is the only safe round-trip — direct binary patching breaks header CRCs / table offsets in subtle ways
- **Mod filename**: `z_hebrew_translation.archive` — `z_` prefix loads after vanilla archives so our overrides win
- **Game language**: must be Arabic in user settings; English language ignores the ar-ar files entirely
