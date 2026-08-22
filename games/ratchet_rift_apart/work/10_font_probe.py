"""R&C Rift Apart FONT recon.
(1) Try known Insomniac font asset paths via crc64 against the R&C toc.
(2) Raw-scan the small UI archives (conduit/config + any tex_ui) for sfnt fonts,
    parse name+cmap (Insomniac delta 0/36), report Hebrew/Arabic/Latin coverage.
Read-only. Mirrors SM2 scripts 52 + 57.
"""
import os, sys, struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = "F:/Game Lab/Ratchet & Clank - Rift Apart"
TOC  = os.path.join(GAME, "toc")
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib
from dat1lib import crc64

KNOWN = {b"CFF ", b"CFF2", b"head", b"hhea", b"maxp", b"name", b"post",
         b"OS/2", b"cmap", b"glyf", b"loca", b"GPOS", b"GSUB", b"hmtx",
         b"vmtx", b"vhea", b"DSIG", b"BASE", b"GDEF", b"fpgm", b"prep",
         b"cvt ", b"gasp", b"kern"}
NAME_IDS = {0: "Copyright", 1: "Family", 2: "Subfamily", 4: "FullName", 6: "PostScript"}
DELTAS = (0, 36)


def validate(buf, j, magic):
    if buf[j:j+4] != magic: return None
    if j + 12 > len(buf): return None
    nt = struct.unpack(">H", buf[j+4:j+6])[0]
    if not (4 <= nt <= 40): return None
    if j + 12 + nt*16 > len(buf): return None
    extents, known = [], 0
    for k in range(nt):
        rec = buf[j+12 + k*16: j+12 + (k+1)*16]
        tag = rec[:4]
        if not all(0x20 <= b <= 0x7E for b in tag): return None
        off = struct.unpack(">I", rec[8:12])[0]
        ln = struct.unpack(">I", rec[12:16])[0]
        extents.append((tag, off, ln))
        if tag in KNOWN: known += 1
    if known < 5: return None
    total = max(o+l for _, o, l in extents)
    if total > len(buf) - j: return None
    return total


def read_names(buf, j, delta=0):
    nt = struct.unpack(">H", buf[j+4:j+6])[0]
    for k in range(nt):
        rec = buf[j+12 + k*16: j+12 + (k+1)*16]
        if rec[:4] == b"name":
            off = struct.unpack(">I", rec[8:12])[0] - delta
            ln = struct.unpack(">I", rec[12:16])[0]
            n = buf[j+off: j+off+ln]
            if len(n) < 6: return {}
            fmt, count, soff = struct.unpack(">HHH", n[:6])
            strings = n[soff:]
            rows = {}
            for i in range(count):
                r2 = n[6 + i*12: 6 + (i+1)*12]
                if len(r2) < 12: break
                plat, enc, lang, nid, slen, sro = struct.unpack(">HHHHHH", r2)
                if sro + slen > len(strings): continue
                s = strings[sro:sro+slen]
                if plat == 3:
                    try: rows.setdefault(nid, s.decode("utf-16-be", "replace"))
                    except Exception: pass
                elif plat == 1 and nid not in rows:
                    try: rows.setdefault(nid, s.decode("latin-1", "replace"))
                    except Exception: pass
            return rows
    return {}


def cmap_coverage(buf, j, delta=0):
    nt = struct.unpack(">H", buf[j+4:j+6])[0]
    cmap_off = None
    for k in range(nt):
        rec = buf[j+12 + k*16: j+12 + (k+1)*16]
        if rec[:4] == b"cmap":
            cmap_off = j + struct.unpack(">I", rec[8:12])[0] - delta
            break
    if cmap_off is None: return set()
    c = buf[cmap_off:]
    if len(c) < 4: return set()
    version, num = struct.unpack(">HH", c[:4])
    best = None
    for k in range(num):
        sh = c[4 + k*8: 4 + (k+1)*8]
        if len(sh) < 8: break
        plat, enc, sub_off = struct.unpack(">HHI", sh)
        if plat == 3 and enc == 10: best = sub_off; break
        if (plat == 0) or (plat == 3 and enc == 1): best = sub_off
    if best is None: return set()
    sub = c[best:]
    if len(sub) < 4: return set()
    fmt = struct.unpack(">H", sub[:2])[0]
    cps = set()
    try:
        if fmt == 4:
            seg2 = struct.unpack(">H", sub[6:8])[0]; seg = seg2 // 2
            ec_off = 14; sc_off = ec_off + 2*seg + 2
            end = struct.unpack(f">{seg}H", sub[ec_off:ec_off+2*seg])
            start = struct.unpack(f">{seg}H", sub[sc_off:sc_off+2*seg])
            for s, e in zip(start, end):
                if s == 0xFFFF: continue
                for cp in range(s, min(e, 0xFFFF)+1): cps.add(cp)
        elif fmt == 12:
            ng = struct.unpack(">I", sub[12:16])[0]; go = 16
            for g in range(ng):
                rec = sub[go + g*12: go + (g+1)*12]
                if len(rec) < 12: break
                sc, ec, _ = struct.unpack(">III", rec)
                if ec - sc > 100000: continue
                for cp in range(sc, ec+1): cps.add(cp)
        elif fmt == 6:
            first, cnt = struct.unpack(">HH", sub[6:10])
            for i in range(cnt): cps.add(first + i)
    except Exception: pass
    return cps


