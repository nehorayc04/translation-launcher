#!/usr/bin/env python3
"""
acs_font_deploy.py -- DECISIVE font test: inject Hebrew into the Arabic-slot UI
FontFile(s) IN-PLACE and answer the crown question of the font phase:

    Does AC Shadows rasterize the UI at runtime from the FontFile TTF
    (so a TTF glyph-merge fixes Hebrew), OR from a pre-baked SDF/raster
    atlas (PhoenixFontDescriptorData / OfflineGlyphs) that never saw Hebrew
    at bake time (so the TTF is irrelevant and the atlas must be cracked)?

The Arabic UI renders in DIN Pro (FontFile idx 9 Bold / 10 Regular, 42/47 Arabic,
0/27 Hebrew). We add the 27 Hebrew letters from the game's OWN Avenir Next World
Demi (FontFile 12, 27/27 Hebrew, same upem 1000 -- no external font, no scaling).

IN-PLACE + CONTIGUOUS (no forge rewrite): the Hebrew makes the sfnt bigger, but
we strip a few cosmetic tables (kern/hdmx/VDMX/LTSH/gasp -- NOT GSUB/GDEF, so
Arabic shaping is preserved) so the re-encoded resource lands UNDER the slot,
then grow it back to the EXACT slot size with incompressible filler bytes placed
AFTER the sfnt (the font parser stops at the sfnt's own table extents and ignores
the tail). Same offset, same size, TOC untouched -> the forge stays byte-for-byte
contiguous. Mermaid codec (acs_cfd, decoder_type 10 -- the game's own).

Backup = just the edited resource blob(s) to a small sidecar (a 20.7 GB forge copy
is neither needed nor wise); --revert writes them back byte-for-byte.

    python acs_font_deploy.py --dry       # offline: build + validate, write nothing
    python acs_font_deploy.py --apply      # write Hebrew DIN into boot.forge in-place
    python acs_font_deploy.py --revert      # restore the pristine resource blob(s)

GAME must be CLOSED.  Expected in-game outcomes (menu, Arabic slot):
  * Hebrew LETTERS in place of the boxes  -> the TTF is the renderer. FONT SOLVED.
  * Arabic still fine + Hebrew still boxes -> font loaded OK; the baked atlas is
    authoritative for glyph coverage. Pivot to cracking PHXFD/GOFF.
  * Arabic ALSO breaks                     -> the fill/strip broke the font (bad
    test); revert and reconsider.
"""
import io
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "anno1800", "work"))

import acs_forge as F          # noqa: E402
import acs_cfd as C            # noqa: E402
from anno_font import _add_hebrew  # noqa: E402
from fontTools.ttLib import TTFont  # noqa: E402

GAME = os.environ.get("ACS_GAME", r"C:\Games\Assassin's Creed Shadows")
BOOT = os.path.join(GAME, "DataPC_boot.forge")
DONOR_FF = 12                  # FontFile idx 12 = Avenir Next World Demi (27/27 Hebrew, upem 1000)
TARGETS = [int(x) for x in os.environ.get("ACS_FONT_IDX", "9,10").split(",")]
STRIP = ("kern", "hdmx", "VDMX", "LTSH", "gasp")   # cosmetic only -- keep GSUB/GDEF (Arabic shaping)
SFNT_MAGICS = (b"\x00\x01\x00\x00", b"OTTO", b"true", b"ttcf")
BAK = os.path.join(HERE, "_fontbak_%d.bin")
POOL = None                    # lazy incompressible filler pool


def _pool():
    global POOL
    if POOL is None:
        POOL = os.urandom(1 << 20)     # 1 MB of incompressible bytes; slice for filler
    return POOL


def _extract_donor(oodle):
    info = F.parse(BOOT)
    r = info["recs"][DONOR_FF]
    with open(BOOT, "rb") as f:
        f.seek(r["offset"]); blob = f.read(r["size"])
    cfds, _ = C.decode_resource(blob, oodle)
    payload = max((d for d, _ in cfds), key=len)
    pos = min(x for x in (payload.find(m) for m in SFNT_MAGICS) if x >= 0)
    return TTFont(io.BytesIO(payload[pos:]))


def _read_resource(idx, oodle):
    info = F.parse(BOOT)
    r = info["recs"][idx]
    with open(BOOT, "rb") as f:
        f.seek(r["offset"]); blob = f.read(r["size"])
    cfds, end = C.decode_resource(blob, oodle)
    assert end == r["size"], f"resource {idx}: {len(cfds)} CFDs consumed {end} != slot {r['size']}"
    return r, blob, cfds


def _new_sfnt(payload, donor):
    pos = min(x for x in (payload.find(m) for m in SFNT_MAGICS) if x >= 0)
    t = TTFont(io.BytesIO(payload[pos:]))
    fam = t["name"].getDebugName(1)
    stripped = [x for x in STRIP if x in t]
    for x in stripped:
        del t[x]
    added, skipped = _add_hebrew(t, donor)
    buf = io.BytesIO(); t.save(buf)
    return pos, buf.getvalue(), fam, stripped, added


def _encode(cfds, new_payload, oodle, level):
    """Re-encode the resource: head CFDs verbatim, last CFD = new_payload."""
    parts = list(cfds)
    parts[-1] = (new_payload, cfds[-1][1])
    return b"".join(C.build_cfd(d, ci, oodle, level=level) for d, ci in parts)


