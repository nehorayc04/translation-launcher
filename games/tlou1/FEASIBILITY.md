# The Last of Us Part I (PC) — FEASIBILITY

## Verdict: 🟢 GO — medium tier ("LTR-hijack + VISUAL + font-inject" class)

Every pre-translation gate is **solved or has a proven path**; the container + text codec are
already built in pure Python and roundtrip-verified. This is **not** the easy free-bidi Arabic-slot
class (CP2077/GoWR) — TLOU Part I ships **no RTL locale at all** — it is the **AC2 / Anno / GTA V /
Witcher-3-menu class** we have shipped repeatedly: hijack an **LTR** slot, store Hebrew **VISUAL**
(pre-reversed), and **inject Hebrew glyphs**. One in-game **menu proof** closes the two remaining
gates (bidi-storage + font) at once — tooling is staged and one command away.

## Gate-by-gate

| Gate | Status | Detail |
|---|---|---|
| **Container** | ✅ CRACKED | PSARC v1.4 Oodle. Pure-Python reader (`tools/psarc.py`) reads TOC + Oodle blocks; md5-ordered-entry bug fixed. Game ships its own `oo2core_9`. Mature external repackers exist too (**ndarc**, **UnPSARC**, **TLOU_PSARC_Tool**). |
| **Text location + format** | ✅ CRACKED | `core.psarc/text2/<lang>.{common,subtitles,subtitles-systemic}` + `sid-lookup`. ND loc v2: `u32 count; count×{u64 SID,u64 off}; UTF-8 blob`. Codec `tools/tlou_loc.py` decode+encode **roundtrip-verified**. Real English decodes cleanly ("CONTINUE", "ELLIE", dialogue). |
| **SID keying** | ✅ | SID identical across languages → map EN→HE by SID. No hash to compute; edit in place. |
| **Gender variants** | ✅ N/A | ND loc has ONE string per SID (no femaleVariant/maleVariant) → no backfill trap. |
| **Arabic slot** | ❌ none | 26 LTR languages, zero RTL. → hijack an LTR slot (see below). |
| **Bidi** | 🟡 VISUAL (expected) | Engine does NO bidi/shaping (draws raw byte order) → store VISUAL. `work/tlou_rtl.py to_visual` built (9/9 selftest). **Confirm via menu-proof** (logical vs visual test strings). |
| **Font** | 🟡 inject/replace | No shipped face has Hebrew. DINPro = CFF → REPLACE with a Latin+Hebrew face (`work/tlou_font.py`). EASY (loose OTF/TTF, no atlas, no byte-length constraint on the loose path). |
| **Deploy** | ✅ green path | Loose-file override (drop modified files / extract+rename core.psarc) or ndarc repack. |
| **Anti-cheat / DRM** | ✅ GREEN | No Denuvo, no EAC/BattlEye, no asset checksums. Single-player. Hundreds of Nexus mods load modified archives. |
| **Activation** | ✅ | Options → Language → set **Text + Subtitle = the hijacked LTR slot**, Speech = English. |
| **Precedent** | ✅ strong | Full **Arabic** fan-translations of TLOU Part I PC exist (prove text+font+RTL end-to-end); a **Japanese** UI/subtitle Nexus mod (mods/138) proves the exact `text2` + `seriffont` swap loads. TLOU2 "Better Arabic Localisation" corroborates the RTL-visual approach on the sibling engine. |

## Arabic slot — DEFINITIVE: NONE

Steam appid 1888930 supported languages (verbatim): *English\*, Italian\*, Spanish - Spain\*, Czech,
Dutch, Greek\*, French\*, German\*, Danish, Finnish, Hungarian, Japanese\*, Korean, Norwegian, Polish\*,
Portuguese - Brazil\*, Portuguese - Portugal\*, Russian\*, Simplified Chinese, Spanish - Latin America\*,
Swedish, Thai, Traditional Chinese, Turkish\*, Croatian* (\* = full audio). **All LTR** (Latin/Cyrillic/
Greek/CJK/Thai). The 26th data code is `sas` (Spanish-LatAm) / `uke` (UK-English). This is a
publisher-wide Sony/ND-PC pattern, not a Part-I oversight. Confirmed directly from the game data
(`core.psarc/text2/` has no `ara`).

→ **We hijack an LTR slot.** Candidate policy (decide with the user in Phase 2):
- Replace **English (`eng`)** — simplest activation ("set Text = English"), but loses an in-game
  English reference; OR
- Replace a **language the user won't use** (e.g. a Nordic/`nor`, or `gre`) so English stays available;
  the user selects that language for Hebrew.

## Biggest risk (what the menu-proof settles)

The **font + bidi combination**, Hebrew-specifically:
1. **VISUAL vs LOGICAL storage** — the ND-Arabic case study + offline-baker evidence say VISUAL; the
   menu-proof stores some strings logical and some visual and we read which is correct.
2. **Font swap takes without tofu** — the loose DINPro replacement renders Hebrew (Arabic/Japanese
   precedent says yes; Hebrew-specifically unproven until the shot).
Both are closed by ONE screenshot. Tooling staged: `work/build_menu_proof.py`.

## Why medium (not easy) tier

Easy-tier (Anno/Hogwarts/Witcher) had the container solved by an off-the-shelf tool AND a proven bidi
answer AND (Witcher/Hogwarts) an existing Hebrew-covering font. Here we own the RTL visual bake AND the
font injection AND the deploy still needs a confirmed loose-override-vs-repack decision — but all three
are proven patterns we've shipped. No hard research gate remains (unlike AC Shadows' v42 repacker).

## Next step (Phase-1 finish)
`python work/build_menu_proof.py --deploy` (or the extract+rename fallback in `proof/DEPLOY.txt`) →
launch → Options → Language → Text+Subtitles = English → screenshot the main menu → the user (Hebrew
speaker) confirms: LOGICAL vs VISUAL, font renders, no tofu/crash. Then Phase 2 (PIPELINE.md).

## מסמכים קשורים
- באותה תיקייה: [[games/tlou1/PIPELINE|PIPELINE]], [[games/tlou1/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#tlou1|CLAUDE_INDEX_games]]
