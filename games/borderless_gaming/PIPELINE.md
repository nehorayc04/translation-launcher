# Borderless Gaming — Hebrew — Pipeline

`games.id` / detector key: **`borderless-gaming`** · Steam appid **388080** ·
software (not a game mod), like VirtualDJ.

## Tools (`work/`)

| File | Role |
|---|---|
| `bg_lang.py` | codec — `flatten` / `unflatten` / `build_hebrew` / `dump`. Identity rebuild of all 30 shipped files is **byte-identical**. `selftest` included. |
| `build_reference.py` | builds the New-Era reference corpus (EN + ar/de/fr/ru/es/it per key) |
| `qa_scan.py` | the gate: coverage, `{0}`/`\n` multisets, niqqud, foreign script, bidi controls, untranslated leaks, cross-reference drift |
| `build_hebrew.py` | `--deploy` / `--revert` the real translation (runs `qa_scan` first and refuses to build if it fails) |
| `build_menu_proof.py` | the Phase-1 proof. Carries `real_appdata()` (env-redirection-safe) |

`hebrew.json` = the translation (`{"Dotted.Key": "Hebrew"}`, 343 keys).
`extract/en.json`, `extract/ar.json` = flattened corpora;
`extract/reference.{json,txt}` = the multi-language reference.

## Build

```bash
cd games/borderless_gaming
P=../../.venv/Scripts/python.exe

# corpus (re-extract after a game update)
$P work/bg_lang.py flatten "$BG/languages/en-US.json" extract/en.json

# build from a {"Dotted.Key": "Hebrew"} map
$P work/bg_lang.py build "$BG/languages/en-US.json" agent_handoff/hebrew.json out/he-IL.json
```

`build_hebrew` clones the English tree and swaps only leaves → the key set can
never drift (schema is `additionalProperties:false`); untranslated leaves stay
English, never blank.

## Deploy

Copy `out/he-IL.json` → `%APPDATA%\coreutils\borderless-gaming\languages\he-IL.json`
then pick **עברית** in Settings → Language (or set `"language": "he-IL"` in
`settings.json`).

- The install folder is never touched → Steam file verification can't revert it.
- Revert = delete the one file.
- Resolve AppData via `FOLDERID_Profile` + `AppData\Roaming`, **not** `%APPDATA%`
  and **not** `FOLDERID_RoamingAppData` — both are redirected in this environment.

## Rules for the translation

1. **Store LOGICAL Hebrew.** Avalonia runs the Unicode Bidi Algorithm. Never
   pre-reverse, never insert `&rlm;` / RLE / PDF.
2. **No niqqud.**
3. Preserve `{0}` / `{1}` / `\n` **exactly** (same multiset as the English).
4. Keep the key set identical — translate values only.
5. Product/brand names stay Latin: `Borderless Gaming`, `Steam`, `Discord`,
   `WinIgnore`, shader names (`FSR`, `Anime4K`, `CRT-Geom`, `Lanczos`, `CuNNy`,
   `FSRCNNX`), `Win`/`Ctrl`/`Shift`/`ScrollLock` key names.
6. `Language.Name` = `עברית`, `Language.Code` = `he-IL`.

## Glossary (locked, cross-verified against ar/de/fr/ru/es/it)

| EN | HE | note |
|---|---|---|
| Make Borderless | הסר מסגרת | ar `إزالة الحدود` / ru `Убрать рамки` = *remove* the borders |
| borderless mode | מצב ללא מסגרת | |
| Profile / Preset | פרופיל / פריסט | ru/es/it all borrow "preset" |
| Effect / Shader | אפקט / שיידר | |
| Scaling / upscaling | שינוי קנה מידה / הגדלת רזולוציה | |
| Frame | פריים | deliberately NOT מסגרת — that is "border" here |
| Overlay / Tray / Taskbar | שכבת-על / מגש המערכת / שורת המשימות | |
| Cursor / Capture / Latency / Tearing | סמן / לכידה / השהיה / קריעת תמונה | |
| Monitor, Display | צג | |
| Container / Gradient | מכל / מעבר צבע | |
| Borderless Gaming, Steam, Discord, WinIgnore, BGProxy, Win32, FP16, DirectFlip, HLSL, Vsync, shader names | stay Latin | |

Imperatives are 2nd-person masculine singular (Microsoft-Hebrew convention, and
what ar/de/ru use); a `Description`/`Tooltip` under a toggle is phrased as a
verbal noun, matching the reference languages.

## The SECOND text surface - shader metadata (effect editor)

