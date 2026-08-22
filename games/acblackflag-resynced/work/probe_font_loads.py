#!/usr/bin/env python3
"""
DECISIVE PROBE — does our patch_02 PhoenixFont override actually get loaded?

Takes the Hebrew-injected Noto Kufi fonts and ADDITIONALLY overwrites the outline of
every Arabic-reachable glyph (base codepoints + all GSUB-reachable presentation forms
and ligatures) with the Hebrew SHIN outline. Then deploys.

Reading the result in-game (Arabic locale):
  * Arabic text renders as SHIN shapes  -> the font override IS loaded. Hebrew tofu is
    therefore a codepoint/atlas gate, not a font-content problem -> switch to the
    carrier strategy (store Hebrew as Arabic codepoints that already exist in the
    baked atlas, with Hebrew outlines behind them).
  * Arabic text unchanged               -> the override is NOT loaded at all; the
    engine reads its Arabic font from somewhere else. Hunt that source instead.

    python work/probe_font_loads.py --deploy
"""
import io
import os
import struct
import sys
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from inject_hebrew_font import load_resource, rebuild_resource, PAIRS, HEB_RANGE  # noqa: E402

HEFONTS = os.path.join(HERE, "hefonts")
PROBE = os.path.join(HERE, "hefonts_probe")


def arabic_reachable(font):
    """All glyph names reachable from Arabic codepoints, incl. GSUB substitution targets."""
    cmap = font.getBestCmap()
    seed = {gn for cp, gn in cmap.items()
            if 0x0600 <= cp <= 0x06FF or 0xFB50 <= cp <= 0xFDFF or 0xFE70 <= cp <= 0xFEFF}
    reach = set(seed)
    if "GSUB" in font:
        for lk in font["GSUB"].table.LookupList.Lookup:
            for st in lk.SubTable:
                try:
                    if hasattr(st, "mapping"):
                        for a, b in st.mapping.items():
                            if a in reach:
                                reach.update([b] if isinstance(b, str) else b)
                    if hasattr(st, "alternates"):
                        for a, alts in st.alternates.items():
                            if a in reach:
                                reach.update(alts)
                    if hasattr(st, "ligatures"):
                        for a, ligs in st.ligatures.items():
                            if a in reach:
                                for lig in ligs:
                                    reach.add(lig.LigGlyph)
                except Exception:
                    pass
    return reach


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true")
    a = ap.parse_args()
    from fontTools.ttLib import TTFont
    os.makedirs(PROBE, exist_ok=True)

    for _, _, fid, label in PAIRS:
        src = os.path.join(HEFONTS, f"{fid:08x}.bin")
        cfd0, obj, off, ln, tl = load_resource(src)
        font = TTFont(io.BytesIO(obj[off:off + ln]))
        cmap = font.getBestCmap()
        shin = cmap.get(0x05E9)
        if not shin:
            print(f"{label}: no Hebrew shin in cmap — build hefonts first"); return 1
        glyf = font["glyf"]
        targets = arabic_reachable(font)
        n = 0
        for gn in targets:
            if gn in glyf and gn != shin:
                glyf[gn] = glyf[shin]
                n += 1
        buf = io.BytesIO(); font.save(buf); new_sfnt = buf.getvalue(); font.close()
        new_cfd0, new_obj = rebuild_resource(cfd0, obj, off, ln, tl, new_sfnt)
        open(os.path.join(PROBE, f"{fid:08x}.bin"), "wb").write(new_cfd0 + new_obj)
        print(f"{label}: overwrote {n} Arabic glyph outlines with SHIN; obj {len(obj):,} -> {len(new_obj):,} B")

    if a.deploy:
        # rebuild patch_02 sourcing the fonts from the probe dir
        import build_arabic_hebrew_patch as B
        B.HEFONTS = PROBE
        sys.argv = ["build_arabic_hebrew_patch.py", "--deploy"]
        return B.main()
    print("built (dry-run). add --deploy")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
