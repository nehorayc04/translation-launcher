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
- No font swap. Hebrew renders with the engine's default Arabic glyph
  set, which has zero Hebrew coverage. If the test ships boxes/tofu
  instead of Hebrew letters, we'll need to also replace the Arabic font
  asset (similar to the Heebo swap from CP2077). This is the one piece
  of CP2077-equivalent work that didn't transfer 1:1.

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
