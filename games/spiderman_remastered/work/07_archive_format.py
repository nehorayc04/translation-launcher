"""MSMR — DEPLOY GATE probe #3: archive container format + in-place-edit feasibility.

READ-ONLY. Reads (never writes) the game archives.
  * magic of every archive on disk (DSAR = block-compressed, else raw)
  * the DSAR block map around the localization asset -> can we do a same-size
    in-place edit (option a) without repacking?
  * install_bucket / chunkmap semantics (what a NEW archive entry must carry)
  * whether any asset is already served from a RAW (non-DSAR) archive
"""
import os, sys, struct, json
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = r"D:\Games\Spider-man Remastered"
ARCH = os.path.join(GAME, "asset_archive")
TOC  = os.path.join(ARCH, "toc")
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import dat1lib, dat1lib.types.toc, dat1lib.crc64 as crc64

with open(TOC, "rb") as f:
    t = dat1lib.read(f)
arch = t.get_archives_section()
ids  = t.get_assets_section().ids
sizes= t.get_sizes_section()
offs = t.get_offsets_section()

print("=== archive files on disk: magic + size ===")
present, missing = [], []
for i, a in enumerate(arch.archives):
    nm = bytes(a.filename).split(b"\x00")[0].decode("ascii", "ignore")
    p = os.path.join(ARCH, nm)
    if not os.path.exists(p):
        missing.append((i, nm)); continue
    sz = os.path.getsize(p)
    with open(p, "rb") as f:
        head = f.read(32)
    m = struct.unpack("<I", head[:4])[0]
    kind = "DSAR" if m == 0x52415344 else f"RAW/0x{m:08X}"
    present.append((i, nm, sz, kind))
    print(f"  [{i:3}] {nm:<14} {sz:>13,}  magic={head[:4]!r} -> {kind}  "
          f"bucket=0x{a.install_bucket:08X} chunkmap=0x{a.chunkmap:08X}")
print(f"\n  present={len(present)} missing={len(missing)}")
for i, nm in missing:
    a = arch.archives[i]
    print(f"    MISSING [{i:3}] {nm:<14} bucket=0x{a.install_bucket:08X} chunkmap=0x{a.chunkmap:08X}")

print("\n=== install_bucket decode (hypothesis: (lang<<24)|2 for voice, 0 for base) ===")
for i, a in enumerate(arch.archives):
    nm = bytes(a.filename).split(b"\x00")[0].decode("ascii", "ignore")
    b = a.install_bucket
    print(f"  [{i:3}] {nm:<14} bucket=0x{b:08X} (hi={b>>24:3} lo={b & 0xFFFFFF:3})  chunkmap={a.chunkmap:>8} (0x{a.chunkmap:X})")

print("\n=== do any assets live in a RAW (non-DSAR) archive today? ===")
kindmap = {i: k for i, nm, sz, k in present}
cnt = Counter()
for i in range(len(offs.entries)):
    cnt[offs.entries[i].archive_index] += 1
for ai in sorted(cnt):
    nm = bytes(arch.archives[ai].filename).split(b"\x00")[0].decode("ascii","ignore")
    print(f"  archive[{ai:2}] {nm:<14} {cnt[ai]:>7} assets  kind={kindmap.get(ai,'<missing on disk>')}")

# ---------------- DSAR block map around the localization asset --------------
LOC = crc64.hash("localization/localization_all.localization")
hits = [i for i, a in enumerate(ids) if a == LOC]
print(f"\n=== DSAR block map around the localization variants ({len(hits)} variants) ===")
seen_arch = set()
for k, idx in enumerate(hits):
    oe, se = offs.entries[idx], sizes.entries[idx]
    print(f"  variant {k:02d}: asset_idx={idx:<7} archive={oe.archive_index} offset={oe.offset:>12,} size={se.value:>10,}")
    seen_arch.add(oe.archive_index)
print(f"  archives involved: {sorted(seen_arch)}")

for ai in sorted(seen_arch):
    nm = bytes(arch.archives[ai].filename).split(b"\x00")[0].decode("ascii","ignore")
    p = os.path.join(ARCH, nm)
    if not os.path.exists(p):
        print(f"\n  [{ai}] {nm} NOT ON DISK"); continue
    with open(p, "rb") as f:
        hdr = f.read(32)
        magic, = struct.unpack("<I", hdr[:4])
        if magic != 0x52415344:
            print(f"\n  [{ai}] {nm} is RAW (no block map)"); continue
        f.seek(12); blocks_header_end = struct.unpack("<I", f.read(4))[0]
        f.seek(0); h32 = f.read(32)
        print(f"\n  [{ai}] {nm}  size={os.path.getsize(p):,}")
        print(f"      DSAR header[0:32] = {h32.hex()}")
        print(f"      fields <IIII IIII> = {struct.unpack('<8I', h32)}")
        print(f"      blocks_header_end = {blocks_header_end}  -> {(blocks_header_end-32)//32} blocks")
        f.seek(32)
        blocks = []
        while f.tell() < blocks_header_end:
            blocks.append(struct.unpack("<IIIIIIII", f.read(32)))
        print(f"      parsed {len(blocks)} blocks; first 3:")
        for b in blocks[:3]:
            print(f"        real_off={b[0]:>12,} comp_off={b[2]:>12,} real_sz={b[4]:>8,} comp_sz={b[5]:>8,} rest={b[1],b[3],b[6],b[7]}")
        # which blocks cover each loc variant in this archive?
        for k, idx in enumerate(hits):
            oe, se = offs.entries[idx], sizes.entries[idx]
            if oe.archive_index != ai: continue
            a0, a1 = oe.offset, oe.offset + se.value
            cov = [(bi,b) for bi,b in enumerate(blocks) if b[0] < a1 and a0 < b[0]+b[4]]
            first, last = cov[0], cov[-1]
            fully = all(b[0] >= a0 and b[0]+b[4] <= a1 for _,b in cov)
            shares_first = first[1][0] < a0
            shares_last  = last[1][0]+last[1][4] > a1
            print(f"      variant idx={idx}: asset[{a0:,}..{a1:,}] spans blocks {first[0]}..{last[0]} "
                  f"({len(cov)} blocks) block_aligned={not (shares_first or shares_last)} "
                  f"(shares_first_block={shares_first} shares_last_block={shares_last})")
            print(f"        first block real_off={first[1][0]:,} real_sz={first[1][4]:,} comp_sz={first[1][5]:,}")
            print(f"        last  block real_off={last[1][0]:,} real_sz={last[1][4]:,} comp_sz={last[1][5]:,}")
