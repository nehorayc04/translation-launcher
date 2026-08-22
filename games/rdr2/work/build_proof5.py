#!/usr/bin/env python3
"""build_proof5.py — paragraph LAYOUT: wrap near the real box width, and right-align.

Proof #4 established that the bidi/text side is correct (punctuation, brackets, mixed
EN/HE, line order) and measured the boot-splash box at ~120 chars. But the paragraph was
wrapped at 70, i.e. every line filled only ~58% of the box — and the game's boxes are
LEFT-aligned while JUSTIFYING only the lines THEY wrap. Our explicit `~n~` lines are each
treated as a final line, so nothing is justified and the RIGHT edge — where an RTL reader's
eye starts — comes out ragged. The text decodes perfectly and still reads as broken.

Two independent fixes, tested side by side on the two boot splash screens:

  LEGAL_SPLASH_1B  wrap at 115 (near the measured 120), NO padding
                   -> lines nearly fill the box, so raggedness shrinks on its own.
  LEGAL_SPLASH_2B  wrap at 115 + RIGHT-ALIGNED (pad each visual line on its LEFT)
                   -> every line ends at the same right edge = a true RTL block.

Whichever reads better wins; if the padded one loses its spaces, the engine trims leading
whitespace and fix #1 is the answer on its own.

Run:  python build_proof5.py <ready_mod_extracted_dir> <font_lib_efigs_HE.gfx> [--deploy]
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rdr2_text as R
from rdr2_rtl import to_visual, wrap_visual

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "proof5")
GAME = r"C:\Program Files (x86)\Steam\steamapps\common\Red Dead Redemption 2"

WIDTH = 115          # measured box = 120 fits / 130 wraps; 115 leaves a small margin

PARA = (
    "(1) זהו מבחן פריסה: השורות אמורות למלא כמעט את כל רוחב התיבה, ולא להשאיר שוליים גדולים. "
    "(2) הטקסט נשמר בסדר חזותי הפוך מראש, ולכן חשוב שסדר השורות והיישור יהיו תקינים. "
    "(3) אם כל שורה מתחילה באותו מקום בצד ימין, הקריאה זורמת והפסקה נראית כמו פסקה אמיתית. "
    "(4) אם הקצה הימני מדורג, העין לא יודעת מאיפה להתחיל בכל שורה וזה נראה שבור. "
    "(5) ארתור מורגן רכב מ-Valentine אל Saint Denis, ושילם 45.50 דולר על רובה. "
    "(6) המשפט האחרון של הפסקה חייב להופיע בשורה האחרונה."
)

# ⚠️ These values are written ALREADY VISUAL, so they must NOT go through
# `build_hebrew` (it would run `to_visual` a second time and undo the conversion — the
# padding then lands on the wrong side). We emit the records directly instead.
PROOF_VISUAL = {
    "LEGAL_SPLASH_1": to_visual(
        "ZZ-RDR2-P5-ZZ ~n~ "
        "מבחן 5: פריסת פסקה — רוחב 115 תווים ~n~ "
        "מסך זה: ללא ריפוד. המסך הבא: מיושר לימין."
    ),
    "LEGAL_SPLASH_1B": wrap_visual(PARA, WIDTH),                     # fix 1 only
    "LEGAL_SPLASH_2": to_visual("מסך זה: אותה פסקה, מיושרת לימין (ריפוד רווחים משמאל)."),
    "LEGAL_SPLASH_2B": wrap_visual(PARA, WIDTH, align_right=True),   # fix 1 + fix 2
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

    # already visual -> emit records directly, NOT via build_hebrew (no second conversion)
    recs = [{"kind": "entry", "key": k, "val": v} for k, v in PROOF_VISUAL.items()]
    text = "# RED DEAD REDEMPTION 2 Hebrew — proof #5 (paragraph layout: width + right-align)\n\n" \
           + R.serialise(recs) + "\n"
    txt_path = os.path.join(OUT, "lml", "tranar", "Ko Games Studio.gxt2")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(text)

    print("built proof #5 at:", OUT)
    print(f"paragraph lines @ {WIDTH}: {PROOF_VISUAL['LEGAL_SPLASH_1B'].count('~n~') + 1}")

    if deploy:
        # the loader is already installed from an earlier proof -> swap only the content
        for rel in ("lml/tranar/Ko Games Studio.gxt2",
                    "lml/KGF/asset_replace/font_lib_efigs.gfx"):
            shutil.copy2(os.path.join(OUT, *rel.split("/")), os.path.join(GAME, *rel.split("\\" if "\\" in rel else "/")))
        print("deployed to:", GAME)


if __name__ == "__main__":
    main()
