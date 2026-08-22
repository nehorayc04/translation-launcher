#!/usr/bin/env python3
"""
acs_stream_probe.py -- BINARY DIAGNOSTIC: which raster stream does the menu draw from?

THE CONTRADICTION this settles
------------------------------
After acs_atlas_inject, Hebrew codepoints resolve to a GLYPH (they were boxes before, so
the codepoint remap at record+32 definitely reaches the live menu weight) -- but the shape
drawn is the repurposed slot's ORIGINAL Arabic presentation form, not the Hebrew raster we
wrote at that record's tex_offset. Verified offline, repeatedly:
  * all 8 Arabic weights hold 27 clean Hebrew rasters at their records' tex_offset
  * no un-injected Arabic weight exists (the other 33 PHXFD are Latin/CJK/Hangul)
  * no font-atlas cache on disk; the DX12 cache is rebuilt on a cold launch

A PHXFD object holds TWO 8-bit raster regions:
    stream A  [~52 KB .. ~2.86 MB]  addressed by the page-1 records  (what we injected)
    TAIL      [~2.86 MB .. EOF]     ~714 KB, addressed by further size-pages in the GAP
                                    (page-2 hdr @38,432: em=1000 scale=1 count=108, and its
                                     record 0 rasters at exactly the TAIL start)
So either the renderer reads stream A (and something subtler defeats our write), or it reads
the TAIL, which we never touched -- which would leave the original shapes on screen.

THE PROBE
---------
Rebuild from the PRISTINE backup, re-apply the Hebrew injection, and additionally FLIP a
small set of the largest Arabic glyphs upside-down inside stream A. Then:

    Arabic in the menu is mangled/upside-down -> stream A IS the atlas the menu samples
    Arabic renders perfectly normal           -> stream A is never read; the TAIL is it

WHY "from pristine" and "only a few glyphs" (both learned the hard way)
----------------------------------------------------------------------
The deployed object already spends ALL of its slack: it encodes to EXACTLY the forge slot
(headroom 0) because acs_atlas_inject's exact-slot fill padded it with ~15 KB of filler. So
ANY further edit overshoots unless we drop that filler and rebuild. And the first attempt --
zeroing all 1028 non-Hebrew rasters -- made the object so compressible that the fill needed
~500 KB of filler; the decoded payload grew half a megabyte past the object's internal size
fields and the game BLACK-SCREENED after the logo. Flipping a few dozen glyphs changes the
size by ~1-4 KB, well inside the ~15 KB of real headroom.

    python acs_stream_probe.py --dry [N]     # build + validate, write nothing
    python acs_stream_probe.py --apply [N]   # deploy the probe (GAME MUST BE CLOSED)
    python acs_stream_probe.py --revert      # restore the pre-probe (injected) state
"""
import glob
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import acs_cfd as C            # noqa: E402
import acs_atlas_inject as AI  # noqa: E402

BAK = os.path.join(HERE, "_probebak_%d.bin")
HEB_LO, HEB_HI = 0x05D0, 0x05EA
DEFAULT_N = 60


def pristine(idx, oodle):
    """Decode the untouched resource blob saved by acs_atlas_inject."""
    with open(AI.BAK % idx, "rb") as g:
        off, size = struct.unpack("<QQ", g.read(16))
        rest = g.read()
    if len(rest) == size:                       # old single-forge backup format
        forge, blob = AI._P2, rest
    else:
        z = rest.index(b"\x00")
        forge, blob = rest[:z].decode(), rest[z + 1:]
    cfds, end = C.decode_resource(blob, oodle)
    assert end == size
    return forge, off, size, blob, cfds, max((x for x, _ in cfds), key=len)


def flip_largest(dec, n):
    """Vertically flip the n largest NON-Hebrew glyph rasters in stream A.

    A flip keeps each glyph's byte multiset, so the size delta is small, but the glyph is
    drawn upside-down -- unmistakable on screen. The largest glyphs are chosen because they
    are the most visible in the menu."""
    _g, _c, _s, recs = AI._records(dec)
    cand = [r for r in recs
            if not (HEB_LO <= r["cp"] <= HEB_HI)
            and r["W"] > 0 and r["H"] > 0 and r["toff"] > 0
            and r["toff"] + r["W"] * r["H"] <= len(dec)]
    cand.sort(key=lambda r: -(r["W"] * r["H"]))
    d = bytearray(dec)
    for r in cand[:n]:
        w, h, t = r["W"], r["H"], r["toff"]
        rows = [bytes(d[t + y * w: t + (y + 1) * w]) for y in range(h)]
        d[t:t + w * h] = b"".join(reversed(rows))
    return bytes(d), min(n, len(cand))


