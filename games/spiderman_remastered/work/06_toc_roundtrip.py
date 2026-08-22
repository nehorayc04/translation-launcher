"""MSMR toc — DEPLOY GATE probe #2: does dat1lib round-trip the toc?

READ-ONLY on the game folder. Every write goes to the scratchpad.
Tests, in order:
  A. no-op parse -> dat1.save()                  (no refresh)      byte-compare inner DAT1
  B. no-op parse -> full_refresh() -> save()      (every section re-serialized)
  C. each recalculation strategy
  D. TOC.save() (the zlib wrapper) -> re-read -> compare inner DAT1
  E. a REAL index-redirect edit (append archive + repoint one asset) -> re-read -> verify
"""
import os, sys, io, struct, zlib, shutil, hashlib, tempfile, copy

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = r"D:\Games\Spider-man Remastered"
TOC  = os.path.join(GAME, "asset_archive", "toc")
SP   = os.path.join(os.environ.get("TMP", tempfile.gettempdir()), "msmr_deploy_probe")
os.makedirs(SP, exist_ok=True)

sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import dat1lib, dat1lib.types.toc, dat1lib.crc64 as crc64
import dat1lib.types.dat1 as _d1

assert os.path.abspath(SP).lower().startswith(os.path.abspath(tempfile.gettempdir()).lower()[:3]), "scratchpad guard"

def sha(b): return hashlib.sha256(b).hexdigest()[:16]

ORIG_INNER = open(os.path.join(HERE, "_toc_inner_original.bin"), "rb").read()
print(f"[*] pristine inner DAT1: {len(ORIG_INNER)} bytes sha={sha(ORIG_INNER)}")

def load(strat):
    with open(TOC, "rb") as f:
        t = dat1lib.read(f)
    t.dat1.set_recalculation_strategy(strat)
    return t

def inner_of(t):
    buf = io.BytesIO(); t.dat1.save(buf); return buf.getvalue()

def diff_report(a, b, label):
    same = a == b
    print(f"  [{'IDENTICAL' if same else 'DIFFERS  '}] {label}: len {len(a)} vs {len(b)}  sha {sha(a)} vs {sha(b)}")
    if not same:
        n = min(len(a), len(b))
        first = next((i for i in range(n) if a[i] != b[i]), n)
        cnt = sum(1 for i in range(n) if a[i] != b[i])
        print(f"      first diff @ {first}, differing bytes: {cnt}/{n} ({100*cnt/n:.4f}%)")
        print(f"      orig[{first}:{first+24}] = {a[first:first+24].hex()}")
        print(f"      new [{first}:{first+24}] = {b[first:first+24].hex()}")
    return same

STRATS = {
    "ORIGINAL_ORDER      ": _d1.RECALCULATE_ORIGINAL_ORDER,
    "PRESERVE_PADDING    ": _d1.RECALCULATE_PRESERVE_PADDING,
    "STRAIGHTFORWARD     ": _d1.RECALCULATE_STRAIGHTFORWARD_ORDER,
}

print("\n=== A. no-op parse -> save (no refresh) ===")
for name, s in STRATS.items():
    t = load(s)
    diff_report(ORIG_INNER, inner_of(t), f"strat={name}")

print("\n=== B. parse -> full_refresh() -> save  (every section re-serialized) ===")
for name, s in STRATS.items():
    t = load(s)
    try:
        t.dat1.full_refresh()
        diff_report(ORIG_INNER, inner_of(t), f"strat={name}")
    except Exception as ex:
        print(f"  [ERROR   ] strat={name}: {type(ex).__name__}: {ex}")

print("\n=== B2. per-section refresh: which sections re-serialize byte-exactly? ===")
t = load(_d1.RECALCULATE_ORIGINAL_ORDER)
TAGNAME = {0x398ABFF0:"Archives",0x506D7B8A:"AssetIds",0x65BCF461:"Sizes",
           0xDCD720B5:"Offsets",0xEDE8ADA9:"Spans",0x6D921D7B:"KeyAssets"}
for tag, nm in TAGNAME.items():
    ndx = t.dat1._sections_map.get(tag)
    if ndx is None:
        print(f"  {tag:08X} {nm:10} ABSENT"); continue
    before = bytes(t.dat1._sections_data[ndx])
    sec = t.dat1.sections[ndx]
    try:
        after = bytes(sec.save())
        ok = before == after
        print(f"  {tag:08X} {nm:10} save() {'byte-identical' if ok else 'DIFFERS'}  ({len(before)} -> {len(after)})")
        if not ok:
            first = next((i for i in range(min(len(before),len(after))) if before[i]!=after[i]), -1)
            print(f"       first diff @ {first}: {before[first:first+16].hex()} vs {after[first:first+16].hex()}")
    except Exception as ex:
        print(f"  {tag:08X} {nm:10} save() RAISED {type(ex).__name__}: {ex}")

print("\n=== C. TOC.save() full wrapper -> write to scratchpad -> re-read ===")
t = load(_d1.RECALCULATE_ORIGINAL_ORDER)
out = os.path.join(SP, "toc_noop")
with open(out, "wb") as f:
    t.save(f)
