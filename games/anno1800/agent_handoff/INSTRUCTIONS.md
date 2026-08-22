# Anno 1800 — Hebrew translation handoff (RESUME instruction for a fresh agent)

You are continuing an existing EN→Hebrew translation of **Anno 1800** (Ubisoft —
a Belle-Époque / late-19th-century industrial city-builder). About **52,200 of
58,682** strings are already translated (~93%); **only ~4,400 remain** — you are
finishing the final stretch. Your job: translate the rest, in batches, until
`get_batch.py` prints **All done!**. Do NOT stop between batches — keep looping
until it says done. The loop ALWAYS resumes from where it stopped: `get_batch.py`
only ever hands you strings that are still untranslated, so you cannot lose work.

Work from this folder:
`c:\Users\Nehoray_Cohen\Projects\Game translator\games\anno1800\agent_handoff`

## The loop (repeat until you see "All done!")
1. `python get_batch.py`
   → writes `current_batch.json` = `{guid: english}` (the next 400 untranslated).
   → if it prints **All done!**, you are finished — stop.
2. Translate EVERY string in `current_batch.json` per the RULES below.
3. Write `trans_part_1.json` = `{guid: hebrew}` for the strings you translated.
   For strings that are pure codes/placeholders (see SKIP), instead append their
   guids to the list in `skip.json` (a JSON array) — do NOT put them in trans.
   Every guid in the batch must end up in EXACTLY one place (trans_part_1.json OR skip.json).
4. `python loop_merge.py`
   → validates + merges the clean lines into `hebrew.json`, and prints any line it
   REJECTED (TAG MISMATCH / FOREIGN SCRIPT / EMPTY). Fix ONLY the rejected guids in
   `trans_part_1.json` and re-run `loop_merge.py` until 0 problems.
5. Go back to step 1.

When finished, also run: `copy hebrew.json ..\work\hebrew.json` (sync for the build).

## HARD RULES (a violation makes the line get rejected)
1. Output **Hebrew**. Latin letters allowed ONLY for names/brands kept in Latin
   (see glossary). NEVER any other script (no Arabic, Cyrillic, Greek, CJK, Thai…).
2. **NEVER use niqqud / vowel points** (no vowel marks). Plain letters only.
3. **Preserve every token character-for-character, same COUNT and same FORM:**
   - Tags `<i> </i> <b> </b>` and line breaks. COPY THE EXACT FORM you see: if the
     source has `<br />` (with a space) keep `<br />`; if `<br/>` keep `<br/>`.
     Never change the spacing or the count.
   - Square-bracket data-binds, e.g. `[NotificationContext Value(Area) Area CityName]`,
     `[ToolOneDataHelper FirstPartyServiceName]`, `[AssetData([RefGuid] Text)]`,
     `[GamepadActionManager GamepadButtonTooltip(RS_Vertical)]`. Copy verbatim, keep
     the same count, and DO NOT translate anything inside `[ ]`.
   - printf specs `%ls %d %s %i %%` — copy verbatim.
   Translate ONLY the prose OUTSIDE these tokens.
4. Store **LOGICAL** reading order (type Hebrew normally). Do NOT reverse anything —
   a later build step handles the on-screen RTL.
5. **Output strictly valid JSON** — escape every `"` inside a Hebrew value as `\"`.
6. Register: natural, fluent, literary Hebrew fitting a refined 19th-century
   industrial setting. Idiomatic, not word-for-word.

## SKIP (put the guid in skip.json, NOT translated)
A string that is purely a code / not real text: just `%ls`; an ALL_CAPS_UNDERSCORE
id like `MovieCapture_Moderate`; a string starting with `!`; a bare data-bind with no
prose; internal tokens like `Human0`, `Profile_*`, `TEST_*`, `small_feedback_ship01`.
If a string has ANY real words, TRANSLATE it (don't skip).

## Names
Transliterate people/place names to Hebrew (Paloma Valente=פלומה ולנטה, Old Nate=נייט
הזקן, Enbesa=אנבסה, Archibald=ארצ'יבלד, Mercier=מרסייה). A class name in parens like
`(Boreas Class)` = `(מחלקת בוריאס)`. Keep these PRODUCT names in LATIN: `Anno 1800`,
`Empire of the Skies`, `DLC`.

## Glossary (use consistently)
airship=ספינת אוויר · rigid airship=ספינת אוויר נוקשה · airship platform=רציף ספינות אוויר ·
hangar=האנגר · post office=סניף דואר · post box=תיבת דואר · mail=דואר · airmail=דואר אוויר ·
item=פריט · module=מודול · good/goods=סחורה/סחורות · workforce=כוח עבודה · bauxite=בוקסיט ·
helium=הליום · aluminium=אלומיניום · oil=נפט · coal=פחם · iron=ברזל · mine=מכרה · deposit=מרבץ ·
furnace=כבשן · flamethrower=להביור · flak=נ"מ · monitor(ship)=מוניטור · torpedo=טורפדו ·
hull=גוף · drop goods=סחורות הטלה · trade route=מסלול סחר · trading post=תחנת סחר ·
charter=צ'רטר · warehouse/storage=מחסן/אחסון · ornament=קישוט · Old World=העולם הישן ·
New World=העולם החדש · Farmer=חקלאי · Worker=פועל · Artisan=אומן · Engineer=מהנדס ·
Investor=משקיע · Jornalero=חורנלרו · Obrero=אוברו · Attractiveness=אטרקטיביות ·
Expedition=משלחת · Quest=משימה · the Queen=המלכה · happiness=אושר · productivity=פריון ·
residents=תושבים · island=אי · harbour=נמל · ship=ספינה · skull(expedition difficulty)=גולגולת ·
Paloma=פלומה · Daily Courier=השליח היומי · Grand Gallery=הגלריה הגדולה.

## After ALL strings are translated (you'll see "All done!")
Tell Nehoray (he runs the final build): `python work/build_mod.py` rebuilds the mod
(VISUAL transform + Hebrew font injection) into `Documents\Anno 1800\mods\
zzz_hebrew_translation\`. Activation in-game: Settings → Text Language = **Korean**,
Audio = English, restart. Then publish (GitHub `anno1800-hebrew-mods` + Worker slug
`anno1800-hebrew` + Supabase `games` + `mod_version_history`).
