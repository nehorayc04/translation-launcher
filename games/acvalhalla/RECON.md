# Assassin's Creed Valhalla — Hebrew groundwork (Phase 1 recon)

Install: `C:\Games\Assassin's Creed Valhalla` (legit Ubisoft Connect, EMEA key).
Engine: **AnvilNext 2.0, scimitar forge v29 — identical container version to AC Mirage.**
`games.id` (proposed): `acvalhalla`. Detector exe: `ACValhalla.exe`.

## Context — how Arabic was made to work in-game
The account's Ubisoft license marks Arabic **"supported but not installed"** (region gate), so
config/VPN never activated it (game reverts `Text=ar-AR`→`en-US`). The community **R2Unlocker**
(`upc_r2_loader64.dll` swap) flips the entitlement gate → the game loads its own on-disk Arabic
packages natively. **Result, user-confirmed in-game: FULL Arabic — main menu + subtitles + font +
RTL, all perfect.** So the font + bidi pipeline are PROVEN working (the auto-save warning renders
flawless RTL Arabic). Set `Documents\...\ACValhalla.ini` `Text=ar-SA`, `Subtitles=ar-SA`, run
detached from Ubisoft Connect.

## Gate status

| Gate | Status | Notes |
|---|---|---|
| Container (v29) | ✅ | `games/acmirage/tools/mirage_forge.py` parses every forge as-is. 136 forges. |
| RTL slot | ✅ | Arabic is a first-class slot, WORKING in-game (R2Unlocker). Arabic-slot hijack. |
| DRM / mods load | ✅ | Denuvo/VMProtect on exe only; asset forges accept edits (redirect proven). |
| Deploy mechanism | ✅ | TOC index-redirect proven (6 redirects applied+reverted byte-exact). Mirage append-relocate available. |
| Loc format (accessible) | 🟡 | LocalizationPackage (class 1849465967, marker `0xD28389B5`, `acu_loc.decode_payload`) decodes on **RAW-stored** resources. ~34,518 Arabic strings found across 8 DLC/patch forges (dlc_20/207/211/222/223/232/243/247) — Type 22 (UI/item names) + Type 24 (subtitles). Injection PROVEN (English→Arabic redirect served Arabic). |
| **Base forge codec** | 🔴 **WALL — DICTIONARY-based Oodle** | See the deep-dive below. NOT a DLL/version issue: the **same `8c 0a` (Mermaid) header both decodes (25%) and fails (75%)** with the SAME oo2core_9. The 75% reference data OUTSIDE the block (a shared Oodle **dictionary**) → fuzzSafe `OodleLZ_Decompress` returns 0 standalone. Only dictionary-free blocks + RAW-stored blocks decode. |

## Codec crack — deep-dive (2026-07-28)
Attempt to crack the base-forge Oodle (user authorized). **Definitive finding: it is NOT a
DLL/version problem — it is dictionary/external-reference Oodle compression.** Evidence + ruled-out:
- `8c 0a` header is IDENTICAL on decoding AND failing blocks; header byte histograms (bytes 0-3)
  do NOT separate ok from fail → same codec (Mermaid), same DLL, different **content**.
- Same DLL decodes **25%** of `8c0a` blocks fine (real content) and **75%** return 0 — the hallmark
  of a compressor that only emits back-references into a shared **dictionary** when it helps; blocks
  with no useful dict match decode standalone.
- **Ruled out** (all return 0 on a real failing block, id 268, `8c0a…` 938→1478): oo2core_9 AND
  oo2core_5; fuzzSafe 0/1; output padding 0-512; comp-offset ±4 (adler); the 16-byte CFD#0 meta as
  decode history; a solid-stream rolling 512 KB window across file-ordered resources; every
  `threadPhase` (0-3) × `checkCRC` × decoderMem-scratch combination.
- **The dictionary hypothesis is RULED OUT** (dedicated hunt, user-authorized 2026-07-28): a dummy
  decode-window prefix of 1 KB → 1 MB all fail, so it is NOT a `decBufBase` back-reference; a solid-
  stream growing-buffer decode from resource 0 in file order = 0/126; the contiguous harness itself
  is PROVEN correct (decodes a known-good 20,635-byte block).
