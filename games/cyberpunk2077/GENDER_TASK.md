# CP2077 — תיקון מגדר מהערבית של המשחק (ציר הפנייה)

**רקע:** האנגלית לא מבחינה מגדר, אז ה-femaleVariant שלנו (מוצג כש-V נקבה) קיבל לרוב
צורת **זכר** ("אתה שואל") במקום נקבה. הערבית המקצועית של המשחק כבר קבעה נכון ("تسألين/أنتِ").
`gender_oracle scan` השווה את כל הספיין מול הערבי ומצא **1,302 שורות** שבהן ה-femaleVariant
צריך להיות נקבה. השיטה המלאה: `universal/GENDER_ORACLE_ROLLOUT.md` + `orchestration/RULES.md` #12.

> **היקף מדויק:** זה ציר ה**פנייה** (אתה→את) בלבד — ה-batch הגדול והנראה. **לא** כולל: ציר
> הדובר (אני מוכן→מוכנה, דורש אורקל רוסי — בבנייה), שורות שהערבי בהן דו-משמעי, ומחלקת
> M==F תלוית-שחקן. אלה passות המשך נפרדות. אל תמציא תיקונים מעבר ל-worklist.

## הקלט
`games/cyberpunk2077/gender_oracle_delegate.jsonl` — 1,302 שורות, כל אחת:
```json
{"src":"base|dlc","section":"...","pk":"...","en":"<מקור אנגלי>",
 "he_female_current":"<עברית זכר, שגוי>","he_male":"<maleVariant לשמירה>",
 "ar_female":"<הערבי הנקבי = אמת-הקרקע>","target":"feminine"}
```

## מה לעשות (Claude בונה כלים + מאמת; הסוכן מתקן — [[delegate-all-translation]])
1. **האצל לסוכן Google** את התיקון: לכל שורה, לקחת את `he_female_current` ולהפוך את **פניית
   הנמען** לנקבה כך שתתאים ל-`ar_female` (אתה→את, שואל→שואלת, צריך→צריכה…). **לשנות אך ורק
   מורפמת-מגדר של הנמען** — לא לגעת במשמעות, ב-tokens (`<...>`,`{value}`,`%d`,`\n`,`[..]`),
   בשמות, במילות 1st-person ("אני יודע" נשאר), ולא בתארי 3rd-person. פלט: `he_female_fixed`.
   בנה handoff כמו הפרוטוקול הרגיל (folders + get_batch/merge_batch + INSTRUCTIONS עם דוגמאות
   מהערבי), md5-partition ל-N סוכנים, anti-cheat: דחה שורה שבה scaffold השתנה או שהנמען לא נקבה.
2. **אמת עצמאית (אל תסמוך על הסוכן):** לכל תיקון —
   - `universal/dualgender_verify_agents.classify_fill(fixed, current)` → scaffold זהה + שינוי-מגדר
     אמיתי + בלי niqqud/internal-edit.
   - `universal/gender_oracle.he_addressee(fixed) == "f"` (הנמען אכן נקבה עכשיו).
   דחה כל שורה שנכשלת → החזר לסוכן.
3. **החל לספיין** (`localization_translated.json` + `dlc_ep1_translated.json`) עם הבטיחות של
   `universal/dualgender_fix` (גיבוי `.bak.goracle.<ts>` + `qa.lock` + atomic + **guard פר-שורה:**
   כתוב רק אם הערך הנוכחי עדיין שווה ל-`he_female_current`). **maleVariant:** אם ריק → קבע אותו
   ל-`he_female_current` (הטקסט הזכרי) *לפני* שמחליפים את femaleVariant → פיצול נכון fV=נקבה/mV=זכר.
   (אפשר להרחיב `universal/gender_oracle_fix.py:apply()` — הוא כבר עושה בדיוק את זה; רק החלף את
   מקור ה-`fv_new` מהאינפלקטור הדטרמיניסטי לפלט המאומת של הסוכן.)
4. **אפה ופרוס** (המשחק סגור, WolvenKit פנוי, **לא** שתי אפיות base במקביל):
   - `python rebuild_onscreens_and_pack.py` (~90ש')
   - `python rebuild_subtitles_and_pack.py --sections-file <הסקשנים המושפעים>` (diff מול הגיבוי)
   - `python rebuild_dlc_and_pack.py --force-rebake`
5. **סרוק שוב לאימות:** הרץ `gender_oracle scan` מחדש — מספר האי-התאמות (1,390) צריך לצנוח כמעט לאפס.

## ⚠️ אל תעשה
- אל תריץ את `gender_oracle_fix.py --apply` (ההיפוך הדטרמיניסטי **over-flip** — הוכח:
  "מנסה"→"מנסי", "אני יודע"→"יודעת", "לך"→"לכי"). התיקון = **סוכן**, לא אינפלקטור.
- אל תתרגם מחדש משמעות. אל תפרסם בלי "פרסם".

## מסמכים קשורים
- באותה תיקייה: [[games/cyberpunk2077/OPUS_QA_REVIEW_REPORT_2026-06-15|OPUS_QA_REVIEW_REPORT_2026-06-15]], [[games/cyberpunk2077/human_review|human_review]], [[games/cyberpunk2077/human_review_g4|human_review_g4]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#cyberpunk2077|CLAUDE_INDEX_games]]
