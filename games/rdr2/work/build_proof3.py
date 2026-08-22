#!/usr/bin/env python3
"""build_proof3.py — proof #3: the three cases the menu-proof did NOT cover.

The menu proof (2026-07-19) closed mount + font + short-line RTL. It left three open:

  Q1  LONG PARAGRAPH + the engine's own word-wrap.  THE decisive one.
      We store VISUAL (pre-reversed) and the engine wraps in STORAGE order, so a long
      un-broken Hebrew paragraph should wrap into lines whose ORDER is inverted (the
      end of the sentence lands on the first line, and you must read bottom-up).
      `visual_line` already splits on ~n~ and keeps line order — but that only helps
      for EXPLICIT breaks. So this is an A/B:
        LEGAL_SPLASH_2B = the paragraph RAW      (auto-wrap  -> expected BROKEN)
        LEGAL_SPLASH_1B = the SAME text PRE-WRAPPED with ~n~ (expected CORRECT)
      Both are long auto-wrapping paragraphs on the two consecutive boot splash
      screens, so ONE launch answers it. Numbered sentence markers (1)(2)(3)... make
      an inverted line order unmistakable at a glance.

  Q2  MIXED English+Hebrew in one sentence — a stress line with Latin words, digits,
      decimals, a date and punctuation, beyond the short "RTL: 12" that already passed.

  Q3  The BIG distressed title ("ALERT") — font or image?  Already answered from the
      data: Ko Games' Arabic DOES translate WARNING_EXIT_WINDOWS ('ALERT' -> 'يحذر')
      while shipping ONLY font_lib_efigs.gfx, so it is a FONT FACE inside the very
      file we injected. This confirms it in 3 seconds: ESC -> Quit to desktop.

Run:  python build_proof3.py <ready_mod_extracted_dir> <font_lib_efigs_HE.gfx>
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(__file__))
import rdr2_text as R

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "proof3")

# Conservative: the English paragraph justifies to roughly 100-120 chars, but Hebrew
# glyphs run wider. 70 keeps every pre-wrapped line comfortably inside the box, so the
# control line CANNOT auto-wrap — which is the whole point of the control.
WRAP = 70

# One paragraph, used twice. The (n) markers are the tell: read the block right-to-left,
# top line first — if the numbers climb 1,2,3... the wrap is fine; if they climb from the
# BOTTOM line upward, the engine wrapped our pre-reversed text and inverted the order.
PARA = (
    "(1) זהו מבחן פסקה ארוכה בעברית שנועד לבדוק כיצד המנוע גולש שורות. "
    "(2) הטקסט נשמר בסדר חזותי הפוך מראש, ולכן חשוב לוודא שסדר השורות נשאר תקין. "
    "(3) אם המספרים עולים משורה לשורה מלמעלה למטה, הגלישה האוטומטית עובדת כמו שצריך. "
    "(4) אם המספרים עולים מלמטה כלפי מעלה, המנוע גולש לפי סדר האחסון ויש לשבור שורות ידנית. "
    "(5) ארתור מורגן רכב מ-Valentine אל Saint Denis. "
    "(6) המשפט האחרון של הפסקה חייב להופיע בשורה האחרונה."
)


def wrap_logical(text, width=WRAP):
    """Greedy word-wrap on the LOGICAL text, joined with ~n~ so `visual_line` reverses
    each line on its own and keeps the line order (see gtav_gxt2.visual_line)."""
    words, lines, cur = text.split(), [], ""
    for w in words:
        cand = w if not cur else cur + " " + w
        if len(cand) > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return "~n~".join(lines)


PROOF = {
    # --- Q1: A/B on two consecutive boot screens -------------------------------
    "LEGAL_SPLASH_2B": PARA,                 # RAW  -> engine auto-wrap
    "LEGAL_SPLASH_1B": wrap_logical(PARA),   # PRE-WRAPPED with ~n~ -> control

    # --- Q2: mixed English + Hebrew in one sentence ----------------------------
    "LEGAL_SPLASH_2": (
        "מבחן ערבוב: ארתור קנה רובה Lancaster Repeater ב-45.50 דולר "
        "בחנות של Valentine בתאריך 12/04/1899, ואז נסע 3 ק\"מ."
    ),
    "LEGAL_SPLASH_1": (
        "ZZ-RDR2-P3-ZZ ~n~ מבחן 3: פסקה ארוכה, ערבוב אנגלית, וכותרת גדולה ~n~ "
        "סימני פיסוק: (סוגריים) \"מרכאות\" 'גרש' — מקף, נקודה. סוף!"
    ),

    # --- Q3: the big distressed title + its body (ESC -> Quit to desktop) ------
    "WARNING_EXIT_WINDOWS":  "אזהרה",
    "WARNING_EXIT_WINDOWS2": "אזהרה",
    "EXIT_SURE_2": "האם אתה בטוח שברצונך לצאת אל שולחן העבודה?~n~כל ההתקדמות שלא נשמרה תאבד.",
    # same big-title face, in case the quit alert uses one of the siblings
    "MG_ALERT": "אזהרה",
    "SG_HDNG": "אזהרה",
    "ALERT_ERROR_MSG": "אזהרה",
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
    recs = R.build_hebrew([], PROOF)
    text = "# RED DEAD REDEMPTION 2 Hebrew — proof #3 (paragraph wrap / mixed / big title)\n\n" \
           + R.serialise(recs) + "\n"
    with open(os.path.join(OUT, "lml", "tranar", "Ko Games Studio.gxt2"), "w", encoding="utf-8") as f:
        f.write(text)

    print("built proof #3 at:", OUT)
    print(f"pre-wrapped control = {wrap_logical(PARA).count('~n~') + 1} lines at <= {WRAP} chars")
    total = 0
    for root, _, files in os.walk(OUT):
        for fn in files:
            p = os.path.join(root, fn)
            total += os.path.getsize(p)
    print(f"total {total} B")


if __name__ == "__main__":
    main()
