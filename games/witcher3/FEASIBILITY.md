# The Witcher 3 — Hebrew — FEASIBILITY

## Verdict: 🟢 **GO — ALL GATES CLOSED** (one of the EASIEST games in the project)

REDengine 3 ships an **official Arabic (RTL) locale** stored **CLEARTEXT**, the string format is **fully
cracked with a working pure-Python read/write codec**, string ids map cleanly EN→HE, there is **no
anti-cheat**, and the deploy is a simple Mods-folder `.w3strings` drop. **The in-game menu proof PASSED
(2026-07-01):** Hebrew renders cleanly with the vanilla font (no font work) and correct RTL. Ready for
Phase 2 (translation).

## The 4 pillars — status

| Pillar | Status | Notes |
|---|---|---|
| **Format read/write** | ✅ **SOLVED** | `work/w3strings.py` decodes + encodes; round-trip byte-identical on small files, semantic-identical (valid, re-decodes to the same `{id:text}`) on large files. **Proven in-game:** the game loaded our Python-encoded 27,601-string `ar.w3strings`. |
| **Arabic slot (free RTL)** | ✅ **SOLVED** | Official next-gen `ar.w3strings`, **cleartext (keyID 0)** → Hebrew = plain UTF-16LE. `str_id` shared across langs → clean EN→HE by id. |
| **Bidi mode** | ✅ **SOLVED (VISUAL)** | Confirmed in-game: the menu is NON-BIDI for Hebrew → store **VISUAL** (pre-reversed, no RLO). v1 logical+RLO rendered mirrored; v2 visual rendered correct. |
| **Font** | ✅ **NO WORK** | The Arabic-locale font already renders Hebrew (zero tofu in the proof). No SWF editing. |

## Identity round-trip (Phase-5 proof) — PASSED

`decode → encode → compare`, run live on the real Arabic files:
- Small files (`dlc9`, `dlc4` ar) → **MD5-identical** (byte-exact container serialization). ✅
- Large files (`content0`, `content4`, `content1` ar) → **not byte-identical but semantically identical**:
  `count3` matches exactly, no dedup, and the rebuilt file **re-decodes to the identical `{str_id:text}`
  map**. The only difference is the internal blob string-ORDER (the game stores the blob in an authoring
  order, not block1-order); our offsets are internally consistent, so the file is valid and loadable.
- **Deterministic** builds (fixed layout, no randomness) — safe for version-tracking.
- Final acceptance = the in-game menu proof (Phase-6, user gate).

## Gates — all closed ✅

1. ✅ **Font** — the vanilla Arabic-locale font renders Hebrew cleanly (proof, zero tofu). No SWF work.
2. ✅ **In-game menu proof (Phase-6) — PASSED.** VISUAL Hebrew, correct RTL, readable, no crash;
   the game loaded our Python-built `ar.w3strings`.

## Remaining (Phase-2 detail, not blocking)
- **Dialogue/subtitle bidi**: confirmed VISUAL for the MENU; do a quick in-game dialogue proof at the
  start of Phase 2 to confirm the subtitle surface is also VISUAL (very likely — the engine has no
  Hebrew bidi). If a surface differs, apply `visual_line` per-surface.

## Risks / caveats (minor)
- **Numbers/Latin inside a Hebrew line**: `visual_line` keeps Latin/digit runs forward and flips run
  order; eyeball a line with an embedded number/name during Phase 2 (e.g. gold amounts, level numbers).
- **UI vs subtitle split** isn't available from the `.w3strings` alone (no readable keys). Not blocking —
  we translate the whole id set.
- **Scale:** ~94k unique ids / ~6.5M chars incl. both expansions — a large haul (delegate to agents),
  but purely translation volume now that all engineering is proven.

## Why this is "easy tier"

Like Anno 1800: no repack of a compressed archive for the text (a loose `.w3strings` overrides the base),
the Arabic slot is cleartext, an official RTL locale + no anti-cheat, the id mapping is 1:1 across
languages, and **the font already covers Hebrew** — so the whole engineering chain (extract → translate →
encode → deploy → activate) is proven end-to-end with only translation volume left.

## מסמכים קשורים
- באותה תיקייה: [[games/witcher3/KNOWN_ISSUES|KNOWN_ISSUES]], [[games/witcher3/PIPELINE|PIPELINE]], [[games/witcher3/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#witcher3|CLAUDE_INDEX_games]]
