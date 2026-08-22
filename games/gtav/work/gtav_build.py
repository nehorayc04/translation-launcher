#!/usr/bin/env python3
"""gtav_build.py — assemble + deploy the Hebrew global.gxt2 into the OpenIV mods/ slot.

Pipeline:
  1. read agent_handoff/hebrew.json {joaat_hex: hebrew_LOGICAL}
  2. read work/global_en.json (pristine English dict, from gtav_extract.py)
  3. for every key: VISUAL-reverse the Hebrew (gtav_gxt2.visual_line); untranslated keys
     keep their English so nothing goes blank
  4. write a new global.gxt2 (gtav_gxt2.write_gxt2)
  5. repack into mods/update/update.rpf via gtautil (or write an OPEN RPF7 that OpenIV
     still loads — sidesteps NG-encrypt) and back up the prior mods copy first
  6. game must be CLOSED. Activation: none — the user keeps Language=American and sees
     Hebrew (American slot hijacked). The Hebrew Scaleform font is already installed.

Without gtautil this stops after step 4 (writes work/global_he.gxt2) and prints the
manual OpenIV import step. Reversible: the real update/update.rpf is never touched.
"""
import json, os, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gtav_gxt2 as G  # noqa
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GAME = r"F:\Games\Grand Theft Auto V Legacy"
HANDOFF = os.path.normpath(os.path.join(HERE, "..", "agent_handoff"))
GXT2_REL = r"x64\data\lang\american_rel.rpf\global.gxt2"


def find_gtautil():
    for c in (os.environ.get("GTAUTIL"), shutil.which("gtautil"),
              os.path.join(GAME, "gtautil.exe"),
              os.path.join(HERE, "..", "tools", "gtautil.exe")):
        if c and os.path.exists(c):
            return os.path.abspath(c)
    return None


def build_gxt2():
    en = json.load(open(os.path.join(HERE, "global_en.json"), encoding="utf-8"))
    he = json.load(open(os.path.join(HANDOFF, "hebrew.json"), encoding="utf-8"))
    out = {}
    nh = 0
    for hex_key, eng in en.items():
        h = int(hex_key, 16)
        logical = he.get(hex_key)
        if logical:
            out[h] = G.visual_line(logical)        # logical -> visual at build time
            nh += 1
        else:
            out[h] = eng                           # keep English (no blank)
    blob = G.write_gxt2(out)
    dst = os.path.join(HERE, "global_he.gxt2")
    open(dst, "wb").write(blob)
    print(f"built {dst}: {len(out)} entries, {nh} Hebrew (visual), "
          f"{len(out)-nh} English fallback, {len(blob)} bytes")
    return dst


def deploy(gxt2_path):
    gt = find_gtautil()
    if not gt:
        print("gtautil not found — gxt2 built but NOT deployed.\n"
              f"MANUAL: import {gxt2_path}\n  into mods/update/update.rpf at {GXT2_REL}\n"
              "via OpenIV (right-click american_rel.rpf > Replace), game closed.",
              file=sys.stderr)
        return
    upd = os.path.join(GAME, "mods", "update", "update.rpf")
    bak = upd + ".bak.%s" % time.strftime("%Y%m%d_%H%M%S")
    shutil.copy2(upd, bak)
    print("backup ->", bak)
    # gtautil replaces a nested file and re-encrypts the archive (fixarchive).
    subprocess.run([gt, "replace", "--input", upd, "--file", GXT2_REL,
                    "--data", gxt2_path], check=True)
    print("deployed Hebrew global.gxt2 into mods/update/update.rpf")


def main():
    if "--build-only" in sys.argv:
        build_gxt2()
        return
    deploy(build_gxt2())


if __name__ == "__main__":
    main()