- **The stream is INTACT — this is a pure codec-version incompatibility.** For the failing block
  (id 268): the 4-byte prefix is a real `adler32(comp,0)` and it **MATCHES the stored checksum**
  (`d6fb624b`) — so the 938 comp bytes are byte-exact and uncorrupted, start `8c 0a` (Mermaid), and
  `OodleLZ_Decompress` still returns 0 on oo2core_9 AND oo2core_5, every parameter. A valid Oodle
  stream that both available DLLs refuse ⇒ **it needs the SPECIFIC Oodle version Valhalla shipped
  (2020 ≈ oo2core_8 / Oodle 2.8.x)**, which is NOT on this machine. oo2core_9 (2.9, dropped legacy
  paths) decodes only the ~25% "simple" blocks; the 75% hit a 2.8-era feature it refuses.
- **The true remaining unlock = the exact `oo2core_8_win64.dll`** (or extracting Oodle from the
  VMProtect-packed exe — extremely hard). I cannot obtain/download that binary here, so the base
  forge cannot be decoded with available resources. Mirage (2023, oo2core_9-native) had no such gap.
- **Even if cracked**, two walls remain: the frontend UI/menu format (AC Unity-class) and the
  missing/statically-linked font. So the Oodle crack is necessary-but-not-sufficient for the menu;
  it would unlock the base-game subtitle/dialogue text.
| **Menu / UI text** | 🔴 | The Arabic menu strings (`متابعة`/`خيارات`/`المتجر` …) are **not** in any decodable LocalizationPackage nor as raw UTF-8/UTF-16 in TitleScreen/DataPC — same class as AC Unity's undecodable frontend format (compounded by the codec wall). |
| Font | 🔴 unknown | **No `FontFile` (class 3295364632) resource** in DataPC / extra / TitleScreen; only an OTTO false-positive. The Arabic-capable font IS loaded (Arabic renders) but is not a named forge resource → likely statically linked / behind the codec wall. Hebrew coverage UNANSWERED. |

## Verdict — 🟡 PARTIAL / NOT the quick Mirage clone

Unlike AC Mirage (whose loc + fonts decoded cleanly with oo2core_9), **Valhalla's base forge is
Oodle-compressed with a codec no available oo2core decompresses**, and its menu/UI text is in an
undecodable frontend format. What is reachable today = the RAW-stored Arabic loc in the DLC/patch
forges (subtitles/dialogue/item-names). A full Hebrew mod is a **dedicated multi-step RE session**:
1. **Crack the base-forge Oodle decode** — identify the exact Oodle variant / extract the codec
   from the exe, or find the matching oo2core version. This unlocks base-game text + likely the
   font + the menu package.
2. **Crack the frontend UI/menu format** (AC Unity-class).
3. **Locate + cmap-check the font**; inject Heebo if it lacks Hebrew (Mirage `mirage_font.py`).

## The cheap next step that answers the biggest question
Deploy a Hebrew menu-proof into a RAW-accessible **Arabic subtitle package** (a decodable one in a
DLC/patch forge) via Mirage `mirage_build` + `mirage_deploy`, with: a Latin marker `ZZ-VAL-OK-ZZ`,
the same word LOGICAL vs VISUAL + `אבגד`, and all 27 Hebrew letters. User loads that DLC content →
one screenshot answers the **font gate** (does the loaded Arabic font cover Hebrew?):
- Hebrew renders → font is free → subtitle/dialogue Hebrew mod is GO (pending the codec for base text).
- Tofu → font injection also needed.

## Tools
`games/acvalhalla/tools/` = Mirage stack copied + `check_font.py`, `find_menu.py`,
`list_ar_packages.py`. Run with the repo `.venv` python. Oodle DLL:
`C:\Games\Battlefield 6\oo2core_9_win64.dll` (decodes RAW-store + Mirage, NOT Valhalla base).

## Install cleanliness
Crack files removed earlier; the injection redirect was reverted byte-exact
(`he_arabic_redirect.journal.REVERTED.json`). Pristine except the user-added R2Unlocker DLL
(`upc_r2_loader64.dll`) with the original backed up as `upc_r2_loader64_o.dll`.
