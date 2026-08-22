"""Confirm the diagnosis: parse the extracted standard TTFs and report
Hebrew vs Arabic vs Latin glyph coverage for each fontmap font."""
import os, struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SRC = os.path.join(ROOT, "games", "spiderman2", "extracted", "fontmap_assets")


def tables(data):
    nt = struct.unpack(">H", data[4:6])[0]
    t = {}
    for k in range(nt):
        rec = data[12 + k*16: 12 + (k+1)*16]
        tag = rec[:4]
        off, ln = struct.unpack(">II", rec[8:16])
        t[tag] = (off, ln)
    return t


def names(data):
    t = tables(data)
    if b"name" not in t:
        return {}
    off, ln = t[b"name"]
    n = data[off:off+ln]
    fmt, count, soff = struct.unpack(">HHH", n[:6])
    strings = n[soff:]
    rows = {}
    for i in range(count):
        r = n[6+i*12:6+(i+1)*12]
        if len(r) < 12:
            break
        plat, enc, lang, nid, slen, sro = struct.unpack(">HHHHHH", r)
        if sro+slen > len(strings):
            continue
        if plat == 3:
            try:
                rows.setdefault(nid, strings[sro:sro+slen].decode("utf-16-be", "replace"))
            except Exception:
                pass
    return rows


def cmap_cps(data):
    t = tables(data)
    if b"cmap" not in t:
        return set()
    off, ln = t[b"cmap"]
    c = data[off:off+ln]
    ver, num = struct.unpack(">HH", c[:4])
    best = None
    for k in range(num):
        plat, enc, so = struct.unpack(">HHI", c[4+k*8:12+k*8])
        if plat == 3 and enc == 10:
            best = so; break
        if (plat == 0) or (plat == 3 and enc == 1):
            best = so
    if best is None:
        return set()
    sub = c[best:]
    fmt = struct.unpack(">H", sub[:2])[0]
    cps = set()
    if fmt == 4:
        seg = struct.unpack(">H", sub[6:8])[0] // 2
        eo = 14; so = eo + 2*seg + 2
        end = struct.unpack(f">{seg}H", sub[eo:eo+2*seg])
        start = struct.unpack(f">{seg}H", sub[so:so+2*seg])
        for s, e in zip(start, end):
            if s != 0xFFFF:
                cps.update(range(s, min(e, 0xFFFF)+1))
    elif fmt == 12:
        ng = struct.unpack(">I", sub[12:16])[0]
        for g in range(ng):
            sc, ec, _ = struct.unpack(">III", sub[16+g*12:28+g*12])
            if ec-sc < 100000:
                cps.update(range(sc, ec+1))
    return cps


def cov(cps, lo, hi):
    return sum(1 for cp in cps if lo <= cp <= hi), hi-lo+1


print(f"{'font':<34}{'family':<22}{'HEB':>9}{'ARA':>9}{'LAT':>9}{'CYR':>9}")
for fn in sorted(os.listdir(SRC)):
    if not fn.endswith(".rawasset"):
        continue
    data = open(os.path.join(SRC, fn), "rb").read()
    if data[:4] not in (b"\x00\x01\x00\x00", b"OTTO", b"true"):
        print(f"{fn:<34} (magic {data[:4].hex()})")
        continue
    fam = names(data).get(1, "?")
    cps = cmap_cps(data)
    h = cov(cps, 0x0590, 0x05FF)
    a = cov(cps, 0x0600, 0x06FF)
    l = cov(cps, 0x0041, 0x007A)
    c = cov(cps, 0x0400, 0x04FF)
    name = fn.replace(".rawasset", "")
    print(f"{name:<34}{str(fam):<22}{h[0]:>4}/{h[1]:<4}{a[0]:>4}/{a[1]:<4}"
          f"{l[0]:>4}/{l[1]:<4}{c[0]:>4}/{c[1]:<4}")
