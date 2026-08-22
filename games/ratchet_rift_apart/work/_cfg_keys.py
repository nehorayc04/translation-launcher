import os, sys, re
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
gi=next(i for i,x in enumerate(ids) if aid_of(x)==0x8B875EC96CB13E41)
data=bytes(t.extract_asset(gi))
# every ASCII run that looks like a PC-settings l10n key referenced by the settings config
keys=sorted(set(m.decode() for m in re.findall(rb'PC(?:GRAPHICS|DISPLAY|AUDIO|_)[A-Z0-9_]+', data)))
up=[k for k in keys if k.endswith('_UPPERCASE')]
base=[k for k in keys if not k.endswith('_UPPERCASE') and not k.endswith('_DESC')]
print(f'config references {len(keys)} PC keys: {len(up)} _UPPERCASE, {len(base)} base, rest _DESC')
print('--- BASE (non-uppercase) referenced by the settings config (would reverse if we set base->LOGICAL) ---')
for k in base: print('   ', k)
print('--- sample _UPPERCASE referenced ---')
for k in up[:12]: print('   ', k)
