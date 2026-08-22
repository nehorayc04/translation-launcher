#!/usr/bin/env python3
r"""
aco_scan.py — locate AC Odyssey resources by CONTENT (ScimitarClass hash).

v28 forges carry NO name table, so a resource is found by the u32 class hash at
content[0] (= crc32 of the class name, e.g. LocalizationPackage = 1849465967).

Cheap by construction: `aco_cfd.peek_class` inflates ONLY the first block of the
object CFD, so a multi-GB forge is scanned without decompressing it.

    python aco_scan.py hist  <forge> [--limit N]          # class histogram
    python aco_scan.py find  <forge> <class_hash|name>    # entries of that class
    python aco_scan.py sweep <class_hash|name> [forges…]  # all forges in the game dir
"""
import argparse
import os
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import aco_forge                                      # noqa: E402
import aco_cfd                                        # noqa: E402

GAME = os.environ.get("ACO_GAME", r"F:\Games\Assassin's Creed Odyssey")

KNOWN = {
    zlib.crc32(b"LocalizationPackage"): "LocalizationPackage",
    zlib.crc32(b"TextureMap"): "TextureMap",
    zlib.crc32(b"TextureMapSpec"): "TextureMapSpec",
    zlib.crc32(b"FontFile"): "FontFile",
    zlib.crc32(b"FireData"): "FireData",
    zlib.crc32(b"EntityBuilder"): "EntityBuilder",
}


def resolve(token):
    if token.isdigit():
        return int(token)
    return zlib.crc32(token.encode())


def scan(path, want=None, quiet=False):
    """Yield (entry, class_hash). If want is set, only matching entries."""
    fg = aco_forge.Forge(path)
    od = aco_cfd.oodle()
    hits, hist = [], {}
    for e in fg.entries:
        try:
            blob = fg.read(e)
            h = aco_cfd.peek_class(blob, od)
        except Exception:
            h = None
        if h is None:
            continue
        hist[h] = hist.get(h, 0) + 1
        if want is not None and h == want:
            hits.append(e)
            if not quiet:
                print(f"  HIT {os.path.basename(path)} #{e.index} id={e.id} "
                      f"size={e.size:,}")
    fg.close()
    return hits, hist


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["hist", "find", "sweep"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--limit", type=int, default=30)
    a = ap.parse_args()

    if a.cmd == "hist":
        _, hist = scan(a.args[0], None)
        for h, n in sorted(hist.items(), key=lambda x: -x[1])[: a.limit]:
            print(f"  {h:>12}  {n:>6}  {KNOWN.get(h, '')}")
        return

    if a.cmd == "find":
        want = resolve(a.args[1])
        print(f"looking for class {want} ({KNOWN.get(want, '?')}) in {a.args[0]}")
        hits, _ = scan(a.args[0], want)
        print(f"total: {len(hits)}")
        return

    if a.cmd == "sweep":
        want = resolve(a.args[0])
        forges = a.args[1:] or sorted(
            os.path.join(GAME, f) for f in os.listdir(GAME) if f.endswith(".forge"))
        print(f"sweeping {len(forges)} forges for class {want} "
              f"({KNOWN.get(want, '?')})")
        total = 0
        for p in forges:
            try:
                hits, _ = scan(p, want)
            except Exception as ex:
                print(f"  [skip] {os.path.basename(p)}: {type(ex).__name__}: {ex}")
                continue
            if hits:
                print(f"  == {os.path.basename(p)}: {len(hits)} hit(s)")
            total += len(hits)
        print(f"TOTAL {total}")


if __name__ == "__main__":
    main()
