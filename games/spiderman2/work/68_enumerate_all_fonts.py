"""Enumerate EVERY standard-sfnt font asset in d/userinterface by content
(not by path). Extract each asset; if it starts with an sfnt magic, parse its
family + Hebrew coverage. This finds the lowercase azbukapro_regular_normal
fonts (and any other) we couldn't locate by path-CRC64, so we can swap every
font that lacks Hebrew. Writes a manifest of (asset_idx, family, HEB, size)."""
import os, sys, struct, json
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib

MAGICS = (b"\x00\x01\x00\x00", b"OTTO", b"ttcf", b"true")

def parse(data):
    """family, hebrew_count, arabic_count for a STANDARD sfnt at offset 0."""
    nt = struct.unpack(">H", data[4:6])[0]
    if not (1 <= nt <= 60):
        return None
    t = {}
    for k in range(nt):
        rec = data[12+k*16:12+(k+1)*16]
        if len(rec) < 16:
            return None
        t[rec[:4]] = struct.unpack(">II", rec[8:16])
    fam = "?"
    if b"name" in t:
        off, ln = t[b"name"]; n = data[off:off+ln]
        if len(n) >= 6:
            cnt, soff = struct.unpack(">HH", n[2:6]); strings = n[soff:]
            for i in range(cnt):
                r = n[6+i*12:6+(i+1)*12]
                if len(r) < 12: break
                pl, en, lg, nid, sl, sr = struct.unpack(">HHHHHH", r)
                if nid == 1 and pl == 3 and sr+sl <= len(strings):
                    try: fam = strings[sr:sr+sl].decode("utf-16-be","replace"); break
                    except: pass
    heb = ara = 0
    if b"cmap" in t:
        off, ln = t[b"cmap"]; c = data[off:off+ln]
        if len(c) >= 4:
            num = struct.unpack(">H", c[2:4])[0]; best=None
            for k in range(num):
                if 4+k*8+8 > len(c): break
                pl,en,so = struct.unpack(">HHI", c[4+k*8:12+k*8])
                if (pl==0) or (pl==3 and en in (1,10)): best=so
            if best is not None and best < len(c):
                sub=c[best:]; fmt=struct.unpack(">H",sub[:2])[0]; cps=set()
                try:
                    if fmt==4:
                        seg=struct.unpack(">H",sub[6:8])[0]//2; eo=14; so=eo+2*seg+2
                        end=struct.unpack(f">{seg}H",sub[eo:eo+2*seg]); st=struct.unpack(f">{seg}H",sub[so:so+2*seg])
                        for a,b in zip(st,end):
                            if a!=0xFFFF: cps.update(range(a,min(b,0xFFFF)+1))
                    elif fmt==12:
                        ng=struct.unpack(">I",sub[12:16])[0]
                        for g in range(ng):
                            sc,ec,_=struct.unpack(">III",sub[16+g*12:28+g*12])
                            if ec-sc<70000: cps.update(range(sc,ec+1))
                except: pass
                heb=sum(1 for x in cps if 0x590<=x<=0x5FF); ara=sum(1 for x in cps if 0x600<=x<=0x6FF)
    return fam, heb, ara

with open(os.path.join(GAME, "toc"), "rb") as f:
    toc = dat1lib.read(f)
toc.set_archives_dir(GAME)
archs = toc.get_archives_section().archives
ui_arch = next(i for i,a in enumerate(archs)
               if bytes(a.filename).split(b"\x00")[0].decode("ascii","replace").endswith("userinterface"))
ids = toc.get_assets_section().ids

fonts = []
checked = 0
for idx in range(len(ids)):
    e = toc.get_asset_entry_by_index(idx)
    if not e or e.archive != ui_arch:
        continue
    if e.size < 4000 or e.size > 30_000_000:
        continue
    try:
        d = bytes(toc.extract_asset(e))
    except Exception:
        continue
    checked += 1
    # standard sfnt at 0, OR after an 8-byte Insomniac prefix
    for base in (0, 8):
        if d[base:base+4] in MAGICS:
            r = parse(d[base:])
            if r:
                fam, heb, ara = r
                fonts.append({"idx": idx, "aid": f"{e.asset_id:016X}",
                              "size": e.size, "base": base, "family": fam,
                              "heb": heb, "ara": ara})
            break

fonts.sort(key=lambda x: (x["heb"], -x["size"]))
print(f"[*] checked {checked} assets, found {len(fonts)} sfnt fonts\n")
print(f"{'idx':>8} {'asset_id':>17} {'size':>9} {'base':>4} {'HEB':>5} {'ARA':>5}  family")
for x in fonts:
    flag = "  <-- NO HEBREW" if x["heb"] < 5 else ""
    print(f"{x['idx']:>8} {x['aid']:>17} {x['size']:>9} {x['base']:>4} "
          f"{x['heb']:>5} {x['ara']:>5}  {x['family']!r}{flag}")

out = os.path.join(HERE, "all_ui_fonts.json")
json.dump(fonts, open(out, "w"), indent=1)
print(f"\n[+] manifest -> {out}")
