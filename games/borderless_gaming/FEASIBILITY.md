# Borderless Gaming — Hebrew — Phase-1 Feasibility

**Verdict: 🟢 GO — the easiest target in the entire project. ALL GATES CLOSED
in-app 2026-07-19 (menu proof PASSED, user screenshot).**
No container, no compression, no encryption, no repack, **no font work at all**,
no anti-cheat, no DRM. One loose JSON file, 343 strings.

| Gate | Status | Evidence |
|---|---|---|
| Container | 🟢 none | text is loose `languages/<code>.json`, plain UTF-8 |
| Codec | 🟢 built + proven | `work/bg_lang.py` rebuilds **all 30 shipped language files byte-identical** |
| Scope | 🟢 tiny | **343 strings / 10,284 EN chars** — a single-session translation |
| Discovery | ✅ **PROVEN in-app** | a `he-IL.json` we ADDED appeared as **עברית** in Settings → Language, and the `ZZ-BG-OK-ZZ` marker showed in the title → no Arabic hijack |
| Font | ✅ **PROVEN free** | `אפקטים` / `חיפוש חלונות...` rendered clean, **zero tofu** — system fallback covers Hebrew, no injection |
| bidi | ✅ **PROVEN LOGICAL** | the trailing `...` of `חיפוש חלונות...` rendered on the LEFT → store natural Hebrew, zero bidi code |
| Deploy | 🟢 user-side | ONE file in `%APPDATA%\coreutils\borderless-gaming\languages\` — install folder untouched |
| DRM / anti-cheat | 🟢 none | ordinary Steam utility (appid **388080**, app version 1.4.5) |

⚠️ One cosmetic finding from the same screenshot: **the app does NOT mirror its
layout** (no per-culture `FlowDirection`) — panels/labels stay LTR-aligned while
the text itself is correctly RTL. Not a blocker and not data-fixable from a
language file; judge it again once a full Hebrew pass is in.

---

## 1. The target

- Install: `F:\SteamLibrary\steamapps\common\Borderless Gaming` (Steam appid **388080**)
- Not a game — a Windows utility (borderless-window tool with an upscaling/shader layer)
- Framework: **.NET + Avalonia UI** (`libSkiaSharp.dll`, `av_libglesv2.dll`,
  `libHarfBuzzSharp.dll`, single-file `BorderlessGaming.exe` ≈ 71 MB)
- Proposed `games.id` / detector key: **`borderless-gaming`**

## 2. Text

`languages/` holds **30 language files + `schema.json`**:

```
ar-SA bg-BG cs-CZ da-DK de-DE el-GR en-US es-419 es-ES fi-FI fr-FR hu-HU
id-ID it-IT ja-JP ko-KR nb-NO nl-NL pl-PL pt-BR pt-PT ro-RO ru-RU sv-SE
th-TH tr-TR uk-UA vi-VN zh-CN zh-TW
```

Format — plain UTF-8 JSON, **2-space indent, CRLF**, no BOM, nested objects:

```json
{
  "$schema": "./schema.json",
  "Language": { "Name": "English", "Code": "en-US" },
  "TitleBar": { "Settings": "Settings", "Effects": "Effects" }
}
```

- **343 string leaves**, key sets across languages are **identical** (0 missing in ar-SA)
- Length profile: 239 ≤25 chars · 54 ≤60 · 46 ≤140 · 4 >140 — UI-dominant, no subtitles
- Tokens to preserve verbatim: **`{0}` ×23, `{1}` ×7, `\n` ×3**. Nothing else —
  no HTML, no `%d`, no bracket tokens, no gender variants.
- Top-level sections: `Language App TitleBar Windows Profiles Settings Shortcuts
  Dialogs Notifications Profile MatchType SizeType ContainerType WinIgnore Tray
  Common AreaSelector EffectEditor` (`Profile` alone is 141 = the shader/effects
  parameter surface).

⚠️ `schema.json` sets **`additionalProperties: false`** and lists every section as
`required` → the Hebrew file must carry **exactly the same key set** as `en-US.json`.
`bg_lang.build_hebrew` guarantees this (it clones the English tree and only swaps
leaves; anything untranslated falls back to English, never blank).

## 3. Add Hebrew — do NOT hijack the Arabic slot

Unlike every previous target, evidence says the language list is **discovered**,
not hardcoded:

- Each file carries its own `Language.Name` + `Language.Code` — exactly the
  metadata a picker needs from a scanned file.
- `es-419` (a shipped file) does **not** appear as a literal anywhere in the exe,
  so the shipped set is not a hardcoded table.
- The exe contains `"Failed to create languages directory"` and a `*.json` filter
  string, and the app **creates an empty `languages/` folder in `%APPDATA%`** on
  first run — a user-side override/extension folder.

⚠️ False positive to ignore: `he-IL` occurs 16× in the exe, but so does `ar-SA`,
and the surrounding bytes are the standard **.NET/ICU culture table**
(`uz|tt|pa|gu|…|ar-SA|bg-BG|…|he-IL|…`) — it proves nothing about the app.

⇒ Ship **`he-IL.json`** as a genuine Hebrew locale. Confirmed by the proof below.

## 4. bidi — expected LOGICAL, zero bidi code

The exe carries Avalonia's full Unicode Bidi Algorithm implementation
(`LeftToRightEmbedding`, `RightToLeftIsolate`, `PopDirectionalFormat`,
`FirstStrongIsolate`, …), i.e. text-run bidi is done by the framework — same
class as Hogwarts Legacy / Unreal. **Store natural Hebrew; never pre-reverse and
never inject `&rlm;`/RLE.**

Open sub-question, cosmetic only: whether the app sets **`FlowDirection`** per
culture (mirroring panels/alignment) or leaves it LTR. `FlowDirection` appears
only as an Avalonia type name, so it can't be settled statically — the proof's
mixed line + trailing colon show it.

## 5. Font — expected free

The app embeds only `Inter-{Thin,Light,Regular,Medium,SemiBold,Bold}.ttf` +
`Roboto-Light.ttf` as Avalonia resources. Inter has **no** Hebrew glyphs — but it
also has no Arabic, Thai, Chinese, Japanese or Korean, and the app ships all of
those. ⇒ it must already rely on **Skia/Avalonia system-font fallback**, which on
Windows resolves Hebrew (Segoe UI / David / Arial). So font work is expected to be
**zero** — the proof's Hebrew strings confirm it (readable vs tofu boxes).

## 6. Deploy — user-side, Steam-proof

Target: `%APPDATA%\coreutils\borderless-gaming\languages\he-IL.json`
(the app's own user config root, alongside `settings.json`, `profiles/`,
`effects/`, `presets/`).

- The **install folder is never touched** → Steam "Verify integrity of game
  files" cannot revert the translation, and no admin rights are needed.
- Removal = delete one file.
- Fallback target if the user folder turns out not to be scanned:
  `<install>\languages\he-IL.json` (same file, no other change).

⚠️ `%APPDATA%` is **redirected** under Antigravity, and so is
`FOLDERID_RoamingAppData`. Only **`FOLDERID_Profile`** returns the real home —
resolve that and append `AppData\Roaming` (`work/build_menu_proof.py:real_appdata`).

## 7. Language activation

`%APPDATA%\coreutils\borderless-gaming\settings.json` holds a flat
`"language": ""` key (empty = follow the system). So an in-launcher
Hebrew/English switch is a **one-key JSON edit** — the cleanest activation
mechanism of any target so far (a new `kind:"json"` for
`translation_manager/game_language.py`, or set it once at install).

## 8. Menu proof — ✅ PASSED in-app (2026-07-19), reverted

`python work/build_menu_proof.py --deploy` (revert: `--revert`)

Wrote `he-IL.json` (343 keys, 10 Hebrew leaves, rest English) to the user folder;
the user launched the app and screenshotted it. Results:

| Observed | Gate closed |
|---|---|
| **עברית** listed in Settings → Language | discovery works → ship a real locale, no Arabic hijack |
| Title bar showed **`ZZ-BG-OK-ZZ`** | the added file is genuinely loaded (font-independent proof) |
| `אפקטים`, `חיפוש חלונות...` clean, **no ▯** | system font fallback covers Hebrew → **zero font work** |
| the `...` of `חיפוש חלונות...` sat on the LEFT | **bidi = LOGICAL** — natural Hebrew, no pre-reversal, no `&rlm;` |
| everything else stayed English | the English fallback for untranslated leaves behaves as designed |
| panels/labels stayed LTR-aligned | app does **not** set per-culture `FlowDirection` — cosmetic only |

`--revert` removed the file and reset `settings.json` `"language"` back to `""`.
(If the app was open it may rewrite that on exit — then just pick English in the UI.)

## 9. Phase 2 (after the proof)

343 strings ≈ one pass — no fleet, no NIM streams, no gender oracle (a UI with
no dialogue; the few user-facing sentences are imperative/neutral). Build a small
agent handoff per [[delegate-all-translation]] (Claude builds tooling + glossary,
never translates), then `bg_lang.build_hebrew` → deploy → publish like VirtualDJ
(a software title, not a game mod).

Glossary decisions to lock before translating: Borderless / Profile / Preset /
Effect / Shader / Upscaling / WinIgnore / Tray / Overlay, and whether the product
name **Borderless Gaming** stays Latin (recommended: yes, like VirtualDJ).

## מסמכים קשורים
- באותה תיקייה: [[games/borderless_gaming/PIPELINE|PIPELINE]], [[games/borderless_gaming/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#borderless_gaming|CLAUDE_INDEX_games]]
