"""FULL font inventory of d/userinterface + d/conduit.

Raw-scan the archive bytes for EVERY font magic (TrueType 00010000, OTTO,
ttcf, wOFF, wOF2). Previous scans only looked for OTTO and so missed every
TrueType .ttf (AzbukaPro + any TrueType fallback). For each validated font:
report family/subfamily + Hebrew vs Arabic glyph coverage. The font that
covers Arabic but NOT Hebrew is the one cohtml uses to render the Arabic
slot -> our replacement target.
"""
import os, sys, struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
OUT  = os.path.join(ROOT, "games", "spiderman2", "extracted", "all_fonts")
os.makedirs(OUT, exist_ok=True)

ARCHIVES = ["userinterface", "conduit"]

KNOWN = {b"CFF ", b"CFF2", b"head", b"hhea", b"maxp", b"name", b"post",
         b"OS/2", b"cmap", b"glyf", b"loca", b"GPOS", b"GSUB", b"hmtx",
         b"vmtx", b"vhea", b"DSIG", b"BASE", b"GDEF", b"fpgm", b"prep",
         b"cvt ", b"gasp", b"kern"}

NAME_IDS = {0:"Copyright",1:"Family",2:"Subfamily",4:"FullName",6:"PostScript"}

# Insomniac custom sfnt: table-directory offsets are stored +36 from the real
# byte position. true_offset = stored_offset - DELTA. (verified: head.magic at
# 212 when record said 236). We parse name/cmap at both delta 0 and 36 and keep
# whichever yields sane data.
DELTAS = (0, 36)


def validate(buf, j, magic):
    """Return total font length if a valid sfnt table directory sits at j."""
    if buf[j:j+4] != magic:
        return None
    if j + 12 > len(buf):
        return None
    nt = struct.unpack(">H", buf[j+4:j+6])[0]
    if not (4 <= nt <= 40):
        return None
    if j + 12 + nt*16 > len(buf):
        return None
    extents = []
    known = 0
    for k in range(nt):
        rec = buf[j+12 + k*16 : j+12 + (k+1)*16]
        tag = rec[:4]
        if not all(0x20 <= b <= 0x7E for b in tag):
            return None
        off = struct.unpack(">I", rec[8:12])[0]
        ln  = struct.unpack(">I", rec[12:16])[0]
        extents.append((tag, off, ln))
        if tag in KNOWN:
            known += 1
    if known < 5:
        return None
    total = max(o+l for _, o, l in extents)
    if total > len(buf) - j:
        return None
    return total


def read_names(buf, j, delta=0):
    nt = struct.unpack(">H", buf[j+4:j+6])[0]
    for k in range(nt):
        rec = buf[j+12 + k*16 : j+12 + (k+1)*16]
        if rec[:4] == b"name":
            off = struct.unpack(">I", rec[8:12])[0] - delta
            ln  = struct.unpack(">I", rec[12:16])[0]
            n = buf[j+off : j+off+ln]
            if len(n) < 6:
                return {}
            fmt, count, soff = struct.unpack(">HHH", n[:6])
            strings = n[soff:]
            rows = {}
            for i in range(count):
                r2 = n[6 + i*12 : 6 + (i+1)*12]
                if len(r2) < 12:
                    break
                plat, enc, lang, nid, slen, sro = struct.unpack(">HHHHHH", r2)
                if sro + slen > len(strings):
                    continue
                s = strings[sro:sro+slen]
                if plat == 3:
                    try:
                        rows.setdefault(nid, s.decode("utf-16-be", "replace"))
                    except Exception:
                        pass
                elif plat == 1 and nid not in rows:
                    try:
                        rows.setdefault(nid, s.decode("latin-1", "replace"))
                    except Exception:
                        pass
            return rows
    return {}


