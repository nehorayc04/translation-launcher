# Witcher 3 — reglue tail (89 lines). Agent translation handoff.

You are finishing the **last 89 lines** of the Hebrew translation for **The Witcher 3: Wild Hunt**.
The cloud fleet stalled on these because they are the **longest lore/book paragraphs** in the game
(some are 2,000+ characters) plus a few short ones. Translate them directly — you are faster than the
throttled fleet on the long ones.

## The loop (repeat until "All done!")
Work in this folder. Run every command from here:
`games/witcher3/fleet/agent_reglue/`

1. `python get_batch.py 20`
   → writes `current_batch.json` = `{ "id": {"en": "...", "ar": "..."} , ... }` (20 lines; use a
   smaller N like 8 when the batch has giant paragraphs).
2. **Translate every `en` into fluent Hebrew** and put the Hebrew in each entry. Two accepted shapes —
   either is fine:
   - `{ "id": "התרגום העברי" }`  ← simplest
   - `{ "id": {"en":"...", "ar":"...", "he":"התרגום העברי"} }`  ← keep the object, add `"he"`
   Overwrite `current_batch.json` with your translations.
3. `python merge_batch.py`
   → validates + merges the good ones into `hebrew.json`; anything rejected stays queued for the next
   `get_batch.py`. It prints how many merged / rejected and how many remain.
4. Repeat 1–3 until `get_batch.py` prints **"All done!"**.

## Translation rules (Witcher 3, period register)
- **Register:** fluent, literary, period-appropriate Hebrew — this is dark-fantasy medieval prose
  (bestiary entries, alchemy recipes, journals, gwent, letters). Books/notes read like real
  period documents. Natural Hebrew, never a stiff word-for-word calque.
- **Store LOGICAL Hebrew** — write it in normal reading order. **Do NOT reverse letters, do NOT add
  RTL marks (no `‮`/`‏`).** The build step bakes the visual/RTL order later.
- **NO niqqud** (vowel points). Plain letters only. (The merge auto-strips niqqud, but don't add it.)
- **Preserve every structural token EXACTLY**, same count, unchanged:
  - `<br>` line breaks, and any other `<...>` tags — keep them verbatim, in place.
  - `{...}` braces, `%s`/`%d`/`%1`/printf specs, `&...;` entities — verbatim.
  The merge REJECTS a line whose token multiset differs from the English, so copy them carefully.
- **Names stay in their established form.** Witcher canon in Hebrew (verify the standard spelling, don't
  invent): Geralt=גרלט, Ciri=סירי, Yennefer= יניפר, Triss=טריס, Dandelion=ריבן/דנדליון (use the common
  Hebrew fan/official form), Novigrad=נוביגרד, Velen=ולן, Skellige=סקליגה, Nilfgaard=נילפגארד. A line
  that is JUST a proper name / code / number may be left as-is (the merge allows a verbatim copy for a
  bare name).
- **Gender:** where an `"ar"` (Arabic) field is present it is the game's professional translation — use
  it as the ground truth for **addressee gender/number** (أنتَ=אתה, أنتِ=את, أنتم=אתם, feminine ـة, 2nd-fem
  verb ـين). If there's no `ar`, use the most natural default from context.
- The GIANT book/journal paragraphs: translate the WHOLE thing, keep every `<br>` in place, keep it
  readable. Don't summarize or drop sentences.

## Do NOT
- Don't translate into anything but Hebrew (no leftover English prose, no Arabic/other script — the
  merge rejects those). A bare proper-name/code copied verbatim is the only allowed non-Hebrew.
- Don't touch any file except `current_batch.json` (and let the scripts write `hebrew.json`).
- Don't run any other script. Don't `git`. Just the get→translate→merge loop.

When you finish: `hebrew.json` holds all 89. The main PC's pull folds it into the game automatically.
