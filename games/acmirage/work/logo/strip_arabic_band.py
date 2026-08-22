#!/usr/bin/env python3
"""
strip_arabic_band.py — make every ARABIC logo texture look like the LATIN one:
keep ASSASSIN'S CREED + MIRAGE, drop the script line underneath.

The game ships one logo texture per script, and the Latin-style variants simply have
nothing under MIRAGE. `UI_PressStart_Text_RU` proves it on the SAME canvas as the Arabic
one — 1024x560, identical first two bands, and no third:

    UI_PressStart_Text_AR   1024x560  bands (6,201) (232,348) (375,540)   <- 3 lines
    UI_PressStart_Text_RU   1024x560  bands (6,201) (233,345)             <- the target

So this does not draw anything: it clears the alpha of everything BELOW MIRAGE. The
result is the Latin lockup, in the Arabic slot, at the same size and position.

Two properties make it safe:

  * the cut is BLOCK-ALIGNED. BC7 is 4x4 blocks with no inter-block state, so every
    block row that still contains MIRAGE ink is carried over BYTE-IDENTICALLY and only
    fully-cleared block rows are re-encoded. Verified per texture as `max err 0`.
  * the payload keeps its exact length, so the resource is a delta-0 swap and goes back
    in-place: the forge's size, records, offsets and every other resource are untouched.

The store order is BOTTOM-UP (proved by diffing a decode against the reference with and
without `flipud`), so the rows to re-encode are the FIRST block rows of the payload, not
the last — getting that backwards silently keeps the Arabic and wipes ASSASSIN'S CREED,
and a per-band check still reads "clean" because both halves are individually correct.

    python strip_arabic_band.py            # build + preview + verify
    python strip_arabic_band.py --deploy    # also write into the forge
"""
import argparse
import os
import struct
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, "..", "..", "tools")
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "acshadows", "tools"))

from bc7_encode import encode  # noqa: E402
from find_logo import bands_of  # noqa: E402
from mirage_texture import load  # noqa: E402
import mirage_deploy  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

FORGE = r"F:/Game Lab/Assassin's Creed Mirage/DataPC_extra.forge"

# every texture the name scan found carrying Arabic (find_ar_textures.py):
#   2 families x {Map_PC, MapDesc, Map_Durango_Orbis}. The Durango/Orbis pair is the
#   console half-res copy the PC build never reads — patched anyway so the answer is
#   "no Arabic anywhere", not "no Arabic where I looked".
TARGETS = [
    (2181436741074, 1024, 560, "PressStart_AR_Map_PC"),
    (2181436741075, 1024, 560, "PressStart_AR_MapDesc"),
    (2181436742028,  512, 280, "PressStart_AR_Durango"),
    (2141045950540, 1072, 600, "TitleReveal_AR_Map_PC"),
    (2141045950541, 1072, 600, "TitleReveal_AR_MapDesc"),
    (2141045950553,  536, 300, "TitleReveal_AR_Durango"),
]


def decode_rgba(pixels, w, h):
    """BC7 payload -> display-order RGBA (the store order is bottom-up)."""
    return np.flipud(np.array(Image.frombytes("RGBA", (w, h), pixels, "bcn", (7,))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--forge", default=FORGE)
    a = ap.parse_args()

    built, failed = [], 0
    for rid, w, h, label in TARGETS:
        res, _ = load(a.forge, rid, payload_len=w * h)
        orig = decode_rgba(res.pixels, w, h)
        bands = bands_of(orig[..., 3])
        print(f"\n=== {label}  ({res.name})")
        print(f"    {w}x{h}  bands={bands}")
        if len(bands) < 3:
            print("    already has no script line — skipped")
            continue

        # everything under MIRAGE goes; snap UP to a block boundary so no block row
        # holding MIRAGE ink is ever re-encoded
        cut = -(-(bands[1][1] + 1) // 4) * 4
        print(f"    clearing display rows {cut}..{h-1}  "
              f"(MIRAGE ends {bands[1][1]}, script line was {bands[2]})")

        out = orig.copy()
        out[cut:, :, :] = 0                      # transparent black, RGB included

        flipped = np.flipud(out)                 # -> store order
        n_rows = (h - cut) // 4                  # the cleared rows sit FIRST when stored
        enc = encode(np.ascontiguousarray(flipped[: n_rows * 4]))
        payload = enc + res.pixels[n_rows * (w // 4) * 16:]
        assert len(payload) == len(res.pixels), f"{len(payload)} != {len(res.pixels)}"

        back = decode_rgba(payload, w, h)
        keep_err = int(np.abs(back[:cut].astype(int) - orig[:cut].astype(int)).max())
        residue = int(back[cut:, :, 3].max())
        new_bands = bands_of(back[..., 3])
        ok = keep_err == 0 and residue == 0
        print(f"    kept rows 0..{cut-1}: max err {keep_err} "
              f"({'IDENTICAL' if keep_err == 0 else 'CHANGED — REJECT'})  |  "
              f"leftover alpha below: {residue}  |  bands now {new_bands}")
        if not ok:
            print("    !! verification failed — not deploying this one")
            failed += 1
            continue

        prev = Image.new("RGB", (w, h), (12, 10, 22))
        im = Image.fromarray(back)
        prev.paste(im, (0, 0), im)
        prev.save(os.path.join(HERE, f"_STRIP_{label}.png"))
        blob = res.rebuild(payload)
        print(f"    blob {len(blob):,} B  -> _STRIP_{label}.png")
        built.append((rid, label, blob))

    print(f"\n{len(built)} texture(s) built, {failed} rejected")
    if failed:
        raise SystemExit("refusing to deploy while a texture fails verification")
    if not a.deploy:
        print("(dry run — pass --deploy to write into the forge)")
        return 0

    for rid, label, blob in built:
        print(f"\n-- {label}")
        mirage_deploy.apply_inplace(a.forge, rid, blob)
    return 0


if __name__ == "__main__":
    sys.exit(main())
