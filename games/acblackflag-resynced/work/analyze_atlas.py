#!/usr/bin/env python3
"""Offline structural analysis of the cached 0xcbd4939a font-atlas resources
(work/atlas/*.bin). Goal: find (a) which atlas serves ARABIC, (b) the glyph-metrics
table (codepoint -> atlas rect), (c) where the texture payload starts.

Heuristics:
 * scan for ASCENDING runs of u16/u32 values inside Unicode ranges (a codepoint table),
 * detect fixed-stride record arrays around those runs,
 * locate the big high-entropy tail (the compressed/BCn texture payload),
 * report which Unicode blocks each atlas covers -> identifies Arabic vs Latin vs CJK.
"""
import os, sys, json, struct
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ATL = os.path.join(HERE, "atlas")

BLOCKS = [
    ("Latin", 0x0020, 0x024F),
    ("Greek", 0x0370, 0x03FF),
    ("Cyrillic", 0x0400, 0x04FF),
    ("Hebrew", 0x0590, 0x05FF),
    ("Arabic", 0x0600, 0x06FF),
    ("Thai", 0x0E00, 0x0E7F),
    ("CJK", 0x4E00, 0x9FFF),
    ("Hangul", 0xAC00, 0xD7AF),
    ("ArabicPresA", 0xFB50, 0xFDFF),
    ("ArabicPresB", 0xFE70, 0xFEFF),
]


def block_of(cp):
    for name, lo, hi in BLOCKS:
        if lo <= cp <= hi:
            return name
    return None


def scan_codepoints(data, width, stride_max=64):
    """Find ascending sequences of `width`-byte little-endian ints that look like
    codepoints. Returns Counter of block -> hits, and candidate (offset, stride) pairs."""
    fmt = "<H" if width == 2 else "<I"
    n = len(data)
    hits = Counter()
    cands = []
    # test a set of plausible strides; for each, walk and look for long ascending runs
    for stride in (width, 4, 6, 8, 12, 16, 20, 24, 32, 40, 48):
        if stride < width:
            continue
        step = max(1, stride)
        # sample the file in windows to keep it fast
        off = 0
        run_start = None; run_len = 0; last = -1
        while off + width <= n:
            v = struct.unpack_from(fmt, data, off)[0]
            b = block_of(v)
            if b and v > last:
                if run_start is None:
                    run_start = off
                run_len += 1
                last = v
            else:
                if run_len >= 16:
                    cands.append((run_start, stride, run_len))
                run_start = None; run_len = 0; last = -1
            off += step
        if run_len >= 16:
            cands.append((run_start, stride, run_len))
    return cands


def profile(path):
    data = open(path, "rb").read()
    n = len(data)
    out = {"file": os.path.basename(path), "size": n}
    # unicode coverage: count how many DISTINCT values in each block appear as u16 aligned
    cnt = Counter()
    seen = {b[0]: set() for b in BLOCKS}
    for off in range(0, min(n, 2_000_000) - 2, 2):
        v = struct.unpack_from("<H", data, off)[0]
        b = block_of(v)
        if b:
            seen[b].add(v)
    out["u16_distinct_by_block"] = {k: len(v) for k, v in seen.items() if v}
    # candidate metric tables
    cands = scan_codepoints(data[:2_000_000], 2)
    cands.sort(key=lambda c: -c[2])
    out["ascending_runs"] = [{"off": c[0], "stride": c[1], "len": c[2]} for c in cands[:8]]
    out["head32"] = data[:32].hex()
    return out


def main():
    files = sorted(f for f in os.listdir(ATL) if f.endswith(".bin"))
    only = os.environ.get("ONLY")
    if only:
        files = [f for f in files if only in f]
    for f in files:
        p = profile(os.path.join(ATL, f))
        print(f"\n=== {p['file']}  ({p['size']:,} B) head={p['head32'][:32]}")
        cov = p["u16_distinct_by_block"]
        if cov:
            print("  u16 distinct per block:", ", ".join(f"{k}={v}" for k, v in sorted(cov.items(), key=lambda kv: -kv[1])))
        for r in p["ascending_runs"][:4]:
            print(f"    ascending run: off=0x{r['off']:x} stride={r['stride']} len={r['len']}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
