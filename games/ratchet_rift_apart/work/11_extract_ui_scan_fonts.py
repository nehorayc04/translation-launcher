"""Extract every asset from R&C d/conduit + d/config + d/tex_ui, decompress via
dat1lib, and (a) detect embedded sfnt fonts (magic scan on the DECOMPRESSED bytes,
incl. Insomniac 8-byte-prefix variant) and (b) dump all font-path strings + the
fontmap. Read-only."""
import os, sys, struct, re

GAME = "F:/Game Lab/Ratchet & Clank - Rift Apart"
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib

toc = dat1lib.read(open(os.path.join(GAME, "toc"), "rb"))
toc.set_archives_dir(GAME)
archs = toc.get_archives_section()
anames = {i: bytes(a.filename).split(b"\x00")[0].decode("ascii", "replace") for i, a in enumerate(archs.archives)}
TARGET = {11: "conduit", 16: "config", 110: "tex_ui"}

assets = toc.get_assets_section()
sizes = toc.get_sizes_section()
n = len(assets.ids)
print(f"total assets {n}")

SFNT = (b"\x00\x01\x00\x00", b"OTTO", b"ttcf", b"wOFF", b"wOF2", b"true")
KNOWN = {b"cmap", b"head", b"hhea", b"maxp", b"name", b"post", b"OS/2", b"glyf",
         b"loca", b"CFF ", b"GPOS", b"GSUB", b"hmtx"}


def sfnt_at(buf, j):
    if buf[j:j+4] not in SFNT: return None
    if j + 12 > len(buf): return None
    nt = struct.unpack(">H", buf[j+4:j+6])[0]
    if not (4 <= nt <= 40) or j + 12 + nt*16 > len(buf): return None
    known = 0
    for k in range(nt):
        tag = buf[j+12+k*16: j+16+k*16]
        if not all(0x20 <= b <= 0x7E for b in tag): return None
        if tag in KNOWN: known += 1
    return nt if known >= 4 else None


font_hits = []
strings_seen = set()
scanned = 0
for idx in range(n):
    e = toc.get_asset_entry_by_index(idx)
    if e is None or e.archive not in TARGET:
        continue
    try:
        raw = bytes(toc.extract_asset(e))
    except Exception:
        continue
    scanned += 1
    aid = assets.ids[idx]
    # font strings
    for m in re.finditer(rb"[ -~]{4,120}", raw):
        s = m.group()
        if b".ttf" in s or b".otf" in s or b"font" in s.lower() or b"Frutiger" in s or b"Azbuka" in s or b"woff" in s.lower():
            t = s.decode("latin-1")
            if t not in strings_seen:
                strings_seen.add(t)
    # sfnt magic scan (offset 0, offset 8 = Insomniac prefix, and full scan)
    for probe in (0, 8):
        nt = sfnt_at(raw, probe)
        if nt:
            font_hits.append((TARGET[e.archive], aid, e.size, len(raw), probe, nt, raw[probe:probe+4]))
    # also a broad find of each magic anywhere
    for mg in SFNT:
        pos = raw.find(mg)
        if pos >= 0 and pos not in (0, 8):
            nt = sfnt_at(raw, pos)
            if nt:
                font_hits.append((TARGET[e.archive], aid, e.size, len(raw), pos, nt, mg))

print(f"scanned {scanned} assets in {sorted(TARGET.values())}")
print("\n=== SFNT font hits ===")
if not font_hits:
    print("  (none)")
for arch, aid, csize, dsize, off, nt, mg in font_hits:
    print(f"  d/{arch} asset=0x{aid:016X} csize={csize} dsize={dsize} sfnt@{off} nt={nt} magic={mg!r}")

print(f"\n=== font-related strings ({len(strings_seen)}) ===")
for t in sorted(strings_seen):
    print(f"  {t!r}")
