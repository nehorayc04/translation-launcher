"""MSMR — DEPLOY GATE probe #4:
  (1) PROVE the engine's own data already uses a RAW (non-DSAR) archive by
      extracting real assets out of a00s034.us via the raw offset+size path.
      Control: extract from a DSAR archive too (known-positive).
  (2) Scan Spider-Man.exe for the strings that decide the deploy options:
      archive path handling, any loose-file / mod / override support,
      'toc', 'asset_archive', 'MOD0', 'd\\mods', chunk/bucket wording.
READ-ONLY.
"""
import os, sys, re, struct, mmap

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = r"D:\Games\Spider-man Remastered"
ARCH = os.path.join(GAME, "asset_archive")
EXE  = os.path.join(GAME, "Spider-Man.exe")
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import dat1lib, dat1lib.types.toc

with open(os.path.join(ARCH, "toc"), "rb") as f:
    t = dat1lib.read(f)
t.set_archives_dir(ARCH)
arch = t.get_archives_section(); ids = t.get_assets_section().ids
sizes = t.get_sizes_section(); offs = t.get_offsets_section()

print("=== (1a) CONTROL: extract from a DSAR archive (known-positive) ===")
dsar_idx = next(i for i in range(len(offs.entries))
                if offs.entries[i].archive_index == 19 and 200 < sizes.entries[i].value < 100000)
e = t.get_asset_entry_by_index(dsar_idx)
d = bytes(t.extract_asset(e))
print(f"  idx={dsar_idx} archive={e.archive} off={e.offset} size={e.size} got={len(d)} "
      f"head={d[:16].hex()} magic4={d[:4]!r}")
print(f"  [{'OK' if len(d)==e.size else 'FAIL'}] DSAR path returns declared size")

print("\n=== (1b) RAW archive a00s034.us — extract 6 assets by plain offset+size ===")
raw_idxs = [i for i in range(len(offs.entries)) if offs.entries[i].archive_index == 34][:6]
p34 = os.path.join(ARCH, "a00s034.us")
fsz = os.path.getsize(p34)
print(f"  a00s034.us = {fsz:,} bytes; first 16 bytes = ", end="")
with open(p34, "rb") as f:
    print(f.read(16).hex())
ok_all = True
for i in raw_idxs:
    e = t.get_asset_entry_by_index(i)
    with open(p34, "rb") as f:
        f.seek(e.offset); blob = f.read(e.size)
    m4 = blob[:4]
    inrange = e.offset + e.size <= fsz
    print(f"  idx={i:<7} off={e.offset:>12,} size={e.size:>9,} in_file={inrange} "
          f"got={len(blob):>9,} magic={m4!r} u32=0x{struct.unpack('<I', m4)[0]:08X}")
    ok_all &= inrange and len(blob) == e.size
print(f"  [{'OK' if ok_all else 'FAIL'}] every RAW asset lies inside the file at its declared offset+size")
# highest offset+size in that archive vs the file length -> proves it's a flat concat
mx = max(offs.entries[i].offset + sizes.entries[i].value
         for i in range(len(offs.entries)) if offs.entries[i].archive_index == 34)
print(f"  max(offset+size) over all 44,369 raw assets = {mx:,}  file = {fsz:,}  "
      f"-> {'FITS (flat raw concat CONFIRMED)' if mx <= fsz else 'OVERFLOWS'}")

print("\n=== (2) Spider-Man.exe string scan ===")
print(f"  exe size: {os.path.getsize(EXE):,}")
PATTERNS = [
    rb"asset_archive", rb"\btoc\b", rb"MOD0", rb"d\\\\mods", rb"d/mods",
    rb"[Mm]od[Ss]", rb"override", rb"loose", rb"install_bucket", rb"chunk[Mm]ap",
    rb"DSAR", rb"localization", rb"\.localization", rb"Language", rb"arabic",
    rb"ArchiveTOC", rb"Archive TOC", rb"AssetArchive", rb"streaming",
]
with open(EXE, "rb") as f:
    data = f.read()
print(f"  loaded {len(data):,} bytes")

def count_ascii(pat):
    return len(re.findall(pat, data))
def count_utf16(s):
    return len(re.findall(re.escape(s.encode("utf-16-le")), data))

for p in PATTERNS:
    try:
        n = count_ascii(p)
    except re.error as ex:
        n = f"regex-err {ex}"
    print(f"  ascii {p!r:28} -> {n}")

for s in ["asset_archive", "toc", "mods", "MOD0", "localization", "override"]:
    print(f"  utf16 {s!r:16} -> {count_utf16(s)}")

print("\n=== (2b) context around 'asset_archive' / archive-path strings ===")
for m in list(re.finditer(rb"asset_archive", data))[:10]:
    a = max(0, m.start()-90); b = min(len(data), m.end()+90)
    frag = data[a:b]
    printable = re.sub(rb"[^\x20-\x7e]", b".", frag).decode("ascii")
    print(f"  @0x{m.start():08X}: {printable}")

print("\n=== (2c) any 'd\\mods' / mod-folder style strings? ===")
for pat in [rb"[A-Za-z0-9_./\\-]{0,40}mods[A-Za-z0-9_./\\-]{0,40}"]:
    hits = re.findall(pat, data)
    uniq = sorted({h for h in hits if len(h) > 4})[:60]
    print(f"  {len(hits)} raw hits, {len(uniq)} unique (showing up to 60):")
    for u in uniq:
        print("    ", u.decode("ascii", "replace"))

print("\n=== (2d) archive filename format strings (how the engine builds a path) ===")
for pat in [rb"%s%s", rb"g00s%", rb"a00s%", rb"%s\\%s", rb"%s/%s", rb"\.us\b", rb"\.ar\b"]:
    print(f"  {pat!r:16} -> {len(re.findall(pat, data))}")
for m in list(re.finditer(rb"[ -~]{0,30}00s[ -~]{0,30}", data))[:20]:
    print(f"    @0x{m.start():08X}: {m.group().decode('ascii','replace')!r}")
