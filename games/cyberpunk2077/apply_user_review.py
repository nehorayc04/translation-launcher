# -*- coding: utf-8 -*-
"""apply_user_review.py — apply the user's 54 reviewed fixes (2026-06-12).

Modes per pk: "full" = replace the whole value; "sub" = surgical (old,new)
replacements on the full value. Applied to BOTH onscreens.json and
onscreens_final.json mirrors. Backup + atomic write + residual check.
"""
import os, sys, json, time, shutil, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "universal"))
import get_next_audit_batch as G
import cp2077_qa_defects as Q

FULL = {
    "68":  "בריאות זה הסטייל החדש!",
    "1429": "ניתן לגרום נזק לא-קטלני לדמויות בטווח",
    "1432": "ניתן לגרום נזק קטלני לדמויות בטווח",
    "3863": "מסכת מנפו 'אקאי אוני' מסריג-בוסט מטיטניום",
    "3947": "הכובע המומלץ לסובלים מהפרעת דלדול קשב",
    "3979": "ארה\"ב מתה. יחי ארה\"ב.",
    "4054": "צי ספינות קלות-משקל עם ריפוד מרוכב",
    "4056": "ציים בוציים",
    "4063": "ציים מפלסטיק מחוזק",
    "4404": "גופיית ננו-אריג מרופטת עם חיתוכים",
    "4406": "גופיית פוליאמיד מחוזק מדגם X",
    "4706": "אפוד מגן מארמיד משולב פוליקרבונט מבית אראסאקה",
    "6485": "פגיעה בול",
    "6510": "קוברה",
    "6517": "עקבות דם",
    "6588": "קליסטניקה",
    "22585": "סייבורג מומחה חבלה",
    "27267": "דואליסטים קרטזיאניים (ויניל)",
    "27427": "גופיית הסוואה טקטי-פייבר קרועה",          # maleVariant too
    "27612": "אמנדה רובינשטיין",
    "34403": "אמנדה רובינשטיין",
    "27965": "גליץ' בנשק",
    "33346": "הנרי קאלהן",
    "33347": "לוטננט \"קרייזי\" הנרי קאלהן",
    "37756": "לוטננט הנרי קאלהן",
    "36051": "אני אכה את השטן מתוכך! הקשיבו לברייס סטון מכריז כל יום ראשון, רק ב-N54",
    "36243": "סוויטות ומכונות המזל של בטי החטובה *** המכונות שלנו מתפוצצות בתפרים",
    "36960": "פאנם ומיץ'",
    "37372": "מרוץ הבאדלנדס",
    "40626": "ימטר על רשעים פחים; אש וגפרית ורוח זלעפות מנת כוסם.",
    "41389": "עוזר בקרה",
    "41475": "דיבוב באנגלית",
    "41515": "סול ברייט",
    "41695": "NVIDIA",
    "42242": "CHIROMATIX",
    "43725": "נוהג בהפקרות מוחלטת",
    "44437": "המעבר העילי בלוויו",
    "44516": "ונטורה & סקייליין",
    "19612": "סוג משימה: SOS: דרוש שכיר חרב\\nמטרה: חילוץ אייריס טאנר\\nמיקום: אדג'ווד ליין.\\nפרטים:",
}

SUB = {
    "17863": [("טוב? <br>", "נו? <br>"),
              ("בNoice סיטי", "בנייט סיטי"),
              ("פדרי אומר שהוא.", "פדרה אומר שכן.")],
    "19663": [("לnieder ולנוע בשקט", "להתכופף ולנוע בשקט")],
    "20151": [("בNoice City", "בנייט סיטי")],
    "21363": [("ריב פרץ בתוטנstanz", "קטטה פרצה בטוטנטאנז"),
              ("בבעלות הכנופיה Maelstrom", "בבעלות כנופיית המאלסטרום")],
    "21366": [("שהWraiths", "שהרייתס")],
    "21378": [("כbagian", "כחלק")],
    "27243": [("וamber", "וענבר")],
    "27404": [("משולש ברmudah", "משולש ברמודה")],
    "28443": [("גrouchiness", "עצבנות")],
    "28885": [("דetective J. McNulty", "הבלש ג'יי. מקנאלטי")],
    "36032": [("בNight City", "בנייט סיטי")],
    "40198": [("בNight City", "בנייט סיטי")],
    "42776": [("אתה יכול לבחור Quickhacks ו-Breach Protocol עם",
               "ניתן לבחור פריצות מהירות ואת פרוטוקול הפריצה באמצעות"),
              ("וpeut", "ואפשר")],
    "42778": [("לnieder ולחבוא", "להתכופף ולהסתתר")],
}

SECS = ("onscreens/onscreens.json", "onscreens/onscreens_final.json")


def main():
    data = json.load(open(G.BASE_TR, encoding="utf-8"))
    if not Q.acquire_lock("apply_user_review"):
        sys.exit("[abort] QA lock held")
    try:
        applied = subbed = 0
        for sec in SECS:
            for e in data.get(sec, []):
                if not isinstance(e, dict):
                    continue
                pk = str(e.get("primaryKey"))
                if pk in FULL:
                    for fld in ("femaleVariant", "maleVariant"):
                        v = e.get(fld)
                        if v:                      # mirror both gender slots
                            e[fld] = FULL[pk]
                            applied += 1
                if pk in SUB:
                    for fld in ("femaleVariant", "maleVariant"):
                        v = e.get(fld)
                        if not v:
                            continue
                        nv = v
                        for old, new in SUB[pk]:
                            nv = nv.replace(old, new)
                        if nv != v:
                            e[fld] = nv
                            subbed += 1
        bak = f"{G.BASE_TR}.bak.userreview.{time.strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(G.BASE_TR, bak)
        tmp = G.BASE_TR + ".tmp"
        json.dump(data, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
        os.replace(tmp, G.BASE_TR)
        print(f"full-replaced fields: {applied} | surgical fields: {subbed} | backup {os.path.basename(bak)}")
    finally:
        Q.release_lock()

    # residual check: none of the flagged tokens should remain at these pks
    data = json.load(open(G.BASE_TR, encoding="utf-8"))
    dec = json.load(open(r"c:/Users/Nehoray_Cohen/Downloads/review_decisions.json", encoding="utf-8"))
    bad = []
    for sec in SECS:
        for e in data.get(sec, []):
            if not isinstance(e, dict):
                continue
            pk = str(e.get("primaryKey"))
            for d in dec:
                if d["pk"] == pk and pk != "21153":      # 21153 deferred
                    for fld in ("femaleVariant", "maleVariant"):
                        if d["word"] in (e.get(fld) or ""):
                            bad.append((pk, fld, d["word"]))
    print("residual flagged tokens:", bad if bad else "NONE — all clean")


if __name__ == "__main__":
    main()
