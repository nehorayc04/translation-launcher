# Marvel's Spider-Man Remastered — FEASIBILITY

## Verdict: 🟢 GO — every gate closed offline/self-verified, DEPLOYED, awaiting one screenshot

| Gate | Status | Evidence |
|---|---|---|
| 1. Language settings / RTL surfaces | 🟢 closed | Confirmed no Arabic text locale exists (0 Arabic codepoints, 23/23 variants). Reclassified as LTR-slot hijack — the earlier "Nexus mod proves RTL" claim retracted (page unreachable, no archive; and there is no Arabic slot to have proven anything with). |
| 2. Container | 🟢 closed | `dat1lib` (already vendored for SM2) reads MSMR's `toc` natively — magic, 6-section layout, all 771,670 assets enumerate cleanly. |
| 3. Text codec + round-trip | 🟢 closed | `msmr_loc.py` — identity round-trip **23/23 variants SEMANTIC-PASS, 0 mismatches**; single-key patch test isolates exactly 1 changed value. |
| 4. RTL slot decision | 🟢 closed (by measurement, not assumption) | No RTL locale to hijack → LTR-slot hijack, store-VISUAL class (Playbook §8b, same family as AC2/Anno/GTA/TLOU/R&C). Bidi mode is the ONE thing the deployed proof still needs a screenshot to confirm — both LOGICAL and VISUAL are shipped side by side. |
| 5. Deploy mechanism | 🟢 closed, offline-validated AND live-deployed (after one real bug fixed) | Index-redirect (`msmr_deploy.py`), same class as SM2's proven applier, adapted to MSMR's older split-section toc. Offline: 771,669 untouched assets confirmed drift=0, redirect round-trips through the toc's own reader. **The FIRST live deploy exposed a real bug** — cloning `chunkmap` (a per-archive-unique id on this toc generation, unlike SM2/R&C's RCRA format) from an existing archive caused a collision invisible to every `dat1lib`-based check, breaking the pre-game Launcher UI + hanging boot. Fixed (`chunkmap` now assigned uniquely per appended archive); re-verified with a full-corpus diff of all ~57,361 unpatched keys through the live toc — 0 unexpected changes. Redeployed. See PIPELINE.md for the full writeup. |
| 6. Font | 🟢 closed, self-verified | Scaleform `DefineFont3`, format already solved (Witcher 3 codec, reused verbatim). 135 Hebrew glyphs added across the 5 `Font_LatinAS3.gfx` faces, re-parse confirms 27/face, rebuild re-opens cleanly in FFdec. |
| 7. DRM / integrity | 🟢 clean | 0 Denuvo/VMProtect/anti-cheat; the cleanest profile measured in this project. Overstrike ships first-class MSMR support (live modding scene edits this exact toc). |

## The one real risk this session found and closed itself

MSMR's language **enum is per-title** and does **not** match SM2's or R&C's numbering
(`kLanguageArabic = 19` here, `kLanguageMxSpanish` inserted at 17 shifts everything
after it). Combined with the variant→span map being **non-arithmetic** (unlike
R&C's clean `variant N -> span N×8`), a naive single-span deploy targeting "span 0
= English" would very likely have been **invisible on launch** — this machine's
registry `TextLanguage` was found already set to `19` (resolving to span 152, an
entirely different variant than span 0) before this session began.

**Resolution:** measure-with-a-ladder. Instead of guessing which span the engine
actually reads, the proof patches **three** candidate spans (0 / 8 / 152) each with
its own distinct Latin marker, and the registry was reset to `1` (English) so the
expected default path is exercised. Whichever marker appears on the boot splash
names the live slot unambiguously — no second deploy cycle needed regardless of
outcome.

## Scope (Phase 2, not started — [[delegate-all-translation]])

From the English variant (`variant_01`, span 8), 57,368 total key-value records:

| Metric | Count |
|---|---:|
| Total KEYS records | 57,368 |
| Non-empty English VALUES | 49,351 |
| **GLOBAL unique English values** (the real Phase-2 translation cost) | **46,556** |

Split by section prefix (UI / dialogue-subtitle / credits convention, same pattern
as every prior game in this project):

| Bucket | Records |
|---|---:|
| UI/menus/HUD | 10,987 |
| Subtitles/dialogue | 33,252 |
| Credits | 5,112 |

No gender oracle scoped yet — MSMR ships 22 sibling language variants (see the
language table in RECON.md), so a New-Era reference panel (ru/pl for speaker+
addressee gender, es/fr/it/pt for referent, de for register) is available for free
once Phase 2 starts; not built this session (out of scope for groundwork).

## What is left for the user

Nothing except launching the game and looking. Everything else — container read,
codec, font injection, deploy — is done and live on disk right now. See
PIPELINE.md for the exact revert command if anything needs to be undone.
