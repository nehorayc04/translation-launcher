# A Plague Tale: Requiem — FEASIBILITY

## Verdict: 🟢 **GO — easy tier for the TEXT, one gate = the FONT**

The text pipeline is the **easiest in the whole project** (loose `.pc` plain-text,
no repack, no compression, no anti-cheat). The ONLY thing that could push this to
"medium" is whether the Arabic-slot font already carries Hebrew glyphs — decided
by the menu proof.

| Playbook gate | Status |
|---|---|
| Format mapped | ✅ plain text `TT n "value" KEY`, UTF-8/CRLF, tt01=EN, tt23=AR |
| Arabic slot exists | ✅ official `ARABIC` (TSC_ID 23) + `BIG_ARABIC` font; renders RTL in game |
| bidi mode determined | ✅ **CONFIRMED IN-GAME 2026-07-03** — RTL-layout, LTR-islands pre-reversed, RTL scripts logical |
| identity round-trip | ✅ trivial — plain text; `pt_text.py` proves byte-identical re-emit |
| **menu proof in-game** | ✅ **DONE** — file IS read; `to_stored` transform confirmed (raw Latin rendered reversed → transformed Latin `ZZ-CH-ONE` rendered FORWARD/correct) |
| **font has Hebrew?** | 🔴 **NO — confirmed the SOLE gate**: Hebrew rendered BLANK (no glyph, not tofu ⇒ `Fonts_Z` skips unmapped codepoints) → must inject |
| count report | ✅ 17,476 subtitles + 1,433 UI + 1,752 credits = 20,661 |
| deploy target | ✅ overwrite `TRTEXT/tt23.pc` (loose, runtime-read; backup `.he_backup`) |
| anti-cheat / DRM | ✅ none (no Denuvo, no EAC) |

### Menu proof result (2026-07-03, user-confirmed in-game)
1. Raw Latin markers (`ZZPLAY`/`ZZAUDIO`/`ZZ-CH-ONE`, no transform) rendered **reversed**
   (`YALPZZ`/`OIDUAZZ`/`ENO-HC-ZZ`) → proves (a) tt23.pc **is read**, (b) Latin font works,
   (c) the engine does **RTL char-layout** (my model).
2. The SAME markers via `pt_rtl.to_stored` rendered **FORWARD/correct** (`ZZ-CH-ONE`) →
   proves the transform is right (Hebrew stays logical, LTR islands pre-reversed).
3. Hebrew (first proof) rendered **BLANK** (no glyph) → the slot font lacks Hebrew.
⇒ **Text pipeline PROVEN end-to-end. The only remaining work is Hebrew font injection.**

## The bidi model (a THIRD engine class — reverse-engineered from the game's Arabic)
The Zouna engine positions the stored characters **right-to-left** but does **no**
bidi reordering of LTR runs and **no** Arabic shaping. Proof from tt23.pc (the
game's own working Arabic — our ground truth):

* Arabic words are stored **LOGICAL + pre-shaped** (presentation forms); a full
  visual reverse would put the last word first — it does not.
* LTR islands are stored **reversed in place**, run order preserved:
  * digit `"12"` → `"21"` (ACHIEVEMENT__DESC_12)
  * roman `"XVII"` → `"IIVX"` (MENU__CHAPTER17; IV→VI, IX→XI, …), the `" - "`
    separator stays after the numeral
  * `"Asobo Studio"` → `"oidutS obosA"` (multi-word Latin reverses as a unit)
  * embedded `"…Asobo Studio…"` inside an Arabic sentence reverses **in place**
* `{STR_…}` tokens kept **verbatim, forward, in place**.

**⇒ Hebrew is easier than Arabic here (no shaping):** store base Hebrew
`U+05D0–05EA` **logical**, pre-reverse LTR islands only, keep tokens verbatim.
Implemented + self-tested in `work/pt_rtl.py` against these exact conventions →
the proof output is byte-structurally identical to the game's Arabic. High
confidence it renders correctly **modulo the font**.

> ⚠️ This must still be **confirmed in-game** (playbook rule: no compile error
> catches mirror text). The proof is designed to confirm it in one launch.

## The one gate — Hebrew font glyphs
No file lists Hebrew; the Arabic atlas (BIG_ARABIC) is Arabic presentation forms.
Two outcomes from the menu proof:
1. **Hebrew renders** (the slot font happens to include it) → **zero font work**,
   full GO, straight to Phase 2.
2. **Tofu / empty boxes** → inject 27 Hebrew glyphs into the `Fonts_Z` atlas +
   metrics inside `FONT/ENGLISH.DPC` (the SM2/WD2/GoWR/Anno atlas-injection class),
   repacking the DPC with **APT_DPC_Tool** / **bff** (LZ4). Sub-risks: (a) free
   atlas cells vs. a taller atlas; (b) the `Fonts_Z` UV/descent format is
   proprietary (parse+rebuild, not paint-on-PNG); (c) the DPC **repacker itself**
   (APT_DPC_Tool import is buggy; bff Requiem support is PARTIAL) may need
   fixing/RE before the DPC re-loads. Font atmosphere: pick a period-fitting
   serif Hebrew (David / Frank Ruehl), user-confirmed — same as GoWR/Anno.

## Recommended pipeline
1. **Extract** `tt01.pc` → `extract/en.json` (`work/extract_corpus.py`). ✅ done.
2. **Translate EN→He** — delegate to Google/Antigravity agents (rule
   [[delegate-all-translation]]). Scope-order: UI (1,433) → subtitles (17,476) →
   credits (1,752, optional). Translator writes **LOGICAL** Hebrew.
3. **Build**: `overrides[key] = pt_rtl.to_stored(hebrew_logical)`; write with
   `pt_text.write_overrides(tt23.pc.he_backup → tt23.pc)` (surgical, keeps every
   non-translated byte identical).
4. **Font**: if the proof shows tofu, inject Hebrew into `FONT/ENGLISH.DPC`.
5. **Deploy**: overwrite `TRTEXT/tt23.pc` (backup first). No repack for text.
6. **Publish** like the other games (GitHub `plague-tale-requiem-hebrew-mods`
   release + Worker slug `plague-tale-requiem-hebrew` + Supabase `games` row +
   `mod_version_history`).

## Open items before Phase 2
- [ ] **Menu proof in-game** (`build_proof.py --deploy`) → confirm (a) Hebrew
      glyphs render, (b) RTL + numbers + `{STR_}` correct, (c) which file is live
      (`.pc` vs `.IGN` — proof writes both), (d) no crash.
- [ ] If tofu → build the `FONT/ENGLISH.DPC` Hebrew-glyph injector (font sub-project).
- [ ] Confirm the community `/translate` pool import (`extract/ct_strings.json`).

## מסמכים קשורים
- באותה תיקייה: [[games/plague_tale_requiem/PIPELINE|PIPELINE]], [[games/plague_tale_requiem/RECON|RECON]], [[games/plague_tale_requiem/RESEARCH_FONTSIZE|RESEARCH_FONTSIZE]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#plague_tale_requiem|CLAUDE_INDEX_games]]
