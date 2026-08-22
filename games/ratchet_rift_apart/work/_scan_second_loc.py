import os, sys, struct
GAME = r"F:\Game Lab\Ratchet & Clank - Rift Apart"
sys.path.insert(0, os.path.join("games", "spiderman2", "tools", "ALERT"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import dat1lib, dat1lib.types.dat1 as _d1
with open(os.path.join(GAME, "toc.tm_he_backup"), "rb") as f:
    t = dat1lib.read(f)
t.dat1.set_recalculation_strategy(_d1.RECALCULATE_ORIGINAL_ORDER)
t.set_archives_dir(GAME)
assets = t.get_assets_section(); sizes = t.get_sizes_section(); archs = t.get_archives_section()
ids = getattr(assets, "ids", None) or getattr(assets, "values", None) or []
def aid_of(x): return int.from_bytes(bytes(x), "little") if not isinstance(x, int) else x
def an(i):
    try: return bytes(archs.archives[i].filename).split(b"\x00")[0].decode("ascii", "ignore")
    except Exception: return "?"
KEY = b"SETTINGS_DISPLAY_GRAPHICS_TAB"
VT = struct.pack("<I", 0x70A382B8)   # VALUES tag => loc DAT1
tgt = {i for i in range(len(archs.archives)) if an(i).lower() in ("d\\localization", "d\\userinterface")}
print("scanning archives:", {i: an(i) for i in tgt})
hits = []; scanned = 0
for gi, aid in enumerate(ids):
    se = sizes.entries[gi]
    if se.archive_index not in tgt: continue
    if se.value < 500: continue
    scanned += 1
    try: data = bytes(t.extract_asset(gi))
    except Exception: continue
    if KEY in data:
        isloc = VT in data[:5000]
        hits.append((aid_of(aid), gi, se.archive_index, se.value, isloc))
print(f"scanned {scanned}; assets with '{KEY.decode()}': {len(hits)}")
for aid, gi, ai, val, isloc in hits:
    tag = "localization_all" if aid == 0xBE55D94F171BF8DE else ("<<< SECOND LOC DAT1 >>>" if isloc else "UI-doc")
    print(f"  aid=0x{aid:016X} gi={gi} arch={ai}({an(ai)}) val={val} isLocDAT1={isloc}  [{tag}]")
