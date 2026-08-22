"""FC5 round 3 -- a REAL Hebrew main menu, stored VISUAL.

Round 2 settled the last gate by MATCHING the rendered glyphs against the atlas
(read_glyphs.py) instead of reading the screenshot by eye: both LOGICAL strings came out in
strict STORAGE order (`שלום` -> starts ש ends ם; `אבגד` -> starts א ends ד).  So the engine
does NOT reorder Hebrew -- its RTL pipeline is gated to the ARABIC script, the AC-Mirage /
Witcher-4.00 signature -- and Hebrew must be stored PRE-REVERSED.

Everything is therefore run through the real UBA with an RTL base (python-bidi), which also
places punctuation, digits and Latin islands correctly -- a hand-rolled run-reversal gets
those wrong on every real sentence ([[store-visual-use-real-uba]]).

Two rows are deliberately kept as a LOGICAL/VISUAL A/B so the choice stays visible on screen.

  python build_menu_he.py [--deploy|--revert]
"""
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from fc5_fat import Fat
from fc5_crc64 import name_hash
import fc5_oasis as O
import fc5_deploy as D
import build_proof as P
from bidi.algorithm import get_display

PC = D.PC
UI_PATH = "languages/arabic/oasisstrings.oasis.bin"
V = lambda s: get_display(s, base_dir="R")     # store VISUAL -- the engine draws as-is

PARA = 'בדיקה: "מרכאות" (סוגריים) — 12 פריטים, ו-Far Cry 5. סוף!'

# (label, [(sectionCRC, id) ...], stored value, note)
PLAN = [
    ("CONTINUE",  [(0x2fe9eadf, 92598), (0x1d9dd44b, 346551), (0x1d9dd44b, 158920)],
     V("המשך משחק"),        "real label"),
    ("NEW GAME",  [(0x2fe9eadf, 92596)],  V("משחק חדש"),        "real label"),
    ("ARCADE",    [(0x2fe9eadf, 251869)], V("ארקייד"),          "real label"),
    ("ADD-ONS",   [(0x2fe9eadf, 696261), (0x2fe9eadf, 849258)],
     V("תוספים"),           "real label"),
    ("OPTIONS",   [(0x2fe9eadf, 149368), (0x2fe9eadf, 150446)],
     V("אפשרויות"),         "real label"),
    # the id first guessed for STORE was wrong; these are every key whose Arabic is 'متجر'
    ("STORE",     [(0x2fe9eadf, 696260), (0x2fe9eadf, 495034), (0x111fe2e1, 870241),
                   (0x119860b8, 700977), (0x127baf74, 852550), (0x3388e58b, 587105)],
     V("חנות"),             "real label"),
    ("CONTINUE2", [(0x2fe9eadf, 696298)], V("המשך"),            "real label"),
    ("QUIT-DESK", [(0xdd3795ad, 167159)], V("יציאה לשולחן העבודה"),
     "the longest label -- watch for clipping"),
    ("LOAD GAME", [(0x1bac2b45, 540039)], V("טען משחק"),        "real label"),
    ("QUIT",      [(0x72711922, 345696), (0x72711922, 274781), (0x8220ea2b, 461746)],
     V("אבגדהוזחטיכךלמםנןסעפףצץקרשת"), "FONT: all 27 letters, VISUAL"),
    ("SETTINGS",  [(0xdd3795ad, 57433)],  V(PARA),              "LAYOUT: punct/digits/Latin"),
    ("RESUME",    [(0xdd3795ad, 551896), (0xf3759c4e, 25553)],
     PARA,                  "A/B control: the SAME sentence stored LOGICAL"),
    ("Arabic",    [(0x82c1dced, 874045)], V("עברית"),           "the language-menu label"),
    ("Yes",       [(0x061dc80e, 506894)], V("כן"),              "real label"),
    ("No",        [(0x061dc80e, 506895)], V("לא"),              "real label"),
]


def main(cmd):
    if cmd == "--revert":
        D.revert_all(); return
    edits = {}
    for _, keys, val, _ in PLAN:
        for k in keys:
            edits[k] = val
    print("round-3 plan (VISUAL unless noted):")
    for label, keys, val, note in PLAN:
        print(f"  {label:11s} {val[:40]!r:44s} {note}")
    print(f"\n{len(edits)} keys\n")

    D.revert_all()          # a deployed slot must never be the input
    heb_ffd = open(os.path.join(P.EXTRACT, "hebrew.ffd"), "rb").read()
    heb_xbt = open(os.path.join(P.EXTRACT, "hebrew.xbt"), "rb").read()

    payloads = {}
    h = name_hash(UI_PATH)
    for arch, fat in P.all_archives():
        reps = {}
        if h in fat.by_hash:
            raw = fat.read_data(fat.by_hash[h])
            new, applied = O.edit(raw, edits)
            flat = O.flat(O.parse(new)[1])
            landed = sum(1 for k, v in edits.items() if flat.get(k) == v)
            print(f"  {arch}: text applied={applied} landed={landed}/{len(edits)}")
            reps[h] = new
        if P.FFD_H in fat.by_hash:
            reps[P.FFD_H] = heb_ffd
        if P.XBT_H in fat.by_hash:
            reps[P.XBT_H] = heb_xbt
        if reps:
            payloads[arch] = reps

    if cmd != "--deploy":
        print("\n(dry run -- archives left REVERTED)"); return
    ok = True
    for arch, reps in payloads.items():
        ok &= D.deploy_archive(arch, reps)
    print("\n  DEPLOY OK" if ok else "\n  DEPLOY FAILED")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main(sys.argv[1] if len(sys.argv) > 1 else "")