def _build_exact(cfds, base_payload, slot, oodle):
    """Grow base_payload with incompressible filler (after the sfnt) so the
    re-encoded resource is EXACTLY `slot` bytes. Returns (blob, level, k)."""
    pool = _pool()
    for lv in (9, 8, 7):
        blob0 = _encode(cfds, base_payload, oodle, lv)
        if len(blob0) > slot:
            continue                                   # even bare doesn't fit at this level
        for base_seed in range(0, len(pool) - (slot << 1), 65537):
            k = slot - len(blob0)
            for _ in range(8):                          # Newton toward the target
                pay = base_payload + pool[base_seed:base_seed + k]
                blob = _encode(cfds, pay, oodle, lv)
                gap = slot - len(blob)
                if gap == 0:
                    return blob, lv, k
                if abs(gap) <= 32:
                    break
                k = max(0, k + gap)
            lo, hi = max(0, k - 40), k + 40             # dense window scan around the neighbourhood
            for kk in range(lo, hi):
                pay = base_payload + pool[base_seed:base_seed + kk]
                blob = _encode(cfds, pay, oodle, lv)
                if len(blob) == slot:
                    return blob, lv, kk
            # target fell in a size-gap for this seed -> reseed (reshuffles the jumps)
    return None, None, None


def _validate(blob, oodle):
    """Decode the built resource and confirm it yields a valid font with Hebrew."""
    cfds, end = C.decode_resource(blob, oodle)
    assert end == len(blob), f"decode consumed {end} != {len(blob)}"
    payload = max((d for d, _ in cfds), key=len)
    pos = min(x for x in (payload.find(m) for m in SFNT_MAGICS) if x >= 0)
    t = TTFont(io.BytesIO(payload[pos:]), lazy=True)
    cm = set(t.getBestCmap().keys())
    heb = sum(1 for c in range(0x05D0, 0x05EB) if c in cm)
    ara = sum(1 for c in range(0x0621, 0x0650) if c in cm)
    return heb, ara


def build_all(oodle):
    donor = _extract_donor(oodle)
    out = []
    for idx in TARGETS:
        r, blob, cfds = _read_resource(idx, oodle)
        payload = cfds[-1][0]
        pos, new_sfnt, fam, stripped, added = _new_sfnt(payload, donor)
        base_payload = payload[:pos] + new_sfnt
        newblob, lv, k = _build_exact(cfds, base_payload, r["size"], oodle)
        if newblob is None:
            print(f"  idx={idx} {fam}: NO EXACT FILL (font too big even bare) -- needs a forge repack")
            out.append((idx, r, blob, None, fam, stripped, added, None, None))
            continue
        heb, ara = _validate(newblob, oodle)
        # decoder_type of every block in the new payload CFD (must all be 10 = Mermaid)
        dtypes = _block_decoder_types(newblob)
        ok = (len(newblob) == r["size"] and heb == 27 and ara >= 40 and all(t == 10 for t in dtypes))
        print(f"  idx={idx} {fam:16} strip={stripped} +Heb={added} | slot={r['size']:,} "
              f"built={len(newblob):,} lv{lv} filler={k} | Heb={heb}/27 Ara={ara} "
              f"codec={sorted(set(dtypes))} -> {'OK' if ok else 'FAIL'}")
        out.append((idx, r, blob, newblob if ok else None, fam, stripped, added, heb, dtypes))
    return out


def _block_decoder_types(blob):
    """Return the Oodle decoder_type (byte1 & 0x7f) of every compressed block."""
    types = []
    off = 0
    n = len(blob)
    while off + 8 <= n and struct.unpack_from("<Q", blob, off)[0] == C.MAGIC:
        cnt = struct.unpack_from("<i", blob, off + 15)[0]
        bi = off + 19
        blocks = [struct.unpack_from("<ii", blob, bi + 8 * i) for i in range(cnt)]
        p = bi + cnt * 8
        for uncomp, comp in blocks:
            p += 4
            if comp != uncomp and comp >= 2:            # skip stored blocks
                types.append(blob[p + 1] & 0x7F)
            p += comp
        off = p
    return types


def apply():
    oodle = C._oodle()
    built = build_all(oodle)
    if any(nb is None for *_, nb, _, _, _, _ in [(b[0], b[1], b[2], b[3], b[4], b[5], b[6]) for b in built]):
        pass
    ready = [b for b in built if b[3] is not None]
    if not ready:
        print("\nnothing ready to write -- aborting."); return 1
    # backup pristine blobs first
    for idx, r, blob, newblob, *_ in ready:
        with open(BAK % idx, "wb") as g:
            g.write(struct.pack("<QQ", r["offset"], r["size"]) + blob)
    with open(BOOT, "r+b") as f:
        for idx, r, blob, newblob, *_ in ready:
            assert len(newblob) == r["size"]
            f.seek(r["offset"]); f.write(newblob)
    print(f"\nWROTE {len(ready)} font resource(s) in-place -> {os.path.basename(BOOT)}")
    print("Backups:", [os.path.basename(BAK % b[0]) for b in ready])
    print("\nLAUNCH the game -> main menu. Report: Hebrew letters (TTF solved) / "
          "boxes-but-Arabic-fine (atlas) / Arabic-broken (revert).")
    return 0


def revert():
    n = 0
    with open(BOOT, "r+b") as f:
        for idx in TARGETS:
            p = BAK % idx
            if not os.path.exists(p):
                continue
            with open(p, "rb") as g:
                off, size = struct.unpack("<QQ", g.read(16))
                blob = g.read()
            assert len(blob) == size
            f.seek(off); f.write(blob)
            n += 1
            print(f"  reverted idx={idx} ({size:,} B @0x{off:x})")
    print(f"reverted {n} resource(s)." if n else "no backups found.")
    return 0


def dry():
    oodle = C._oodle()
    print(f"=== DRY: build + validate Hebrew DIN (idx {TARGETS}), write nothing ===")
    build_all(oodle)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    a = sys.argv[1] if len(sys.argv) > 1 else "--dry"
    sys.exit({"--dry": dry, "--apply": apply, "--revert": revert}.get(a, dry)())
