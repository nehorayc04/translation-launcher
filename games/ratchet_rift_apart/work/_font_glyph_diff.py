import os, sys, io
sys.path.insert(0, 'games/spiderman2/tools/ALERT')
sys.path.insert(0, '.venv/Lib/site-packages')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import dat1lib, dat1lib.types.dat1 as _d1
from fontTools.ttLib import TTFont
GAME = r'F:\Game Lab\Ratchet & Clank - Rift Apart'
with open(os.path.join(GAME,'toc.tm_he_backup'),'rb') as f:
    t = dat1lib.read(f)
t.dat1.set_recalculation_strategy(_d1.RECALCULATE_ORIGINAL_ORDER)
t.set_archives_dir(GAME)
assets=t.get_assets_section(); ids=getattr(assets,'ids',None) or getattr(assets,'values',None) or []
def aid_of(x): return int.from_bytes(bytes(x),'little') if not isinstance(x,int) else x

TARGETS = {
    'SIE-Gothic-Reg': (0xB927D5EA184444C1, 'sie_gothic_regular_he.ttf'),
    'ProximaNova-Reg': (0xA2197874D2B7B1AC, 'proximanova_regular_normal_he.ttf'),
}
for name,(aid,injfn) in TARGETS.items():
    gi = next(i for i,x in enumerate(ids) if aid_of(x)==aid)
    data = bytes(t.extract_asset(gi))
    off = 0 if data[:4] in (b'\x00\x01\x00\x00', b'OTTO', b'true') else 36
    orig = TTFont(io.BytesIO(data[off:]))
    ocmap = set(orig.getBestCmap())
    inj = TTFont(f'games/ratchet_rift_apart/work/fonts/{injfn}')
    icmap = set(inj.getBestCmap())
    lost = sorted(ocmap - icmap)
    print(f'=== {name} === orig glyphs={len(ocmap)} injected glyphs={len(icmap)} LOST={len(lost)}')
    if lost:
        print('  lost codepoints (first 60):', [hex(c) for c in lost[:60]])
        # show what characters those are
        print('  as chars:', ''.join(chr(c) if c>=0x20 else f'[{hex(c)}]' for c in lost[:80]))
