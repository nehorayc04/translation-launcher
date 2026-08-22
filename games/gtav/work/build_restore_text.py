#!/usr/bin/env python3
"""build_restore_text.py — TEXT-ONLY restore OIV (vanilla gxt2 in BOTH slots, no fonts).

Restores the vanilla global.gxt2 in both the BASE (x64b) and PATCH (update) slots, so it
undoes every Hebrew gxt2 deploy. Touches NO fonts, so it can be combined with an OpenIV
"Uninstall Menyoo_Hebrew_Font.oiv" (which restores the true original fonts) without
conflict. Output: release/gtav_restore_TEXT.oiv.
"""
import os, uuid, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ORIG = os.path.normpath(os.path.join(HERE, "..", "_originals"))
REL = os.path.normpath(os.path.join(HERE, "..", "release"))
GAME = r"F:\Games\Grand Theft Auto V Legacy"
OG_BASE = os.path.join(HERE, "_rpf", "global.gxt2")                    # 1,141,267
OG_PATCH = os.path.join(ORIG, "global_PATCH_vanilla_351entries.gxt2")  # 111,375
GUID = "{" + str(uuid.uuid4()).upper() + "}"

ASSEMBLY = r'''<?xml version="1.0" encoding="utf-8"?>
<package version="2.2" id="%s" target="Five">
  <metadata>
    <name>GTA V - RESTORE vanilla TEXT only (gxt2 base + patch)</name>
    <version>
      <major>1</major>
      <minor>0</minor>
    </version>
    <author>
      <displayName>Game Translator</displayName>
    </author>
    <description><![CDATA[Restores the vanilla global.gxt2 in BOTH the base (x64b) and patch (update) slots. No fonts touched - uninstall Menyoo_Hebrew_Font.oiv separately for the fonts.]]></description>
  </metadata>
  <colors>
    <headerBackground useBlackTextColor="False">$FFB71C1C</headerBackground>
    <iconBackground>$FF2E2E2E</iconBackground>
  </colors>
  <content>
    <archive path="x64b.rpf" createIfNotExist="True" type="RPF7">
      <archive path="data\lang\american_rel.rpf" createIfNotExist="True" type="RPF7">
        <add source="global.gxt2">global.gxt2</add>
      </archive>
    </archive>
    <archive path="update\update.rpf" createIfNotExist="True" type="RPF7">
      <archive path="x64\patch\data\lang\american_rel.rpf" createIfNotExist="True" type="RPF7">
        <add source="global_patch.gxt2">global.gxt2</add>
      </archive>
    </archive>
  </content>
</package>
''' % GUID


def main():
    os.makedirs(REL, exist_ok=True)
    out = os.path.join(REL, "gtav_restore_TEXT.oiv")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("assembly.xml", ASSEMBLY)
        z.writestr("content/global.gxt2", open(OG_BASE, "rb").read())
        z.writestr("content/global_patch.gxt2", open(OG_PATCH, "rb").read())
    import shutil
    shutil.copy2(out, os.path.join(GAME, "gtav_restore_TEXT.oiv"))
    print("built", out, os.path.getsize(out), "bytes -> game folder")


if __name__ == "__main__":
    main()
