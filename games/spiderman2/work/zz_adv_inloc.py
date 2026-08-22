"""Confirm the descriptions analyzed by the bidi sim actually exist (byte-identical)
in the DEPLOYED arabic_patched_hebrew_menu.localization. The sim reads *_he.json;
the game reads the .localization. Prove they agree for a sample + count."""
import os, sys, io, struct, json, re
HERE=os.path.dirname(os.path.abspath(__file__))
ROOT=os.path.abspath(os.path.join(HERE,"..","..",".."))
sys.path.insert(0, os.path.join(ROOT,"games","spiderman2","tools","ALERT"))
import dat1lib, dat1lib.types.dat1
RLM="‏"
def has_heb(s): return any("א"<=c<="ת" for c in s)

LOC=os.path.join(HERE,"arabic_patched_hebrew_menu.localization")
raw=open(LOC,"rb").read(); pay=raw[36:]
d=dat1lib.types.dat1.DAT1(io.BytesIO(pay),None)
secs={sh.tag:(sh.offset,sh.size) for sh in d.header.sections}
def sec(tag): o,s=secs[tag]; return pay[o:o+s]
TAG_VALUES=0x70A382B8; TAG_KEYS=0x4D73CEBD; TAG_TEXT_OFFSETS=0xF80DEEB4
TAG_KEY_OFFSETS=0xA4EA55B2; TAG_ENTRY_COUNT=0xD540A903
cnt=struct.unpack("<I",sec(TAG_ENTRY_COUNT))[0]
keys=sec(TAG_KEYS); vals=sec(TAG_VALUES)
toff=list(struct.unpack(f"<{cnt}I",sec(TAG_TEXT_OFFSETS)))
koff=list(struct.unpack(f"<{cnt}I",sec(TAG_KEY_OFFSETS)))
def cstr(buf,off):
    e=buf.find(b"\x00",off); e=e if e>=0 else len(buf); return buf[off:e]
loc={}
for i in range(cnt):
    k=cstr(keys,koff[i]).decode("utf-8","replace")
    v=cstr(vals,toff[i]).decode("utf-8","replace")
    loc[k]=v

# source descriptions
src={}
for fn in ["settings_he.json"]+[f"menus{n}_he.json" for n in range(2,14)]+["menus_he.json"]:
    p=os.path.join(HERE,fn)
    if not os.path.exists(p): continue
    for k,v in json.load(open(p,encoding="utf-8")).items():
        if isinstance(v,str) and v.startswith(RLM) and has_heb(v): src.setdefault(k,v)

present=0; mismatch=0; absent=[]
for k,v in src.items():
    if k not in loc: absent.append(k); continue
    if loc[k]==v: present+=1
    else: mismatch+=1
print(f"description keys in sim: {len(src)}")
print(f"  present & byte-identical in deployed .localization: {present}")
print(f"  present but DIFFERENT value: {mismatch}")
print(f"  ABSENT from .localization: {len(absent)}")
if absent[:10]: print("   sample absent:", absent[:10])
# spot 3
for k in list(src)[:3]:
    print(f"   sample {k}: loc has RLM-prefixed = {loc.get(k,'')[:1]==RLM}")
