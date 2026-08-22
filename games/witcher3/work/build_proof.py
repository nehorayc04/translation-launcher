"""Phase-6 PROOF (per-file, correct): apply VISUAL Hebrew overrides into the CORRECT content/dlc
ar.w3strings each id actually belongs to (an id lives in ONE specific file; writing it into the
wrong file is ignored by the engine). This is also the real Phase-2 build shape.

Overrides = menu labels + the dialogue batches. Each modified file gets a <file>.he_backup.

Usage:  py build_proof.py --deploy   |   py build_proof.py --revert   |   py build_proof.py (dry-run)
"""
import os, sys, json, glob, shutil
import w3strings as W
from build_menu_proof import MENU, visual_line

GAME = r"D:\Games\The Witcher 3 - Complete Edition"
HERE = os.path.dirname(os.path.abspath(__file__))
BATCHES = ["dialogue_batch_he.json", "opening_batch_he.json"]


def load_overrides():
    ov = {int(k): v for k, v in MENU.items()}
    for fn in BATCHES:
        p = os.path.join(HERE, fn)
        if os.path.exists(p):
            ov.update({int(k): v for k, v in json.load(open(p, encoding="utf-8")).items()})
    return ov


def ar_files():
    return sorted(glob.glob(os.path.join(GAME, "content", "content*", "ar.w3strings")) +
                  glob.glob(os.path.join(GAME, "dlc", "*", "content", "ar.w3strings")))


def revert():
    n = 0
    for p in ar_files():
        bak = p + ".he_backup"
        if os.path.exists(bak):
            shutil.copy2(bak, p)
            n += 1
    print(f"reverted {n} files from .he_backup")


def build(deploy=False):
    ov = load_overrides()
    print(f"total overrides: {len(ov)}")
    total_applied = 0
    for p in ar_files():
        src = p + ".he_backup" if os.path.exists(p + ".he_backup") else p
        d = W.decode(open(src, "rb").read())
        if d["keyid"] != 0:
            continue
        applied = 0
        for e in d["entries"]:
            if e["str_id"] in ov:
                e["text"] = visual_line(ov[e["str_id"]])
                applied += 1
        if applied == 0:
            continue
        rel = os.path.relpath(p, GAME)
        rebuilt = W.encode(d["entries"], d["block2"], version=d["version"])
        # sanity re-decode
        m2 = {e["str_id"]: e["text"] for e in W.decode(rebuilt)["entries"]}
        ok = all(m2.get(sid) == visual_line(ov[sid]) for sid in ov
                 if sid in {e["str_id"] for e in d["entries"]})
        print(f"  {rel:44} applied={applied:>4}  reok={ok}")
        total_applied += applied
        if deploy:
            if not os.path.exists(p + ".he_backup"):
                shutil.copy2(p, p + ".he_backup")
            open(p, "wb").write(rebuilt)
    print(f"TOTAL applied across files: {total_applied}")
    if deploy:
        print("DEPLOYED. Fully CLOSE the game, relaunch, New Game (Text Language=Arabic).")
    else:
        print("(dry-run) re-run with --deploy")


if __name__ == "__main__":
    if "--revert" in sys.argv:
        revert()
    else:
        build(deploy="--deploy" in sys.argv)
