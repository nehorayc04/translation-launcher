"""Ground truth: are these keys actually IN localization_all, what are their ORIGINAL values,
and does any OTHER asset in ANY archive carry them? Resolves the 'marker didn't appear' mystery."""
import os, sys, io, struct
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = r"F:\Game Lab\Ratchet & Clank - Rift Apart"
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import dat1lib, dat1lib.types.dat1 as _d1

TAG_V, TAG_K, TAG_TO, TAG_KO, TAG_EC = 0x70A382B8, 0x4D73CEBD, 0xF80DEEB4, 0xA4EA55B2, 0xD540A903
KEYS = [b"SETTINGSCATEGORY_GRAPHICS", b"SETTINGSCATEGORY_DISPLAY", b"SETTINGS_DISPLAY_GRAPHICS_TAB",
        b"SETTINGS_GAMEPAD_TAB", b"TEXT_SAVESLOT_HEADER", b"UI_PERC",
        b"PCGRAPHICSSETTINGS_HIGH", b"PCDISPLAYSETTINGS_WINDOWMODE"]

def cstr(b, o):
    e = b.find(b"\x00", o); return b[o:(e if e >= 0 else len(b))]

def dump_variant(blob, tag):
    d = dat1lib.types.dat1.DAT1(io.BytesIO(blob), None)
    S = {sh.tag: (sh.offset, sh.size) for sh in d.header.sections}
    def sb(t): o, s = S[t]; return blob[o:o + s]
    if TAG_EC not in S:
        print(f"  [{tag}] not a loc DAT1 (no ENTRY_COUNT)"); return
    cnt = struct.unpack("<I", sb(TAG_EC))[0]
    kb, vb = sb(TAG_K), sb(TAG_V)
    ko = list(struct.unpack(f"<{cnt}I", sb(TAG_KO)))
    to = list(struct.unpack(f"<{cnt}I", sb(TAG_TO)))
    km = {cstr(kb, ko[i]): i for i in range(cnt)}
    print(f"  [{tag}] cnt={cnt}")
    for K in KEYS:
        if K in km:
            i = km[K]; v = cstr(vb, to[i])
            print(f"    {K.decode():32s} PRESENT  val={v[:60]!r}")
        else:
            print(f"    {K.decode():32s} ABSENT")

# 1) ORIGINAL localization_all span-8 (variant_01) from the extracted variants
LOCS = os.path.join(HERE, "..", "extracted", "loc_variants")
import re
files = sorted(os.listdir(LOCS))
v01 = next(f for f in files if re.match(r"variant_0*1_", f))
raw = open(os.path.join(LOCS, v01), "rb").read()
print(f"=== ORIGINAL localization_all {v01} (span 8) ===")
dump_variant(raw[36:], "orig-v01")

# 2) scan EVERY archive for any OTHER asset that contains these key strings
print("\n=== scan ALL archives for a SECOND asset carrying these keys ===")
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
NEEDLES = [b"SETTINGS_DISPLAY_GRAPHICS_TAB", b"SETTINGSCATEGORY_GRAPHICS", b"UI_PERC", b"TEXT_SAVESLOT_HEADER"]
VT = struct.pack("<I", TAG_V)
found = {}
scanned = 0
for gi, aid in enumerate(ids):
    se = sizes.entries[gi]
    if se.value < 200: continue
    scanned += 1
    try: data = bytes(t.extract_asset(gi))
    except Exception: continue
    for n in NEEDLES:
        if n in data:
            a = aid_of(aid)
            found.setdefault(a, {"gi": gi, "arch": se.archive_index, "val": se.value,
                                 "isloc": VT in data[:6000], "needles": set()})
            found[a]["needles"].add(n.decode())
print(f"scanned {scanned} assets")
for a, info in sorted(found.items()):
    tag = "localization_all" if a == 0xBE55D94F171BF8DE else ("SECOND-LOC-DAT1" if info["isloc"] else "OTHER-DOC")
    print(f"  aid=0x{a:016X} gi={info['gi']} arch={info['arch']}({an(info['arch'])}) "
          f"val={info['val']} isLoc={info['isloc']} [{tag}]  keys={sorted(info['needles'])}")
