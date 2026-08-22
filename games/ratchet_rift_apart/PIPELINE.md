# Ratchet & Clank: Rift Apart — PIPELINE (build + deploy recipe)

This mirrors the Spider-Man 2 pipeline (same Insomniac engine) with ONE structural change: **no Arabic
slot → hijack the English variant + inject Hebrew into the Latin (Proxima Nova) font**. Everything below
reuses `translation_manager/spiderman2_mod.py` and `dat1lib` (at `games/spiderman2/tools/ALERT`), driven
by the repo `.venv` python.

## 0. Facts the build depends on (verified 2026-07-12)
- toc = TOC2/RCRA v202300; loc asset `localization/localization_all.localization`, aid `0xBE55D94F171BF8DE`, 32 variants.
- Hijack target = **span 0 (variant_00, en-US)**; size-entry index **87375**; header must stay, DAT1 payload = `raw[36:]`.
- DAT1 sections: VALUES `0x70A382B8`, KEYS `0x4D73CEBD`, TEXT_OFFSETS `0xF80DEEB4`, KEY_OFFSETS `0xA4EA55B2`,
  ENTRY_COUNT `0xD540A903`. entry_count 24,575.
- Subtitle marker = `<ts="a;b">`. Preserve verbatim: `<ts=...>`, `%`-format specs (per-key printf gate like SM2),
  `\n`/`<br>`, `[TOKEN]`/`{VALUE}` style tokens, `*emphasis*` asterisks.

## 1. Extract the corpus
```
.venv/Scripts/python.exe games/ratchet_rift_apart/work/01_probe.py      # dumps 32 variants to extracted/loc_variants/
```
English SOURCE = `variant_00_idx87375.localization`. Build `{key: english}` (+ optional `{key: <other-lang>}` for a
gender/context oracle — French/German/Spanish/Italian/Russian all decode with the same codec) via a corpus builder
cloned from SM2's `10_build_patched_localization.py` reader half.

## 2. Delegate translation (Claude never translates — [[delegate-all-translation]])
Build the agent handoff (per `universal/AGENT_TRANSLATION_HANDOFF_TEMPLATE.md`, model on
`games/watchdogs2/agent_handoff/`): `to_translate.json` {key: en}, `get_batch.py`/`merge_batch.py` loop with an
R&C anti-cheat (`<ts>`/`%`/token multiset preserved; reject copy-EN-on-prose, niqqud, foreign script), `INSTRUCTIONS.md`
(R&C glossary: Ratchet=רצ'ט, Clank=קלאנק, Rivet=ריווט, Kit=קיט, Dr. Nefarious=ד"ר נפאריוס, Lombax=לומבקס, Bolts=ברגים,
Raritanium=רריטניום, Pocket Dimension/Rift = ריפט/ממד כיס). Order UI → subtitles → CREDITS (last/optional). Store LOGICAL.
- **Name registry + internet check** ([[name-registry-and-internet-check]]): build `name_registry.json` (canonical
  Hebrew for every character/planet/weapon), web-verify spellings, enforce identical in every line.
