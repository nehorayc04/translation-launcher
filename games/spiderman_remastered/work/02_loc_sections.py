"""MSMR — localization codec + language map (Phase-1 gate).

READ-ONLY. Operates on the already-extracted variants under
games/spiderman_remastered/extract/loc_variants/ (produced by 01_probe.py).

(a) EMPIRICALLY locate the inner DAT1 magic in the asset (never assume 36).
(b) Parse the inner DAT1 and list every section: tag / offset / size.
(c) Per section tag, count DISTINCT contents across all 23 variants
    (sha1 of the full section bytes). The section that differs on all 23 IS
    the values/strings section; identical-on-all are shared key/metadata.
(d) Decode the values section (NUL-separated UTF-8 first; hexdump fallback)
    and classify each variant by the dominant Unicode script of ITS OWN values.
(e) Print variant -> asset index -> span -> LANGUAGE, and name the ARABIC
    (Hebrew target) + ENGLISH (source) slots.

NOTE: the DAT1 header is parsed MANUALLY (struct) rather than via
dat1lib.types.dat1.DAT1 — that class byte-scans the whole inter-header string
blob in pure Python, which is minutes per variant on a 6 MB asset. Layout is
taken verbatim from dat1lib/types/dat1.py (DAT1Header / DAT1SectionHeader).
"""
import os, sys, io, json, struct, hashlib
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
LOCS = os.path.join(ROOT, "games", "spiderman_remastered", "extract", "loc_variants")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DAT1_MAGIC = 0x44415431  # 'DAT1' LE -> bytes '1TAD'

# ------------------------------------------------------------------ helpers
def hexdump(buf, off=0, n=96, label=""):
    if label:
        print(f"  --- {label} ---")
    end = min(off + n, len(buf))
    for i in range(off, end, 16):
        row = buf[i:i + 16]
        h = " ".join(f"{b:02x}" for b in row)
        a = "".join(chr(b) if 32 <= b < 127 else "." for b in row)
        print(f"    {i:06X}  {h:<47}  |{a}|")


def find_dat1(raw: bytes):
    for magic in (b"1TAD", b"DAT1"):
        o = raw.find(magic)
        if o != -1:
            return o, magic.decode()
    return -1, None


class D1:
    """Minimal DAT1 header parser (layout from dat1lib/types/dat1.py)."""
    def __init__(self, pay: bytes):
        self.pay = pay
        self.magic, self.unk1, self.size = struct.unpack_from("<III", pay, 0)
        nsec, nunk = struct.unpack_from("<HH", pay, 12)
        self.nunk = nunk
        self.sections = []  # (tag, offset, size)
        for i in range(nsec):
            t, o, s = struct.unpack_from("<III", pay, 16 + 12 * i)
            self.sections.append((t, o, s))
        self.hdr_end = 16 + 12 * nsec + 8 * nunk
        self.unknowns = pay[16 + 12 * nsec: self.hdr_end]
        self.min_off = min((o for _, o, _ in self.sections), default=len(pay))
        self.strings_blob = pay[self.hdr_end:self.min_off]

    def seg(self, tag):
        for t, o, s in self.sections:
            if t == tag:
                return self.pay[o:o + s]
        return b""


ASSET_TYPES = {0x122BB0AB: "localization", 0x51B8E006: "toc", 0x2A077A51: "dag"}


def sniff_cp(text: str, c=None) -> Counter:
    if c is None:
        c = Counter()
    for ch in text:
        cp = ord(ch)
        if   cp < 0x80: c["ascii"] += 1
        elif 0x0590 <= cp <= 0x05FF: c["hebrew"] += 1
        elif 0x0600 <= cp <= 0x06FF: c["arabic"] += 1
        elif 0xFB50 <= cp <= 0xFEFF: c["arabic_pres"] += 1
        elif 0x0400 <= cp <= 0x04FF: c["cyrillic"] += 1
        elif 0x0370 <= cp <= 0x03FF: c["greek"] += 1
        elif 0x3040 <= cp <= 0x309F: c["hiragana"] += 1
        elif 0x30A0 <= cp <= 0x30FF: c["katakana"] += 1
        elif 0xAC00 <= cp <= 0xD7AF: c["hangul"] += 1
        elif 0x1100 <= cp <= 0x11FF: c["hangul"] += 1
        elif 0x0E00 <= cp <= 0x0E7F: c["thai"] += 1
        elif 0x4E00 <= cp <= 0x9FFF: c["cjk"] += 1
        elif 0x3400 <= cp <= 0x4DBF: c["cjk"] += 1
        elif 0x0100 <= cp <= 0x017F: c["latin_ext_a"] += 1
        elif 0x0180 <= cp <= 0x024F: c["latin_ext_b"] += 1
        elif 0x00C0 <= cp <= 0x00FF: c["latin1_accent"] += 1
    return c


