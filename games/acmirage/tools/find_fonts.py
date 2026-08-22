#!/usr/bin/env python3
"""
find_fonts.py — hunt for the font AC Mirage actually renders with.

The menu proof (2026-07-22) showed Latin + Arabic render but Hebrew is tofu, so an
Arabic-capable face IS loaded — it is just not a named forge resource ("Font" grep
finds only DebugFontTexture / SDR_UI_WorldMap_FogFont) and the VMProtect-packed exe
carries no sfnt.

This decompresses EVERY resource of a forge and looks for a real font inside:
  * sfnt   \\x00\\x01\\x00\\x00  (TrueType)     — validated by parsing the table directory
  * OTTO   (CFF/OpenType)
  * ttcf   (TrueType collection)
  * wOFF / wOF2
A hit is only reported when the table directory is self-consistent, because the sfnt
magic matches enormous amounts of random binary (the AC Unity lesson).

    python find_fonts.py <forge> [--limit N]
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

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

MAGICS = [b"\x00\x01\x00\x00", b"OTTO", b"ttcf", b"wOFF", b"wOF2"]
KNOWN_TABLES = {b"cmap", b"glyf", b"head", b"hhea", b"hmtx", b"loca", b"maxp",
                b"name", b"post", b"OS/2", b"CFF ", b"GSUB", b"GPOS"}


def valid_sfnt(buf, off):
    """A real sfnt has a sane numTables and recognisable 4-byte table tags."""
    if off + 12 > len(buf):
        return None
    num = struct.unpack_from(">H", buf, off + 4)[0]
    if not (4 <= num <= 64):
        return None
    if off + 12 + num * 16 > len(buf):
        return None
    tags = [buf[off + 12 + i * 16: off + 16 + i * 16] for i in range(num)]
    hits = sum(1 for t in tags if t in KNOWN_TABLES)
    if hits < 4:
        return None
    end = 0
    for i in range(num):
        o, l = struct.unpack_from(">II", buf, off + 12 + i * 16 + 8)
        end = max(end, o + l)
    return {"tables": [t.decode("latin1") for t in tags], "n": num, "end": end}


def scan_resource(data):
    out = []
    for m in MAGICS:
        start = 0
        while True:
            i = data.find(m, start)
            if i < 0:
                break
            start = i + 1
            if m == b"\x00\x01\x00\x00":
                v = valid_sfnt(data, i)
                if v:
                    out.append((i, "TTF", v))
            else:
                out.append((i, m.decode("latin1"), None))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("forge")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    fg = Forge(a.forge)
    od = acs_cfd._oodle()
    entries = fg.entries[: a.limit] if a.limit else fg.entries
    print(f"# {os.path.basename(a.forge)}  {len(entries):,} resources", flush=True)
    found = err = 0
    for i, e in enumerate(entries):
        try:
            cfds, _ = acs_cfd.decode_resource(fg.read(e), od)
        except Exception:
            err += 1
            continue
        for data, _ci in cfds:
            for off, kind, v in scan_resource(data):
                cls = struct.unpack_from("<I", data, 0)[0] if len(data) >= 4 else 0
                nlen = struct.unpack_from("<i", data, 8)[0] if len(data) >= 12 else 0
                name = ""
                if 0 < nlen <= 512 and 12 + nlen <= len(data):
                    name = data[12:12 + nlen].decode("utf-8", "replace")
                print(f"  HIT #{e.index} id={e.id} cls={cls} {kind}@{off} "
                      f"{('tables=' + ','.join(v['tables'][:8])) if v else ''}  {name}",
                      flush=True)
                found += 1
        if (i + 1) % 2000 == 0:
            print(f"  ... {i+1:,}/{len(entries):,}  hits={found}", file=sys.stderr, flush=True)
    print(f"# done: {found} font hit(s), {err} undecodable")


if __name__ == "__main__":
    main()
