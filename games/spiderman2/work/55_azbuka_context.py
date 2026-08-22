"""Dump context around every 'AzbukaPro' / font-name hit in d/userinterface
and d/config — find the real font asset names + any fallback config that
lists fonts per script."""
import os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")


def hits(buf, tok):
    i = 0
    while True:
        j = buf.find(tok, i)
        if j < 0:
            break
        yield j
        i = j + 1


def readable_around(buf, j, back=80, fwd=160):
    s = buf[max(0, j-back):j+fwd]
    # split on NULs, show printable tokens >=3
    out = []
    for m in re.finditer(rb"[ -~]{3,}", s):
        out.append(m.group().decode("latin-1"))
    return out


for arch, tokens in (("config", (b"AzbukaPro", b"fallback", b"font", b".ttf", b".otf")),
                     ("userinterface", (b"AzbukaPro", b"MagicSpell"))):
    path = os.path.join(GAME, "d", arch)
    buf = open(path, "rb").read()
    print("\n" + "#" * 72)
    print(f"# d/{arch}  ({len(buf):,} bytes)")
    print("#" * 72)
    for tok in tokens:
        offs = list(hits(buf, tok))
        print(f"\n=== token {tok!r}: {len(offs)} hits ===")
        # cluster: show first 6 unique-ish contexts
        shown = 0
        last = -9999
        for j in offs:
            if j - last < 200:   # same cluster, skip
                last = j
                continue
            last = j
            toks = readable_around(buf, j)
            print(f"  [{j:>9}] {toks}")
            shown += 1
            if shown >= 8:
                print(f"  ... ({len(offs)} total)")
                break
