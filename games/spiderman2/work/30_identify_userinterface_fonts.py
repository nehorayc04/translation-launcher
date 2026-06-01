"""Identify each font found in d/userinterface — Family, Subfamily, glyph count,
Unicode coverage."""
import os, struct
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
FONT_DIR = os.path.join(ROOT, "games", "spiderman2", "extracted", "found_fonts")

NAME_IDS = {0:"Copyright",1:"Family",2:"Subfamily",3:"UniqueID",4:"FullName",
            5:"Version",6:"PostScript",7:"Trademark",8:"Manufacturer",
            9:"Designer",16:"PreferredFamily",17:"PreferredSubfamily"}

def parse_font(data, label):
    print(f"\n=== {label} ({len(data)} bytes) ===")
    magic = data[:4]
    if magic not in (b"OTTO", b"\x00\x01\x00\x00", b"ttcf"):
        print(f"  !! magic = {magic!r}")
        return
    nt = struct.unpack(">H", data[4:6])[0]
    print(f"  magic={magic!r} numTables={nt}")
    tables = {}
    for k in range(nt):
        rec = data[12 + k*16 : 12 + (k+1)*16]
        tag = rec[:4]
        off = struct.unpack(">I", rec[8:12])[0]
        ln  = struct.unpack(">I", rec[12:16])[0]
        tables[tag] = (off, ln)

    # name table
    if b"name" in tables:
        off, ln = tables[b"name"]
        n = data[off:off+ln]
        fmt, count, soff = struct.unpack(">HHH", n[:6])
        strings = n[soff:]
        rows = {}
        for i in range(count):
            rec = n[6 + i*12 : 6 + (i+1)*12]
            if len(rec) < 12:
                break
            plat, enc, lang, nid, slen, srecoff = struct.unpack(">HHHHHH", rec)
            if srecoff + slen > len(strings):
                continue
            s = strings[srecoff:srecoff+slen]
            if plat == 3:
                try:
                    rows.setdefault(nid, s.decode("utf-16-be", "replace"))
                except: pass
        for k_id in (1, 2, 4, 6, 8, 16, 17):
            if k_id in rows:
                print(f"  name[{NAME_IDS.get(k_id, str(k_id)):<18}]: {rows[k_id]!r}")

    # cmap — count glyphs + check Hebrew/Arabic coverage
    if b"cmap" in tables:
        off, ln = tables[b"cmap"]
        c = data[off:off+ln]
        if len(c) >= 4:
            version, num_subtables = struct.unpack(">HH", c[:4])
            # Walk subtables to find Unicode (platform 0 OR platform 3 enc 1/10)
            unicode_subtable = None
            for k in range(num_subtables):
                sh_rec = c[4 + k*8 : 4 + (k+1)*8]
                plat, enc, sub_off = struct.unpack(">HHI", sh_rec)
                if (plat == 0) or (plat == 3 and enc in (1, 10)):
                    unicode_subtable = sub_off
                    break
            if unicode_subtable is not None:
                sub = c[unicode_subtable:]
                if len(sub) >= 4:
                    fmt = struct.unpack(">H", sub[:2])[0]
                    print(f"  cmap subtable format={fmt}")
                    # Format 4: BMP only.   Format 12: full Unicode.
                    codepoints = set()
                    if fmt == 4 and len(sub) >= 14:
                        seg_count_x2 = struct.unpack(">H", sub[6:8])[0]
                        seg_count = seg_count_x2 // 2
                        ec_off = 14
                        sc_off = ec_off + 2*seg_count + 2
                        end_codes = struct.unpack(f">{seg_count}H", sub[ec_off : ec_off + 2*seg_count])
                        start_codes = struct.unpack(f">{seg_count}H", sub[sc_off : sc_off + 2*seg_count])
                        for s, e in zip(start_codes, end_codes):
                            if e == 0xFFFF and s == 0xFFFF: continue
                            # Only test specific ranges to keep this cheap
                            for cp in range(s, min(e, 0xFFFF) + 1):
                                codepoints.add(cp)
                    elif fmt == 12 and len(sub) >= 16:
                        num_groups = struct.unpack(">I", sub[12:16])[0]
                        groups_off = 16
                        for g in range(num_groups):
                            rec = sub[groups_off + g*12 : groups_off + (g+1)*12]
                            sc, ec, _ = struct.unpack(">III", rec)
                            for cp in range(sc, ec + 1):
                                codepoints.add(cp)

                    # Coverage report
                    def cov(name, lo, hi):
                        in_range = sum(1 for cp in codepoints if lo <= cp <= hi)
                        total = hi - lo + 1
                        return f"{in_range}/{total}"
                    print(f"  glyph count (cmap): {len(codepoints)}")
                    print(f"  Hebrew (U+0590..05FF):   {cov('hebrew', 0x0590, 0x05FF)}")
                    print(f"  Arabic (U+0600..06FF):   {cov('arabic', 0x0600, 0x06FF)}")
                    print(f"  Latin Basic (U+0020..007F):  {cov('ascii', 0x0020, 0x007F)}")
                    print(f"  Cyrillic (U+0400..04FF):   {cov('cyrillic', 0x0400, 0x04FF)}")
                    print(f"  CJK (U+4E00..9FFF):   {cov('cjk', 0x4E00, 0x9FFF)}")
                    print(f"  Hangul (U+AC00..D7AF):   {cov('hangul', 0xAC00, 0xD7AF)}")

for fn in sorted(os.listdir(FONT_DIR)):
    if not fn.endswith(".bin"): continue
    p = os.path.join(FONT_DIR, fn)
    try:
        parse_font(open(p, "rb").read(), fn)
    except Exception as ex:
        print(f"  !! parse failed: {ex}")
