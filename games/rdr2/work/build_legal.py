#!/usr/bin/env python3
"""build_legal.py — the REAL boot legal splash, in Hebrew, through the finished pipeline.

Not a proof any more: this is the game's own `LEGAL_SPLASH_*` text translated and run through
everything proofs #1-#7 established — UBA logical→visual, pre-wrap to the measured box budget,
balanced line widths, and full justification with a ragged final line. Both boot screens are
genuinely localized, and it is the first real content to use the whole chain end to end.

⚠️ Translation authorship: the standing rule is that Claude never translates game text
([[delegate-all-translation]]). The user explicitly asked for these four strings ("תכתוב את
המשפטים האלו בעברית המקורי"), the same one-off override used before for VirtualDJ and the
Plague Tale tail. The ~218k-line corpus still goes to the fleet.

Notes on the source:
  * The corpus dump shows `�` for `©` and `?` for `™` — dump mojibake, not the game. Both
    glyphs exist in the font (checked), so they are written properly here.
  * URLs stay Latin: UBA keeps them forward as LTR runs inside the RTL line.
  * `LEGAL_SPLASH_2` carries a real `~n~~n~` paragraph break, so each block is justified on its
    own and the breaks are re-emitted in place.
  * No value may contain `=` — the LML `KEY = value` parser eats it (seen in-game).

Run:  python build_legal.py <ready_mod_extracted_dir> <font_lib_efigs_HE.gfx> [--deploy]
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rdr2_text as R
from rdr2_rtl import justify_visual_px

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "legal")
GAME = r"C:\Program Files (x86)\Steam\steamapps\common\Red Dead Redemption 2"

BUDGET = 13500
FACE = "Hapna Slab Serif  DemiBold"

HEB = {
    # screen 2, top — copyright / trademarks
    "LEGAL_SPLASH_1":
        "Rockstar Games, Inc. ©2005-19. השמות Rockstar Games, Red Dead Redemption, "
        "Redemption, Red Dead ו-Dead Eye הם סימנים, לוגואים וזכויות יוצרים של "
        "Take-Two Interactive. Dolby וסמל ה-D הכפול הם סימנים מסחריים של "
        "Dolby Laboratories. כל יתר הסימנים והסימנים המסחריים הם רכושם של בעליהם "
        "בהתאמה. כל הזכויות שמורות.",

    # screen 2, body — licence / online account terms
    "LEGAL_SPLASH_1B":
        "תנאי רישיון התוכנה מופיעים במשחק ובכתובת www.rockstargames.com/eula; תנאי "
        "החשבון המקוון מופיעים בכתובת www.rockstargames.com/socialclub. גישה שאינה "
        "ניתנת להעברה לתכונות מיוחדות, כגון תוכן, שירותים ותכונות בלעדיים, ניתנים "
        "לפתיחה, להורדה, לריבוי משתתפים, מקוונים או בונוס, עשויה לחייב קוד סידורי "
        "חד-פעמי, תשלום נוסף ו/או רישום חשבון מקוון שאינו ניתן להעברה (משתנה, גיל 13 "
        "ומעלה). הגישה לתכונות מיוחדות עשויה לחייב חיבור לאינטרנט, עשויה שלא להיות "
        "זמינה לכל המשתמשים או בכל עת, ועשויה להיפסק, להשתנות או להיות מוצעת בתנאים "
        "שונים ללא הודעה מוקדמת. הפרה של הסכם הרישיון, של כללי ההתנהגות או של מדיניות "
        "אחרת עלולה להביא להגבלה או להפסקה של הגישה למשחק או לחשבון המקוון. למידע "
        "עדכני, לשירות לקוחות ולתמיכה טכנית בקרו בכתובת www.rockstargames.com/support.",

    # screen 1, top — Social Club / privacy (keeps its own ~n~~n~ break)
    "LEGAL_SPLASH_2":
        "המידע על המשחק שלכם עשוי להיות מוצג בדפי אינטרנט ובטבלאות שיאים, ובכללם אלה "
        "שבכתובת http://www.rockstargames.com/socialclub. ~n~~n~"
        "לפרטים, לכללים הרשמיים או לביטול ההשתתפות בתכונות מסוימות של Social Club "
        "בקרו בכתובת http://www.rockstargames.com/socialclub/privacy.",

    # screen 1, body — fiction disclaimer / EULA
    "LEGAL_SPLASH_2B":
        "משחק זה הוא בדיוני. הוא עשוי להציג אנשים, מקומות, חברות, קבוצות, אירועים, "
        "מבנים ודברים אחרים הדומים לאלה שבעולם האמיתי; אין להם כל קשר או שיוך למשחק "
        "זה, והצגתם אינה עובדתית. יוצרי המשחק, מפיציו ובעלי הרישיון שלו אינם מאשרים, "
        "מעודדים או תומכים בתוכן כלשהו. העתקה לא מורשית, שינוי, הנדסה לאחור, פירוק "
        "קוד, שידור, הצגה פומבית, השכרה, תשלום עבור משחק או עקיפה של הגנת ההעתקה "
        "אסורים ומהווים הפרה של הסכם הרישיון.",
}

LOADER_ROOT = ["dinput8.dll", "ScriptHookRDR2.dll", "vfs.asi", "ModManager.Core.dll",
               "ModManager.NativeInterop.dll", "NLog.dll", "lml.ini"]
LOADER_LML = ["mods.xml", "patterns.dat", "KGF/install.xml", "tranar/install.xml"]


def render(logical):
    """Justify each ~n~-separated BLOCK on its own, keeping the author's breaks in place."""
    return "~n~".join(
        "" if not b.strip() else justify_visual_px(b.strip(), BUDGET, FACE)
        for b in logical.split("~n~")
    )


def main():
    ready_dir, font_src = sys.argv[1], sys.argv[2]
    deploy = "--deploy" in sys.argv

    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, "lml", "KGF", "asset_replace"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "lml", "tranar"), exist_ok=True)
    for f in LOADER_ROOT:
        shutil.copy2(os.path.join(ready_dir, f), os.path.join(OUT, f))
    for f in LOADER_LML:
        dst = os.path.join(OUT, "lml", f)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(os.path.join(ready_dir, "lml", f), dst)
    shutil.copy2(font_src, os.path.join(OUT, "lml", "KGF", "asset_replace", "font_lib_efigs.gfx"))

    for k, v in HEB.items():
        assert "=" not in v, f"{k}: '=' breaks the LML parser"

    recs = [{"kind": "entry", "key": k, "val": render(v)} for k, v in HEB.items()]
    text = "# RED DEAD REDEMPTION 2 Hebrew — boot legal splash (real game text)\n\n" \
           + R.serialise(recs) + "\n"
    with open(os.path.join(OUT, "lml", "tranar", "Ko Games Studio.gxt2"), "w", encoding="utf-8") as f:
        f.write(text)

    print("built legal splash at:", OUT)
    for k in HEB:
        segs = render(HEB[k]).split("~n~")
        print(f"  {k:<16} lines={len(segs):>2}  chars={len(HEB[k]):>4}")

    if deploy:
        for rel in ("lml/tranar/Ko Games Studio.gxt2",
                    "lml/KGF/asset_replace/font_lib_efigs.gfx"):
            parts = rel.split("/")
            shutil.copy2(os.path.join(OUT, *parts), os.path.join(GAME, *parts))
        print("deployed to:", GAME)


if __name__ == "__main__":
    main()
