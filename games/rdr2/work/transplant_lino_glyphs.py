#!/usr/bin/env python3
"""transplant_lino_glyphs.py — give EVERY face the Hebrew LETTERFORMS that RDR Lino has.

🔴 THE DEFECT THE USER SAW, and it is a letterFORM problem, not a size one. The font carries
TWO different Hebrew glyph sets: `RDR Lino` was rebuilt by `rdr2_stencil_font.build_letter`
(a western, condensed, slightly distressed construction matching that face's own Latin),
while the other 17 faces got the plain modern-sans donor from `font_add_hebrew`. So the
prompt bar (Lino) renders `צא מהמשחק` in the game's own western style while the pause menu
renders the same words in a thin generic sans — two different-looking fonts in one UI.
The user's instruction: "שהפונט התפריט יהיה אותו פונט כמו שיש ל'סיפור' 'צא מהמשחק'".

🔑 WHY TRANSPLANT INSTEAD OF IDENTIFYING THE MENU'S FACE. All 18 faces draw the SAME donor
outlines, so a screenshot cannot say which face any surface uses — the only distinguishing
signal is size, and identifying one face costs one game launch per candidate. Copying Lino's
glyphs into every face makes the answer true regardless of which face the menu turns out to
be, and it is what "the same font everywhere" means anyway.

SINGLE VARIABLE: each face keeps its CURRENT Hebrew height. `k` is measured per face as
(that face's own Hebrew median box height) / (Lino's), so this changes the letterform and
nothing else — a regression can only be a letterform regression.

    python transplant_lino_glyphs.py report
    python transplant_lino_glyphs.py apply <out.xml>
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from rescale_hebrew_faces import (          # noqa: E402
    HEB_HI, HEB_LO, RE_ADV, box_of, codes_of, face_slices, glyph_spans, scale_glyph,
)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

FI = os.path.join(HERE, "_fontinspect")
SRC = os.path.join(FI, "rescaled_full.xml")     # == the currently deployed .gfx
OUT = os.path.join(FI, "lino_full.xml")
SOURCE_FACE = "RDR Lino"


def hebrew_of(txt, a, b):
    """-> {codepoint: (glyph_span, advance, box_height)} for one face's Hebrew glyphs."""
    gl, gi = glyph_spans(txt, a, b)
    codes = codes_of(txt, gi)
    out = {}
    for i in range(min(len(gl), len(gi))):
        c = codes[i]
        if not (HEB_LO <= c <= HEB_HI):
            continue
        bx = box_of(txt, *gl[i])
        m = RE_ADV.search(txt[gi[i][0]:gi[i][1]])
        out[c] = (gl[i], gi[i], int(m.group(1)) if m else 0,
                  (bx[3] - bx[1]) if bx else 0)
    return out


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    print(f"reading {SRC} ({os.path.getsize(SRC)/1e6:.0f} MB) ...", flush=True)
    txt = open(SRC, encoding="utf-8", errors="replace").read()
    print(f"loaded {len(txt)/1e6:.0f} M chars\n", flush=True)

    faces = face_slices(txt)
    src = next((f for f in faces if f[0] == SOURCE_FACE), None)
    if src is None:
        sys.exit(f"!! source face {SOURCE_FACE!r} not found")
    sheb = hebrew_of(txt, src[1], src[2])
    sh = sorted(v[3] for v in sheb.values())[len(sheb) // 2]
    print(f"source {SOURCE_FACE}: {len(sheb)} Hebrew glyphs, median box height {sh}\n")

    edits, plan = [], []
    for name, a, b in faces:
        if name == SOURCE_FACE:
            continue
        dst = hebrew_of(txt, a, b)
        if not dst:
            continue
        dh = sorted(v[3] for v in dst.values())[len(dst) // 2]
        if dh <= 0:
            continue
        k = dh / sh
        cnt = 0
        for c, (gspan, ispan, _adv, _h) in dst.items():
            if c not in sheb:
                continue
            sg, si, sadv, _ = sheb[c]
            # the SOURCE glyph body, scaled to this face's own current height
            edits.append((gspan[0], gspan[1], scale_glyph(txt[sg[0]:sg[1]], k)))
            seg = txt[ispan[0]:ispan[1]]
            m = RE_ADV.search(seg)
            if m:
                adv = int(round(sadv * k))
                edits.append((ispan[0], ispan[1],
                              seg[:m.start()] + f'advanceX="{adv}"' + seg[m.end():]))
            cnt += 1
        plan.append((name, cnt, dh, k))

    print(f"{'face':32} {'glyphs':>7} {'height':>7} {'k':>7}")
    print("-" * 58)
    for name, cnt, dh, k in plan:
        print(f"{name[:32]:32} {cnt:>7} {dh:>7} {k:>7.3f}")
    print(f"\n{sum(p[1] for p in plan)} glyphs across {len(plan)} faces")

    if cmd != "apply":
        print("\n(report only — run `apply <out.xml>`)")
        return

    out_path = sys.argv[2] if len(sys.argv) > 2 else OUT
    # ⚠️ ONE join, never a slice-concat per edit — that copies the whole 345 M-char document
    # per edit and turns ~900 edits into hundreds of GB of copying.
    edits.sort(key=lambda t: t[0])
    parts, cur = [], 0
    for s, e, rep in edits:
        if s < cur:
            sys.exit(f"!! overlapping edits at {s} (prev end {cur})")
        parts.append(txt[cur:s])
        parts.append(rep)
        cur = e
    parts.append(txt[cur:])
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("".join(parts))
    print(f"\nwrote {out_path} ({os.path.getsize(out_path)/1e6:.0f} MB)")


if __name__ == "__main__":
    main()
