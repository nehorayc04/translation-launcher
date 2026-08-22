# -*- coding: utf-8 -*-
"""
dualgender_inflect.py — DETERMINISTIC Hebrew feminine→masculine inflector for the
CP2077 dual-gender residual (the lines the Google agents couldn't do without cheating).

It is NOT a translator: the correct Hebrew already exists (he_female). This converts
that female form to the male V form by changing ONLY gendered morphemes — a curated
feminine→masculine word map (suffixal changes only) + a context-aware את→אתה
(applied ONLY when the next word is a feminine 2nd-person verb, so the accusative
marker "את הX" is never touched).

Every output is re-validated by the SAME anti-cheat as the agents
(dualgender_verify_agents.classify_fill): scaffold preserved + a real suffixal gender
change + no niqqud/foreign/internal-edit. A line where nothing maps (or the result
fails validation) is left M=F (stored "__SKIP__") — safe, never corrupts.

CLI: python dualgender_inflect.py            # dry-run report
     python dualgender_inflect.py --write     # fill each agent's fixed_male.json
"""
from __future__ import annotations
import argparse, json, os, re, sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from dualgender_verify_agents import classify_fill

ROOT = os.path.dirname(HERE)
BASEDIR = os.path.join(ROOT, "games", "cyberpunk2077", "agent_handoff_dualgender")
PREF = set("הושכלבמ")   # Hebrew one-letter prefixes
HEBRUN = re.compile("[א-ת]+")

