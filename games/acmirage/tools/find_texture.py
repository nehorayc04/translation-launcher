#!/usr/bin/env python3
"""
find_texture.py — locate every texture of a given pixel size across a forge, by CONTENT.

Name-based hunting is unreliable in this game: patch forges store their resource names
ENCRYPTED (`name_len & 0x40000000` — 5,226 of 6,581 in `DataPC_extra_patch_01`), so a
name grep silently returns zero hits there and reads as "nothing to see". The same
asset also appears under DIFFERENT resource ids in different forges, so an id sweep is
not conclusive either. Only decoding each resource and measuring its texture answers it.

    python find_texture.py <forge> [--w 1072] [--h 600]
"""
import argparse
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "acshadows", "tools"))

from mirage_forge import Forge  # noqa: E402
import acs_cfd  # noqa: E402
from mirage_texdump import find_dims  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

TEX = {2729961751: "TextureMap", 2560476850: "TextureMapSpec"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("forge")
    ap.add_argument("--w", type=int, default=1072)
    ap.add_argument("--h", type=int, default=0, help="0 = any height")
    a = ap.parse_args()

    fg = Forge(a.forge)
    od = acs_cfd._oodle()
    base = os.path.basename(a.forge)
    tex = hits = bad = 0
    for i, e in enumerate(fg.entries):
        try:
            cfds, _ = acs_cfd.decode_resource(fg.read(e), od)
            if not cfds:
                bad += 1
                continue
            c = cfds[-1][0]
        except Exception:
            bad += 1
            continue
        if len(c) < 16:
            continue
        cls, _size, nlen = struct.unpack_from("<Iii", c, 0)
        if cls not in TEX:
            continue
        tex += 1
        d = find_dims(c)
        if not d or d[0] != a.w or (a.h and d[1] != a.h):
            continue
        nm = ("<encrypted>" if nlen & 0x40000000
              else c[12:12 + (nlen & 0xFFFF)].decode("utf-8", "replace"))
        print(f"HIT {base} id={e.id} {TEX[cls]} {d[0]}x{d[1]} "
              f"content={len(c):,} name={nm}", flush=True)
        hits += 1
    fg.f.close()
    print(f"## {base}: entries={len(fg.entries):,} textures={tex:,} "
          f"hits={hits} undecodable={bad}", flush=True)


if __name__ == "__main__":
    main()
