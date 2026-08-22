"""MSMR — DEPLOY GATE probe #7: final checks before writing the recipe.
  * DRM / integrity posture of Spider-Man.exe (does anything hash the toc?)
  * which SPAN the localization asset lives in (needed for a .stage-style payload)
  * PROVE dat1lib's ArchiveFileEntry.make() is broken (must build the entry by hand)
  * confirm span asset-ids are SORTED (the engine binary-searches -> constraint
    only when ADDING an id, not when rerouting)
READ-ONLY.
"""
import os, re, sys, struct, io
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = r"D:\Games\Spider-man Remastered"
ARCH = os.path.join(GAME, "asset_archive")
EXE  = os.path.join(GAME, "Spider-Man.exe")
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import dat1lib, dat1lib.types.toc, dat1lib.crc64 as crc64
import dat1lib.types.sections.toc.archives as A

print("=== DRM / integrity posture of Spider-Man.exe ===")
data = open(EXE, "rb").read()
for pat in [rb"[Dd]enuvo", rb"VMProtect", rb"\.vmp", rb"BattlEye", rb"EasyAntiCheat",
            rb"SHA256", rb"sha256", rb"integrity", rb"Integrity", rb"tamper", rb"Tamper",
            rb"checksum", rb"Checksum", rb"CRC32", rb"crc64"]:
    print(f"  {pat!r:16} -> {len(re.findall(pat, data))}")
print("  PE sections:")
try:
    pe_off = struct.unpack("<I", data[0x3C:0x40])[0]
    nsec = struct.unpack("<H", data[pe_off+6:pe_off+8])[0]
    opt = struct.unpack("<H", data[pe_off+20:pe_off+22])[0]
    st = pe_off + 24 + opt
    for i in range(nsec):
        e = data[st+i*40: st+(i+1)*40]
        nm = e[:8].rstrip(b"\x00").decode("ascii", "replace")
        vsz, va, rsz, ra = struct.unpack("<IIII", e[8:24])
        ch, = struct.unpack("<I", e[36:40])
        print(f"    {nm:<10} vsize={vsz:>11,} rawsize={rsz:>11,} chars=0x{ch:08X}")
except Exception as ex:
    print("    PE parse failed:", ex)

print("\n=== the localization asset: span membership ===")
with open(os.path.join(ARCH, "toc"), "rb") as f:
    t = dat1lib.read(f)
ids = t.get_assets_section().ids
spans = t.get_spans_section()
LOC = crc64.hash("localization/localization_all.localization")
hits = [i for i, a in enumerate(ids) if a == LOC]
def span_of(idx):
    for si, sp in enumerate(spans.entries):
        if sp.count and sp.asset_index <= idx < sp.asset_index + sp.count:
            return si
    return None
print(f"  asset_id = {LOC:016X}")
for k, i in enumerate(hits):
    print(f"    variant {k:02d}  asset_index={i:<7} span={span_of(i)}")

print("\n=== are asset-ids SORTED within each span? (engine binary-search constraint) ===")
unsorted_spans = []
for si, sp in enumerate(spans.entries):
    if sp.count < 2: continue
    seg = ids[sp.asset_index: sp.asset_index + sp.count]
    if any(seg[j] > seg[j+1] for j in range(len(seg)-1)):
        unsorted_spans.append(si)
print(f"  non-empty spans checked: {sum(1 for s in spans.entries if s.count>1)}")
print(f"  spans whose ids are NOT ascending: {len(unsorted_spans)} {unsorted_spans[:10]}")
print(f"  -> ids ARE sorted per span: {len(unsorted_spans)==0}  "
      f"(so ADDING an id needs a re-sort + size.index fixup; a pure REROUTE does not)")

print("\n=== dat1lib ArchiveFileEntry.make() — is it usable? ===")
try:
    e = A.ArchiveFileEntry.make(0, 10046, "Hebrew\\tm_he_0")
    print("  make() returned OK:", e)
except Exception as ex:
    print(f"  make() RAISED {type(ex).__name__}: {ex}")
    print("  -> MUST construct the entry by hand (deepcopy a template + set filename/bucket/chunkmap)")

print("\n=== hand-built entry round-trips? ===")
arch = t.get_archives_section()
import copy
tmpl = arch.archives[0]
ne = copy.deepcopy(tmpl)
nm = "Hebrew\\tm_he_0".encode("ascii")
ne.filename = bytearray(nm + b"\x00" * (64 - len(nm)))
ne.install_bucket = 0
ne.chunkmap = 10000 + len(arch.archives)     # == ALERT's own new_archive() rule
arch.archives.append(ne)
blob = arch.save()
print(f"  archives section: {len(arch.archives)} entries -> {len(blob)} bytes "
      f"({len(blob)/len(arch.archives):.1f} B/entry, expect 72.0)")
re_read = A.ArchivesSection(blob, t.dat1)
last = re_read.archives[-1]
print(f"  re-read last entry: name={bytes(last.filename).split(b'@'[0:0] or b'\\x00')[0]!r} "
      f"bucket={last.install_bucket} chunkmap={last.chunkmap}")
print(f"  [{'PASS' if len(blob)%72==0 and last.chunkmap==10046 and last.install_bucket==0 else 'FAIL'}] "
      f"hand-built ArchiveFileEntry serializes correctly")
