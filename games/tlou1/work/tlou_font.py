#!/usr/bin/env python3
r"""
tlou_font.py - Hebrew font for The Last of Us Part I.

The shipped UI fonts (`core.psarc/fonts/*.otf|*.ttf`) cover Latin/Cyrillic/Greek/
CJK/Thai but NONE covers Hebrew (cmap-verified: 0 glyphs in U+05D0-05EA across all
16 faces). The primary UI faces `DINPro-Regular.otf` / `DINPro-Medium.otf` are
CFF/PostScript-outline OTFs, so the Anno-style `glyf` glyph-copy injection is a
no-op on them. The robust approach for a LOOSE-FILE override (no byte-length
constraint) is REPLACE: ship a font that covers BOTH Latin and Hebrew under the
target's filename, optionally masquerading the internal `name` table so an engine
that matches by family name still resolves it.

Aesthetic: TLOU's UI is a clean industrial grotesque (FF DIN / Neue Helvetica).
Good Hebrew pairings (present a choice to the user): Heebo (a Hebrew Roboto -
closest to DIN), Assistant, Rubik, or the classic David / Frank Ruehl. For the
menu-PROOF, any Latin+Hebrew font (Arial covers both, universal) proves render.

CLI:
    python tlou_font.py check <font>                       # cmap coverage
    python tlou_font.py make  <hebrew_src> <out.otf> [--name-ref <DINPro.otf>]
"""
import os
import sys
import io
import argparse

from fontTools.ttLib import TTFont

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RANGES = {
    "Latin":    (0x41, 0x7A),
    "Latin-1":  (0xC0, 0xFF),
    "Hebrew":   (0x5D0, 0x5EA),
    "HebrewPts":(0x591, 0x5C7),
    "Arabic":   (0x600, 0x6FF),
    "Cyrillic": (0x400, 0x4FF),
    "Greek":    (0x391, 0x3A9),
    "Thai":     (0xE01, 0xE3A),
}

HEBREW_SRC_CANDIDATES = [
    r"C:\Windows\Fonts\arial.ttf",     # Arial - Latin + full Hebrew, universal (proof)
    r"C:\Windows\Fonts\ arial.ttf",
    r"C:\Windows\Fonts\david.ttf",     # David - clean Hebrew
    r"C:\Windows\Fonts\FrankRuehl.ttf",
]


def _coverage(ft):
    cmap = set(ft.getBestCmap().keys())
    out = []
    for name, (lo, hi) in RANGES.items():
        n = sum(1 for cp in range(lo, hi + 1) if cp in cmap)
        if n:
            out.append(f"{name}={n}/{hi - lo + 1}")
    return len(cmap), out


def cmd_check(a):
    with open(a.font, "rb") as f:
        ft = TTFont(io.BytesIO(f.read()), lazy=True)
    n, cov = _coverage(ft)
    print(f"{os.path.basename(a.font)}  glyphs~{n}  {'  '.join(cov)}")


def _pick_src(explicit):
    for p in ([explicit] if explicit else []) + HEBREW_SRC_CANDIDATES:
        if p and os.path.isfile(p):
            return p
    raise SystemExit("no Hebrew+Latin source font found (pass one explicitly)")


def cmd_make(a):
    src = _pick_src(a.hebrew_src)
    ft = TTFont(src)
    # verify it actually covers Hebrew + Latin
    cmap = set(ft.getBestCmap().keys())
    heb = sum(1 for cp in range(0x5D0, 0x5EB) if cp in cmap)
    lat = sum(1 for cp in range(0x41, 0x7B) if cp in cmap)
    if heb < 20 or lat < 40:
        raise SystemExit(f"source font weak coverage (Hebrew {heb}/27, Latin {lat}/58): {src}")
    # optional: masquerade as the reference font's family/style names
    if a.name_ref and os.path.isfile(a.name_ref):
        ref = TTFont(a.name_ref)
        ref_name = ref["name"]
        ft["name"] = ref_name
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    ft.save(a.out)
    n, cov = _coverage(TTFont(a.out, lazy=True))
    print(f"wrote {a.out}  (from {os.path.basename(src)}"
          + (f", named as {os.path.basename(a.name_ref)}" if a.name_ref else "")
          + f")  glyphs~{n}  {'  '.join(cov)}")


def main():
    ap = argparse.ArgumentParser(description="TLOU Part I Hebrew font")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check"); c.add_argument("font")
    m = sub.add_parser("make")
    m.add_argument("hebrew_src", nargs="?", default=None)
    m.add_argument("out")
    m.add_argument("--name-ref", help="OTF whose name table to copy (masquerade)")
    a = ap.parse_args()
    {"check": cmd_check, "make": cmd_make}[a.cmd](a)


if __name__ == "__main__":
    main()
