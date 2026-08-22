"""Measure the Hebrew size FC6 actually renders, so FC5 can match it.

FC6 merges Heebo OUTLINES into the game's own TrueType UI fonts (fc6_font._add_hebrew scales
the donor to the target's upem), so a Hebrew letter there occupies its NATURAL Heebo fraction
of the em -- whatever point size the engine picks.  FC5's font is a baked bitmap atlas, so the
equivalent is: render Heebo at the same fraction of FC5's em.

The scale-free invariant that transfers between two different UIs is the ratio
    Hebrew body : Latin cap
so measure it from the real FC6 fonts and re-apply it to FC5's measured Latin cap.

  python -u match_fc6_size.py
"""
import sys, os, io

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "games", "farcry6", "tools"))
sys.path.insert(0, HERE)
from fontTools.ttLib import TTFont
from fc5_font import parse_fnt, FONTS

FC6 = os.environ.get("FC6_GAME", r"F:/Game Lab/Far Cry 6")
HEEBO = os.path.join(REPO, "games", "spiderman2", "extracted", "_heebo", "Heebo-Medium.ttf")


def ink(ft, ch):
    """Glyph ink height in font units, as a fraction of the em."""
    cm = ft.getBestCmap()
    cp = ord(ch)
    if cp not in cm:
        return None
    gs = ft.getGlyphSet()
    from fontTools.pens.boundsPen import BoundsPen
    bp = BoundsPen(gs)
    gs[cm[cp]].draw(bp)
    if not bp.bounds:
        return None
    x0, y0, x1, y1 = bp.bounds
    return (y1 - y0) / ft["head"].unitsPerEm


heebo = TTFont(HEEBO)
H = {c: ink(heebo, c) for c in "מאבגדנסע"}
H_body = sum(v for v in H.values() if v) / len([v for v in H.values() if v])
print(f"Heebo-Medium  hebrew body = {H_body:.4f} em   (per letter: "
      + ", ".join(f"{k}={v:.3f}" for k, v in H.items() if v) + ")")

# --- FC6's own UI fonts
print("\nFC6 UI fonts:")
found = {}
try:
    from fc6_fat import Fat as Fat6
    PC6 = os.path.join(FC6, "data_final", "pc")
    import glob
    for q in sorted(glob.glob(os.path.join(PC6, "**", "*.fat"), recursive=True)):
        try:
            f = Fat6(q)
        except Exception:
            continue
        for e in f.entries:
            if not (8000 <= e.unc <= 6_000_000):
                continue
            try:
                d = f.read_data(e)
            except Exception:
                continue
            if d[:4] not in (b"\x00\x01\x00\x00", b"true"):
                continue
            try:
                ft = TTFont(io.BytesIO(d))
                fam = (ft["name"].getDebugName(1) or "").lower()
            except Exception:
                continue
            if not any(t in fam for t in ("tt commons", "noto kufi")):
                continue
            if fam in found:
                continue
            capA = ink(ft, "A"); alef = ink(ft, "\u0627")
            found[fam] = (capA, alef)
            print(f"  {fam:34s} upem={ft['head'].unitsPerEm:<6} "
                  f"cap(A)={capA if capA else float('nan'):.4f} em   "
                  f"alef={alef if alef else float('nan'):.4f} em")
except Exception as ex:
    print("  [!] could not read FC6 archives:", ex)

lat = [v[0] for v in found.values() if v[0]]
if lat:
    C = sum(lat) / len(lat)
    print(f"\nFC6 latin cap = {C:.4f} em  ->  FC6 renders  hebrew/latin-cap = {H_body/C:.3f}")
else:
    C = None

# --- FC5
chars = parse_fnt(os.path.join(HERE, "..", "extract", "arabic.fnt"))
cap5 = chars[65][3]
alef5 = chars[0x0627][3] if 0x0627 in chars else None
print(f"\nFC5 atlas: latin cap = {cap5:.2f} px   arabic alef = {alef5:.2f} px")
if C:
    tgt = cap5 * (H_body / C)
    print(f"  -> to match FC6, FC5 hebrew body should be {tgt:.1f} px  (currently 25)")
# an Arabic-anchored cross-check: both games render Arabic in the same slot
al6 = [v[1] for v in found.values() if v[1]]
if al6 and alef5:
    A = sum(al6) / len(al6)
    print(f"  cross-check vs ARABIC: FC6 alef = {A:.4f} em -> hebrew/alef = {H_body/A:.3f}"
          f"  ->  {alef5 * H_body / A:.1f} px")
