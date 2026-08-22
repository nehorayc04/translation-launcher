"""Which SPAN do the PC/system screens read? The main menu reads variant_01/span 8 (the
ladder proved it), but the in-game SETTINGS tab, the SELECT PROFILE screen and the launcher
tabs all show the KEY NAME for keys whose value IS present in span 8 — so those surfaces read
a DIFFERENT span where the key is empty/missing. Put a unique PURE-LATIN marker per span in the
failing keys; one launch of each surface names the span it reads. Latin rules out font+bidi.

  SETTINGS_DISPLAY_GRAPHICS_TAB -> "S<N>"   (in-game settings tab)
  TEXT_SAVESLOT_HEADER          -> "P<N>"   (SELECT PROFILE header)
  SETTINGSCATEGORY_GRAPHICS     -> "G<N>"   (launcher Graphics tab)
  SETTINGS_GAMEPAD_TAB          -> "C<N>"   (a control: this one WORKS today, shows בקר)

    python 42_marker_test.py --deploy   (game CLOSED)   then read the on-screen number
    python 40_build_full.py --deploy    to restore the real build
"""
import os, sys, io, re, json, struct, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = r"F:\Game Lab\Ratchet & Clank - Rift Apart"
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
sys.path.insert(0, os.path.join(ROOT, "translation_manager"))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import dat1lib, dat1lib.types.dat1
import rc_rtl

# keep the FULL Hebrew so a single launch diagnoses without losing the translation
_clean = json.load(open(os.path.join(HERE, "hebrew_clean.json"), encoding="utf-8"))
_LOG = ("LAUNCHER_", "PCGRAPHICSSETTINGS_", "PCDISPLAYSETTINGS_", "PC_", "PCAUDIO", "SETTINGSCATEGORY_")
def _store(k, v):
    return rc_rtl._unesc(v) if k.startswith(_LOG) else rc_rtl.to_visual(v)
HEB = {k: _store(k, v) for k, v in _clean.items()}

LOCS = os.path.join(HERE, "..", "extracted", "loc_variants")
FONTS = os.path.join(HERE, "fonts")
STAGE = os.path.join(HERE, "build", "rc_marker.stage")
LOC_AID = 0xBE55D94F171BF8DE
FF = {0xA2197874D2B7B1AC: "proximanova_regular_normal_he.ttf", 0xB5F411285669C55D: "proximanova_bold_normal_he.ttf",
      0xB927D5EA184444C1: "sie_gothic_regular_he.ttf",         0x8187C80EF59344DC: "sie_gothic_bold_he.ttf"}
TAG_V, TAG_K, TAG_TO, TAG_KO, TAG_EC = 0x70A382B8, 0x4D73CEBD, 0xF80DEEB4, 0xA4EA55B2, 0xD540A903
HDR, SHDR, ALIGN = 16, 12, 16

def cstr(b, o): e = b.find(b"\x00", o); return b[o:(e if e >= 0 else len(b))]
def au(x, a): return (x + a - 1) // a * a

def rebuild(path, patches):
    raw = open(path, "rb").read(); pay = raw[36:]
    d = dat1lib.types.dat1.DAT1(io.BytesIO(pay), None)
    S = {sh.tag: (sh.offset, sh.size) for sh in d.header.sections}
    def sb(t): o, s = S[t]; return pay[o:o + s]
    cnt = struct.unpack("<I", sb(TAG_EC))[0]
    kb, vb = sb(TAG_K), sb(TAG_V)
    to = list(struct.unpack(f"<{cnt}I", sb(TAG_TO))); ko = list(struct.unpack(f"<{cnt}I", sb(TAG_KO)))
    ent = [[cstr(kb, ko[i]).decode("utf-8", "replace"), cstr(vb, to[i])] for i in range(cnt)]
    hit = 0
    for i, (k, v) in enumerate(ent):
        if k in patches: ent[i][1] = patches[k].encode("utf-8"); hit += 1
    nv = bytearray(b"\x00"); seen = {b"": 0}; nt = [0] * cnt
    for i, (k, v) in enumerate(ent):
        if v in seen: nt[i] = seen[v]; continue
        nt[i] = len(nv); nv.extend(v); nv.extend(b"\x00"); seen[v] = nt[i]
    ov = {TAG_V: bytes(nv), TAG_TO: struct.pack(f"<{cnt}I", *nt)}
    heads = list(d.header.sections)
    sd = {sh.tag: (ov.get(sh.tag, pay[sh.offset:sh.offset + sh.size]), sh) for sh in heads}
    out = bytearray(pay[:HDR])
    for sh in heads: out.extend(struct.pack("<III", sh.tag, 0, 0))
    if d.header.unknowns: out.extend(d.header.unknowns)
    first = min(sh.offset for sh in heads)
    if len(out) < first: out.extend(pay[len(out):first])
    no = {}
    for sh in sorted(heads, key=lambda s: s.offset):
        c = au(len(out), ALIGN)
        if c > len(out): out.extend(b"\x00" * (c - len(out)))
        no[sh.tag] = len(out); out.extend(sd[sh.tag][0])
    for idx, sh in enumerate(heads):
        struct.pack_into("<III", out, HDR + idx * SHDR, sh.tag, no[sh.tag], len(sd[sh.tag][0]))
    ho = bytes(pay[:HDR]).find(struct.pack("<I", d.header.size))
    if ho >= 0: struct.pack_into("<I", out, ho, len(out))
    return bytes(out), hit

os.makedirs(os.path.dirname(STAGE), exist_ok=True)
files = sorted(os.listdir(LOCS)); assert len(files) == 32
entries = {}
for fn in files:
    n = int(re.match(r"variant_(\d+)_", fn).group(1))
    patches = dict(HEB)                       # full Hebrew, then override the 4 diagnostic keys
    patches["SETTINGS_DISPLAY_GRAPHICS_TAB"] = f"S{n}"
    patches["TEXT_SAVESLOT_HEADER"]          = f"P{n}"
    patches["SETTINGSCATEGORY_GRAPHICS"]     = f"G{n}"
    patches["SETTINGS_GAMEPAD_TAB"]          = f"C{n}"
    blob, hit = rebuild(os.path.join(LOCS, fn), patches)
    entries[f"{n * 8}/{LOC_AID:016X}"] = blob
with zipfile.ZipFile(STAGE, "w", zipfile.ZIP_DEFLATED) as z:
    for k, v in entries.items(): z.writestr(k, v)
    for aid, fn in FF.items(): z.writestr(f"0/{aid:016X}", open(os.path.join(FONTS, fn), "rb").read())
    z.writestr("info.json", '{"name":"R&C span marker test","author":"translation-hub"}')
print(f"[+] {STAGE} ({os.path.getsize(STAGE)/1e6:.1f} MB, {len(entries)} spans)")
print("    in-game settings tab -> S<N> | profile header -> P<N> | launcher Graphics tab -> G<N> | control -> C<N>")

if "--deploy" in sys.argv:
    import spiderman2_mod as sm
    print("\n[*] deploying marker test (game CLOSED)…")
    print("[deploy]", sm.apply(GAME, [STAGE], cb=lambda p, pct, m: print(f"    {pct:5.1f}% {m}") if pct in (5.0, 97.0, 100.0) else None))
