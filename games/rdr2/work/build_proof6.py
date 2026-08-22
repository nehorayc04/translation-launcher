#!/usr/bin/env python3
"""build_proof6.py — pixel-accurate paragraph layout: wrap AND right-align by real advances.

Proof #5 padded by CHARACTER COUNT and the paragraph came out CENTRED, not right-aligned.
The font metrics say why: in this font a Hebrew letter advances ~129 units and a space only
~60, so **one letter is worth ~2.2 spaces** — padding one space per missing character buys
barely half the distance. The user spotted it from the screenshot ("if it can reach the
middle, it should be able to reach the right").

`rdr2_metrics.py` now carries the real `glyphInfo advanceX` table for all 18 faces, so both
the wrap and the padding are computed in font units. Budget calibrated from the proof-#4
ruler: the boot splash FITS the 120-char line (13,537 units) and REJECTS the 130-char one
(14,849), so 13,500 is proven safe.

Two faces are tested side by side because we do not yet know which one the splash uses —
though it barely matters here: all candidates measure the same ruler within ~4%.

  LEGAL_SPLASH_1B  right-aligned using "Hapna Slab Serif  DemiBold"
  LEGAL_SPLASH_2B  right-aligned using "Cabrito Norm Demi"

Whichever lands flush against the right margin identifies the face and confirms the method.

Run:  python build_proof6.py <ready_mod_extracted_dir> <font_lib_efigs_HE.gfx> [--deploy]
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rdr2_text as R
from rdr2_rtl import to_visual, wrap_visual_px

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "proof6")
GAME = r"C:\Program Files (x86)\Steam\steamapps\common\Red Dead Redemption 2"

BUDGET = 13500                       # font units; ruler: 120 chars = 13537 fits, 130 = 14849 not
FACE_A = "Hapna Slab Serif  DemiBold"
FACE_B = "Cabrito Norm Demi"

PARA = (
    "(1) זהו מבחן יישור לימין לפי רוחבי גליפים אמיתיים, ולא לפי ספירת תווים. "
    "(2) בגרסה הקודמת כל שורה רופדה ברווח אחד לכל תו חסר, אבל אות עברית רחבה פי 2.2 מרווח. "
    "(3) לכן הפסקה הגיעה רק עד האמצע, וזו בדיוק הייתה ההוכחה שהכיוון נכון והמידה שגויה. "
    "(4) עכשיו הריפוד מחושב ביחידות הפונט, ולכן כל שורה אמורה להסתיים בדיוק באותו קצה ימני. "
    "(5) ארתור מורגן רכב מ-Valentine אל Saint Denis, ושילם 45.50 דולר על רובה. "
    "(6) המשפט האחרון של הפסקה חייב להיגמר בקצה הימני, לא באמצע ולא בשמאל."
)

PROOF_VISUAL = {
    "LEGAL_SPLASH_1": to_visual(
        "ZZ-RDR2-P6-ZZ ~n~ "
        "מבחן 6: יישור לימין לפי רוחבי גליפים ~n~ "
        "מסך זה: גופן Hapna. המסך הבא: גופן Cabrito."
    ),
    "LEGAL_SPLASH_1B": wrap_visual_px(PARA, BUDGET, FACE_A),
    "LEGAL_SPLASH_2": to_visual("מסך זה: אותה פסקה, נמדדה לפי גופן Cabrito."),
    "LEGAL_SPLASH_2B": wrap_visual_px(PARA, BUDGET, FACE_B),
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

    # already visual -> write records directly (build_hebrew would convert a SECOND time)
    recs = [{"kind": "entry", "key": k, "val": v} for k, v in PROOF_VISUAL.items()]
    text = "# RED DEAD REDEMPTION 2 Hebrew — proof #6 (pixel-accurate wrap + right-align)\n\n" \
           + R.serialise(recs) + "\n"
    with open(os.path.join(OUT, "lml", "tranar", "Ko Games Studio.gxt2"), "w", encoding="utf-8") as f:
        f.write(text)

    print("built proof #6 at:", OUT)
    for k, face in (("LEGAL_SPLASH_1B", FACE_A), ("LEGAL_SPLASH_2B", FACE_B)):
        segs = PROOF_VISUAL[k].split("~n~")
        pads = [len(s) - len(s.lstrip(" ")) for s in segs]
        print(f"  {k:<16} face={face:<28} lines={len(segs)} pad_spaces={pads}")

    if deploy:
        for rel in ("lml/tranar/Ko Games Studio.gxt2",
                    "lml/KGF/asset_replace/font_lib_efigs.gfx"):
            parts = rel.split("/")
            shutil.copy2(os.path.join(OUT, *parts), os.path.join(GAME, *parts))
        print("deployed to:", GAME)


if __name__ == "__main__":
    main()
