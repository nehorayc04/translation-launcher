"""Full dump of FC5's font SWF (d27eb425d5b53ec6) -- the single resource that owns all
12 glyph atlases.  4,404 bytes, so everything can be printed."""
import sys, os, struct, re

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(HERE, "tools"))
sys.path.insert(0, os.path.join(HERE, "work"))
from fc5_fat import Fat
from fc5_crc64 import name_hash
import find_swf_fonts as F

PC = os.path.join(os.environ.get("FC5_GAME", r"F:/SteamLibrary/steamapps/common/FarCry5"),
                  "data_final", "pc")
H = 0xd27eb425d5b53ec6

f = Fat(os.path.join(PC, "common.fat"))
d = f.read_data(f.by_hash[H])
open(os.path.join(HERE, "extract", "fontswf.bin"), "wb").write(d)
print(f"{H:016x}  {len(d):,} bytes  head={d[:8]!r}\n")


def hexdump(data, off=0, n=None, indent="  "):
    n = len(data) if n is None else n
    for i in range(0, min(n, len(data)), 16):
        c = data[i:i + 16]
        hx = " ".join(f"{x:02x}" for x in c)
        asc = "".join(chr(x) if 32 <= x < 127 else "." for x in c)
        print(f"{indent}{off+i:06x}  {hx:<47}  |{asc}|")


print("=== tag stream ===")
sw = F.deobfuscate(d)
for code, payload in F.tags(sw):
    print(f"\n-- tag {code}  len={len(payload)}")
    if len(payload) <= 512:
        hexdump(payload)
    else:
        hexdump(payload, 0, 128)
        print("   ...")
        hexdump(payload, len(payload) - 64, 64)

print("\n=== all printable strings (>=4) ===")
for m in re.finditer(rb"[\x20-\x7e]{4,}", d):
    s = m.group().decode("latin-1")
    hh = name_hash(s)
    print(f"  0x{m.start():04x}  {s!r}   crc64={hh:016x}")

print("\n=== embedded u64s that are real resources ===")
known = {}
for q in ("common.fat", "patch.fat"):
    p = os.path.join(PC, q)
    if os.path.exists(p):
        for e in Fat(p).entries:
            known.setdefault(e.hash, (q, e.unc))
for off in range(0, len(d) - 8):
    h = struct.unpack_from("<Q", d, off)[0]
    if h in known:
        q, unc = known[h]
        print(f"  0x{off:04x}  {h:016x}  {q} unc={unc:,}")
