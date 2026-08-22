#!/usr/bin/env python3
"""
ud_font.py - Hebrew glyphs for Until Dawn (Bates/Ballistic Moon) UI fonts.

The .ufont assets in Bates/Content/UI/Fonts/{Univers,Cotford}/ are loose,
unwrapped raw TTF/OTF files (repak `get` returns them byte-identical to a
plain font file — no uasset header at all). cmap-verified: 0/27 Hebrew in
every one of them (Latin/Cyrillic/CJK fallback fonts exist, no Hebrew/Arabic).

Two techniques depending on outline format (auto-detected):
  * Univers (TrueType, `glyf` table)  -> MERGE: copy Hebrew glyph outlines
    from a donor font into the existing font (Anno-style), keeping the
    original Latin glyphs/metrics/name untouched.
  * Cotford (CFF/PostScript, `CFF ` table) -> glyf-merge is a no-op on CFF
    fonts -> REPLACE: ship the donor font wholesale, masquerading its
    `name` table as the original (TLOU1-style), so anything that matches
    by family/style name still resolves it.

CLI:
    ud_font.py check  <font.ufont>
    ud_font.py inject <target.ufont> <out.ufont> [hebrew_src.ttf]
"""
import os
import sys

from fontTools.ttLib import TTFont
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.recordingPen import DecomposingRecordingPen

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HEB_LO, HEB_HI = 0x0590, 0x05FF

DEFAULT_SRC_CANDIDATES = [
    os.path.join(os.path.dirname(__file__), "..", "..", "spiderman2", "extracted", "_heebo", "Heebo-Regular.ttf"),
    r"C:\Windows\Fonts\david.ttf",
    r"C:\Windows\Fonts\frank.ttf",
    r"C:\Windows\Fonts\arial.ttf",
]


def _pick_src(explicit):
    for p in ([explicit] if explicit else []) + DEFAULT_SRC_CANDIDATES:
        if p and os.path.isfile(p):
            return os.path.abspath(p)
    raise SystemExit("no Hebrew+Latin source font found (pass one explicitly)")


def _coverage(ft):
    cmap = ft.getBestCmap()
    heb = sum(1 for cp in range(0x05D0, 0x05EB) if cp in cmap)
    lat = sum(1 for cp in range(0x41, 0x5B) if cp in cmap)
    return len(cmap), heb, lat


def _merge_glyf(tgt, src):
    """TrueType (glyf) merge: add Hebrew block into tgt, preserve everything else."""
    scale = tgt["head"].unitsPerEm / src["head"].unitsPerEm
    src_cmap = src.getBestCmap()
    src_gs = src.getGlyphSet()
    src_hmtx = src["hmtx"]
    tgt_glyf = tgt["glyf"]
    tgt_hmtx = tgt["hmtx"]
    tgt_cmaps = [t for t in tgt["cmap"].tables if t.isUnicode()]
    added = skipped = 0
    for cp in range(HEB_LO, HEB_HI + 1):
        gname_src = src_cmap.get(cp)
        if not gname_src:
            continue
        new_name = "heb_%04X" % cp
        if new_name not in tgt_glyf:
            try:
                rec = DecomposingRecordingPen(src_gs)
                src_gs[gname_src].draw(rec)
                pen = TTGlyphPen(glyphSet=None)
                rec.replay(TransformPen(pen, (scale, 0, 0, scale, 0, 0)))
                tgt_glyf[new_name] = pen.glyph()
            except Exception:
                skipped += 1
                continue
            tgt_hmtx[new_name] = (int(round(src_hmtx[gname_src][0] * scale)), 0)
            added += 1
        for t in tgt_cmaps:
            t.cmap[cp] = new_name
    order = tgt.getGlyphOrder()
    for cp in range(HEB_LO, HEB_HI + 1):
        nm = "heb_%04X" % cp
        if nm in tgt_glyf and nm not in order:
            order.append(nm)
    tgt.setGlyphOrder(order)
    for vt in ("vmtx", "vhea", "VORG"):
        if vt in tgt:
            del tgt[vt]
    if "OS/2" in tgt:
        os2 = tgt["OS/2"]
        os2.ulUnicodeRange1 = os2.ulUnicodeRange1 | (1 << 11)
        if getattr(os2, "ulCodePageRange1", None) is not None:
            os2.ulCodePageRange1 = os2.ulCodePageRange1 | (1 << 5)
    return added, skipped


def inject(target_path, out_path, hebrew_src=None):
    src_path = _pick_src(hebrew_src)
    src = TTFont(src_path)
    tgt = TTFont(target_path)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)

    if "glyf" in tgt:
        added, skipped = _merge_glyf(tgt, src)
        tgt.save(out_path)
        mode = "merge(glyf)"
    elif "CFF " in tgt:
        # CFF/PostScript: glyf-copy is a no-op -> replace wholesale, keep the
        # original family/style name so anything matching by name still finds it.
        ref_name = tgt["name"]
        src["name"] = ref_name
        src.save(out_path)
        added, skipped = None, None
        mode = "replace(CFF->donor, name masqueraded)"
    else:
        raise SystemExit(f"{target_path}: no glyf/CFF table, don't know how to inject")

    n, heb, lat = _coverage(TTFont(out_path, lazy=True))
    return mode, added, skipped, src_path, (n, heb, lat)


def cmd_check(path):
    f = TTFont(path, lazy=True)
    n, heb, lat = _coverage(f)
    tables = "glyf" if "glyf" in f else ("CFF" if "CFF " in f else "?")
    print(f"{os.path.basename(path)}: [{tables}] glyphs~{n} Hebrew={heb}/27 Latin={lat}/26")


def main(argv):
    if len(argv) >= 2 and argv[1] == "check":
        cmd_check(argv[2])
        return 0
    if len(argv) >= 4 and argv[1] == "inject":
        src = argv[4] if len(argv) > 4 else None
        mode, added, skipped, used, (n, heb, lat) = inject(argv[2], argv[3], src)
        print(f"[{mode}] from {used}")
        if added is not None:
            print(f"  added {added} glyphs (skipped {skipped})")
        print(f"  -> {argv[3]}  glyphs~{n} Hebrew={heb}/27 Latin={lat}/26")
        return 0
    print("usage: ud_font.py check <font.ufont>\n"
          "       ud_font.py inject <target.ufont> <out.ufont> [hebrew_src.ttf]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
