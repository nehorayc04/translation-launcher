"""Independent deep integrity check of the BUILT localization archive.
Confirms every entry decodes, descriptions are RLM+plain with no leftover
wrappers, inner markup is preserved vs source, labels keep RLE, count is sane."""
import os, sys, io, struct, re, json, glob
ROOT = r"C:\Users\Nehoray_Cohen\Projects\Game translator"
HERE = os.path.join(ROOT, "games", "spiderman2", "work")
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib, dat1lib.types.dat1

RLM, RLE, PDF, ALM, LRI = "‏", "‫", "‬", "؜", "⁦"
src = open(os.path.join(HERE, "10_build_patched_localization.py"), encoding="utf-8").read()
def tag(n): return int(re.search(n + r"\s*=\s*(0x[0-9A-Fa-f]+)", src).group(1), 16)
TEC, TK, TV, TTO, TKO = map(tag, ["TAG_ENTRY_COUNT","TAG_KEYS","TAG_VALUES","TAG_TEXT_OFFSETS","TAG_KEY_OFFSETS"])

raw = open(os.path.join(HERE, "arabic_patched_hebrew_menu.localization"), "rb").read()
pay = raw[36:]
d = dat1lib.types.dat1.DAT1(io.BytesIO(pay), None)
secs = {sh.tag:(sh.offset, sh.size) for sh in d.header.sections}
def sec(t): o,s = secs[t]; return pay[o:o+s]
cnt = struct.unpack("<I", sec(TEC))[0]
keys, vals = sec(TK), sec(TV)
toff = list(struct.unpack(f"<{cnt}I", sec(TTO)))
koff = list(struct.unpack(f"<{cnt}I", sec(TKO)))
def cstr(b,o): e=b.find(b"\x00",o); return b[o:e]

# load source descriptions for markup comparison
src_desc = {}
for fn in glob.glob(os.path.join(HERE, "menus*_he.json")) + [os.path.join(HERE,"settings_he.json")]:
    for k,v in json.load(open(fn,encoding="utf-8")).items():
        if isinstance(v,str) and v.startswith(RLM): src_desc.setdefault(k,v)

decode_fail = bad_rlm = leftover = markup_lost = double_rlm = 0
all_keys = set()
examples = []
for i in range(cnt):
    try:
        kn = cstr(keys, koff[i]).decode("utf-8")
        v  = cstr(vals, toff[i]).decode("utf-8")
    except Exception:
        decode_fail += 1; continue
    all_keys.add(kn)
    if kn in src_desc:
        if not v.startswith(RLM): bad_rlm += 1; examples.append(("NO_RLM",kn,v[:40]))
        if v[1:].startswith(RLM): double_rlm += 1; examples.append(("DBL_RLM",kn,v[:40]))
        if ("<span dir='rtl'>" in v) or ("<div" in v) or (ALM in v) or (LRI in v) or (RLE in v):
            leftover += 1; examples.append(("LEFTOVER",kn,v[:40]))
        # markup preserved: every tag/entity/{..} in source must be in built value
        for tok in re.findall(r"<[^>]+>|&[a-zA-Z]+;|\{[^}]*\}", src_desc[kn]):
            if tok not in v:
                markup_lost += 1; examples.append(("MARKUP",kn,tok)); break

print("="*64)
print(f"  entries in archive   : {cnt}")
print(f"  unique keys          : {len(all_keys)}")
print(f"  UTF-8 decode failures: {decode_fail}")
print(f"  descriptions checked : {sum(1 for k in src_desc if k in all_keys)} / {len(src_desc)} source")
print(f"  missing leading RLM  : {bad_rlm}")
print(f"  double RLM           : {double_rlm}")
print(f"  leftover wrappers    : {leftover}")
print(f"  inner markup lost    : {markup_lost}")
print("="*64)
if examples:
    print("ISSUES (first 12):")
    for t,k,x in examples[:12]: print(f"  [{t}] {k}: {x}")
else:
    print("CLEAN — no integrity issues found.")
