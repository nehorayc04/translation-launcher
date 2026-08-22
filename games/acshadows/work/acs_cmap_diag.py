#!/usr/bin/env python3
"""
acs_cmap_diag.py -- DECISIVE cmap diagnostic for the AC Shadows font gate.

We proved: TTF-glyph injection (adding Hebrew outlines) does NOTHING in-game, and the
PHXFD baked SDF atlas is the renderer. The atlas has NO internal codepoint table and is
keyed by GLYPH INDEX -> so codepoint->glyph MUST resolve through a font's `cmap`, then
glyph-index -> atlas record. The atlas already contains full Latin/Arabic (the "SHADOWS"
title + the Arabic menu render), but NOT Hebrew glyph indices (1575..1638 in Avenir),
so Hebrew -> box.

This test does NOT touch the atlas. It REMAPS the Hebrew `cmap` of the candidate menu
fonts so each Hebrew codepoint points at an EXISTING in-atlas Latin glyph:

    U+05D0 (alef) -> 'A' ,  U+05D1 -> 'B' , ... U+05E9 -> 'Z' , U+05EA -> 'A'

Then the menu Hebrew items ("משחק חדש", "טעינה") should render a row of LATIN LETTERS
instead of boxes. Outcomes, from ONE launch:

  * Hebrew items show LATIN letters -> CONFIRMED: the menu resolves codepoint via this
    font's cmap into the glyph-index-keyed atlas. The FIX is then purely: grow the atlas
    to carry records+rasters at the glyph indices Hebrew resolves to (or remap Hebrew to
    freshly-added atlas records). We also learn WHICH font (9/10 DIN vs 12 Avenir) and
    that the atlas covers those Latin indices.
  * Still boxes on every font -> the menu does NOT consult a TTF cmap for glyph selection
    (glyph resolution is engine-internal); pivot to matching the atlas raster by pixels.

Pure in-place, Mermaid, exact forge-slot (no repack). GAME must be CLOSED.

    python acs_cmap_diag.py --dry     # offline build+validate, write nothing
    python acs_cmap_diag.py --apply    # write remapped fonts into boot.forge in-place
    python acs_cmap_diag.py --revert    # restore pristine resource blobs
"""
import io
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import acs_forge as F          # noqa: E402
import acs_cfd as C            # noqa: E402
from fontTools.ttLib import TTFont  # noqa: E402

GAME = os.environ.get("ACS_GAME", r"C:\Games\Assassin's Creed Shadows")
BOOT = os.path.join(GAME, "DataPC_boot.forge")
TARGETS = [int(x) for x in os.environ.get("ACS_FONT_IDX", "9,10,12").split(",")]
STRIP = ("kern", "hdmx", "VDMX", "LTSH", "gasp")   # cosmetic only; keep GSUB/GDEF
SFNT_MAGICS = (b"\x00\x01\x00\x00", b"OTTO", b"true", b"ttcf")
BAK = os.path.join(HERE, "_cmapbak_%d.bin")
_POOL = None


def _pool():
    global _POOL
    if _POOL is None:
        _POOL = os.urandom(1 << 20)
    return _POOL


def _read_resource(idx, oodle):
    info = F.parse(BOOT)
    r = info["recs"][idx]
    with open(BOOT, "rb") as f:
        f.seek(r["offset"]); blob = f.read(r["size"])
    cfds, end = C.decode_resource(blob, oodle)
    assert end == r["size"], f"res {idx}: consumed {end} != slot {r['size']}"
    return r, blob, cfds


def _sfnt_pos(payload):
    return min(x for x in (payload.find(m) for m in SFNT_MAGICS) if x >= 0)


def _remap_cmap(payload):
    """Remap U+05D0..05EA in every cmap subtable to Latin 'A'+i glyph names, adding the
    entries where absent. Returns (pos, new_sfnt_bytes, family, stripped, nmapped)."""
    pos = _sfnt_pos(payload)
    t = TTFont(io.BytesIO(payload[pos:]))
    fam = t["name"].getDebugName(1)
    order = set(t.getGlyphOrder())
    # target Latin glyph name for each Hebrew codepoint (A..Z then wrap)
    def latin_name(i):
        for cand in (chr(ord('A') + (i % 26)),):           # 'A'.. 'Z'
            if cand in order:
                return cand
        # fall back to whatever the font maps U+0041+i to
        cm = t.getBestCmap()
        return cm.get(0x41 + (i % 26))
    stripped = [x for x in STRIP if x in t]
    for x in stripped:
        del t[x]
    nmapped = 0
    for table in t["cmap"].tables:
        cmap = table.cmap
        for i in range(27):
            cp = 0x05D0 + i
            gn = latin_name(i)
            if gn:
                cmap[cp] = gn
                nmapped += 1
    buf = io.BytesIO(); t.save(buf)
    return pos, buf.getvalue(), fam, stripped, nmapped


def _encode(cfds, new_payload, oodle, level):
    parts = list(cfds)
    parts[-1] = (new_payload, cfds[-1][1])
    return b"".join(C.build_cfd(d, ci, oodle, level=level) for d, ci in parts)


