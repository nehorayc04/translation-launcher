# עידן חדש — Per-language roles for line-by-line Hebrew QA (all games)

**Doctrine ("עידן חדש", 2026-07-12).** Every game ships the SAME line in many languages. Each
language encodes something English (and therefore a naive Hebrew translation) drops — addressee
gender, speaker gender, referent gender, number, register. Instead of translating from English and
"guessing", the fleet goes **line-by-line** and, for each line, consults **every language the game
ships**, taking from each what it is best at, to decide/verify the Hebrew is correct — then moves to
the next line with the same routine.

Two modes:
- **New game (translate):** translate the line, and set gender/number/register from the multi-language
  consensus AT translation time (never fix gender in a later pass). Verify per language before moving on.
- **Already-translated game (review only):** for each existing Hebrew line, verify it is translated
  correctly (meaning) and that gender/number/register match the languages; fix only real errors
  (monotonic — never degrade a good line), then next line.

Hebrew needs FOUR facts English hides: **addressee** gender/number (you: אתה/את/אתם), **speaker**
gender (I: masc/fem verb), **referent** gender (3rd person: ה.../...ת), and **register/number** (formal
vs plural). No single language gives all four — so we combine them by strength, and take a CONSENSUS
(a real error only when the evidence AGREES against the Hebrew).

---

## The languages, by strength

### Semitic — the gold for ADDRESSEE gender (closest to Hebrew)
- **Arabic (ar)** — THE primary oracle. Same distinctions as Hebrew (both Semitic): addressee
  `أنتَ`=אתה(m) / `أنتِ`=את(f) / `أنتم/أنتن`=אתם(pl); feminine 2nd-person verb ending `ـين`
  (تفعلين); object/possessive `ـكَ`/`ـكِ`/`ـكم`; feminine referent `ـة`. **Strengths:** best addressee
  gender; the **ONLY confound-free plural** — Arabic `أنتم` is a TRUE plural (Arabic does NOT use a
  plural for a polite singular), so plural is trusted from Arabic alone. **Weakness:** the pronoun
  gender needs vocalization (the kasra/fatha diacritic); a bare `أنت` and a bare `تفعل` are ambiguous
  → then fall back to the other languages.

### Slavic — the gold for SPEAKER gender (separates I from you)
- **Russian (ru)** — Past-tense verbs carry the SUBJECT's gender: `я сказал`=male speaker /
  `сказала`=female speaker; `ты знал/знала`=addressee. Because Russian marks the subject, it
  **separates the SPEAKER (я) from the ADDRESSEE (ты)** — the one thing Arabic can't do, and the cure
  for the "a masculine Hebrew verb is really the male speaker, not a wrong addressee" false alarm.
  Adjectives mark referent gender. **⚠️ `вы` = plural OR polite-SINGULAR (the formal-you trap) — never
  take plural from вы.**
- **Polish (pl)** — Richest of all: past tense marks gender AND person — `byłeś`=you-masc,
  `byłaś`=you-fem, `byłem`=I-masc, `byłam`=I-fem. Cleanly gives BOTH addressee and speaker gender.
  Adjective agreement (gotowy/gotowa). `wy`=plural is CLEANER than Russian (Polish formal is
  Pan/Pani, not wy) — a usable plural signal. Excellent all-round gender oracle.
- **Czech (cz)** — like Polish: past-tense gender (byl/byla, -l/-la), `ty`/`vy` (⚠️ vy = formal-plural trap).

### Romance — the gold for REFERENT (3rd-person) gender + adjective agreement
- **Spanish (es / esmx)** — predicate adjective/participle `-o/-a` gives gender: `estás listo/lista`
  =addressee, `estoy cansado/cansada`=speaker, `está muerta`=3rd-person referent; `bienvenido/a`.
  Number: `tú`(sing) vs `vosotros`(Spain plural — CLEAN) vs `ustedes`(LatAm plural); **⚠️ `usted`
  =formal singular = trap.** `esmx` uses `ustedes` for all plural (no vosotros). **Strength:** referent
  + addressee gender via copula+adjective.
- **Italian (it)** — adjective `-o/-a`: `sei pronto/pronta`=addressee, `sono stanca`=speaker;
  `benvenuto/a`. Number `tu` vs `voi`. **⚠️ `voi` can be formal in some registers — don't take plural
  from voi alone.**
- **French (fr)** — past-participle/adjective agreement: `tu es prêt/prête`, `venu/venue`. Written fem
  `-e` marks gender. **⚠️ `vous` = plural OR formal-singular = trap.** Weaker/noisier gender signal
  than es/it (many adjectives change only in writing), so use as a secondary vote.
- **Portuguese (br, Brazilian)** — adjective `-o/-a` referent gender; `tu`/`você`(sing) vs `vocês`(pl).