# feminine -> masculine, SUFFIXAL changes only (drop ת/ה/י or add ה). Homographs that
# are also common non-gendered words (אחת, ישנה, קמה, גרה, שנה…) are deliberately OMITTED.
FEM2MASC = {
    # present participles (fem ־ת / ־ה  →  masc)
    "יודעת": "יודע", "הולכת": "הולך", "חושבת": "חושב", "מבינה": "מבין",
    "יושבת": "יושב", "עומדת": "עומד", "אוכלת": "אוכל", "נותנת": "נותן",
    "לוקחת": "לוקח", "אומרת": "אומר", "שומעת": "שומע", "מרגישה": "מרגיש",
    "מדברת": "מדבר", "מחפשת": "מחפש", "מכירה": "מכיר", "זוכרת": "זוכר",
    "שוכחת": "שוכח", "מאמינה": "מאמין", "מבקשת": "מבקש", "חוזרת": "חוזר",
    "נשארת": "נשאר", "עוזרת": "עוזר", "עובדת": "עובד", "מוכרת": "מוכר",
    "נראית": "נראה", "נשמעת": "נשמע", "מתכוונת": "מתכוון", "מנהלת": "מנהל",
    "שולטת": "שולט", "מספרת": "מספר", "כותבת": "כותב", "קוראת": "קורא",
    "לומדת": "לומד", "מלמדת": "מלמד", "שולחת": "שולח", "מקבלת": "מקבל",
    "מחזירה": "מחזיר", "מוצאת": "מוצא", "מאבדת": "מאבד", "בוחרת": "בוחר",
    "מחליטה": "מחליט", "מסכימה": "מסכים", "מתנגדת": "מתנגד", "מפחדת": "מפחד",
    "דואגת": "דואג", "כועסת": "כועס", "צוחקת": "צוחק", "מחייכת": "מחייך",
    "נופלת": "נופל", "מתעוררת": "מתעורר", "אוהבת": "אוהב", "שונאת": "שונא",
    "מצטערת": "מצטער", "מתגעגעת": "מתגעגע", "מקנאה": "מקנא", "נלחמת": "נלחם",
    "עושה": "עושה", "רואה": "רואה",  # ktiv-invariant (no-op guard)
    "מודעת": "מודע", "בודקת": "בודק", "מנסה": "מנסה", "מגלה": "מגלה",
    "מתנהגת": "מתנהג", "שואלת": "שואל", "עונה": "עונה", "מתעייפת": "מתעייף",
    "מחזיקה": "מחזיק", "מרגישה": "מרגיש", "רוצה": "רוצה", "יכולה": "יכול",
    "מנסה": "מנסה", "מציעה": "מציע", "מזהה": "מזהה", "בונה": "בונה",
    "שולפת": "שולף", "יורה": "יורה", "רצה": "רץ", "בורחת": "בורח",
    "מתקרבת": "מתקרב", "מתרחקת": "מתרחק", "נכנסת": "נכנס", "יוצאת": "יוצא",
    "עולה": "עולה", "יורדת": "יורד", "עוברת": "עובר", "חוצה": "חוצה",
    "מובילה": "מוביל", "מחכה": "מחכה", "מודדת": "מודד", "בולעת": "בולע",
    # modal / necessity
    "צריכה": "צריך", "חייבת": "חייב", "אמורה": "אמור", "מוכרחה": "מוכרח",
    "זקוקה": "זקוק", "מסוגלת": "מסוגל", "רגילה": "רגיל", "מודאגת": "מודאג",
    "נשבעת": "נשבע", "מניחה": "מניח", "מתכוננת": "מתכונן",
    # adjectives
    "מוכנה": "מוכן", "בטוחה": "בטוח", "גדולה": "גדול", "קטנה": "קטן",
    "חדשה": "חדש", "חזקה": "חזק", "חלשה": "חלש", "מהירה": "מהיר",
    "חכמה": "חכם", "עייפה": "עייף", "שמחה": "שמח", "עצובה": "עצוב",
    "צודקת": "צודק", "אחראית": "אחראי", "מוכשרת": "מוכשר", "חשובה": "חשוב",
    "מסוכנת": "מסוכן", "בריאה": "בריא", "חופשייה": "חופשי", "עשירה": "עשיר",
    "צעירה": "צעיר", "יחידה": "יחיד", "ראשונה": "ראשון", "אחרונה": "אחרון",
    "מלאה": "מלא", "ריקה": "ריק", "בודדה": "בודד", "לבדה": "לבד",
    "בטוחה": "בטוח", "מודעת": "מודע", "מוכנה": "מוכן", "מפוחדת": "מפוחד",
    "מבולבלת": "מבולבל", "מתוחה": "מתוח", "רגועה": "רגוע", "עסוקה": "עסוק",
    "נאמנה": "נאמן", "גאה": "גאה", "אמיצה": "אמיץ", "פוחדת": "פוחד",
    "טובה": "טוב", "עדיפה": "עדיף", "מיוחדת": "מיוחד", "נוספת": "נוסף",
    "יפה": "יפה", "מתה": "מת", "אחראית": "אחראי", "נבונה": "נבון",
    "אוטומטית": "אוטומטי", "פנימית": "פנימי", "חיצונית": "חיצוני",
    "אמיתית": "אמיתי", "אישית": "אישי", "מקומית": "מקומי", "רשמית": "רשמי",
    "כללית": "כללי", "ידידותית": "ידידותי", "רגישה": "רגיש", "קשה": "קשה",
    # more common present-tense verbs
    "מפעילה": "מפעיל", "משתמשת": "משתמש", "עוזבת": "עוזב", "מדליקה": "מדליק",
    "מחזירה": "מחזיר", "משלמת": "משלם", "קונה": "קונה", "מוכרת": "מוכר",
    "נכנסת": "נכנס", "בורחת": "בורח", "נזהרת": "נזהר", "מוותרת": "מוותר",
    "מסתכלת": "מסתכל", "מתקשרת": "מתקשר", "מדווחת": "מדווח", "בוטחת": "בוטח",
    # imperatives (fem ־י → masc)
    "קחי": "קח", "תני": "תן", "שבי": "שב", "בואי": "בוא", "לכי": "לך",
    "עשי": "עשה", "קומי": "קום", "שמרי": "שמור", "זכרי": "זכור",
    "שכחי": "שכח", "עזרי": "עזור", "ספרי": "ספר", "כתבי": "כתוב",
    "קראי": "קרא", "שמעי": "שמע", "ראי": "ראה", "דברי": "דבר",
    "חכי": "חכה", "בדקי": "בדוק", "נסי": "נסה", "בחרי": "בחר",
    "פתחי": "פתח", "סגרי": "סגור", "תפסי": "תפוס", "הקשיבי": "הקשב",
    "הביטי": "הבט", "עצרי": "עצור", "רוצי": "רוץ", "מהרי": "מהר",
    "הישארי": "הישאר", "צאי": "צא", "היכנסי": "היכנס", "גשי": "גש",
    "תפני": "תפנה",
    # future 2nd person (fem prefix ת + ־י → masc)
    "תעשי": "תעשה", "תראי": "תראה", "תלכי": "תלך", "תדעי": "תדע",
    "תבואי": "תבוא", "תשמעי": "תשמע", "תזכרי": "תזכור", "תשכחי": "תשכח",
    "תיזהרי": "תיזהר", "תסתכלי": "תסתכל", "תגידי": "תגיד", "תמצאי": "תמצא",
    "תבחרי": "תבחר", "תחליטי": "תחליט", "תוכלי": "תוכל", "תרצי": "תרצה",
    "תצטרכי": "תצטרך", "תבדקי": "תבדוק", "תנסי": "תנסה", "תדאגי": "תדאג",
    "תחשבי": "תחשוב", "תביני": "תבין", "תשלחי": "תשלח", "תקבלי": "תקבל",
    "תחזרי": "תחזור", "תעברי": "תעבור", "תספרי": "תספר", "תכתבי": "תכתוב",
    "תקראי": "תקרא", "תפתחי": "תפתח", "תסגרי": "תסגור", "תתני": "תתן",
    "תיקחי": "תיקח", "תשבי": "תשב", "תקומי": "תקום", "תגלי": "תגלה",
    "תעזרי": "תעזור", "תעני": "תענה", "תשאלי": "תשאל", "תדברי": "תדבר",
    "תקשיבי": "תקשיב", "תזוזי": "תזוז", "תפחדי": "תפחד", "תצליחי": "תצליח",
    "תרגישי": "תרגיש", "תחשדי": "תחשוד", "תמשיכי": "תמשיך", "תפסיקי": "תפסיק",
    "תעצרי": "תעצור", "תרוצי": "תרוצי", "תיזהרי": "תיזהר", "תשתמשי": "תשתמש",
}


