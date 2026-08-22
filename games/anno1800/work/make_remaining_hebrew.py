#!/usr/bin/env python3
"""make_remaining_hebrew.py — translate the genuine remaining lines that were outside the
original corpus (New World/Isabel + Enbesa campaign narrative, controller hints, a few UI).
User-authorized one-time direct translation (override of the delegate rule) for a bounded set.
Markup kept LITERAL (<b>..</b>, <br/>); the builder escapes + carrier-izes. Writes
remaining_hebrew.json which build_arabic_disguise merges into hebrew.json."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))

# GUIDs deliberately NOT translated (dev/test/dummy/duplicated placeholder) or moved to exclusion
SKIP = {"706","700032","4630","804037","11939","11940","11941","11942","11943","11944","11945","11946"}
SHIP_TO_EXCLUDE = {"111932"}   # 'Ship-of-the-Line' = ship name -> keep English

HEB = {
 # --- controller / gamepad hints (button labels stay Latin) ---
 "24905": "הטה את המצלמה עם <b>RB + המקל הימני</b>",
 "24906": "אפס את זווית המצלמה עם <b>RSB (לחיצה על המקל הימני)</b>",
 "24908": "פתח את תפריט הבנייה עם <b>RT</b>",
 "24909": "פתח את הכלים עם <b>LT</b> — תמצא שם כלים להזיז או להרוס, למשל, בניין",
 "24911": "בעת בניית כביש: <br />לחץ <b>A</b> פעם אחת כדי להתחיל כביש, ושוב כדי לסיים אותו",
 "24912": "בעת בניית מגורים: <br />לחץ <b>A</b> פעם אחת כדי לבנות מגורים בודדים",
 "24917": "לחץ <b>Y</b> כדי לגשת לכל תפריטי הניהול",
 "24918": "תן לספינה פקודת הפלגה עם <b>X</b>",
 "10000004": "לחץ <b>LSB (לחיצה על המקל השמאלי)</b> כדי לקפוץ אל הספינה הנבחרת",
 "10000005": "כשבניין נבחר, לחץ <b>Directional Pad Right</b> כדי לפעול מול הפאנל שלו",
 "10000007": "כשספינה נבחרת, לחץ <b>Directional Pad Right</b> כדי לפעול מול הפאנל שלה",
 "10000009": "הכלים שעל <b>LT</b> מכילים גם פקודות מהירות שימושיות לבניין או לספינה שמתחת לסמן",
 "10000010": "לחץ <b>Direction Pad Up</b> כדי לפתוח את מפת האזור — שם תוכל לשנע במהירות למקומות רחוקים",
 "10000011": "זכור שאתה יכול לקפוץ בין עמדות המסחר שלך עם <b>LSB (לחיצה על המקל השמאלי)</b> <br />(בטל קודם בחירת בניין או ספינה)",
 "10000013": "לחץ <b>Directional Pad Down</b> כדי לפתוח את תפריט הספינות",
 "10000014": "לחץ <b>LB + A</b> כדי לבחור כמה ספינות",
 "10000016": "לחץ <b>LB + A</b> כדי לבחור כמה ספינות",
 "10000017": "<b>הקשה כפולה על A</b> מעל ספינה כדי לבחור את כל הספינות מהסוג הזה שעל המסך",
 "10000018": "לחץ <b>LB + הקשה כפולה על A</b> בכל מקום כדי לבחור את כל הספינות שעל המסך",
 "600901": "למעלה: פתח מפת ניווט מהיר",
 "600903": "L1: הצג את המפגש הקודם",
 "600904": "למעלה: סגור את מפת הניווט המהיר",
 "600914": "R1: קפוץ לבניין הבא",
 "600915": "L1: קפוץ לבניין הקודם",

 # --- misc UI ---
 "929": "שדות חייבים להיות משויכים לבניין ראשי, המגדיר את הכמות המרבית",
 "930": "בחר בניין חווה",
 "24030": "כל מבני התעשייה הכבדה",
 "11964": "שגיאה: אינך הבעלים של הפריט שהוצע",
 "11965": "שגיאה: הפריט שאתה רוצה להציע כבר מוצע למכירה",
 "11966": "הפריט הוצע בהצלחה",
 "11967": "שגיאה: שגיאת מסד-נתונים פנימית",
 "25447": "בלשונית \"קבוצות\", אתה יכול ליצור קבוצות עם <b>X</b> כדי לבחור אותן במהירות",
 "126841": "שינוי במים",
 "126845": "צלילה של מוסיקה",
 "131676": "מסעך למיפוי גבולות אנבסה עבור סר ארצ'יבלד מקבל תפנית בלתי צפויה",
 "131677": "מסעך למיפוי גבולות אנבסה עבור סר ארצ'יבלד לוקח פנייה נוספת",
 "131678": "מסעך למיפוי גבולות אנבסה עבור סר ארצ'יבלד מגיע לעצירה פתאומית",
 "131679": "מסעך למיפוי גבולות אנבסה חשף מבנה-סלע מקומר ומקסים",
 "131710": "בנה ספינות-אוויר משלך והיה הראשון שממריא מעל מתחריך!",
 "135154": "מכירות מושבי טרקלין משוערות",
 "135161": "מכירות מושבי טרקלין משוערות",
 "135162": "מכירות מושבי טרקלין משוערות",
}


def main():
    src = json.load(open(os.path.join(HERE, "remaining_to_translate.json"), encoding="utf-8"))
    out = {}
    missing = []
    for g in src:
        if g in SKIP or g in SHIP_TO_EXCLUDE:
            continue
        if g in HEB:
            out[g] = HEB[g]
        else:
            missing.append(g)   # quest paragraphs handled separately (below), or flagged
    # merge the quest-paragraph translations from the companion file if present
    qp = os.path.join(HERE, "remaining_hebrew_quests.json")
    if os.path.exists(qp):
        for g, v in json.load(open(qp, encoding="utf-8")).items():
            if g not in SKIP:
                out[g] = v
                if g in missing:
                    missing.remove(g)
    json.dump(out, open(os.path.join(HERE, "remaining_hebrew.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"remaining_hebrew.json: {len(out)} translated")
    if missing:
        print(f"  still untranslated (quest paragraphs -> need remaining_hebrew_quests.json): {len(missing)}")
        print("   " + " ".join(sorted(missing, key=int)))
    # also add the ship name to the exclusion set
    ex = os.path.join(HERE, "editable_names_exclude.json")
    cur = set(json.load(open(ex)))
    if not SHIP_TO_EXCLUDE <= cur:
        cur |= SHIP_TO_EXCLUDE
        json.dump(sorted(cur), open(ex, "w"))
        print(f"  added {SHIP_TO_EXCLUDE} to exclusion (ship name -> English)")


if __name__ == "__main__":
    main()
