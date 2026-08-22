#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""analyze_inner_blocks.py — verify /ghost_title.xpps in gapack_misc_g.psarc and map the
Hebrew-record region (xpps 0x87ec92..0x87f352) to an inner-PSARC-stream offset, confirming
the containing block(s) are RAW/STORED (not zlib) so a same-size surgical edit is legal.
"""
import os, sys, importlib.util, struct

HERE = os.path.dirname(os.path.abspath(__file__))
GAME_DIR = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(GAME_DIR))
GAME = os.environ.get("GOT_GAME", r"F:/Games/Ghost of Tsushima DC")
GG = os.path.join(GAME, "cache_pc", "psarc", "gapack_misc_g.psarc")
CACHE = r"C:/Users/NEHORA~1/AppData/Local/Temp/claude/c--Users-Nehoray-Cohen-Projects-Game-translator/a86ff9b5-d140-4c99-b5de-33e68113ffe9/scratchpad"


def _load(name, path):
    s = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m); return m


dsar = _load("dsar", os.path.join(REPO, "games", "tlou2", "tools", "dsar.py"))

HEB_START = 0x87ec92          # ALEF (cp 0x5d0)
HEB_END = 0x87ec92 + 27 * 64  # one past TAV's record

ps = dsar.Psarc2(GG)
print(f"gapack_misc_g: DSAR entries={ps.d.num_entries} innerSize={ps.d.total_size:,} "
      f"inner PSARC files={ps.num_files} block_size=0x{ps.block_size:x} comp={ps.compression}")
ent = next(e for e in ps.files() if e.path == "/ghost_title.xpps")
print(f"/ghost_title.xpps: orig_size={ent.orig_size:,} block_start={ent.block_start} "
      f"inner_offset(entry.offset)=0x{ent.offset:x}")

# verify the extracted bytes match the cached ghost_title.bin
xpps = ps.extract(ent)
cached = open(os.path.join(CACHE, "ghost_title.bin"), "rb").read()
print(f"extract == cached ghost_title.bin : {xpps == cached}  (len {len(xpps):,} vs {len(cached):,})")

# walk the entry blocks, compute inner-stream position of each, classify raw/stored/zlib
bs = ps.block_size
nblocks = (ent.orig_size + bs - 1) // bs
pos = ent.offset           # inner-stream offset of block 0
print(f"\nentry spans {nblocks} inner-PSARC blocks:")


def classify(val, rawlen):
    if val == 0:
        return "RAW", bs
    if val >= rawlen:
        return "STORED", val
    return "ZLIB", val


# find which block(s) the Hebrew region falls in + map offsets
map_ok = True
heb_inner = None
for k in range(nblocks):
    val = ps.block_table[ent.block_start + k]
    rawlen = min(bs, ent.orig_size - k * bs)
    kind, csize = classify(val, rawlen)
    xlo, xhi = k * bs, k * bs + rawlen          # xpps content span of this block
    inner_lo = pos                               # inner-stream span of this block
    # does this block overlap the Hebrew region?
    if xlo < HEB_END and xhi > HEB_START:
        print(f"  block {k}: xpps[0x{xlo:x}..0x{xhi:x}) kind={kind} csize=0x{csize:x} "
              f"inner=0x{inner_lo:x}  <-- COVERS HEBREW REGION")
        if kind == "ZLIB":
            map_ok = False
        # map the whole Hebrew region if it's inside this raw/stored block
        if xlo <= HEB_START and HEB_END <= xhi and kind in ("RAW", "STORED"):
            heb_inner = inner_lo + (HEB_START - xlo)
    pos += csize

print(f"\nHebrew region xpps[0x{HEB_START:x}..0x{HEB_END:x}) -> inner-stream offset "
      f"{('0x%x' % heb_inner) if heb_inner is not None else 'N/A'}  block-raw/stored={map_ok}")

# PROVE the mapping: read the inner stream at heb_inner and compare to xpps[HEB_START:HEB_END]
if heb_inner is not None:
    got = ps.d.read(heb_inner, HEB_END - HEB_START)
    exp = xpps[HEB_START:HEB_END]
    print(f"inner-stream read at 0x{heb_inner:x} == xpps[heb region]: {got == exp}  "
          f"(identity map {'CONFIRMED' if got == exp else 'FAILED'})")
    # also show whether the simple F+xpps_off identity holds (like the gapack_misc_l proof)
    simple = ent.offset + HEB_START
    print(f"simple F+xpps_off = 0x{simple:x}  matches computed = {simple == heb_inner}")
ps.d.f.close()
