#!/usr/bin/env python3
"""
find_ar_textures.py — list every TEXTURE whose name marks it as the ARABIC variant.

Fast, because it never decompresses a whole texture: a resource's name sits at content
offset 12, i.e. inside the FIRST block of the LAST CFD, so the CFD block table is walked
to find that block and only that one is decompressed. Decoding a 600 KB texture just to
read its name is what made the earlier sweeps feel impossible.

    python find_ar_textures.py <forge> [<forge> ...]
"""
import argparse
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "acshadows", "tools"))

from mirage_forge import Forge  # noqa: E402
import acs_cfd  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

TEX = {2729961751: "TextureMap", 2560476850: "TextureMapSpec"}
# `_AR` / `_Arabic` as a whole token — not the "ar" inside "Target" or "Arch".
AR_RE = re.compile(r"(?<![A-Za-z0-9])(AR|Arabic|ARABIC|arb|ARB)(?![A-Za-z0-9])")


def head_of_last_cfd(blob, oodle, want=4096):
    """First `want` bytes of the resource CONTENT, decompressing one block at most."""
    off, n, last = 0, len(blob), None
    while off + 8 <= n and struct.unpack_from("<Q", blob, off)[0] == acs_cfd.MAGIC:
        count = struct.unpack_from("<i", blob, off + 15)[0]
        bi = off + 19
        blocks = [struct.unpack_from("<ii", blob, bi + 8 * i) for i in range(count)]
        p = bi + count * 8
        last = (p, blocks)
        for _u, c in blocks:
            p += 4 + c
        off = p
    if not last:
        return b""
    p, blocks = last
    if not blocks:
        return b""
    uncomp, comp = blocks[0]
    data = blob[p + 4:p + 4 + comp]
    return (data if comp == uncomp else oodle.decompress(data, uncomp))[:want]


def scan(path, oodle):
    fg = Forge(path)
    base = os.path.basename(path)
    hits, enc, tex = [], 0, 0
    for i, e in enumerate(fg.entries):
        try:
            head = head_of_last_cfd(fg.read(e), oodle)
        except Exception:
            continue
        if len(head) < 16:
            continue
        cls, _size, nlen = struct.unpack_from("<Iii", head, 0)
        if cls not in TEX:
            continue
        tex += 1
        if nlen & 0x40000000:                     # patch forges encrypt the NAME field
            enc += 1
            continue
        name = head[12:12 + (nlen & 0xFFFF)].decode("utf-8", "replace")
        if AR_RE.search(name):
            hits.append((e.id, e.size, name))
            print(f"  {base}  id={e.id:<16} {e.size:>10,}B  {name}", flush=True)
        if (i + 1) % 5000 == 0:
            print(f"   … {i+1:,}/{len(fg.entries):,}  textures={tex} hits={len(hits)}",
                  file=sys.stderr, flush=True)
    fg.f.close()
    print(f"## {base}: entries={len(fg.entries):,} textures={tex:,} "
          f"encrypted-name={enc:,} ARABIC={len(hits)}")
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("forges", nargs="+")
    a = ap.parse_args()
    od = acs_cfd._oodle()
    total = []
    for p in a.forges:
        total += [(p,) + h for h in scan(p, od)]
    print(f"\n=== {len(total)} Arabic texture(s) total ===")
    for p, rid, size, name in total:
        print(f"{os.path.basename(p)}\t{rid}\t{size}\t{name}")


if __name__ == "__main__":
    main()
