# -*- coding: utf-8 -*-
"""Phase 4: the 36-byte glyph record array — find start, count, decode; plus whole-file entropy."""
import sys, os, struct, math, collections, unicodedata
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

D = r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acblackflag\work\atlas"
FILES = [
    ("16243", 0x88c2952a), ("16245", 0x88c2952b), ("16248", 0x88c2952c),
    ("19498", 0x88cf5a5b), ("19499", 0x8b21454b), ("19500", 0x88cf5a5c),
    ("70970", 0x88c902b3), ("70971", 0x88c902b5), ("70972", 0x88c902b1),
    ("70973", 0x88cab006), ("70974", 0x88c902b0),
]
data = {}
for name, fid in FILES:
    with open(os.path.join(D, f"{name}_{fid:08x}.bin"), "rb") as f:
        data[name] = (fid, f.read())
def u32(b, o): return struct.unpack_from("<I", b, o)[0]
def u16(b, o): return struct.unpack_from("<H", b, o)[0]
def f32(b, o): return struct.unpack_from("<f", b, o)[0]
def hx(b): return " ".join(f"{x:02x}" for x in b)
NE = {n: 0x20 + u32(data[n][1], 0x1c) for n, _ in FILES}

print("=" * 110)
print("A) WHOLE-FILE ENTROPY PROFILE (64 KB windows)")
print("=" * 110)
def ent(bs):
    if not bs: return 0.0
    c = collections.Counter(bs); n = len(bs)
    return -sum((v/n)*math.log2(v/n) for v in c.values())
for name, fid in FILES:
    b = data[name][1]
    es = [ent(b[o:o+65536]) for o in range(0, len(b), 65536)]
    print(f"  {name}: n={len(es)} min={min(es):.2f} max={max(es):.2f} avg={sum(es)/len(es):.2f}")
    print(f"      {' '.join(f'{e:.1f}' for e in es)}")

print()
print("=" * 110)
print("B) HUNT the 36-byte record array: scan for the longest run where")
print("   u16@k is a plausible codepoint (0x20..0xFFFD) and u16@k+2 == 0 and stride 36")
print("=" * 110)
def score_start(b, start, maxrec=200000):
    """count consecutive records from `start` satisfying the record shape"""
    k = start; c = 0
    n = len(b)
    while k + 36 <= n and c < maxrec:
        cp = u16(b, k); pad = u16(b, k+2)
        if pad != 0: break
        if not (0x20 <= cp <= 0xFFFD): break
        # advance float must be finite and sane
        try:
            adv = f32(b, k+4)
        except Exception:
            break
        if not (-1e4 < adv < 1e4): break
        k += 36; c += 1
    return c

for name, fid in FILES:
    b = data[name][1]; ne = NE[name]
    best = (0, None)
    for start in range(ne + 200, ne + 600):
        c = score_start(b, start)
        if c > best[0]:
            best = (c, start)
    cnt, st = best
    print(f"\n  {name}: best array start=0x{st:x} (nend+{st-ne}) records={cnt} "
          f"span=0x{st:x}..0x{st+cnt*36:x} ({cnt*36} B)  fileSize=0x{len(b):x}")
    if st is None: continue
    print(f"    first 6 records:")
    for i in range(min(6, cnt)):
        k = st + i*36
        cp = u16(b, k)
        fl = [f32(b, k+4+4*j) for j in range(7)]
        tail = u32(b, k+32)
        try: nm = unicodedata.name(chr(cp))
        except Exception: nm = "?"
        print(f"      [{i}] U+{cp:04X} {nm[:34]:<34} floats={[round(x,3) for x in fl]} tail={tail}")

print()
print("=" * 110)
print("C) CODEPOINT CENSUS of the record array per file (Unicode block histogram)")
print("=" * 110)
BLOCKS = [
    (0x0000, 0x007F, "ASCII"), (0x0080, 0x00FF, "Latin-1"), (0x0100, 0x017F, "LatinExtA"),
    (0x0180, 0x024F, "LatinExtB"), (0x0370, 0x03FF, "Greek"), (0x0400, 0x04FF, "Cyrillic"),
    (0x0590, 0x05FF, "HEBREW"), (0x0600, 0x06FF, "ARABIC"), (0x0750, 0x077F, "ArabicSupp"),
    (0x0E00, 0x0E7F, "Thai"), (0x2000, 0x206F, "GenPunct"), (0x20A0, 0x20CF, "Currency"),
    (0x2100, 0x214F, "LetterLike"), (0x2190, 0x21FF, "Arrows"), (0x2200, 0x22FF, "MathOps"),
    (0x2500, 0x257F, "BoxDraw"), (0x25A0, 0x25FF, "Geometric"), (0x2600, 0x26FF, "Misc"),
    (0x3000, 0x303F, "CJKPunct"), (0x3040, 0x309F, "Hiragana"), (0x30A0, 0x30FF, "Katakana"),
    (0x4E00, 0x9FFF, "CJK"), (0xAC00, 0xD7AF, "Hangul"),
    (0xFB50, 0xFDFF, "ArabicPresA"), (0xFE70, 0xFEFF, "ArabicPresB"),
    (0xFF00, 0xFFEF, "Halfwidth"),
]
summary = {}
for name, fid in FILES:
    b = data[name][1]; ne = NE[name]
    best = (0, None)
    for start in range(ne + 200, ne + 600):
        c = score_start(b, start)
        if c > best[0]: best = (c, start)
    cnt, st = best
    cps = [u16(b, st + i*36) for i in range(cnt)]
    hist = collections.Counter()
    for cp in cps:
        for lo, hi, nm in BLOCKS:
            if lo <= cp <= hi:
                hist[nm] += 1; break
        else:
            hist["other"] += 1
    summary[name] = (cnt, st, cps, hist)
    top = ", ".join(f"{k}={v}" for k, v in hist.most_common(10))
    print(f"  {name}: {cnt} glyphs | {top}")

print()
print("=" * 110)
print("D) HEBREW + ARABIC coverage detail")
print("=" * 110)
for name, fid in FILES:
    cnt, st, cps, hist = summary[name]
    heb = sorted({c for c in cps if 0x0590 <= c <= 0x05FF})
    ara = sorted({c for c in cps if 0x0600 <= c <= 0x06FF})
    prA = sorted({c for c in cps if 0xFB50 <= c <= 0xFDFF})
    prB = sorted({c for c in cps if 0xFE70 <= c <= 0xFEFF})
    print(f"  {name}: HEBREW={len(heb)} ARABIC={len(ara)} PresA={len(prA)} PresB={len(prB)}")
    if heb:
        print(f"      hebrew cps: {[f'U+{c:04X}' for c in heb]}")

print()
print("=" * 110)
print("E) The record TAIL u32 — is it an offset? check monotonicity + range vs file size")
print("=" * 110)
for name, fid in FILES:
    b = data[name][1]; cnt, st, cps, hist = summary[name]
    tails = [u32(b, st + i*36 + 32) for i in range(cnt)]
    arr_end = st + cnt*36
    mono = all(tails[i] <= tails[i+1] for i in range(len(tails)-1))
    print(f"  {name}: n={cnt} min={min(tails)} max={max(tails)} monotonic={mono} "
          f"arrayEnd=0x{arr_end:x} fileSize=0x{len(b):x} bytesAfterArray={len(b)-arr_end} "
          f"max+arrEnd=0x{max(tails)+arr_end:x}")
    print(f"      first 12 tails: {tails[:12]}")
    print(f"      last  6 tails: {tails[-6:]}")
