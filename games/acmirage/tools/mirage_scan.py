#!/usr/bin/env python3
"""
mirage_scan.py — walk an AC Mirage v29 forge, decode each resource's CFD chain
just far enough to read its Anvil object header, and report class + NAME.

Object header (after CFD decompression), verified on real Mirage resources:
    u32  class_hash   (== zlib.crc32(ClassName), e.g. LocalizationPackage=1849465967)
    i32  size
    i32  name_len
    char[name_len] name        (e.g. "ACK_Fight_AgileBrawler_MediumHurt_Rightward")

v29 forges carry NO name table (AnvilToolkit does a hash->name DB lookup), so this
CONTENT scan is how you locate a resource. Only the FIRST Oodle block of the object
CFD is decompressed, which keeps a full-forge sweep cheap.

    python mirage_scan.py <forge> classes            # class histogram
    python mirage_scan.py <forge> find <class_hash>  # list resources of a class
    python mirage_scan.py <forge> names --grep loc
"""
import argparse
import os
import struct
import sys
import zlib
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "acshadows", "tools"))

from mirage_forge import Forge  # noqa: E402
import acs_cfd  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

KNOWN = {
    zlib.crc32(n.encode()): n
    for n in (
        "LocalizationPackage", "StringTable", "CompressedFileData", "DataFile",
        "TextureMap", "EntityBuilder", "SoundBank", "FireData", "Mesh",
        "Material", "AnimationClip", "UIScreen", "Font", "FontDescriptor",
    )
}


def object_header(buf, oodle, want_bytes=64):
    """Decode CFDs at buf[0] until we have >= want_bytes of the OBJECT CFD."""
    off = 0
    n = 0
    while off < len(buf) - 8 and struct.unpack_from("<Q", buf, off)[0] == acs_cfd.MAGIC:
        count = struct.unpack_from("<i", buf, off + 15)[0]
        bi = off + 19
        blocks = [struct.unpack_from("<ii", buf, bi + 8 * i) for i in range(count)]
        p = bi + count * 8
        if n == 0:                      # CFD0 = tiny meta block, skip its payload
            for uncomp, comp in blocks:
                p += 4 + comp
            off = p
            n += 1
            continue
        uncomp, comp = blocks[0]        # only the FIRST block of the object CFD
        p += 4
        cdata = buf[p:p + comp]
        data = cdata if comp == uncomp else oodle.decompress(cdata, uncomp)
        return data[:max(want_bytes, 4096)]
    return None


def parse_header(data):
    if not data or len(data) < 12:
        return None
    cls, size, nlen = struct.unpack_from("<Iii", data, 0)
    if not (0 <= nlen <= 512) or 12 + nlen > len(data):
        return cls, size, None
    name = data[12:12 + nlen].decode("utf-8", "replace")
    return cls, size, name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("forge")
    ap.add_argument("cmd", choices=["classes", "find", "names"])
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--grep")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    fg = Forge(a.forge)
    od = acs_cfd._oodle()
    entries = fg.entries[: a.limit] if a.limit else fg.entries

    hist = Counter()
    rows = []
    errors = 0
    for i, e in enumerate(entries):
        try:
            hdr = parse_header(object_header(fg.read(e), od))
        except Exception:
            errors += 1
            continue
        if not hdr:
            errors += 1
            continue
        cls, size, name = hdr
        hist[cls] += 1
        rows.append((e, cls, name))
        if (i + 1) % 5000 == 0:
            print(f"  ... {i+1:,}/{len(entries):,}", file=sys.stderr)

    if a.cmd == "classes":
        print(f"# {os.path.basename(a.forge)}  entries={len(entries):,}  undecodable={errors}")
        for cls, n in hist.most_common(40):
            print(f"  {cls:<12} {KNOWN.get(cls,''):<22} {n:>8,}")
    elif a.cmd == "find":
        want = int(a.arg)
        for e, cls, name in rows:
            if cls == want:
                print(f"  #{e.index:<6} id={e.id:<22} size={e.size:>10,}  {name}")
    elif a.cmd == "names":
        pat = (a.grep or "").lower()
        for e, cls, name in rows:
            if name and pat in name.lower():
                print(f"  #{e.index:<6} id={e.id:<22} cls={cls:<12} size={e.size:>10,}  {name}")


if __name__ == "__main__":
    main()
