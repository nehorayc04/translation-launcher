#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fv_core_scan.py — scan the cached core_common for glyph tables (RICH + CMAP) and,
for the cleanest/biggest ones, report the codepoint coverage + what sits immediately
before/after (candidate FontVerts). Efficient: single pass over the 64-byte-record
signature (u32@+8 == 4 AND u16@+62 == 0xffff)."""
import os, sys, struct
CACHE = r"C:/Users/NEHORA~1/AppData/Local/Temp/claude/c--Users-Nehoray-Cohen-Projects-Game-translator/a86ff9b5-d140-4c99-b5de-33e68113ffe9/scratchpad"
GREC = 64


def find_tables(data):
    """Find maximal runs of ascending-cp 64-byte rich records. Uses a strided scan on
    the '04 00 00 00' @+8 signature but verifies +62==0xffff too."""
    n = len(data)
    tables = []
    pat = b"\x04\x00\x00\x00"
    i = data.find(pat)
    seen_end = -1
    while i != -1:
        p = i - 8  # record start
        if p >= 0 and p > seen_end and p + GREC <= n and \
           struct.unpack_from("<H", data, p + 62)[0] == 0xffff and \
           struct.unpack_from("<H", data, p + 2)[0] == 0:
            # walk a run of ascending-cp records
            cps = []
            q = p
            while q + GREC <= n and struct.unpack_from("<I", data, q + 8)[0] == 4 \
                    and struct.unpack_from("<H", data, q + 62)[0] == 0xffff \
                    and struct.unpack_from("<H", data, q + 2)[0] == 0:
                c = struct.unpack_from("<H", data, q)[0]
                if c == 0xffff:
                    q += GREC
                    break
                if cps and c <= cps[-1]:
                    break
                cps.append(c)
                q += GREC
            if len(cps) >= 8:
                tables.append((p, cps, q))
                seen_end = q
                i = data.find(pat, q)
                continue
        i = data.find(pat, i + 1)
    return tables


def main():
    data = open(os.path.join(CACHE, "core_common.bin"), "rb").read()
    print(f"core_common size={len(data):,}  magic={data[:4]!r}")
    tbls = find_tables(data)
    print(f"\nRICH glyph tables: {len(tbls)}")
    # classify by coverage; show the widest-cp and the largest
    def cover(cps):
        return (min(cps), max(cps), len(cps))
    tbls_sorted = sorted(tbls, key=lambda t: -len(t[1]))
    print("\n== top 25 tables by size ==")
    for s, cps, e in tbls_sorted[:25]:
        mn, mx, n = cover(cps)
        arb = sum(1 for c in cps if 0x600 <= c <= 0x6ff)
        heb = sum(1 for c in cps if 0x590 <= c <= 0x5ff)
        cjk = sum(1 for c in cps if 0x3000 <= c <= 0x9fff)
        tag = ""
        if arb: tag += f" AR={arb}"
        if heb: tag += f" HE={heb}"
        if cjk: tag += f" CJK={cjk}"
        print(f"  @0x{s:x}..0x{e:x} n={n} cp[0x{mn:x}..0x{mx:x}]{tag}")

    # widest-cp tables (max cp high)
    print("\n== tables reaching highest cp (script coverage) ==")
    for s, cps, e in sorted(tbls, key=lambda t: -max(t[1]))[:12]:
        print(f"  @0x{s:x} n={len(cps)} cp[0x{min(cps):x}..0x{max(cps):x}]")

    # for the biggest table, dump 96 bytes before and after
    if tbls_sorted:
        s, cps, e = tbls_sorted[0]
        print(f"\n== biggest table @0x{s:x} n={len(cps)} ; 96B before / 128B after ==")
        def hd(b, base):
            return "\n".join(f"  {base+i:08x}  {b[i:i+16].hex()}" for i in range(0, len(b), 16))
        print("BEFORE:"); print(hd(data[s-96:s], s-96))
        print("AFTER:"); print(hd(data[e:e+128], e))


if __name__ == "__main__":
    main()