# distinctive letters/words per latin-script language
LATIN_HINTS = [
    ("german",     ["ß", "ä", "ö", "ü", " der ", " die ", " und ", " nicht ", " ist ", " ich "]),
    ("french",     ["ç", "è", "ê", "à", "û", " les ", " des ", " vous ", " est ", " pour ", " une "]),
    ("italian",    ["à", "è", "ù", "ò", " gli ", " della ", " questo ", " sono ", " per ", " non "]),
    ("spanish",    ["ñ", "¿", "¡", " los ", " para ", " está ", " que ", " con ", " una "]),
    ("portuguese", ["ã", "õ", "ç", " você ", " não ", " uma ", " para ", " está ", " com "]),
    ("polish",     ["ł", "ą", "ę", "ś", "ż", "ź", "ć", "ń", " nie ", " jest ", " się "]),
    ("dutch",      [" het ", " een ", " niet ", " voor ", " van ", " ik ", " je "]),
    ("danish",     ["æ", "ø", "å", " ikke ", " være ", " til ", " det "]),
    ("czech",      ["č", "ř", "ž", "ě", "ů", "ň", " není ", " jsem ", " to "]),
    ("hungarian",  ["ő", "ű", "ó", " nem ", " egy ", " van ", " hogy "]),
    ("turkish",    ["ğ", "ş", "ı", "İ", " bir ", " için ", " değil "]),
    ("finnish",    [" että ", " ei ", "ää", "öö", " on ", " se "]),
    ("swedish",    ["å", "ä", "ö", " inte ", " och ", " att ", " det "]),
    ("norwegian",  ["ø", "æ", " ikke ", " som ", " til ", " det "]),
    ("latam_es",   ["ñ", "¿", "¡", " ustedes ", " acá "]),
]


def guess_latin(strings, sample=6000):
    joined = " " + " ".join(strings[:sample]).lower() + " "
    scores = {n: sum(joined.count(t) for t in toks) for n, toks in LATIN_HINTS}
    return sorted(scores.items(), key=lambda x: -x[1])


SCRIPT_LANG = {"hebrew": "HEBREW", "arabic": "ARABIC", "arabic_pres": "ARABIC(pres-forms)",
               "cyrillic": "RUSSIAN", "greek": "GREEK", "hiragana": "JAPANESE",
               "katakana": "JAPANESE", "hangul": "KOREAN", "thai": "THAI", "cjk": "CHINESE"}


def guess_lang(strings):
    cnt = Counter()
    for s in strings:
        sniff_cp(s, cnt)
    non_latin = {k: v for k, v in cnt.items()
                 if k not in ("ascii", "latin1_accent", "latin_ext_a", "latin_ext_b")}
    if non_latin:
        dom, n = max(non_latin.items(), key=lambda x: x[1])
        if n > 200:
            return SCRIPT_LANG.get(dom, dom.upper()), cnt, None
    best = guess_latin(strings)
    if best and best[0][1] >= 20:
        tag = best[0][0].upper()
        margin = best[0][1] / max(1, best[1][1])
        if margin < 1.35:
            tag += f"?(vs {best[1][0]})"
        return tag, cnt, best[:4]
    return "ENGLISH", cnt, best[:4] if best else None


# ------------------------------------------------------------------ (a) layout
fns = sorted(f for f in os.listdir(LOCS) if f.endswith(".localization"))
print(f"[*] {len(fns)} localization variants in {LOCS}\n", flush=True)

