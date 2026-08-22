import os, sys, re, struct
sys.path.insert(0, 'games/spiderman2/tools/ALERT')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import dat1lib, dat1lib.types.dat1 as _d1
GAME = r'F:\Game Lab\Ratchet & Clank - Rift Apart'
with open(os.path.join(GAME,'toc.tm_he_backup'),'rb') as f:
    t = dat1lib.read(f)
t.dat1.set_recalculation_strategy(_d1.RECALCULATE_ORIGINAL_ORDER)
t.set_archives_dir(GAME)
assets=t.get_assets_section(); sizes=t.get_sizes_section(); archs=t.get_archives_section()
ids = getattr(assets,'ids',None) or getattr(assets,'values',None) or []
def aid_of(x): return int.from_bytes(bytes(x),'little') if not isinstance(x,int) else x
def an(i):
    try: return bytes(archs.archives[i].filename).split(b'\x00')[0].decode('ascii','ignore')
    except: return '?'
# 1) FULL PC-key extraction from the launcher config UI-DOC
CFG = 0x8B875EC96CB13E41
gi = next(i for i,x in enumerate(ids) if aid_of(x)==CFG)
data = bytes(t.extract_asset(gi))
keys = sorted(set(m.decode() for m in re.findall(rb'[A-Z][A-Z0-9_]{4,}', data)))
print(f'=== ALL identifier-like ASCII strings (len>=5) in the config UI-DOC: {len(keys)} ===')
for k in keys: print('  ', k)
