#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fonk_a1_struct.py — map the NAMS container tags, bound the fOnk chunk, and hunt
for a codepoint ladder (cmap) + interpret the post-fOnk header several ways."""
import os, struct, re, math, collections

HERE = os.path.dirname(os.path.abspath(__file__))
EX   = os.path.join(HERE, "..", "extract")
TMM  = os.path.join(EX, "game.sprig.texmeshman")
FONK_OFF = 0x156BFF7

raw = open(TMM, "rb").read()
N = len(raw)


def ent(b):
    if not b: return 0.0
    c = collections.Counter(b); n = len(b)
    return -sum((v/n)*math.log2(v/n) for v in c.values())


def main():
    # 1) FourCC tag scan — 4 printable ASCII, look for known + neighbours of fOnk.
    tagre = re.compile(rb"[A-Za-z][A-Za-z0-9_]{3}")
    # too noisy globally; instead scan a window around fOnk for uppercase-ish tags
    print("== printable 4-byte tokens within fOnk-2KB .. fOnk+40KB (filtered) ==")
    lo, hi = FONK_OFF-0x800, FONK_OFF+0x9C40
    seen = []
    for m in re.finditer(rb"[A-Za-z]{4}", raw[lo:hi]):
        tok = m.group()
        # keep tokens that look like a tag (mixed/upper) — skip lowercase noise unless known
        seen.append((lo+m.start(), tok))
    # show fOnk + any token containing a capital
    for pos, tok in seen:
        s = tok.decode()
        if any(c.isupper() for c in s) or s in ("fOnk",):
            print(f"   0x{pos:08x} (fOnk{pos-FONK_OFF:+d})  {s!r}")

    # 2) Post-fOnk header — try many interpretations of the 64 bytes after the tag.
    hdr = raw[FONK_OFF+4:FONK_OFF+4+64]
    print(f"\n== 64 bytes after 'fOnk' @0x{FONK_OFF+4:x} ==")
    print("   " + hdr.hex())
    print("   as u32 LE:", [hex(x) for x in struct.unpack_from("<16I", hdr, 0)])
    print("   as u16 LE:", [hex(x) for x in struct.unpack_from("<16H", hdr, 0)][:16])
    print("   as f32 LE:", [round(x, 4) for x in struct.unpack_from("<16f", hdr, 0)][:8])

    # 3) Entropy comparison: fOnk region vs a truly-random slice vs a low region.
    print("\n== entropy comparison (does fOnk look COMPRESSED [~7.95] or STRUCTURED [~7.2-7.6]?) ==")
    print(f"   fOnk+0..64KB : {ent(raw[FONK_OFF:FONK_OFF+65536]):.4f}")
    print(f"   os.urandom   : {ent(os.urandom(65536)):.4f}")
    import zlib
    z = zlib.compress(raw[FONK_OFF:FONK_OFF+65536], 9)
    print(f"   zlib(fOnk)   : {ent(z):.4f}  (compressed {len(raw[FONK_OFF:FONK_OFF+65536])}->{len(z)}, ratio {len(z)/65536:.3f})")
    print("   -> if fOnk compresses well (<0.9), it is NOT already compressed; if ratio ~1.0 it IS.")

    # 4) Byte histogram of fOnk region (structure shows spikes at 0x00/0xff or tag bytes).
    hist = collections.Counter(raw[FONK_OFF:FONK_OFF+65536])
    print("\n== top-12 byte values in fOnk+0..64KB ==")
    for b, c in hist.most_common(12):
        print(f"   0x{b:02x}: {c}  ({100*c/65536:.2f}%)")

    # 5) CODEPOINT LADDER hunt: look for ascending u16 runs matching ASCII/Arabic ranges.
    #    Scan the whole file for runs of >=8 strictly-ascending u16 in [0x20,0x6ff] with
    #    small deltas — that's a cmap.
    print("\n== codepoint-ladder hunt (ascending u16 in [0x20..0x6ff], run>=10) ==")
    found = 0
    i = 0
    step = 2
    # scan on a coarse basis: try both stride-2 and stride-4 (u16 field inside a wider record)
    for stride in (2, 4, 8, 12, 16, 20, 24, 28, 32):
        runs = []
        # walk aligned-ish: for each start offset 0..stride-1 is too much; sample near fOnk only
        base = FONK_OFF
        end  = min(N, FONK_OFF + 200000)
        for start in range(0, stride, 2):
            p = base + start
            run_start = None; prev = None; cnt = 0
            while p + 2 <= end:
                v = struct.unpack_from("<H", raw, p)[0]
                ok = (0x20 <= v <= 0x6FF)
                if ok and prev is not None and 0 < v - prev <= 8:
                    cnt += 1
                    if run_start is None:
                        run_start = p - stride; cnt = 2
                else:
                    if cnt >= 10:
                        runs.append((run_start, cnt, prev))
                    run_start = None; cnt = 0
                prev = v if ok else None
                p += stride
            if cnt >= 10:
                runs.append((run_start, cnt, prev))
        if runs:
            print(f"   stride={stride}: {len(runs)} runs; top: " +
                  ", ".join(f"@0x{r[0]:x} len{r[1]} end~{r[2]:#x}" for r in runs[:4]))

    # 6) Also try codepoints as u32 (some fonts store cp as u32).
    print("\n== codepoint-ladder hunt as u32 in [0x20..0x6ff], run>=10 ==")
    for stride in (4, 8, 12, 16, 20, 24, 28, 32):
        base = FONK_OFF; end = min(N, FONK_OFF + 200000)
        for start in range(0, stride, 4):
            p = base + start; prev=None; cnt=0; rs=None
            while p+4 <= end:
                v = struct.unpack_from("<I", raw, p)[0]
                ok = 0x20 <= v <= 0x6FF
                if ok and prev is not None and 0 < v-prev <= 8:
                    cnt += 1
                    if rs is None: rs = p-stride; cnt=2
                else:
                    if cnt >= 10:
                        print(f"   stride={stride} start={start}: @0x{rs:x} len{cnt} end~{prev:#x}")
                    rs=None; cnt=0
                prev = v if ok else None
                p += stride


if __name__ == "__main__":
    main()
