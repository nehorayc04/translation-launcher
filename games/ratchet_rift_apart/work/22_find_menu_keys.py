"""Find good main-menu / settings UI keys in variant_00 (English) for the menu-proof:
short, no <ts> timing tag, main-menu-ish. Print key -> english value."""
import os, sys, io, struct
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import dat1lib, dat1lib.types.dat1

SRC = os.path.join(HERE, "..", "extracted", "loc_variants", "variant_00_idx87375.localization")
TAG_VALUES, TAG_KEYS = 0x70A382B8, 0x4D73CEBD
TAG_TEXT_OFFSETS, TAG_KEY_OFFSETS, TAG_ENTRY_COUNT = 0xF80DEEB4, 0xA4EA55B2, 0xD540A903

raw = open(SRC, "rb").read(); pay = raw[36:]
d = dat1lib.types.dat1.DAT1(io.BytesIO(pay), None)
secs = {sh.tag:(sh.offset,sh.size) for sh in d.header.sections}
def sb(t): o,s=secs[t]; return pay[o:o+s]
cnt = struct.unpack("<I", sb(TAG_ENTRY_COUNT))[0]
kb, vb = sb(TAG_KEYS), sb(TAG_VALUES)
ko = list(struct.unpack(f"<{cnt}I", sb(TAG_KEY_OFFSETS)))
to = list(struct.unpack(f"<{cnt}I", sb(TAG_TEXT_OFFSETS)))
def cstr(b,o): e=b.find(b"\x00",o); return b[o:(e if e>=0 else len(b))]

pairs = {}
for i in range(cnt):
    k = cstr(kb,ko[i]).decode("utf-8","replace")
    v = cstr(vb,to[i]).decode("utf-8","replace")
    if k and k not in pairs:
        pairs[k] = v

# candidates: short UI values, no <ts>, main-menu words
WANT = ["CONTINUE","NEW_GAME","NEWGAME","NEW GAME","LOAD","OPTION","SETTING","QUIT","EXIT",
        "MAIN_MENU","MAINMENU","LANGUAGE","SUBTITLE","AUDIO","DISPLAY","GRAPHIC","BRIGHT",
        "RESUME","START","BACK","APPLY","ACCEPT","CANCEL","CREDITS","PAUSE","SAVE"]
print("=== menu/settings candidates (key -> EN, no <ts>, len<=40) ===")
shown = 0
for k,v in pairs.items():
    if "<ts" in v: continue
    if not v or len(v) > 40: continue
    ku = k.upper()
    if any(w in ku for w in WANT):
        print(f"  {k:45} = {v!r}")
        shown += 1
        if shown >= 60: break
print(f"\n[*] total keys with values: {len(pairs)}")
