#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""build_font_mechproof.py — the DECISIVE cheap test for the +14/+16/+18 contradiction.

Round-2 claim (arabic_font_table.md): (+14,+16,+18) is the per-glyph OUTLINE reference into
  the external FontVerts store; real Arabic letters carry distinct refs, the 27 Hebrew records
  carry a degenerate ref (3 distinct / 27) -> Hebrew tofus.
Attempt-#5 claim (FONT_ATTEMPT5_FINDINGS.md): the 64-byte records are a pure CMAP (Latin A/O/i
  differ only in cp); nothing in the record points at an outline.

MEASURED here (analyze_font_refs.py, real ghost_title.xpps):
  * Latin A..Z : (+14,+16,+18)=(4,39,0xffff) IDENTICAL, geom=0  -> a shared sentinel (attempt#5's evidence).
  * Hebrew 0x5d0..0x5ea : (+14,+16)=(104,1522) fixed, +18 in {11,12,13} = 3 distinct / 27; geom per-glyph.
  * Arabic letters : (+14,+16,+18) per-glyph DISTINCT (e.g. 46/71, 23/31); Arabic 0x62a geom=(364,-152,5.0)
    ~ Hebrew alef geom=(262,-348,5.0), yet Arabic renders and Hebrew tofus -> the DISCRIMINATOR is the ref,
    NOT geom (this already refutes attempt#5's "nonzero geom -> notdef box"). geom alone can't be the shape:
    Hebrew already has rich per-glyph geom and still tofus.

THE PROOF: overwrite ONLY bytes [+14:+20] (=(+14,+16,+18)) of each of the 27 Hebrew records with the
same 6 bytes from 27 DISTINCT real Arabic letter records. cp (+0) + geom + everything else stay
byte-identical; record count + size unchanged. Deploy in-place (engine crashes on a duplicate path ->
an added override is impossible; the gapack_misc_l proof was also in-place). Then look in-game with
Text=Arabic:
  * If the 27 Hebrew codepoints now render as 27 real ARABIC letters (NOT tofu) => (+14,+16,+18) IS the
    outline ref; the record IS editable to change the glyph; the ONLY remaining work is synthesising
    Hebrew outlines into FontVerts + repointing these fields. (round-2 CONFIRMED, attempt#5 refuted.)
  * If still tofu => (+14,+16,+18) is not (alone) the shape source; try --fields full (also copies geom),
    else the outline lives in an external hash-store keyed elsewhere (attempt#5 confirmed).

Usage:
  python build_font_mechproof.py                 # build to scratch + validate offline (no game file touched)
  python build_font_mechproof.py --fields full   # also copy geom (+22..+45) as a fallback disambiguation
Env: GOT_GAME (default F:/Games/Ghost of Tsushima DC). Run with the repo .venv python (needs lz4).
The human deploys (see the printed commands); this script writes ONLY to the scratch dir.
"""
import os, sys, argparse, importlib.util, struct, collections

HERE = os.path.dirname(os.path.abspath(__file__))
GAME_DIR = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(GAME_DIR))
GAME = os.environ.get("GOT_GAME", r"F:/Games/Ghost of Tsushima DC")
GG = os.path.join(GAME, "cache_pc", "psarc", "gapack_misc_g.psarc")
SCRATCH = r"C:/Users/NEHORA~1/AppData/Local/Temp/claude/c--Users-Nehoray-Cohen-Projects-Game-translator/a86ff9b5-d140-4c99-b5de-33e68113ffe9/scratchpad"
OUT = os.path.join(SCRATCH, "gapack_misc_g_mechproof.psarc")

INNER = "/ghost_title.xpps"
GREC = 64
HEB0 = 0x87ec92          # ALEF (cp 0x5d0) record offset within ghost_title.xpps
HEB_CP0 = 0x5d0
NHEB = 27                # 0x5d0..0x5ea inclusive


def _load(name, path):
    s = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m); return m


dsar = _load("dsar", os.path.join(REPO, "games", "tlou2", "tools", "dsar.py"))
got_dsar = _load("got_dsar", os.path.join(HERE, "got_dsar.py"))


def u16(b, p): return struct.unpack_from("<H", b, p)[0]
def f32(b, p): return struct.unpack_from("<f", b, p)[0]


def is_rec(b, p):
    return p + GREC <= len(b) and u16(b, p + 2) == 0 and b[p + 20] == 0xf8 and u16(b, p + 62) == 0xffff


def pick_arabic_sources(x, n):
    """Return n Arabic-letter record offsets with DISTINCT (+14,+16,+18), +18 != 0xffff,
    scanning the Arabic letter codepoint ranges in file order (isolated/basic first)."""
    # collect every record in the font-table region, keyed by offset
    recs = []
    p = 0x866000
    while p < 0x8a0000:
        if is_rec(x, p):
            recs.append(p); p += GREC
        else:
            p += 1
    # Arabic LETTER codepoints (exclude harakat/marks 0x610-0x61a, 0x64b-0x65f, tatweel 0x640)
    def is_arabic_letter(cp):
        return (0x621 <= cp <= 0x63a and cp != 0x640) or (0x641 <= cp <= 0x64a) \
            or (0x671 <= cp <= 0x6d3) or (0x6fa <= cp <= 0x6ff)
    chosen, seen = [], set()
    for off in recs:
        cp = u16(x, off)
        if not is_arabic_letter(cp):
            continue
        v14, v16, v18 = u16(x, off + 14), u16(x, off + 16), u16(x, off + 18)
        if v18 == 0xffff:                 # skip the sentinel/no-index records
            continue
        ref = (v14, v16, v18)
        if ref in seen:                   # need DISTINCT refs -> distinct shapes
            continue
        seen.add(ref); chosen.append((off, cp, ref))
        if len(chosen) >= n:
            break
    return chosen


def build(fields):
    # 1. pristine ghost_title.xpps from the REAL archive (read-only)
    ps = dsar.Psarc2(GG)
    ent = next(e for e in ps.files() if e.path == INNER)
    F = ent.offset
    x = ps.extract(ent)
    assert len(x) == ent.orig_size == 10_103_200, len(x)
    print(f"pristine {INNER}: {len(x):,} B  entry.offset(F)=0x{F:x}  block_start={ent.block_start}")

    # 2. verify the 27 Hebrew records (cp ladder 0x5d0..0x5ea, contiguous, valid)
    heb = []
    for i in range(NHEB):
        off = HEB0 + i * GREC
        assert is_rec(x, off), f"Hebrew rec {i} not a valid record @0x{off:x}"
        cp = u16(x, off)
        assert cp == HEB_CP0 + i, f"Hebrew rec {i} cp 0x{cp:x} != 0x{HEB_CP0 + i:x}"
        heb.append(off)
    heb_refs = collections.Counter((u16(x, o + 14), u16(x, o + 16), u16(x, o + 18)) for o in heb)
    print(f"27 Hebrew records @0x{HEB0:x}: cp 0x{HEB_CP0:x}..0x{HEB_CP0+NHEB-1:x}, "
          f"DISTINCT (+14,+16,+18)={len(heb_refs)}/27 -> {dict(heb_refs)}")

    # 3. pick 27 distinct-ref Arabic sources
    src = pick_arabic_sources(x, NHEB)
    assert len(src) == NHEB, f"only found {len(src)} distinct Arabic refs"
    print(f"\n27 Arabic source glyphs (distinct refs):")
    for i, (off, cp, ref) in enumerate(src):
        print(f"  heb[0x{HEB_CP0+i:04x}] <- arab 0x{cp:04x} @0x{off:08x}  (+14,+16,+18)={ref}")

    # 4. build the edited xpps: copy ONLY [+14:+20] (ref) — or [+14:+46] (full) for --fields full
    fld = (14, 46) if fields == "full" else (14, 20)
    xb = bytearray(x)
    per_rec_changed = 0
    for i in range(NHEB):
        hoff, (soff, scp, sref) = heb[i], src[i]
        old = bytes(xb[hoff + fld[0]:hoff + fld[1]])
        new = x[soff + fld[0]:soff + fld[1]]
        xb[hoff + fld[0]:hoff + fld[1]] = new
        if old != new:
            per_rec_changed += 1
        # guard: cp (+0..3) and the +62 sentinel are UNCHANGED
        assert u16(xb, hoff) == HEB_CP0 + i, "cp changed!"
        assert u16(xb, hoff + 62) == 0xffff, "sentinel changed!"
    new_x = bytes(xb)
    assert len(new_x) == len(x), "SAME-SIZE violated"
    # exact byte-diff must be confined to the 27 records' [fld] windows
    diffs = [k for k in range(len(x)) if x[k] != new_x[k]]
    allowed = set()
    for i in range(NHEB):
        for k in range(HEB0 + i * GREC + fld[0], HEB0 + i * GREC + fld[1]):
            allowed.add(k)
    assert all(k in allowed for k in diffs), "edit escaped the record ref windows!"
    print(f"\nedited xpps: fields={fields} window=[+{fld[0]},+{fld[1]}) per-record; "
          f"{len(diffs)} bytes changed across {per_rec_changed} records; length unchanged ({len(new_x):,} B)")

    # readback: each Hebrew record now carries its Arabic source's ref (and cp intact)
    for i in range(NHEB):
        hoff, (soff, scp, sref) = heb[i], src[i]
        got = (u16(new_x, hoff + 14), u16(new_x, hoff + 16), u16(new_x, hoff + 18))
        assert got == sref, f"heb {i} ref {got} != arabic {sref}"
        assert u16(new_x, hoff) == HEB_CP0 + i
    print("readback: all 27 Hebrew records now carry the Arabic (+14,+16,+18); cps intact.")

    # 5. identity-map the edits into the inner PSARC stream (block 135 is RAW -> inner = F + xpps_off)
    inner_probe = ps.d.read(F + HEB0, NHEB * GREC)
    assert inner_probe == x[HEB0:HEB0 + NHEB * GREC], "identity map FAILED (region not raw?)"
    edits = []                     # coalesce contiguous diffs into runs
    i = 0
    while i < len(new_x):
        if new_x[i] != x[i]:
            j = i
            while j < len(new_x) and new_x[j] != x[j]:
                j += 1
            edits.append((F + i, new_x[i:j])); i = j
        else:
            i += 1
    span_lo, span_hi = min(o for o, _ in edits), max(o + len(b) for o, b in edits)
    print(f"identity map CONFIRMED; {len(edits)} inner-edit runs, inner span "
          f"0x{span_lo:x}..0x{span_hi:x} (all in RAW block 135)")
    ps.d.f.close()

    # 6. surgical same-size DSAR patch -> scratch deployable gapack_misc_g
    os.makedirs(SCRATCH, exist_ok=True)
    nchg, sz = got_dsar.patch_inner(GG, OUT, edits)
    print(f"\npatch_inner: re-LZ4'd {nchg} of {ps.d.num_entries} DSAR chunks -> {OUT}  ({sz:,} B)")

    # 7. OFFLINE validation of the scratch archive
    v = dsar.Psarc2(OUT)
    assert v.num_files == ps.num_files, (v.num_files, ps.num_files)
    ve = next(e for e in v.files() if e.path == INNER)
    vx = v.extract(ve)
    assert vx == new_x, "rebuilt ghost_title.xpps != our edited bytes"
    for i in range(NHEB):
        hoff = HEB0 + i * GREC
        got = (u16(vx, hoff + 14), u16(vx, hoff + 16), u16(vx, hoff + 18))
        assert got == src[i][2], f"re-read heb {i} ref mismatch"
        assert u16(vx, hoff) == HEB_CP0 + i
    orig = dsar.Psarc2(GG)
    others = [e for e in v.files() if e.path != INNER][:6]
    for e in others:
        oe = next(o for o in orig.files() if o.path == e.path)
        assert v.extract(e) == orig.extract(oe), f"unexpected change in {e.path}"
    print(f"VALIDATED offline: {v.num_files} inner files; ghost_title.xpps carries the 27 Arabic refs; "
          f"cps intact; {len(others)} other files byte-identical; archive re-reads via dsar.py.")
    v.d.f.close(); orig.d.f.close()

    bak = GG + ".he_backup"
    print("\n--- DEPLOY (human) ---")
    print(f'  copy /Y "{OUT}" "{GG}"   (first back up:  copy /Y "{GG}" "{bak}")')
    print("  then launch -> Settings -> Options -> General -> Text Language = العربية")
    print("  LOOK: do the 27 Hebrew letters (menu Hebrew) now show as ARABIC letters (not tofu)?")
    print("--- REVERT (human) ---")
    print(f'  copy /Y "{bak}" "{GG}"    (or Steam/Epic: Verify Integrity of game files)')
    return OUT, sz, src


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fields", choices=["ref", "full"], default="ref",
                    help="ref = copy (+14,+16,+18) only [task spec, default]; full = also copy geom (+22..+45)")
    a = ap.parse_args()
    build(a.fields)
