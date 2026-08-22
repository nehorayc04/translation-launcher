"""Dump + structurally analyse the FC5 font bank.

cf402ed3ebb8872f (common.fat, 25,238 B) is the ONLY resource that references both glyph
atlases, so it is the FontDescriptor / CFontBank -- the table that says which codepoint
lives at which atlas rect with which advance.  Without it, injected pixels are unaddressable.

  python -u dump_fontbank.py            -> hexdump + structure guesses -> extract/fontbank.bin
"""
import sys, os, struct, collections

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from fc5_fat import Fat

PC = os.path.join(os.environ.get("FC5_GAME", r"F:/SteamLibrary/steamapps/common/FarCry5"),
                  "data_final", "pc")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "extract")
os.makedirs(OUT, exist_ok=True)

H = 0xcf402ed3ebb8872f
ATLASES = {0x4121034366bd73a3: "arabic", 0xc44a353a7c4073c2: "latin"}

f = Fat(os.path.join(PC, "common.fat"))
e = f.by_hash[H]
b = f.read_data(e)
open(os.path.join(OUT, "fontbank.bin"), "wb").write(b)
print(f"{H:016x}  {len(b):,} bytes  (scheme {e.scheme})\n")


def hexdump(data, off, n=128, label=""):
    if label:
        print(f"--- {label} @0x{off:x}")
    for i in range(0, n, 16):
        chunk = data[off + i:off + i + 16]
        if not chunk:
            break
        hx = " ".join(f"{c:02x}" for c in chunk)
        asc = "".join(chr(c) if 32 <= c < 127 else "." for c in chunk)
        print(f"  {off+i:06x}  {hx:<47}  |{asc}|")


hexdump(b, 0, 256, "head")

# where are the atlas references?
print("\n--- atlas references")
refs = []
for h, name in ATLASES.items():
    nd = struct.pack("<Q", h)
    p = 0
    while True:
        p = b.find(nd, p)
        if p < 0:
            break
        refs.append((p, h, name))
        p += 1
refs.sort()
for p, h, name in refs:
    print(f"  {name:8s} {h:016x} @0x{p:x}")
    hexdump(b, max(0, p - 48), 128)
    print()

# strings
print("--- printable strings (>=4)")
import re
seen = []
for m in re.finditer(rb"[\x20-\x7e]{4,}", b):
    s = m.group().decode("latin-1")
    seen.append((m.start(), s))
for off, s in seen[:60]:
    print(f"  0x{off:06x}  {s}")
print(f"  ({len(seen)} strings total)")

# u16 codepoint runs -- a glyph table is normally an ascending codepoint array
print("\n--- ascending u16 runs (candidate codepoint tables)")
n = len(b)
i = 0
runs = []
while i + 4 <= n:
    a = struct.unpack_from("<H", b, i)[0]
    j = i + 2
    prev = a
    cnt = 1
    while j + 2 <= n:
        v = struct.unpack_from("<H", b, j)[0]
        if v <= prev or v - prev > 0x400:
            break
        prev = v
        cnt += 1
        j += 2
    if cnt >= 24:
        runs.append((i, cnt, a, prev))
        i = j
    else:
        i += 2
for off, cnt, lo, hi in runs[:40]:
    print(f"  @0x{off:06x} n={cnt:<5} U+{lo:04X}..U+{hi:04X}")
print(f"  ({len(runs)} runs)")

# stride guess: look for a repeating record whose first field ascends by 1 codepoint
print("\n--- record-stride scan (u16 codepoint at a fixed stride)")
best = []
for stride in range(8, 65, 2):
    for base in range(0, min(4096, n - stride * 40), 2):
        cps = []
        ok = True
        prev = -1
        for k in range(40):
            q = base + k * stride
            if q + 2 > n:
                ok = False
                break
            v = struct.unpack_from("<H", b, q)[0]
            if v <= prev or v > 0xFFFD:
                ok = False
                break
            prev = v
            cps.append(v)
        if ok:
            best.append((stride, base, cps[0], cps[-1]))
            break
for stride, base, lo, hi in best:
    print(f"  stride={stride:<3} base=0x{base:04x}  U+{lo:04X}..U+{hi:04X}")
