# Ghost of Tsushima DC — FEASIBILITY (Phase 1)

## Verdict: 🟡 GO-WITH-CAVEATS — "prove the two gates, then run" (medium–hard tier)

Everything on the **container / text / deploy** axis is SOLVED and proven; the **font** is the one hard,
uncertain gate, and **bidi** is a leans-LOGICAL that needs one in-game test. Both remaining gates are closed by a
SINGLE menu-proof launch (`work/build_menu_proof.py`), already built + validated offline.

| Gate | Status | Notes |
|---|---|---|
| Container (DSAR→PSARC) | 🟢 SOLVED | identical to TLOU2; `dsar.py` reads, `psarc_write`+`dsar_write` rebuild — round-trip PASS |
| Text format (KCAP `.xpps`) | 🟢 CRACKED | `tools/xpps.py` reads EN/AR; surgical override works; identity round-trip byte-identical |
| Arabic slot (RTL hijack) | 🟢 EXISTS | `lang_arabic_text.xpps` 17 MB, official locale, stored LOGICAL |
| Deploy | 🟢 SOLVED | override `.psarc` in `cache_pc/psarc/`; no gapack rebuild; DRM-free/no anti-cheat |
| Repack round-trip | 🟢 PROVEN | semantic byte-exact on `gapack_misc_p`; **free growth, no delta-0 pad** |
| **bidi mode** | 🟡 LEANS LOGICAL | Arabic stored logical + `python-bidi` reorders it → engine bidis; **menu-proof decides** |
| **font (Hebrew glyphs)** | 🔴 THE GATE | proprietary compressed `fOnk` vector font, no Hebrew; needs a crack+inject sub-project |

## Why GO
- **Arabic-slot hijack applies** — an official Arabic text locale ships (`lang_arabic_text.xpps`), so Hebrew
  inherits the engine's tested RTL path (pending the bidi confirmation below).
- **Read AND write are both done in pure Python** — the container is byte-for-byte the TLOU2 stack (reader +
  writers reused unchanged), and the KCAP `.xpps` codec is cracked with a byte-identical identity round-trip and a
  working surgical override. **No GUI tool, no closed dependency, no repacker gap** (unlike AC Shadows v42).
- **Deploy is light + reversible + safe** — drop ONE small override `.psarc` (sorting after `gapack_misc_l`) into
  `cache_pc/psarc/`; the engine's alphabetical mount overrides the packed `/lang_arabic_text.xpps`. The 1.43 GB
  gapack is never rebuilt; the 55 shipped archives are untouched; revert = delete one file. **RUNE crack,
  DRM-free, no Denuvo/EAC, PSARC has no whole-archive checksum** → asset edits load (whole GoT Nexus mod scene
  proves it). Free growth → Hebrew may exceed the 17 MB Arabic slot.
- **Precedent:** non-shipped-language fan translations already load in this game (Austronesian pack; commercial
  Persian RTL localization).

## The caveats (open gates)
1. **bidi (🟡, cheap to close).** The Arabic is stored in logical reading order (a `python-bidi` `get_display`
   reorders it), which strongly implies the engine applies bidi at draw time → **store Hebrew LOGICAL** as the
   working hypothesis. But an official Arabic slot does NOT guarantee Hebrew rides the same pass (Witcher 3: shipped
   Arabic logical+RLO yet Hebrew needed VISUAL; GoWR: engine gated the Hebrew codepoint range). The menu-proof
   patches some keys LOGICAL and some VISUAL — one screenshot decides.
2. **font (🔴, the real risk).** The UI/subtitle glyphs live in a **proprietary, compressed `fOnk` vector-font**
   resource (`SFontData`/`FontGlyphs`/`FontVerts`), NOT a TTF and NOT a DDS atlas. Arabic is covered; Hebrew almost
   certainly is not. If the menu-proof shows tofu, we need a **`fOnk` sub-project**: crack the compressed
   glyph-vertex format + codepoint→glyph map, inject Hebrew outlines (`U+05D0–05EA`), repack `game.sprig.texmeshman`.
   This is harder than the SM2/WD2/GoWR font work (those were DDS atlases / bitmap or a TTF); a proprietary vector
   format with no OS font-linking fallback is the genuine unknown. There is a chance the engine falls back to a
   system font or the `fOnk` already carries a broad range — the menu-proof settles it.

## The one action that closes both gates
`python games/ghost_of_tsushima/work/build_menu_proof.py --deploy` → launch → Settings → Options → General →
Text Language = العربية. Read the main menu:
- **CONTINUE = "ZZ-GOT-OK-ZZ"** (Latin) → the override `.psarc` mounts (font-independent proof of load).
- **New Game / Load Game / Options** (stored LOGICAL Hebrew) vs **Subtitles** (stored VISUAL Hebrew):
  - LOGICAL ones correct → **bidi=LOGICAL** (store logical). VISUAL one correct + LOGICAL reversed → **bidi=VISUAL**.
  - Any Hebrew as **tofu/boxes** → font lacks Hebrew → the `fOnk` injection sub-project is required.
Revert: `--revert`.

## If the font gate blocks
Fallbacks, best-first: (a) crack + inject `fOnk` (the proper fix); (b) check whether a system/OS font fallback can
be forced; (c) if injection proves infeasible, the project stalls at the font like AC Shadows stalled at the v42
repacker — text/deploy would be ready, font pending a breakthrough. Recommend attempting the menu-proof FIRST
(it may show the font already renders, collapsing the risk to zero) before investing in cracking `fOnk`.

## מסמכים קשורים
- באותה תיקייה: [[games/ghost_of_tsushima/PIPELINE|PIPELINE]], [[games/ghost_of_tsushima/RECON|RECON]], [[games/ghost_of_tsushima/RESEARCH_FONT|RESEARCH_FONT]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#ghost_of_tsushima|CLAUDE_INDEX_games]]
