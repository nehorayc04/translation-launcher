import os,sys,struct
HERE=os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,HERE); sys.path.insert(0,os.path.join(HERE,"..","..","acshadows","tools"))
from mirage_forge import Forge
import acs_cfd
from fontTools.ttLib import TTFont
od=acs_cfd._oodle()
fg=Forge(r"C:\Games\Assassin's Creed Valhalla\DataPC.forge")
e=[x for x in fg.entries if x.id==1948121226727][0]
cfds,_=acs_cfd.decode_resource(fg.read(e),od)
for bi,(data,ci) in enumerate(cfds):
    for mag in (b"OTTO",b"\x00\x01\x00\x00"):
        off=data.find(mag)
        if off<0: continue
        font=data[off:]
        p="games/acvalhalla/extract/ui_font.otf"
        open(p,"wb").write(font)
        try:
            f=TTFont(p,fontNumber=0,lazy=True); cmap=f.getBestCmap()
        except Exception as ex:
            print(f"block {bi} {mag} @{off}: parse fail {ex}"); continue
        c=lambda a,b: sum(1 for x in cmap if a<=x<=b)
        cls=struct.unpack_from("<I",data,0)[0]
        print(f"block {bi} cls={cls} {mag.decode('latin1')}@{off} bytes={len(data)}")
        print("  face:",f["name"].getDebugName(4) or f["name"].getDebugName(1))
        print(f"  Latin:{c(0x41,0x5A)}/26  Arabic:{c(0x0600,0x06FF)}  Arabic-pres:{c(0xFE70,0xFEFF)+c(0xFB50,0xFDFF)}  Hebrew:{c(0x05D0,0x05EA)}/27  total-cmap:{len(cmap)}")
        raise SystemExit
print("no font block found")
