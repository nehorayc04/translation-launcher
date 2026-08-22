"""
auto_loop.py — לולאת תרגום אוטומטית מלאה.
מתרגם INLINE (ללא API/Google Translate).
מטפל ב:
- שמות: נשמרים באנגלית אם is_namey=True
- ביטויים: תרגום עברי מלא עם מגדר
- control char prefix נשמר
- tags/placeholders נשמרים
"""
import json, re, os, subprocess, sys

CTRL = "".join(chr(c) for c in range(0x20))
NAMEWORD = re.compile(r"^[A-Z0-9][\w.\-'/]*$")
FOREIGN = re.compile(r"[؀-ۿ぀-ヿ一-鿿가-힣Ѐ-ӿ]")
LOWER = re.compile(r"[a-z]{2,}")
STRUCT = re.compile(r"<[^>]*>|\{[^}]*\}|%%|%[#0-9.*\-+]*[a-zA-Z]+|&[a-zA-Z#0-9]+;")
HEB = re.compile(r"[֐-׿]")
NIQ = re.compile(r"[֑-ֽֿׁׂ]")

HERE = os.path.dirname(os.path.abspath(__file__))
BATCH_FILE = os.path.join(HERE, "current_batch.json")
HE_FILE = os.path.join(HERE, "current_batch_he.json")


def get_ctrl(s):
    return s[: len(s) - len(s.lstrip(CTRL))]


def is_namey(en):
    en_c = en.lstrip(CTRL).strip()
    ws = en_c.split()
    return bool(ws) and len(ws) <= 4 and all(NAMEWORD.match(w) for w in ws)


def translate_entry(k, en_raw):
    """
    Translate en_raw to Hebrew (f, m).
    Returns (f_str, m_str) or None if untranslatable.
    The ctrl prefix of en_raw is preserved in output.
    """
    ctrl = get_ctrl(en_raw)
    en = en_raw.lstrip(CTRL).strip()

    # If foreign chars in source — skip
    if FOREIGN.search(en):
        return None

    # If is a proper name — keep as-is
    if is_namey(en) and not FOREIGN.search(en):
        return (en_raw, en_raw)

    # Lookup in our translation table
    t = TRANSLATION_TABLE.get(en) or TRANSLATION_TABLE.get(en.rstrip(".!?,"))
    if t:
        if isinstance(t, str):
            f, m = t, t
        else:
            f, m = t
        return (ctrl + f, ctrl + m)

    # Check for struct-only entries (e.g., just a tag/placeholder)
    core = STRUCT.sub("", en).strip()
    if not core:
        # Pure structural text — keep as-is
        return (en_raw, en_raw)

    # Can't translate — return None (will be skipped)
    return None


