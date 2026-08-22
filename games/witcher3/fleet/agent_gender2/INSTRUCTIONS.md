# Witcher 3 — subtitle gender/number fix (191 lines). Agent handoff.

These 191 Hebrew subtitle lines already read fluently, but the **addressee gender or number
is WRONG** — the line addresses the listener as masculine when it should be feminine, singular
when it should be plural, or the reverse. Example bugs seen in-game:
- `אתה חושבת` → should be `את חושבת` (feminine addressee)
- `היזהר מהאיל` (sing.) → should be `היזהרו מהאיל` (the crowd is addressed — plural)
- `למה את/ה כאן` → pick ONE form (`למה את כאן` / `למה אתה כאן`), never the `את/ה` slash hedge

Your job: **re-INFLECT each line to the correct gender/number — change ONLY the gender/number
morphemes, keep every other word identical.** This is NOT a re-translation. Do not rephrase, do
not improve wording, do not touch names/tags/punctuation — only flip אתה↔את↔אתם, the verb
endings (חושב↔חושבת↔חושבים), possessives (שלך↔שלכם), etc.

## The ground truth = the Arabic
Each entry has an `"ar"` field = the game's **professional Arabic** translation. Arabic marks the
addressee exactly like Hebrew, so it is the authority:
- `أنتَ` / masculine verb = **masculine singular** → אתה + masc verb
- `أنتِ` / ـين feminine verb / ـكِ = **feminine singular** → את + fem verb
- `أنتم` / أنتنّ / plural verb (ـوا, تـ…ون) / ـكم = **plural** → אתם + plural verb
The `"target"` field is my automatic guess (`f`/`m`/`pl`) from the Arabic — trust the Arabic text
itself over `target` if they ever disagree.

## If a line is ALREADY correct
Some flags are false alarms (the masc/fem word was a 1st/3rd-person verb, not the addressee, or my
oracle misread it). If after reading EN+AR the Hebrew addressee is **already right**, answer the
literal string `SKIP` for that id — do not force a wrong change.

## The loop (repeat until "All done!")
Work from this folder: `games/witcher3/fleet/agent_gender2/`
1. `python get_batch.py 40`
   → writes `current_batch.json` = `{ "id": {"en":..,"he":..,"ar":..,"target":".."} , ... }`
2. For each id, replace its value with the corrected Hebrew string (or `SKIP`). Two accepted shapes:
   - `{ "id": "התיקון העברי" }`
   - `{ "id": {"en":..,"he":..,"ar":..,"target":"..","fix":"התיקון העברי"} }`
   Overwrite `current_batch.json`.
3. `python merge_batch.py`  → validates + merges the good ones into `fixed.json`.
4. Repeat until `get_batch.py` prints **"All done!"**.

## Hard rules (the merge REJECTS violations — a rejected line just comes back next round)
- **Inflection ONLY.** Every non-Hebrew character (Latin names, digits, `<...>` tags, `{...}`,
  `%d`/`%s`, `&...;`, punctuation) and every non-gender word must stay **byte-identical**. The
  merge compares the "scaffold" (everything that isn't a Hebrew letter) and rejects any change to
  it. So don't add/remove/reorder words — only re-inflect the Hebrew.
- **Store LOGICAL Hebrew** (normal reading order). No letter-reversal, no RTL marks (`‮`/`‏`).
- **NO niqqud.** **NO Arabic/foreign letters** in the output.
- Keep every structural token EXACTLY, same count.

## Do NOT
- Don't re-translate or rephrase — only fix gender/number.
- Don't touch any file except `current_batch.json`. Don't run other scripts. Don't `git`.

When done: `fixed.json` holds all 191. The main PC folds it into `hebrew.json`, re-verifies against
the Arabic, and rebuilds the game.
