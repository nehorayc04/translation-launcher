import os,re,struct,glob,io
D=r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acblackflag\work\fontsys"
try:
    from fontTools.ttLib import TTFont
except ImportError:
    print("NO fontTools"); raise SystemExit
def find_sfnt(b):
    for m in re.finditer(rb"\x00\x01\x00\x00|OTTO", b):
        o=m.start()
        if o+12>len(b): continue
        nt,=struct.unpack_from(">H",b,o+4)
        if 3<=nt<=64 and re.fullmatch(rb"[A-Za-z0-9/ ]{4}",b[o+12:o+16]): return o,nt
    return None,None
def rng(cps,a,b): return sum(1 for c in cps if a<=c<=b)
rows=[]
for f in sorted(glob.glob(os.path.join(D,"PhoenixFont_*.bin")))+sorted(glob.glob(os.path.join(D,"FontFile_*.bin"))):
    b=open(f,"rb").read(); o,nt=find_sfnt(b)
    base=os.path.basename(f)
    if o is None: print(f"{base:44s} no sfnt"); continue
    # sfnt length = max(tableOffset+len)
    end=0
    for i in range(nt):
        tag,ck,off,ln=struct.unpack_from(">4sIII",b,o+12+16*i); end=max(end,off+ln)
    sub=b[o:o+end]
    try:
        tf=TTFont(io.BytesIO(sub),fontNumber=0,lazy=True)
        cps=set(tf.getBestCmap().keys())
        try: name=tf["name"].getDebugName(4) or tf["name"].getDebugName(1)
        except: name="?"
        print(f"{base:44s} sfnt@{o:<5} len={end:>9,} glyphs={tf['maxp'].numGlyphs:>6} '{name}'")
        print(f"      cps={len(cps):>6}  HEBREW(0590-05FF)={rng(cps,0x590,0x5FF):>3}  "
              f"ARABIC(0600-06FF)={rng(cps,0x600,0x6FF):>3}  PresA={rng(cps,0xFB50,0xFDFF):>3}  "
              f"PresB={rng(cps,0xFE70,0xFEFF):>3}  Latin={rng(cps,0x20,0x24F):>3}  CJK={rng(cps,0x4E00,0x9FFF):>5}  Hangul={rng(cps,0xAC00,0xD7A3):>5}")
    except Exception as e:
        print(f"{base:44s} sfnt@{o} parse fail: {e}")
