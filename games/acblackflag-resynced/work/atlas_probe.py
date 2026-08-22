#!/usr/bin/env python3
"""atlas_probe.py -- format triage of the baked glyph-atlas resources (class 0xcbd4939a).

Answers: is the decoded payload compressed/encrypted, or structured data?
"""
import os, sys, json, math, struct, collections

ATLAS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "atlas")
FILES = [
    "16243_88c2952a.bin", "16245_88c2952b.bin", "16248_88c2952c.bin",
    "19498_88cf5a5b.bin", "19499_8b21454b.bin", "19500_88cf5a5c.bin",
    "70970_88c902b3.bin", "70971_88c902b5.bin", "70972_88c902b1.bin",
    "70973_88cab006.bin", "70974_88c902b0.bin",
]
ARABIC = "70970_88c902b3.bin"
OTHER = "16243_88c2952a.bin"


def load(name):
    with open(os.path.join(ATLAS, name), "rb") as f:
        return f.read()


def ent(chunk):
    if not chunk:
        return 0.0
    c = collections.Counter(chunk)
    n = len(chunk)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


def entropy_profile(data, win=4096):
    return [(off, ent(data[off:off + win])) for off in range(0, len(data), win)]


def cmd_entropy():
    for name in (ARABIC, OTHER):
        d = load(name)
        prof = entropy_profile(d)
        vals = [e for _, e in prof]
        print(f"\n=== {name}  ({len(d):,} B, {len(prof)} windows of 4096) ===")
        print(f"  overall entropy       : {ent(d):.4f} bits/byte")
        print(f"  window min/med/max    : {min(vals):.3f} / {sorted(vals)[len(vals)//2]:.3f} / {max(vals):.3f}")
        # histogram of window entropies
        buckets = collections.Counter(int(v) for v in vals)
        print("  window-entropy histogram (bits/byte bucket -> count):")
        for b in sorted(buckets):
            print(f"    [{b}.0-{b}.99) : {buckets[b]:5d}  {'#'*min(60, buckets[b]//max(1,len(vals)//60))}")
        # first 40 windows in detail (header region)
        print("  first 32 windows:")
        for off, e in prof[:32]:
            print(f"    0x{off:08x}: {e:.3f}")
        # find first sustained high-entropy point (>7.5 for 4 windows in a row)
        run = 0
        start = None
        for off, e in prof:
            if e > 7.5:
                if run == 0:
                    start = off
                run += 1
                if run >= 4:
                    print(f"  first sustained (>7.5, 4 win) high entropy at 0x{start:x}")
                    break
            else:
                run = 0
        else:
            print("  NO sustained high-entropy region found (>7.5 over 4 windows)")
        # low-entropy islands (<4.0)
        low = [(off, e) for off, e in prof if e < 4.0]
        print(f"  windows with entropy < 4.0 : {len(low)} / {len(prof)}")
        hi = [(off, e) for off, e in prof if e > 7.5]
        print(f"  windows with entropy > 7.5 : {len(hi)} / {len(prof)}")
        if hi:
            print(f"    first={hi[0][0]:#x} last={hi[-1][0]:#x}")


def cmd_magic():
    pats = {
        "CFD 0x1004FA9957FBAA33": bytes.fromhex("33aafb5799fa0410"),
        "zstd 28B52FFD": bytes.fromhex("28b52ffd"),
        "zlib 7801": b"\x78\x01",
        "zlib 789c": b"\x78\x9c",
        "zlib 78da": b"\x78\xda",
        "LZ4 frame 04224D18": bytes.fromhex("04224d18"),
        "gzip 1F8B08": bytes.fromhex("1f8b08"),
        "DDS  'DDS '": b"DDS ",
        "sfnt 00010000": bytes.fromhex("00010000"),
        "OTTO": b"OTTO",
        "PNG": b"\x89PNG",
        "LZO?": b"\x89LZO",
        "xz": bytes.fromhex("fd377a585a00"),
        "bzip2 BZh": b"BZh",
    }
    for name in FILES:
        d = load(name)
        hits = []
        for label, pat in pats.items():
            idx = []
            i = d.find(pat)
            while i >= 0 and len(idx) < 6:
                idx.append(i)
                i = d.find(pat, i + 1)
            total = 0
            j = d.find(pat)
            while j >= 0:
                total += 1
                j = d.find(pat, j + 1)
                if total > 100000:
                    break
            if idx:
                hits.append(f"{label} x{total} @ " + ",".join(hex(x) for x in idx[:5]))
        print(f"\n--- {name} ({len(d):,}) ---")
        for h in hits:
            print("   ", h)
        if not hits:
            print("    (no magics)")


def cmd_head():
    for name in FILES:
        d = load(name)
        print(f"\n{name}  len={len(d):,}")
        for off in (0, 0x20, 0x40, 0x60, 0x80, 0xa0, 0xc0, 0xe0, 0x100, 0x120):
            row = d[off:off + 32]
            asc = "".join(chr(b) if 32 <= b < 127 else "." for b in row)
            print(f"  {off:04x}: {row.hex()}  {asc}")


