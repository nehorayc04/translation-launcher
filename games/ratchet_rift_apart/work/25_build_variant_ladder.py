"""VARIANT LADDER — find WHICH of the 32 localization variants the game actually
reads, in ONE launch ([[measure-with-a-ladder]]).

The menu-proof patched span 0 (variant_00 / en-US) and nothing changed on screen,
while `MENU_LOADGAME_TITLE` (the ONLY key whose English value is "LOAD GAME", and
visible on the CONTINUE GAME screen) stayed English → the game reads a DIFFERENT
variant. Instead of guessing, patch ALL 32: variant N gets the unique Latin marker
`ZZ-NN-ZZ` in that key. One screenshot names the live variant.

Bonus on the same screen (so one shot also answers font + bidi if it lands):
  MENU_VIEWCREDITS_TITLE = 'קרדיטים'          (LOGICAL)
  MENU_SETTINGS_HEADER   = visual('הגדרות')   (VISUAL)

Fonts are re-included because apply() reverts a prior apply before re-applying.

    python 25_build_variant_ladder.py            # build
    python 25_build_variant_ladder.py --deploy   # build + apply (game CLOSED)
    python 25_build_variant_ladder.py --revert
"""
import os, sys, io, re, struct, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = r"F:\Game Lab\Ratchet & Clank - Rift Apart"
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import dat1lib, dat1lib.types.dat1

LOCS   = os.path.join(HERE, "..", "extracted", "loc_variants")
FONTS  = os.path.join(HERE, "fonts")
OUTDIR = os.path.join(HERE, "menu_proof"); os.makedirs(OUTDIR, exist_ok=True)
STAGE  = os.path.join(OUTDIR, "rc_variant_ladder.stage")

LOC_AID, FONT_REG, FONT_BLD = 0xBE55D94F171BF8DE, 0xA2197874D2B7B1AC, 0xB5F411285669C55D
TAG_VALUES, TAG_KEYS = 0x70A382B8, 0x4D73CEBD
TAG_TEXT_OFFSETS, TAG_KEY_OFFSETS, TAG_ENTRY_COUNT = 0xF80DEEB4, 0xA4EA55B2, 0xD540A903
HEADER_SIZE, SECTION_HEADER_SIZE, ALIGN = 16, 12, 16

def _is_heb(c): return 0x0590 <= ord(c) <= 0x05FF
def visual(s):
    out=[]
    for line in s.split("\n"):
        runs, cur, ch_h = [], "", None
        for ch in line:
            h=_is_heb(ch)
            if ch_h is None or h==ch_h: cur+=ch; ch_h=h
            else: runs.append((ch_h,cur)); cur, ch_h = ch, h
        if cur: runs.append((ch_h,cur))
        out.append("".join((t[::-1] if h else t) for h,t in reversed(runs)))
    return "\n".join(out)

def cstr(b,o):
    e=b.find(b"\x00",o); return b[o:(e if e>=0 else len(b))]
def align_up(x,a): return (x+a-1)//a*a