The effect editor's category names, effect names, parameter labels and tooltips
are NOT in `languages/<code>.json`. They are authored as attributes inside the
107 `.slang` sources in the install folder:

```slang
[bgfx::EFFECT("CRT Easymode", 2)]
[bgfx::CATEGORY("CRT")]
[bgfx::PARAM("Sharpness Horizontal", 0.5, 0.0, 1.0, "Controls ...")]
```

720 unique strings / 26,909 chars. Proof that they are not in the exe:
`"Anti-Aliasing"` and `"Upscaling"` do not occur in `BorderlessGaming.exe`.

**Deploy = patch the compiled-effect CACHE, not the sources.** Three rounds of
in-app proofs established why:

1. A user-side `.slang` **does override** the installed one - the CRT tree
   showed `ZZ-A-LATIN-ZZ` / `ZZ-B-UESC-ZZ` in place of CRT Easymode / CRT Geom,
   still 5 entries, not 9.
2. But Hebrew never survives Slang's reflection step. Raw UTF-8, with and
   without a BOM, is rejected outright:
   `'3' is an invalid escapable character within a JSON string.
   Path: $.parameters[0]...userAttribs[0].arguments[0]` - the reflection JSON
   escapes non-ASCII with C-style OCTAL escapes (`\327`), which JSON forbids.
   `\uXXXX` is swallowed undecoded (it rendered as `05D705D3...`). All 107
   shipped shaders are pure ASCII, so upstream never exercised this path.
3. `cache/effects/*.bin` is a .NET `BinaryWriter` stream - every string is
   length-prefixed UTF-8, so Hebrew is legal there - and its validity key is the
   **SHA-256 of the SOURCE**, stored inside the cache. We never touch the
   source, so a patched cache stays valid and the app never recompiles.
   Confirmed in-app: category `סרט`, `ZZ-CACHE-OK-ZZ`, Hebrew parameter labels.

Format and patching rules live in `work/bg_cache.py`. Patches are anchored on
the Slang **variable name**, never on free text - 49 metadata strings occur more
than once (an effect name that equals a pass name, e.g. `CAS`), so a blind
search-and-replace would hit the wrong one.

```bash
python work/build_effects.py            # dry run
python work/build_effects.py --deploy   # runs qa_effects.py first, refuses on failure
python work/build_effects.py --revert
```

Idempotent: every entry keeps a pristine copy under
`%APPDATA%\coreutils\borderless-gaming\hebrew_backup\effects\` and the patch is
always built from that copy. **After a software update the sources change, the
cache is recompiled in English - just run `--deploy` again**; the tool notices
the new hash, refreshes the backup and re-applies.

Deliberately skipped: the 176 `PASS` names (`Conv-4x3x3x16`, `Depth-to-Space`)
are internal neural-network layer names; translating them is meaningless.

### Untranslatable by design (upstream gaps, do not chase)

| What | Why |
|---|---|
| Dropdown values (`Auto/Integer/Fit/Stretch/Fill`, Window Size Mode, Borderless Mode, Sync Mode) | C# enum names. **All 343 language keys were checked - the app has no `.Values`/`.Items`/`.Enum` convention anywhere**, so no dropdown value in the whole app is localizable. |
| `New Preset` (the default name of a new preset) | hardcoded literal in the exe; the *button* `EffectEditor.NewPreset` does have a key and is translated |
| Effect names like Anime4K / FSR / CuNNy / CRT Geom | intentional - brand and algorithm names stay Latin |

Patching the exe was rejected: a 71 MB single-file managed bundle, reverted by
every update and by Steam's file verification - the opposite of the property
that made the user-side deploy worth choosing.

## Phase 2 checklist

- [x] Menu proof confirmed in-app (discovery / font / bidi)
- [x] Lock the glossary
- [x] Translate all 343 strings (New-Era: every line cross-checked against ar/de/fr/ru/es/it)
- [x] QA scan clean (coverage 343/343, tokens, niqqud, foreign, bidi, cross-refs)
- [x] Build + deploy
- [ ] User confirmation in-app
- [ ] Publish like VirtualDJ: GitHub release repo + Worker slug `borderless-gaming-hebrew`
      + Supabase `games` row (`is_software=true`) + `mod_version_history`
- [ ] Optional launcher applier `translation_manager/borderless_gaming_mod.py`
      (copy one file in/out) + a `kind:"json"` language switch on `settings.json`

## מסמכים קשורים
- באותה תיקייה: [[games/borderless_gaming/FEASIBILITY|FEASIBILITY]], [[games/borderless_gaming/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#borderless_gaming|CLAUDE_INDEX_games]]
