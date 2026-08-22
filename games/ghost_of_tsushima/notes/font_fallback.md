# GoT — CAN WE AVOID CRACKING `fOnk`? (OS/external-font fallback investigation)

Date 2026-07-07. All findings verified by running Python against the REAL
`GhostOfTsushima.exe` (29,284,984 B) + game data. Tools:
`work/font_fallback_probe.py`, `work/font_fallback_probe2.py`.

## VERDICT — NO. There is no cheap win. `fOnk` must be cracked.

The game has **TWO completely separate text subsystems**, and the OS/GDI font
path (the only path with automatic Hebrew glyph coverage) is confined to the
**launcher window** — it does NOT and cannot feed the **in-game** menu/subtitle
renderer, which is a self-contained GPU vector-font (`fOnk`) pipeline with **zero
OS involvement and zero glyph-level fallback**. There is no font config, no
per-language font selection, and no engine font-linking to exploit.

---

## The two subsystems (offsets in the exe)

### (A) LAUNCHER window — Win32 **GDI**, DOES get Hebrew for free
String cluster @≈0x10F2900 (contiguous NUL-separated keys):
`launcher_enabled` · `Launcher_Font` · `Launcher_Font_Version` ·
`Launcher_Icon` · `Launcher_Cursor_Arrow` · `Launcher_Bitmap_Background`
("Could not load background image, ensure file is A0R8G8B8…") ·
`Failed to register launcher window class` · `Failed to create launcher window`
· `GameWindow`. **Immediately after `Launcher_Font_Version` @0x10F29B8 is the
UTF-16LE facename `"MS Shell Dlg"`** — the GDI logical font the launcher passes
to `CreateFontW`.

GDI import cluster (each appears **once**, in the GDI32/USER32 import name
table @0x1475F00–0x1476010, as ONE offscreen-bitmap blit sequence):
`CreateCompatibleDC` · `CreateCompatibleBitmap` · `CreateFontW` ·
`AddFontMemResourceEx` · `RemoveFontMemResourceEx` · `SelectObject` ·
`SetTextColor` · `SetBkMode` · `GetTextExtentPointW` (measure) · `BitBlt` ·
`StretchBlt` · `SetStretchBltMode` · `GetDeviceCaps` · `GetStockObject` ·
`DeleteObject` · `DeleteDC` · `GetObjectW`.

Interpretation: the launcher `AddFontMemResourceEx()`-loads the `Launcher_Font`
blob (a game-data UI font resource — see "no sfnt" below), `CreateFontW(…,
"MS Shell Dlg")`, renders text into an offscreen DC, and `BitBlt/StretchBlt`s it
onto its window over `Launcher_Bitmap_Background`. **This is why the launcher
shows Hebrew: it is plain Windows GDI text, and GDI "MS Shell Dlg" gets
automatic Windows system font-linking (`FontLink\SystemLink`) — the OS
substitutes Hebrew glyphs from a system face for any codepoint the selected
font lacks.** This coverage is a property of the OS GDI path, not of the game.

### (B) IN-GAME renderer — proprietary **`fOnk` GPU vector font**, NO OS path
String cluster @0x1107F10–0x1278548: `FontGlyphs` · `FontVerts` · `SFontData`
· `FONTK` (= the `fOnk` chunk tag; the data resource is in
`game.sprig.texmeshman` @0x156BFF7, NOT in the exe) · `FONT_KIND` · `FONT_SIZE`
· `LARGE_FONT_SIZE_FACTOR`. Outlines tessellated to vertices → uploaded to the
GPU. The rendered glyph set is exactly what is baked into the `fOnk` resource;
a missing codepoint (Hebrew U+05D0–05EA) → notdef box = the tofu observed
in-game.

---

## Why (A) cannot rescue (B) — the checks that prove it

1. **No OS text-shaping / font-linking API in the whole exe.** ABSENT:
   `DirectWrite`/`dwrite`/`DWrite`/`IDWriteFactory`, `usp10`/`Uniscribe`,
   `FontLink`/`font_link`/`SystemFallback`, `AddFontResourceW/ExW`,
   `GetGlyphOutlineW`, `GetGlyphIndicesW`, `GetFontData`, `EnumFontFamiliesExW`.
   → the engine renderer has no code that would ask Windows for a fallback glyph.
   The GDI text APIs that DO exist appear exactly once each — in the single
   launcher blit sequence — never in a game-render context.

2. **The only 4 `*font*` strings besides the fOnk structs are the launcher
   keys** (`Launcher_Font`, `Launcher_Font_Version`). There is **no font config,
   no `.ini/.cfg/.json` font field, no per-language font resource selector, no
   registry font key**. On-disk config = only `steam_emu.ini` (the crack).
   Game settings live in registry `Software\Sucker Punch Productions\Ghost of
   Tsushima DIRECTOR'S CUT` + `Documents\…\*.log/.sav` — none carry a font path.
   → nothing to point at an external TTF.

3. **No glyph-level fallback exists.** The 4 `*fallback*` strings in the exe are
   all unrelated: `TalkToNpcUsedFallbackCamera`, `Countryside_fallback`,
   `SET_TELEPORT_FALLBACK_SCORING`, DirectStorage "using fallback", TLS
   `FALLBACK_SCSV`. **Zero** are font/glyph fallback.

4. **No embedded TTF/OTF to swap.** `sfnt`-header scan validated by real table
   tags over the exe = **0** valid fonts (confirms the earlier recon). The
   `Launcher_Font` blob is a game-data resource looked up by key (not present by
   ASCII name in the 55 `cache_pc` files or the 9 extracts — it is hashed inside
   a package), so even the launcher font is not a loose file to edit, and it is
   irrelevant to the in-game renderer regardless.

---

## Answers to the four sub-questions
- **(a) GDI/OS path for the in-game menu?** No. `CreateFontW` +
  `AddFontMemResourceEx` exist ONLY for the launcher window's GDI blit. The
  in-game menu/subtitle text never touches GDI or any OS font API.
- **(b) A font config the game reads?** No. No ini/cfg/json/registry font key,
  no per-language font selection. Nothing configurable.
- **(c) The launcher renders Hebrew — reusable?** The launcher renders Hebrew
  via **GDI `"MS Shell Dlg"` + Windows automatic system font-linking** (an OS
  feature, in the launcher subsystem). It is real, but **NOT reusable** for the
  in-game renderer: different code, GPU vector `fOnk`, no GDI, no OS font, no
  shaping/fallback library. There is no bridge/config between the two.
- **(d) Glyph-level fallback between font resources in the engine?** No — no
  DirectWrite/Uniscribe/FontLink and no font-fallback string anywhere.

## Consequence
The in-game menu is **pure `fOnk` vector with no OS fallback**. To render
Hebrew we MUST crack the `fOnk` format (SFontData / FontGlyphs / FontVerts,
compressed inside `game.sprig.texmeshman`) and inject 27 Hebrew glyph outlines
mapped to U+05D0–05EA (a sub-project). The `AddFontMemResourceEx` / launcher /
system-font-linking route is a dead end for in-game text.
