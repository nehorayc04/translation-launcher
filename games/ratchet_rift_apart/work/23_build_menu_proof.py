"""R&C Rift Apart — MENU-PROOF builder (Playbook Stage 6).

Builds ONE deployable payload that patches the in-game PAUSE menu (immediately
reachable) with Hebrew in THREE bidi modes on the SAME screen so a single
screenshot decides the mode:
  • LOGICAL  (natural reading order, no control char)
  • LOGICAL+RLM (natural order + a leading U+200F anchor)
  • VISUAL   (pre-reversed per WD2/GoWR visual_line)
plus a pure-Latin marker (proves the toc-redirect MOUNTS, font-independent) and
Hebrew+digit / Hebrew+Latin diagnostics.

Payload = a .stage zip with 3 assets (all span 0):
  0/BE55D94F171BF8DE  → rebuilt Hebrew localization DAT1 (36-byte header stripped)
  0/A2197874D2B7B1AC  → Hebrew-injected Proxima Nova Regular (raw TTF)
  0/B5F411285669C55D  → Hebrew-injected Proxima Nova Bold (raw TTF)

Deploy/revert via the SM2 native applier (translation_manager/spiderman2_mod.py),
which backs up the toc and is fully reversible. GAME MUST BE CLOSED to deploy.

    python 23_build_menu_proof.py            # build only
    python 23_build_menu_proof.py --deploy   # build + apply to the game
    python 23_build_menu_proof.py --revert    # restore the pristine toc
"""
import os, sys, io, struct, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = r"F:\Game Lab\Ratchet & Clank - Rift Apart"
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import dat1lib, dat1lib.types.dat1

LOC_SRC = os.path.join(HERE, "..", "extracted", "loc_variants", "variant_00_idx87375.localization")
FONTS   = os.path.join(HERE, "fonts")
OUTDIR  = os.path.join(HERE, "menu_proof"); os.makedirs(OUTDIR, exist_ok=True)
STAGE   = os.path.join(OUTDIR, "rc_hebrew_menuproof.stage")

LOC_AID  = 0xBE55D94F171BF8DE
FONT_REG = 0xA2197874D2B7B1AC
FONT_BLD = 0xB5F411285669C55D
SPAN = 0

TAG_VALUES, TAG_KEYS = 0x70A382B8, 0x4D73CEBD
TAG_TEXT_OFFSETS, TAG_KEY_OFFSETS, TAG_ENTRY_COUNT = 0xF80DEEB4, 0xA4EA55B2, 0xD540A903
HEADER_SIZE, SECTION_HEADER_SIZE, ALIGN = 16, 12, 16
RLM = "‏"

def _is_heb(c): return 0x0590 <= ord(c) <= 0x05FF
def visual(s):
    """Pre-reverse for a NON-bidi renderer: reverse each Hebrew run + flip run
    order; keep Latin/digit/space runs forward. Per line."""
    out = []
    for line in s.split("\n"):
        runs, cur, cur_h = [], "", None
        for ch in line:
            h = _is_heb(ch)
            if cur_h is None or h == cur_h:
                cur += ch; cur_h = h
            else:
                runs.append((cur_h, cur)); cur, cur_h = ch, h
        if cur: runs.append((cur_h, cur))
        out.append("".join((t[::-1] if h else t) for h, t in reversed(runs)))
    return "\n".join(out)

