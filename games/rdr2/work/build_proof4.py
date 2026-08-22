#!/usr/bin/env python3
"""build_proof4.py — verify the UBA visual fix in-game AND measure the text-box width.

Proof #3 produced two findings:
  1. Long paragraph + engine auto-wrap  -> LINE ORDER INVERTED (markers ran (6)->(1)).
     Pre-wrapping the SAME text with explicit ~n~ rendered in the correct order.
     => every value long enough to wrap must be PRE-WRAPPED, which needs the box width.
  2. Multi-character neutral runs were mis-placed by GTA V's `visual_line`
     (`: (` , `) "` , `, `) -> colon before the wrong word, `(סוגריים)` shown as
     `)סוגריים(`. Replaced by the real Unicode Bidi Algorithm in `rdr2_rtl.to_visual`.

This proof checks both:
  * LEGAL_SPLASH_1  — the SAME punctuation line that failed, now via UBA. Must read
                      `סימני פיסוק: (סוגריים) "מרכאות" — מקף, נקודה. סוף!` exactly.
  * LEGAL_SPLASH_2  — the mixed EN/HE line via UBA (spacing around `45.50` was off before).
  * LEGAL_SPLASH_2B — a WIDTH RULER: lines of exactly 60,70,…,130 chars, each carrying its
                      own length at BOTH ends. The largest N whose two `[N]` markers stay on
                      ONE line is the usable width for this surface; the first N that splits
                      is over the limit. That number feeds `build_hebrew(wrap_width=...)`.
  * LEGAL_SPLASH_1B — the proof-#3 paragraph, pre-wrapped + UBA. Markers (1)…(6) must run
                      top-down and the punctuation must sit correctly.
  * the quit ALERT  — regression check on the big title + a `~n~` body (already passed).

Run:  python build_proof4.py <ready_mod_extracted_dir> <font_lib_efigs_HE.gfx>
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rdr2_text as R
from rdr2_rtl import wrap_logical

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "proof4")

PARA = (
    "(1) זהו מבחן פסקה ארוכה בעברית שנועד לבדוק כיצד המנוע גולש שורות. "
    "(2) הטקסט נשמר בסדר חזותי הפוך מראש, ולכן חשוב לוודא שסדר השורות נשאר תקין. "
    "(3) אם המספרים עולים משורה לשורה מלמעלה למטה, הגלישה האוטומטית עובדת כמו שצריך. "
    "(4) אם המספרים עולים מלמטה כלפי מעלה, המנוע גולש לפי סדר האחסון ויש לשבור שורות ידנית. "
    "(5) ארתור מורגן רכב מ-Valentine אל Saint Denis. "
    "(6) המשפט האחרון של הפסקה חייב להופיע בשורה האחרונה."
)

RULER_WIDTHS = (60, 70, 80, 90, 100, 110, 120, 130)


def ruler_line(n):
    """A line of EXACTLY n chars carrying its own length at both ends.

    Read right-to-left: if both [n] markers sit on the same line, n fits."""
    head, tail = f"[{n}] ", f" [{n}]"
    filler_len = n - len(head) - len(tail)
    words = []
    used = 0
    while used < filler_len:
        w = "בדיקה"
        add = len(w) if not words else len(w) + 1
        if used + add > filler_len:
            break
        words.append(w)
        used += add
    line = head + " ".join(words) + tail
    return line + "ם" * (n - len(line))     # pad to exactly n


PROOF = {
    "LEGAL_SPLASH_1": (
        "ZZ-RDR2-P4-ZZ ~n~ "
        "סימני פיסוק: (סוגריים) \"מרכאות\" — מקף, נקודה. סוף! ~n~ "
        "מספרים: 1, 2 ו-3. שאלה? תשובה: כן."
    ),
    "LEGAL_SPLASH_2": (
        "מבחן ערבוב: ארתור קנה רובה Lancaster Repeater ב-45.50 דולר "
        "בחנות של Valentine בתאריך 12/04/1899, ואז נסע 3 ק\"מ."
    ),
    # width ruler — pre-wrapped ONLY at our own explicit ~n~, one line per width
    "LEGAL_SPLASH_2B": "~n~".join(ruler_line(n) for n in RULER_WIDTHS),
    # the paragraph, pre-wrapped + UBA: expected fully correct
    "LEGAL_SPLASH_1B": wrap_logical(PARA, 70),
    # regression: big title + ~n~ body
    "WARNING_EXIT_WINDOWS": "אזהרה",
    "WARNING_EXIT_WINDOWS2": "אזהרה",
    "EXIT_SURE_2": "האם אתה בטוח שברצונך לצאת (אל שולחן העבודה)?~n~כל ההתקדמות שלא נשמרה תאבד.",
}

LOADER_ROOT = ["dinput8.dll", "ScriptHookRDR2.dll", "vfs.asi", "ModManager.Core.dll",
               "ModManager.NativeInterop.dll", "NLog.dll", "lml.ini"]
LOADER_LML = ["mods.xml", "patterns.dat", "KGF/install.xml", "tranar/install.xml"]


def main():
    ready_dir, font_src = sys.argv[1], sys.argv[2]
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
    # wrap_width=None: every value here is already broken by hand, so the builder must not
    # re-wrap and disturb the ruler.
    recs = R.build_hebrew([], PROOF)
    text = "# RED DEAD REDEMPTION 2 Hebrew — proof #4 (UBA punctuation fix + width ruler)\n\n" \
           + R.serialise(recs) + "\n"
    with open(os.path.join(OUT, "lml", "tranar", "Ko Games Studio.gxt2"), "w", encoding="utf-8") as f:
        f.write(text)

    for n in RULER_WIDTHS:
        assert len(ruler_line(n)) == n, n
    print("built proof #4 at:", OUT)
    print("ruler widths:", ", ".join(map(str, RULER_WIDTHS)))
    total = sum(os.path.getsize(os.path.join(r, fn))
                for r, _, fs in os.walk(OUT) for fn in fs)
    print(f"total {total} B")


if __name__ == "__main__":
    main()
