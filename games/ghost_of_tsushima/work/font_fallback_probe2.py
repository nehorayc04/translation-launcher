#!/usr/bin/env python3
"""Probe 2: (a) where does the launcher get its font bytes (is Launcher_Font a
real TTF fed to AddFontMemResourceEx, and does it carry Hebrew or rely on GDI
font-linking)?  (b) any font config/ini/registry the game reads?  (c) confirm
the GDI text APIs form ONE launcher blit sequence, separate from fOnk.

READ-ONLY. Verified against real files."""
import re, os, glob

EXE = r"F:/Games/Ghost of Tsushima DC/GhostOfTsushima.exe"
GAMEDIR = r"F:/Games/Ghost of Tsushima DC"

def load(p):
    with open(p, "rb") as f:
        return f.read()

def find_all(buf, needle, limit=50):
    out = []
    i = buf.find(needle)
    while i != -1 and len(out) < limit:
        out.append(i); i = buf.find(needle, i + 1)
    return out

def ascii_run(buf, off, back=250, fwd=250):
    lo, hi = max(0, off-back), min(len(buf), off+fwd)
    cur=bytearray(); start=lo; toks=[]
    for i in range(lo,hi):
        b=buf[i]
        if 0x20<=b<0x7f:
            if not cur: start=i
            cur.append(b)
        else:
            if len(cur)>=3: toks.append(cur.decode())
            cur=bytearray()
    if len(cur)>=3: toks.append(cur.decode())
    return toks

def sfnt_scan(buf, tag=b""):
    """Find valid sfnt headers (0x00010000 / 'OTTO' / 'true' / 'ttcf') validated
    by plausible table-tag first entry."""
    magics = [b"\x00\x01\x00\x00", b"OTTO", b"true", b"ttcf", b"typ1"]
    good = []
    for m in magics:
        for off in find_all(buf, m, limit=200):
            # numTables at off+4 (u16 BE)
            if off+12 > len(buf): continue
            numTables = int.from_bytes(buf[off+4:off+6], "big")
            if not (1 <= numTables <= 40): continue
            tag0 = buf[off+12:off+16]
            if all(0x20<=c<0x7f for c in tag0) and tag0.isalnum() or tag0 in (b"cmap",b"head",b"glyf",b"OS/2",b"name",b"GDEF",b"CFF ",b"maxp",b"post",b"hhea",b"hmtx",b"loca"):
                good.append((off, m, numTables, tag0))
    return good

def main():
    buf = load(EXE)
    print("== A. Launcher_Font byte context (what feeds AddFontMemResourceEx) ==")
    for off in find_all(buf, b"Launcher_Font"):
        # show raw bytes around to see if it's a key list or a filename/path
        lo,hi = max(0,off-32), min(len(buf), off+64)
        print(f"  @0x{off:X}: {buf[lo:hi]!r}")

    print("\n== B. is there ANY valid sfnt (TTF/OTF) in the exe? ==")
    g = sfnt_scan(buf)
    print(f"  valid sfnt headers found: {len(g)}")
    for off,m,n,t in g[:10]:
        print(f"    @0x{off:X} magic={m!r} tables={n} tag0={t!r}")

    print("\n== C. Launcher_Font / launcher assets in game data packages ==")
    # search cache + extract for the launcher font resource
    roots = [
        os.path.join(GAMEDIR, "cache_pc"),
        r"c:/Users/Nehoray_Cohen/Projects/Game translator/games/ghost_of_tsushima/extract",
    ]
    needles = [b"Launcher_Font", b"Launcher_Bitmap_Background", b"Launcher_Icon"]
    for root in roots:
        if not os.path.isdir(root):
            print(f"  (missing {root})"); continue
        files = []
        for dp,_,fns in os.walk(root):
            for fn in fns:
                files.append(os.path.join(dp,fn))
        print(f"  {root}: {len(files)} files")
        for fp in files:
            try:
                sz = os.path.getsize(fp)
                if sz > 300_000_000: continue
                b = load(fp)
            except Exception as e:
                continue
            for nd in needles:
                if nd in b:
                    hits = find_all(b, nd, limit=3)
                    print(f"    HIT {nd.decode():26s} in {os.path.basename(fp)} @{['0x%X'%h for h in hits]}")

    print("\n== D. font config / ini / registry keys the game reads ==")
    strs = []
    cur=bytearray(); start=0
    for i,b in enumerate(buf):
        if 0x20<=b<0x7f:
            if not cur: start=i
            cur.append(b)
        else:
            if len(cur)>=4: strs.append((start,cur.decode()))
            cur=bytearray()
    pat = re.compile(r"(\.ini|\.cfg|\.json|settings|Settings|SOFTWARE\\|Software\\|"
                     r"Sucker Punch|SuckerPunch|Nixxes|\.xml|Font|FONT)", )
    hits = [(o,s) for o,s in strs if pat.search(s)]
    # narrow to font-ish + config-ish
    fontcfg = [(o,s) for o,s in hits if re.search(r"[Ff]ont", s)]
    print(f"  strings containing 'font'/'Font'/'FONT': {len(fontcfg)}")
    for o,s in fontcfg[:60]:
        print(f"    0x{o:08X} {s!r}")

    print("\n== E. registry paths (RegOpenKeyExW/A targets) ==")
    reg = [(o,s) for o,s in strs if ("SOFTWARE\\" in s or "Software\\" in s)]
    for o,s in reg[:30]:
        print(f"    0x{o:08X} {s!r}")

if __name__ == "__main__":
    main()
