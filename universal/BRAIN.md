# מוח-הלוקליזציה הדטרמיניסטי — `universal/brain.py` (עידן חדש 2)

הופך את הצי מ"כלי-תרגום פר-שורה" ל**סוכן-לוקליזציה אוטונומי שמפתח מוח-ידע מתמשך** — מילון קשיח
שגדל לאט לאט על ידי למידה בזמן-אמת, עם **שער-אמון** שמונע הרעלה. זהו ה**גרעין הדטרמיניסטי**
(ללא embeddings; שכבת ה-RAG/pgvector היא תוספת נפרדת). Claude בונה+מאמת, **לא מתרגם**
([[delegate-all-translation]]). משלים את `universal/multilang_review.py` + `universal/MULTILANG_REVIEW.md`.

## ⚠️ הדיסציפלינה הקריטית
המוח לומד מ**פלט-צי לא-מהימן**. לקח **לעולם** לא נכנס למילון הסמכותי עד ש-`validate_lesson()` עובר
**וגם** `promote(...)` נקרא במפורש עם `approved_by` (ברירת-מחדל דחייה). בלי השער — מונח שגוי שנלמד
מוקדם מרעיל כל שורה עתידית וכל משחק עתידי. ה-Vector DB הוא ה-20% הקל; שער-האמון הוא ה-80% שקובע.

## שכבות (המפורש גובר בקנון: universal < game < run)
- **universal** — `universal/brain_universal.json`: תיקונים דטרמיניסטיים (הסרת ניקוד/zero-width),
  כללי-הנחיה (RTL/tokens/ניטרלי-סביב-משתנה/brand). מונחים כמעט ריקים — גדל דרך השער.
- **game** — `games/<game>/fleet/brain_glossary.json`: מונחים קנוניים, lore/פלגים, do_not_translate,
  מגדר-רפרנט, `variants` (צורות-עברית שגויות ש-`canon()` מחליף).
- **run** — overlay אופציונלי להחלטות תוך-כדי-ריצה.

## ה-4 מנגנונים
1. **מילון מדורג** — `Brain.for_game(fleet_dir)` טוען universal + game (+run). `terms_in(en)` מחזיר
   את המונחים הקנוניים שמופיעים בשורה (הכי-ארוך-קודם, dedup).
2. **הזרקת-מונחים בדיספאטץ'** — `inject_fragment(en)` → פסקה עברית קומפקטית (`Dead Eye → עין המוות ·
   Pinkerton → [שמור לטיני]`) שנדחפת ל-`sys`/`src` של ה-worker. + `rules_text()` להנחיות.
3. **`canon(he, en)` ב-merge** — מחליף כל `variant` שגוי בעברית בצורה הקנונית, prefix-aware (אות-תחילית
   אחת מ-והבלמכש), do_not_translate נשמר. תיקון מונח מתקן את **כל הקורפוס** בלי תרגום-מחדש (רטרואקטיבי).
4. **consistency-audit → תיבת-לקחים + שער** — `audit_consistency(banked)` מוצא (א) **סטייה** (אותה
   אנגלית קצרה עם >1 עברית → majority=קנוני, minority=variants) ו-(ב) **מונח-חסר** (מונח-מילון שאנגליתו
   בשורה אבל העברית הקנונית נעדרת). ה-findings הם **מועמדים** → `LessonInbox.add_all()` → אדם/אימות-יריב
   → `promote(lesson, glossary_path, approved_by)`.

## שער-הקידום (`promote`)
- מסרב בלי `approved_by`, ומסרב על כשל-`validate_lesson` (no-english / no-hebrew / niqqud / כתב-זר /
  regex-שבור). `term_absent` = advisory בלבד (לא יוצר מונח אוטומטית — אדם/סוכן קובע את הקנוני האמיתי).
- `divergence` → מונח עם `variants` (ה-minority). `repair` → regex. `rule` → טקסט-הנחיה.
- כל רשומה שקודמה נושאת `approved_by` + `provenance` + `confidence` (auditability).

## מיגרציה מ-name_registry קיים
`ingest_name_registry(registry_path, fixes_path, glossary_path)` — ממיר
`name_registry.json` (en→he) + `name_fixes.json` (שגוי→נכון) למילון-מוח; ה-fixes הופכים ל-`variants`
ש-`canon()` אוכף. (RDR2/PT/SM2 כבר מחזיקים את הקבצים האלה.)

## שימוש במתאם-צי (דיספאטץ' + merge)
```python
import sys, os; sys.path.insert(0, "<repo>/universal")
import brain
B = brain.Brain.for_game(FLEET_DIR)                     # universal + game glossary

# בדיספאטץ' (בונה sys/src לכל שורה):
frag = B.inject_fragment(line_en); guide = B.rules_text()   # דחוף ל-sys

# ב-merge (pull), לכל שורה שחזרה:
he = B.canon(B.repairs_apply(worker_he), en=line_en)        # אוכף מונחים + תיקונים דטרמיניסטיים

# מדי N שורות (למידה):
inbox = brain.LessonInbox(os.path.join(FLEET_DIR, "brain_lessons.jsonl"))
inbox.add_all(B.audit_consistency(banked))                  # מועמדים לא-מהימנים
# אז אדם/אימות-יריב:
ok, msg = brain.promote(lesson, os.path.join(FLEET_DIR, "brain_glossary.json"), approved_by="claude-verify")
```
המנוע זהה לכל משחק — מתורגם (ביקורת) או חדש (תרגום). המוח נבנה לאט, מאומת בכל צעד, ומשדרג את
המהלך בזמן-אמת (הזרקה) ורטרואקטיבית (canon ב-merge).
