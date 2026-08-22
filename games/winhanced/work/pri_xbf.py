"""Carve the XBF payloads embedded inside Winhanced.pri.

We never have to understand the MRM/PRI container: an XBF declares its own
exact length in its header (0x0c + metadataSize + nodeSize), so every payload
can be located by its magic and cut precisely, then validated by parsing it.
A blob that does not parse is not an XBF and is skipped.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

import xbf

MAGIC = b"XBF\x00"


@dataclass
class Embedded:
    offset: int  # absolute offset in the .pri
    length: int
    obj: xbf.Xbf


def carve(pri_path) -> list[Embedded]:
    data = Path(pri_path).read_bytes()
    out: list[Embedded] = []
    pos = 0
    while True:
        i = data.find(MAGIC, pos)
        if i < 0:
            break
        pos = i + 4
        if i + 12 > len(data):
            continue
        meta, node = struct.unpack_from("<II", data, i + 4)
        total = xbf.META_BASE + meta + node
        if total <= 0 or i + total > len(data) or total > 8 << 20:
            continue
        blob = data[i : i + total]
        try:
            o = _parse_bytes(blob, f"pri@0x{i:x}")
        except Exception:  # noqa: BLE001 -- a false magic hit, not an XBF
            continue
        out.append(Embedded(i, total, o))
    return out


def _parse_bytes(blob: bytes, name: str) -> xbf.Xbf:
    """xbf.parse() works on a path; this is the in-memory twin."""
    import tempfile, os

    fd, tmp = tempfile.mkstemp(suffix=".xbf")
    try:
        os.write(fd, blob)
        os.close(fd)
        o = xbf.parse(tmp)
        o.path = Path(name)
        return o
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


if __name__ == "__main__":
    import sys

    root = Path(r"C:\Program Files\Winhanced")
    pri = root / "Winhanced.pri"
    emb = carve(pri)
    print(f"{pri.name}: {len(emb)} embedded XBF payloads")
    tot = sum(len(e.obj.strings) for e in emb)
    print(f"  strings: {tot}")

    # rebuild each unchanged -> must be byte-identical to the carved slice
    data = pri.read_bytes()
    ok = bad = 0
    for e in emb:
        rebuilt = xbf.build(e.obj, list(e.obj.strings))
        if rebuilt == data[e.offset : e.offset + e.length]:
            ok += 1
        else:
            bad += 1
    print(f"  identity round-trip: {ok} ok / {bad} bad")

    # compare with the loose files on disk
    loose = {}
    for f in sorted(root.rglob("*.xbf")):
        loose[f.name] = set(xbf.parse(f).strings)
    loose_all = set().union(*loose.values()) if loose else set()
    pri_all = set()
    for e in emb:
        pri_all |= set(e.obj.strings)

    print()
    print(f"  distinct strings  loose={len(loose_all)}  pri={len(pri_all)}")
    print(f"  only in pri   : {len(pri_all - loose_all)}")
    print(f"  only in loose : {len(loose_all - pri_all)}")
    only = sorted(s for s in (pri_all - loose_all) if " " in s.strip())
    print(f"\n  sentence-like strings present ONLY in the pri: {len(only)}")
    for s in only[:30]:
        print(f"     {s[:92]!r}")
