import os, sys, struct, re
sys.path.insert(0, 'games/spiderman2/tools/ALERT')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import dat1lib, dat1lib.types.dat1 as _d1
GAME = r'F:\Game Lab\Ratchet & Clank - Rift Apart'
with open(os.path.join(GAME,'toc.tm_he_backup'),'rb') as f:
    t = dat1lib.read(f)
t.dat1.set_recalculation_strategy(_d1.RECALCULATE_ORIGINAL_ORDER)
t.set_archives_dir(GAME)
assets=t.get_assets_section(); sizes=t.get_sizes_section()
ids = getattr(assets,'ids',None) or getattr(assets,'values',None) or []
def aid_of(x): return int.from_bytes(bytes(x),'little') if not isinstance(x,int) else x

# 1) the config UI-DOC
CFG = 0x8B875EC96CB13E41
gi = next(i for i,x in enumerate(ids) if aid_of(x)==CFG)
data = bytes(t.extract_asset(gi))
print(f'=== config 0x{CFG:016X} gi={gi} len={len(data)} magic={data[:4]!r} ===')
# DAT1 sections?
try:
    d = dat1lib.types.dat1.DAT1.__new__(dat1lib.types.dat1.DAT1)
    import io as _io
    d2 = dat1lib.types.dat1.DAT1(_io.BytesIO(data[36:] if data[:4] not in (b'1TAD',) else data), None)
    print('  sections:', [hex(sh.tag) for sh in d2.header.sections][:20])
except Exception as e:
    print('  (not a plain DAT1:', e, ')')
for KEY in [b'SETTINGS_DISPLAY_GRAPHICS_TAB', b'SETTINGSCATEGORY_GRAPHICS', b'SETTINGS_GAMEPAD_TAB']:
    p = data.find(KEY)
    print(f'  {KEY.decode():30s} at {p}')
    if p>=0:
        ctx = data[max(0,p-48):p+len(KEY)+48]
        print('    ctx:', ctx)

# 2) which loc variant carries UI_PERC exactly (whole-word) + as substring
LOC = 0xBE55D94F171BF8DE
gi2 = next(i for i,x in enumerate(ids) if aid_of(x)==LOC)
ld = bytes(t.extract_asset(gi2))
for needle in [b'\x00UI_PERC\x00', b'UI_PERCENT', b'UI_PERC']:
    cnt = ld.count(needle)
    print(f'loc contains {needle!r}: {cnt}')
    p = ld.find(needle)
    if p>=0: print('   first ctx:', ld[max(0,p-8):p+40])
