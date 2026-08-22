#!/usr/bin/env python3
"""
acs_goff_deploy.py -- edit the AC Shadows Arabic GOFF glyph atlas (boot.forge idx 18)
in-place, Mermaid-encoded, exact forge-slot size (zero pad, forge stays contiguous).

Two modes:

  --diag   DIAGNOSTIC (zero rasterization): remap existing lowercase-Latin glyph
           codepoints -> the Hebrew letters in the menu words, so the menu Hebrew
           renders those (wrong-shaped but VISIBLE) glyphs instead of boxes. If it
           shows glyphs -> GOFF *is* the menu renderer and the whole rebuild+deploy
           path works; then the real Hebrew-raster injection lands. If boxes persist
           -> the 10 MB PhoenixFontDescriptorData atlas is authoritative instead.

  --revert restore the pristine GOFF blob.

Fit-to-slot: the atlas is in the 20.7 GB boot.forge, so we do NOT re-pack -- the edit
keeps the resource EXACTLY its slot size. A codepoint remap barely changes the decoded
size, but Mermaid may compress it a few bytes worse; we DROP a handful of unused spare
glyphs (rare Arabic presentation forms) to get comfortably under slot, then append
incompressible filler after the last block (the engine reads only `count` glyphs by
offset, so the tail is ignored) to land on the slot to the byte.

GAME must be CLOSED.
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import acs_forge as F        # noqa: E402
import acs_cfd as C          # noqa: E402
import acs_goff as G         # noqa: E402

GAME = os.environ.get("ACS_GAME", r"C:\Games\Assassin's Creed Shadows")
BOOT = os.path.join(GAME, "DataPC_boot.forge")
IDX = int(os.environ.get("ACS_GOFF_IDX", "18"))
BAK = os.path.join(HERE, "_goffbak_%d.bin")
POOL = os.urandom(1 << 20)

# The Hebrew letters that appear in the two menu words we prove with:
#   "משחק חדש" (New Game)  +  "טעינה" (Load)  ->  unique: מ ש ח ק ד ט ע י נ ה
DIAG_HEB = "משחקדטעינה"          # 10 distinct Hebrew letters


def _read(oodle):
    info = F.parse(BOOT)
    r = info["recs"][IDX]
    with open(BOOT, "rb") as f:
        f.seek(r["offset"]); blob = f.read(r["size"])
    cfds, end = C.decode_resource(blob, oodle)
    assert end == r["size"]
    dec = max((d for d, _ in cfds), key=len)
    return r, blob, cfds, dec


def _encode(cfds, new_dec, oodle, level):
    """Re-encode the resource. CFD0 is the 20-byte descriptor whose @10 == the object's
    decoded size (the loc law) -- patch it to the NEW object size, or the engine reads
    the wrong length -> black screen."""
    parts = list(cfds)
    c0 = bytearray(cfds[0][0])
    struct.pack_into("<I", c0, 10, len(new_dec))
    parts[0] = (bytes(c0), cfds[0][1])
    parts[-1] = (new_dec, cfds[-1][1])
    return b"".join(C.build_cfd(d, ci, oodle, level=level) for d, ci in parts)


def _fit_to_slot(cfds, gd, slot, oodle):
    """Rebuild gd, then land the re-encoded resource EXACTLY on `slot` bytes."""
    for lv in (9, 8, 7):
        base = _encode(cfds, G.build(gd), oodle, lv)
        if len(base) > slot:
            continue
        for seed in range(0, len(POOL) - (slot << 1), 65537):
            k = slot - len(base)
            for _ in range(8):
                blob = _encode(cfds, G.build(gd, POOL[seed:seed + k]), oodle, lv)
                gap = slot - len(blob)
                if gap == 0:
                    return blob, lv, k
                if abs(gap) <= 32:
                    break
                k = max(0, k + gap)
            for kk in range(max(0, k - 40), k + 40):
                blob = _encode(cfds, G.build(gd, POOL[seed:seed + kk]), oodle, lv)
                if len(blob) == slot:
                    return blob, lv, kk
    return None, None, None


def _build_diag(gd):
    """Remap the first len(DIAG_HEB) lowercase-Latin glyph codepoints -> Hebrew, and
    DROP the SPARE lowercase-Latin glyphs (0x61-0x7A not remapped) to free slot headroom.
    Lowercase Latin cannot appear in the Arabic menu or the uppercase 'SHADOWS' title, so
    dropping it is safe -- unlike Arabic presentation forms, which the shaped menu uses."""
    lc = [i for i, (cp, _) in enumerate(gd["cmap"]) if 0x61 <= cp <= 0x7A]
    remap = []
    for k, ch in enumerate(DIAG_HEB):
        gd["cmap"][lc[k]][0] = ord(ch)
        remap.append((lc[k], ch))
    drop = set(lc[len(DIAG_HEB):])          # every remaining lowercase-Latin glyph
    gd["cmap"] = [c for i, c in enumerate(gd["cmap"]) if i not in drop]
    gd["blocks"] = [b for i, b in enumerate(gd["blocks"]) if i not in drop]
    gd["count"] = len(gd["cmap"])
    return remap, len(drop)


def diag(write):
    oodle = C._oodle()
    r, blob, cfds, dec = _read(oodle)
    gd = G.parse(dec)
    assert G.build(gd) == dec, "GOFF codec round-trip failed on live data"
    remap, ndrop = _build_diag(gd)
    newblob, lv, k = _fit_to_slot(cfds, gd, r["size"], oodle)
    print(f"GOFF idx={IDX} slot={r['size']:,}  remapped {len(remap)} latin->Hebrew "
          f"({' '.join(ch for _, ch in remap)}), dropped {ndrop} spare lowercase-latin, "
          f"count->{gd['count']}")
    if newblob is None:
        print("  NO EXACT FIT -- aborting."); return 1
    # validate: re-decode, re-parse, confirm Hebrew cps present + blocks intact
    cfds2, end2 = C.decode_resource(newblob, oodle)
    assert end2 == len(newblob)
    gd2 = G.parse(max((d for d, _ in cfds2), key=len))
    heb = sorted({c for c, _ in gd2["cmap"] if 0x5D0 <= c <= 0x5EA})
    print(f"  built={len(newblob):,}==slot lv{lv} filler={k}  Hebrew cps now in atlas: "
          f"{[hex(c) for c in heb]}")
    if not write:
        print("  (--diag dry preview; pass --apply to write)"); return 0
    with open(BAK % IDX, "wb") as gbak:
        gbak.write(struct.pack("<QQ", r["offset"], r["size"]) + blob)
    with open(BOOT, "r+b") as f:
        f.seek(r["offset"]); f.write(newblob)
    print(f"\nWROTE GOFF idx={IDX} in-place. Backup: {os.path.basename(BAK % IDX)}")
    print("LAUNCH -> main menu. If 'משחק חדש'/'טעינה' show GLYPHS (any shape, not boxes) "
          "-> GOFF is the renderer, font path proven. If still boxes -> PHXFD is the atlas.")
    return 0


def revert():
    p = BAK % IDX
    if not os.path.exists(p):
        print("no backup found."); return 1
    with open(p, "rb") as g:
        off, size = struct.unpack("<QQ", g.read(16)); data = g.read()
    assert len(data) == size
    with open(BOOT, "r+b") as f:
        f.seek(off); f.write(data)
    print(f"reverted GOFF idx={IDX} ({size:,} B @0x{off:x}).")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    a = sys.argv[1] if len(sys.argv) > 1 else "--diag"
    if a == "--revert":
        sys.exit(revert())
    sys.exit(diag(write=(a == "--apply")))
