"""Locate the R&C TTF font assets by their now-known exact paths, extract, and
report Family + Hebrew/Arabic/Latin/Cyrillic coverage. Also dump the uifontmap
config. Read-only."""
import os, sys, struct
GAME = "F:/Game Lab/Ratchet & Clank - Rift Apart"
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib
from dat1lib import crc64

FONT_PATHS = [
    "ui/loaded/authored/_common/fonts/proximanova_regular_normal.ttf",
    "ui/loaded/authored/_common/fonts/proximanova_bold_normal.ttf",
    "ui/loaded/authored/_common/fonts/cs/MYingHeiPRC-W4.ttf",
    "ui/loaded/authored/_common/fonts/ct/MElleHK-Medium.ttf",
    "ui/loaded/authored/_common/fonts/jp/SIE-TBGoStdR-Normal.ttf",
    "ui/loaded/authored/_common/fonts/kr/AsiaKDREAM2-R.ttf",
]
CONFIG_PATHS = ["configs/uiconfig/uifontmap.config", "configs\\uiconfig\\uifontmap.config"]

toc = dat1lib.read(open(os.path.join(GAME, "toc"), "rb"))
toc.set_archives_dir(GAME)
archs = toc.get_archives_section()
anames = {i: bytes(a.filename).split(b"\x00")[0].decode("ascii", "replace") for i, a in enumerate(archs.archives)}

NAME_IDS = {1: "Family", 2: "Subfamily", 4: "FullName", 6: "PostScript"}


def parse_ttf(data):
    """Standard sfnt parse (offset 0). Returns (names, codepoints)."""
    off0 = 0
    magic = data[:4]
    if magic not in (b"\x00\x01\x00\x00", b"OTTO", b"true", b"ttcf"):
        # try Insomniac 8-byte prefix variant
        return None, None
    nt = struct.unpack(">H", data[4:6])[0]
    tables = {}
    for k in range(nt):
        rec = data[12 + k*16: 12 + (k+1)*16]
        tables[rec[:4]] = (struct.unpack(">I", rec[8:12])[0], struct.unpack(">I", rec[12:16])[0])
    names = {}
    if b"name" in tables:
        o, l = tables[b"name"]; n = data[o:o+l]
        if len(n) >= 6:
            fmt, count, so = struct.unpack(">HHH", n[:6]); strings = n[so:]
            for i in range(count):
                r = n[6+i*12: 6+(i+1)*12]
                if len(r) < 12: break
                plat, enc, lang, nid, sl, sro = struct.unpack(">HHHHHH", r)
                if sro+sl > len(strings): continue
                s = strings[sro:sro+sl]
                if plat == 3:
                    try: names.setdefault(nid, s.decode("utf-16-be", "replace"))
                    except Exception: pass
    cps = set()
    if b"cmap" in tables:
        o, l = tables[b"cmap"]; c = data[o:o+l]
        if len(c) >= 4:
            _, num = struct.unpack(">HH", c[:4]); best = None
            for k in range(num):
                sh = c[4+k*8: 4+(k+1)*8]
                if len(sh) < 8: break
                plat, enc, so = struct.unpack(">HHI", sh)
                if plat == 3 and enc == 10: best = so; break
                if plat == 0 or (plat == 3 and enc == 1): best = so
            if best is not None:
                sub = c[best:]
                fmt = struct.unpack(">H", sub[:2])[0]
                try:
                    if fmt == 4:
                        seg = struct.unpack(">H", sub[6:8])[0]//2
                        eo = 14; so2 = eo+2*seg+2
                        end = struct.unpack(f">{seg}H", sub[eo:eo+2*seg])
                        start = struct.unpack(f">{seg}H", sub[so2:so2+2*seg])
                        for s, e in zip(start, end):
                            if s == 0xFFFF: continue
                            for cp in range(s, min(e, 0xFFFF)+1): cps.add(cp)
                    elif fmt == 12:
                        ng = struct.unpack(">I", sub[12:16])[0]
                        for g in range(ng):
                            r = sub[16+g*12: 16+(g+1)*12]
                            if len(r) < 12: break
                            sc, ec, _ = struct.unpack(">III", r)
                            if ec-sc > 100000: continue
                            for cp in range(sc, ec+1): cps.add(cp)
                except Exception: pass
    return names, cps


def cov(cps, lo, hi):
    return sum(1 for cp in cps if lo <= cp <= hi), hi-lo+1


print("=== FONT ASSETS ===")
for path in FONT_PATHS:
    aid = crc64.hash(path)
    entries = toc.get_asset_entries_by_assetid(aid, stop_on_first=True)
    if not entries:
        print(f"[-] {path}  (aid=0x{aid:016X}) NOT FOUND")
        continue
    e = entries[0]
    raw = bytes(toc.extract_asset(e))
    print(f"\n[+] {path}")
    print(f"    aid=0x{aid:016X} archive={e.archive}({anames.get(e.archive,'?')}) size={e.size} dsize={len(raw)} head={raw[:8].hex()}")
    # detect wrapper: does an sfnt magic appear at 0 or 8?
    off = None
    for cand in (0, 8):
        if raw[cand:cand+4] in (b"\x00\x01\x00\x00", b"OTTO", b"true"):
            off = cand; break
    if off is None:
        # search first 64 bytes
        for cand in range(64):
            if raw[cand:cand+4] in (b"\x00\x01\x00\x00", b"OTTO", b"true"):
                off = cand; break
    if off is None:
        print("    !! no sfnt magic in first 64 bytes")
        continue
    if off: print(f"    (sfnt magic at +{off} — {off}-byte wrapper header)")
    names, cps = parse_ttf(raw[off:])
    if names is None:
        print("    !! parse failed")
        continue
    fam = names.get(1, "?"); sub = names.get(2, "")
    heb = cov(cps, 0x0590, 0x05FF); ara = cov(cps, 0x0600, 0x06FF)
    lat = cov(cps, 0x0041, 0x007A); cyr = cov(cps, 0x0400, 0x04FF)
    flag = "  <<< HAS HEBREW" if heb[0] > 20 else ""
    print(f"    Family={fam!r} Sub={sub!r} glyphs={len(cps)}")
    print(f"    HEB={heb[0]}/27  ARA={ara[0]}/{ara[1]}  LAT={lat[0]}/{lat[1]}  CYR={cyr[0]}/{cyr[1]}{flag}")
    # list any Hebrew codepoints actually present
    hebcps = sorted(cp for cp in cps if 0x0590 <= cp <= 0x05FF)
    if hebcps:
        print(f"    Hebrew cps present: {[hex(c) for c in hebcps]}")

print("\n=== uifontmap.config ===")
for cp in CONFIG_PATHS:
    aid = crc64.hash(cp)
    entries = toc.get_asset_entries_by_assetid(aid, stop_on_first=True)
    if entries:
        raw = bytes(toc.extract_asset(entries[0]))
        print(f"[+] {cp} size={len(raw)}")
        import re
        for m in re.finditer(rb"[ -~]{3,160}", raw):
            print("   ", m.group().decode("latin-1"))
        break
    else:
        print(f"[-] {cp} not found")
