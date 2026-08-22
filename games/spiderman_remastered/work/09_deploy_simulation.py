"""MSMR — DEPLOY GATE probe #5: END-TO-END offline deploy simulation.

Builds a fake 'asset_archive' in the scratchpad containing ONLY:
   toc            (a copy of the real one, then patched by us)
   tm_he_0        (our raw mod blob)
…then uses dat1lib's OWN archive reader (the same offset+size+magic logic the
engine uses) to read the redirected asset back and byte-compare it.

Also dumps the exe's command-line switch table + 'loose'/'override' contexts to
look for a dev/loose-file asset-override path (deploy option c).

The real game folder is opened READ-ONLY; every write goes to the scratchpad.
"""
import os, sys, io, re, shutil, struct, hashlib, tempfile, copy, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = r"D:\Games\Spider-man Remastered"
ARCH = os.path.join(GAME, "asset_archive")
TOC  = os.path.join(ARCH, "toc")
EXE  = os.path.join(GAME, "Spider-Man.exe")
SP   = os.path.join(tempfile.gettempdir(), "msmr_deploy_sim")
shutil.rmtree(SP, ignore_errors=True); os.makedirs(SP, exist_ok=True)

sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import dat1lib, dat1lib.types.toc, dat1lib.crc64 as crc64
import dat1lib.types.dat1 as _d1

def sha(b): return hashlib.sha256(b).hexdigest()[:16]

LOC = crc64.hash("localization/localization_all.localization")

# ---------------------------------------------------------------- 1. payload
VAR = os.path.join(ROOT, "games", "spiderman_remastered", "extract",
                   "loc_variants", "variant_00_idx207368.localization")
blob = bytearray(open(VAR, "rb").read())
print(f"[*] source payload: variant_00 ({len(blob):,} bytes) sha={sha(bytes(blob))}")
# make it a DIFFERENT size so we prove size-change works (translation always changes size)
blob += b"\xAB\xCD\xEF\x01" * 777          # grow by 3108 bytes
MARK = b"MSMR-HE-DEPLOY-MARKER"
blob[64:64+len(MARK)] = MARK               # a marker we can find on read-back
blob = bytes(blob)
print(f"[*] modified payload: {len(blob):,} bytes (grown, marker injected) sha={sha(blob)}")

# ---------------------------------------------------------------- 2. patch toc
shutil.copy2(TOC, os.path.join(SP, "toc"))
MODNAME = "tm_he_0"                        # FLAT name in asset_archive/ = shipped convention
open(os.path.join(SP, MODNAME), "wb").write(blob)

with open(os.path.join(SP, "toc"), "rb") as f:
    t = dat1lib.read(f)
t.dat1.set_recalculation_strategy(_d1.RECALCULATE_ORIGINAL_ORDER)
ids   = t.get_assets_section().ids
sizes = t.get_sizes_section()
offs  = t.get_offsets_section()
arch  = t.get_archives_section()

target = next(i for i, a in enumerate(ids) if a == LOC)
before = (sizes.entries[target].value, offs.entries[target].archive_index, offs.entries[target].offset)
print(f"[*] target asset index {target}: BEFORE size={before[0]:,} archive={before[1]} offset={before[2]:,}")

tmpl = arch.archives[0]                    # clone a BASE (bucket 0) entry
ne = copy.deepcopy(tmpl)
raw_nm = MODNAME.encode("ascii")
ne.filename = bytearray(raw_nm + b"\x00" * (64 - len(raw_nm)))
ne.install_bucket = tmpl.install_bucket    # 0 = base game, always installed
ne.chunkmap       = tmpl.chunkmap          # cloned from g00s000
new_ai = len(arch.archives)
arch.archives.append(ne)

sizes.entries[target].value      = len(blob)
offs.entries[target].archive_index = new_ai
offs.entries[target].offset        = 0

for tag in (arch.TAG, sizes.TAG, offs.TAG):
    t.dat1.refresh_section_data(tag)
with open(os.path.join(SP, "toc"), "wb") as f:
    t.save(f)
print(f"[*] patched toc written ({os.path.getsize(os.path.join(SP,'toc')):,} bytes)")

# ---------------------------------------------------------------- 3. read back
print("\n=== READ-BACK through dat1lib's archive reader (== the engine's logic) ===")
with open(os.path.join(SP, "toc"), "rb") as f:
    t2 = dat1lib.read(f)
