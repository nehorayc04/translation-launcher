#!/usr/bin/env python3
"""build_menu_proof.py — assemble a ready-to-drop Lenny's-Mod-Loader menu-proof for RDR2.

Proves the WHOLE Hebrew chain in-game with the minimum content: it overrides the boot
LEGAL_SPLASH (guaranteed visible every launch — the same key Ko Games' Arabic mod uses) with
a Latin mount-marker + Hebrew stored VISUAL, and ships the Hebrew-injected Scaleform font.
When the user boots RDR2 with LML installed:
  * the marker  ZZ-RDR2-OK-ZZ  appearing  = the DataFile override MOUNTS + the font LOADS,
  * the Hebrew reading correctly right-to-left (not mirrored) = bidi is VISUAL (as expected
    from the Arabic-mod precedent); mirrored = it is LOGICAL (flip build_hebrew off visual).

Layout produced (mirrors Ko Games' proven two-mod structure):
  menu_proof/lml/mods.xml
  menu_proof/lml/rdr2he_font/install.xml        (FileReplacement -> font_lib_efigs.gfx)
  menu_proof/lml/rdr2he_font/asset_replace/font_lib_efigs.gfx
  menu_proof/lml/rdr2he_text/install.xml        (DataFile)
  menu_proof/lml/rdr2he_text/RDR2 Hebrew.gxt2

Run:  python build_menu_proof.py <font_lib_efigs_HE.gfx>
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(__file__))
import rdr2_text as R

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "menu_proof", "lml")

# Boot-splash proof strings (logical Hebrew; build_hebrew stores them VISUAL). LEGAL_SPLASH_1
# is the disclaimer banner shown at every launch. The Latin marker proves mount+font.
PROOF = {
    "LEGAL_SPLASH_1": "ZZ-RDR2-OK-ZZ ~n~ שלום עולם — תרגום עברית ~n~ בדיקת כיוון: 12 כוכבים",
    "LEGAL_SPLASH_2": "מרכז התרגום העברי ~n~ Hebrew Translation Hub",
}

MODS_XML = """﻿<?xml version="1.0" encoding="utf-8"?>
<ModsManager>
  <Mods>
    <Mod folder="rdr2he_font">
      <Name>RDR2 Hebrew Font (proof)</Name>
      <Enabled>true</Enabled>
      <Overwrite>false</Overwrite>
      <DisabledGroups />
    </Mod>
    <Mod folder="rdr2he_text">
      <Name>RDR2 Hebrew Text (proof)</Name>
      <Enabled>true</Enabled>
      <Overwrite>false</Overwrite>
      <DisabledGroups />
    </Mod>
  </Mods>
  <LoadOrder>
    <Mod>rdr2he_font</Mod>
    <Mod>rdr2he_text</Mod>
  </LoadOrder>
</ModsManager>
"""

FONT_INSTALL = """<EasyInstall>
    <Name>RDR2 Hebrew Font (proof)</Name>
    <Author>Hebrew Translation Hub</Author>
    <Version>1.0.0</Version>
    <Resources>
        <Resource>
            <StreamingFiles>stream</StreamingFiles>
            <FileReplacement>
                <GamePath>update:/x64/patch/data/cdimages/scaleform_frontend/font_lib_efigs.gfx</GamePath>
                <FilePath>asset_replace/font_lib_efigs.gfx</FilePath>
            </FileReplacement>
        </Resource>
    </Resources>
</EasyInstall>
"""

TEXT_INSTALL = """<EasyInstall>
    <Name>RDR2 Hebrew Text (proof)</Name>
    <Author>Hebrew Translation Hub</Author>
    <Version>1.0.0</Version>
    <Resources>
        <Resource>
            <DataFile>RDR2 Hebrew.gxt2</DataFile>
        </Resource>
    </Resources>
</EasyInstall>
"""


def main():
    font_src = sys.argv[1]
    if os.path.isdir(os.path.join(HERE, "menu_proof")):
        shutil.rmtree(os.path.join(HERE, "menu_proof"))
    os.makedirs(os.path.join(OUT, "rdr2he_font", "asset_replace"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "rdr2he_text"), exist_ok=True)

    # text override (VISUAL)
    recs = R.build_hebrew([], PROOF)          # empty base -> just our proof keys
    text = "# RED DEAD REDEMPTION 2 Hebrew — menu proof\n\n" + R.serialise(recs) + "\n"
    with open(os.path.join(OUT, "rdr2he_text", "RDR2 Hebrew.gxt2"), "w", encoding="utf-8") as f:
        f.write(text)

    with open(os.path.join(OUT, "mods.xml"), "w", encoding="utf-8") as f:
        f.write(MODS_XML)
    with open(os.path.join(OUT, "rdr2he_font", "install.xml"), "w", encoding="utf-8") as f:
        f.write(FONT_INSTALL)
    with open(os.path.join(OUT, "rdr2he_text", "install.xml"), "w", encoding="utf-8") as f:
        f.write(TEXT_INSTALL)
    shutil.copy2(font_src, os.path.join(OUT, "rdr2he_font", "asset_replace", "font_lib_efigs.gfx"))

    print("built menu-proof LML at:", OUT)
    for root, _, files in os.walk(os.path.join(HERE, "menu_proof")):
        for fn in files:
            p = os.path.join(root, fn)
            print(f"  {os.path.relpath(p, HERE)}  ({os.path.getsize(p)} B)")
    print("\nVISUAL storage sample (LEGAL_SPLASH_1):")
    print("  " + R.to_map(recs)["LEGAL_SPLASH_1"])


if __name__ == "__main__":
    main()
