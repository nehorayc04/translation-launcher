# Assassin's Creed II — Hebrew translation FEASIBILITY

**Verdict: 🟢 GO (with one container caveat).** Right-to-left Hebrew in the AC2 UI
is achievable and has a proven precedent. The hard novelty (RTL on a 2009 engine
with no bidi) is solved by the same "bake direction into the data" method this
project already uses, plus a font-atlas glyph injection. The only non-trivial
dependency is the **container round-trip**, which a free tool already on this
machine (AnvilToolkit) performs.

This is a multi-session engineering project (like GoWR / SM2 / WD2), NOT a
one-shot. This document + RECON.md + PIPELINE.md are the foundation; the first
in-game Hebrew proof is the next milestone.

---

## Why GO

| Pillar | Status | Evidence |
|---|---|---|
| **Archive format** | ✅ solved (read) | `scimitar` v25 `.forge` fully parsed by `tools/ac2_forge.py`; any resource extractable by name. |
| **Text location + format** | ✅ identified | `DataPC.forge` → `LocalizationPackage_<Lang>` (char-index serialization). 14 LTR languages, **no Arabic/Hebrew**. |
| **Font** | ✅ approachable | `DataPC_extra.forge` → per-script DDS atlases incl. a **Cyrillic (Russian) CharacterSet** → the engine renders non-Latin scripts; we add/redraw a Hebrew atlas. |
| **RTL method** | ✅ proven + built | No engine bidi → store **visual-reversed** Hebrew. `work/ac2_rtl.py` implemented + unit-tested. Persian/Arabic AC2 patches prove the chain end-to-end. |
| **Container round-trip** | ✅ **format decompiled** | The LocalizationPackage read+write, StringTable/Fragment/IndexedData, DataFile + ForgeFile, and CRC32/64 were obtained by **decompiling AnvilToolkit** (see `FORMAT.md`). The whole pipeline is reproducible in **pure Python — NO GUI tool required**. (The char-index "checksum" fear was unfounded: the discarded u32 is a constant marker, not a content CRC.) |
| **Deploy / activation** | ✅ clear | Repack the edited forge in place (back up the original). User sets in-game language to the hijacked slot. No Denuvo/anti-cheat on a 2009 title. |

## The two engineering gates (same shape as every game here)

1. **Loc repack** — turn translated+reversed Hebrew into a valid
   `LocalizationPackage` inside `DataPC.forge`. **The format is fully decompiled
   (`FORMAT.md`)** → build a pure-Python codec (`work/ac2_loc.py`, in progress):
   decode the existing payload → translate+reverse → re-encode → in-place patch
   (or full forge rewrite via the `ForgeFile` port). NO AnvilToolkit GUI needed.
2. **Hebrew font glyphs** — the Latin atlas has no Hebrew. Draw Hebrew glyphs into
   a DDS atlas (over unused Latin slots, or by repurposing a CharacterSet we don't
   need) and point the loc indices at them. `texconv.exe` (CLI, bundled with
   AnvilToolkit) converts DDS — also scriptable, no GUI.

Translation of the strings runs in parallel and is gated only on DEPLOY.

## The one real risk + how we de-risk it

**No AC2 *text* mod has been published in Hebrew, and the LocalizationPackage
write path is the community's known weak spot.** Mitigation: prove a
**zero-translation identity round-trip first** — export English loc → import it
UNCHANGED → repack → game still boots with identical English. That validates the
AnvilToolkit repack+checksum chain before investing in translation. Then a
single Hebrew test string (with its glyphs drawn into the atlas) proves RTL
rendering. Only then scale up. (Same "prove-before-invest" discipline as ACS.)

## What is explicitly NOT yet done

- No game file has been modified. Everything so far is read-only recon + tooling.
- The LocalizationPackage **write** path is not yet implemented in Python (uses
  AnvilToolkit) — and not yet exercised end-to-end.
- No Hebrew glyphs drawn; no in-game verification.
- No translation run started (by design — prove the pipeline first).

## Difference from the other Ubisoft games in this repo

- **vs AC Shadows** (`games/acshadows/`): totally different generation. ACS = forge
  v42 + Oodle + a TTF that already has Hebrew + a *real Arabic locale*. AC2 = forge
  v25, char-index loc, DDS bitmap atlases, **no Arabic slot, no bidi**. AC2 is older
  and lower-level but, crucially, its repacker (AnvilToolkit) is FREE and present,
  whereas ACS is gated on a Discord-only v42 repacker.
- **vs WD2** (`games/watchdogs2/`): WD2 had an Arabic slot (free RTL). AC2 does not
  → we add the reversal + font ourselves. Same `.loc`-style "bake the language"
  philosophy, harder because no RTL pipeline exists to inherit.

## מסמכים קשורים
- באותה תיקייה: [[games/assassinscreed2/FORMAT|FORMAT]], [[games/assassinscreed2/PIPELINE|PIPELINE]], [[games/assassinscreed2/RECON|RECON]], [[games/assassinscreed2/RESEARCH_SMALLSIZE|RESEARCH_SMALLSIZE]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#assassinscreed2|CLAUDE_INDEX_games]]