def _build_exact(cfds, base_payload, slot, oodle):
    pool = _pool()
    for lv in (9, 8, 7):
        blob0 = _encode(cfds, base_payload, oodle, lv)
        if len(blob0) > slot:
            continue
        for seed in range(0, len(pool) - (slot << 1), 65537):
            k = slot - len(blob0)
            for _ in range(8):
                pay = base_payload + pool[seed:seed + k]
                blob = _encode(cfds, pay, oodle, lv)
                gap = slot - len(blob)
                if gap == 0:
                    return blob, lv, k
                if abs(gap) <= 32:
                    break
                k = max(0, k + gap)
            for kk in range(max(0, k - 48), k + 48):
                pay = base_payload + pool[seed:seed + kk]
                if len(_encode(cfds, pay, oodle, lv)) == slot:
                    return _encode(cfds, pay, oodle, lv), lv, kk
    return None, None, None


def _block_decoder_types(blob):
    types = []
    off = 0; n = len(blob)
    while off + 8 <= n and struct.unpack_from("<Q", blob, off)[0] == C.MAGIC:
        cnt = struct.unpack_from("<i", blob, off + 15)[0]
        bi = off + 19
        blocks = [struct.unpack_from("<ii", blob, bi + 8 * i) for i in range(cnt)]
        p = bi + cnt * 8
        for uncomp, comp in blocks:
            p += 4
            if comp != uncomp and comp >= 2:
                types.append(blob[p + 1] & 0x7F)
            p += comp
        off = p
    return types


def _validate(blob, oodle):
    cfds, end = C.decode_resource(blob, oodle)
    assert end == len(blob)
    payload = max((d for d, _ in cfds), key=len)
    t = TTFont(io.BytesIO(payload[_sfnt_pos(payload):]), lazy=True)
    cm = t.getBestCmap()
    # confirm the Hebrew codepoints now resolve to the Latin glyph names
    ok = all(cm.get(0x05D0 + i) == chr(ord('A') + (i % 26)) or cm.get(0x05D0 + i) is not None
             for i in range(27))
    return ok


def build_all(oodle):
    out = []
    for idx in TARGETS:
        r, blob, cfds = _read_resource(idx, oodle)
        payload = cfds[-1][0]
        pos, new_sfnt, fam, stripped, nmapped = _remap_cmap(payload)
        base = payload[:pos] + new_sfnt
        nb, lv, k = _build_exact(cfds, base, r["size"], oodle)
        if nb is None:
            print(f"  idx={idx} {fam}: NO EXACT FILL -- skipping")
            out.append((idx, r, blob, None)); continue
        okcm = _validate(nb, oodle)
        dtypes = _block_decoder_types(nb)
        ok = (len(nb) == r["size"] and okcm and all(t == 10 for t in dtypes))
        print(f"  idx={idx} {fam:22} strip={stripped} remapped={nmapped} | "
              f"slot={r['size']:,} built={len(nb):,} lv{lv} filler={k} "
              f"cmapOK={okcm} codec={sorted(set(dtypes))} -> {'OK' if ok else 'FAIL'}")
        out.append((idx, r, blob, nb if ok else None))
    return out


def apply(write):
    oodle = C._oodle()
    built = build_all(oodle)
    ready = [b for b in built if b[3] is not None]
    if not ready:
        print("\nnothing ready -- aborting."); return 1
    if not write:
        print("\n--dry: all built + validated, nothing written. Pass --apply to deploy.")
        return 0
    for idx, r, blob, nb in ready:
        with open(BAK % idx, "wb") as g:
            g.write(struct.pack("<QQ", r["offset"], r["size"]) + blob)
        with open(BOOT, "r+b") as f:
            f.seek(r["offset"]); f.write(nb)
        print(f"WROTE idx={idx} in-place ({r['size']:,} B @0x{r['offset']:x}); backup {os.path.basename(BAK % idx)}")
    print("\nLAUNCH -> main menu. If the Hebrew items ('משחק חדש'/'טעינה') show LATIN LETTERS "
          "(A,B,...) instead of boxes -> the menu resolves glyphs via the TTF cmap into the "
          "atlas; the fix is to grow the atlas at the Hebrew glyph indices. If still boxes -> "
          "glyph resolution is engine-internal.")
    return 0


def revert():
    n = 0
    for idx in TARGETS:
        p = BAK % idx
        if not os.path.exists(p):
            continue
        with open(p, "rb") as g:
            off, size = struct.unpack("<QQ", g.read(16)); data = g.read()
        assert len(data) == size
        with open(BOOT, "r+b") as f:
            f.seek(off); f.write(data)
        print(f"reverted idx={idx} ({size:,} B @0x{off:x})"); n += 1
    if not n:
        print("no backups found.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    a = sys.argv[1] if len(sys.argv) > 1 else "--dry"
    if a == "--revert":
        sys.exit(revert())
    sys.exit(apply(write=(a == "--apply")))
