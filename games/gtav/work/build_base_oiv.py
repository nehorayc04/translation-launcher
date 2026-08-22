#!/usr/bin/env python3
"""build_base_oiv.py — install the full Hebrew table into the REAL x64b BASE file (game
folder), the standard way every full GTA V translation (russifikator) ships.

Why: on this build there is NO mods path for the full table — mods\\x64b.rpf is not read at
runtime (verified: Hebrew there had zero effect), update2.rpf does not exist, the update
x64/patch slot is an OVERRIDE layer that HANGS story-load with a full table (proven with the
full AND the +325-DLC-key superset), and a custom DLC pack failed to mount. The ONLY layer
that loads the full table as the BASE (not as overrides) is x64b\\data\\lang\\american_rel.rpf
itself. Editing it = the table loads once as the base map -> no override-merge at world-init
-> no hang. Install to the GAME FOLDER (real files). Reversible via gtav_restore_BASE.oiv or
Steam/Rockstar "Verify Integrity".

gtav_hebrew_BASE.oiv (install to GAME FOLDER) writes, to the REAL files:
  * x64b\\data\\lang\\american_rel.rpf\\global.gxt2          <- full Hebrew (23,136)
  * update\\update.rpf\\x64\\patch\\data\\lang\\american_rel.rpf\\global.gxt2  <- vanilla 351 (clean)
  * update\\update.rpf\\x64\\data\\cdimages\\scaleform_generic.rpf\\font_lib_efigs.gfx     <- Hebrew font
  * update\\update.rpf\\x64\\data\\cdimages\\scaleform_platform_pc.rpf\\font_lib_efigs_pc.gfx <- Hebrew font
gtav_restore_BASE.oiv restores all four to byte-perfect vanilla.

⚠️ Before installing, the user must clear the mods folder for these archives (or delete the
mods folder) so the real edited files are the ones the game loads (mods\\update.rpf shadows
the real update.rpf).
"""
import os, uuid, zipfile, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
GTAV = os.path.normpath(os.path.join(HERE, ".."))
ORIG = os.path.join(GTAV, "_originals")
FSRC = os.path.join(GTAV, "_fonts_src")
REL = os.path.join(GTAV, "release")
GAME = r"F:\Games\Grand Theft Auto V Legacy"

HE_GXT2 = os.path.join(HERE, "global_he.gxt2")                          # Hebrew base
OG_BASE = os.path.join(HERE, "_rpf", "global.gxt2")                     # vanilla base 1,141,267
OG_PATCH = os.path.join(ORIG, "global_PATCH_vanilla_351entries.gxt2")   # vanilla patch 111,375
HE_EFIGS = os.path.join(ORIG, "font_lib_efigs_HEBREW.gfx")
HE_PC = os.path.join(ORIG, "font_lib_efigs_pc_HEBREW.gfx")
VAN_EFIGS = os.path.join(FSRC, "scaleform_generic.rpf", "font_lib_efigs.gfx")
VAN_PC = os.path.join(FSRC, "scaleform_platform_pc.rpf", "font_lib_efigs_pc.gfx")

ASM = '''<?xml version="1.0" encoding="utf-8"?>
<package version="2.2" id="%(id)s" target="Five">
  <metadata>
    <name>%(name)s</name>
    <version><major>1</major><minor>0</minor></version>
    <author><displayName>Game Translator</displayName></author>
    <description><![CDATA[%(desc)s]]></description>
  </metadata>
  <colors>
    <headerBackground useBlackTextColor="False">%(color)s</headerBackground>
    <iconBackground>$FF2E2E2E</iconBackground>
  </colors>
  <content>
    <archive path="x64b.rpf" createIfNotExist="True" type="RPF7">
      <archive path="data\\lang\\american_rel.rpf" createIfNotExist="True" type="RPF7">
        <add source="%(base)s">global.gxt2</add>
      </archive>
    </archive>
    <archive path="update\\update.rpf" createIfNotExist="True" type="RPF7">
      <archive path="x64\\patch\\data\\lang\\american_rel.rpf" createIfNotExist="True" type="RPF7">
        <add source="global_patch_vanilla.gxt2">global.gxt2</add>
      </archive>
      <archive path="x64\\data\\cdimages\\scaleform_generic.rpf" createIfNotExist="True" type="RPF7">
        <add source="%(fgen)s">font_lib_efigs.gfx</add>
      </archive>
      <archive path="x64\\data\\cdimages\\scaleform_platform_pc.rpf" createIfNotExist="True" type="RPF7">
        <add source="%(fpc)s">font_lib_efigs_pc.gfx</add>
      </archive>
    </archive>
  </content>
</package>
'''


def build(fname, name, desc, color, base_src, fgen_src, fpc_src, files):
    os.makedirs(REL, exist_ok=True)
    out = os.path.join(REL, fname)
    asm = ASM % dict(id="{" + str(uuid.uuid4()).upper() + "}", name=name, desc=desc,
                     color=color, base=base_src, fgen=fgen_src, fpc=fpc_src)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("assembly.xml", asm)
        for arc, src in files.items():
            z.write(src, "content/" + arc)
    shutil.copy2(out, os.path.join(GAME, fname))
    print("built", fname, os.path.getsize(out), "B -> game folder")


def main():
    build("gtav_hebrew_BASE.oiv",
          "GTA V Hebrew - BASE file (full UI, install to GAME folder)",
          "Full Hebrew UI written into the REAL x64b base table (the standard full-translation method) + Hebrew fonts + clean vanilla patch slot. INSTALL TO GAME FOLDER. Clear the mods folder first. Set language to American.",
          "$FF1565C0",
          "global_he.gxt2", "font_lib_efigs_HEBREW.gfx", "font_lib_efigs_pc_HEBREW.gfx",
          {"global_he.gxt2": HE_GXT2, "global_patch_vanilla.gxt2": OG_PATCH,
           "font_lib_efigs_HEBREW.gfx": HE_EFIGS, "font_lib_efigs_pc_HEBREW.gfx": HE_PC})
    build("gtav_restore_BASE.oiv",
          "GTA V - RESTORE vanilla BASE (game folder)",
          "Restores byte-perfect vanilla: x64b base global.gxt2 + patch slot + both fonts. INSTALL TO GAME FOLDER.",
          "$FFB71C1C",
          "global_base_vanilla.gxt2", "font_lib_efigs_vanilla.gfx", "font_lib_efigs_pc_vanilla.gfx",
          {"global_base_vanilla.gxt2": OG_BASE, "global_patch_vanilla.gxt2": OG_PATCH,
           "font_lib_efigs_vanilla.gfx": VAN_EFIGS, "font_lib_efigs_pc_vanilla.gfx": VAN_PC})


if __name__ == "__main__":
    main()
