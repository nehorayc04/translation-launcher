#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""build_mechproof.py — THE font-mechanism proof for Ghost of Tsushima DC.

Question it answers (the pivotal one): does a cmap glyph record's body
(+14 page, +16 region, +18 index, +22.. geometry, +30 size) DETERMINE the rendered
glyph shape, or is the shape bound to the codepoint externally? This decides whether
the whole (page,region,index)->outline decoding is the right path to Hebrew.

Method (same-size in-place edit of ghost_title.xpps in gapack_misc_g; ghost_title is
stored RAW in the inner PSARC, verified -> identity map inner = F + xpps_off):
  copy the FULL body (bytes +14..+63) of a KNOWN rendering glyph onto chosen Hebrew
  letter records (keep their cp). The Hebrew letters appear in the ALREADY-DEPLOYED
  menu words (gapack_misc_l menu-proof). One screenshot then reads:
    Test A (Arabic ref):  מ ש ח ק  <- Arabic-alef(0x627) body -> "משחק חדש"(New Game)
                          should show Arabic alef strokes if the record body wins.
    Test B (Latin xref):  ה ג ר    <- Latin-'O'(0x4f) body -> "הגדרות"(Options)
                          should show 'O' rings if a cross-script Latin ref renders.
    Test C (size):        ד        <- keep Hebrew ref, size(+30) 5.0->60.0
                          tests if size alone changes the notdef box.
    Control:              ו ת כ ב י ט ע ן  untouched -> stay tofu boxes.

    python build_mechproof.py            # build + validate OFFLINE (no game file changed)
    python build_mechproof.py --deploy   # + back up gapack_misc_g -> .he_backup, swap in
    python build_mechproof.py --revert   # restore gapack_misc_g from .he_backup
Env: GOT_GAME. Run with the repo .venv python (needs lz4).
"""
import os, sys, argparse, importlib.util, struct, shutil, time

HERE = os.path.dirname(os.path.abspath(__file__))
GAME_DIR = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(GAME_DIR))
GAME = os.environ.get("GOT_GAME", r"F:/Games/Ghost of Tsushima DC")
GG = os.path.join(GAME, "cache_pc", "psarc", "gapack_misc_g.psarc")
BAK = GG + ".he_backup"
INNER = "/ghost_title.xpps"
GHT_CACHE = os.path.join(GAME_DIR, "extract", "ghost_title.xpps")

GREC = 64
HEB_BASE = 0x87ec92     # record for cp 0x5d0 (ALEF); stride 64, ascending
HEB0 = 0x5d0
AR_ALEF = 0x880dd2      # Arabic 0x627 (renders as ا) — page129 reg1680 idx6 size10
LAT_O = 0x867cd2        # Latin 'O' 0x4f (renders) — page4 reg39 size0


def _load(name, path):
    s = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m); return m

dsar = _load("dsar", os.path.join(REPO, "games", "tlou2", "tools", "dsar.py"))
got_dsar = _load("got_dsar", os.path.join(HERE, "got_dsar.py"))


def heb_off(cp):
    return HEB_BASE + (cp - HEB0) * GREC


def build(deploy=False):
    t0 = time.time()
    gt = bytearray(open(GHT_CACHE, "rb").read())
    orig = bytes(gt)
    ar_body = bytes(gt[AR_ALEF + 14: AR_ALEF + GREC])     # 50 bytes
    lo_body = bytes(gt[LAT_O + 14: LAT_O + GREC])

    report = []
    # Test A: Arabic-alef body onto מ ש ח ק
    for name, cp in [("מ", 0x5de), ("ש", 0x5e9), ("ח", 0x5d7), ("ק", 0x5e7)]:
        o = heb_off(cp); gt[o + 14:o + GREC] = ar_body
        report.append(f"  [A arabic ] {name} cp=0x{cp:x} @0x{o:x} <- Arabic-alef body")
    # Test B: Latin-O body onto ה ג ר
    for name, cp in [("ה", 0x5d4), ("ג", 0x5d2), ("ר", 0x5e8)]:
        o = heb_off(cp); gt[o + 14:o + GREC] = lo_body
        report.append(f"  [B latin-O] {name} cp=0x{cp:x} @0x{o:x} <- Latin-O body")
    # Test C: size 5->60 on ד (keep Hebrew ref+geom)
    o = heb_off(0x5d3); struct.pack_into("<f", gt, o + 30, 60.0)
    report.append(f"  [C size   ] ד cp=0x5d3 @0x{o:x} size(+30) 5.0->60.0 (keep Hebrew ref)")

    assert len(gt) == len(orig), "same-size invariant"
    print(f"edited ghost_title.xpps (same size {len(gt):,}B):")
    print("\n".join(report))

    # locate ghost_title in gapack_misc_g + verify identity map over the edited region
    ps = dsar.Psarc2(BAK if os.path.exists(BAK) else GG)
    ent = next(e for e in ps.files() if e.path == INNER)
    F = ent.offset
    lo = min(heb_off(c) for c in (0x5d2, 0x5d3, 0x5d4, 0x5d7, 0x5de, 0x5e7, 0x5e8, 0x5e9))
    hi = max(heb_off(c) for c in (0x5d2, 0x5d3, 0x5d4, 0x5d7, 0x5de, 0x5e7, 0x5e8, 0x5e9)) + GREC
    raw = ps.d.read(F + lo, hi - lo)
    assert raw == orig[lo:hi], "identity map FAILED over edit region (ghost_title not raw here)"
    edits = []
    i = lo
    while i < hi:
        if gt[i] != orig[i]:
            j = i
            while j < hi and gt[j] != orig[j]:
                j += 1
            edits.append((F + i, bytes(gt[i:j])))
            i = j
        else:
            i += 1
    print(f"identity map OK; {len(edits)} differing runs at inner offsets "
          f"0x{edits[0][0]:x}..0x{edits[-1][0]+len(edits[-1][1]):x}")
    ps.d.f.close()

    out = GG + ".tmp"
    nchg, sz = got_dsar.patch_inner(BAK if os.path.exists(BAK) else GG, out, edits)
    print(f"patch_inner: re-LZ4'd {nchg} DSAR chunks; out {sz:,} B ({time.time()-t0:.0f}s)")

    # offline validation: re-read ghost_title from the rebuilt archive == our edited bytes
    v = dsar.Psarc2(out)
    ve = next(e for e in v.files() if e.path == INNER)
    got = v.extract(ve)
    assert got == bytes(gt), "rebuilt ghost_title != edited bytes"
    v.d.f.close()
    print("VALIDATED offline: rebuilt ghost_title.xpps == our edit")

    if deploy:
        if not os.path.exists(BAK):
            print("backing up gapack_misc_g -> .he_backup (1.5 GB)...")
            shutil.copyfile(GG, BAK)
        os.replace(out, GG)
        print(f"\nDEPLOYED (in-place) -> {GG}")
        print("Launch -> menu. Read 'משחק חדש'(New Game) for Arabic alefs (Test A),")
        print("'הגדרות'(Options) for 'O' rings (Test B), ד for a bigger box (Test C).")
    else:
        os.remove(out)
        print("\n(dry run — no game file changed; re-run with --deploy)")


def revert():
    if os.path.exists(BAK):
        os.replace(BAK, GG); print("restored gapack_misc_g from .he_backup")
    else:
        print("no .he_backup to restore")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    if a.revert: revert()
    else: build(deploy=a.deploy)
