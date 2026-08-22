# 007 First Light — FEASIBILITY (2026-07-10)

## Verdict: 🟢 GO — strong, low-risk feasibility ("prove repack, then run")

The Glacier engine is the most-modded engine in this whole project's peer set, and — decisively —
**a full community Arabic localization already exists for this exact game** (Nexus #11: ~48k entries,
an injected Arabic font, full RTL + Arabic letter-shaping). That single fact retires the two gates
that historically cost the most everywhere else (RTL/bidi + a font that carries the script). **Hebrew
is strictly easier than Arabic** (RTL, but no cursive letter-joining/shaping). The container + text
codec are already cracked and validated in pure Python this session.

## Gate-by-gate

| Gate | Status | Notes |
|---|---|---|
| **Container read** | 🟢 DONE | `gl_rpkg.py` parses both 20/35 GB chunks with exact metadata consumption, 0 error. |
| **Text decode** | 🟢 DONE | `gl_locr.py`: 164/164 LOCRs decoded clean; real EN + all 14 langs extracted. |
| **Text encode (write)** | 🟢 DONE | LOCR ciphertext round-trip 119/119 byte-identical; Hebrew UTF-8 clean. 007 XTEA key recovered. |
| **Arabic slot?** | 🟡 NO official Arabic | 15 LTR/CJK slots → **LTR-slot hijack** (AC2/Anno/GTA/TLOU class), not an Arabic-slot. |
| **RTL feasible on engine?** | 🟢 PROVEN (community) | Nexus Arabic mod renders RTL in-game → Hebrew RTL achievable. **bidi = VISUAL (confirmed):** the Arabic mod is a PyInstaller installer that bundles `python-bidi` + `arabic_reshaper` → the engine does **NO bidi/shaping**, the mod bakes VISUAL order. Hebrew = visual-reverse, **no reshaping** (simpler than Arabic). |
| **Font has Hebrew?** | 🔴 almost certainly not | UI font = Scaleform **GFXF** (14 SWF DefineFont resources). Inject Hebrew — a **known, already-solved class** in this repo (Witcher 3 `swf_font.py`, GTA V Scaleform). Arabic mod proves injection works here. |
| **DRM / anti-cheat** | 🟢 clear | Cracked build (voices38 + Goldberg); Denuvo (exe-only) doesn't checksum RPKGs; no EAC. |
| **Deploy** | 🟡 needs identity round-trip | Glacier has a native **patch-RPKG** system; RPKG-Tool `first-light` + Simple Mod Framework + ZHMModSDK support it. Must prove a repack the game loads (Stage-5). |
| **Scope** | 🟢 known | ~7.3k LOCR (UI) + ~42k DLGE (dialogue) ≈ 49k. |

## Why LTR-slot hijack (not Arabic-slot)
The CLNG lists exactly 15 language slots (`xx en fr it de es ru mx br pl cn jp tc kr tr`), all LTR/CJK —
no `ar`. So we ship Hebrew inside one existing LTR slot's LOCR/DLGE strings + swap that slot's font,
exactly like AC2 (English slot), Anno (English), GTA V (American), TLOU (English). The user then sets the
game's Text Language to that slot. **Candidate sacrifice slot:** Turkish (14) or one of the Spanish/
Portuguese/Polish slots — a language a Hebrew player is unlikely to use; final choice in PIPELINE
(mirror whatever the Nexus Arabic mod hijacked, or pick least-used). English (slot 1) is the
lowest-friction alternative (nothing to change in Settings) at the cost of losing English text.

## bidi mode — VISUAL (confirmed from the Arabic mod)
The community Arabic mod (`Arabic Hesham 007 #11`) is a **PyInstaller onefile installer** that bundles
**`python-bidi` + `arabic_reshaper` + `fontTools`** (verified by statically extracting its CArchive —
`C:/tmp/arabic_mod`, no execution). That combo is the canonical "engine does NOT do bidi → pre-reshape
+ visual-reorder the text at build time" stack. So **Glacier stores VISUAL** — the mod bakes reversed
(and, for Arabic, letter-shaped) order into the strings. **Hebrew is simpler: visual-reverse only, no
letter-shaping.** Its translation payload is `data\payload.enc` (5.1 MB, encrypted — the translator's
own work; **we do NOT touch/extract it**, we build Hebrew from scratch). The menu-proof still confirms
in-game, but the mode is settled: **store VISUAL** (`gl_rtl.py to_visual`, reuse WD2/GTA `visual_line`).

## Risks / open items (none blocking)
1. **DLGE decode** — the dialogue/subtitle format (per-language subtitle + WAV/switch containers) is more
   complex than LOCR. Located; TonyTools `DLGE::Convert` is the reference. This is ~85% of the scope, so
   it must be cracked in Phase-1.5 before the big translation. (LOCR alone covers the UI proof.)
2. **Repack that the game loads** — Glacier's patch system + reference/hash-depends bookkeeping. RPKG-Tool
   `first-light` already generates loadable RPKGs (commit "[RPKG] Fix RPKG generation"); we either drive a
   pure-Python patch writer (preferred, playbook style) or accept RPKG-Tool as the packer.
3. **Font injection into GFXF** — Scaleform SWF; reuse the repo's proven SWF-font pipeline. Confirm the
   GFXF is standard SWF (extract one and inspect) before committing.
4. **Menu-proof** — one hijacked-slot LOCR patch + font, in-game, to lock VISUAL-vs-LOGICAL + font + repack.

## Bottom line
Everything hard about a brand-new 2025 AAA title is already de-risked: the container and text codec are
cracked and round-trip-proven in pure Python **today**, and a shipping community Arabic mod proves RTL +
font injection on this exact engine+game. This is one of the **strongest Phase-1 starts** in the project.
Next real work = DLGE decode + an identity-repack + a menu-proof screenshot; then delegate the ~49k
translation.

## מסמכים קשורים
- באותה תיקייה: [[games/007_first_light/PIPELINE|PIPELINE]], [[games/007_first_light/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#007_first_light|CLAUDE_INDEX_games]]
