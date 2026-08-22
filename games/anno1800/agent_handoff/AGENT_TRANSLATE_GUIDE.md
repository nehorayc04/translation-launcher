# Anno 1800 EN→Hebrew translation guide (for translator agents)

You translate **Anno 1800** (Ubisoft — Belle-Époque / late-19th-century city-builder)
UI + quest text from English to **Hebrew**.

## I/O
- INPUT: a JSON object `{guid: english_string}` (the file path is given to you).
- OUTPUT 1 — `trans_part_<K>.json`: JSON object `{guid: hebrew_string}` for every string you translate.
- OUTPUT 2 — `skip_part_<K>.json`: JSON array `[guid, ...]` of guids you did NOT translate (codes/placeholders).
- Every input guid must appear in EXACTLY ONE of the two files.

## HARD rules (a violation makes the line get rejected on merge)
1. Output **Hebrew**. Latin letters allowed ONLY for names/brands kept in Latin (see glossary). NEVER any other script (no Arabic, Cyrillic, Greek, CJK, Thai…).
2. **NEVER use niqqud / vowel points** (no ַ ָ ֵ ִ ֹ ֻ ּ ֿ etc.). Plain Hebrew letters only. (This is the #1 cause of rejections — double-check.)
3. **Preserve every token character-for-character, same COUNT and same FORM:**
   - Tags `<i> </i> <b> </b>` and line breaks. COPY THE EXACT FORM: if the source has `<br />` (with a space) keep `<br />`; if `<br/>` keep `<br/>`. Never change spacing/count.
   - Square-bracket data-binds, e.g. `[NotificationContext Value(Area) Area CityName]`, `[ToolOneDataHelper FirstPartyServiceName]`, `[GamepadActionManager GamepadButtonTooltip(RS_Vertical)]`, `[Conditions QuestCondition AchievedPercentage]`. Copy verbatim; DO NOT translate anything inside `[ ]`; keep the same count.
   - printf specs `%ls %d %s %i %%` etc. — copy verbatim.
   Translate ONLY the prose OUTSIDE these tokens.
4. Store **LOGICAL** reading order (type Hebrew normally). Do NOT reverse anything — a later build step handles RTL.
5. Register: natural, fluent, literary Hebrew fitting a refined 19th-century industrial setting. Idiomatic, not word-for-word.

## SKIP (put guid in skip_part_<K>.json, NOT trans)
A string that is purely a code / not real text: just `%ls`; an ALL_CAPS_UNDERSCORE id like `MovieCapture_Moderate`; a string starting with `!`; a bare data-bind with no prose; internal tokens like `Human0`, `Profile_*`, `TEST_*`. If a string has ANY real words, TRANSLATE it (don't skip).

## Names
Transliterate people/place names to Hebrew (Paloma Valente→פלומה ולנטה, Old Nate→נייט הזקן, Enbesa→אנבסה, Archibald→ארצ'יבלד). Keep these product names in LATIN: `Anno 1800`, `Empire of the Skies`, `DLC`. A class name in parentheses like `(Boreas Class)` → transliterate: `(מחלקת בוריאס)`.

## Glossary (use consistently)
airship=ספינת אוויר · rigid airship=ספינת אוויר נוקשה · airship platform=רציף ספינות אוויר · hangar=האנגר · post office=סניף דואר · post box=תיבת דואר · mail=דואר · airmail=דואר אוויר · item=פריט · module=מודול · good/goods=סחורה/סחורות · workforce=כוח עבודה · bauxite=בוקסיט · helium=הליום · aluminium=אלומיניום · oil=נפט · coal=פחם · iron=ברזל · mine=מכרה · deposit=מרבץ · furnace=כבשן · flamethrower=להביור · flak=נ"מ · monitor(ship)=מוניטור · torpedo=טורפדו · hull=גוף · drop goods=סחורות הטלה · trade route=מסלול סחר · trading post=תחנת סחר · charter=צ'רטר · warehouse/storage=מחסן/אחסון · ornament=קישוט · Old World=העולם הישן · New World=העולם החדש · Farmer=חקלאי · Worker=פועל · Artisan=אומן · Engineer=מהנדס · Investor=משקיע · Jornalero=חורנלרו · Obrero=אוברו · Attractiveness=אטרקטיביות · Expedition=משלחת · Quest=משימה · the Queen=המלכה · happiness=אושר · productivity=פריון · residents=תושבים · island=אי · harbour=נמל · ship=ספינה · skull(expedition difficulty)=גולגולת.

After writing both files, reply with ONLY: `part<K> done: translated=<N> skipped=<M>`.
