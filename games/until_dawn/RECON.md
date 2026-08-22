# Until Dawn (2024 PC remake) — RECON

## Install

- Path: `F:\Games\Until Dawn` (FitGirl repack — `_Redist/fitgirl.md5` present,
  cracked `steam_api64.rne` under `Windows/Engine/Binaries/ThirdParty/Steamworks/`).
- Runnable exe: `Windows/Bates.exe` (small launcher stub) →
  `Windows/Bates/Binaries/Win64/Bates-Win64-Shipping.exe` (shipping/cooked build).
- Internal project codename: **Bates** (Ballistic Moon / Sony Interactive
  Entertainment — 2024 remake of the 2015 PS4 exclusive). `Bates.uproject`
  `EngineAssociation` GUID + `TargetPlatforms: [PS5, Windows, XSX]`, DLSS/FSR3/
  Nanite-adjacent plugins, `.crashdata`/Sentry SDK → **Unreal Engine 5**.
- No Denuvo / EAC / BattlEye found anywhere in the tree. Steam-emu crack only
  (single-player, no anti-cheat concerns for deploy).

## Container

- `Bates/Content/Paks/Bates-Windows.pak` (8.46 GB) + IoStore pair
  `Bates-Windows.{ucas,utoc}` (41.4 GB / 44.5 MB) + `global.{ucas,utoc}`.
- `.pak` = classic UE **PakFile V11** ("Fnv64BugFix"), **not encrypted**
  (`encryption guid: 00000000...`), compression Oodle, 154,974 entries —
  verified via `repak info`/`list`/`get` (`games/hogwarts_legacy/tools/repak.exe`,
  reused unchanged; already proven on Hogwarts Legacy's identical V11 format).
- **All loose/non-package files (Config `*.ini`, `Bates.uproject`, and —
  critically — every `.locres` + every `.ufont`) live in the legacy `.pak`,
  NOT in the IoStore container.** IoStore only carries cooked UAsset package
  chunks; loose files always ship via the classic pak. This means our entire
  translation target is reachable with `repak` alone — the 41 GB `.ucas` never
  needs to be touched or even parsed.

## Text

- `Bates/Content/Localization/Game/<culture>/Game.locres` — **20 LTR cultures**,
  **no Arabic, no Hebrew**: da, de, en, es-419, es, fi, fr, it, ja, ko, nl, no,
  pl, pt-BR, pt, ru, sv, tr, zh-Hans, zh-Hant (`DefaultGame.ini
  +CulturesToStage=`). `NativeGameCulture` unset → defaults to **en**.
- Format = standard Unreal **LocRes** (`FTextLocalizationResource`), version
  **3 = Optimized_CityHash64_UTF16** (confirmed from the magic+version byte).
  Spec ported from the public reference implementation
  `akintos/UnrealLocres` (`LocresLib/LocresFile.cs` — MIT-style, fetched and
  used to write `tools/ud_locres.py` read+write from scratch in pure Python;
  no C#/GUI tool needed).
- **All text lives in ONE StringTable namespace `ST_Localized`** — no MAIN/SUB
  split like Hogwarts Legacy; UI, settings, story dialogue subtitles, and
  making-of/bonus-material captions are all interleaved in the same file,
  distinguished only by key-name PREFIX convention (see PIPELINE.md).
- `en/Game.locres` = 1,027,040 B, **12,689 entries / 9,863 unique strings**
  (after string-table dedup). Every other locale is a **strict subset of the
  English key set** (0 extra keys anywhere) — English is the true source/
  superset, confirmed by set-diff across ru/ja/de/fr/pl/tr/nl (each missing
  1.2k–2.7k keys vs. en, presumably lines that never got that language's
  translation and fall back to the source string at runtime).
- The corpus is REAL, substantial dialogue (not a stub) — sample:
  `SMG013_59521` = `" ... I've looked down there... no way out."`, with
  `<Italic>…</Italic>` rich-text tags exactly like CP2077's markup style.

## Language settings (decisive finding)

`BATES_SETTING_GROUP_LOCALE`="Language" groups **three independent settings**:
- `BATES_SETTING_SPEECHLANG` = "Speech Language"
- `BATES_SETTING_SUBTITLELANG` = "Subtitle Language"
- `BATES_SETTING_TEXTLANGUAGE` = "Text Language"

Speech (voice audio) is decoupled from Text/Subtitle language — same pattern
as CP2077/SM2/WD2/GoWR. Whichever slot we hijack for Hebrew, English voice
acting is unaffected regardless of the chosen Text/Subtitle language.

## Font

- UI fonts are loose `.ufont` files under `Bates/Content/UI/Fonts/` — and,
  unlike every other cooked-asset case in this project, `repak get` returns
  them **byte-identical to a bare TTF/OTF file** (sfnt magic literally at
  offset 0). No uasset wrapper to parse at all — the simplest font case in
  the whole repo.
- Two main families: **Univers** (TrueType/`glyf`, 6 weights — UI/body text)
  and **Cotford** (CFF/PostScript, 3 weights — display/heading text), plus a
  `FallbackFonts/` tree with dedicated companions per script
  (`*_cyr`/`*_jp`/`*_kr`/`*_simp_ch`/`*_trad_ch`) — **no Arabic/Hebrew
  fallback exists**. `OpenDyslexic` accessibility font also present.
- cmap-verified: **0/27 Hebrew, 26/26 Latin** on every Univers/Cotford weight
  checked. Injection required.
- Univers (`glyf`) → Anno/TLOU-style glyph MERGE (fontTools
  `DecomposingRecordingPen`+`TransformPen`, preserves original Latin).
  Cotford (`CFF `) → glyf-merge is a no-op on CFF → REPLACE wholesale with a
  donor font, masquerading the `name` table (same technique as TLOU1's
  DINPro replace). Both implemented in `tools/ud_font.py`, verified
  27/27 Hebrew + 26/26 Latin preserved on both.

## No Arabic slot → LTR hijack (AC2/Anno/GTA/TLOU class)

No official Arabic/RTL locale exists anywhere in this game. Per the
playbook's non-Arabic-slot class, we hijack an existing LTR culture. It is
**not yet certain** whether the engine loads `en/Game.locres` as an override
when the active culture already equals the native culture (`en`) — some UE
projects skip loading the native locres and rely on the compiled-in source
text instead. The menu-proof (see PIPELINE.md) tests **both** `en` and a
non-native culture (`tr`) at once so a single deploy answers this
definitively, alongside whether Hebrew renders with correct bidi and via the
injected font.

## מסמכים קשורים
- באותה תיקייה: [[games/until_dawn/FEASIBILITY|FEASIBILITY]], [[games/until_dawn/PIPELINE|PIPELINE]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#until_dawn|CLAUDE_INDEX_games]]
