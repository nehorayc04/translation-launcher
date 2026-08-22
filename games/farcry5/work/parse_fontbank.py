"""Reverse the FC5 font bank layout (cf402ed3ebb8872f).

The head is a 154-entry table of {u32,u32,u64 hash}; further in sits a contiguous array of
every glyph-atlas hash (verified against the 10 atlases found by CONTENT).  This walks the
file resolving every u64 against the real archives, so the structure delimits itself instead
of being guessed.

  python -u parse_fontbank.py
"""
import sys, os, struct, glob

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from fc5_fat import Fat

PC = os.path.join(os.environ.get("FC5_GAME", r"F:/SteamLibrary/steamapps/common/FarCry5"),
                  "data_final", "pc")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "extract")
b = open(os.path.join(OUT, "fontbank.bin"), "rb").read()
n = len(b)

# every hash the game actually ships, so a u64 can be classified as "real resource" or noise
known = {}
for q in ("common.fat", "patch.fat", "worlds/installpkg.fat"):
    p = os.path.join(PC, q)
    if os.path.exists(p):
        f = Fat(p)
        for e in f.entries:
            known.setdefault(e.hash, (q, e.unc, e.scheme))
print(f"known hashes: {len(known):,}\n")

# ---- where does a u64 resolve to a real resource?
hits = []
for off in range(0, n - 8):
    h = struct.unpack_from("<Q", b, off)[0]
    if h in known:
        hits.append((off, h))
print(f"u64 positions resolving to a real resource: {len(hits)}")

# group into contiguous 8-aligned runs
runs = []
cur = []
for off, h in hits:
    if cur and off - cur[-1][0] == 8:
        cur.append((off, h))
    else:
        if len(cur) >= 2:
            runs.append(cur)
        cur = [(off, h)]
if len(cur) >= 2:
    runs.append(cur)
print(f"contiguous runs (stride 8): {len(runs)}")
for r in runs:
    print(f"  @0x{r[0][0]:06x} .. 0x{r[-1][0]:06x}  n={len(r)}")
    for off, h in r:
        q, unc, sch = known[h]
        print(f"      0x{off:06x} {h:016x}  {q:<22} unc={unc:<10,} sch={sch}")
print()

# stride-16 hits (the head table)
h16 = [(o, h) for o, h in hits if (o - 12) % 16 == 0 and o < 0x9a4 + 16]
print(f"head-table hashes at (off-12)%16==0 below 0x9b4: {len(h16)}")
cnt = struct.unpack_from("<I", b, 0)[0]
print(f"head count field = {cnt}  -> table would end at 0x{4 + cnt*16:x}\n")

print("--- head table (first 12)")
for i in range(min(12, cnt)):
    o = 4 + i * 16
    a, c = struct.unpack_from("<II", b, o)
    h = struct.unpack_from("<Q", b, o + 8)[0]
    tag = ""
    if h in known:
        q, unc, sch = known[h]
        tag = f"  <- {q} unc={unc:,}"
    print(f"  [{i:3}] a={a:<8} c={c:<6} hash={h:016x}{tag}")

print("\n--- what sits right after the head table")
end = 4 + cnt * 16
for i in range(0, 192, 16):
    off = end + i
    if off + 16 > n:
        break
    chunk = b[off:off + 16]
    hx = " ".join(f"{c:02x}" for c in chunk)
    asc = "".join(chr(c) if 32 <= c < 127 else "." for c in chunk)
    print(f"  {off:06x}  {hx:<47}  |{asc}|")

print("\n--- u16 values in [1,1024] density per 1KB block (atlas-rect hunting)")
for blk in range(0, n, 1024):
    seg = b[blk:blk + 1024]
    vals = struct.unpack_from("<" + "H" * (len(seg) // 2), seg, 0)
    good = sum(1 for v in vals if 1 <= v <= 1024)
    print(f"  0x{blk:05x}  {good:4}/{len(vals):4}  {'#' * (good * 40 // max(1,len(vals)))}")
