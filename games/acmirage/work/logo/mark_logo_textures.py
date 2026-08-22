#!/usr/bin/env python3
"""
mark_logo_textures.py — paint each logo texture a DIFFERENT solid colour, so ONE launch
identifies which asset the main menu actually draws.

Every content search has now come up empty: the Arabic artwork exists in exactly 6
textures across every forge scanned (extra, extra_patch, DataPC, DataPC_patch,
SharedGroup x2, TitleScreen, DX12 x5, WhiteRoom x2, Alula, dlc_2) and all 6 are already
stripped — yet the main menu still shows it. So the remaining question is not "where is
the Arabic" but "what does the main menu draw", and only the screen can answer that.

This is the ladder trick ([[measure-with-a-ladder]]) applied to identity instead of a
value: give each candidate a UNIQUE unmistakable colour and read the answer off one
screenshot.

    magenta -> UI_PressStart_Text_AR      (the press-start lockup, gold)
    cyan    -> UI_TitleReveal_AR          (the white lockup)
    yellow  -> UI_TitleReveal_LogoText    (the LATIN two-line lockup)

Outcomes, all decisive:
  * a coloured block appears  -> that texture IS the main-menu logo
  * AC+MIRAGE turns yellow but the Arabic line does NOT -> the menu COMPOSITES the Latin
    lockup with a separate Arabic strip, and the strip is a one-band texture that every
    3-band signature search would have rejected
  * nothing changes           -> the menu logo is none of these; stop scanning textures

The press-start screen is a free control: it must turn magenta, which proves the deploy
path still works and keeps a null result meaningful.

    python mark_logo_textures.py            # build + preview
    python mark_logo_textures.py --deploy
    python mark_logo_textures.py --revert   # restore the pristine forge
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, "..", "..", "tools")
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "acshadows", "tools"))

from bc7_encode import encode  # noqa: E402
from mirage_texture import load  # noqa: E402
import mirage_deploy  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

FORGE = r"F:/Game Lab/Assassin's Creed Mirage/DataPC_extra.forge"

MARKS = [
    (2181436741074, 1024, 560, (255, 0, 255), "PressStart_AR_Map_PC   MAGENTA"),
    (2181436741075, 1024, 560, (255, 0, 255), "PressStart_AR_MapDesc  MAGENTA"),
    (2141045950540, 1072, 600, (0, 255, 255), "TitleReveal_AR_Map_PC  CYAN"),
    (2141045950541, 1072, 600, (0, 255, 255), "TitleReveal_AR_MapDesc CYAN"),
    (2141045585818, 1072, 384, (255, 255, 0), "TitleReveal_LogoText   YELLOW"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--forge", default=FORGE)
    a = ap.parse_args()

    if a.revert:
        return mirage_deploy.revert(a.forge)

    built = []
    for rid, w, h, rgb, label in MARKS:
        res, _ = load(a.forge, rid, payload_len=w * h)
        img = np.zeros((h, w, 4), np.uint8)
        img[:, :, 0], img[:, :, 1], img[:, :, 2] = rgb
        img[:, :, 3] = 255                      # fully opaque: impossible to miss
        payload = encode(img)
        if len(payload) != len(res.pixels):
            print(f"  !! {label}: payload {len(payload)} != slot {len(res.pixels)}")
            continue
        # decode it straight back — the only proof the marker will actually LOOK like the
        # marker. A null result is only meaningful if the probe itself is sound.
        back = np.array(Image.frombytes("RGBA", (w, h), payload, "bcn", (7,)))
        flat = back.reshape(-1, 4)
        uniform = bool((flat == flat[0]).all())
        got = tuple(int(x) for x in flat[0])
        blob = res.rebuild(payload)
        print(f"  {label:<32} {w}x{h}  blob {len(blob):,} B  decode={got} "
              f"{'UNIFORM' if uniform else '!! NOT UNIFORM'}   ({res.name})")
        # tolerance, not equality: BC7 mode 6 is near-lossless but not exact (max 1/255),
        # and a guard tighter than the encoder rejects perfectly good output
        off = max(abs(a_ - b_) for a_, b_ in zip(got[:3], rgb))
        if not uniform or off > 4:
            print(f"     !! marker would not render as intended (off by {off}) — skipped")
            continue
        built.append((rid, label, blob))

    if not a.deploy:
        print("\n(dry run — pass --deploy to write into the forge)")
        return 0
    for rid, label, blob in built:
        print(f"\n-- {label}")
        mirage_deploy.apply_inplace(a.forge, rid, blob)
    print("\nNow launch and screenshot the MAIN MENU (and note the press-start screen).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
