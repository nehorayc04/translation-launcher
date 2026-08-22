#!/usr/bin/env python3
"""build_oiv.py — package the Hebrew global.gxt2 into an OpenIV .oiv installer.

Output: games/gtav/release/gtav_hebrew_ui.oiv  (a ZIP: assembly.xml + content/global.gxt2)
Install: open it in OpenIV -> Install (Package installer). OpenIV edits the nested
american_rel.rpf inside update.rpf and creates the safe mods/ override automatically —
exactly like the Hebrew font OIV. Reversible via OpenIV (Uninstall). Keep the in-game
language = American to see Hebrew. The Hebrew Scaleform font must already be installed.
"""
import os, uuid, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
GXT2 = os.path.join(HERE, "global_he.gxt2")
OUT = os.path.normpath(os.path.join(HERE, "..", "release", "gtav_hebrew_ui.oiv"))

GUID = "{" + str(uuid.uuid4()).upper() + "}"

ASSEMBLY = r'''<?xml version="1.0" encoding="utf-8"?>
<package version="2.2" id="%s" target="Five">
  <metadata>
    <name>GTA V Hebrew UI Translation</name>
    <version>
      <major>1</major>
      <minor>0</minor>
    </version>
    <author>
      <displayName>Game Translator</displayName>
    </author>
    <description><![CDATA[Installs the Hebrew translation of the GTA V interface (global.gxt2, American/English slot). 23,136 UI strings in visual RTL order. Keep the in-game language = American to see Hebrew. Requires the Hebrew Scaleform font (font_lib_efigs.gfx) to be installed (Menyoo_Hebrew_Font.oiv).]]></description>
  </metadata>
  <colors>
    <headerBackground useBlackTextColor="False">$FF1565C0</headerBackground>
    <iconBackground>$FF2E2E2E</iconBackground>
  </colors>
  <content>
    <archive path="x64b.rpf" createIfNotExist="True" type="RPF7">
      <archive path="data\lang\american_rel.rpf" createIfNotExist="True" type="RPF7">
        <add source="global.gxt2">global.gxt2</add>
      </archive>
    </archive>
  </content>
</package>
''' % GUID


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    data = open(GXT2, "rb").read()
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("assembly.xml", ASSEMBLY)
        z.writestr("content/global.gxt2", data)
    print("built", OUT, os.path.getsize(OUT), "bytes")
    print("guid", GUID, "| gxt2", len(data), "bytes")
    with zipfile.ZipFile(OUT) as z:
        print("contents:", z.namelist())


if __name__ == "__main__":
    main()
