#!/usr/bin/env python3
"""READ-ONLY verification of the deployed AC Shadows Hebrew font state.
Never writes a forge. Confirms:
  1. all 3 forges parse + contiguity invariant holds
  2. pristine backups exist and are decodable
  3. each of the 8 PHXFD weights currently on disk has 27 Hebrew codepoints
  4. the injected rasters read back as real ink (not empty/tofu)
"""
import os, sys, struct, glob

REPO = r"c:\Users\Nehoray_Cohen\Projects\Game translator"
os.environ["ACS_OODLE_DLL"] = os.path.join(REPO, "Game Lab", "Battlefield 6", "oo2core_9_win64.dll")
sys.path.insert(0, os.path.join(REPO, "games", "acshadows", "tools"))
sys.path.insert(0, os.path.join(REPO, "games", "acshadows", "work"))
import acs_forge as F
import acs_cfd as C
import acs_atlas_inject as AI

GAME = r"C:\Games\Assassin's Creed Shadows"
P2 = os.path.join(GAME, "DataPC_boot_patch_02.forge")
P1 = os.path.join(GAME, "DataPC_boot_patch_01.forge")
BOOT = os.path.join(GAME, "DataPC_boot.forge")
WEIGHTS = [(P2, 20630), (P2, 20631), (P2, 20632),
           (P1, 24062), (P1, 24063),
           (BOOT, 82569), (BOOT, 82570), (BOOT, 82571)]
HEB = set(range(0x05D0, 0x05EA + 1))

def main():
    oodle = C._oodle()
    print("== 1. FORGE TOC CONTIGUITY ==")
    for p in (BOOT, P1, P2):
        info = F.parse(p)
        good, total = F.invariant(info["recs"])
        print(f"  {os.path.basename(p):<30} v{info['version']} count={info['count']:>6} "
              f"invariant={good}/{total} {'OK' if good==total else 'MISMATCH'}")

    print("\n== 2. PRISTINE BACKUPS ==")
    baks = sorted(glob.glob(os.path.join(REPO, "games", "acshadows", "work", "_atlasbak_*.bin")))
    print(f"  {len(baks)} _atlasbak_*.bin present")
    for b in baks:
        idx = int(os.path.basename(b).split("_")[2].split(".")[0])
        with open(b, "rb") as g:
            off, size = struct.unpack("<QQ", g.read(16)); rest = g.read()
        blen = len(rest) if len(rest) == size else len(rest) - rest.index(b"\x00") - 1
        print(f"    idx {idx:<6} off=0x{off:x} slot={size:>10,} blob={blen:>10,} "
              f"{'OK' if blen==size else 'MISMATCH'}")

    print("\n== 3. LIVE WEIGHTS: Hebrew codepoints on disk NOW ==")
    all_ok = True
    for forge, idx in WEIGHTS:
        info = F.parse(forge); r = info["recs"][idx]
        with open(forge, "rb") as f:
            f.seek(r["offset"]); blob = f.read(r["size"])
        cfds, end = C.decode_resource(blob, oodle)
        dec = max((x for x, _ in cfds), key=len)
        _g, _c, _s, recs = AI._records(dec)
        cps = {x["cp"] for x in recs}
        heb_present = sorted(cp for cp in cps if cp in HEB)
        n = len(heb_present)
        # readback ink: for each Hebrew record, count non-zero raster bytes
        ink = 0; boxes = 0
        for x in recs:
            if x["cp"] in HEB and x["W"] > 0 and x["H"] > 0 and 0 < x["toff"] <= len(dec):
                raster = dec[x["toff"]: x["toff"] + x["W"]*x["H"]]
                nz = sum(1 for v in raster if v >= AI.EDGE)
                ink += nz
                if nz == 0:
                    boxes += 1
        status = "OK" if n == 27 and boxes == 0 else "PROBLEM"
        if status != "OK": all_ok = False
        print(f"  idx={idx:<6} ({os.path.basename(forge):<28}) slot={r['size']:>10,} "
              f"decoded={len(dec):>10,} Heb={n:>2}/27 ink_px={ink:>7,} empty={boxes} -> {status}")
    print(f"\n== VERDICT: {'ALL 8 WEIGHTS PATCHED, 27/27 EACH, NO EMPTY RASTERS' if all_ok else 'PROBLEM DETECTED'} ==")
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
