# Witcher 3 — reglue round 2 (640 GLUED lines). Agent cleanup handoff.

These 640 lines already have a Hebrew translation, but it is **BROKEN**: an English word got left
untranslated and **glued straight onto the Hebrew** (no space), e.g.:
- `ג'רalt` → should be **גרלט** (the name *Geralt* leaked in as "alt")
- `אlegendריות` / `אlegendary` → should be **אגדיות / אגדי** (*legendary*)
- `ampire` → the Hebrew for *Vampire* = **ערפד**
- `נ.Executed`, `המ.executioner`, `שריון(turney)`, `ahaha` (laughter) …

Your job: **re-translate each `en` from scratch into clean, fluent Hebrew** — a proper full
translation with NO English word glued in and NO leftover Latin (unless it's a bare proper
name/code). Don't try to "patch" the broken Hebrew; translate the English source fresh.

## The loop (repeat until "All done!")
Work from this folder: `games/witcher3/fleet/agent_reglue2/`

1. `python get_batch.py 25`
   → writes `current_batch.json` = `{ "id": {"en":"...", "ar":"..."} , ... }`
   (use a smaller N like 8 if a batch has long lore paragraphs.)
2. **Translate every `en` into clean Hebrew** and put it in each entry. Two accepted shapes:
   - `{ "id": "התרגום העברי" }`
   - `{ "id": {"en":"...","ar":"...","he":"התרגום העברי"} }`
   Overwrite `current_batch.json`.
3. `python merge_batch.py`  → validates + merges the good ones into `hebrew.json`.
4. Repeat until `get_batch.py` prints **"All done!"**.

## Rules (same as round 1)
- Fluent, literary, period Witcher-3 Hebrew (dark-fantasy: bestiary, alchemy, gear names, journals,
  gwent cards, letters). Natural, not word-for-word.
- **Store LOGICAL Hebrew** (normal reading order). No letter-reversal, no RTL marks (`‮`/`‏`). The
  build bakes visual/RTL later.
- **NO niqqud.**
- **Preserve every structural token EXACTLY**, same count: `<br>` + any `<...>` tags, `{...}`,
  `%s`/`%d`/`%1` printf, `&...;` entities. The merge REJECTS a token-count mismatch.
- **NO leftover English word glued to Hebrew** — this is the whole point. Translate the word:
  Geralt=גרלט, Vampire=ערפד, legendary=אגדי, legend=אגדה, silver=כסף, sword=חרב, etc. Verify canon
  W3 Hebrew names (Geralt=גרלט, Ciri=סירי, Yennefer=יניפר, Triss=טריס, Skellige=סקליגה,
  Novigrad=נוביגרד, Velen=ולן, Nilfgaard=נילפגארד). A line that is JUST a bare proper name/code may
  be left verbatim (the merge allows that).
- **Gender:** where an `"ar"` field exists it is the game's professional translation — use it as the
  addressee gender/number ground truth (أنتَ=אתה, أنتِ=את, أنتم=אתם, feminine ـة).

## Do NOT
- Don't leave any English prose word inside the Hebrew (the merge's `no-hebrew` + your own care).
- Don't touch any file except `current_batch.json`. Don't run other scripts. Don't `git`.

When done: `hebrew.json` holds clean Hebrew for all 640. The main PC folds it into the game + re-runs QA.
