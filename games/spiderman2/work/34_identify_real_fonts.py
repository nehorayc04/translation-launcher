"""Identify the 4 reconstructed OTFs — name + Unicode coverage."""
import os, struct
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
DIR = os.path.join(ROOT, "games", "spiderman2", "extracted", "reconstructed_otf")

NAME_IDS = {0:"Copyright",1:"Family",2:"Subfamily",3:"UniqueID",4:"FullName",
            5:"Version",6:"PostScript",7:"Trademark",8:"Manufacturer",
            9:"Designer",16:"PreferredFamily",17:"PreferredSubfamily"}

def parse(data, label):
    print(f"\n=== {label} ({len(data)} bytes) ===")
    magic = data[:4]
    nt = struct.unpack(">H", data[4:6])[0]
    print(f"  magic={magic!r} numTables={nt}")
    tables = {}
    for k in range(nt):
        rec = data[12 + k*16 : 12 + (k+1)*16]
        tag = rec[:4]
        off = struct.unpack(">I", rec[8:12])[0]
        ln  = struct.unpack(">I", rec[12:16])[0]
        tables[tag] = (off, ln)

    # name
    if b"name" in tables:
        off, ln = tables[b"name"]
        n = data[off:off+ln]
        try:
            fmt, count, soff = struct.unpack(">HHH", n[:6])
            strings = n[soff:]
            rows = {}
            for i in range(count):
                rec2 = n[6 + i*12 : 6 + (i+1)*12]
                if len(rec2) < 12: break
                plat, enc, lang, nid, slen, srecoff = struct.unpack(">HHHHHH", rec2)
                if srecoff + slen > len(strings): continue
                s = strings[srecoff:srecoff+slen]
                if plat == 3:
                    try: rows.setdefault(nid, s.decode("utf-16-be", "replace"))
                    except: pass
            for k_id in (1, 2, 4, 5, 6, 8, 16, 17):
                if k_id in rows:
                    print(f"  name[{NAME_IDS.get(k_id, str(k_id)):<18}]: {rows[k_id]!r}")
        except Exception as e:
            print(f"  name table parse error: {e}")

    # cmap → coverage
    if b"cmap" in tables:
        off, ln = tables[b"cmap"]
        c = data[off:off+ln]
        try:
            version, num_subtables = struct.unpack(">HH", c[:4])
            best = None   # (priority, offset)
            for k in range(num_subtables):
                sh = c[4 + k*8 : 4 + (k+1)*8]
                plat, enc, sub_off = struct.unpack(">HHI", sh)
                # prefer (3,10) > (3,1) > (0,*)
                pri = -1
                if plat == 3 and enc == 10: pri = 3
                elif plat == 3 and enc == 1: pri = 2
                elif plat == 0: pri = 1
                if pri > 0 and (best is None or pri > best[0]):
                    best = (pri, sub_off)
            if best:
                sub = c[best[1]:]
                fmt = struct.unpack(">H", sub[:2])[0]
                print(f"  cmap subtable format={fmt}")
                codepoints = set()
                if fmt == 4 and len(sub) >= 14:
                    seg_count_x2 = struct.unpack(">H", sub[6:8])[0]
                    seg_count = seg_count_x2 // 2
                    end_codes = struct.unpack(f">{seg_count}H", sub[14 : 14 + 2*seg_count])
                    start_codes = struct.unpack(f">{seg_count}H", sub[14 + 2*seg_count + 2 : 14 + 4*seg_count + 2])
                    for s, e in zip(start_codes, end_codes):
                        if s == 0xFFFF and e == 0xFFFF: continue
                        for cp in range(s, min(e, 0xFFFF) + 1):
                            codepoints.add(cp)
                elif fmt == 12 and len(sub) >= 16:
                    num_groups = struct.unpack(">I", sub[12:16])[0]
                    for g in range(num_groups):
                        rec = sub[16 + g*12 : 16 + (g+1)*12]
                        sc, ec, _ = struct.unpack(">III", rec)
                        for cp in range(sc, min(ec, 0x10FFFF) + 1):
                            codepoints.add(cp)
                def cov(name, lo, hi):
                    in_range = sum(1 for cp in codepoints if lo <= cp <= hi)
                    total = hi - lo + 1
                    pct = 100.0*in_range/total if total else 0
                    return f"{in_range:>5}/{total:<5} ({pct:>5.1f}%)"
                print(f"  total mapped codepoints: {len(codepoints)}")
                print(f"  Latin Basic    (U+0020-007F):    {cov('lat', 0x0020, 0x007F)}")
                print(f"  Latin-1 Supp   (U+0080-00FF):    {cov('lat1', 0x0080, 0x00FF)}")
                print(f"  Hebrew         (U+0590-05FF):    {cov('he', 0x0590, 0x05FF)}")
                print(f"  Arabic         (U+0600-06FF):    {cov('ar', 0x0600, 0x06FF)}")
                print(f"  Arab.Presents.A(U+FB50-FDFF):    {cov('arpA', 0xFB50, 0xFDFF)}")
                print(f"  Arab.Presents.B(U+FE70-FEFF):    {cov('arpB', 0xFE70, 0xFEFF)}")
                print(f"  Cyrillic       (U+0400-04FF):    {cov('cyr', 0x0400, 0x04FF)}")
                print(f"  Greek          (U+0370-03FF):    {cov('grk', 0x0370, 0x03FF)}")
                print(f"  CJK Unified    (U+4E00-9FFF):    {cov('cjk', 0x4E00, 0x9FFF)}")
                print(f"  Hiragana       (U+3040-309F):    {cov('hir', 0x3040, 0x309F)}")
                print(f"  Hangul         (U+AC00-D7AF):    {cov('hng', 0xAC00, 0xD7AF)}")
                print(f"  Thai           (U+0E00-0E7F):    {cov('thai', 0x0E00, 0x0E7F)}")
        except Exception as e:
            print(f"  cmap parse error: {e}")

for fn in sorted(os.listdir(DIR)):
    if fn.endswith(".otf"):
        parse(open(os.path.join(DIR, fn), "rb").read(), fn)
