# Witcher 3 — untranslated subtitles (1,717 lines still showing Arabic in-game). Agent handoff.

These 1,717 Witcher-3 subtitle lines were **missed by the translation** — in-game they still show the
original **Arabic** (a visible bug). Each has an English source (and Russian). Translate the **English**
into fluent Hebrew. Set the **addressee gender/number** correctly using the other languages (see below).

## The loop (repeat until "All done!")
Work from this folder: `games/witcher3/fleet/agent_untranslated/`
1. `python get_batch.py 40`   (use 15 if the batch has long lore paragraphs)
   → `current_batch.json` = `{ "id": {"en":..,"ar":..,"ru":..,"gender":"f"/"m"/"pl"/""} , ... }`
2. Translate every `en` into Hebrew; put the Hebrew in each id. Two accepted shapes:
   - `{ "id": "התרגום העברי" }`
   - `{ "id": {"en":..,"ar":..,"ru":..,"gender":"..","he":"התרגום"} }`
   Overwrite `current_batch.json`.
3. `python merge_batch.py`  → validates + merges into `hebrew_out.json`.
4. Repeat until `get_batch.py` prints **"All done!"**.

## Translation rules (Witcher 3, period register)
- Fluent, literary, period-appropriate dark-fantasy Hebrew (bestiary/alchemy/journals/gwent/letters).
  Natural, not word-for-word.
- **Store LOGICAL Hebrew** (normal reading order). No letter-reversal, no RTL marks (`‮`/`‏`). The build
  bakes visual/RTL later.
- **NO niqqud.** No Arabic/other-script letters in the output (Latin is fine for names/tokens).
- **Preserve every structural token EXACTLY**, same count: `<br>` + any `<...>` tags, `{...}`,
  `%s`/`%d`/`%1` printf, `&...;` entities. The merge REJECTS a token-count mismatch.
- **Names — canonical W3 Hebrew** (verify, don't invent): Geralt=גרלט, Ciri=סירי, Yennefer=יניפר,
  Triss=טריס, Dandelion=דנדליון, Novigrad=נוביגרד, Velen=ולן, Skellige=סקליגה, Nilfgaard=נילפגארד,
  Roach=רואץ'. A line that is JUST a bare name/code may be copied verbatim.

## ⚠️ GENDER / NUMBER of the addressee — this is required, get it right the FIRST time
Do NOT default to masculine. Decide the addressee's gender/number from the **other languages of the
same line** (they mark what English hides), in this order of trust:
- **`"gender"` field** = my automatic multi-language consensus (`f`/`m`/`pl`) — trust it when present.
- **`"ar"` (Arabic)** — أنتَ=אתה(m), أنتِ=את(f), أنتم=אתם(pl), feminine verb ـين/ـكِ = fem.
- **`"ru"` (Russian)** — ты + past -л(m)/-ла(f); **вы = plural OR polite-singular** (don't treat вы as
  plural unless Arabic also says أنتم).
So: masculine addressee → אתה + masc verbs; feminine → את + fem verbs (חושבת, תגידי, קחי); true plural
(Arabic أنتم) → אתם + plural verbs. When nothing marks it and context is neutral, use masculine singular.

## Do NOT
- Don't leave any English/Arabic prose in the Hebrew (a bare proper name/code is the only allowed non-Hebrew).
- Don't touch any file except `current_batch.json`. Don't run other scripts. Don't `git`.

When done: `hebrew_out.json` holds all 1,717. The main PC folds it into the game + re-verifies gender.
