import os,sys,struct
sys.path.insert(0,"games/acvalhalla/tools"); sys.path.insert(0,"games/acshadows/tools"); sys.path.insert(0,"games/acunity/work")
from mirage_forge import Forge
from mirage_loc import MARKER
from acu_loc import decode_payload
import acs_cfd
try: sys.stdout.reconfigure(encoding="utf-8",errors="replace")
except: pass
od=acs_cfd._oodle()
fg=Forge(r"C:\Games\Assassin's Creed Valhalla\DataPC.forge")
pkgs=[]
for e in fg.entries:
    try: cfds,_=acs_cfd.decode_resource(fg.read(e),od)
    except: continue
    content=b"".join(d for d,_ in cfds)
    mk=content.find(struct.pack("<I",MARKER))
    if mk<0: continue
    typ=struct.unpack_from("<i",content,mk-16)[0]
    cnt=struct.unpack_from("<i",content,mk+4)[0]
    if cnt==0: continue
    try: s=decode_payload(content[mk+8:])
    except: continue
    # arabic if any value has arabic-block chars
    ar=any(any(0x0600<=ord(c)<=0x06FF for c in v) for v in list(s.values())[:50] if v)
    pkgs.append((typ,cnt,e.id,ar,list(s.items())[:3]))
pkgs.sort(key=lambda x:-x[1])
print("Type counts:",{})
from collections import Counter
c=Counter((t,ar) for t,cnt,i,ar,s in pkgs)
print("packages in DataPC.forge by (Type,isArabic):",dict(c))
print("\n--- top Arabic (Type 22/24) packages ---")
for typ,cnt,eid,ar,sample in pkgs:
    if ar and typ in (22,24):
        print(f"Type{typ} cnt={cnt} id={eid}")
        for k,v in sample: print(f"    {k}: {v!r}")
        print()