t2.set_archives_dir(SP)                    # the fake asset_archive
e = t2.get_asset_entry_by_index(target)
nm = bytes(t2.get_archives_section().archives[e.archive].filename).split(b"\x00")[0].decode()
print(f"  entry: archive={e.archive} ('{nm}') offset={e.offset} size={e.size:,}")
got = bytes(t2.extract_asset(e))
print(f"  read {len(got):,} bytes sha={sha(got)}")
print(f"  bytes match payload : {got == blob}")
print(f"  marker at offset 64 : {got[64:64+len(MARK)]!r}")
ok1 = got == blob
print(f"  [{'PASS' if ok1 else 'FAIL'}] redirected asset resolves + reads byte-exact from a RAW mod file")

# every OTHER localization variant must still point at the untouched g00s019
print("\n=== other variants untouched? ===")
others = [i for i, a in enumerate(ids) if a == LOC and i != target]
o2 = t2.get_offsets_section(); s2 = t2.get_sizes_section()
bad = [i for i in others if o2.entries[i].archive_index != 19]
print(f"  {len(others)} other variants; still archive 19: {len(others)-len(bad)}  drifted: {len(bad)}")

# global drift check
with open(TOC, "rb") as f:
    t0 = dat1lib.read(f)
s0, o0 = t0.get_sizes_section(), t0.get_offsets_section()
drift = sum(1 for i in range(len(s0.entries)) if i != target and (
    s0.entries[i].value != s2.entries[i].value or
    o0.entries[i].archive_index != o2.entries[i].archive_index or
    o0.entries[i].offset != o2.entries[i].offset))
print(f"  global drift across 771,669 untouched entries: {drift}  -> {'CLEAN' if drift==0 else 'CORRUPT'}")

# ---------------------------------------------------------------- 4. revert
print("\n=== revert simulation (restore backup + delete mod file) ===")
# TRAP: TOC._get_archive() CACHES an OPEN file handle per archive it read, so the
# mod file is locked until we release them. set_archives_dir() closes them all.
try:
    os.remove(os.path.join(SP, MODNAME))
    print("  [!] unexpected: file was deletable while dat1lib held it")
except PermissionError as ex:
    print(f"  [TRAP CONFIRMED] mod file locked by dat1lib's cached handle: WinError {ex.winerror}")
t2.set_archives_dir(SP)     # closes every cached archive handle
print("  released handles via set_archives_dir()")
bk = os.path.join(SP, "toc.he_backup"); shutil.copy2(TOC, bk)
shutil.copy2(bk, os.path.join(SP, "toc")); os.remove(os.path.join(SP, MODNAME))
same = open(os.path.join(SP, "toc"), "rb").read() == open(TOC, "rb").read()
print(f"  restored toc byte-identical to the real one: {same}")
print(f"  mod file removed: {not os.path.exists(os.path.join(SP, MODNAME))}")

# ---------------------------------------------------------------- 5. exe recon
print("\n=== exe: command-line switch table around 'asset_archive/toc' ===")
data = open(EXE, "rb").read()
m = re.search(rb"asset_archive/toc", data)
a, b = max(0, m.start()-3000), min(len(data), m.end()+600)
frag = data[a:b]
sw = sorted({s.decode("ascii") for s in re.findall(rb"-[a-z][a-z0-9_]{3,30}", frag)})
print(f"  switches near the archive path ({len(sw)}):")
for i in range(0, len(sw), 6):
    print("    " + "  ".join(f"{x:<28}" for x in sw[i:i+6]))

print("\n=== exe: ALL '-switch' style strings mentioning asset/archive/mod/loose/dev ===")
allsw = sorted({s.decode("ascii") for s in re.findall(rb"-[a-z][a-z0-9_]{3,40}", data)})
kw = [s for s in allsw if any(k in s for k in ("asset","archive","mod","loose","dev","path","dir","toc","local","lang","debug"))]
print(f"  {len(allsw)} total switch-like strings; {len(kw)} matching keywords:")
for i in range(0, len(kw), 4):
    print("    " + "  ".join(f"{x:<36}" for x in kw[i:i+4]))

print("\n=== exe: 'loose' + 'DSAR' + 'Archive TOC' contexts ===")
for pat in (rb"loose", rb"DSAR", rb"Archive TOC"):
    for mm in list(re.finditer(pat, data))[:6]:
        a2, b2 = max(0, mm.start()-70), min(len(data), mm.end()+70)
        s = re.sub(rb"[^\x20-\x7e]", b".", data[a2:b2]).decode("ascii")
        print(f"  {pat.decode():12} @0x{mm.start():08X}: {s}")

print(f"\n[i] scratchpad: {SP}")
print(f"[i] REAL GAME UNTOUCHED — toc sha = {sha(open(TOC,'rb').read())}")
