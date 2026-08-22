"""Extract the game's own Hebrew font 'Aguda for Insomniac' (assets 426245 reg,
300766 bold) as standard .ttf, and report Hebrew/Latin/Arabic coverage. If it
covers Hebrew + Latin it's the ideal in-game-styled replacement (vs plain
Arial)."""
import os, sys, struct
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
OUT  = os.path.join(ROOT, "games", "spiderman2", "extracted", "aguda")
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib

TARGETS = {426245: "Aguda-Regular.ttf", 300766: "Aguda-Bold.ttf"}

def cov(data):
    nt = struct.unpack(">H", data[4:6])[0]; t={}
    for k in range(nt):
        r=data[12+k*16:12+(k+1)*16]; t[r[:4]]=struct.unpack(">II",r[8:16])
    fam="?"
    if b"name" in t:
        off,ln=t[b"name"]; n=data[off:off+ln]; cnt,so=struct.unpack(">HH",n[2:6]); s=n[so:]
        for i in range(cnt):
            r=n[6+i*12:6+(i+1)*12]
            if len(r)<12: break
            pl,en,lg,nid,sl,sr=struct.unpack(">HHHHHH",r)
            if nid==1 and pl==3 and sr+sl<=len(s):
                fam=s[sr:sr+sl].decode("utf-16-be","replace"); break
    cps=set()
    if b"cmap" in t:
        off,ln=t[b"cmap"]; c=data[off:off+ln]; num=struct.unpack(">H",c[2:4])[0]; best=None
        for k in range(num):
            pl,en,so=struct.unpack(">HHI",c[4+k*8:12+k*8])
            if pl==3 and en==10: best=so; break
            if (pl==0) or (pl==3 and en==1): best=so
        if best:
            sub=c[best:]; fmt=struct.unpack(">H",sub[:2])[0]
            if fmt==4:
                seg=struct.unpack(">H",sub[6:8])[0]//2; eo=14; so2=eo+2*seg+2
                end=struct.unpack(f">{seg}H",sub[eo:eo+2*seg]); st=struct.unpack(f">{seg}H",sub[so2:so2+2*seg])
                for a,b in zip(st,end):
                    if a!=0xFFFF: cps.update(range(a,min(b,0xFFFF)+1))
            elif fmt==12:
                ng=struct.unpack(">I",sub[12:16])[0]
                for g in range(ng):
                    sc,ec,_=struct.unpack(">III",sub[16+g*12:28+g*12])
                    if ec-sc<70000: cps.update(range(sc,ec+1))
    def c2(lo,hi): return sum(1 for x in cps if lo<=x<=hi)
    return fam, c2(0x590,0x5FF), c2(0x41,0x7A), c2(0x600,0x6FF), len(cps)

with open(os.path.join(GAME,"toc"),"rb") as f:
    toc=dat1lib.read(f)
toc.set_archives_dir(GAME)
for idx,name in TARGETS.items():
    e=toc.get_asset_entry_by_index(idx)
    d=bytes(toc.extract_asset(e))
    open(os.path.join(OUT,name),"wb").write(d)
    fam,heb,lat,ara,tot=cov(d)
    print(f"{name}: head={d[:4].hex()} size={len(d)} family={fam!r}")
    print(f"   HEB={heb}/112  LAT={lat}/58  ARA={ara}/256  total_glyphs={tot}")
print(f"\nsaved -> {OUT}")
