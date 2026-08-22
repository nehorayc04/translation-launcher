import os, sys, struct
sys.path.insert(0, 'games/spiderman2/tools/ALERT')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import dat1lib, dat1lib.types.dat1 as _d1
GAME = r'F:\Game Lab\Ratchet & Clank - Rift Apart'
with open(os.path.join(GAME,'toc.tm_he_backup'),'rb') as f:
    t = dat1lib.read(f)
t.dat1.set_recalculation_strategy(_d1.RECALCULATE_ORIGINAL_ORDER)
t.set_archives_dir(GAME)
assets=t.get_assets_section(); ids=getattr(assets,'ids',None) or getattr(assets,'values',None) or []
def aid_of(x): return int.from_bytes(bytes(x),'little') if not isinstance(x,int) else x
CFG = 0x8B875EC96CB13E41
gi = next(i for i,x in enumerate(ids) if aid_of(x)==CFG)
data = bytes(t.extract_asset(gi))

def dump(key, window=80):
    kb = key.encode()
    idx = 0
    while True:
        p = data.find(kb, idx)
        if p < 0: break
        pre = data[max(0,p-window):p]
        post = data[p:p+len(kb)+40]
        print(f'--- {key} @ {p} ---')
        print('  PRE :', pre.hex(' '))
        print('  PRE(asc):', ''.join(chr(b) if 0x20<=b<0x7f else '.' for b in pre))
        print('  POST:', post[:len(kb)+40].hex(' '))
        idx = p+1

for k in ['SETTINGS_GAMEPAD_TAB', 'SETTINGS_DISPLAY_GRAPHICS_TAB', 'SETTINGS_MOUSE_TAB', 'SETTINGS_KEY_BINDING_TAB']:
    dump(k)
