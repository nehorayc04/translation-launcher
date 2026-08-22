# Assassin's Creed II — Hebrew translation PIPELINE

The concrete recipe. Mirrors the Universal Playbook (CLAUDE.md) but adapted to
AC2's no-bidi, char-index, DDS-atlas reality. **Path A** below uses AnvilToolkit
(GUI, on this machine) for the container round-trip; Path B (a full Python
repacker) is a later option.

Install: `D:\Games\Assassin's Creed II`. Forges: text = `DataPC.forge`,
fonts = `DataPC_extra.forge`. Tools: `games/assassinscreed2/tools` + `work`.
AnvilToolkit: `C:\Users\Nehoray_Cohen\Downloads\AnvilToolkit_Release_v1.2.10…`.

> ⚠️ Back up the original forges before ANY write:
> `copy "DataPC.forge" "DataPC.forge.he_backup"` (and `DataPC_extra.forge`).
> Ubisoft Connect "verify files" will revert a modded forge — re-apply after.

---

## Phase 0 — choose the slot (DECIDED 2026-06-18)

AC2 has no Arabic slot. **User decisions:**
- **Slot = a side language → `LocalizationPackage_Norwegian`** (index 46 in
  `DataPC.forge`; `Danish` index 45 is interchangeable). Keeps English readable for
  comparison while iterating. In-game: set Text language = **Norwegian (Norsk)**.
- **Repack = AnvilToolkit** (GUI-assisted; a few clicks per build). NOT a
  from-scratch Python repacker (that stays a future option).
- **Scope, phase 1 = UI / menus only** (`LocalizationPackage_Norwegian`, the
  non-`_Subtitles` package). Subtitles come later.

## Phase 1 — identity round-trip (PROVE the repack before investing)

1. AnvilToolkit → open game dir → unpack `DataPC.forge`.
2. Export `LocalizationPackage_English` → XML. **Import the SAME XML back
   unchanged** → repack `DataPC.forge`.
3. Launch AC2, set language = English → game boots with identical text.
   ✅ This proves the AnvilToolkit char-index + checksum repack chain works on
   this install before any translation. (Cross-check our reader: `python
   tools/ac2_forge.py "<game>\DataPC.forge" extract LocalizationPackage_English
   extract/loc_en.bin` and diff the re-packed one.)

## Phase 2 — Hebrew font glyphs (gate 2)

1. AnvilToolkit → unpack `DataPC_extra.forge` → open `AC2Aaux_ProBold_Latin_1_MapDesc`
   (and `_ProMedium_Latin_1`) in the texture viewer → export DDS.
2. `work/ac2_font.py` (to build) draws the 27 Hebrew letters (David/Heebo) into
   chosen atlas cells — either unused Latin slots or a repurposed CharacterSet —
   keeping the same cell metrics; writes the new DDS + records the
   codepoint→cell map used by the loc encoder. `texconv.exe` (in AnvilToolkit
   `Utils/`) handles DDS format. Verify visually in AnvilToolkit's viewer.
3. Import DDS back → repack `DataPC_extra.forge`.

## Phase 3 — translate + reverse (gate 1 content)

1. AnvilToolkit → export `LocalizationPackage_<slot>` → XML (the editable text).
2. `work/ac2_translate.py` (SM2-trio template): EN→Hebrew via the local LM,
   preserving every tag/placeholder; writes Hebrew back into the XML's values.
   Glossary = AC2/Ezio names stay Latin (Ezio, Auditore, Firenze, Altaïr…).
3. `work/ac2_rtl.py` `to_visual()` rewrites each Hebrew value into **visual RTL
   order** (numbers/Latin/tokens kept forward, brackets mirrored). Run ONCE.
4. (Glyph mapping) the visual Hebrew must use the codepoints the atlas glyphs were
   drawn at (Phase 2). If we draw Hebrew at its real Unicode block, values stay
   Hebrew; if we hijack Latin slots, map Hebrew→Latin codepoints here.
5. AnvilToolkit → import the new XML → repack `DataPC.forge`.

## Phase 4 — first proof + iterate

Start with the **highest-visibility UI** (main menu, pause menu, settings labels),
a handful of strings, full pipeline → launch → screenshot. Confirm: readable,
correctly-ordered Hebrew; numbers/Latin forward; no tofu (glyphs present). Iterate
on metrics/positioning like GoWR's font calibration. THEN scale to all strings,
then subtitles (`LocalizationPackage_<slot>_Subtitles`).

## Phase 5 — publish (when complete, same as SM2/CP2077)

GitHub release repo + manifest, Cloudflare Worker slug, Supabase `games` row +
`mod_version_history`, optional launcher card + `assassinscreed2_mod.py`
lifecycle. The mod ships as the modified `DataPC.forge` (+ `DataPC_extra.forge` for
the font); deploy = back-up-then-replace, re-apply after a Ubisoft verify.

---

## Tooling status

| File | Role | Status |
|---|---|---|
| `tools/ac2_forge.py` | scimitar-v25 forge reader/extractor | ✅ working, verified |
| `work/ac2_rtl.py` | Hebrew logical→visual RTL reversal | ✅ working, unit-tested |
| `work/ac2_translate.py` | EN→He LM translator (SM2 trio template) | 🟡 template — adapt I/O to AnvilToolkit XML |
| `work/ac2_watchdog.py` | self-healing LM supervisor | 🟡 template |
| `work/ac2_progress.py` | website progress push | 🟡 template |
| `work/ac2_font.py` | DDS atlas Hebrew glyph injection | ⛔ to build (Phase 2) |
| loc XML transform driver | wire translate+rtl over the XML | ⛔ to build (Phase 3) |
| Python loc repacker (Path B) | replace the AnvilToolkit GUI step | ⛔ future (RECON §2 head-start) |

## Open questions for the user

1. Which language slot to hijack (English vs a keep-English-visible option)?
2. OK to proceed with the **AnvilToolkit-assisted** flow (a few GUI clicks per
   build), or hold for a fully-scripted Python repacker first?
3. Scope: UI/menus only, or UI + subtitles (the subtitle package is ~larger)?

## מסמכים קשורים
- באותה תיקייה: [[games/assassinscreed2/FEASIBILITY|FEASIBILITY]], [[games/assassinscreed2/FORMAT|FORMAT]], [[games/assassinscreed2/RECON|RECON]], [[games/assassinscreed2/RESEARCH_SMALLSIZE|RESEARCH_SMALLSIZE]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#assassinscreed2|CLAUDE_INDEX_games]]
