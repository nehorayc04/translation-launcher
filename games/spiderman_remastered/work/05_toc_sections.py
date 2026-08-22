"""MSMR toc — DEPLOY GATE probe #1: exact section inventory + record layout.

READ-ONLY on the game folder (opens the toc for reading only).
Dumps every DAT1 section header (tag/offset/size), decodes each toc section with
dat1lib, and verifies the MSMR record layouts + the parallel-index assumption
that an index-redirect deploy depends on.
"""
import os, sys, io, struct, json, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = r"D:\Games\Spider-man Remastered"
ARCH = os.path.join(GAME, "asset_archive")
TOC  = os.path.join(ARCH, "toc")

sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import dat1lib, dat1lib.types.toc
import dat1lib.types.dat1 as _d1

raw = open(TOC, "rb").read()
print(f"[*] toc on disk: {len(raw)} bytes")
magic, logical = struct.unpack("<II", raw[:8])
print(f"[*] header: magic=0x{magic:08X} declared_uncompressed_len={logical}")

dec = zlib.decompressobj(0)
inner = dec.decompress(raw[8:])
print(f"[*] inner DAT1 (decompressed): {len(inner)} bytes  match_declared={len(inner)==logical}")
print(f"[*] inner first 4 bytes: {inner[:4]!r} (expect b'DAT1' as 1TAD LE -> {struct.unpack('<I', inner[:4])[0]:08X})")

open(os.path.join(HERE, "_toc_inner_original.bin"), "wb").write(inner)
print(f"[+] saved pristine inner DAT1 -> _toc_inner_original.bin")

# ---- raw DAT1 header walk (independent of dat1lib) -----------------------
m, unk1, size = struct.unpack("<III", inner[:12])
nsec, nunk = struct.unpack("<HH", inner[12:16])
print(f"\n=== DAT1 header (raw walk) ===")
print(f"  magic=0x{m:08X} unk1=0x{unk1:08X} (0x51B8E006='toc') size={size} sections={nsec} unknowns={nunk}")
hdrs = []
off = 16
for i in range(nsec):
    tag, o, sz = struct.unpack("<III", inner[off:off+12]); off += 12
    hdrs.append((tag, o, sz))
unknowns = inner[off:off+8*nunk]; off += 8*nunk
strings_start = off
first_sec = min(h[1] for h in hdrs)
print(f"  header ends at {off}, first section offset {first_sec}, strings blob = {first_sec-off} bytes")

TAGNAME = {
    0x398ABFF0: "ArchivesSection      (Archive TOC File Metadata)",
    0x506D7B8A: "AssetIdsSection      (Archive TOC Asset IDs)",
    0x65BCF461: "SizesSection         (Archive TOC Asset Metadata)",
    0xDCD720B5: "OffsetsSection       (Archive TOC Asset Dupe Metadata)",
    0xEDE8ADA9: "SpansSection         (Archive TOC Header)",
    0x6D921D7B: "KeyAssetsSection     (Archive TOC Key Asset IDs)",
    0x30444F4D: "Mod0Section          (MOD0 JSON - modding-tool marker)",
}
print(f"\n=== sections (file order) ===")
print("   # tag        offset      size    ends_at  pad_before  name")
prev_end = first_sec
for i, (tag, o, sz) in enumerate(hdrs):
    print(f"  {i:2} {tag:08X}  {o:9}  {sz:9}  {o+sz:9}  {'?':>10}  {TAGNAME.get(tag,'<unknown>')}")
print(f"\n=== sections (offset order, with padding) ===")
cur = first_sec
for tag, o, sz in sorted(hdrs, key=lambda h: h[1]):
    pad = o - cur
    print(f"  {tag:08X} off={o:9} size={sz:9} pad_before={pad}  {TAGNAME.get(tag,'<unknown>')}")
    cur = o + sz
print(f"  [tail] declared size={size}  last section ends at {cur}  trailing={len(inner)-cur}")
print(f"  header order == tag-sorted order? {[h[0] for h in hdrs] == sorted(h[0] for h in hdrs)}")

