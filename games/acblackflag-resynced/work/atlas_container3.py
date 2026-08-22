# -*- coding: utf-8 -*-
"""Phase 3: inner block size + trailer, entropy map, FourCC context, ascending-u16 charmap hunt."""
import sys, os, struct, math, collections
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
def hx(b): return " ".join(f"{x:02x}" for x in b)
NE = {}
for name, fid in FILES:
    b = data[name][1]
    NE[name] = 0x20 + u32(b, 0x1c)

print("=" * 110)
print("A) INNER BLOCK SIZE @ nend+51  and the TRAILER")
print("=" * 110)
for name, fid in FILES:
    b = data[name][1]; ne = NE[name]; n = len(b)
    v51 = u32(b, ne + 51)
    start = ne + 55
    end = start + v51
    print(f"{name}: nend=0x{ne:04x} u32@nend+51={v51} blockStart=0x{start:04x} "
          f"blockEnd=0x{end:x} fileSize=0x{n:x} tail={n-end}B")
print("\n  last 40 bytes of each file:")
for name, fid in FILES:
    b = data[name][1]
    print(f"  {name}: {hx(b[-40:])}")

print()
print("=" * 110)
print("B) FULL DUMP nend+50 .. nend+272 (the structured prologue) for 3 files")
print("=" * 110)
for name in ("70970", "16243", "19498"):
    b = data[name][1]; ne = NE[name]
    print(f"\n--- {name}  (nend=0x{ne:04x})")
    for rel in range(50, 272, 16):
        seg = b[ne + rel: ne + rel + 16]
        asc = "".join(chr(c) if 32 <= c < 127 else "." for c in seg)
        print(f"  nend+{rel:<4d} (abs 0x{ne+rel:04x})  {hx(seg):<47}  |{asc}|")

print()
print("=" * 110)
print("C) CONST/VAR mask, name-relative, over nend+50 .. nend+400  (all 11 aligned)")
print("=" * 110)
L0, L1 = 50, 400
mask = []
for rel in range(L0, L1):
    vals = {data[n][1][NE[n] + rel] for n, _ in FILES}
    mask.append(len(vals) == 1)
runs = []; s = 0
for i in range(1, len(mask) + 1):
    if i == len(mask) or mask[i] != mask[s]:
        runs.append((L0 + s, L0 + i - 1, mask[s])); s = i
ref = data["70970"][1]; rne = NE["70970"]
for a, bb, c in runs:
    tag = "CONST" if c else "VAR  "
    seg = ref[rne + a: rne + bb + 1]
    asc = "".join(chr(x) if 32 <= x < 127 else "." for x in seg)
    print(f"  nend+{a:<4d}..+{bb:<4d} ({bb-a+1:4d}B) {tag}  {hx(seg[:28])}{'...' if len(seg)>28 else ''}  |{asc[:28]}|")

print()
print("=" * 110)
print("D) 'GFOF' exact position + 32 bytes of context")
print("=" * 110)
for name, fid in FILES:
    b = data[name][1]; ne = NE[name]
    i = b.find(b"GFOF")
    if i < 0:
        print(f"  {name}: not found"); continue
    print(f"  {name}: abs=0x{i:04x} nend+{i-ne}  ctx: "
          f"{hx(b[i-12:i])} [{hx(b[i:i+4])}] {hx(b[i+4:i+20])}")
print("\n  total GFOF occurrences per file:")
for name, fid in FILES:
    b = data[name][1]
    print(f"  {name}: {b.count(b'GFOF')}   PHXFD: {b.count(b'PHXFD')}")

print()
print("=" * 110)
print("E) SLIDING-WINDOW ENTROPY (window 512B, step 256) — first 24 KB, per file")
print("   printing the offset where entropy first exceeds 7.4 bits/byte and stays high")
print("=" * 110)
def ent(bs):
    if not bs: return 0.0
    c = collections.Counter(bs); n = len(bs)
    return -sum((v/n) * math.log2(v/n) for v in c.values())
for name, fid in FILES:
    b = data[name][1]; ne = NE[name]
    rows = []
    for off in range(0, min(len(b), 0x6000), 256):
        rows.append((off, ent(b[off:off+512])))
    first_hi = next((o for o, e in rows if e > 7.4), None)
    print(f"\n  {name} (nend=0x{ne:04x}):")
    print("    " + "  ".join(f"{o:#06x}:{e:.2f}" for o, e in rows[:24]))
    print(f"    first window >7.4 bits: {hex(first_hi) if first_hi is not None else 'none in 24KB'}")

print()
print("=" * 110)
print("F) WHOLE-FILE ENTROPY PROFILE (window 64KB, step 64KB) — where does the bulk sit?")
print("=" * 110)
for name, fid in FILES:
    b = data[name][1]
    es = []
    for off in range(0, len(b), 65536):
        es.append(ent(b[off:off+65536]))
    lo = min(es); hi = max(es); avg = sum(es)/len(es)
    print(f"  {name}: {len(es)} windows  min={lo:.2f} max={hi:.2f} avg={avg:.2f}  "
          f"profile={' '.join(f'{e:.1f}' for e in es[:20])}{' ...' if len(es)>20 else ''}")

print()
print("=" * 110)
print("G) ASCENDING-u16 RUN HUNT (candidate codepoint/charmap table) — runs >= 24 strictly ascending")
print("=" * 110)
for name, fid in FILES:
    b = data[name][1]
    best = []
    n = len(b) - 2
    for align in (0, 2):
        i = align; runstart = align; prev = None
        while i < n:
            v = b[i] | (b[i+1] << 8)
            if prev is not None and v > prev:
                pass
            else:
                if prev is not None and (i - runstart) // 2 >= 24:
                    best.append((runstart, (i - runstart)//2, align))
                runstart = i
            prev = v
            i += 2
    best.sort(key=lambda t: -t[1])
    print(f"  {name}: top ascending-u16 runs: " +
          ", ".join(f"@0x{o:x} len={l} (stride2,align{a})" for o, l, a in best[:6]))
    if best:
        o, l, a = best[0]
        vals = struct.unpack_from("<%dH" % min(l, 40), b, o)
        print(f"      values: {list(vals)}")
