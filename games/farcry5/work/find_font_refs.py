"""Find the resource that OWNS the font atlas.

We now know the Arabic glyph atlas by CONTENT (flat-white RGB + all information in alpha):
    4121034366bd73a3   1024x1024   arabic
    c44a353a7c4073c2   1024x1024   latin/cyrillic
The pixels alone are not addressable -- something must say "codepoint X lives at rect Y with
advance Z".  In Dunia every resource points at another by its u64 name hash, so the metrics
record is simply whichever resource CONTAINS those 8 bytes.

  python -u find_font_refs.py [hash ...]      -> prints every referencing entry
"""
import sys, os, struct

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from fc5_fat import Fat

PC = os.path.join(os.environ.get("FC5_GAME", r"F:/SteamLibrary/steamapps/common/FarCry5"),
                  "data_final", "pc")

TARGETS = [int(x, 16) for x in sys.argv[1:]] or [0x4121034366bd73a3, 0xc44a353a7c4073c2]
ARCHIVES = ["common.fat", "patch.fat", "worlds/installpkg.fat"]

needles = {}
for h in TARGETS:
    needles[struct.pack("<Q", h)] = (h, "LE")
    needles[struct.pack(">Q", h)] = (h, "BE")
    # Dunia also stores hashes high-word-first as two u32 (see the FAT entry layout)
    needles[struct.pack("<II", (h >> 32) & 0xFFFFFFFF, h & 0xFFFFFFFF)] = (h, "HI/LO")

print("searching for:")
for h in TARGETS:
    print(f"  {h:016x}")
print()

for arch in ARCHIVES:
    p = os.path.join(PC, arch)
    if not os.path.exists(p):
        continue
    f = Fat(p)
    print(f"### {arch} ({f.count:,} entries)", flush=True)
    hits = 0
    for i, e in enumerate(f.entries):
        if e.unc > 32_000_000 or e.unc < 8:
            continue
        try:
            b = f.read_data(e)
        except Exception:
            continue
        for nd, (h, kind) in needles.items():
            off = b.find(nd)
            if off >= 0:
                hits += 1
                head = b[:4]
                print(f"  {e.hash:016x} unc={e.unc:<9,} sch={e.scheme} "
                      f"ref={h:016x} as {kind} @0x{off:x}  head={head!r}", flush=True)
        if i % 20000 == 0 and i:
            print(f"    .. {i:,}/{f.count:,}", flush=True)
    print(f"### {arch}: {hits} referencing entries\n", flush=True)
