#!/usr/bin/env python3
"""build_restore_patch.py — OIV that restores the TRUE vanilla PATCH global.gxt2.

The user extracted the genuine vanilla of update.rpf\\x64\\patch\\data\\lang\\
american_rel.rpf\\global.gxt2 = 111,375 bytes / 351 strings (md5 ebddedec...). The
earlier Hebrew mod wrongly wrote a FULL 23,136-entry table into this small patch slot
-> crash; and the first "restore" used the wrong base file. This OIV puts the genuine
351-string patch vanilla back into the exact patch slot. Output:
release/gtav_restore_patch_vanilla.oiv.
"""
import os, uuid, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "_originals",
                                    "global_PATCH_vanilla_351entries.gxt2"))
OUT = os.path.normpath(os.path.join(HERE, "..", "release",
                                    "gtav_restore_patch_vanilla.oiv"))
GUID = "{" + str(uuid.uuid4()).upper() + "}"

ASSEMBLY = r'''<?xml version="1.0" encoding="utf-8"?>
<package version="2.2" id="%s" target="Five">
  <metadata>
    <name>GTA V - RESTORE TRUE patch vanilla global.gxt2 (351 strings)</name>
    <version>
      <major>1</major>
      <minor>1</minor>
    </version>
    <author>
      <displayName>Game Translator</displayName>
    </author>
    <description><![CDATA[Restores the GENUINE vanilla patch global.gxt2 (111375 bytes / 351 strings, md5 ebddedec5ced9aff678d871f8e549109) into update.rpf x64/patch/data/lang/american_rel.rpf. Undoes the wrongly-deployed full Hebrew table in this slot.]]></description>
  </metadata>
  <colors>
    <headerBackground useBlackTextColor="False">$FFB71C1C</headerBackground>
    <iconBackground>$FF2E2E2E</iconBackground>
  </colors>
  <content>
    <archive path="update\update.rpf" createIfNotExist="True" type="RPF7">
      <archive path="x64\patch\data\lang\american_rel.rpf" createIfNotExist="True" type="RPF7">
        <add source="global.gxt2">global.gxt2</add>
      </archive>
    </archive>
  </content>
</package>
''' % GUID


def main():
    data = open(SRC, "rb").read()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("assembly.xml", ASSEMBLY)
        z.writestr("content/global.gxt2", data)
    print("built", OUT, os.path.getsize(OUT), "bytes | vanilla", len(data), "bytes")


if __name__ == "__main__":
    main()