def run(mode, n):
    oodle = C._oodle()
    glyphs = AI.raster_hebrew(px_body=52)
    AI._POOL = os.urandom(4 << 20)
    built = []
    for _forge_cfg, idx in AI.WEIGHTS:
        forge, off, size, blob, cfds, dec = pristine(idx, oodle)
        inj, _slots = AI.inject(dec, glyphs)            # keep the Hebrew
        # Headroom differs per weight, so back off until this one fits its slot. Even a
        # handful of flipped glyphs answers the question; a weight left un-flipped would
        # not (we could not tell "not read" from "not changed").
        chosen = nb = None
        heb = flipped = 0
        for cand in [c for c in (n, n // 2, n // 4, 12, 6, 3) if c >= 1]:
            nd, fl = flip_largest(inj, cand)            # + the visible diagnostic
            assert len(nd) == len(dec)
            b = AI._encode_exact(cfds, nd, size, oodle)
            if b is None or len(b) != size or not AI._decoder_ok(b):
                continue
            c2, _ = C.decode_resource(b, oodle)
            d2 = max((x for x, _ in c2), key=len)
            cps = {x["cp"] for x in AI._records(d2)[3]}
            h = sum(1 for i in range(27) if (0x05D0 + i) in cps)
            if h == 27:
                chosen, nb, heb, flipped = cand, b, h, fl
                break
        print(f"  idx={idx:<6} ({os.path.basename(forge):<28}) slot={size:>10,} "
              f"flipped={flipped:<4} Heb={heb:>2}/27 -> "
              f"{'OK' if nb else 'FAIL'}{'' if chosen in (None, n) else f'  (backed off to {chosen})'}")
        built.append((forge, off, size, blob, nb))

    ready = [b for b in built if b[4] is not None]
    if mode != "--apply":
        print(f"\n--dry: {len(ready)}/{len(built)} weights built (flip n={n}). "
              f"Pass --apply to deploy.")
        return 0 if len(ready) == len(built) else 1
    if len(ready) != len(built):
        print("\nnot all weights built -- aborting (a partial probe proves nothing). "
              "Retry with a smaller N.")
        return 1
    for forge, off, size, blob, nb in ready:
        with open(forge, "r+b") as f:
            f.seek(off)
            f.write(nb)
        print(f"WROTE @0x{off:x} in {os.path.basename(forge)} ({size:,} B)")
    print("\nPROBE DEPLOYED (Hebrew injection intact + the largest Arabic glyphs flipped).\n"
          "Cold-launch -> main menu (Arabic slot) and read the ARABIC words "
          "(متابعة / النظام / لعبة جديدة+):\n"
          "  * upside-down / mangled => stream A IS the atlas the menu draws\n"
          "  * perfectly normal      => stream A is never read; the TAIL is the atlas\n"
          "Undo with:  python acs_stream_probe.py --revert")
    return 0


def revert():
    """Rebuild the plain injected state from the pristine backups (no probe flip)."""
    oodle = C._oodle()
    glyphs = AI.raster_hebrew(px_body=52)
    AI._POOL = os.urandom(4 << 20)
    n = 0
    for _forge_cfg, idx in AI.WEIGHTS:
        forge, off, size, blob, cfds, dec = pristine(idx, oodle)
        inj, _ = AI.inject(dec, glyphs)
        nb = AI._encode_exact(cfds, inj, size, oodle)
        if nb is None or len(nb) != size:
            print(f"  idx={idx}: rebuild FAILED -- restoring pristine blob instead")
            nb = blob
        with open(forge, "r+b") as f:
            f.seek(off)
            f.write(nb)
        print(f"  idx={idx} -> {os.path.basename(forge)} restored (injected, no flip)")
        n += 1
    for p in glob.glob(os.path.join(HERE, "_probebak_*.bin")):
        os.remove(p)
    print(f"reverted {n} weights to the injected state.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    a = sys.argv[1] if len(sys.argv) > 1 else "--dry"
    N = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_N
    sys.exit(revert() if a == "--revert" else run(a, N))