def _is_fem2p(stem: str) -> bool:
    """Is this stem a feminine 2nd-person verb (so a preceding את = you-fem)?"""
    if stem in FEM2MASC:
        return True
    return stem.startswith("ת") and stem.endswith("י") and len(stem) >= 3


def _map_word(word: str, nxt: str | None) -> str:
    """Inflect one Hebrew word (with up to 2 leading prefix letters). Returns the
    word unchanged if nothing applies."""
    for pl in (0, 1, 2):
        if pl and (len(word) <= pl or word[pl - 1] not in PREF):
            break
        stem = word[pl:]
        if stem in FEM2MASC:
            return word[:pl] + FEM2MASC[stem]
        if stem == "את" and nxt is not None and _is_fem2p(nxt):
            return word[:pl] + "אתה"
    return word


def inflect(he_female: str) -> str:
    """Return the masculine V form of he_female (scaffold preserved)."""
    runs = [(m.start(), m.end(), m.group(0)) for m in HEBRUN.finditer(he_female)]
    if not runs:
        return he_female
    stems = [w.lstrip("".join(PREF)) for _, _, w in runs]  # for look-ahead
    out = []
    prev_end = 0
    for i, (s, e, word) in enumerate(runs):
        out.append(he_female[prev_end:s])          # non-Hebrew before (scaffold)
        nxt = stems[i + 1] if i + 1 < len(runs) else None
        out.append(_map_word(word, nxt))
        prev_end = e
    out.append(he_female[prev_end:])
    return "".join(out)


def run(write: bool) -> int:
    total = inflected = neutral = failed = already = 0
    for name in ("agent_1", "agent_2", "agent_3"):
        d = os.path.join(BASEDIR, name)
        tf = json.load(open(os.path.join(d, "to_fix.json"), encoding="utf-8"))
        fp = os.path.join(d, "fixed_male.json")
        done = json.load(open(fp, encoding="utf-8")) if os.path.exists(fp) else {}
        a_inf = a_neu = a_fail = 0
        for k, src in tf.items():
            if k in done:
                already += 1
                continue
            total += 1
            fem = src.get("he_female", "")
            cand = inflect(fem)
            if cand != fem:
                val, why = classify_fill(cand, fem, "")
                if not why:
                    done[k] = val
                    inflected += 1; a_inf += 1
                    continue
                a_fail += 1; failed += 1
            # no change or failed validation -> M = F (safe, gender-neutral)
            done[k] = "__SKIP__"
            neutral += 1; a_neu += 1
        if write:
            json.dump(done, open(fp, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"  {name}: inflected {a_inf}  M=F {a_neu}  (map-failed {a_fail})")
    print("=" * 50)
    print(f"residual processed: {total}")
    print(f"  DETERMINISTIC inflections: {inflected}")
    print(f"  left M=F (neutral/unmapped): {neutral}")
    print(f"  (already done by agents, kept: {already})")
    print("WROTE fixed_male.json" if write else "(dry-run — pass --write to apply)")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="dualgender_inflect")
    p.add_argument("--write", action="store_true")
    a = p.parse_args(argv)
    return run(a.write)


if __name__ == "__main__":
    raise SystemExit(main())