print("=" * 80)
print("(a) ASSET LAYOUT — locate the inner DAT1 magic EMPIRICALLY")
print("=" * 80)
raw0 = open(os.path.join(LOCS, fns[0]), "rb").read()
hexdump(raw0, 0, 96, f"{fns[0]}  (first 96 bytes of the whole asset)")
d1_off, d1_kind = find_dat1(raw0[:8192])
print(f"\n  DAT1 magic bytes '{d1_kind}' first occur at offset = {d1_off}")

offs = defaultdict(list)
for fn in fns:
    r = open(os.path.join(LOCS, fn), "rb").read(8192)
    o, k = find_dat1(r)
    offs[(o, k)].append(fn)
print(f"  same offset across all {len(fns)} variants? "
      + ", ".join(f"offset {o} ('{k}') x{len(v)}" for (o, k), v in offs.items()))

HDR = d1_off
print(f"\n  => outer asset header = {HDR} bytes ; DAT1 payload = raw[{HDR}:]")
print("  (matches the SM2 / R&C 36-byte asset header)" if HDR == 36
      else f"  !! NOT 36 — the SM2/R&C assumption would have been WRONG here")

print(f"\n  the {HDR}-byte outer header decoded as u32 LE:")
for i in range(0, HDR, 4):
    v = struct.unpack_from("<I", raw0, i)[0]
    note = ""
    if v == len(raw0):
        note = "  <- == total asset size"
    if v == len(raw0) - HDR:
        note = "  <- == payload size (asset - header)"
    print(f"    +0x{i:02X}: {v:>12}  0x{v:08X}{note}")

# does every variant share the same outer header shape?
print("\n  outer header across variants (u32 at +0x00 / +0x04 / +0x08):")
for fn in fns[:4] + fns[-2:]:
    r = open(os.path.join(LOCS, fn), "rb").read(HDR)
    a, b, c = struct.unpack_from("<III", r, 0)
    print(f"    {fn[:26]:26} {a:08X} {b:08X} {c:08X}  size={os.path.getsize(os.path.join(LOCS,fn))}")


def load(path):
    raw = open(path, "rb").read()
    return raw, D1(raw[HDR:])


# ------------------------------------------------------------------ (b) sections
print("\n" + "=" * 80)
print("(b) INNER DAT1 SECTIONS")
print("=" * 80)
raw0, d0 = load(os.path.join(LOCS, fns[0]))
print(f"  magic        = 0x{d0.magic:08X} ({'DAT1 OK' if d0.magic == DAT1_MAGIC else 'MISMATCH'})")
print(f"  unk1 (type)  = 0x{d0.unk1:08X}  -> {ASSET_TYPES.get(d0.unk1, '?')}")
print(f"  size field   = {d0.size}   (payload len {len(d0.pay)})")
print(f"  sections     = {len(d0.sections)} ; unknowns = {d0.nunk} ({len(d0.unknowns)} B)")
print(f"  header ends  = {d0.hdr_end} ; first section at {d0.min_off}")
print(f"  string blob  = {len(d0.strings_blob)} B between them\n")
if d0.strings_blob:
    toks = [t for t in d0.strings_blob.split(b"\x00") if t]
    print(f"  string blob: {len(toks)} NUL tokens; samples:")
    for t in toks[:10]:
        print(f"    {t.decode('utf-8','replace')!r}")
    print()

sec_info = []
for t, o, s in d0.sections:
    seg = d0.pay[o:o + s]
    sec_info.append((t, o, s))
    probe = seg[:20000]
    printable = sum(1 for b in probe if 32 <= b < 127 or b in (9, 10, 13))
    ratio = printable / max(1, len(probe))
    nuls = probe.count(0)
    print(f"  tag=0x{t:08X} off={o:>9} size={s:>9}  printable={ratio:6.1%} "
          f"nul={nuls:>6}  first8={seg[:8].hex()}")

# ------------------------------------------------------------------ (c) variance
print("\n" + "=" * 80)
print("(c) PER-SECTION CONTENT VARIANCE ACROSS ALL VARIANTS (sha1 of the FULL section)")
print("=" * 80, flush=True)
tag_hashes = defaultdict(set)
tag_sizes = defaultdict(set)
variant_d1 = {}
for fn in fns:
    _, d = load(os.path.join(LOCS, fn))
    variant_d1[fn] = d
    for t, o, s in d.sections:
        tag_hashes[t].add(hashlib.sha1(d.pay[o:o + s]).hexdigest())
        tag_sizes[t].add(s)

