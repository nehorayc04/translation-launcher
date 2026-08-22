#!/usr/bin/env python3
"""build_proof7.py — kill the residual right-align error: BALANCE the wrap + MEASURE the space.

Proof #6 got lines 1-3 flush (pads of 1-5 spaces) but left the last line ~50px short (pad of
71 spaces). Two independent causes, one fix each:

  A. GREEDY WRAP dumps the remainder on the final line (13224/13272/13414/**9268** units), so
     that line alone needs a 71-space pad — and ANY error in the assumed space advance is
     multiplied by exactly that count. `rdr2_metrics.wrap_px_balanced` evens the widths out
     (12222/12584/12362/12010) so every pad lands in the 15-25 range and the same relative
     error becomes invisible.
  B. The space advance is still a GUESS, because we do not know which of the 18 faces the
     splash renders with (candidates disagree 52-60 units, i.e. up to 15%). Stop guessing and
     let the game measure it: a LADDER of lines that are N spaces followed by the number N
     itself, for N = 200…400. Whichever number lands flush against the right margin gives
     `space = (BUDGET - width("NNN")) / N` directly, with no face assumption at all.

  LEGAL_SPLASH_1B  the paragraph, BALANCED wrap + pixel pad   (fix A)
  LEGAL_SPLASH_2B  the space-calibration ladder                (fix B)

The ladder's first row is the proof-#4 ruler line that is KNOWN to fit exactly one line, so it
also marks where the true right margin is for comparison.

Run:  python build_proof7.py <ready_mod_extracted_dir> <font_lib_efigs_HE.gfx> [--deploy]
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rdr2_metrics as M
import rdr2_text as R
from build_proof4 import ruler_line
from rdr2_rtl import _segment_to_visual, justify_visual_px, to_visual

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "proof7")
GAME = r"C:\Program Files (x86)\Steam\steamapps\common\Red Dead Redemption 2"

BUDGET = 13500
FACE = "Hapna Slab Serif  DemiBold"
LADDER = (200, 240, 280, 320, 360, 400)

PARA = (
    "(1) זהו מבחן יישור לימין עם שבירה מאוזנת: כל השורות אמורות להיות באותו אורך בערך. "
    "(2) בגרסה הקודמת השבירה הייתה חמדנית, ולכן השורה האחרונה יצאה קצרה בהרבה מהשאר. "
    "(3) שורה קצרה דורשת ריפוד ענק, וכל טעות ברוחב הרווח מוכפלת במספר הרווחים הזה. "
    "(4) עכשיו כל שורה צריכה בערך אותו ריפוד קטן, ולכן הקצה הימני אמור להיות ישר לגמרי. "
    "(5) ארתור מורגן רכב מ-Valentine אל Saint Denis, ושילם 45.50 דולר על הרובה. "
    "(6) המשפט האחרון של הפסקה חייב להיגמר בקצה הימני, בדיוק כמו כל שאר השורות."
)


def balanced_paragraph():
    """FULLY JUSTIFIED — flush on both edges, matching the game's own English paragraphs.

    The earlier version right-aligned by padding each line's left margin, which leaves the
    left edge ragged; the paragraph's FIRST line then visibly starts with an indent, which is
    what the user kept pointing at. `justify_visual_px` puts the slack in the word GAPS
    instead (last line excepted, as typography requires)."""
    return justify_visual_px(PARA, BUDGET, FACE)


def calibration_ladder():
    """N spaces + the number N. The row whose number touches the right margin gives the
    true space advance: space = (BUDGET - width(str(N))) / N."""
    rows = [_segment_to_visual(ruler_line(120))]        # known-to-fit reference margin
    rows += [" " * n + str(n) for n in LADDER]
    return "~n~".join(rows)


PROOF_VISUAL = {
    "LEGAL_SPLASH_1": to_visual(
        "ZZ-RDR2-P7-ZZ ~n~ "
        "מבחן 7: שבירה מאוזנת — כל השורות באותו אורך ~n~ "
        "המסך הבא: סרגל כיול רוחב הרווח."
    ),
    "LEGAL_SPLASH_1B": balanced_paragraph(),
    "LEGAL_SPLASH_2": to_visual(
        "סרגל כיול: השורה העליונה = הקצה הימני האמיתי. "
        "איזה מספר נוגע בו?"
    ),
    "LEGAL_SPLASH_2B": calibration_ladder(),
}

LOADER_ROOT = ["dinput8.dll", "ScriptHookRDR2.dll", "vfs.asi", "ModManager.Core.dll",
               "ModManager.NativeInterop.dll", "NLog.dll", "lml.ini"]
LOADER_LML = ["mods.xml", "patterns.dat", "KGF/install.xml", "tranar/install.xml"]


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

    recs = [{"kind": "entry", "key": k, "val": v} for k, v in PROOF_VISUAL.items()]
    text = "# RED DEAD REDEMPTION 2 Hebrew — proof #7 (balanced wrap + space calibration)\n\n" \
           + R.serialise(recs) + "\n"
    with open(os.path.join(OUT, "lml", "tranar", "Ko Games Studio.gxt2"), "w", encoding="utf-8") as f:
        f.write(text)

    print("built proof #7 at:", OUT)
    for i, l in enumerate(M.wrap_px_balanced(PARA, BUDGET, FACE), 1):
        print(f"  para L{i}: width={M.text_width(l, FACE):>7.0f}  pad={M.pad_spaces(l, BUDGET, FACE):>3} sp")
    print("  ladder rows:", ", ".join(str(n) for n in LADDER),
          f"(assumed space={M.space_width(FACE)} -> full box ≈ "
          f"{int((BUDGET - M.text_width('200', FACE)) / M.space_width(FACE))} spaces)")

    if deploy:
        for rel in ("lml/tranar/Ko Games Studio.gxt2",
                    "lml/KGF/asset_replace/font_lib_efigs.gfx"):
            parts = rel.split("/")
            shutil.copy2(os.path.join(OUT, *parts), os.path.join(GAME, *parts))
        print("deployed to:", GAME)


if __name__ == "__main__":
    main()
