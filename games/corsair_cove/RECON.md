# Corsair Cove — RECON

| | |
|---|---|
| Install | `E:\Games\Corsair Cove` |
| Developer / publisher | **Limbic Entertainment** / **Hooded Horse** |
| Engine | **Unreal Engine 5**, `WinGDK` target (Microsoft-Store / Xbox GDK build) |
| Version | `1.1.1.0` (`MicrosoftGame.config`), StoreId `9PHS0189K408` |
| Shipping exe | `CorsairCove\Binaries\WinGDK\CorsairCove.exe` (173.8 MB) |
| Root exe | `CorsairCove.exe` (352 KB — a GDK launch stub) |
| Crack | RUNE (`RUNE_*.png` + `ms_emu.json` + `winmm.dll` proxy in `Binaries\WinGDK`) |
| Proposed `games.id` | **`corsair-cove`** (no existing catalog row — checked live, 47 rows, 0 hits) |

## Layout

```
Corsair Cove/
  CorsairCove.exe                gamelaunchhelper.exe  MicrosoftGame.config  appxmanifest.xml
  CorsairCove/
    Binaries/WinGDK/             CorsairCove.exe (real) + GDK/Wwise/DLSS dlls + the crack
    Content/
      Movies/Limbic.bk2          Splash/Splash.bmp
      Paks/                      <- everything below
    Plugins/                     Amd/FSR4  Nvidia/DLSS  Wwise
  Engine/  Resources/  _Redist/
```

## Containers

**Hybrid UE5: legacy `.pak` + IoStore `.ucas`/`.utoc`.** 29 chunk pairs, ~27 GB.
Every `.pak` is **v11 (Fnv64BugFix), NOT encrypted, no AES key, compression `None`**
(the IoStore side carries the compressed cooked assets).

| pak | size | entries | holds |
|---|---:|---:|---|
| `pakchunk0-WinGDK.pak` | 3.09 GB | 11,515 | **all loose files** — locres, StringTable CSVs, Config, Slate art, Wwise banks |
| `pakchunk0_s25-WinGDK.pak` | 101 MB | **18** | **the game's UI fonts** (`*.ufont`) |
| `pakchunk0_s27-WinGDK.pak` | 5.2 MB | 9 | the Engine font faces |
| `pakchunk20-WinGDK.pak` | 585 MB | 6,939 | Wwise `.bnk`/`.wem` |
| `pakchunk0_s1..s26` | 339 B each | 0 | empty stubs beside their IoStore container |

**`repak` 0.2.3 (already vendored at `games/hogwarts_legacy/tools/repak.exe`) reads AND
writes all of them with no key** → the container workstream is 100 % reuse from
Until Dawn / Hogwarts Legacy.

**The IoStore side is never needed**: every file we touch (locres, CSV, `.ufont`) is a
loose file in a legacy pak.

## Text

* `CorsairCove/Content/Localization/CoveGame/<culture>/CoveGame.locres` — **12 cultures**
  (`de en es fr it ja ko pl pt-BR ru zh-Hans zh-Hant`), UE **LocRes v3**.
* `CorsairCove/Content/StringTables/**/*.csv` — **172 developer CSVs**, and **171 of them
  are registered as RUNTIME string tables** (`DefaultGame.ini` `+StringTableCSVs=`), so the
  CSVs are read from file at runtime, not merely staged leftovers.
* `[Internationalization] +LocalizationPaths=%GAMEDIR%Content/Localization/CoveGame`
* `+CulturesToStage=` lists exactly those 12 — **no Arabic, no Hebrew**.

⚠️ `Content/StringTables/ST_Languages.csv` *does* carry an `Arabic` row ("Language name
used by text and audio options"), i.e. an RTL locale was once planned. It is **not**
in `CulturesToStage` and no `ar` locres ships — so it is a leftover, not a shipped slot.

## Fonts

`pakchunk0_s25-WinGDK.pak` → 18 `.ufont`, each `[u32 sfntSize][sfnt][4×00]`:

| face | outlines | Hebrew | role |
|---|---|---|---|
| `Alegreya-Regular` / `-SemiBold` | glyf | **0/27** | serif display |
| `AlegreyaSans-{Regular,Bold}-FixedNumbers` | glyf | **0/27** | sans UI |
| `Noto{Sans,Serif}{JP,KR,SC,TC}` ×14 | JP glyf, rest CFF | 0/27 | per-culture CJK fallbacks |

The Engine's own Slate fonts also ship loose in `pakchunk0` (Roboto ×10,
`NotoNaskhArabicUI`, `NotoSansThai`, `DroidSansFallback*`) — **all 0/27 Hebrew**.

## DRM / integrity

Clean. `CorsairCove.exe`: **0** hits for Denuvo / VMProtect / `.vmp` / EAC / BattlEye /
`tamper`. `SHA256` ×136 and `integrity` ×4 are stock UE crypto strings. PE sections are
ordinary and unpacked (`.text` 124 MB, `.reloc` 3.1 MB). No `.sig` pak-signature files.
