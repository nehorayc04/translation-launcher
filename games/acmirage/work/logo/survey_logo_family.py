#!/usr/bin/env python3
"""
survey_logo_family.py — dump the whole per-language logo family + check patch shadowing.

Two questions before touching anything:
  1. what does the LATIN variant look like (that is the target look), and
  2. does a patch forge carry the same resource ids (§8e: the patch wins).
"""
import os
import struct
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, "..", "..", "tools")
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "acshadows", "tools"))

from mirage_forge import Forge  # noqa: E402
import acs_cfd  # noqa: E402
from find_ar_textures import head_of_last_cfd, TEX  # noqa: E402
from find_logo import bands_of, dims_any  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

GAME = r"F:/Game Lab/Assassin's Creed Mirage"
EXTRA = os.path.join(GAME, "DataPC_extra.forge")
AR_IDS = [2181436741074, 2181436741075, 2181436742028,
          2141045950540, 2141045950541, 2141045950553]
PATCHES = ["DataPC_extra_patch_01.forge", "DataPC_patch_01.forge",
           "DataPC_TitleScreen_patch_01.forge"]


def main():
    od = acs_cfd._oodle()

    print("### patch-forge shadowing check")
    for p in PATCHES:
        path = os.path.join(GAME, p)
        if not os.path.exists(path):
            continue
        fg = Forge(path)
        ids = {e.id for e in fg.entries}
        fg.f.close()
        hit = sorted(set(AR_IDS) & ids)
        print(f"  {p:<34} {len(ids):>7,} entries  -> shadows {hit if hit else 'NONE'}")

    print("\n### the logo family in DataPC_extra.forge")
    fg = Forge(EXTRA)
    fam = []
    for e in fg.entries:
        try:
            head = head_of_last_cfd(fg.read(e), od)
        except Exception:
            continue
        if len(head) < 16:
            continue
        cls, _s, nlen = struct.unpack_from("<Iii", head, 0)
        if cls not in TEX or (nlen & 0x40000000):
            continue
        name = head[12:12 + (nlen & 0xFFFF)].decode("utf-8", "replace")
        if "PressStart" in name or "TitleReveal" in name:
            fam.append((name, e))
    print(f"  {len(fam)} member(s)")

    for name, e in sorted(fam):
        try:
            cfds, _ = acs_cfd.decode_resource(fg.read(e), od)
            c = cfds[-1][0]
        except Exception as ex:
            print(f"  {name:<58} decode failed: {type(ex).__name__}")
            continue
        d = dims_any(c)
        if not d:
            print(f"  {name:<58} (no dims)")
            continue
        w, h, hdr = d
        try:
            img = np.flipud(np.array(
                Image.frombytes("RGBA", (w, h), c[hdr:hdr + w * h], "bcn", (7,))))
        except Exception:
            print(f"  {name:<58} {w}x{h} (decode err)")
            continue
        b = bands_of(img[..., 3])
        ink = img[..., 3] > 200
        rgb = img[..., :3][ink].mean(axis=0).round(0) if ink.any() else None
        print(f"  {name:<58} {w}x{h:<5} bands={b} ink_rgb={rgb}")
    fg.f.close()


if __name__ == "__main__":
    main()