# ---- dat1lib decode ------------------------------------------------------
print(f"\n=== dat1lib decode ===")
with open(TOC, "rb") as f:
    t = dat1lib.read(f)
print(f"  class={type(t).__name__} version={t.version}")

archs  = t.get_archives_section()
aids   = t.get_assets_section()
sizes  = t.get_sizes_section()
offs   = t.get_offsets_section()
spans  = t.get_spans_section()
keyas  = t.dat1.get_section(0x6D921D7B)
mod0   = t.dat1.get_section(0x30444F4D)

print(f"  archives : {len(archs.archives)}  (version tag {archs.version})")
print(f"  asset_ids: {len(aids.ids)}")
print(f"  sizes    : {len(sizes.entries)}  entry_class={type(sizes.entries[0]).__name__}")
print(f"  offsets  : {len(offs.entries) if offs else None}")
print(f"  spans    : {len(spans.entries) if spans else None}")
print(f"  keyassets: {len(keyas.ids) if keyas else None}")
print(f"  MOD0     : {'PRESENT' if mod0 else 'absent'}")

# section byte sizes vs counts -> proves record width
for tag, o, sz in hdrs:
    nm = TAGNAME.get(tag, "?")
    if tag == 0x398ABFF0: n = len(archs.archives)
    elif tag == 0x506D7B8A: n = len(aids.ids)
    elif tag == 0x65BCF461: n = len(sizes.entries)
    elif tag == 0xDCD720B5: n = len(offs.entries) if offs else 0
    elif tag == 0xEDE8ADA9: n = len(spans.entries) if spans else 0
    elif tag == 0x6D921D7B: n = len(keyas.ids) if keyas else 0
    else: n = 0
    if n:
        print(f"  [width] {tag:08X} {sz} bytes / {n} entries = {sz/n:.4f} bytes/entry   {nm.split('(')[0].strip()}")

# ---- MSMR SizeEntry semantics -------------------------------------------
print(f"\n=== SizeEntry {{always1,value,index}} semantics ===")
bad_a1 = sum(1 for e in sizes.entries if e.always1 != 1)
bad_ix = sum(1 for j, e in enumerate(sizes.entries) if e.index != j)
print(f"  entries with always1 != 1 : {bad_a1}")
print(f"  entries with index  != pos: {bad_ix}   -> {'PARALLEL (index==pos)' if bad_ix==0 else 'DEDUP POINTER (index is an offsets-table index)'}")
print(f"  first 5: " + " | ".join(f"a1={e.always1} val={e.value} idx={e.index}" for e in sizes.entries[:5]))
mx = max(e.index for e in sizes.entries)
print(f"  max size.index = {mx}   len(offsets) = {len(offs.entries) if offs else '?'}")

print(f"\n=== OffsetEntry {{archive_index,offset}} ===")
print(f"  first 5: " + " | ".join(f"arch={e.archive_index} off={e.offset}" for e in offs.entries[:5]))
from collections import Counter
c = Counter(e.archive_index for e in offs.entries)
print(f"  archive_index histogram (top 10): {c.most_common(10)}")
print(f"  max archive_index referenced = {max(c)}  (archives count = {len(archs.archives)})")

print(f"\n=== ArchiveFileEntry ({len(archs.archives)}) ===")
for i, a in enumerate(archs.archives):
    nm = bytes(a.filename).split(b"\x00")[0].decode("ascii", "ignore")
    tail = bytes(a.filename)[len(nm):]
    nz = tail.rstrip(b"\x00")
    print(f"  [{i:3}] bucket={a.install_bucket:<3} chunkmap=0x{a.chunkmap:08X} name={nm!r} name_field_len={len(a.filename)} junk_after_nul={nz!r}")

print(f"\n=== SpansSection ({len(spans.entries)}) first 12 ===")
for i, sp in enumerate(spans.entries[:12]):
    print(f"  span[{i:3}] asset_index={sp.asset_index:<8} count={sp.count}")
nonzero = [(i, sp.asset_index, sp.count) for i, sp in enumerate(spans.entries) if sp.count]
print(f"  non-empty spans: {len(nonzero)} / {len(spans.entries)}")