# ── the proof patch set: PAUSE menu (one screen) + settings + diagnostics ──
# mode: LOG=logical, RLM=logical+leading &rlm;, VIS=visual, LAT=latin marker
PATCHES = {
    # pause OPTIONS submenu — LOGICAL vs VISUAL side by side
    "PAUSE_OPTION_RESUME_TITLE":         ("LOG", "המשך"),
    "PAUSE_OPTION_SETTINGS_TITLE":       ("LOG", "הגדרות"),
    "PAUSE_OPTION_MANUALSAVE_TITLE":     ("RLM", "שמירה ידנית"),
    "PAUSE_OPTION_RESTART_TITLE":        ("VIS", "התחל מחדש"),
    "PAUSE_OPTION_CONTROLLERLAYOUT_TITLE":("VIS", "פריסת שלט"),
    "PAUSE_OPTION_QUIT_TITLE":           ("VIS", "יציאה"),
    "PAUSE_OPTION_PHOTO_MODE_TITLE":     ("LAT", "ZZ-RC-OK-ZZ"),
    "PAUSE_OPTIONS_HEADER":              ("LOG", "אפשרויות"),
    # the desc line for the (default-highlighted) RESUME — digit + Latin island diagnostics
    "PAUSE_OPTION_RESUME_DESC":          ("LOG", "בדיקה: שלב 12, מצב Ratchet"),
    # settings screen labels
    "TEXTLANGUAGE_TITLE":                ("LOG", "שפת טקסט"),
    "MENU_SUBTITLES_TITLE":              ("LOG", "כתוביות"),
    "AUDIOLANGUAGE_TITLE":               ("VIS", "שפת דיבוב"),
    # pause tabs (top row) — bonus comparison
    "UI_PAUSE_WEAPONS":                  ("LOG", "נשק"),
    "UI_PAUSE_ARMOR":                    ("VIS", "שריון"),
    "UI_PAUSE_MAP":                      ("LOG", "מפה"),
    # main menu / load
    "MENU_LOADGAME_TITLE":               ("LOG", "טען משחק"),
    "MENU_NEWGAME_HEADER":               ("VIS", "משחק חדש"),
    "TEXT_QUIT_GAME":                    ("LOG", "צא מהמשחק"),
}
def render(mode, txt):
    if mode == "LAT": return txt
    if mode == "VIS": return visual(txt)
    if mode == "RLM": return RLM + txt
    return txt  # LOG

def cstr(buf, off):
    e = buf.find(b"\x00", off); return buf[off:(e if e >= 0 else len(buf))]
def align_up(x, a): return (x + a - 1)//a*a

