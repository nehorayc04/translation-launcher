#!/usr/bin/env python3
"""
dump_texture_names.py — full texture inventory for a forge, as a greppable TSV.

Built after a targeted `_AR` name filter missed the asset that was actually on screen:
a pattern search only finds the naming convention you guessed. Dumping every texture
name once costs the same scan and can then be grepped a hundred different ways for free.

Fast: the name lives at content offset 12, so only the FIRST block of the LAST CFD is
decompressed — never the whole texture.

    python dump_texture_names.py <forge> [...] > inventory.tsv
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
from find_ar_textures import head_of_last_cfd, TEX  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("forges", nargs="+")
    ap.add_argument("--all-classes", action="store_true",
                    help="dump every resource, not only textures")
    a = ap.parse_args()
    od = acs_cfd._oodle()
    for path in a.forges:
        fg = Forge(path)
        base = os.path.basename(path)
        n_tex = n_enc = 0
        for i, e in enumerate(fg.entries):
            try:
                head = head_of_last_cfd(fg.read(e), od)
            except Exception:
                continue
            if len(head) < 16:
                continue
            cls, _s, nlen = struct.unpack_from("<Iii", head, 0)
            is_tex = cls in TEX
            if not (is_tex or a.all_classes):
                continue
            if is_tex:
                n_tex += 1
            if nlen & 0x40000000:
                n_enc += 1
                name = "<ENCRYPTED>"
            else:
                name = head[12:12 + (nlen & 0xFFFF)].decode("utf-8", "replace")
            print(f"{base}\t{e.id}\t{e.size}\t{TEX.get(cls, cls)}\t{name}")
            if (i + 1) % 5000 == 0:
                print(f"   … {base} {i+1:,}/{len(fg.entries):,}", file=sys.stderr, flush=True)
        fg.f.close()
        print(f"## {base}: entries={len(fg.entries):,} textures={n_tex:,} "
              f"encrypted-name={n_enc:,}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
