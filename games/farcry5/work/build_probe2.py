"""
FC5 round 2 -- CHARSET FINGERPRINT of the Arabic-locale font.

Round 1 proved the patched oasis MOUNTS (the Latin marker rendered) and that Hebrew
comes out as tofu boxes.  That leaves one question: WHAT can the font the Arabic locale
uses actually draw?  The answer decides the whole font strategy:

  * if Cyrillic / Greek / CJK also tofu -> it is a small Arabic+Latin face, loaded per
    locale, and we must find and extend THAT face
  * if they render -> it is a big multi-script face and Hebrew is simply absent from it

Method: patch rows that are KNOWN to be on the main menu (all in section 2fe9eadf, read
off the round-1 screenshot), each with
  * an ASCII "N:" label -- ASCII always renders, so every row is self-identifying, and
  * a UNIQUE repeat count -- the number of boxes tells the rows apart even when nothing
    renders.  (Round 1's flaw: two different probes were both 4 characters long.)

  python build_probe2.py --deploy | --revert
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from fc5_fat import Fat
from fc5_crc64 import name_hash
import fc5_oasis as O
import fc5_deploy as D

UI_PATH = "languages/arabic/oasisstrings.oasis.bin"

# (row on screen, keys, value, script under test)
PLAN = [
    ("row1 CONTINUE",   [(0x2fe9eadf, 92598)],                    "ZZ-R2-ZZ",        "MOUNT marker (ASCII)"),
    ("row2 NEW GAME",   [(0x2fe9eadf, 92596)],                    "1:" + "Ы" * 2,    "Cyrillic x2"),
    ("row3 ARCADE",     [(0x2fe9eadf, 251869)],                   "2:" + "Ω" * 3,    "Greek x3"),
    ("row4 ADD-ONS",    [(0x2fe9eadf, 696261), (0x2fe9eadf, 849258)],
                                                                  "3:" + "Ł" * 4,    "Latin-Ext-A x4"),
    ("row5 OPTIONS",    [(0x2fe9eadf, 149368), (0x2fe9eadf, 150446)],
                                                                  "4:" + "漢" * 5,   "CJK x5"),
    ("row6 STORE",      [(0x2fe9eadf, 696260)],                   "5:" + "א" * 6,    "HEBREW x6"),
    ("row7 CONTINUE2",  [(0x2fe9eadf, 696298)],                   "6:" + "é" * 7,    "Latin-1 accented x7"),
    ("row8 QUIT-DESK",  [(0xdd3795ad, 167159)],                   "7:" + "ك" * 8,    "Arabic x8 (CONTROL - must render)"),
]


def build():
    edits = {}
    for _, keys, val, _ in PLAN:
        for k in keys:
            edits[k] = val
    return edits


def main(cmd):
    if cmd == "--revert":
        D.revert_all(); return
    edits = build()
    print("charset-fingerprint plan (each row is self-identifying via its ASCII label):")
    for row, keys, val, why in PLAN:
        print(f"  {row:16s} {val!r:22s} {why}")
    print(f"\n{len(edits)} keys\n")

    # Deploy is append-only and revert restores the .fat + truncates the .dat, so the
    # cleanest way to guarantee a PRISTINE input is simply to revert first.
    D.revert_all()

    payloads = {}
    h = name_hash(UI_PATH)
    for arch in ("common.fat", "patch.fat"):
        fat = Fat(os.path.join(D.PC, arch))
        raw = fat.read_data(fat.by_hash[h])
        ver, secs = O.parse(raw)
        base = O.flat(secs)
        # sanity: the input must be pristine (no leftover marker from an earlier round)
        assert not any(str(v).startswith("ZZ-") for v in base.values()), "input is NOT pristine"
        new, applied = O.edit(raw, edits)
        flat = O.flat(O.parse(new)[1])
        landed = sum(1 for k, v in edits.items() if flat.get(k) == v)
        print(f"  {arch}: applied={applied} landed={landed}/{len(edits)}  {len(raw):,} -> {len(new):,} B")
        payloads[arch] = {h: new}

    if cmd != "--deploy":
        print("\n(dry run -- archives left REVERTED)"); return

    ok = True
    for arch, reps in payloads.items():
        ok &= D.deploy_archive(arch, reps)
    print("\n  DEPLOY OK" if ok else "\n  DEPLOY FAILED")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main(sys.argv[1] if len(sys.argv) > 1 else "")
