import os,sys,struct,glob
sys.path.insert(0,"games/acvalhalla/tools"); sys.path.insert(0,"games/acshadows/tools"); sys.path.insert(0,"games/acunity/work")
from mirage_forge import Forge
from mirage_loc import decode_cfds, MARKER
from acu_loc import decode_payload
import acs_cfd
try: sys.stdout.reconfigure(encoding="utf-8",errors="replace")
except: pass
LOC=1849465967
od=acs_cfd._oodle()
# distinctive Arabic menu strings seen on screen
TARGETS={"متابعة":"Continue","خيارات":"Options","المتجر":"Store","لعبة جديدة":"NewGame","الخروج إلى سطح المكتب":"ExitDesktop"}
GAME=r"C:\Games\Assassin's Creed Valhalla"
cand=["DataPC_ACK_TitleScreen.forge","DataPC.forge","DataPC_extra.forge",
      "DataPC_20_dlc_patch_01.forge","DataPC_207_dlc_patch_01.forge","DataPC_232_dlc_patch_01.forge"]
for fn in cand:
    p=os.path.join(GAME,fn)
    if not os.path.exists(p): continue
    fg=Forge(p); found=False
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
        vals="\n".join(str(v) for v in s.values())
        hits=[en for ar,en in TARGETS.items() if ar in vals]
        if len(hits)>=2:
            print(f"[{fn}] id={e.id} Type={typ} cnt={cnt} MENU-HITS={hits}",flush=True)
            for ar,en in TARGETS.items():
                for k,v in s.items():
                    if v==ar: print(f"    id={k}: {en} = {v!r}"); break
            found=True
    if found: print(f"  ^^ menu package is in {fn}",flush=True)
print("--- done")
