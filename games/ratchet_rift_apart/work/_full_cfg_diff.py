import os, sys, re, json
sys.path.insert(0, 'games/spiderman2/tools/ALERT')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import dat1lib, dat1lib.types.dat1 as _d1
GAME = r'F:\Game Lab\Ratchet & Clank - Rift Apart'
with open(os.path.join(GAME,'toc.tm_he_backup'),'rb') as f:
    t = dat1lib.read(f)
t.dat1.set_recalculation_strategy(_d1.RECALCULATE_ORIGINAL_ORDER)
t.set_archives_dir(GAME)
assets=t.get_assets_section(); ids = getattr(assets,'ids',None) or getattr(assets,'values',None) or []
def aid_of(x): return int.from_bytes(bytes(x),'little') if not isinstance(x,int) else x
CFG = 0x8B875EC96CB13E41
gi = next(i for i,x in enumerate(ids) if aid_of(x)==CFG)
data = bytes(t.extract_asset(gi))
refs = sorted(set(m.decode() for m in re.findall(rb'[A-Z][A-Z0-9_]{4,}', data)))
print(f'config-doc references: {len(refs)} identifiers')

clean = json.load(open('games/ratchet_rift_apart/work/hebrew_clean.json', encoding='utf-8'))
en = json.load(open('games/ratchet_rift_apart/work/hebrew.json', encoding='utf-8')) if os.path.exists('games/ratchet_rift_apart/work/hebrew.json') else {}

missing = [k for k in refs if k not in clean]
print(f'\nMISSING from hebrew_clean.json (would show literal key OR fallback): {len(missing)}')
for k in missing: print('  ', k)
