"""Parameterized parallel-agent prep for the WD2 Hebrew QA pass.

  python prep_agents.py N

Splits whatever WORK REMAINS (lines not yet reviewed in any prior round) into N
balanced, DISJOINT folders agent_1..agent_N — each a fully isolated workspace
(own corpus + scripts + state) so N fresh agents run in parallel with ZERO
collision. Re-run any time with a DIFFERENT N (the # of agents not currently hit
by the 5-hour limit changes) — prior progress is harvested first, so the next
round only covers what is left.

Round flow:
  1. harvest every agent_*/qa_reviewed.json + corrections.json into the persistent
     progress_reviewed.json / progress_corrections.json, then delete the old folders.
  2. remaining = corpus ids NOT in progress_reviewed.
  3. balanced split of `remaining` into agent_1..agent_N.
When all rounds are done -> Claude runs apply_corrections.py (merges progress +
every agent folder) -> rebuild -> deploy.
"""
import json, os, re, shutil, sys, glob, stat, time
HERE = os.path.dirname(os.path.abspath(__file__))

def _force_rmtree(d):
    """Resilient delete: clear read-only + retry through transient AV/indexer locks."""
    def onexc(func, path, exc):
        try: os.chmod(path, stat.S_IWRITE)
        except Exception: pass
        try: func(path)
        except Exception: pass
    for attempt in range(6):
        try:
            shutil.rmtree(d, onexc=onexc); return
        except Exception:
            time.sleep(0.5)
    # last resort: rename out of the way so the split can proceed
    try: os.rename(d, d + f".stale{int(time.time())}")
    except Exception: shutil.rmtree(d, ignore_errors=True)
CORPUS = os.path.join(HERE, "corpus.json")
P_REVIEWED = os.path.join(HERE, "progress_reviewed.json")
P_CORR     = os.path.join(HERE, "progress_corrections.json")
SEV = ["ENGLISH_LEAK","UNTRANSLATED","TOKEN_MISMATCH","BRACKET","OVERFLOW",
       "FOREIGN","NIQQUD","PLACENAME","ICON_TOKEN"]
def rank(flags):
    for i, s in enumerate(SEV):
        if s in flags: return i
    return len(SEV) + (0 if flags else 1)
