#!/usr/bin/env python3
"""
acs_forge_probe.py — read-only inspector for Assassin's Creed Shadows
Ubisoft "scimitar" .forge archives (Anvil engine).

This tool NEVER writes to a forge. It exists to characterize the format and
to LOCATE which archive holds the localization (oasis string) data, so the
real extraction/repacking can be aimed correctly once a version-42 capable
forge tool is in place.

Empirically confirmed on this machine (DataPC_*.forge):
    magic   : b"scimitar\\x00"  (offset 0, 9 bytes)
    version : uint32 LE @ offset 9  ==  0x2A  (42)   <-- AC Shadows generation
    (older AC titles use lower version numbers; tools key on this number.)

USAGE
    python acs_forge_probe.py header  "<forge>"
        Print magic, version, and a labeled hexdump of the first 128 bytes.

    python acs_forge_probe.py strings "<forge>" [--pattern oasis,loc,ar-,en-US]
                                                 [--utf16] [--ascii]
                                                 [--max-mb 64] [--limit 200]
        Read-only scan for printable ASCII and/or UTF-16LE token runs whose
        text matches any comma-separated --pattern (case-insensitive). Used to
        find the localization container ("oasis"/"loc"/language codes) without
        a full extractor. Multi-GB forges are scanned only up to --max-mb from
        the start AND --max-mb from the end (the table-of-contents / string
        blobs cluster at the edges) unless --max-mb 0 (whole file).

    python acs_forge_probe.py survey "<game_dir>"
        Run a quick header check on every .forge in a directory and print a
        one-line magic/version summary per archive.

This is groundwork, not the final pipeline — see ../PIPELINE.md.
"""
import sys
import os
import struct
import argparse

MAGIC = b"scimitar\x00"


def read_header(path):
    with open(path, "rb") as f:
        head = f.read(128)
    if head[:9] != MAGIC:
        return {"ok": False, "magic": head[:9], "raw": head}
    version = struct.unpack_from("<I", head, 9)[0]
    return {"ok": True, "magic": head[:8].decode("ascii"), "version": version, "raw": head}


def cmd_header(path):
    info = read_header(path)
    size = os.path.getsize(path)
    print(f"file    : {path}")
    print(f"size    : {size:,} bytes ({size/1024/1024/1024:.2f} GiB)")
    if not info["ok"]:
        print(f"magic   : {info['magic']!r}  <-- NOT a scimitar forge")
        return 1
    print(f"magic   : {info['magic']!r}")
    print(f"version : {info['version']}  (0x{info['version']:X})")
    print("hexdump (first 128 bytes):")
    raw = info["raw"]
    for off in range(0, len(raw), 16):
        chunk = raw[off:off + 16]
        hexs = " ".join(f"{b:02x}" for b in chunk)
        text = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        print(f"  {off:04x}: {hexs:<47}  {text}")
    return 0


def _iter_windows(path, max_mb):
    """Yield (file_offset, bytes) windows. If max_mb>0, only head+tail."""
    size = os.path.getsize(path)
    cap = max_mb * 1024 * 1024 if max_mb else 0
    with open(path, "rb") as f:
        if cap == 0 or size <= 2 * cap:
            data = f.read()
            yield 0, data
            return
        head = f.read(cap)
        yield 0, head
        f.seek(size - cap)
        tail = f.read(cap)
        yield size - cap, tail


def _ascii_runs(data, base, min_len=4):
    run = bytearray()
    start = 0
    for i, b in enumerate(data):
        if 32 <= b < 127:
            if not run:
                start = i
            run.append(b)
        else:
            if len(run) >= min_len:
                yield base + start, run.decode("ascii", "replace")
            run = bytearray()
    if len(run) >= min_len:
        yield base + start, run.decode("ascii", "replace")


def _utf16_runs(data, base, min_len=4):
    # printable UTF-16LE: ascii byte followed by 0x00, repeated
    run = []
    start = 0
    i = 0
    n = len(data) - 1
    while i < n:
        lo, hi = data[i], data[i + 1]
        if hi == 0 and 32 <= lo < 127:
            if not run:
                start = i
            run.append(chr(lo))
            i += 2
        else:
            if len(run) >= min_len:
                yield base + start, "".join(run)
            run = []
            i += 1
    if len(run) >= min_len:
        yield base + start, "".join(run)


def cmd_strings(path, patterns, utf16, ascii_, max_mb, limit):
    pats = [p.strip().lower() for p in patterns.split(",") if p.strip()] if patterns else []

    def match(s):
        if not pats:
            return True
        sl = s.lower()
        return any(p in sl for p in pats)

    found = 0
    seen = set()
    for base, data in _iter_windows(path, max_mb):
        gens = []
        if ascii_:
            gens.append(("A", _ascii_runs(data, base)))
        if utf16:
            gens.append(("U", _utf16_runs(data, base)))
        for tag, gen in gens:
            for off, s in gen:
                if match(s) and (tag, s) not in seen:
                    seen.add((tag, s))
                    print(f"  [{tag}] @0x{off:09x}  {s[:160]}")
                    found += 1
                    if found >= limit:
                        print(f"  ... (limit {limit} reached)")
                        return 0
    print(f"  ({found} match(es))")
    return 0


def cmd_survey(game_dir):
    forges = sorted(f for f in os.listdir(game_dir) if f.lower().endswith(".forge"))
    print(f"{'version':>7}  {'size (GiB)':>10}  name")
    versions = {}
    for name in forges:
        p = os.path.join(game_dir, name)
        info = read_header(p)
        size = os.path.getsize(p) / 1024 / 1024 / 1024
        v = info.get("version") if info["ok"] else "NOT-FORGE"
        versions[v] = versions.get(v, 0) + 1
        print(f"{str(v):>7}  {size:>10.2f}  {name}")
    print(f"\nversion histogram: {versions}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Read-only AC Shadows scimitar .forge probe")
    sub = ap.add_subparsers(dest="cmd", required=True)

    h = sub.add_parser("header")
    h.add_argument("forge")

    s = sub.add_parser("strings")
    s.add_argument("forge")
    s.add_argument("--pattern", default="oasis,loc,ar-,en-US,language,stringtable,localization")
    s.add_argument("--utf16", action="store_true", default=True)
    s.add_argument("--no-utf16", dest="utf16", action="store_false")
    s.add_argument("--ascii", action="store_true", default=True)
    s.add_argument("--no-ascii", dest="ascii", action="store_false")
    s.add_argument("--max-mb", type=int, default=64)
    s.add_argument("--limit", type=int, default=200)

    sv = sub.add_parser("survey")
    sv.add_argument("game_dir")

    a = ap.parse_args()
    if a.cmd == "header":
        return cmd_header(a.forge)
    if a.cmd == "strings":
        return cmd_strings(a.forge, a.pattern, a.utf16, a.ascii, a.max_mb, a.limit)
    if a.cmd == "survey":
        return cmd_survey(a.game_dir)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
