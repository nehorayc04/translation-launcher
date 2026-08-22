# 📏 RULES — כללים משותפים לכל המשחקים

הכללים שכל הנחיה לסוכן מקבלת אוטומטית. כשמתגלה כלל חדש שטוב לכמה משחקים — המוח
מוסיף אותו כאן (וליומן למטה) ומחיל על כל הנחיה עתידית. כללים ספציפיים-למשחק
חיים אצל המשחק עצמו (ראה "מצביעים" למטה), לא כאן.

## כללי-ליבה (חלים על כל משחק)

1. **Claude לא מתרגם בעצמו.** התרגום ותיקוני-התרגום נעשים תמיד ע"י סוכן Google
   או LM מקומי. Claude רק בונה כלים וכותב הנחיות. ‎[[delegate-all-translation]]
2. **Arabic-slot hijack.** אין locale עברי כמעט אף פעם, אבל יש ערבית (RTL) →
   משגרים עברית בתוך חריץ הערבית ויורשים את ה-bidi של המנוע בחינם.
3. **Visual מול Logical bidi — תלוי מנוע.** מנוע שעושה bidi (כמו כתוביות WD2) →
   אחסן עברית **לוגית**. מנוע ללא bidi (תפריט WD2/Anno/GTA/AC2) → אחסן **ויזואלית**
   (הפוך כל ריצה עברית + סדר הריצות). תמיד להוכיח A/B in-game לפני ריצה מלאה.
4. **שמור tokens מילה-במילה.** `<ts>`, `[TOKEN]`, `{VALUE}`, `%d`/`%s`/`%%`,
   `&rlm;`/`<br>`, `[[S:cue]]` — multiset זהה למקור, אחרת הבדיקה דוחה.
5. **passthrough לשמות/קודים.** קבל תוצאה בלי עברית כשהמקור הוא שם-פרטי/קוד
   (≤4 מילים או בלי מילה אנגלית אמיתית). אחרת הסוכן/QA נתקע לנצח על שמות.
6. **anti-cheat — attestation by enumeration.** סוכן חלש מנסה לזייף "All done"
   (ממלא אנגלית או `{}` ריק). המיזוג מקבל שורה רק אם יש לה ערך אמיתי / `"OK"`,
   ודוחה אנגלית-על-פרוזה (≥2 מילים lowercase). תמיד לסרוק עצמאית אחרי "done".
7. **לעולם לא לסמוך על בדיקת-המיזוג של הסוכן.** אחרי כל ריצת סוכן, Claude סורק
   את כל הספיין: `TOK.findall(en)==TOK.findall(he)` + foreign + niqqud + כיסוי.
8. **UTF-8 stdout בכל סקריפט** (`sys.stdout.reconfigure(...)`) + הרצת ילדים עם
   `PYTHONIOENCODING=utf-8`. אחרת `→`/`…`/emoji מפילים את התהליך ב-cp1255.
9. **פרסום בלי לשבור `releases/latest`.** להשאיר תג FULL יציב אחד ולעשות
   `--clobber` לנכסים שלו; לא ליצור תגי `vX-beta.N` שמסתדרים מתחת ליציב.
10. **סנכרון 4 משטחים.** גרסה+sha+stage חייבים להסכים: Supabase `games`,
    `mod_version_history`, ה-`manifest.json` ב-GitHub, וה-zip.

## מצביעים לכללים הספציפיים לכל משחק

| משחק | היכן הכללים/המילון |
|---|---|
| spiderman2 | `games/spiderman2/work/` + `names_research.json` + handoff |
| watchdogs2 | `games/watchdogs2/PIPELINE.md` + `agent_handoff*/INSTRUCTIONS.md` |
| godofwar_ragnarok | `games/godofwar_ragnarok/PIPELINE.md` + `work/` glossary |
| anno1800 | `games/anno1800/agent_handoff/INSTRUCTIONS.md` (Belle-Époque) |
| gtav | `games/gtav/agent_handoff_full/INSTRUCTIONS.md` |
| cyberpunk2077 | `games/cyberpunk2077/qa_review_*` + glossary בפלייבוק |
| הכול | `universal/NEW_GAME_GROUNDWORK_PLAYBOOK.md` + `AGENT_TRANSLATION_HANDOFF_TEMPLATE.md` |
| מגדר (הכול) | `universal/GENDER_ORACLE_ROLLOUT.md` — מגדר מהלוקל הממוגדר של המשחק (כלל #12) |

11. **read-modify-write של ארכיון משחק = in-place, לא full-repack.** כשעורכים ארכיון
    גדול במקום (RPF7/forge/RDA וכו') בשביל deploy — לשמר את הפריסה הפיזית המקורית
    (offsets + padding) ולהוסיף רק את הקבצים ששונו בסוף + לתקן רק את ה-TOC entry שלהם.
    **full-repack שאורז הכול מחדש מפיל את ה-padding המקורי והמנוע עלול להיכשל** (GTA:
    `ERR_GEN_ZLIB_2` אחרי שה-update.rpf הצטמצם 2.6GB→1.8GB). תמיד להשוות גודל-פלט מול
    המקור — צמצום דרמטי = דגל אדום. ‎[[gtav-groundwork-go]]
12. **מגדר/מספר מהלוקל הממוגדר של המשחק, לא מאנגלית.** אנגלית לא מבחינה מגדר → תרגום
    ממנה מנחש. המשחק כבר כולל תרגום מקצועי ממוגדר (**ערבית** = הכי קרוב לעברית: أنتَ/أنتِ
    = אתה/את; אם אין — רוסית לדובר, ספרדית/צרפתית/גרמנית לרפרנט). **מקור המשמעות = אנגלית,
    מקור המגדר = הלוקל הממוגדר.** לתרגומים קיימים: פאס תיקון דטרמיניסטי (`gender_oracle
    scan` → `dualgender_inflect` — מתקן **רק** את המורפמה, אפס תרגום-מחדש). לתרגום חדש:
    לצרף להאנדוף את איתות-המגדר פר-שורה. השיטה המלאה + טבלת מקור פר-משחק:
    `universal/GENDER_ORACLE_ROLLOUT.md`. ‎[[gender-oracle-from-game-langs]]

## יומן כללים שנוספו

- 2026-06-29 — נוצר הרישום. כללי-הליבה לעיל נדלו מ-CLAUDE.md והפלייבוק הקיים.
- 2026-06-26 — כלל 11 (in-place vs full-repack) נוסף מלקח ה-ZLIB של GTA launcher.
- 2026-07-06 — כלל 12 (מגדר מהלוקל הממוגדר של המשחק) נוסף; `GENDER_ORACLE_ROLLOUT.md`.

## מסמכים קשורים
- באותה תיקייה: [[orchestration/BOOT|BOOT]], [[orchestration/COMMANDS|COMMANDS]], [[orchestration/DOCTRINE|DOCTRINE]], [[orchestration/FLEET|FLEET]], [[orchestration/HANDOFF|HANDOFF]], [[orchestration/MISSION|MISSION]], [[orchestration/README|README]]
- מפת הבקרה: [[CLAUDE_INDEX#⚙️ סביבה / כלים / אורchestration|CLAUDE_INDEX]]
