#!/usr/bin/env python3
"""build_full_oivs.py — build the two complete OpenIV packages:

  gtav_hebrew_FULL.oiv    — installs the WHOLE Hebrew mod:
        Hebrew global.gxt2  -> x64b.rpf\\data\\lang\\american_rel.rpf  (the BASE UI table)
        Hebrew font_lib_efigs.gfx     -> update.rpf x64\\data\\cdimages\\scaleform_generic.rpf
        Hebrew font_lib_efigs_pc.gfx  -> update.rpf x64\\data\\cdimages\\scaleform_platform_pc.rpf

  gtav_restore_FULL.oiv   — restores EVERYTHING to vanilla:
        original base global.gxt2  (1,141,267 B) -> x64b base slot
        original patch global.gxt2 (111,375 B)   -> update.rpf x64\\patch\\... slot
        original font_lib_efigs.gfx (96,789 B)    -> both scaleform_generic + platform_pc

Note: the original font_lib_efigs_pc.gfx was not separately backed up; the restore reuses
the original font_lib_efigs.gfx for the _pc slot too (the prior install used one identical
Hebrew font for both slots, and the original EFIGS font renders Latin cleanly). If a true
byte-perfect _pc revert is ever needed, extract the vanilla font_lib_efigs_pc.gfx and swap.
"""
import os, uuid, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ORIG = os.path.normpath(os.path.join(HERE, "..", "_originals"))
REL = os.path.normpath(os.path.join(HERE, "..", "release"))
GAME = r"F:\Games\Grand Theft Auto V Legacy"
GTAV_FONTS_PC = os.path.normpath(os.path.join(HERE, "..", "_fonts_src", "scaleform_platform_pc.rpf"))

HE_GXT2 = os.path.join(HERE, "global_he.gxt2")
HE_EFIGS = os.path.join(ORIG, "font_lib_efigs_HEBREW.gfx")
HE_PC = os.path.join(ORIG, "font_lib_efigs_pc_HEBREW.gfx")
OG_BASE = os.path.join(HERE, "_rpf", "global.gxt2")                     # 1,141,267
OG_PATCH = os.path.join(ORIG, "global_PATCH_vanilla_351entries.gxt2")   # 111,375
OG_EFIGS = os.path.join(ORIG, "font_lib_efigs_ORIGINAL.gfx")            # 96,789  (generic)
OG_PC = os.path.join(GTAV_FONTS_PC, "font_lib_efigs_pc.gfx")            # 232,883 (REAL vanilla PC)


def pkg(name, desc, color, files, content):
    """files: {arcname_in_zip: src_path}; content: the <content>...</content> XML."""
    guid = "{" + str(uuid.uuid4()).upper() + "}"
    asm = ('<?xml version="1.0" encoding="utf-8"?>\n'
           '<package version="2.2" id="' + guid + '" target="Five">\n'
           '  <metadata>\n'
           '    <name>' + name + '</name>\n'
           '    <version><major>1</major><minor>0</minor></version>\n'
           '    <author><displayName>Game Translator</displayName></author>\n'
           '    <description><![CDATA[' + desc + ']]></description>\n'
           '  </metadata>\n'
           '  <colors>\n'
           '    <headerBackground useBlackTextColor="False">' + color + '</headerBackground>\n'
           '    <iconBackground>$FF2E2E2E</iconBackground>\n'
           '  </colors>\n'
           + content +
           '</package>\n')
    out = os.path.join(REL, name_to_file[name])
    os.makedirs(REL, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("assembly.xml", asm)
        for arc, src in files.items():
            z.writestr("content/" + arc, open(src, "rb").read())
    import shutil
    shutil.copy2(out, os.path.join(GAME, name_to_file[name]))
    print("built", out, os.path.getsize(out), "bytes ->", name_to_file[name])


name_to_file = {
    "GTA V Hebrew - FULL (UI + Font)": "gtav_hebrew_FULL.oiv",
    "GTA V - RESTORE ORIGINAL (FULL: UI + Font)": "gtav_restore_FULL.oiv",
}

INSTALL_CONTENT = r'''  <content>
    <archive path="x64b.rpf" createIfNotExist="True" type="RPF7">
      <archive path="data\lang\american_rel.rpf" createIfNotExist="True" type="RPF7">
        <add source="global_vanilla.gxt2">global.gxt2</add>
      </archive>
    </archive>
    <archive path="update\update.rpf" createIfNotExist="True" type="RPF7">
      <archive path="x64\patch\data\lang\american_rel.rpf" createIfNotExist="True" type="RPF7">
        <add source="global.gxt2">global.gxt2</add>
      </archive>
      <archive path="x64\data\cdimages\scaleform_generic.rpf" createIfNotExist="True" type="RPF7">
        <add source="font_lib_efigs.gfx">font_lib_efigs.gfx</add>
      </archive>
      <archive path="x64\data\cdimages\scaleform_platform_pc.rpf" createIfNotExist="True" type="RPF7">
        <add source="font_lib_efigs_pc.gfx">font_lib_efigs_pc.gfx</add>
      </archive>
    </archive>
  </content>
'''

RESTORE_CONTENT = r'''  <content>
    <archive path="x64b.rpf" createIfNotExist="True" type="RPF7">
      <archive path="data\lang\american_rel.rpf" createIfNotExist="True" type="RPF7">
        <add source="global.gxt2">global.gxt2</add>
      </archive>
    </archive>
    <archive path="update\update.rpf" createIfNotExist="True" type="RPF7">
      <archive path="x64\patch\data\lang\american_rel.rpf" createIfNotExist="True" type="RPF7">
        <add source="global_patch.gxt2">global.gxt2</add>
      </archive>
      <archive path="x64\data\cdimages\scaleform_generic.rpf" createIfNotExist="True" type="RPF7">
        <add source="font_lib_efigs.gfx">font_lib_efigs.gfx</add>
      </archive>
      <archive path="x64\data\cdimages\scaleform_platform_pc.rpf" createIfNotExist="True" type="RPF7">
        <add source="font_lib_efigs_pc.gfx">font_lib_efigs_pc.gfx</add>
      </archive>
    </archive>
  </content>
'''


def main():
    pkg("GTA V Hebrew - FULL (UI + Font)",
        "Installs the COMPLETE Hebrew mod: the Hebrew UI translation (global.gxt2, 23,136 strings, visual RTL) into the base american_rel slot, PLUS the Hebrew Scaleform fonts. Keep the in-game language = American to see Hebrew.",
        "$FF1565C0",
        {"global.gxt2": HE_GXT2, "global_vanilla.gxt2": OG_BASE,
         "font_lib_efigs.gfx": HE_EFIGS, "font_lib_efigs_pc.gfx": HE_PC},
        INSTALL_CONTENT)
    pkg("GTA V - RESTORE ORIGINAL (FULL: UI + Font)",
        "Restores EVERYTHING to vanilla: the original base + patch global.gxt2 AND the original Scaleform fonts. Undoes the Hebrew mod completely.",
        "$FFB71C1C",
        {"global.gxt2": OG_BASE, "global_patch.gxt2": OG_PATCH,
         "font_lib_efigs.gfx": OG_EFIGS, "font_lib_efigs_pc.gfx": OG_PC},
        RESTORE_CONTENT)


if __name__ == "__main__":
    main()