- **Gender oracle** (no Arabic → the game's OWN gendered locs): join by key the French/Spanish/Italian/Russian
  variants for referent/addressee gender (Rivet is female, Ratchet male — critical for Hebrew verbs).
- **Community `/translate` pool:** import the ~17.5k lines via `universal/community_translate.py import ratchet-rift-apart`
  (3 Hebrew categories by visibility: ממשק → כתוביות → קרדיטים).

## 3. Font — inject Hebrew into Proxima Nova (Phase-1 sub-task)
Clone the SM2 font tooling / reuse the GoWR/Anno/W3 fontTools glyph-merge:
- Extract `proximanova_regular_normal.ttf` (aid `0xA2197874D2B7B1AC`) + `proximanova_bold_normal.ttf`
  (`0xB5F411285669C55D`) from archive 109 via `dat1lib.extract_asset` (they come out as clean sfnt TTF).
- Merge Hebrew outlines U+05D0–05EA from a donor (**Rubik** recommended — bilingual, rounded, fits R&C; Heebo/Frank
  Ruehl alternates) via fontTools (DecomposingRecordingPen + TransformPen to match upem), extend cmap (format 4/12),
  keep the Proxima Nova `name`/Latin/Cyrillic intact.
- **EMPTY the U+200F / U+200E glyphs** (SM2 lesson) so `&rlm;` anchors never render as visible marks/tofu.
- Optionally cmap-alias Arabic-Indic digits→Latin if any label formats them (unlikely in an English slot).
- Deploy the injected font the SAME way as the loc (toc-redirect its asset), OR ship it as a second `.stage` entry.

## 4. bidi — menu-proof decides (Playbook Stage 6, do this BEFORE the full haul)
`work/build_menu_proof.py` (clone SM2's): patch ~30 high-visibility keys (Continue/New Game/Load/Options/Quit + a few
settings labels + a chapter/planet title) in **TWO** builds — **A = LOGICAL + leading `&rlm;`**, **B = VISUAL**
(pre-reversed via the WD2/GoWR `visual_line`) — plus 3 diagnostics: a pure-Latin marker `ZZ-RC-OK-ZZ` (proves mount),
`שלב 12` (digit ordering), `מצב Ratchet` (Latin-island ordering). Both bake the Hebrew-injected Proxima Nova. Deploy
each via §5, set Text Language = English, screenshot the menu + a settings sub-screen.
- **Marker `ZZ-RC-OK-ZZ` shows** → toc-redirect + rebuilt DAT1 mount over the base. **Build A correct RTL** → SHIP
  LOGICAL+RLM; **only Build B correct** → SHIP VISUAL. **No tofu** → font coverage OK; **no stray marks** → U+200F/E
  emptied correctly. Revert = restore `toc.tm_he_backup`.

## 5. Build the loc + deploy (native applier, reuse SM2 AS-IS)
- **Builder** (clone `games/spiderman2/work/10_build_patched_localization.py`): start from `variant_00`, fill every
  value with English (base), override translated keys with Hebrew (LOGICAL; apply the chosen bidi transform), run the
  per-key printf `%`-gate, rebuild VALUES + TEXT_OFFSETS (dedup, leading NUL), re-emit the DAT1 (SEMANTIC-PASS verified),
  strip the 36-byte header → emit a `.stage`/`.modular` whose entry is **`0/BE55D94F171BF8DE`** (add `8/…`, `16/…`,
  `144/…` for en-GB coverage). For untranslated tail: fall back to **English** (NOT another language — Heebo/Proxima
  has Latin, renders fine), so no tofu.
- **Deploy** = `translation_manager/spiderman2_mod.apply(game_root, payload)` — writes `d\mods\tm_he_*`, appends an
  archive entry, redirects each hijacked variant's size-entry `{archive_index=new, offset=0, value=len}` (header_offset
  untouched), backs up `toc.tm_he_backup` once. **Game must be CLOSED** (toc lock). **Revert** = `revert(game_root)`.
- **Activation** = Settings → Game Settings → **Text Language = English** (default), Voice = English (independent).

## 6. Publish (only on explicit "פרסם")
Like SM2/GoWR: GitHub repo `hebrew-translation-hub/ratchet-rift-apart-hebrew-mods` + FULL release (releases/latest) with the
`.stage`/`.modular` + injected fonts + a Hebrew readme + `install.py` (SM2-applier bundled) + manifest; Worker slug
`ratchet-rift-apart-hebrew`; Supabase `games` id=`ratchet-rift-apart` (already inserted, availability=planned →
flip to available/beta) + `mod_version_history`; optional launcher applier `translation_manager/ratchet_rift_apart_mod.py`
(reuse `spiderman2_mod.apply/revert` directly — no new code) + detection already wired in `game_detector.py`.

## Reusable-from-SM2 checklist
- ✅ dat1lib reader/writer (`games/spiderman2/tools/ALERT`) — AS-IS
- ✅ native applier `translation_manager/spiderman2_mod.py` — AS-IS (verified)
- ♻️ loc builder `10_build_patched_localization.py` — clone, swap SRC to variant_00, add the bidi transform
- ♻️ font injection (SM2 scripts 30/33/52/57 + fontTools) — clone, target Proxima Nova (TTF, no wrapper — simpler)
- ♻️ menu-proof `build_menu_proof.py` — clone, two-build (LOGICAL vs VISUAL)
- ♻️ agent handoff (WD2 template) — new R&C glossary + gender oracle from fr/es/it/ru

## מסמכים קשורים
- באותה תיקייה: [[games/ratchet_rift_apart/FEASIBILITY|FEASIBILITY]], [[games/ratchet_rift_apart/PUBLISH|PUBLISH]], [[games/ratchet_rift_apart/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#ratchet_rift_apart|CLAUDE_INDEX_games]]
