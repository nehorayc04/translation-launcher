#!/usr/bin/env python3
"""Deploy the David font by an in-place DELTA-0 splice into r4gui.bundle:
snappy-compress the new fonts_ar.redswf, pad to the original entry zsize, overwrite the entry's
data region. Bundle size + all TOC metadata (incl. hashes) stay byte-identical. Reversible via backup.
Usage:  py deploy_font_bundle.py           (deploy)
        py deploy_font_bundle.py --revert   (restore r4gui.bundle from backup)
"""
import os, sys, struct, shutil
import potato_bundle as P

GAME = r"D:\Games\The Witcher 3 - Complete Edition"
BUNDLE = os.path.join(GAME, "content", "content0", "bundles", "r4gui.bundle")
BAK = BUNDLE + ".he_backup"
HERE = os.path.dirname(os.path.abspath(__file__))
NEW = os.path.join(HERE, "fonts", "fonts_ar_david.redswf")


def revert():
    if os.path.exists(BAK):
        shutil.copy2(BAK, BUNDLE)
        print("reverted r4gui.bundle from backup")
    else:
        print("no backup found")


def deploy():
    new = open(NEW, "rb").read()
    d, ents = P.list_entries(BUNDLE)
    e = [x for x in ents if x["name"].endswith("fonts_ar.redswf")][0]
    comp = P.snappy_compress(new)
    assert P.snappy_decompress(comp) == new, "snappy roundtrip failed"
    if len(comp) > e["zsize"]:
        raise SystemExit(f"compressed {len(comp)} > entry zsize {e['zsize']} — cannot delta-0 splice")
    payload = comp + b"\x00" * (e["zsize"] - len(comp))   # pad to exact zsize (inflate ignores trailer)
    assert len(payload) == e["zsize"]
    if not os.path.exists(BAK):
        shutil.copy2(BUNDLE, BAK)
        print(f"backed up -> {BAK}")
    with open(BUNDLE, "r+b") as f:
        f.seek(e["offs"])
        f.write(payload)
    print(f"SPLICED David fonts_ar.redswf into r4gui.bundle @off={e['offs']} "
          f"({len(comp)} snappy + {e['zsize']-len(comp)} pad = {e['zsize']} bytes, bundle size unchanged)")
    print("Fully restart the game (Text Language = Arabic) and check the Hebrew font.")


if __name__ == "__main__":
    if "--revert" in sys.argv:
        revert()
    else:
        deploy()
