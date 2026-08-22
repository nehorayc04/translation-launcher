"""Extract the English base (variant_00) localization to english.json — the
authoritative MEANING reference for the QA review (Arabic is a parallel target).
"""
import os, sys, io, json, struct
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib, dat1lib.types.dat1

TAG_VALUES=0x70A382B8; TAG_KEYS=0x4D73CEBD; TAG_TEXT_OFFSETS=0xF80DEEB4
TAG_KEY_OFFSETS=0xA4EA55B2; TAG_ENTRY_COUNT=0xD540A903

def cstr(buf, off):
    e = buf.find(b"\x00", off)
    return buf[off:e if e >= 0 else len(buf)]

EN = os.path.join(ROOT, "games", "spiderman2", "extracted",
                  "loc_variants", "variant_00_idx419917.localization")
raw = open(EN, "rb").read(); pay = raw[36:]
dat = dat1lib.types.dat1.DAT1(io.BytesIO(pay), None)
secs = {sh.tag: (sh.offset, sh.size) for sh in dat.header.sections}
def sec(tag): o, s = secs[tag]; return pay[o:o+s]
cnt = struct.unpack("<I", sec(TAG_ENTRY_COUNT))[0]
keys = sec(TAG_KEYS); vals = sec(TAG_VALUES)
toff = list(struct.unpack(f"<{cnt}I", sec(TAG_TEXT_OFFSETS)))
koff = list(struct.unpack(f"<{cnt}I", sec(TAG_KEY_OFFSETS)))
out = {}
for i in range(cnt):
    k = cstr(keys, koff[i]).decode("utf-8", "replace")
    if k not in out:
        out[k] = cstr(vals, toff[i]).decode("utf-8", "replace")
json.dump(out, open(os.path.join(HERE, "english.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"english.json: {len(out)} keys")
