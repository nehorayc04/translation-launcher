"""BIDI A/B + TRANSCRIPTION CONTROL — settle LOGICAL vs VISUAL unambiguously.

The variant ladder proved: live variant = 01 (span 8), the font renders Hebrew
cleanly (no tofu), and a LOGICAL-stored word came out in an order the user read as
"reversed" — but a glyph-order reading of the same screenshot suggests it was
actually correct. A screenshot judgement can't separate those two, so this build
uses the [[transcription-control-string]] method instead of asking "is it right?":

  row RESUME      = LOGICAL 'שלום'   (A)   ─┐ same word, two modes, adjacent rows:
  row LOAD GAME   = VISUAL  'שלום'   (B)   ─┘ exactly ONE of them can read as שלום
  row VIEW CREDITS= LOGICAL 'אבגד'   (C)   ─┐ 4 distinct, non-confusable letters:
  desc line       = VISUAL  'אבגד'   (D)   ─┘ the user TRANSCRIBES them left→right

Decision table (from D/C transcription, left→right):
  C reads 'אבגד' → engine draws in STORAGE order (NON-bidi) → SHIP VISUAL
  C reads 'דגבא' → engine REVERSES (bidi/RTL)              → SHIP LOGICAL
(and B vs A must agree with it — that's the cross-check.)

Patches all 32 variants so the answer can't depend on the language slot.

    python 26_build_bidi_ab.py --deploy
    python 26_build_bidi_ab.py --revert
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
STAGE  = os.path.join(OUTDIR, "rc_bidi_ab.stage")
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

# only keys PROVEN visible on the CONTINUE GAME screen by the ladder screenshot
PATCHES = {
    "MENU_CONTINUEGAME_RESUME_TITLE": "שלום",            # A — LOGICAL
    "MENU_LOADGAME_TITLE":            visual("שלום"),    # B — VISUAL
    "MENU_VIEWCREDITS_TITLE":         "אבגד",            # C — LOGICAL control
    "MENU_LOADGAME_DESC":             visual("אבגד"),    # D — VISUAL control
}
print("=== what gets stored (codepoint order) ===")
for k, v in PATCHES.items():
    print(f"  {k:34} = {v!r}   chars={[c for c in v]}")

def cstr(b,o):
    e=b.find(b"\x00",o); return b[o:(e if e>=0 else len(b))]
def align_up(x,a): return (x+a-1)//a*a

def rebuild(path, patches):
    raw=open(path,"rb").read(); pay=raw[36:]
    d=dat1lib.types.dat1.DAT1(io.BytesIO(pay),None)
    S={sh.tag:(sh.offset,sh.size) for sh in d.header.sections}
    def sb(t): o,s=S[t]; return pay[o:o+s]
    cnt=struct.unpack("<I",sb(TAG_ENTRY_COUNT))[0]
    kb,vb=sb(TAG_KEYS),sb(TAG_VALUES)
    toff=list(struct.unpack(f"<{cnt}I",sb(TAG_TEXT_OFFSETS)))
    koff=list(struct.unpack(f"<{cnt}I",sb(TAG_KEY_OFFSETS)))
    ent=[[cstr(kb,koff[i]).decode("utf-8","replace"), cstr(vb,toff[i])] for i in range(cnt)]
    hit=0
    for i,(k,v) in enumerate(ent):
        if k in patches: ent[i][1]=patches[k].encode("utf-8"); hit+=1
    nv=bytearray(b"\x00"); seen={b"":0}; nt=[0]*cnt
    for i,(k,v) in enumerate(ent):
        if v in seen: nt[i]=seen[v]; continue
        nt[i]=len(nv); nv.extend(v); nv.extend(b"\x00"); seen[v]=nt[i]
    ov={TAG_VALUES:bytes(nv), TAG_TEXT_OFFSETS:struct.pack(f"<{cnt}I",*nt)}
    heads=list(d.header.sections)
    sd={sh.tag:(ov.get(sh.tag,pay[sh.offset:sh.offset+sh.size]),sh) for sh in heads}
    out=bytearray(pay[:HEADER_SIZE])
    for sh in heads: out.extend(struct.pack("<III",sh.tag,0,0))
    if d.header.unknowns: out.extend(d.header.unknowns)
    first=min(sh.offset for sh in heads)
    if len(out)<first: out.extend(pay[len(out):first])
    no={}
    for sh in sorted(heads,key=lambda s:s.offset):
        c=align_up(len(out),ALIGN)
        if c>len(out): out.extend(b"\x00"*(c-len(out)))
        no[sh.tag]=len(out); out.extend(sd[sh.tag][0])
    for idx,sh in enumerate(heads):
        struct.pack_into("<III",out,HEADER_SIZE+idx*SECTION_HEADER_SIZE,sh.tag,no[sh.tag],len(sd[sh.tag][0]))
    ho=bytes(pay[:HEADER_SIZE]).find(struct.pack("<I",d.header.size))
    if ho>=0: struct.pack_into("<I",out,ho,len(out))
    return bytes(out),hit

files=sorted(os.listdir(LOCS)); assert len(files)==32
ent={}
for fn in files:
    n=int(re.match(r"variant_(\d+)_",fn).group(1))
    blob,hit=rebuild(os.path.join(LOCS,fn),PATCHES)
    ent[f"{n*8}/{LOC_AID:016X}"]=blob
print(f"\n[+] {len(ent)} variants patched ({hit} keys each)")

freg=open(os.path.join(FONTS,"proximanova_regular_normal_he.ttf"),"rb").read()
fbld=open(os.path.join(FONTS,"proximanova_bold_normal_he.ttf"),"rb").read()
with zipfile.ZipFile(STAGE,"w",zipfile.ZIP_DEFLATED) as z:
    for k,v in ent.items(): z.writestr(k,v)
    z.writestr(f"0/{FONT_REG:016X}",freg); z.writestr(f"0/{FONT_BLD:016X}",fbld)
    z.writestr("info.json",'{"name":"R&C bidi A/B","author":"translation-hub"}')
print(f"[+] {STAGE} ({os.path.getsize(STAGE)/1e6:.1f} MB)")

if "--deploy" in sys.argv:
    sys.path.insert(0, os.path.join(ROOT,"translation_manager"))
    import spiderman2_mod as sm
    print("\n[*] deploying (game must be CLOSED)…")
    print("[deploy]", sm.apply(GAME,[STAGE],cb=lambda p,pct,m: print(f"    {pct:5.1f}% {m}") if pct in (5.0,97.0,100.0) else None))
elif "--revert" in sys.argv:
    sys.path.insert(0, os.path.join(ROOT,"translation_manager"))
    import spiderman2_mod as sm
    print("[revert]", sm.revert(GAME))
