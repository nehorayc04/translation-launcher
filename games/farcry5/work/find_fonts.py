"""Locate every embedded font in FC5 and report Latin / Arabic / Hebrew cmap coverage.

Rule (learned on AC Unity): the sfnt magic matches huge amounts of random binary --
require a plausible table directory AND a successful fontTools load before believing it.
"""
import sys, os, glob, io, struct, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from fc5_fat import Fat
from fontTools.ttLib import TTFont

G = os.environ.get("FC5_GAME", r"F:/SteamLibrary/steamapps/common/FarCry5")
PC = os.path.join(G, "data_final", "pc")
SFNT = (b"\x00\x01\x00\x00", b"OTTO", b"true", b"ttcf")

HEB = range(0x05D0, 0x05EB)
LAT = range(0x0041, 0x005B)
ARA = range(0x0620, 0x0650)

archives = [a for a in sorted(glob.glob(PC + "/**/*.fat", recursive=True))
            if os.path.getsize(a) >= 64]
print(f"scanning {len(archives)} archives for fonts ...\n")

rows = []
for ap in archives:
    try:
        f = Fat(ap)
    except Exception:
        continue
    if not os.path.exists(f.dat_path):
        continue
    rel = os.path.relpath(ap, PC)
    fh = open(f.dat_path, "rb")
    for e in f.entries:
        if not (4000 <= e.unc <= 30_000_000):
            continue
        try:
            if e.scheme == 0:
                fh.seek(e.off); head = fh.read(12)
            else:
                head = f.read_data(e)[:12]
        except Exception:
            continue
        if len(head) < 12 or head[:4] not in SFNT:
            continue
        numTables = struct.unpack_from(">H", head, 4)[0]
        if not (3 <= numTables <= 64):        # table-directory sanity
            continue
        try:
            data = f.read_data(e)
            ft = TTFont(io.BytesIO(data), fontNumber=0, lazy=True)
            cmap = ft.getBestCmap()
        except Exception:
            continue
        name = ""
        try:
            name = ft["name"].getDebugName(4) or ft["name"].getDebugName(1) or ""
        except Exception:
            pass
        outl = "glyf" if "glyf" in ft else ("CFF " if "CFF " in ft else "?")
        rows.append(dict(arch=rel, hash=e.hash, size=e.unc, name=name, outlines=outl,
                         lat=sum(1 for c in LAT if c in cmap),
                         ara=sum(1 for c in ARA if c in cmap),
                         heb=sum(1 for c in HEB if c in cmap),
                         glyphs=len(cmap)))
    fh.close()

print(f"{'archive':30s} {'hash':16s} {'size':>9s} {'out':5s} {'lat':>4s} {'ara':>4s} {'heb':>4s} {'cmap':>6s}  name")
for r in sorted(rows, key=lambda r: (r["arch"], -r["size"])):
    print(f"{r['arch']:30s} {r['hash']:016x} {r['size']:>9,} {r['outlines']:5s} "
          f"{r['lat']:>4}/26 {r['ara']:>4}/48 {r['heb']:>4}/27 {r['glyphs']:>6} {r['name']}")

print(f"\nTOTAL fonts: {len(rows)}")
heb_ok = [r for r in rows if r["heb"] >= 27]
print(f"fonts already covering all 27 Hebrew letters: {len(heb_ok)}")
ara_ok = [r for r in rows if r["ara"] >= 20]
print(f"fonts covering Arabic (the slot we hijack):   {len(ara_ok)}")
for r in ara_ok:
    print(f"   -> {r['arch']} {r['hash']:016x} heb={r['heb']}/27  {r['name']}")
