import importlib.util, os, struct, sys, json, time, re, zlib
HERE=r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acblackflag\work"
TOOLS=os.path.join(HERE,"..","tools")
INJ=os.path.join(HERE,"refmods","injector","oo2core_9_win64.dll")
os.environ["ACS_OODLE_DLL"]=INJ
def _load(n):
    p=os.path.join(TOOLS,n+".py"); s=importlib.util.spec_from_file_location(n,p)
    m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
AF=_load("acbf_forge"); CFD=_load("acbf_cfd")
sys.path.insert(0, os.path.join(HERE,"..","..","acshadows","tools"))
from acs_oodle import Oodle
GAME=r"C:\Games\Assassin's Creed Black Flag Resynced"
FN=os.path.join(GAME,"DataPC_boot.forge")
OUT=os.path.join(HERE,"fontsys"); os.makedirs(OUT,exist_ok=True)
def decode_record(f,r,oo):
    f.seek(r["offset"]); blob=f.read(r["size"]); out=bytearray(); off=0
    while off+19<=len(blob) and struct.unpack_from("<Q",blob,off)[0]==CFD.MAGIC:
        cnt=struct.unpack_from("<i",blob,off+15)[0]; bi=off+19
        binfo=[struct.unpack_from("<ii",blob,bi+8*i) for i in range(cnt)]
        p=bi+cnt*8
        for u,c in binfo:
            p+=4; d=blob[p:p+c]; p+=c
            out += d if c==u else oo.decompress(d,u)
        off=p
    return bytes(out)
CLS={0xa6ea7232:"PhoenixFont",0x9bb2cdf2:"PhoenixFontData",0x669403b9:"PhoenixLocalizedFontData",
     0x61d83bba:"FontManager",0xc46b4618:"FontFile",0xa50273b2:"OfflineGlyphs",
     0x4802a946:"LivePreloadFont",0x005557b9:"PhoenixTextStyleData"}
oo=Oodle(INJ); info=AF.parse(FN); recs=info["recs"]
f=open(FN,"rb"); idxmap={}
for i,r in enumerate(recs):
    if r["hash"] in CLS: idxmap.setdefault(r["hash"],[]).append(i)
for h,lst in idxmap.items():
    print(f"\n=== 0x{h:08x} {CLS[h]}  x{len(lst)} ===")
    for i in lst[:30]:
        r=recs[i]
        try: dec=decode_record(f,r,oo)
        except Exception as e: print(f"  idx {i}: decode fail {e}"); continue
        nm=f"{CLS[h]}_{i}_{r['ts']:08x}.bin"
        open(os.path.join(OUT,nm),"wb").write(dec)
        strs=sorted(set(s.decode('ascii') for s in re.findall(rb"[ -~]{5,}",dec)))
        sfnt = dec.count(b"\x00\x01\x00\x00")
        print(f"  idx {i:>6} fid=0x{r['ts']:08x} flags=0x{r['flags']:x} disk={r['size']:>9,} dec={len(dec):>10,}  strs={len(strs)}")
        for s in strs[:14]: print(f"        {s!r}")
f.close(); print("\n-> ", OUT)
