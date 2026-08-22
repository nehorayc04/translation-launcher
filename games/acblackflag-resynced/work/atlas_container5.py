# -*- coding: utf-8 -*-
"""Phase 5: parse the GFOF sub-header, brute-force the true glyph-array start, census codepoints."""
import sys, os, struct, collections
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
print("A) GFOF SUB-HEADER — 64 bytes after the tag, decoded as u32 / f32 side by side")
print("=" * 110)
for name, fid in FILES:
    b = data[name][1]
    g = b.find(b"GFOF")
    print(f"\n  {name}  GFOF@0x{g:04x} (nend+{g-NE[name]})")
    for rel in range(4, 72, 4):
        o = g + rel
        print(f"     +{rel:<3d} (0x{o:04x}) raw={hx(b[o:o+4])}  u32={u32(b,o):<12d} f32={f32(b,o):< 16.6g}")

print()
print("=" * 110)
print("B) BRUTE-FORCE the glyph-array start S, using N = u32 @ GFOF+0x24 as the record count")
print("   accept S only if ALL N records have pad-u16 == 0 and cp in 0x0001..0xFFFD")
print("=" * 110)
FOUND = {}
for name, fid in FILES:
    b = data[name][1]; g = b.find(b"GFOF"); n = len(b)
    N = u32(b, g + 0x24)
    cands = []
    for S in range(g + 40, g + 160):
        if S + 36 * N > n:
            continue
        ok = True
        for i in range(N):
            k = S + 36 * i
            if u16(b, k + 2) != 0:
                ok = False; break
            cp = u16(b, k)
            if cp == 0 or cp > 0xFFFD:
                ok = False; break
        if ok:
            cands.append(S)
    print(f"  {name}: N={N}  candidate starts={[hex(c) for c in cands]}  "
          f"(GFOF+{[c-g for c in cands]})")
    if cands:
        S = cands[0]
        FOUND[name] = (S, N)

print()
print("=" * 110)
print("C) DECODED GLYPH TABLE — first 8 and last 4 records of each file")
print("=" * 110)
for name, fid in FILES:
    if name not in FOUND:
        print(f"  {name}: NO CANDIDATE"); continue
    b = data[name][1]; S, N = FOUND[name]
    print(f"\n  {name}: start=0x{S:x} N={N} end=0x{S+36*N:x} fileSize=0x{len(b):x}")
    idx = list(range(min(8, N))) + list(range(max(0, N - 4), N))
    for i in idx:
        k = S + 36 * i
        cp = u16(b, k)
        fl = [round(f32(b, k + 4 + 4 * j), 3) for j in range(7)]
        t0, t1 = u16(b, k + 32), u16(b, k + 34)
        ch = chr(cp) if 32 <= cp < 0xD800 else "?"
        print(f"    [{i:5d}] U+{cp:04X} '{ch}' f={fl} u16={t0},{t1}")

print()
print("=" * 110)
print("D) CODEPOINT CENSUS per file")
print("=" * 110)
BLOCKS = [
    (0x0020, 0x007F, "ASCII"), (0x0080, 0x00FF, "Latin1"), (0x0100, 0x017F, "LatExtA"),
    (0x0180, 0x024F, "LatExtB"), (0x0250, 0x02FF, "IPA/Mod"), (0x0300, 0x036F, "Comb"),
    (0x0370, 0x03FF, "Greek"), (0x0400, 0x04FF, "Cyrillic"), (0x0530, 0x058F, "Armenian"),
    (0x0590, 0x05FF, "HEBREW"), (0x0600, 0x06FF, "ARABIC"), (0x0700, 0x074F, "Syriac"),
    (0x0750, 0x077F, "ArabSupp"), (0x0E00, 0x0E7F, "Thai"), (0x1E00, 0x1EFF, "LatExtAdd"),
    (0x2000, 0x206F, "GenPunct"), (0x2070, 0x209F, "SupSub"), (0x20A0, 0x20CF, "Currency"),
    (0x2100, 0x214F, "LetterLike"), (0x2150, 0x218F, "NumForms"), (0x2190, 0x21FF, "Arrows"),
    (0x2200, 0x22FF, "Math"), (0x2300, 0x23FF, "MiscTech"), (0x2500, 0x257F, "BoxDraw"),
    (0x25A0, 0x25FF, "Geom"), (0x2600, 0x26FF, "MiscSym"), (0x3000, 0x303F, "CJKPunct"),
    (0x3040, 0x309F, "Hiragana"), (0x30A0, 0x30FF, "Katakana"), (0x3130, 0x318F, "Jamo"),
    (0x4E00, 0x9FFF, "CJK"), (0xAC00, 0xD7AF, "Hangul"), (0xE000, 0xF8FF, "PUA"),
    (0xFB00, 0xFB4F, "AlphaPres"), (0xFB50, 0xFDFF, "ArabPresA"), (0xFE70, 0xFEFF, "ArabPresB"),
    (0xFF00, 0xFFEF, "Halfwidth"),
]
CENSUS = {}
for name, fid in FILES:
    if name not in FOUND: continue
    b = data[name][1]; S, N = FOUND[name]
    cps = [u16(b, S + 36 * i) for i in range(N)]
    CENSUS[name] = cps
    hist = collections.Counter()
    for cp in cps:
        for lo, hi, nm in BLOCKS:
            if lo <= cp <= hi: hist[nm] += 1; break
        else: hist[f"other"] += 1
    dup = N - len(set(cps))
    asc = all(cps[i] < cps[i+1] for i in range(N-1))
    print(f"\n  {name}: N={N} distinct={len(set(cps))} dups={dup} strictlyAscending={asc}")
    print(f"      " + ", ".join(f"{k}={v}" for k, v in hist.most_common(14)))

print()
print("=" * 110)
print("E) HEBREW vs ARABIC coverage — the money table")
print("=" * 110)
for name, fid in FILES:
    if name not in CENSUS: continue
    cps = CENSUS[name]
    heb = sorted({c for c in cps if 0x0590 <= c <= 0x05FF})
    ara = sorted({c for c in cps if 0x0600 <= c <= 0x06FF})
    pa = sorted({c for c in cps if 0xFB50 <= c <= 0xFDFF})
    pb = sorted({c for c in cps if 0xFE70 <= c <= 0xFEFF})
    print(f"  {name}: HEB={len(heb):4d}  ARABIC={len(ara):4d}  PresA={len(pa):4d}  PresB={len(pb):4d}")
    if heb:
        print(f"        hebrew: {' '.join(f'{c:04X}' for c in heb)}")
