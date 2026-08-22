# Borderless Gaming — Recon (read-only)

Date: 2026-07-19 · Install `F:\SteamLibrary\steamapps\common\Borderless Gaming`
Steam appid **388080** (`steam_appid.txt`). No game files were modified during recon.

## Install layout

```
BorderlessGaming.exe      71.8 MB   single-file .NET + Avalonia
appcontainer.exe           2.2 MB
av_libglesv2.dll           4.4 MB   Avalonia ANGLE
libSkiaSharp.dll           9.4 MB   Skia (text/graphics)
libHarfBuzzSharp.dll       1.6 MB   shaping
steam_api64.dll
languages/                 30 language JSONs + schema.json   <-- the target
presets/                   *.bgfxp shader presets + preset.schema.json
effects/                   *.slang shaders (Anime4K, FSR, CRT, CuNNy, FSRCNNX, …)
```

## User config root

`%APPDATA%\coreutils\borderless-gaming\`

```
settings.json      flat config, has  "language": ""   <- activation key
.winignore
languages/         EMPTY, created by the app on first run  <- deploy target
profiles/  presets/  effects/  cache/  logs/  Sentry/
```

`logs/bg-<yyyymm>.txt` exists (no language lines yet).

## Exe string findings (targeted scan, not a dump)

| Query | utf-8 | utf-16 | Reading |
|---|---:|---:|---|
| `languages` | 6 | 2 | incl. **"Failed to create languages directory"** |
| `*.json` | 0 | 1 | in a filter list next to `*.slang`, `*.png` |
| `es-419` | 0 | 0 | shipped file names are **not** hardcoded → folder is scanned |
| `ar-SA` / `he-IL` | 0 | 16 / 16 | ⚠️ both from the .NET/ICU culture table — proves nothing |
| `RightToLeft` / `LeftToRight` | 5 / 4 | 0 | Avalonia bidi enum + full UBA class names |
| `FlowDirection`, `FontFallback`, `FontManager` | 1 each | 1 | Avalonia type names only |
| `Inter` | 1474 | 119 | `/Assets/Inter-{Thin..Bold}.ttf` + `Roboto-Light.ttf` embedded |
| `Noto`, `Segoe`, `Heebo`, `Rubik` | 4 / 0 / 0 / 0 | — | no Hebrew face bundled |

## Text corpus (measured)

- 343 string leaves, **10,284 EN chars**; ar-SA has the **same 343 keys**, 0 missing
- tokens: `{0}` ×23, `{1}` ×7, `\n` ×3 — nothing else
- lengths: 239 ≤25 · 54 ≤60 · 46 ≤140 · 4 >140 (UI only, no subtitles)
- sections (count): Profile 141, Notifications 35, EffectEditor 25, Dialogs 23,
  Settings 21, Windows 20, Profiles 18, Shortcuts 16, TitleBar 8, WinIgnore 8,
  AreaSelector 6, MatchType 5, Common 4, ContainerType 4, Tray 3, SizeType 3,
  Language 2, App 1

## Codec verification

`work/bg_lang.py` identity-rebuilds **all 30 shipped language files
byte-for-byte** (2-space indent, UTF-8 no BOM, CRLF, non-ASCII literal).

## Environment trap hit during recon

`%APPDATA%` **and** `SHGetKnownFolderPath(FOLDERID_RoamingAppData)` both return
the Antigravity sandbox profile
(`…\AntigravityProfiles\translation-profile3\AppData\Roaming`). Only
**`FOLDERID_Profile`** returns the real `C:\Users\Nehoray_Cohen`. Any user-side
path must be built from FOLDERID_Profile. [[env-redirection-real-home]]

## מסמכים קשורים
- באותה תיקייה: [[games/borderless_gaming/FEASIBILITY|FEASIBILITY]], [[games/borderless_gaming/PIPELINE|PIPELINE]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#borderless_gaming|CLAUDE_INDEX_games]]
