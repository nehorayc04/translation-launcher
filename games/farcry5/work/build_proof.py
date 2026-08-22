"""
FAR CRY 5 — Phase-1 menu proof.  ONE build that closes every open gate at once.

What each patched entry answers:
  1. MOUNT   -- a pure-Latin marker (ZZ-FC5-OK-ZZ). It renders even if the font has no
                Hebrew, so it separates "the file never loaded" from "no glyphs".
  2. BIDI    -- the SAME word stored LOGICAL on one menu row and VISUAL (pre-reversed)
                on the next.  Exactly ONE of them can read as  שלום .
  3. CONTROL -- אבגד  (4 non-confusable letters, no final forms) pins the direction
                independently of how any single word looks.
  4. FONT    -- all 27 Hebrew letters on one row: any tofu/'?' shows the coverage gap.
  5. LAYOUT  -- a sentence with punctuation, parens, digits and a Latin island, in BOTH
                modes, so ordering of neutrals is visible.

Deployed to BOTH common.fat and patch.fat (patch overrides common -- patch every copy).

  python build_proof.py            # build only, report
  python build_proof.py --deploy
  python build_proof.py --revert
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from fc5_fat import Fat
from fc5_crc64 import name_hash
import fc5_oasis as O
import fc5_deploy as D

try:
    from bidi.algorithm import get_display
except ImportError:
    get_display = None

PC = D.PC
UI_PATH = "languages/arabic/oasisstrings.oasis.bin"
MARKER = "ZZ-FC5-OK-ZZ"
ALPHABET = "אבגדהוזחטיכךלמםנןסעפףצץקרשת"      # 27 letters
PARA = 'בדיקה: "מרכאות" (סוגריים) — 12 פריטים, ו-Far Cry 5. סוף!'


def visual(s):
    """Pre-reversed (VISUAL) form via the real UBA with an RTL base."""
    if get_display is None:
        raise SystemExit("python-bidi missing -- run with the repo .venv python")
    return get_display(s, base_dir="R")


# (label, [(sectionCRC, id) ...], value, what-it-tests)
PLAN = [
    ("CONTINUE",  [(0x2fe9eadf, 92598), (0x1d9dd44b, 346551), (0x1d9dd44b, 158920)],
     MARKER,                     "MOUNT (Latin marker -- font-independent)"),
    ("NEW GAME",  [(0x2fe9eadf, 92596)],
     "שלום",                     "BIDI A: stored LOGICAL"),
    ("LOAD GAME", [(0x1bac2b45, 540039)],
     visual("שלום"),             "BIDI B: stored VISUAL (pre-reversed)"),
    ("OPTIONS",   [(0x2fe9eadf, 149368), (0x2fe9eadf, 150446)],
     "אבגד",                     "CONTROL: 4 distinct letters, LOGICAL"),
    ("QUIT",      [(0x72711922, 345696), (0x72711922, 274781), (0x8220ea2b, 461746)],
     ALPHABET,                   "FONT: all 27 Hebrew letters"),
    ("SETTINGS",  [(0xdd3795ad, 57433)],
     PARA,                       "LAYOUT: punctuation/parens/digits/Latin, LOGICAL"),
    ("RESUME",    [(0xdd3795ad, 551896), (0xf3759c4e, 25553)],
     visual(PARA),               "LAYOUT: same sentence, VISUAL"),
    ("Arabic",    [(0x82c1dced, 874045)],
     "עברית",                    "the language-menu label itself"),
    ("Yes",       [(0x061dc80e, 506894)],
     "כן",                       "short LOGICAL"),
    ("No",        [(0x061dc80e, 506895)],
     visual("לא"),               "short VISUAL"),
]


def build():
    edits = {}
    for label, keys, val, why in PLAN:
        for k in keys:
            edits[k] = val
    return edits


# the Hebrew-injected font (built by fc5_font.py + FFDConverter -v FC5).  All three font
# banks map arabic -> this ONE .ffd, so patching it covers the whole hijacked UI.
FFD_H = name_hash(r"UI\Common\fonts\Fire\DIN_Mittelschrift_LT_W1G_Arabic.ffd")
XBT_H = name_hash(r"UI\Common\fonts\Fire\DIN_Mittelschrift_LT_W1G_Arabic_1.xbt")
EXTRACT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "extract")


def all_archives():
    """Every .fat under data_final/pc -- the resources we patch live in several, and a
    patch archive OVERRIDES a base one, so every copy has to be replaced."""
    import glob
    out = []
    for q in sorted(glob.glob(os.path.join(PC, "**", "*.fat"), recursive=True)):
        try:
            f = Fat(q)
        except Exception:
            continue
        if f.count:
            out.append((os.path.relpath(q, PC).replace("\\", "/"), f))
    return out


def main(cmd):
    if cmd == "--revert":
        D.revert_all(); return

    edits = build()
    print("proof plan:")
    for label, keys, val, why in PLAN:
        print(f"  {label:10s} -> {val[:46]!r:50s} {why}")
    print(f"\ntotal edits: {len(edits)} keys\n")

    with_font = "--nofont" not in sys.argv
    heb_ffd = heb_xbt = None
    if with_font:
        heb_ffd = open(os.path.join(EXTRACT, "hebrew.ffd"), "rb").read()
        heb_xbt = open(os.path.join(EXTRACT, "hebrew.xbt"), "rb").read()
        print(f"font: hebrew.ffd {len(heb_ffd):,} B   hebrew.xbt {len(heb_xbt):,} B\n")

    payloads = {}          # archive -> {entry_hash: bytes}
    h = name_hash(UI_PATH)
    for arch, fat in all_archives():
        bak = os.path.join(PC, arch) + ".he_backup"
        if os.path.exists(bak):
            print(f"  [!] {arch} already deployed -- revert first"); return
        reps = {}
        e = fat.by_hash.get(h)
        if e:
            raw = fat.read_data(e)          # ALWAYS the pristine bytes, never a deployed slot
            new, applied = O.edit(raw, edits)
            flat = O.flat(O.parse(new)[1])  # re-parse and confirm every edit really landed
            landed = sum(1 for k, v in edits.items() if flat.get(k) == v)
            print(f"  {arch}: text applied={applied} landed={landed}/{len(edits)}  "
                  f"{len(raw):,} -> {len(new):,} B")
            reps[h] = new
        if with_font:
            if FFD_H in fat.by_hash:
                reps[FFD_H] = heb_ffd; print(f"  {arch}: + font .ffd")
            if XBT_H in fat.by_hash:
                reps[XBT_H] = heb_xbt; print(f"  {arch}: + font atlas .xbt")
        if reps:
            payloads[arch] = reps

    if cmd != "--deploy":
        print("\n(dry run -- pass --deploy to write)"); return

    ok = True
    for arch, reps in payloads.items():
        ok &= D.deploy_archive(arch, reps)
    if ok:
        print("\n  DEPLOY OK.")
        print("  Launch Far Cry 5 -> Options -> Language = Arabic (العربية) -> back to the MAIN MENU.")
        print("  Screenshot it.  Expected reading:")
        print("    CONTINUE  = ZZ-FC5-OK-ZZ   -> the patched oasis MOUNTED")
        print("    NEW GAME / LOAD GAME       -> exactly ONE reads  שלום  = that is the bidi mode")
        print("    OPTIONS   = אבגד            -> direction control")
        print("    QUIT      = 27 letters      -> any box/'?' = the font lacks Hebrew")
        print("  revert: python build_proof.py --revert")
    else:
        print("\n  DEPLOY FAILED -- archives reverted.")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main(sys.argv[1] if len(sys.argv) > 1 else "")