raw_new = open(out, "rb").read()
raw_old = open(TOC, "rb").read()
print(f"  original file {len(raw_old)} bytes sha={sha(raw_old)}")
print(f"  rewritten     {len(raw_new)} bytes sha={sha(raw_new)}  (zlib level differs -> outer bytes need NOT match)")
m2, l2 = struct.unpack("<II", raw_new[:8])
print(f"  new header: magic=0x{m2:08X} declared_len={l2}")
inner2 = zlib.decompressobj(0).decompress(raw_new[8:])
diff_report(ORIG_INNER, inner2, "inner DAT1 after TOC.save()")
with open(out, "rb") as f:
    t2 = dat1lib.read(f)
print(f"  re-read: archives={len(t2.get_archives_section().archives)} assets={len(t2.get_assets_section().ids)} "
      f"sizes={len(t2.get_sizes_section().entries)} offsets={len(t2.get_offsets_section().entries)} "
      f"spans={len(t2.get_spans_section().entries)}")

print("\n=== D. REAL index-redirect edit on the scratchpad copy ===")
LOC_AID = crc64.hash("localization/localization_all.localization")
t = load(_d1.RECALCULATE_ORIGINAL_ORDER)
ids   = t.get_assets_section().ids
sizes = t.get_sizes_section()
offs  = t.get_offsets_section()
arch  = t.get_archives_section()

hits = [i for i, a in enumerate(ids) if a == LOC_AID]
print(f"  localization asset id {LOC_AID:016X} -> {len(hits)} indices: {hits}")
target = hits[0]
se, oe = sizes.entries[target], offs.entries[target]
print(f"  BEFORE idx={target}: size={se.value} always1={se.always1} index={se.index} "
      f"archive={oe.archive_index} offset={oe.offset}")

# append an archive entry naming a mod file (MSMR: bucket u32, chunkmap u32, name[64])
NEW_NAME = "d\\mods\\tm_he_0"
tmpl = arch.archives[0]
new_entry = copy.deepcopy(tmpl)
raw_nm = NEW_NAME.encode("ascii")
new_entry.filename = bytearray(raw_nm + b"\x00" * (64 - len(raw_nm)))
new_entry.install_bucket = 0
new_entry.chunkmap = 0
new_idx = len(arch.archives)
arch.archives.append(new_entry)

FAKE_SIZE = 1234567
se.value = FAKE_SIZE
oe.archive_index = new_idx
oe.offset = 0

for tag in (arch.TAG, sizes.TAG, offs.TAG):
    t.dat1.refresh_section_data(tag)

out2 = os.path.join(SP, "toc_redirected")
with open(out2, "wb") as f:
    t.save(f)
print(f"  wrote {out2} ({os.path.getsize(out2)} bytes)")

with open(out2, "rb") as f:
    t3 = dat1lib.read(f)
a3, s3, o3 = t3.get_archives_section(), t3.get_sizes_section(), t3.get_offsets_section()
i3 = t3.get_assets_section().ids
print(f"  re-read: archives={len(a3.archives)} (was 46) assets={len(i3)} sizes={len(s3.entries)} offsets={len(o3.entries)}")
nm = bytes(a3.archives[new_idx].filename).split(b"\x00")[0].decode("ascii")
print(f"  archive[{new_idx}] name={nm!r} bucket={a3.archives[new_idx].install_bucket} chunkmap={a3.archives[new_idx].chunkmap}")
se3, oe3 = s3.entries[target], o3.entries[target]
print(f"  AFTER  idx={target}: size={se3.value} always1={se3.always1} index={se3.index} "
      f"archive={oe3.archive_index} offset={oe3.offset}")
ok = (nm == NEW_NAME and se3.value == FAKE_SIZE and oe3.archive_index == new_idx
      and oe3.offset == 0 and se3.index == target and se3.always1 == 1)
print(f"  [{'PASS' if ok else 'FAIL'}] redirect survived a save/re-read round-trip")

# sanity: every OTHER entry unchanged?
t0 = load(_d1.RECALCULATE_ORIGINAL_ORDER)
s0, o0 = t0.get_sizes_section(), t0.get_offsets_section()
bad = 0
for i in range(len(s0.entries)):
    if i == target: continue
    if (s0.entries[i].value != s3.entries[i].value or s0.entries[i].index != s3.entries[i].index
        or o0.entries[i].archive_index != o3.entries[i].archive_index
        or o0.entries[i].offset != o3.entries[i].offset):
        bad += 1
        if bad <= 3: print(f"    [!] entry {i} drifted")
print(f"  other entries drifted: {bad} / {len(s0.entries)-1}   -> {'CLEAN' if bad==0 else 'CORRUPT'}")

# does the redirected toc's inner DAT1 differ ONLY where expected?
inner3 = zlib.decompressobj(0).decompress(open(out2,"rb").read()[8:])
print(f"  inner DAT1 grew {len(ORIG_INNER)} -> {len(inner3)}  (+{len(inner3)-len(ORIG_INNER)} bytes; one 72-byte archive entry + realignment)")
print(f"\n[i] scratchpad artifacts in {SP}")
print(f"[i] GAME FOLDER UNTOUCHED — toc sha now: {sha(open(TOC,'rb').read())}")
