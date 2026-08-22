# Spider-Man 2 — עידן חדש line-by-line QA fleet (PREPARED, not yet run)

Implements the **עידן חדש** doctrine (`memory new-era-doctrine` + `universal/NEW_ERA_LANGUAGE_ROLES.md`)
for SM2: SM2 is **already translated** → **review-only** mode. Every Hebrew line is reviewed against
its English source AND the game's own professional translations in every gendered language, each used
for what it is best at. Copied from the Witcher-3 reference (`games/witcher3/fleet/`).

**Status: PREPARED — do NOT run until the user approves.** No NIM key is deployed here yet.

## The language map (established 2026-07-12 by content detection)
SM2 ships each language as `extracted/loc_variants/variant_NN.localization` (a DAT1). The variant
index == the in-game TextLanguage id (0=English, 18=Arabic = the slot we hijacked for Hebrew).

| role | lang | variant | strength |
|---|---|---|---|
| PRIMARY addressee + true plural | **ar** | 18 | إنتَ/إنتِ, ـكِ, أنتم — **Egyptian colloquial** (عايز/عايزة, بتعملي) |
| SPEAKER gender | **ru** | 14 | я …-л/-ла (separates I from you); ⚠️ вы = formal-singular |
| speaker+addressee, clean plural | **pl** | 12 | -łeś/-łaś, wy |
| referent + addressee, clean plural | **es** | 15 | -o/-a, vosotros (es-ES Spain) |
| referent | **it** | 8 | -o/-a |
| extras (votes) | fr 6 · de 7 · pt 13 · zh 21 · esmx 20 | | |

## Files
- **`sm2_extract_langs.py`** — parse each `variant_NN` → `extract/<lang>.json` (key→value). ✅ ran: 11 langs.
- **`sm2_build_corpus.py`** — join he (subtitles_he+dialogue_he, LOGICAL) + en + ar/ru/pl/es/it, bake
  `ag`/`num`/`formal` via the multi-language consensus → `corpus.json`
  `{id:{en,he,ar,ru,pl,es,it,ag,num,formal}}`. ✅ 38,948 lines (2,361 non-Hebrew skipped).
- **`sm2qa_nim.py`** — the standalone NIM QA worker (copy of `w3qa_nim.py`, SM2-adapted): SM2 prompt +
  names glossary (ספיידרמן/מיילס/פיטר/ונום/הלטאה/העקרב/הנשר/החתולה השחורה…), SM2 STRUCT tokens
  (`<ts="..">`, `&rlm;`, `[TOKEN]`, `{VALUE}`, `%spec`, `<span>`), Egyptian-Arabic gender note. Reads
  `corpus.json` → `out.json` `{id:{he,iss}}`. Monotonic guard (only flips gender when the baked
  evidence confirms; formal-you trap; STRUCT/foreign/niqqud/similarity floor). Resumable, singleton-
  locked, NIM key-rotation.

## The Arabic parser — 2nd-person ONLY (the key fix)
`ar_gender` uses ONLY addressee markers (إنتَ/إنتِ pronoun, ـكِ/ـكَ suffix, `بت/هت…ي` colloquial 2nd-fem,
MSA `…ين` verbs, أنتم/إنتوا plural). It deliberately does **NOT** use bare participles (عايزة/فاهمة) —
those are 1st/3rd-person too (`أنا فاهمة` = I-fem SPEAKER) and would pollute the ADDRESSEE signal (the
exact false-positive the doctrine warns about). SM2's Arabic is Egyptian colloquial + largely
un-vocalized, so addressee gender is baked only where clearly marked; the rest rides ru/pl/es/it
consensus + the LLM reading the raw languages. The two Arabic parsers (builder + worker) are kept in
lockstep — edit both.

## Known scope note (same as the W3 reference)
The baked `ag` and the guard are ADDRESSEE-focused. SPEAKER-gender errors (e.g. a female speaker's
`אני שומע`→`שומעת`, seen in `ANGE_CINE_A2_HELPRIO_LOCKEDOUT_001` where Arabic is `أنا فاهمة`) are read
by the LLM from the raw ru/pl/ar per the prompt, but are NOT hard-confirmed by the guard, so a
speaker-gender flip may be conservatively rejected (monotonic — never degrade). Optional enhancement
before the run: bake a `sg` speaker-gender fact from ru/pl `я …-ла` / `-łam` and let the guard accept
a flip that matches `sg`. Flagged for the user to approve.

## To run (per stream, after approval)
Deploy `sm2qa_nim.py` + `corpus.json` + `key.txt` (NIM key) to each stream; slice the corpus disjoint
per stream; `python sm2qa_nim.py` (resumable → `out.json`). Then merge `out.json` fixes back into
`work/subtitles_he.json`/`dialogue_he.json` (only `iss!="ok"`, human-audited), rerun the build chain
`98→10→…→80`, redeploy/publish. The fleet does the work ([[delegate-all-translation]]); Claude builds
the tooling + corpus and drives.
