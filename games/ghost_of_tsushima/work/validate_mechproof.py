#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""validate_mechproof.py — GOLD-STANDARD offline validation of the scratch mechproof archive:
compare ALL 2205 inner files (md5) between the shipping gapack_misc_g and the mechproof; assert
ONLY /ghost_title.xpps differs, and that it differs in EXACTLY the 27 Hebrew records' ref windows.
"""
import os, sys, importlib.util, hashlib, struct

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
GAME = os.environ.get("GOT_GAME", r"F:/Games/Ghost of Tsushima DC")
GG = os.path.join(GAME, "cache_pc", "psarc", "gapack_misc_g.psarc")
SCRATCH = r"C:/Users/NEHORA~1/AppData/Local/Temp/claude/c--Users-Nehoray-Cohen-Projects-Game-translator/a86ff9b5-d140-4c99-b5de-33e68113ffe9/scratchpad"
OUT = os.path.join(SCRATCH, "gapack_misc_g_mechproof.psarc")
INNER = "/ghost_title.xpps"
GREC = 64
HEB0, HEB_CP0, NHEB = 0x87ec92, 0x5d0, 27


def _load(name, path):
    s = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m); return m


dsar = _load("dsar", os.path.join(REPO, "games", "tlou2", "tools", "dsar.py"))
a = dsar.Psarc2(GG)
b = dsar.Psarc2(OUT)
print(f"orig files={a.num_files}  mechproof files={b.num_files}  (match={a.num_files==b.num_files})")
amap = {e.path: e for e in a.files()}
bmap = {e.path: e for e in b.files()}
assert set(amap) == set(bmap), "file set changed!"

differ = []
for i, path in enumerate(sorted(amap)):
    ha = hashlib.md5(a.extract(amap[path])).digest()
    hb = hashlib.md5(b.extract(bmap[path])).digest()
    if ha != hb:
        differ.append(path)
    if i % 400 == 0:
        print(f"  ...{i}/{len(amap)} checked")
print(f"\nfiles that DIFFER: {differ}")
assert differ == [INNER], f"expected only {INNER} to differ, got {differ}"

# confirm the exact byte-diff inside ghost_title.xpps == the 27 records' [+14,+20) windows
xa = a.extract(amap[INNER]); xb = b.extract(bmap[INNER])
assert len(xa) == len(xb) == 10_103_200
diffs = [k for k in range(len(xa)) if xa[k] != xb[k]]
allowed = {k for i in range(NHEB) for k in range(HEB0 + i * GREC + 14, HEB0 + i * GREC + 20)}
assert all(k in allowed for k in diffs), "diff escaped the ref windows!"
recs_touched = sorted({(k - HEB0) // GREC for k in diffs})
cps = [struct.unpack_from("<H", xb, HEB0 + i * GREC)[0] for i in range(NHEB)]
assert cps == list(range(HEB_CP0, HEB_CP0 + NHEB)), "Hebrew cp ladder broken!"
print(f"ghost_title.xpps: {len(diffs)} bytes differ, ALL inside the 27 records' [+14,+20) windows")
print(f"records touched: {len(recs_touched)} (indices {recs_touched[0]}..{recs_touched[-1]}); "
      f"cp ladder 0x{cps[0]:x}..0x{cps[-1]:x} INTACT")
print("\nGOLD VALIDATION PASSED: exactly one inner file changed, exactly as intended; "
      "2204 other files byte-identical; archive re-reads.")
a.d.f.close(); b.d.f.close()
