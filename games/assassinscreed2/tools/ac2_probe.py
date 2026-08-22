#!/usr/bin/env python3
"""
Read-only structure probe for AC2 `.forge` archives — scans for resource-name
substrings and hex-dumps regions. Companion to ac2_forge.py for exploring an
unknown forge (which languages/fonts it carries) without extracting.

    python ac2_probe.py <forge> [needle ...]

Default needles cover localization + fonts. Pure stdlib, UTF-8 stdout.
"""
import sys
import os

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DEFAULT_NEEDLES = ["LocalizationPackage", "Subtitles", "CharacterSet",
                   "MapDesc", "_Latin", "Numbers", "Arabic", "Hebrew", "ar-ar"]


def scan(path, needles, cap=40):
    found = {n: [] for n in needles}
    bn = [(n, n.encode("latin1")) for n in needles]
    with open(path, "rb") as f:
        data = f.read()
    for n, b in bn:
        start = 0
        while len(found[n]) < cap:
            i = data.find(b, start)
            if i < 0:
                break
            ctx = bytes(c if 32 <= c < 127 else 0x2e
                        for c in data[max(0, i - 1):i + 70]).decode("latin1")
            found[n].append((i, ctx))
            start = i + 1
    return found


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    path = argv[1]
    needles = argv[2:] or DEFAULT_NEEDLES
    print(f"### {os.path.basename(path)}  size={os.path.getsize(path):,}")
    res = scan(path, needles)
    for n in needles:
        hits = res[n]
        print(f"\n[{n}] hits={len(hits)}")
        for off, ctx in hits[:10]:
            print(f"  0x{off:08x}: {ctx!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
