#!/usr/bin/env python3
"""
acs_heb_probe.py -- do the REPURPOSED (Hebrew-coded) records draw from their own slot?

WHAT IS ALREADY PROVEN (in-game, 2026-07-18)
--------------------------------------------
`acs_stream_probe.py` flipped the largest NON-Hebrew glyph rasters in stream A and the
menu drew those Arabic letters UPSIDE-DOWN. So the renderer samples stream A at the very
addresses we edit: the write path is correct.

WHAT IS STILL WRONG
-------------------
The Hebrew codepoints resolve to a glyph (boxes -> shapes) but the shape drawn is the
repurposed slot's ORIGINAL Arabic presentation form, not the Hebrew SDF written at that
record's tex_offset. Either the engine reads our bytes and our raster/metrics are wrong,
or for these records it fetches the raster from somewhere else.

THE PROBE (compressibility-neutral, so it cannot repeat the black screen)
------------------------------------------------------------------------
Do NOT inject Hebrew art at all. Take the same 27 presentation-form slots, change ONLY
their codepoint to Hebrew (metrics, W/H and tex_offset stay exactly vanilla), and then
FLIP those 27 original rasters upside-down in place. The byte multiset is unchanged, so
the object encodes to the same size -- no filler, no boot risk.

    Hebrew rows draw UPSIDE-DOWN Arabic -> the engine reads exactly these slots, so the
                                           mapping is right and our RASTER/METRICS are
                                           the bug (fix the rasterizer)
    Hebrew rows draw NORMAL Arabic      -> the raster for these records comes from
                                           somewhere else (chase that source)

    python acs_heb_probe.py --dry
    python acs_heb_probe.py --apply     # GAME MUST BE CLOSED
    python acs_heb_probe.py --revert    # back to the plain injected state
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import acs_cfd as C            # noqa: E402
import acs_atlas_inject as AI  # noqa: E402
import acs_stream_probe as SP  # noqa: E402


def remap_and_flip(dec, glyphs):
    """Pick the SAME slots acs_atlas_inject would, set their codepoint to Hebrew, keep
    every other field and the raster bytes, then flip each of those rasters vertically."""
    _g, _c, _s, recs = AI._records(dec)
    slots = AI.pick_slots(recs, len(glyphs), glyphs)     # identical slot choice
    d = bytearray(dec)
    n = 0
    for gi in range(len(glyphs)):
        r = slots[gi]
        struct.pack_into("<I", d, r["o"] + AI.CP_OFF, 0x05D0 + gi)   # codepoint -> Hebrew only
        w, h, t = r["W"], r["H"], r["toff"]
        if w <= 0 or h <= 0 or t <= 0 or t + w * h > len(d):
            continue
        rows = [bytes(d[t + y * w: t + (y + 1) * w]) for y in range(h)]
        d[t:t + w * h] = b"".join(reversed(rows))             # same bytes, flipped
        n += 1
    return bytes(d), n


def run(mode):
    oodle = C._oodle()
    glyphs = AI.raster_hebrew(px_body=52)                 # only to reproduce slot choice
    AI._POOL = os.urandom(4 << 20)
    built = []
    for _cfg, idx in AI.WEIGHTS:
        forge, off, size, blob, cfds, dec = SP.pristine(idx, oodle)
        nd, n = remap_and_flip(dec, glyphs)
        assert len(nd) == len(dec)
        nb = AI._encode_exact(cfds, nd, size, oodle)
        ok = nb is not None and len(nb) == size and AI._decoder_ok(nb)
        heb = 0
        if ok:
            c2, _ = C.decode_resource(nb, oodle)
            d2 = max((x for x, _ in c2), key=len)
            cps = {r["cp"] for r in AI._records(d2)[3]}
            heb = sum(1 for i in range(27) if (0x05D0 + i) in cps)
        print(f"  idx={idx:<6} ({os.path.basename(forge):<28}) slot={size:>10,} "
              f"flipped={n:<3} Heb={heb:>2}/27 -> {'OK' if ok and heb == 27 else 'FAIL'}")
        built.append((forge, off, size, nb if (ok and heb == 27) else None))

    ready = [b for b in built if b[3] is not None]
    if mode != "--apply":
        print(f"\n--dry: {len(ready)}/{len(built)} weights built. Pass --apply to deploy.")
        return 0 if len(ready) == len(built) else 1
    if len(ready) != len(built):
        print("\nnot all weights built -- aborting.")
        return 1
    for forge, off, size, nb in ready:
        with open(forge, "r+b") as f:
            f.seek(off)
            f.write(nb)
        print(f"WROTE @0x{off:x} in {os.path.basename(forge)} ({size:,} B)")
    print("\nPROBE DEPLOYED (no Hebrew art -- the old Arabic rasters, flipped, under "
          "Hebrew codepoints).\nCold-launch -> a menu row carrying our Hebrew "
          "('New Game' / 'Load'):\n"
          "  * UPSIDE-DOWN Arabic => the engine reads these very slots; our RASTER/METRICS\n"
          "                          are the bug -> fix the rasterizer\n"
          "  * NORMAL Arabic      => the raster comes from another source -> chase it\n"
          "Undo with:  python acs_heb_probe.py --revert")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    a = sys.argv[1] if len(sys.argv) > 1 else "--dry"
    sys.exit(SP.revert() if a == "--revert" else run(a))