def cmd_agree(nbytes=65536):
    ds = [load(n) for n in FILES]
    n = min(nbytes, min(len(d) for d in ds))
    agree = []
    for i in range(n):
        c = collections.Counter(d[i] for d in ds)
        agree.append(c.most_common(1)[0][1])
    # summarize runs
    print(f"per-offset agreement over first {n} bytes of {len(ds)} files")
    runs = []
    cur = agree[0]
    start = 0
    for i in range(1, n):
        # bucket: 11 = all agree, 6-10 = partial, <=5 low
        def b(x):
            return "ALL" if x == 11 else ("HI" if x >= 8 else ("MID" if x >= 5 else "LOW"))
        if b(agree[i]) != b(cur):
            runs.append((start, i, b(cur)))
            start = i
            cur = agree[i]
    runs.append((start, n, b(cur) if False else ("ALL" if cur == 11 else ("HI" if cur >= 8 else ("MID" if cur >= 5 else "LOW")))))
    print("  runs (offset range -> agreement class), first 120:")
    for s, e, cls in runs[:120]:
        print(f"    0x{s:06x}-0x{e:06x}  ({e-s:6d} B)  {cls}")
    print(f"  total runs: {len(runs)}")
    allsame = sum(1 for a in agree if a == 11)
    print(f"  bytes where ALL 11 agree: {allsame} ({100*allsame/n:.2f}%)")
    # where does structure end -> last offset with all-11 agreement in first 4KB
    last = max((i for i in range(min(n, 8192)) if agree[i] == 11), default=-1)
    print(f"  last all-agree offset within first 8KB: 0x{last:x}")
    return agree


def cmd_runs():
    """Investigate the repeating 4-char ASCII runs."""
    d = load(ARABIC)
    # find runs of 4+ identical bytes
    hist = collections.Counter()
    positions = collections.defaultdict(list)
    i = 0
    n = len(d)
    while i < n:
        j = i
        while j + 1 < n and d[j + 1] == d[i]:
            j += 1
        L = j - i + 1
        if L >= 4:
            hist[(d[i], L)] += 1
            if len(positions[d[i]]) < 10:
                positions[d[i]].append((i, L))
        i = j + 1
    print("top repeated-byte runs (byte, runlen) -> count:")
    for (b, L), c in hist.most_common(30):
        ch = chr(b) if 32 <= b < 127 else "."
        print(f"   0x{b:02x} '{ch}' x{L:<4d} : {c}")
    print("\nsample positions:")
    for b in sorted(positions, key=lambda x: -len(positions[x]))[:10]:
        ch = chr(b) if 32 <= b < 127 else "."
        print(f"   0x{b:02x} '{ch}': {positions[b][:6]}")


def cmd_bc7():
    print("BC7/BC(n) plausibility. BC7 & BC3 = 1 byte/pixel; BC1/BC4 = 0.5 B/px.")
    def mipchain(w, h, bpp):
        t = 0
        while w >= 1 and h >= 1:
            t += max(1, w) * max(1, h) * bpp
            if w == 1 and h == 1:
                break
            w = max(1, w // 2); h = max(1, h // 2)
        return int(t)
    cands = []
    for e in range(8, 14):
        for f in range(8, 14):
            w, h = 1 << e, 1 << f
            cands.append((w, h, w * h, "BC7 no-mip"))
            cands.append((w, h, mipchain(w, h, 1), "BC7 mips"))
            cands.append((w, h, w * h // 2, "BC1 no-mip"))
            cands.append((w, h, mipchain(w, h, 0.5), "BC1 mips"))
    for name in FILES:
        sz = os.path.getsize(os.path.join(ATLAS, name))
        best = []
        for w, h, need, kind in cands:
            for hdr in range(0, 4097):
                pass
            diff = sz - need
            if 0 <= diff <= 65536:
                best.append((diff, w, h, kind, need))
        best.sort()
        print(f"\n{name}: {sz:,} B")
        if best:
            for diff, w, h, kind, need in best[:6]:
                print(f"    {kind:12s} {w}x{h} = {need:,}  header/slack = {diff:,}")
        else:
            print("    no single-surface match within 64KB slack")
        # multi-surface: how many 1024x1024 BC7 pages fit
        for page in (1024*1024, 512*512, 2048*2048, 256*256):
            q, r = divmod(sz, page)
            if q >= 1 and r < 65536:
                print(f"    ~{q} pages of {int(page**0.5)}x{int(page**0.5)} BC7 + {r} slack")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "entropy"
    {"entropy": cmd_entropy, "magic": cmd_magic, "head": cmd_head,
     "agree": cmd_agree, "runs": cmd_runs, "bc7": cmd_bc7}[cmd]()