def cmap_coverage(buf, j, delta=0):
    """Return set of covered codepoints (BMP + via format 4/12)."""
    nt = struct.unpack(">H", buf[j+4:j+6])[0]
    cmap_off = None
    for k in range(nt):
        rec = buf[j+12 + k*16 : j+12 + (k+1)*16]
        if rec[:4] == b"cmap":
            cmap_off = j + struct.unpack(">I", rec[8:12])[0] - delta
            break
    if cmap_off is None:
        return set()
    c = buf[cmap_off:]
    if len(c) < 4:
        return set()
    version, num = struct.unpack(">HH", c[:4])
    best = None
    for k in range(num):
        sh = c[4 + k*8 : 4 + (k+1)*8]
        if len(sh) < 8:
            break
        plat, enc, sub_off = struct.unpack(">HHI", sh)
        if plat == 3 and enc == 10:      # full UCS-4, prefer
            best = sub_off; break
        if (plat == 0) or (plat == 3 and enc == 1):
            best = sub_off
    if best is None:
        return set()
    sub = c[best:]
    if len(sub) < 4:
        return set()
    fmt = struct.unpack(">H", sub[:2])[0]
    cps = set()
    try:
        if fmt == 4:
            seg2 = struct.unpack(">H", sub[6:8])[0]
            seg = seg2 // 2
            ec_off = 14
            sc_off = ec_off + 2*seg + 2
            end = struct.unpack(f">{seg}H", sub[ec_off:ec_off+2*seg])
            start = struct.unpack(f">{seg}H", sub[sc_off:sc_off+2*seg])
            for s, e in zip(start, end):
                if s == 0xFFFF:
                    continue
                for cp in range(s, min(e, 0xFFFF) + 1):
                    cps.add(cp)
        elif fmt == 12:
            ng = struct.unpack(">I", sub[12:16])[0]
            go = 16
            for g in range(ng):
                rec = sub[go + g*12 : go + (g+1)*12]
                if len(rec) < 12:
                    break
                sc, ec, _ = struct.unpack(">III", rec)
                if ec - sc > 100000:
                    continue
                for cp in range(sc, ec + 1):
                    cps.add(cp)
        elif fmt == 6:
            first, cnt = struct.unpack(">HH", sub[6:10])
            for i in range(cnt):
                cps.add(first + i)
    except Exception:
        pass
    return cps


def cov(cps, lo, hi):
    n = sum(1 for cp in cps if lo <= cp <= hi)
    return n, (hi - lo + 1)


results = []
for arch in ARCHIVES:
    path = os.path.join(GAME, "d", arch)
    if not os.path.exists(path):
        print(f"[!] missing {path}")
        continue
    data = open(path, "rb").read()
    print(f"\n[*] scanning d/{arch}  ({len(data):,} bytes)")
    for magic in (b"\x00\x01\x00\x00", b"OTTO", b"ttcf"):
        i = 0
        while True:
            j = data.find(magic, i)
            if j < 0:
                break
            i = j + 4
            total = validate(data, j, magic)
            if not total or not (8000 < total < 80_000_000):
                continue
            # Insomniac fonts store table offsets +36; try both, keep richest.
            best = (0, {}, set())
            for delta in DELTAS:
                nm = read_names(data, j, delta) or {}
                cp = cmap_coverage(data, j, delta)
                score = len(cp) + (1000 if nm.get(1) else 0)
                if score > best[0]:
                    best = (score, nm, cp)
            names, cps = best[1], best[2]
            fam = names.get(1, "?")
            sub = names.get(2, "")
            heb = cov(cps, 0x0590, 0x05FF)
            ara = cov(cps, 0x0600, 0x06FF)
            lat = cov(cps, 0x0041, 0x007A)
            cyr = cov(cps, 0x0400, 0x04FF)
            results.append((arch, j, total, magic, fam, sub,
                            len(cps), heb, ara, lat, cyr))
            print(f"  ★ off={j:>10} size={total:>9} {magic!r} "
                  f"fam={fam!r} sub={sub!r}")
            print(f"      glyphs={len(cps):>6}  HEB={heb[0]}/{heb[1]}  "
                  f"ARA={ara[0]}/{ara[1]}  LAT={lat[0]}/{lat[1]}  "
                  f"CYR={cyr[0]}/{cyr[1]}")

print("\n" + "=" * 70)
print(f"TOTAL fonts found: {len(results)}")
print("=" * 70)
print(f"{'arch':<14}{'off':>11}{'size':>10}  {'HEB':>7} {'ARA':>7}  family")
for arch, j, total, magic, fam, sub, ng, heb, ara, lat, cyr in results:
    flag = ""
    if ara[0] > 50 and heb[0] < 10:
        flag = "  <<< ARABIC-ONLY (replace target)"
    elif ara[0] > 50 and heb[0] > 20:
        flag = "  (covers both)"
    print(f"{arch:<14}{j:>11}{total:>10}  {heb[0]:>3}/{heb[1]:<3} "
          f"{ara[0]:>3}/{ara[1]:<3}  {fam!r}{flag}")

# Save each font to disk for follow-up
for arch, j, total, magic, fam, sub, ng, heb, ara, lat, cyr in results:
    data = open(os.path.join(GAME, "d", arch), "rb").read()
    ext = ".otf" if magic == b"OTTO" else (".ttc" if magic == b"ttcf" else ".ttf")
    safe = "".join(ch if (ch.isalnum() or ch in "._-") else "_"
                   for ch in (str(fam) + "_" + str(sub)))[:50] or "font"
    outp = os.path.join(OUT, f"{arch}_off{j}_{safe}{ext}")
    with open(outp, "wb") as wf:
        wf.write(data[j:j+total])
print(f"\n[+] saved {len(results)} fonts -> {OUT}")
