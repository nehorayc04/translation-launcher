#!/usr/bin/env python3
"""Deep diagnostic: true record layout, true scope, non-positional proof, bidi, split."""
import os, struct, json, importlib.util

HERE=os.path.dirname(os.path.abspath(__file__)); GAME=os.path.dirname(HERE)
EN=os.path.join(GAME,"extract","lang_english_text.xpps")
AR=os.path.join(GAME,"extract","lang_arabic_text.xpps")
TOOLS=os.path.join(GAME,"tools")
def load(n,p):
    s=importlib.util.spec_from_file_location(n,p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
alt=load("xpps_alt",os.path.join(TOOLS,"xpps_alt.py"))
old=load("xpps",os.path.join(TOOLS,"xpps.py"))

d=open(EN,"rb").read()
base=struct.unpack_from("<I",d,0x28)[0]
trailer=struct.unpack_from("<I",d,0x2c)[0]
print(f"EN size={len(d)} base={base} trailer_start(0x2c)={trailer} tail={len(d)-trailer}")

# 1. Find the first index table via alt's scanner and dump raw records
tabs=list(alt._iter_tables(d,8))
print(f"\nALT tables found: {len(tabs)}  (start,count):")
for s,c in tabs[:12]:
    print(f"   @0x{s:x} count={c}")
totrec=sum(c for _,c in tabs)
print(f"ALT total records across tables = {totrec}")

# Dump raw bytes of the first 6 records of the first table, decode BOTH ways
s0,c0=tabs[0]
print(f"\n--- raw 16B records @0x{s0:x} (first table) decoded both ways ---")
for j in range(6):
    p=s0+j*16
    raw=d[p:p+16]
    a_key,a_off=struct.unpack_from("<QQ",d,p)          # alt: u64 key, u64 off
    o_z,o_A,o_g,o_off=struct.unpack_from("<IIII",d,p)  # old: u32 z,A,GROUP,off
    # what string does each offset point at?
    def strat(o):
        pp=base+o
        if pp<=0 or pp>=len(d): return "<oob>"
        e=d.find(b"\x00",pp);
        return d[pp:e].decode("utf-8","replace")[:30] if e>0 else "<no-nul>"
    print(f"  rec{j} {raw.hex()}")
    print(f"     ALT key={a_key:016x} off={a_off}  -> {strat(a_off)!r}  (byte before ok={d[base+a_off-1]==0 if 0<base+a_off<len(d) else '?'})")
    print(f"     OLD z={o_z} A={o_A:x} g={o_g:x} off={o_off} -> {strat(o_off)!r}")

# 2. TRUE scope: count NUL-terminated UTF-8 strings in the pool [base..first-table]
#    to sanity-check against reader counts.
pool_end=min(s for s,_ in tabs)   # first table start ~ end of pool
seg=d[base:pool_end]
raw_strs=[x for x in seg.split(b"\x00")]
decodable=0; nonempty=0
for x in raw_strs:
    if not x: continue
    try:
        x.decode("utf-8"); decodable+=1
        if x.strip(): nonempty+=1
    except: pass
print(f"\nPool [0x{base:x}..0x{pool_end:x}] raw NUL-split decodable UTF-8 chunks={decodable} nonempty={nonempty}")

# 3. Reader scope + key-kind split (alt)
en_alt=alt.read_pack(EN); ar_alt=alt.read_pack(AR)
big=sum(1 for k in en_alt if int(k,16)>0xffffffff); small=len(en_alt)-big
print(f"\nALT EN={len(en_alt)} AR={len(ar_alt)}  large-hash-keys={big} small-ids={small}")

# 4. NON-POSITIONAL proof: for shared keys, compare the ORDER index in EN vs AR.
en_ord=alt.read_pack(EN.replace('x','x'),ordered=False)  # dict
en_list=alt.read_pack(EN,ordered=True); ar_list=alt.read_pack(AR,ordered=True)
en_pos={k:i for i,(k,_) in enumerate(en_list)}
ar_pos={k:i for i,(k,_) in enumerate(ar_list)}
common=set(en_pos)&set(ar_pos)
disagree=sum(1 for k in common if en_pos[k]!=ar_pos[k])
print(f"\nNON-POSITIONAL: {len(common)} shared keys; positions differ EN vs AR for {disagree} of them "
      f"({round(100*disagree/len(common),1)}%)  -> if high, join is by KEY not position")
# show 3 keys with very different positions but valid translation
ex=[k for k in sorted(common) if abs(en_pos[k]-ar_pos[k])>50][:4]
for k in ex:
    print(f"   key {k}: EN idx {en_pos[k]} AR idx {ar_pos[k]}  EN={en_alt[k]!r} AR={ar_alt[k]!r}")

# 5. Known UI anchors: Continue/Options/Subtitles/New Game -> find key, check AR translation
print("\nANCHORS (UI):")
for w in ["Continue","Options","Subtitles","New Game","Load Game","Main Menu"]:
    hit=[(k,v) for k,v in en_alt.items() if v==w]
    for k,v in hit[:1]:
        print(f"   {w!r} key={k} -> AR={ar_alt.get(k)!r}")

# 6. BIDI verdict
print("\nBIDI:")
try:
    from bidi.algorithm import get_display
    have=True
except Exception as e:
    have=False; print("   python-bidi NOT available:",e)
# take a known arabic UI string, check stored order vs logical
sample=ar_alt.get([k for k,v in en_alt.items() if v=="Options"][0]) if [k for k,v in en_alt.items() if v=="Options"] else None
# generic: first arabic value
for k,v in ar_alt.items():
    if any('؀'<=c<='ۿ' for c in v) and len(v)>6:
        sample_k=k; sample=v; break
print(f"   sample AR key={sample_k} stored={sample!r}")
if have:
    disp=get_display(sample)
    print(f"   get_display(stored)={disp!r}")
    print(f"   stored==logical? (if get_display changes it, engine expects LOGICAL & does bidi itself)")
    print(f"   stored != display -> {sample!=disp}")
# Check: is a known phrase's first word the semantic first word (logical) ?
