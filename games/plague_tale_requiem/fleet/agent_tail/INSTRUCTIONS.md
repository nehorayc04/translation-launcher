# A Plague Tale: Requiem — Hebrew TAIL translation (agent handoff)

You are a senior **Hebrew** game localizer. Translate the remaining lines of **A Plague Tale:
Requiem** — a grim historical-fiction game set in **1349, plague-ravaged southern France** (the
Inquisition, swarms of rats, alchemy). Main characters: **Amicia, Hugo, Lucas, Beatrice, Vaudin,
Sophia**. Register = serious, literary, period-appropriate (not modern slang).

Work entirely inside THIS folder. Do it in a loop, ~60 lines at a time, until "All done!".

## The loop (repeat until done)
1. `python get_batch.py 60`  → writes `current_batch.json` = `{ "KEY": {"en": "...", "ar": "..."} }`.
   If it prints **"All done!"**, stop — you're finished.
2. Open `current_batch.json`. For **every** entry, translate the **`en`** into fluent, natural,
   period Hebrew and put the Hebrew **in the value** (either replace the object with the Hebrew
   string, or add an `"he": "..."` field to the object — both are accepted).
3. `python merge_batch.py`  → validates + banks the good ones; anything rejected stays queued and
   comes back in the next `get_batch`. Read the reject reasons and fix them next round.
4. Go back to step 1.

## Hard rules (a line is REJECTED if broken)
- **Hebrew only** (Hebrew + Latin/digits allowed). No Arabic, Cyrillic, CJK, Thai, etc.
- **No niqqud** (vowel points).
- **Keep every token VERBATIM** — same count, same form:
  - `{STR_...}` runtime button tokens (e.g. `{STR_Jump}`) — copy exactly, never translate.
  - the pipe **`|`** — it is an in-value **LINE BREAK**, keep the same number of `|` in the same places.
  - `%d` / `%s` / `%%` and similar printf specs — copy exactly.
- **Meaning** comes from **`en`**. **`ar`** (the same line already localized to Arabic) is ONLY a
  **gender/number oracle**: Arabic marks what English hides — who is addressed (أنتَ=אתה / أنتِ=את /
  أنتم=אתם), the speaker's gender, feminine referents (ـة → ...ה), plurals. Make your Hebrew match
  the gender/number the Arabic shows (a line spoken to a woman → את + feminine verbs; to a man →
  אתה + masculine). **Do NOT translate from the Arabic and never copy Arabic words.**
- **Names stay Hebrew transliteration** (Amicia → אמיסיה, Hugo → הוגו, Lucas → לוקא). Brand/code
  tokens stay Latin.
- Write **LOGICAL** Hebrew (normal reading order). RTL/visual baking happens later — do NOT reverse
  anything yourself.

## Do NOT
- Do not edit `get_batch.py` / `merge_batch.py` / `to_translate.json` / `build_tail.py`.
- Do not write an "auto" script that fills values with the English or with placeholders — the merge
  gate rejects untranslated English prose, and that just wastes rounds.
- Do not skip a line by leaving it English (unless it's genuinely a bare name/code with no words).

When `get_batch.py` prints **"All done!"**, report back: total lines translated. That's it.
