"""Extract + reverse FC5's .ffd (FireFontDescriptor) -- the per-glyph metrics table.

The font SWF (d27eb425d5b53ec6) maps every locale to a .ffd; ARABIC (all three font banks)
resolves to a single file:
    UI\\Common\\fonts\\Fire\\DIN_Mittelschrift_LT_W1G_Arabic.ffd  -> 236295edc3a3045b
so one font covers the whole hijacked UI.  This dumps it and probes the record layout by
looking for a codepoint column that ascends -- the structure then delimits itself.

  python -u dump_ffd.py
"""
import sys, os, struct, re, collections

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
from fc5_fat import Fat
from fc5_crc64 import name_hash

PC = os.path.join(os.environ.get("FC5_GAME", r"F:/SteamLibrary/steamapps/common/FarCry5"),
                  "data_final", "pc")
OUT = os.path.join(HERE, "..", "extract")
os.makedirs(OUT, exist_ok=True)

FFDS = {
    "arabic":  r"UI\Common\fonts\Fire\DIN_Mittelschrift_LT_W1G_Arabic.ffd",
    "default": r"UI\Common\fonts\Fire\DIN_Mittelschrift_LT_W1G_Default.ffd",
    "korean":  r"UI\Common\fonts\Fire\DIN_Mittelschrift_LT_W1G_Korean.ffd",
    "fcz_bold": r"UI\Common\fonts\Fire\FCZ_Bold_Default.ffd",
    "fcz_title": r"UI\Common\fonts\Fire\FCZ_Title_Default.ffd",
}
ATLASES = {
    0x4121034366bd73a3: "arabic 1024x1024",
    0xc44a353a7c4073c2: "latin  1024x1024",
    0xc44a353a7e9073c2: "latin? 512x1024",
    0x50803c20f249dc40: "?      1024x512",
    0x73205d587ef5a42a: "?      1024x512",
}

fats = {}
for q in ("common.fat", "patch.fat", "worlds/installpkg.fat"):
    p = os.path.join(PC, q)
    if os.path.exists(p):
        fats[q] = Fat(p)

for name, path in FFDS.items():
    h = name_hash(path)
    where = [(q, f.by_hash[h]) for q, f in fats.items() if h in f.by_hash]
    print(f"{name:11s} {h:016x}  {path}")
    if not where:
        print("    NOT FOUND\n")
        continue
    q, e = where[0]
    d = fats[q].read_data(e)
    open(os.path.join(OUT, f"{name}.ffd"), "wb").write(d)
    print(f"    {q}  unc={e.unc:,} sch={e.scheme}  head={d[:16].hex(' ')}")
    for hh, lbl in ATLASES.items():
        if struct.pack("<Q", hh) in d:
            print(f"    -> references atlas {hh:016x} ({lbl}) @0x{d.find(struct.pack('<Q', hh)):x}")
    print()

d = open(os.path.join(OUT, "arabic.ffd"), "rb").read()
n = len(d)
print(f"=== DIN_Mittelschrift_LT_W1G_Arabic.ffd  ({n:,} bytes) ===")
for i in range(0, min(320, n), 16):
    c = d[i:i + 16]
    print(f"  {i:06x}  {' '.join(f'{x:02x}' for x in c):<47}  "
          f"|{''.join(chr(x) if 32 <= x < 127 else '.' for x in c)}|")

print("\n--- strings")
for m in re.finditer(rb"[\x20-\x7e]{4,}", d):
    print(f"  0x{m.start():06x}  {m.group().decode('latin-1')!r}")

print("\n--- ascending u16/u32 columns (codepoint table hunt)")
best = []
for stride in range(4, 129, 2):
    for width in (2, 4):
        for base in range(0, min(2048, n - stride * 60), 2):
            prev = -1
            cps = []
            ok = True
            for k in range(60):
                q = base + k * stride
                if q + width > n:
                    ok = False; break
                v = struct.unpack_from("<H" if width == 2 else "<I", d, q)[0]
                if v <= prev or v > 0xFFFD:
                    ok = False; break
                prev = v; cps.append(v)
            if ok:
                # how far does it really run?
                k = 60
                while True:
                    q = base + k * stride
                    if q + width > n:
                        break
                    v = struct.unpack_from("<H" if width == 2 else "<I", d, q)[0]
                    if v <= prev or v > 0xFFFD:
                        break
                    prev = v; cps.append(v); k += 1
                best.append((len(cps), stride, width, base, cps[0], cps[-1]))
                break
best.sort(reverse=True)
for cnt, stride, width, base, lo, hi in best[:12]:
    print(f"  n={cnt:<5} stride={stride:<4} u{width*8} base=0x{base:04x}  U+{lo:04X}..U+{hi:04X}")
