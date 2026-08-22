# -*- coding: utf-8 -*-
"""Map the container structure of the Anvil forge class-0xcbd4939a atlas resources."""
import sys, os, struct, json, math
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

D = r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acblackflag\work\atlas"
FILES = [
    ("16243", 0x88c2952a, "16243_88c2952a.bin"),
    ("16245", 0x88c2952b, "16245_88c2952b.bin"),
    ("16248", 0x88c2952c, "16248_88c2952c.bin"),
    ("19498", 0x88cf5a5b, "19498_88cf5a5b.bin"),
    ("19499", 0x8b21454b, "19499_8b21454b.bin"),
    ("19500", 0x88cf5a5c, "19500_88cf5a5c.bin"),
    ("70970", 0x88c902b3, "70970_88c902b3.bin"),
    ("70971", 0x88c902b5, "70971_88c902b5.bin"),
    ("70972", 0x88c902b1, "70972_88c902b1.bin"),
    ("70973", 0x88cab006, "70973_88cab006.bin"),
    ("70974", 0x88c902b0, "70974_88c902b0.bin"),
]

data = {}
for name, fid, fn in FILES:
    p = os.path.join(D, fn)
    with open(p, "rb") as f:
        data[name] = (fid, f.read())

def hx(b):
    return " ".join(f"{x:02x}" for x in b)

print("=" * 100)
print("STEP 1 — HEAD DUMP (first 0x90 bytes) of every file")
print("=" * 100)
for name, fid, fn in FILES:
    _, b = data[name]
    print(f"\n--- {name}  fileID=0x{fid:08x}  size={len(b):,} (0x{len(b):x})")
    for off in range(0, 0x90, 16):
        chunk = b[off:off+16]
        asc = "".join(chr(c) if 32 <= c < 127 else "." for c in chunk)
        print(f"  {off:04x}  {hx(chunk):<47}  |{asc}|")

print()
print("=" * 100)
print("STEP 2 — VERIFY the '01 00 <fileID LE>' claim  (bytes 0..5)")
print("=" * 100)
for name, fid, fn in FILES:
    _, b = data[name]
    head6 = b[:6]
    # candidate: u16 at 0, then u32 LE at 2
    u16_0 = struct.unpack_from("<H", b, 0)[0]
    u32_2 = struct.unpack_from("<I", b, 2)[0]
    u32_0 = struct.unpack_from("<I", b, 0)[0]
    # is fileID present as LE u32 anywhere in first 0x20?
    fid_le = struct.pack("<I", fid)
    fid_be = struct.pack(">I", fid)
    pos_le = b[:0x400].find(fid_le)
    pos_be = b[:0x400].find(fid_be)
    print(f"{name}: head6={hx(head6)}  u16@0={u16_0}  u32@2=0x{u32_2:08x}  "
          f"match={'YES' if u32_2 == fid else 'no'}  fidLE@={pos_le}  fidBE@={pos_be}")

print()
print("=" * 100)
print("STEP 3 — FIELD-BY-FIELD DIFF of the first 0x200 bytes across all 11 files")
print("(CONST = identical byte in all 11; VAR = differs)")
print("=" * 100)
N = 0x200
cols = [name for name, _, _ in FILES]
const_map = []
for off in range(N):
    vals = [data[n][1][off] for n in cols]
    const_map.append(len(set(vals)) == 1)
# print as a run-length map
runs = []
start = 0
for off in range(1, N + 1):
    if off == N or const_map[off] != const_map[start]:
        runs.append((start, off - 1, const_map[start]))
        start = off
for a, bb, c in runs:
    tag = "CONST" if c else "VAR  "
    sample = data["70970"][1][a:bb+1]
    extra = ""
    if c:
        extra = "  bytes=" + hx(sample[:16]) + ("..." if bb - a + 1 > 16 else "")
    print(f"  0x{a:04x}-0x{bb:04x}  ({bb-a+1:4d}B)  {tag}{extra}")

print()
print("=" * 100)
print("STEP 4 — SCAN for every occurrence of class hash 0xcbd4939a in the first 4 KB")
print("=" * 100)
CH = struct.pack("<I", 0xcbd4939a)
CHB = struct.pack(">I", 0xcbd4939a)
for name, fid, fn in FILES:
    _, b = data[name]
    head = b[:0x2000]
    offs_le = []
    i = head.find(CH)
    while i != -1:
        offs_le.append(i)
        i = head.find(CH, i + 1)
    offs_be = []
    i = head.find(CHB)
    while i != -1:
        offs_be.append(i)
        i = head.find(CHB, i + 1)
    print(f"{name}: LE@{[hex(x) for x in offs_le]}  BE@{[hex(x) for x in offs_be]}")

print()
print("=" * 100)
print("STEP 5 — CANDIDATE SIZE/OFFSET FIELDS: scan u32 LE at every offset 0..0x100,")
print("         report which offsets hold a value related to the file size in ALL 11 files")
print("=" * 100)
rels = {}
for off in range(0, 0x100, 1):
    ok_exact = 0
    ok_le = 0     # value <= size and > size*0.5
    ok_plaus = 0  # 0 < value <= size
    deltas = []
    for name, fid, fn in FILES:
        _, b = data[name]
        v = struct.unpack_from("<I", b, off)[0]
        n = len(b)
        deltas.append(n - v)
        if v == n:
            ok_exact += 1
        if 0 < v <= n:
            ok_plaus += 1
        if n * 0.5 < v <= n:
            ok_le += 1
    if ok_plaus == 11 and (ok_le == 11 or len(set(deltas)) == 1):
        print(f"  off 0x{off:03x}: plaus=11 near={ok_le} exact={ok_exact} "
              f"deltas(size-v)={deltas} constDelta={len(set(deltas))==1}")

print()
print("=" * 100)
print("STEP 6 — value table of every u32 LE in the first 0x60 bytes, all files side by side")
print("=" * 100)
hdr = "off    " + "".join(f"{n:>12}" for n in cols)
print(hdr)
for off in range(0, 0x60, 4):
    row = f"0x{off:03x}  "
    for n in cols:
        v = struct.unpack_from("<I", data[n][1], off)[0]
        row += f"{v:12d}"
    print(row)
print()
print("same, hex:")
print(hdr)
for off in range(0, 0x60, 4):
    row = f"0x{off:03x}  "
    for n in cols:
        v = struct.unpack_from("<I", data[n][1], off)[0]
        row += f"    {v:08x}"
    print(row)
print()
print("file sizes:")
row = "size  "
for n in cols:
    row += f"{len(data[n][1]):12d}"
print(row)
