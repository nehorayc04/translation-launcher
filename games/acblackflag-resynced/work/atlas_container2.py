# -*- coding: utf-8 -*-
"""Phase 2: verify the derived header algebra, align on nameLen, hunt FourCCs, entropy map."""
import sys, os, struct, math, re, collections
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
    fn = f"{name}_{fid:08x}.bin"
    with open(os.path.join(D, fn), "rb") as f:
        data[name] = (fid, f.read())

def u32(b, o): return struct.unpack_from("<I", b, o)[0]
def u16(b, o): return struct.unpack_from("<H", b, o)[0]
def hx(b): return " ".join(f"{x:02x}" for x in b)

print("=" * 110)
print("A) HEADER ALGEBRA — verify the derived model on all 11 files")
print("   model: 0x00 u16 ver | 0x02 u32 fileID | 0x06 u32 fileType | 0x0A u32 dataSize=(fileSize-0x14)")
print("          0x0E u16 0 | 0x10 u32 0 | 0x14 u32 classHash | 0x18 u32 recSize | 0x1C u32 nameLen")
print("          0x20 name[nameLen] | +0 u8 0x00 | +1 u32 fileID | +5 u32 fileType | +9 u32 classHash")
print("   check: 0x21 + nameLen + recSize == fileSize")
print("=" * 110)
info = {}
for name, fid in FILES:
    _, b = data[name]
    n = len(b)
    ver, f_id, ftype, dsz = u16(b, 0), u32(b, 2), u32(b, 6), u32(b, 0x0a)
    z1, z2 = u16(b, 0x0e), u32(b, 0x10)
    ch, recsz, namelen = u32(b, 0x14), u32(b, 0x18), u32(b, 0x1c)
    nstart = 0x20
    nend = nstart + namelen
    term = b[nend]
    fid2, ftype2, ch2 = u32(b, nend + 1), u32(b, nend + 5), u32(b, nend + 9)
    ok_size = (0x21 + namelen + recsz) == n
    ok_dsz = (dsz == n - 0x14)
    info[name] = dict(namelen=namelen, nend=nend, body=nend + 13, ftype=ftype)
    print(f"{name}: ver={ver} fid=0x{f_id:08x}({'OK' if f_id==fid else 'BAD'}) ftype={ftype} "
          f"dsz={dsz}{'OK' if ok_dsz else ' BAD'} z={z1},{z2} ch=0x{ch:08x} recSz={recsz} "
          f"nameLen={namelen} term=0x{term:02x} fid2={'OK' if fid2==fid else 'BAD'} "
          f"ftype2={ftype2} ch2=0x{ch2:08x} SIZE_EQ={'OK' if ok_size else 'BAD'}")

print()
print("=" * 110)
print("B) THE NAME BLOB (0x20 .. 0x20+nameLen) — raw bytes + printable + simple decode attempts")
print("=" * 110)
for name, fid in FILES:
    _, b = data[name]
    nl = info[name]["namelen"]
    nb = b[0x20:0x20 + nl]
    asc = "".join(chr(c) if 32 <= c < 127 else "." for c in nb)
    print(f"\n{name} (len {nl}):")
    print("  raw : " + hx(nb))
    print("  ascii: " + asc)
    hi = sum(1 for c in nb if c & 0x80)
    print(f"  high-bit set: {hi}/{nl}   printable-as-is: {sum(1 for c in nb if 32<=c<127)}/{nl}")

print()
print("=" * 110)
print("C) BYTE DIFF of the name blobs, pairwise within the 3 obvious families")
print("=" * 110)
def diffpair(a, bn):
    x = data[a][1][0x20:0x20 + info[a]["namelen"]]
    y = data[bn][1][0x20:0x20 + info[bn]["namelen"]]
    m = min(len(x), len(y))
    d = [i for i in range(m) if x[i] != y[i]]
    print(f"  {a} vs {bn}: lens {len(x)}/{len(y)}  first-diff-idx={d[0] if d else 'none'}  "
          f"ndiff(common)={len(d)}  diffidx={d[:20]}")
for grp in [("16243", "16245"), ("16243", "16248"), ("16245", "16248"),
            ("70970", "70971"), ("70970", "70972"), ("70971", "70972"),
            ("70973", "70974"), ("19498", "19500"), ("19498", "19499")]:
    diffpair(*grp)

print()
print("=" * 110)
print("D) BODY (after name) — dump 0x60 bytes from nend, aligned; then diff across all 11")
print("=" * 110)
for name, fid in FILES:
    _, b = data[name]
    ne = info[name]["nend"]
    seg = b[ne:ne + 0x60]
    asc = "".join(chr(c) if 32 <= c < 127 else "." for c in seg)
    print(f"{name} @0x{ne:04x}: {hx(seg[:0x30])}")
    print(f"            {hx(seg[0x30:0x60])}   |{asc}|")
# aligned diff
L = 0x60
constmask = []
for i in range(L):
    vals = set()
    for name, fid in FILES:
        _, b = data[name]
        vals.add(b[info[name]["nend"] + i])
    constmask.append(len(vals) == 1)
runs = []
s = 0
for i in range(1, L + 1):
    if i == L or constmask[i] != constmask[s]:
        runs.append((s, i - 1, constmask[s])); s = i
print("\n  name-relative CONST/VAR runs (offset relative to nend = 0x20+nameLen):")
ref = data["70970"][1]
rne = info["70970"]["nend"]
for a, bb, c in runs:
    tag = "CONST" if c else "VAR  "
    ex = "  " + hx(ref[rne + a:rne + bb + 1][:24]) if c else ""
    print(f"    +0x{a:02x}..+0x{bb:02x} ({bb-a+1:3d}B) {tag}{ex}")

print()
print("=" * 110)
print("E) ASCII TOKEN HUNT — every printable run >=4 in the first 64 KB of each file")
print("=" * 110)
tok_re = re.compile(rb"[ -~]{4,}")
for name, fid in FILES:
    _, b = data[name]
    hits = [(m.start(), m.group().decode("ascii")) for m in tok_re.finditer(b[:0x10000])]
    print(f"\n{name}: {len(hits)} tokens in first 64KB")
    for off, t in hits[:25]:
        rel = off - info[name]["nend"]
        print(f"   0x{off:06x} (nend{rel:+d}): {t!r}")
    if len(hits) > 25:
        print(f"   ... +{len(hits)-25} more")

print()
print("=" * 110)
print("F) 'GFOF' / 'PHXFD' search across the WHOLE file")
print("=" * 110)
for tokb in (b"GFOF", b"PHXFD", b"PHXF", b"FOFG", b"DFXHP"):
    print(f"\n token {tokb!r}:")
    for name, fid in FILES:
        _, b = data[name]
        offs = []
        i = b.find(tokb)
        while i != -1 and len(offs) < 8:
            offs.append(i); i = b.find(tokb, i + 1)
        tot = b.count(tokb)
        rel = [o - info[name]["nend"] for o in offs]
        print(f"   {name}: count={tot} first={[hex(o) for o in offs]} nend-relative={rel}")