def rebuild(path, patches):
    raw = open(path,"rb").read(); pay = raw[36:]
    d = dat1lib.types.dat1.DAT1(io.BytesIO(pay), None)
    S = {sh.tag:(sh.offset,sh.size) for sh in d.header.sections}
    def sb(t): o,s=S[t]; return pay[o:o+s]
    cnt = struct.unpack("<I", sb(TAG_ENTRY_COUNT))[0]
    kb, vb = sb(TAG_KEYS), sb(TAG_VALUES)
    toff = list(struct.unpack(f"<{cnt}I", sb(TAG_TEXT_OFFSETS)))
    koff = list(struct.unpack(f"<{cnt}I", sb(TAG_KEY_OFFSETS)))
    ent = [[cstr(kb,koff[i]).decode("utf-8","replace"), cstr(vb,toff[i])] for i in range(cnt)]
    hit = 0
    for i,(k,v) in enumerate(ent):
        if k in patches:
            ent[i][1] = patches[k].encode("utf-8"); hit += 1
    nv = bytearray(b"\x00"); seen={b"":0}; nt=[0]*cnt
    for i,(k,v) in enumerate(ent):
        if v in seen: nt[i]=seen[v]; continue
        nt[i]=len(nv); nv.extend(v); nv.extend(b"\x00"); seen[v]=nt[i]
    ov = {TAG_VALUES: bytes(nv), TAG_TEXT_OFFSETS: struct.pack(f"<{cnt}I", *nt)}
    heads = list(d.header.sections)
    sd = {sh.tag:(ov.get(sh.tag, pay[sh.offset:sh.offset+sh.size]), sh) for sh in heads}
    out = bytearray(pay[:HEADER_SIZE])
    for sh in heads: out.extend(struct.pack("<III", sh.tag, 0, 0))
    if d.header.unknowns: out.extend(d.header.unknowns)
    first = min(sh.offset for sh in heads)
    if len(out) < first: out.extend(pay[len(out):first])
    no={}
    for sh in sorted(heads, key=lambda s:s.offset):
        c=align_up(len(out),ALIGN)
        if c>len(out): out.extend(b"\x00"*(c-len(out)))
        no[sh.tag]=len(out); out.extend(sd[sh.tag][0])
    for idx,sh in enumerate(heads):
        struct.pack_into("<III", out, HEADER_SIZE+idx*SECTION_HEADER_SIZE, sh.tag, no[sh.tag], len(sd[sh.tag][0]))
    ho = bytes(pay[:HEADER_SIZE]).find(struct.pack("<I", d.header.size))
    if ho>=0: struct.pack_into("<I", out, ho, len(out))
    return bytes(out), hit

files = sorted(os.listdir(LOCS))
assert len(files) == 32, f"expected 32 variants, got {len(files)}"
entries = {}
print("=== building ladder over all 32 variants ===")
for fn in files:
    m = re.match(r"variant_(\d+)_idx(\d+)\.localization", fn)
    n = int(m.group(1)); span = n * 8
    patches = {
        "MENU_LOADGAME_TITLE":     f"ZZ-{n:02d}-ZZ",
        "MENU_VIEWCREDITS_TITLE":  "קרדיטים",
        "MENU_SETTINGS_HEADER":    visual("הגדרות"),
    }
    blob, hit = rebuild(os.path.join(LOCS, fn), patches)
    entries[f"{span}/{LOC_AID:016X}"] = blob
    if n < 3 or n == 31:
        print(f"  variant_{n:02d} span={span:3} patched={hit} -> {len(blob)} B  marker=ZZ-{n:02d}-ZZ")
print(f"  ... {len(entries)} variants total")

freg = open(os.path.join(FONTS, "proximanova_regular_normal_he.ttf"), "rb").read()
fbld = open(os.path.join(FONTS, "proximanova_bold_normal_he.ttf"), "rb").read()
with zipfile.ZipFile(STAGE, "w", zipfile.ZIP_DEFLATED) as z:
    for name, blob in entries.items():
        z.writestr(name, blob)
    z.writestr(f"0/{FONT_REG:016X}", freg)
    z.writestr(f"0/{FONT_BLD:016X}", fbld)
    z.writestr("info.json", '{"name":"R&C variant ladder","author":"translation-hub"}')
print(f"[+] {STAGE}  ({os.path.getsize(STAGE)/1e6:.1f} MB, {len(entries)} loc + 2 fonts)")

if "--deploy" in sys.argv:
    sys.path.insert(0, os.path.join(ROOT, "translation_manager"))
    import spiderman2_mod as sm
    print("\n[*] deploying (game must be CLOSED)…")
    r = sm.apply(GAME, [STAGE], cb=lambda p,pct,m: print(f"    {pct:5.1f}% {m}") if pct in (5.0,97.0,100.0) else None)
    print("[deploy]", r)
elif "--revert" in sys.argv:
    sys.path.insert(0, os.path.join(ROOT, "translation_manager"))
    import spiderman2_mod as sm
    print("[revert]", sm.revert(GAME))
