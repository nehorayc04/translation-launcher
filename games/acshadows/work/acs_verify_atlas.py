#!/usr/bin/env python3
"""Read the Hebrew glyphs back OUT of the LIVE forges and prove the codepoint->raster
pairing is right.

Single source of truth on purpose: weights come from acs_atlas_inject.discover_weights()
(by CONTENT) and records from acs_atlas_inject._records() (the corrected <I7fI> layout).
The previous verifier kept private copies of both and therefore kept "confirming" a stale
index map and a 4-byte-late record parse.

    python acs_verify_atlas.py            # summary for every Arabic weight
    python acs_verify_atlas.py --show אבש  # + ASCII art for those letters
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import acs_cfd as C            # noqa: E402
import acs_forge as F          # noqa: E402
import acs_atlas_inject as AI  # noqa: E402

RAMP = " .:-=+*#%@"


def _decoded(path, idx, oodle):
    r = next(x for x in F.parse(path)["recs"] if x["i"] == idx)
    with open(path, "rb") as f:
        f.seek(r["offset"])
        blob = f.read(r["size"])
    cfds, _end = C.decode_resource(blob, oodle)
    return max((x for x, _ in cfds), key=len)


def art(dec, r, cols=30):
    w, h, t = r["W"], r["H"], r["toff"]
    if w <= 0 or h <= 0 or t <= 0 or t + w * h > len(dec):
        return ["   <no raster>"]
    step = max(1, w // cols)
    return ["".join(RAMP[min(9, dec[t + y * w + x] * 10 // 256)] for x in range(0, w, step))
            for y in range(0, h, max(1, step * 2))]


def main():
    show = ""
    if "--show" in sys.argv:
        i = sys.argv.index("--show")
        show = sys.argv[i + 1] if len(sys.argv) > i + 1 else "אבש"
    oodle = C._oodle()
    weights = AI.discover_weights()
    if not weights:
        print("no Arabic PHXFD weights found"); return 1
    ok = 0
    for path, idx in weights:
        dec = _decoded(path, idx, oodle)
        _g, cnt, _s, gl = AI._records(dec)
        heb = [r for r in gl if 0x05D0 <= r["cp"] <= 0x05EA]
        bad = [r for r in heb if r["W"] <= 0 or r["H"] <= 0 or r["toff"] <= 0
               or r["toff"] + r["W"] * r["H"] > len(dec)]
        ink = sum(sum(1 for b in dec[r["toff"]:r["toff"] + r["W"] * r["H"]] if b > 140)
                  for r in heb if r not in bad)
        good = len(heb) == 27 and not bad and ink > 0
        ok += good
        print(f"  {os.path.basename(path):<30} idx {idx:<6} glyphs={cnt:<5} "
              f"HEB={len(heb):<3} bad={len(bad):<3} ink={ink:>7,}  "
              f"{'OK' if good else '** FAIL'}")
        for ch in show:
            hit = [r for r in gl if r["cp"] == ord(ch)]
            if hit:
                print(f"     '{ch}' U+{ord(ch):04X}  {hit[0]['W']}x{hit[0]['H']}")
                for ln in art(dec, hit[0]):
                    print("        |" + ln)
        show = show if len(weights) == 1 else ""     # art once, not eight times
    print(f"\n{ok}/{len(weights)} weights carry 27 clean Hebrew glyphs.")
    return 0 if ok == len(weights) else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