def cov(cps, lo, hi):
    return sum(1 for cp in cps if lo <= cp <= hi), (hi - lo + 1)


# ---------- (1) known font paths via crc64 ----------
print("="*70)
print("(1) KNOWN Insomniac font asset paths via crc64 in R&C toc")
print("="*70)
with open(TOC, "rb") as f:
    toc = dat1lib.read(f)
toc.set_archives_dir(GAME)
archs = toc.get_archives_section()
arch_name = {}
for i, a in enumerate(archs.archives):
    arch_name[i] = bytes(a.filename).split(b"\x00")[0].decode("ascii", "replace")

PREFIXES = ["ui/loaded/authored/_common/fonts/", "ui/loaded/authored/_common/font/",
            "ui/loaded/authored/_common/", "loaded/authored/_common/fonts/",
            "authored/_common/fonts/", "_common/fonts/", "fonts/", "conduit/fonts/", ""]
NAMES = ["NeueFrutigerArabic-Regular.ttf", "AzbukaPro-Regular.ttf", "AzbukaPro-Medium.ttf",
         "AzbukaPro-Bold.ttf", "AzbukaPro-Black.ttf", "MagicSpellJF.otf",
         "Insomniac-Regular.ttf", "Frutiger.ttf"]
for name in NAMES:
    hit = None
    for pre in PREFIXES:
        aid = crc64.hash(pre + name)
        entries = toc.get_asset_entries_by_assetid(aid, stop_on_first=True)
        if entries:
            e = entries[0]
            print(f"[+] {name}  path={pre+name!r} archive={e.archive}({arch_name.get(e.archive,'?')}) off={e.offset} size={e.size}")
            hit = True
            break
    if not hit:
        print(f"[-] {name}: no path variant matched")

# ---------- (2) raw-scan small archives for sfnt ----------
print("\n" + "="*70)
print("(2) RAW-SCAN R&C UI archives for embedded sfnt fonts")
print("="*70)
SCAN = ["conduit", "config", "tex_ui", "tex_coretest"]
results = []
for arch in SCAN:
    path = os.path.join(GAME, "d", arch)
    if not os.path.exists(path):
        print(f"[!] missing d/{arch}")
        continue
    data = open(path, "rb").read()
    print(f"\n[*] scan d/{arch} ({len(data):,} bytes)")
    for magic in (b"\x00\x01\x00\x00", b"OTTO", b"ttcf"):
        i = 0
        while True:
            j = data.find(magic, i)
            if j < 0: break
            i = j + 4
            total = validate(data, j, magic)
            if not total or not (8000 < total < 80_000_000): continue
            best = (0, {}, set())
            for delta in DELTAS:
                nm = read_names(data, j, delta) or {}
                cp = cmap_coverage(data, j, delta)
                score = len(cp) + (1000 if nm.get(1) else 0)
                if score > best[0]: best = (score, nm, cp)
            names, cps = best[1], best[2]
            fam = names.get(1, "?"); sub = names.get(2, "")
            heb = cov(cps, 0x0590, 0x05FF); ara = cov(cps, 0x0600, 0x06FF)
            lat = cov(cps, 0x0041, 0x007A); cyr = cov(cps, 0x0400, 0x04FF)
            results.append((arch, j, total, magic, fam, sub, len(cps), heb, ara, lat, cyr))
            print(f"  * off={j} size={total} {magic!r} fam={fam!r} sub={sub!r}")
            print(f"      glyphs={len(cps)} HEB={heb[0]}/{heb[1]} ARA={ara[0]}/{ara[1]} LAT={lat[0]}/{lat[1]} CYR={cyr[0]}/{cyr[1]}")

print("\n" + "="*70)
print(f"SUMMARY: {len(results)} fonts")
for arch, j, total, magic, fam, sub, ng, heb, ara, lat, cyr in results:
    flag = ""
    if heb[0] > 20: flag = "  <<< HAS HEBREW"
    elif ara[0] > 50: flag = "  (Arabic, no Hebrew)"
    print(f"  d/{arch:<10} off={j:<9} {heb[0]:>3}/27heb {ara[0]:>3}ara {lat[0]:>2}lat fam={fam!r}{flag}")

# also dump font-related strings from config (fontmap)
print("\n" + "="*70)
print("(3) font path strings in d/config + d/conduit")
import re
for arch in ("config", "conduit"):
    p = os.path.join(GAME, "d", arch)
    if not os.path.exists(p): continue
    buf = open(p, "rb").read()
    seen = set()
    for m in re.finditer(rb"[ -~]{4,200}", buf):
        s = m.group()
        if b".ttf" in s or b".otf" in s or b"font" in s.lower() or b"Frutiger" in s or b"Azbuka" in s:
            t = s.decode("latin-1")
            if t not in seen:
                seen.add(t)
                print(f"  d/{arch} [{m.start()}] {t!r}")