def jload(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d

GLOSSARY_MD = """\
| EN | עברית | EN | עברית |
|---|---|---|---|
| San Francisco | סן פרנסיסקו | Embarcadero | אמברקדרו |
| Bay Area | אזור מפרץ סן פרנסיסקו (צר→אזור המפרץ) | Los Angeles | לוס אנג'לס |
| Oakland | אוקלנד | Tenderloin | טנדרלוין |
| Silicon Valley | עמק הסיליקון | Frisco | פריסקו |
| Alcatraz | אלקטרז | Twin Peaks | טווין פיקס |
| Marin / Marin County | מרין / מחוז מרין | Fisherman's Wharf | רציף הדייגים |
| Golden Gate / …Bridge | שער הזהב / גשר שער הזהב | Berkeley | ברקלי |
| Coit Tower | מגדל קויט | Fremont | פרימונט |
| Castro | הקסטרו (בלי ה'=קסטרו) | Menlo Park | מנלו פארק |
| Chinatown | צ'יינטאון | Mission District | מישן דיסטריקט |
| Lombard / Lombard Street | רחוב לומברד (טוקן=לומברד) | Peninsula | חצי האי |
| Haight / Haight-Ashbury | הייט / הייט-אשבורי | Treasure Island | טרז'ר איילנד |
| New York | ניו יורק | Nob Hill | נוב היל |
| East Bay | איסט ביי | Pacific Heights | פסיפיק הייטס |
| Palo Alto | פאלו אלטו | Point Bonita | פוינט בוניטה |
| San Mateo | סן מטאו | Sausalito | סאוסליטו |
| Golden Gate Bridge | גשר שער הזהב | Bakersfield | בייקרספילד |"""

def instructions(num, total, folder):
    others = ", ".join(f"agent_{k}" for k in range(1, total + 1) if k != num) or "(אין)"
    return f"""# סוכן {num} מתוך {total} — QA + תיקון תרגום עברית ל-Watch Dogs 2

אתה **סוכן {num}** מתוך {total} שרצים **במקביל**. הסוכנים האחרים: {others}.

## ⚠️ בידוד מוחלט — רק התיקייה שלך
- תיקיית העבודה היחידה שלך:
  `C:\\Users\\Nehoray_Cohen\\Projects\\Game translator\\games\\watchdogs2\\agent_handoff_qa\\{folder}\\`
- **אסור** לגעת בתיקיות הסוכנים האחרים או בכל קובץ אחר. אין קבצים משותפים → אין התנגשות.
- עשה `cd` לתיקייה שלך והרץ **רק** את `qa_get_batch.py` ו-`qa_merge.py` שבה.

## ⚠️ אתה המתרגם — לא מודל חיצוני, ולא סקריפט-מילון
**אתה** קורא, שופט ומתקן בעצמך **כל שורה לגופה**. **אסור** LM Studio / localhost / gemma / כל AI חיצוני.
**אסור לחלוטין לכתוב סקריפט .py / לולאת אוטומציה / מילון החלפות (find&replace / reps / מילוי `{{}}`).**
זה הרס סבבים קודמים — והכלי בנוי כך ש**זה גם פשוט לא יעבוד**: שורה נספרת כ"נבדקה" **רק** אם
רשמת לה ערך ב-qa_fixes.json (תיקון או `"OK"`). קובץ ריק `{{}}` או חלקי **לא מקדם כלום** —
אותו באטץ' יחזור שוב ושוב ולעולם לא תגיע ל-`QA done!`. הדרך היחידה קדימה = לקרוא כל שורה
ולרשום לה ערך. כל באטץ' = **רק 40 שורות**, קטן בכוונה. רק qa_get_batch.py / qa_merge.py מותר להריץ.

## ⚠️ סדר לוגי — אל תהפוך כלום
התרגומים בסדר קריאה רגיל (לוגי). תקן בעברית רגילה. **אל תהפוך אותיות/מילים/שורות** —
סקריפט בנייה נפרד מטפל ב-RTL.

## הלולאה — חזור עד "QA done!" (אל תעצור אחרי באטץ' אחד!)
  א. `python qa_get_batch.py` → `QA done!` → סיים. אחרת נוצר `qa_batch.json` = `[{{pk,en,he,flags}}]` (40 שורות).
  ב. עבור על **כל אחת מ-40 השורות**: השווה `he` ל-`en`.
  ג. כתוב `qa_fixes.json` עם ערך ל**כל** pk בבאטץ' (חובה 40 ערכים):
     שורה שגויה → `"העברית המתוקנת"`. שורה תקינה → `"OK"`.
     דוגמה: `{{"123": "טקסט מתוקן", "124": "OK", "125": "OK", ...}}`.
     (שורה בלי ערך לא נספרת ותחזור שוב — לכן חובה ערך לכל אחת.)
  ד. `python qa_merge.py` → רושם רק את ה-pk-ים שאישרת. `REJECT pk` → תקן רק אותו והרץ שוב.
     `WARN ... NOT attested` → הוסף `"OK"`/תיקון לאלה שחסרים והרץ שוב.
  ה. **מחק `qa_fixes.json`** וחזור ל-א'. עד "QA done!".

## ⏯️ נקטעת (מגבלת 5 שעות)? פשוט תמשיך
התחל בלי זיכרון? רק `cd` לתיקייה שלך והרץ שוב `python qa_get_batch.py`. ההתקדמות שמורה
ב-qa_reviewed.json — אתה ממשיך בדיוק מאיפה שעצרת. **לעולם אל תתחיל מאפס.**

## מה לתקן
1. **מילה עברית משובשת/מומצאת (הכי חשוב):** `נשian`→נמלט, `שמאב`→שמאי, `מטומבגים`→מטומטמים,
   `מה הזאמור`→מה לעזאזל, `כבר נשואים`(for ages)→כבר המון זמן. מילה שאינה עברית תקנית — תקן.
2. **תרגום-שגיאה:** משמעות/זמן/נושא. `high points`→נקודות גבוהות (לא "גובה").
3. **דליפת אנגלית:** מילה אנגלית קטנה בעברית → תרגם (`poeta של slam`→משורר סלאם).
4. **לא מתורגם:** שורה כולה אנגלית → תרגם. אבל שם/מותג/קוד נשאר לטיני.
5. **שמות מקומות:** בדיוק לפי הטבלה למטה (+`glossary.json`), עקבי בכל המשחק.
6. **`OVERFLOW`:** נחתך על המסך → קצר את העברית למשמעות זהה באורך דומה לאנגלית.

## אל תשנה
עברית טבעית נכונה. שמות/מותגים: Marcus, Wrench, Sitara, DedSec, ctOS, Blume, Nudle, Bratva,
Hackerspace, וכל ראשי-התיבות (FBI, NSA, SWAT, GPS, AI, XP). רמזי-קול (laughs)/[laughs] — as-is.

## שמירת טוקנים (qa_merge מאמת)
שמור בדיוק את אותם `[TOKEN]` / `{{VALUE}}` / `%d %s %%` / `&#xA;` / `\\n` שיש **באנגלית**.
**אסור ניקוד. רק עברית+לטינית.**

## גלוסר שמות מקומות (אומת מול ויקיפדיה עברית — חובה):
{GLOSSARY_MD}

## סיום
כש-`qa_get_batch.py` = `QA done!` כתוב: `--- QA SUMMARY (סוכן {num}) --- נבדק: X · תוקן: Y --- END ---`
"""

ACTIONABLE = {"ENGLISH_LEAK", "UNTRANSLATED", "TOKEN_MISMATCH", "BRACKET",
              "OVERFLOW", "PLACENAME", "FOREIGN", "NIQQUD"}  # NOT MISORIENTED (build-handled) / ICON_TOKEN (tofu)

def main():
    if len(sys.argv) < 2 or not sys.argv[1].isdigit():
        print("usage: python prep_agents.py N [--flagged]   (N = parallel agents)"); return
    N = int(sys.argv[1])
    flagged_only = "--flagged" in sys.argv
    corpus = jload(CORPUS, {})
    # 1. harvest prior rounds
    reviewed = set(jload(P_REVIEWED, []))
    corr = jload(P_CORR, {})
    corr.update(jload(os.path.join(HERE, "corrections.json"), {}))   # earlier single-dir 8
    agent_dirs = [d for d in glob.glob(os.path.join(HERE, "agent_*"))
                  if os.path.isdir(d) and re.fullmatch(r"agent_\d+", os.path.basename(d))]
    for d in agent_dirs:
        reviewed |= set(jload(os.path.join(d, "qa_reviewed.json"), []))
        corr.update(jload(os.path.join(d, "corrections.json"), {}))
    reviewed |= set(corr.keys())
    json.dump(sorted(reviewed, key=int), open(P_REVIEWED, "w"), ensure_ascii=False)
    json.dump(corr, open(P_CORR, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    for d in agent_dirs:
        _force_rmtree(d)
    # 2. remaining (optionally only deterministically-flagged, agent-actionable lines)
    remaining = [(pk, v) for pk, v in corpus.items() if pk not in reviewed]
    if flagged_only:
        remaining = [(pk, v) for pk, v in remaining if ACTIONABLE & set(v["flags"])]
    remaining.sort(key=lambda kv: (rank(kv[1]["flags"]), len(kv[1]["en"])))
    # 3. balanced split into N
    parts = [dict() for _ in range(N)]
    for i, (pk, v) in enumerate(remaining):
        parts[i % N][pk] = v
    scope = "FLAGGED-only" if flagged_only else "FULL"
    print(f"corpus {len(corpus)} | already done {len(reviewed)} | REMAINING ({scope}) {len(remaining)} -> {N} agents")
    for k in range(N):
        num = k + 1; folder = f"agent_{num}"; d = os.path.join(HERE, folder)
        os.makedirs(d, exist_ok=True)
        json.dump(parts[k], open(os.path.join(d, "corpus.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        for f in ("qa_get_batch.py", "qa_merge.py", "glossary.json"):
            shutil.copy2(os.path.join(HERE, f), os.path.join(d, f))
        json.dump([], open(os.path.join(d, "qa_reviewed.json"), "w"))
        open(os.path.join(d, "INSTRUCTIONS.md"), "w", encoding="utf-8").write(instructions(num, N, folder))
        fl = sum(1 for x in parts[k].values() if x["flags"])
        print(f"  {folder}: {len(parts[k])} lines ({fl} flagged)")

if __name__ == "__main__":
    main()