for t, o, s in sec_info:
    nd = len(tag_hashes[t])
    verdict = ("VALUES  <- differs on EVERY variant" if nd == len(fns)
               else "SHARED  <- byte-identical on all" if nd == 1
               else f"partly shared ({nd} distinct)")
    print(f"  tag=0x{t:08X}  distinct_content={nd:>3}/{len(fns)}  "
          f"distinct_sizes={len(tag_sizes[t]):>3}  {verdict}")

values_tag = max(sec_info, key=lambda x: (len(tag_hashes[x[0]]), x[2]))[0]
shared_tags = [t for t, _, _ in sec_info if len(tag_hashes[t]) == 1]
print(f"\n  [+] VALUES section tag = 0x{values_tag:08X}")
print(f"  [+] SHARED  section tags = " + (", ".join(f"0x{t:08X}" for t in shared_tags) or "(none)"))

# ------------------------------------------------------------------ (d) codec
print("\n" + "=" * 80)
print("(d) DECODE THE VALUES SECTION")
print("=" * 80)
vseg0 = variant_d1[fns[0]].seg(values_tag)
hexdump(vseg0, 0, 160, f"values head ({len(vseg0)} bytes)")
print()
hexdump(vseg0, max(0, len(vseg0) - 64), 64, "values tail")

parts = vseg0.split(b"\x00")
nonempty = [p for p in parts if p]
ok = bad = 0
for p in nonempty[:5000]:
    try:
        p.decode("utf-8"); ok += 1
    except UnicodeDecodeError:
        bad += 1
print(f"\n  NUL-split: {len(parts)} parts / {len(nonempty)} non-empty / "
      f"utf-8 OK {ok} , BAD {bad} (of first {min(5000,len(nonempty))})")
print("  first 10 tokens:")
for p in nonempty[:10]:
    print(f"    {p.decode('utf-8','replace')!r}")

print("\n  --- SHARED sections ---")
for t in shared_tags:
    seg = variant_d1[fns[0]].seg(t)
    if not seg:
        print(f"  0x{t:08X}: EMPTY")
        continue
    toks = [x for x in seg.split(b"\x00") if x]
    probe = seg[:20000]
    printable = sum(1 for b in probe if 32 <= b < 127)
    if printable / max(1, len(probe)) > 0.5 and toks:
        print(f"  0x{t:08X}: {len(seg)} B TEXT-LIKE, {len(toks)} NUL tokens; samples:")
        for x in toks[:10]:
            print(f"      {x.decode('utf-8','replace')!r}")
    else:
        divs = " ".join(f"/{n}={len(seg)/n:.2f}" for n in (4, 8, 12, 16, 20, 24))
        print(f"  0x{t:08X}: {len(seg)} B BINARY  {divs}")
        hexdump(seg, 0, 64)

# ------------------------------------------------------------------ (e) map
print("\n" + "=" * 80)
print("(e) LANGUAGE MAP — classify each variant BY ITS OWN VALUES SECTION")
print("=" * 80, flush=True)
probe_meta = {}
pj = os.path.join(LOCS, "_probe.json")
if os.path.exists(pj):
    for r in json.load(open(pj, encoding="utf-8"))["variants"]:
        probe_meta[r["k"]] = r

sys.path.insert(0, HERE)
import msmr_loc

# per-entry value lists so we can measure "identical to English" per variant
T_VAL_OFFS, T_COUNT = 0xF80DEEB4, 0xD540A903
N = struct.unpack("<I", variant_d1[fns[0]].seg(T_COUNT))[0]


def entry_values(fn):
    d = variant_d1[fn]
    vb = d.seg(values_tag)
    vo = struct.unpack(f"<{N}I", d.seg(T_VAL_OFFS))
    out = []
    for o in vo:
        e = vb.find(b"\x00", o)
        out.append(vb[o: e if e >= 0 else len(vb)])
    return out


