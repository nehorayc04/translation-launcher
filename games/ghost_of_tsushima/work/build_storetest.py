#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""build_storetest.py — DECISIVE empirical test: is the @0x8b0000 store the glyph OUTLINE,
and is the encoding face-independent?

Overwrite the HEBREW notdef store slot (oid=1522, the 13 units all 27 Hebrew letters share
@0x8b2f90) with the ARABIC-alef real outline units (from oid=1680 @0x8b3480), repeated to fill.
Same-size, same-face (record untouched: cp/oid/count stay), so NO OOB / NO crash.

Predicted in-game (menu-proof gapack_misc_l still deployed = Hebrew menu text):
  * If the Hebrew menu letters render as ALEF STROKES (not tofu boxes) -> the store IS the outline,
    the encoding is face-INDEPENDENT, and injecting Hebrew = writing vertex bytes at oid 1522. HUGE.
  * If they stay tofu boxes -> the store is NOT the outline (we've been decoding the wrong region);
    redirect to kind1 curve blobs / kind3.

    python build_storetest.py            # build + validate offline
    python build_storetest.py --deploy   # swap into gapack_misc_g (.he_backup kept)
    python build_storetest.py --revert
Env: GOT_GAME. Repo .venv python (lz4).
"""
import os, sys, argparse, importlib.util, shutil, time

HERE = os.path.dirname(os.path.abspath(__file__))
GAME_DIR = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(GAME_DIR))
GAME = os.environ.get("GOT_GAME", r"F:/Games/Ghost of Tsushima DC")
GG = os.path.join(GAME, "cache_pc", "psarc", "gapack_misc_g.psarc")
BAK = GG + ".he_backup"
INNER = "/ghost_title.xpps"
GHT_CACHE = os.path.join(GAME_DIR, "extract", "ghost_title.xpps")

STORE = 0x8b0000
HEB_OID = 1522      # notdef slot shared by all 27 Hebrew letters
HEB_CNT = 13        # max Hebrew count
AR_OID = 1680       # Arabic alef
AR_CNT = 6


def _load(name, path):
    s = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m); return m

dsar = _load("dsar", os.path.join(REPO, "games", "tlou2", "tools", "dsar.py"))
got_dsar = _load("got_dsar", os.path.join(HERE, "got_dsar.py"))


def build(deploy=False):
    t0 = time.time()
    gt = bytearray(open(GHT_CACHE, "rb").read())
    orig = bytes(gt)
    alef = bytes(gt[STORE + AR_OID * 8: STORE + (AR_OID + AR_CNT) * 8])   # 48 bytes, 6 units
    hebslot = STORE + HEB_OID * 8
    span = HEB_CNT * 8                                                     # 104 bytes
    fill = (alef * ((span // len(alef)) + 1))[:span]                       # repeat alef units to fill 13 units
    gt[hebslot:hebslot + span] = fill
    assert len(gt) == len(orig)
    print(f"overwrote Hebrew notdef store oid={HEB_OID} @0x{hebslot:x} ({span} B) with Arabic-alef units (repeated)")

    ps = dsar.Psarc2(BAK if os.path.exists(BAK) else GG)
    ent = next(e for e in ps.files() if e.path == INNER)
    F = ent.offset
    raw = ps.d.read(F + hebslot, span)
    assert raw == orig[hebslot:hebslot + span], "identity map FAILED"
    edits = [(F + hebslot, bytes(gt[hebslot:hebslot + span]))]
    ps.d.f.close()

    out = GG + ".tmp"
    nchg, sz = got_dsar.patch_inner(BAK if os.path.exists(BAK) else GG, out, edits)
    print(f"patch_inner: {nchg} chunks re-LZ4'd, out {sz:,} B ({time.time()-t0:.0f}s)")
    v = dsar.Psarc2(out)
    assert v.extract(next(e for e in v.files() if e.path == INNER)) == bytes(gt)
    v.d.f.close()
    print("VALIDATED offline")

    if deploy:
        if not os.path.exists(BAK):
            print("backing up gapack_misc_g..."); shutil.copyfile(GG, BAK)
        os.replace(out, GG)
        print(f"DEPLOYED -> {GG}\nLaunch: if Hebrew menu shows ALEF strokes (not boxes) -> store=outline, face-independent.")
    else:
        os.remove(out); print("(dry run)")


def revert():
    if os.path.exists(BAK):
        os.replace(BAK, GG); print("restored gapack_misc_g")
    else:
        print("no backup")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true"); ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    revert() if a.revert else build(deploy=a.deploy)
