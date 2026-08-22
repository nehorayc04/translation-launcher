#!/usr/bin/env python3
"""
acs_goff.py -- decode + rebuild an AC Shadows `OfflineGlyphs` (GOFF) baked glyph atlas.

Cracked from DataPC_boot.forge (idx 13-18; idx 18 = the ARABIC set). The resource,
once its CFD is Mermaid-decoded (acs_cfd), is:

    wrapper[g]                       # Anvil object header (opaque -- preserved verbatim)
    "GOFF"                           # magic at position g
    f32 sdf0, f32 sdf1               # SDF params (0.875, 0.35)
    u32 count                        # glyph count
    count x { u32 codepoint, u32 offset }   # cmap; `offset` is relative to the GOFF magic (g)
    <glyph blocks>                   # each block = per-glyph metrics header (floats:
                                     #   advance, bearingX, bearingY, height, ...) + 8-bit
                                     #   single-channel coverage pixels. block i =
                                     #   dec[g+off[i] : g+off[i+1]]  (last runs to end).

There is NO separate metrics table -- the metrics live in each glyph's own block header.
Codepoint-indexed => Hebrew is ADDABLE (append a cmap entry + a glyph block).

    python acs_goff.py show <forge> <idx>       # dump header + cmap stats + round-trip
"""
import os
import struct
import sys


def parse(dec):
    """Parse a Mermaid-decoded GOFF object -> dict. `blocks[i]` is glyph i's full block
    (metrics header + coverage pixels); `cmap[i]=[codepoint, offset_from_g]`."""
    g = dec.find(b"GOFF")
    if g < 0:
        raise ValueError("no GOFF magic")
    wrapper = dec[:g]
    p = g + 4
    sdf0, sdf1, count = struct.unpack_from("<ffI", dec, p)
    tbl = p + 12
    cmap = [list(struct.unpack_from("<II", dec, tbl + 8 * i)) for i in range(count)]  # [cp, off_from_g]
    blocks = []
    for i in range(count):
        st = g + cmap[i][1]
        en = (g + cmap[i + 1][1]) if i + 1 < count else len(dec)
        blocks.append(dec[st:en])
    return {"g": g, "wrapper": wrapper, "sdf": (sdf0, sdf1), "count": count,
            "cmap": cmap, "blocks": blocks, "raster_base": g + cmap[0][1]}


def build(gd, tail_filler=b""):
    """Rebuild the GOFF object. cmap offsets (relative to g) are re-derived from the
    block sizes so the index always matches the blocks (order = list order).
    `tail_filler` is appended AFTER the last glyph's block (the engine reads only
    `count` glyphs by offset, so trailing bytes are ignored -- used to hit an exact
    forge-slot size, exactly like the loc deploy's exact_fill)."""
    count = len(gd["cmap"])
    out = bytearray()
    out += gd["wrapper"]
    out += b"GOFF"
    out += struct.pack("<ffI", gd["sdf"][0], gd["sdf"][1], count)
    g = len(gd["wrapper"])
    header_len = 4 + 12 + count * 8            # "GOFF" + sdf/count + cmap
    off = header_len                            # first block sits right after the cmap
    cmap_bytes = bytearray()
    raster = bytearray()
    for i in range(count):
        cmap_bytes += struct.pack("<II", gd["cmap"][i][0], off)
        raster += gd["blocks"][i]
        off += len(gd["blocks"][i])
    raster += tail_filler
    out += cmap_bytes
    out += raster
    # The Anvil object wrapper carries two size fields that MUST track the object size,
    # or the engine reads the wrong length -> black screen (same class as the loc law):
    #   wrapper@4  == decoded_size - 13     wrapper@26 == decoded_size - 30
    # (also update CFD0@10 == decoded_size in the deploy layer.)
    n = len(out)
    struct.pack_into("<I", out, 4, n - 13)
    struct.pack_into("<I", out, 26, n - 30)
    return bytes(out)


def show(forge, idx):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import acs_forge as F
    import acs_cfd as C
    o = C._oodle()
    info = F.parse(forge)
    r = info["recs"][idx]
    with open(forge, "rb") as f:
        f.seek(r["offset"]); blob = f.read(r["size"])
    cfds, _ = C.decode_resource(blob, o)
    dec = max((d for d, _ in cfds), key=len)
    gd = parse(dec)
    # round-trip check
    rebuilt = build(gd)
    ok = rebuilt == dec
    cps = [c for c, _ in gd["cmap"]]
    heb = [c for c in cps if 0x5D0 <= c <= 0x5EA]
    ara = [c for c in cps if 0x600 <= c <= 0x6FF or 0xFB50 <= c <= 0xFEFF]
    bsz = [len(b) for b in gd["blocks"]]
    print(f"GOFF idx={idx}: count={gd['count']} sdf={gd['sdf']} "
          f"arabic={len(ara)} hebrew={len(heb)} raster_base={gd['raster_base']} "
          f"block_sizes {min(bsz)}..{max(bsz)}")
    print(f"round-trip rebuild == decoded: {ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) >= 4 and sys.argv[1] == "show":
        sys.exit(show(sys.argv[2], int(sys.argv[3])))
    print(__doc__)