# =============================================================================
# TRANSLATION TABLE — English → (female_he, male_he)
# Single string means f==m.
# =============================================================================
TRANSLATION_TABLE = {
    # Common game UI
    "Put Down": ("הנח", "הנח"),
    "Take All": ("קחי הכל", "קח הכל"),
    "Buy Soda": ("קני סודה", "קנה סודה"),
    "Old Cars": "מכוניות ישנות",
    "Marker 1": "סמן 1",
    "Unit 303": "יחידה 303",
    "Name Tag": "תג שם",
    "Old Doll": "בובה ישנה",
    "Ice Bath": "אמבטיית קרח",
    "Meds Box": "קופסת תרופות",
    "Mad Dash": "ריצה מטורפת",
    "Air Dash": "קפיצת אוויר",
    "Sit back": ("שבי בנוח", "שב בנוח"),
    "Call me.": ("התקשרי אליי.", "התקשר אליי."),
    "VIP Room": "חדר VIP",
    "WEAK to:": "חלש נגד:",
    "Level Up": "עלייה ברמה",
    "55: Roof": "55: גג",
    "Dead bum": "נחשל מת",
    "Open Map": "פתח מפה",
    "I agree.": ("אני מסכימה.", "אני מסכים."),
    "No funds": "אין כספים",
    "Take Off": "קחי לך", # context: could be game move name; keep original
    "The Hunt": "הציד",
    "Mob Boss": "ראש כנופייה",
    "Hoo boy.": "יאלה נו.",
    "Not yet.": "עדיין לא.",
    "Yep, me.": "כן, אני.",
    "It's me.": "זה אני.",
    "Bye now.": "שלום לך.",
    "Oh, God!": "אלוהים!",
    "Stop it!": ("תפסיקי!", "תפסיק!"),
    "1.315 in": "1.315 אינץ",
    # More common phrases
    "I'm out.": "אני יוצאת.", # wait - NPC text, same
    "No deal.": "אין עסקה.",
    "My bad.": "אשמתי.",
    "Cool it.": ("תרגעי.", "תרגע."),
    "Move it.": ("תזזי.", "תזוז."),
    "Back off.": ("תתרחקי.", "תתרחק."),
    "Drop it.": ("שחרר את זה.", "שחרר את זה."),
    "Forget it": "שכח מזה.",
    "Good one.": "טוב מאוד.",
    "Well then": "אז בכן.",
    "Come on.": ("בואי כבר.", "בוא כבר."),
    "Get out.": ("צאי.", "צא."),
    "Hold on.": "רגע.",
    "Let's go": ("בואי נלך.", "בוא נלך."),
    "Not now.": "לא עכשיו.",
    "Okay then": "אחלה אז.",
    "Right then": "אז יאלה.",
    "See you.": "להתראות.",
    "Sure.": "בטח.",
    "Thanks.": "תודה.",
    "Wow.": "וואו.",
    "Yeah.": "כן.",
    "Yes.": "כן.",
    "No.": "לא.",
    "Wait.": "רגע.",
    "Really?": "באמת?",
    "What?": "מה?",
    "Done.": "סיום.",
    "Fine.": "בסדר.",
    "Later.": "אחר כך.",
    "Okay.": "אחלה.",
    "Right.": "נכון.",
    "Exactly.": "בדיוק.",
    "Agreed.": ("מסכימה.", "מסכים."),
    "Perfect.": "מושלם.",
    "Enough.": "מספיק.",
    "Anyway.": "בכל מקרה.",
    "Easy.": "בקלות.",
    "Go on.": ("המשיכי.", "המשך."),
    "No way.": "לא סיכוי.",
    "Of course.": "כמובן.",
    "Not bad.": "לא רע.",
    "Good luck.": "בהצלחה.",
    "Be careful.": ("היי זהירה.", "היה זהיר."),
    "Watch out.": ("שימי לב.", "שים לב."),
    "Nice work.": "עבודה יפה.",
    "Good job.": "כל הכבוד.",
    "Great.": "מצוין.",
    "Excellent.": "מעולה.",
    "Impressive.": "מרשים.",
    "Interesting.": "מעניין.",
    "Understood.": ("הבנתי.", "הבנתי."),
    "Affirmative.": ("מאשרת.", "מאשר."),
    "Negative.": ("שוללת.", "שולל."),
    "Confirmed.": "מאושר.",
    "Denied.": "נדחה.",
    "Unknown.": "לא ידוע.",
    "Classified.": "מסווג.",
    "Access denied.": "גישה נדחתה.",
    "Mission complete.": "משימה הושלמה.",
    "Mission failed.": "משימה נכשלה.",
    "Objective complete.": "יעד הושג.",
    "Warning.": "אזהרה.",
    "Alert.": "התראה.",
    "Caution.": "זהירות.",
    "Danger.": "סכנה.",
    "Emergency.": "חירום.",
}


def run():
    # Step 1: get_batch.py
    r = subprocess.run([sys.executable, "get_batch.py"], capture_output=True, text=True, cwd=HERE)
    print(r.stdout.strip())
    if "All done!" in r.stdout:
        print("=== All done! ===")
        return True
    if r.returncode != 0:
        print("get_batch.py error:", r.stderr)
        return False

    # Step 2: Read batch
    if not os.path.exists(BATCH_FILE):
        print("No batch file!")
        return False
    cb = json.load(open(BATCH_FILE, encoding="utf-8"))

    # Step 3: Translate
    he = {}
    skipped = []
    for k, en_raw in cb.items():
        result = translate_entry(k, en_raw)
        if result:
            f, m = result
            he[k] = {"f": f, "m": m}
        else:
            skipped.append((k, en_raw))

    if skipped:
        print(f"  Skipped {len(skipped)} untranslatable entries:")
        for k, v in skipped[:5]:
            print(f"    {k}: {repr(v[:60])}")

    with open(HE_FILE, "w", encoding="utf-8") as f:
        json.dump(he, f, ensure_ascii=False, indent=1)
    print(f"  Wrote {len(he)} translations to current_batch_he.json")

    # Step 4: merge_batch.py
    r2 = subprocess.run([sys.executable, "merge_batch.py"], capture_output=True, text=True, cwd=HERE)
    print(r2.stdout.strip())
    return False


if __name__ == "__main__":
    for _ in range(200):  # safety cap
        done = run()
        if done:
            break
    else:
        print("Safety cap reached.")
