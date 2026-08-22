#!/usr/bin/env python3
"""
sweep_loc.py — sweep EVERY AC Mirage forge for LocalizationPackage resources and
report which forge holds the real text, plus whether each copy is plaintext or
carries the patch-forge encryption flag (name_len & 0x40000000).

    python sweep_loc.py <game_dir> [--out report.txt]
"""
import argparse
import os
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "acshadows", "tools"))

from mirage_forge import Forge  # noqa: E402
from mirage_scan import object_header  # noqa: E402
import acs_cfd  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

LOC_CLASS = 1849465967
ENC_FLAG = 0x40000000


def sweep(path, od, out):
    t0 = time.time()
    try:
        fg = Forge(path)
    except Exception as ex:
        print(f"!! {os.path.basename(path)}: {ex}", file=out, flush=True)
        return
    found = []
    enc = 0
    for e in fg.entries:
        try:
            d = object_header(fg.read(e), od, want_bytes=256)
        except Exception:
            continue
        if not d or len(d) < 12:
            continue
        cls, size, nlen = struct.unpack_from("<Iii", d, 0)
        if cls != LOC_CLASS:
            continue
        flagged = bool(nlen & ENC_FLAG)
        enc += flagged
        n = nlen & 0xFFFF
        name = None
        if not flagged and 0 < n <= 512 and 12 + n <= len(d):
            name = d[12:12 + n].decode("utf-8", "replace")
        found.append((e, size, flagged, name))
    dt = time.time() - t0
    print(f"\n##### {os.path.basename(path)}  entries={len(fg.entries):,}  "
          f"loc={len(found)}  encrypted={enc}  ({dt:.0f}s)", file=out, flush=True)
    for e, size, flagged, name in found:
        tag = "ENC " if flagged else "    "
        print(f"  {tag}#{e.index:<7} id={e.id:<22} raw={size:>10,}  {name or ''}",
              file=out, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("game_dir")
    ap.add_argument("--out")
    a = ap.parse_args()

    forges = sorted(
        (os.path.join(a.game_dir, f) for f in os.listdir(a.game_dir) if f.endswith(".forge")),
        key=os.path.getsize,
    )
    od = acs_cfd._oodle()
    out = open(a.out, "w", encoding="utf-8") if a.out else sys.stdout
    print(f"# sweeping {len(forges)} forges", file=out, flush=True)
    for p in forges:
        sweep(p, od, out)
    print("\n# DONE", file=out, flush=True)


if __name__ == "__main__":
    main()