### Germanic — mostly NUMBER (weak gender)
- **German (de)** — little addressee-gender marking. Number: `du`(sing) vs `ihr`(plural); **⚠️ `Sie`
  =formal singular = trap.** Adjectives mark the NOUN's gender, not the addressee. Use for a du/ihr
  number hint + meaning cross-check; not a gender oracle.

### CJK / non-gendered — NUMBER + 3rd-person + meaning cross-check (NOT addressee gender)
- **Chinese (zh traditional / cn simplified)** — no verb gender, BUT: written 3rd-person `他`(he)/
  `她`(she)/`它`(it) = **referent gender**; and `你`(you-sing) vs `你们`(you-PLURAL, CLEAN) vs `您`
  (formal singular). **Strength:** a confound-free-ish plural (`你们`) and written referent gender.
- **Japanese (jp)** — no grammatical gender, but persona/register cues: gendered 1st-person pronouns
  (boku/ore≈male, atashi≈female) and sentence-final particles (wa≈fem, ze/zo≈masc) sometimes hint at
  **speaker persona**; politeness levels. A weak persona/register + meaning cross-check.
- **Korean (kr)** — honorific/speech levels (register), no grammatical gender. Register + meaning cross-check.
- **Hungarian (hu)** — no grammatical gender, no gendered pronouns; te/ti = number only. Meaning cross-check.
- **Turkish (tr)** — no grammatical gender; `sen`(sing) vs `siz`(plural/formal — trap). Number hint only.

---

## How to combine them (the decision rules)

1. **Addressee gender (you = אתה/את):** Arabic (vocalized) decides alone. If Arabic is ambiguous →
   consensus of ≥2 of {Polish, Russian, Spanish, Italian, French}. Polish/Russian also confirm it.
2. **Speaker gender (I = masc/fem verb):** Russian & Polish past tense (я/ja …-ł/-ła). Romance
   1st-person adjective as backup. Never turn a 1st/3rd-person verb into a 2nd-person one.
3. **Referent gender (3rd person):** Spanish/Italian/Portuguese/French predicate adjective + Chinese
   他/她.
4. **Number — plural "you" (אתם):** take ONLY from a confound-free source: **Arabic أنتم** (gold),
   Chinese 你们, Spanish vosotros, Polish wy. **NEVER** from Russian вы / French vous / Italian voi /
   Spanish usted / German Sie / Turkish siz — those are polite-SINGULAR ("formal-you trap"). Also
   "you and X" / "you two" take a plural verb but stay a singular pronoun — the Hebrew is already right.
5. **Register/politeness:** German Sie, Japanese/Korean speech levels (affects tone, not gender).
6. **Meaning / mistranslation:** ALL languages together. If the Hebrew's meaning diverges from the
   English AND from the consensus of the professional translations, it is likely wrong → fix.

**Consensus principle:** flag/change a line only when the evidence AGREES against the Hebrew; a lone
noisy signal never flips a line. This separates real errors from parser noise and formal-you traps.

---

## Reference implementation (Witcher 3 — copy for any game)
- `games/witcher3/fleet/w3_lang_oracle.py` — the 2nd-person addressee parsers + consensus.
- `games/witcher3/fleet/w3qa_nim.py` — FULL line-by-line QA worker (already-translated mode): reviews
  every line vs ar/ru/pl/es/it, fixes gender+phrasing+mistranslation+foreign, monotonic guard +
  formal-you trap (`ag`/`num`/`formal` baked per line), emits `{he, iss}` for a human audit before bake.
- `games/witcher3/fleet/w3ut_nim.py` — TRANSLATE+gender worker (new-game / untranslated mode): sets
  the addressee gender from the consensus AT translation time, guard rejects a wrong-gender output.
- Shared parsers: `universal/gender_oracle.py` (ar_/ru_/pl_/es_/it_addressee, ar_addressee_strict).

Per new game: extract every shipped language to `extract/<lang>.json`, embed the parsers into the
game's fleet worker (workers run standalone on the VMs → no imports), bake `ag/num/formal` into the
corpus, run translate-with-verify (new) or review-only (translated). Related memories:
[[new-era-doctrine]], [[multilang-gender-context-check]], [[gender-oracle-from-game-langs]],
[[delegate-all-translation]], [[fleet-qa-review-hardening]].

## מסמכים קשורים
- באותה תיקייה: [[universal/AGENT_TRANSLATION_HANDOFF_TEMPLATE|AGENT_TRANSLATION_HANDOFF_TEMPLATE]], [[universal/GENDER_ORACLE_ROLLOUT|GENDER_ORACLE_ROLLOUT]], [[universal/NEW_GAME_GROUNDWORK_PLAYBOOK|NEW_GAME_GROUNDWORK_PLAYBOOK]], [[universal/QA_REVIEW_HANDOFF|QA_REVIEW_HANDOFF]], [[universal/cross_audit_dashboard|cross_audit_dashboard]]
- פלייבוקים כלל-פרויקטיים: [[CLAUDE_INDEX#⚙️ סביבה / כלים / אורchestration|CLAUDE_INDEX]]