rows = []
val_by_variant = {}
for k, fn in enumerate(fns):
    d = variant_d1[fn]
    seg = d.seg(values_tag)
    strings = [s.decode("utf-8", "replace") for s in seg.split(b"\x00") if s]
    lang, ev = msmr_loc.classify_language(strings)
    val_by_variant[k] = entry_values(fn)
    pr = probe_meta.get(k, {})
    samples, seen = [], set()
    for s in strings:
        if 12 < len(s) < 70 and any(c.isalpha() for c in s) and s not in seen:
            samples.append(s); seen.add(s)
        if len(samples) >= 3:
            break
    rows.append(dict(k=k, fn=fn, idx=pr.get("index"), span=pr.get("span"),
                     arch=pr.get("archive"), nstr=len(strings), vsize=len(seg),
                     lang=lang, evidence=ev, samples=samples))

# which variant is english? (pick the largest english one as the reference source)
eng = [r for r in rows if r["lang"] == "ENGLISH"]
ref_k = max(eng, key=lambda r: r["nstr"])["k"] if eng else 0
ref_vals = val_by_variant[ref_k]
for r in rows:
    same = sum(1 for a, b in zip(val_by_variant[r["k"]], ref_vals) if a == b)
    r["same_as_en"] = same
    r["same_as_en_pct"] = round(100.0 * same / N, 2)

print(f"\n  reference ENGLISH = variant_{ref_k:02d}\n")
print(f"  {'var':>3} {'assetIdx':>9} {'span':>4} {'uniqVals':>8} {'valuesB':>9} "
      f"{'==EN':>7} {'==EN%':>7}  LANGUAGE")
print("  " + "-" * 88)
for r in rows:
    print(f"  {r['k']:>3} {str(r['idx']):>9} {str(r['span']):>4} {r['nstr']:>8} "
          f"{r['vsize']:>9} {r['same_as_en']:>7} {r['same_as_en_pct']:>6.1f}%  {r['lang']}")

print("\n  === evidence per variant ===")
for r in rows:
    ev = r["evidence"]
    na = {k: v for k, v in ev["chars"].items() if k != "ascii" and v > 30}
    top = ", ".join(f"{k}={v}" for k, v in sorted(na.items(), key=lambda x: -x[1])[:4])
    extra = {k: v for k, v in ev.items()
             if k in ("dk_vs_no", "sv_vs_fi", "es_variant", "pt_variant", "cjk_simpl", "cjk_trad")}
    print(f"  v{r['k']:02d} {r['lang']:<22} acc={ev.get('accent_density',0):.4f} {top}"
          + (f"  {extra}" if extra else ""))

print("\n  === 3 real sample strings per variant ===")
for r in rows:
    print(f"\n  variant_{r['k']:02d}  idx={r['idx']}  span={r['span']}  {r['lang']}"
          f"  (=={r['same_as_en_pct']}% of English)")
    for s in r["samples"]:
        print(f"      {s!r}")

ar = [r for r in rows if r["lang"].startswith("ARABIC")]
he = [r for r in rows if r["lang"].startswith("HEBREW")]
untr = [r for r in rows if r["k"] != ref_k and r["same_as_en_pct"] > 95]
print("\n" + "=" * 80)
print("  VERDICT")
print("=" * 80)
print("  ARABIC  slot (would be the Hebrew target): " +
      (", ".join(f"variant_{r['k']:02d}" for r in ar) or "*** NONE — NO ARABIC TEXT SHIPS ***"))
print("  HEBREW  slot                             : " +
      (", ".join(f"variant_{r['k']:02d}" for r in he) or "NONE"))
print("  ENGLISH (source)                         : " +
      (", ".join(f"variant_{r['k']:02d} idx={r['idx']} span={r['span']}" for r in eng) or "NONE"))
print("  UNTRANSLATED slots (>95% identical to English — free sacrifice slots): " +
      (", ".join(f"variant_{r['k']:02d}(span {r['span']})" for r in untr) or "none"))

out = os.path.join(LOCS, "_langmap.json")
with open(out, "w", encoding="utf-8") as fo:
    json.dump(dict(header_bytes=HDR, dat1_unk1=f"0x{d0.unk1:08X}",
                   values_tag=f"0x{values_tag:08X}",
                   shared_tags=[f"0x{t:08X}" for t in shared_tags],
                   entry_count=N, english_variant=ref_k,
                   sections=[dict(tag=f"0x{t:08X}", offset=o, size=s) for t, o, s in sec_info],
                   variants=rows), fo, ensure_ascii=False, indent=2)
print(f"\n[+] wrote {out}")
