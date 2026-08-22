#!/usr/bin/env python3
"""build_ready_dropin.py — assemble a COMPLETE one-extract RDR2 Hebrew menu-proof drop-in.

Takes the loader INFRASTRUCTURE verbatim from Ko Games' proven `ready-mod` (dinput8 ASI loader,
ScriptHookRDR2.dll, vfs.asi = the LML engine, ModManager libs, lml.ini, patterns.dat) and swaps
ONLY the content: our Hebrew-injected font + our Hebrew menu-proof text (VISUAL). The user
extracts the zip into the RDR2 game folder and launches — nothing else to install.

The menu-proof strings (a menu-PROOF is the one place the playbook lets us translate ~a dozen
strings ourselves): the boot LEGAL_SPLASH (guaranteed visible) + the real Pause/Player-Menu
labels (`PM_*`, `UI_SCF_OPTIONS`, …) whose English we resolved from the corpus. Stored VISUAL.

Run:  python build_ready_dropin.py <ready_mod_extracted_dir> <font_lib_efigs_HE.gfx>
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
OUT = os.path.join(HERE, "menu_proof_ready")

# boot splash (visible every launch) + high-confidence Pause/Player-Menu labels (logical Hebrew;
# build_hebrew stores VISUAL). Marker proves the DataFile override mounts + the font loads.
PROOF = {
    "LEGAL_SPLASH_1": "ZZ-RDR2-OK-ZZ ~n~ תרגום עברית — מרכז התרגום העברי ~n~ בדיקת כיוון RTL: 12 דולרים",
    "LEGAL_SPLASH_2": "אם אתה קורא עברית תקינה מימין לשמאל — הכל עובד",
    "UI_SCF_OPTIONS": "אפשרויות",
    "PM_SCR_STORY":   "סיפור",
    "PM_PANE_NEW":    "משחק חדש",
    "PM_SCR_LOAD":    "טעינת משחק",
    "PM_SG_PAUSE":    "שמירת משחק",
    "PM_PANE_CON":    "פקדים",
    "PM_SCR_DISPLAY": "תצוגה",
    "TITLE_AUDIO":    "שמע",
    "PMNU_HEADER":    "תפריט שחקן",
    "0x57E955BF":     "השהיה",     # PAUSE
    "0x96CA9C59":     "יציאה",     # Quit
    "0xB35CC603":     "כבוד",      # HONOR
}

# loader infrastructure copied verbatim from Ko Games' ready-mod (NOT our IP; the user relies on
# the same public, VirusTotal-scanned files to run the Arabic mod).
LOADER_ROOT = ["dinput8.dll", "ScriptHookRDR2.dll", "vfs.asi", "ModManager.Core.dll",
               "ModManager.NativeInterop.dll", "NLog.dll", "lml.ini"]
LOADER_LML = ["mods.xml", "patterns.dat", "KGF/install.xml", "tranar/install.xml"]


def main():
    ready_dir, font_src = sys.argv[1], sys.argv[2]
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, "lml", "KGF", "asset_replace"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "lml", "tranar"), exist_ok=True)

    # loader infra verbatim
    for f in LOADER_ROOT:
        shutil.copy2(os.path.join(ready_dir, f), os.path.join(OUT, f))
    for f in LOADER_LML:
        dst = os.path.join(OUT, "lml", f)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(os.path.join(ready_dir, "lml", f), dst)

    # our content: Hebrew font (replaces the Arabic one) + Hebrew text (keeps the DataFile name)
    shutil.copy2(font_src, os.path.join(OUT, "lml", "KGF", "asset_replace", "font_lib_efigs.gfx"))
    recs = R.build_hebrew([], PROOF)
    text = "# RED DEAD REDEMPTION 2 Hebrew — menu proof (Hebrew Translation Hub)\n\n" \
           + R.serialise(recs) + "\n"
    with open(os.path.join(OUT, "lml", "tranar", "Ko Games Studio.gxt2"), "w", encoding="utf-8") as f:
        f.write(text)

    print("built ready drop-in at:", OUT)
    total = 0
    for root, _, files in os.walk(OUT):
        for fn in files:
            p = os.path.join(root, fn)
            total += os.path.getsize(p)
            print(f"  {os.path.relpath(p, OUT):55s} {os.path.getsize(p):>10} B")
    print(f"total {total} B")


if __name__ == "__main__":
    main()
