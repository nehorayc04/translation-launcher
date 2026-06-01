"""Extract assets from d/userinterface VIA TOC (decompressing DSAR blocks),
then scan the DECOMPRESSED content for valid OTF/TTF fonts."""
import os, sys, struct
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
TOC  = os.path.join(GAME, "toc")
OUT  = os.path.join(ROOT, "games", "spiderman2", "extracted", "found_fonts_real")
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib

KNOWN = {b"CFF ", b"CFF2", b"head", b"hhea", b"maxp", b"name", b"post",
         b"OS/2", b"cmap", b"glyf", b"loca", b"GPOS", b"GSUB", b"hmtx",
         b"vmtx", b"vhea", b"DSIG", b"BASE", b"GDEF"}

def validate(buf, j, magic):
    if buf[j:j+4] != magic: return None
    nt = struct.unpack(">H", buf[j+4:j+6])[0]
    if not (4 <= nt <= 40): return None
    if j+12 + nt*16 > len(buf): return None
    extents = []
    known = 0
    for k in range(nt):
        rec = buf[j+12 + k*16 : j+12 + (k+1)*16]
        tag = rec[:4]
        if not all(0x20<=b<=0x7E for b in tag): return None
        off = struct.unpack(">I", rec[8:12])[0]
        ln = struct.unpack(">I", rec[12:16])[0]
        extents.append((tag, off, ln))
        if tag in KNOWN: known += 1
    if known < 5: return None
    total = max(o+l for _, o, l in extents)
    if total > len(buf) - j: return None    # font would exceed buffer
    return total

def read_name(buf, j):
    nt = struct.unpack(">H", buf[j+4:j+6])[0]
    for k in range(nt):
        rec = buf[j+12 + k*16 : j+12 + (k+1)*16]
        if rec[:4] == b"name":
            off = struct.unpack(">I", rec[8:12])[0]
            ln  = struct.unpack(">I", rec[12:16])[0]
            n = buf[j+off : j+off+ln]
            if len(n) < 6: return {}
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
            return rows
    return {}

with open(TOC, "rb") as f:
    toc = dat1lib.read(f)
toc.set_archives_dir(GAME)

archs = toc.get_archives_section()
ui_arch = None
for i, a in enumerate(archs.archives):
    name = bytes(a.filename).split(b"\x00")[0].decode("ascii")
    if name.endswith("userinterface"):
        ui_arch = i
        print(f"[+] d/userinterface = archive index {i}")
        break

# Get all asset entries in userinterface
aid_section = toc.get_assets_section()
ui_entries = []
for idx in range(len(aid_section.ids)):
    e = toc.get_asset_entry_by_index(idx)
    if e is not None and e.archive == ui_arch:
        ui_entries.append(e)
ui_entries.sort(key=lambda e: -e.size)
print(f"[+] {len(ui_entries)} entries in userinterface, sorted largest first")
print()

# For each entry, extract + scan
found_fonts = []
for k, e in enumerate(ui_entries):
    if k > 200: break  # cap
    try:
        d = bytes(toc.extract_asset(e))[36:]   # strip AssetEntry prefix
    except Exception as ex:
        continue
    if not d: continue
    if k < 30 or k % 50 == 0:
        head = d[:8]
        head_hex = head.hex()
        print(f"  [{k:3}] idx={e.index:>8} size={len(d):>8}  head={head_hex}")
    # search for valid OTF/TTF
    for magic in (b"OTTO", b"\x00\x01\x00\x00", b"ttcf"):
        i = 0
        while True:
            j = d.find(magic, i)
            if j < 0: break
            total = validate(d, j, magic)
            if total and 20_000 < total < 80_000_000:
                names = {}
                try: names = read_name(d, j) or {}
                except: pass
                family = names.get(1, "?")
                subfamily = names.get(2, "")
                print(f"   ★ FONT in asset idx={e.index} at off={j} size={total} family={family!r} subfamily={subfamily!r}")
                found_fonts.append((e.index, j, total, family, subfamily, d[j:j+total]))
            i = j + 4

print()
print(f"=== {len(found_fonts)} fonts found ===")
for idx, j, total, fam, sub, _ in found_fonts:
    print(f"  asset_idx={idx:<8} off={j:<8} size={total:<8} {fam!r} / {sub!r}")

# Save fonts
for idx, j, total, fam, sub, fontdata in found_fonts:
    safe = (fam + "_" + sub).replace(" ", "_").replace("/", "_")[:50]
    outp = os.path.join(OUT, f"ui_asset{idx}_off{j}_{safe}.bin")
    with open(outp, "wb") as wf: wf.write(fontdata)
    print(f"  saved -> {os.path.basename(outp)}")
