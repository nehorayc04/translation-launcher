# -*- coding: utf-8 -*-
"""Refresh release/data/w3strings/ from the freshly-built files in the GAME folder.

build_mod.py --deploy writes the new ar.w3strings straight into the game; the
release staging dir is a separate copy, so pack_release.py would otherwise ship
a stale build. Staging filenames encode the game-relative path with '__'.

    py sync_release_data.py           # report what would change
    py sync_release_data.py --apply
"""
import os, sys, shutil, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
STAGE = os.path.join(HERE, "..", "release", "data", "w3strings")
GAME = os.environ.get("W3_GAME", r"D:\Games\The Witcher 3 - Complete Edition")


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()[:12]


def main(apply_it):
    same = diff = missing = 0
    for fn in sorted(os.listdir(STAGE)):
        if not fn.endswith(".w3strings"):
            continue
        rel = fn.replace("__", os.sep)
        src = os.path.join(GAME, rel)
        dst = os.path.join(STAGE, fn)
        if not os.path.exists(src):
            print(f"  MISSING in game: {rel}")
            missing += 1
            continue
        a, b = sha(src), sha(dst)
        if a == b:
            same += 1
            continue
        diff += 1
        print(f"  UPDATE {fn}  {b} -> {a}  ({os.path.getsize(dst):,} -> {os.path.getsize(src):,} B)")
        if apply_it:
            shutil.copy2(src, dst)
    print(f"\nup-to-date {same}   updated {diff}   missing {missing}")
    if not apply_it and diff:
        print("(dry-run) re-run with --apply")


if __name__ == "__main__":
    main("--apply" in sys.argv)