def build_loc_dat1():
    raw = open(LOC_SRC, "rb").read()
    payload = raw[36:]
    dat1 = dat1lib.types.dat1.DAT1(io.BytesIO(payload), None)
    secs = {sh.tag:(sh.offset, sh.size) for sh in dat1.header.sections}
    def sb(t): o,s = secs[t]; return payload[o:o+s]
    cnt = struct.unpack("<I", sb(TAG_ENTRY_COUNT))[0]
    kb, vb = sb(TAG_KEYS), sb(TAG_VALUES)
    toff = list(struct.unpack(f"<{cnt}I", sb(TAG_TEXT_OFFSETS)))
    koff = list(struct.unpack(f"<{cnt}I", sb(TAG_KEY_OFFSETS)))
    entries = [[cstr(kb,koff[i]).decode("utf-8","replace"), cstr(vb,toff[i])] for i in range(cnt)]
    applied = {}
    for i,(k,v) in enumerate(entries):
        if k in PATCHES:
            mode, txt = PATCHES[k]
            entries[i][1] = render(mode, txt).encode("utf-8")
            applied[k] = (mode, txt)
    # rebuild VALUES + TEXT_OFFSETS (dedup, leading NUL) — SEMANTIC-PASS verified
    new_vals = bytearray(b"\x00"); seen = {b"":0}; new_toff = [0]*cnt
    for i,(k,v) in enumerate(entries):
        if v in seen: new_toff[i] = seen[v]; continue
        new_toff[i] = len(new_vals); new_vals.extend(v); new_vals.extend(b"\x00"); seen[v] = new_toff[i]
    overrides = {TAG_VALUES: bytes(new_vals), TAG_TEXT_OFFSETS: struct.pack(f"<{cnt}I", *new_toff)}
    heads = list(dat1.header.sections)
    sd = {sh.tag:(overrides.get(sh.tag, payload[sh.offset:sh.offset+sh.size]), sh) for sh in heads}
    out = bytearray(payload[:HEADER_SIZE])
    for sh in heads: out.extend(struct.pack("<III", sh.tag, 0, 0))
    if dat1.header.unknowns: out.extend(dat1.header.unknowns)
    first = min(sh.offset for sh in heads)
    if len(out) < first: out.extend(payload[len(out):first])
    noff = {}
    for sh in sorted(heads, key=lambda s:s.offset):
        cur = align_up(len(out), ALIGN)
        if cur > len(out): out.extend(b"\x00"*(cur-len(out)))
        noff[sh.tag] = len(out); out.extend(sd[sh.tag][0])
    for idx, sh in enumerate(heads):
        struct.pack_into("<III", out, HEADER_SIZE+idx*SECTION_HEADER_SIZE, sh.tag, noff[sh.tag], len(sd[sh.tag][0]))
    hoff = bytes(payload[:HEADER_SIZE]).find(struct.pack("<I", dat1.header.size))
    if hoff >= 0: struct.pack_into("<I", out, hoff, len(out))
    # verify re-parse
    d2 = dat1lib.types.dat1.DAT1(io.BytesIO(bytes(out)), None)
    s2 = {sh.tag:(sh.offset,sh.size) for sh in d2.header.sections}
    def g2(t): o,s=s2[t]; return bytes(out)[o:o+s]
    v2 = g2(TAG_VALUES); t2 = list(struct.unpack(f"<{cnt}I", g2(TAG_TEXT_OFFSETS)))
    k2b = g2(TAG_KEYS); ko2 = list(struct.unpack(f"<{cnt}I", g2(TAG_KEY_OFFSETS)))
    ok = 0
    for i in range(cnt):
        kk = cstr(k2b,ko2[i]).decode("utf-8","replace")
        if kk in PATCHES:
            got = cstr(v2,t2[i]).decode("utf-8","replace")
            want = render(*PATCHES[kk])
            if got == want: ok += 1
            else: print(f"  [MISMATCH] {kk}: got {got!r} want {want!r}")
    print(f"[+] loc rebuilt: {cnt} entries, {len(applied)}/{len(PATCHES)} keys patched, {ok}/{len(applied)} verified on re-parse")
    for k,(m,t) in applied.items(): print(f"      {m}  {k:38} = {t}")
    missing = [k for k in PATCHES if k not in applied]
    if missing: print(f"  [!] keys not found in loc: {missing}")
    return bytes(out)  # DAT1 with 36-byte header stripped

def build_stage():
    loc = build_loc_dat1()
    freg = open(os.path.join(FONTS, "proximanova_regular_normal_he.ttf"), "rb").read()
    fbld = open(os.path.join(FONTS, "proximanova_bold_normal_he.ttf"), "rb").read()
    with zipfile.ZipFile(STAGE, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{SPAN}/{LOC_AID:016X}",  loc)
        z.writestr(f"{SPAN}/{FONT_REG:016X}", freg)
        z.writestr(f"{SPAN}/{FONT_BLD:016X}", fbld)
        z.writestr("info.json", '{"name":"R&C Hebrew menu-proof","author":"translation-hub"}')
    print(f"[+] wrote {STAGE}  (loc {len(loc)} + font_reg {len(freg)} + font_bld {len(fbld)} B)")
    return STAGE

if __name__ == "__main__":
    stage = build_stage()
    if "--deploy" in sys.argv:
        sys.path.insert(0, os.path.join(ROOT, "translation_manager"))
        import spiderman2_mod as sm
        print("\n[*] deploying via spiderman2_mod.apply (game must be CLOSED)…")
        r = sm.apply(GAME, [stage], cb=lambda p,pct,m: print(f"    {pct:5.1f}% {m}"))
        print("[deploy]", r)
    elif "--revert" in sys.argv:
        sys.path.insert(0, os.path.join(ROOT, "translation_manager"))
        import spiderman2_mod as sm
        print("[*] reverting…")
        print("[revert]", sm.revert(GAME))
