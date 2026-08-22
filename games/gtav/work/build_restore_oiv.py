#!/usr/bin/env python3
"""build_restore_oiv.py — OIV that RESTORES the original English global.gxt2.

Packages the pristine extracted original (work/_rpf/global.gxt2) into an .oiv that
re-installs it over our Hebrew one at the same nested path. Run it in OpenIV ->
Install to revert the UI to English. Output: release/gtav_restore_original.oiv.
"""
import os, uuid, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ORIG = os.path.join(HERE, "_rpf", "global.gxt2")          # the pristine original
OUT = os.path.normpath(os.path.join(HERE, "..", "release", "gtav_restore_original.oiv"))
GUID = "{" + str(uuid.uuid4()).upper() + "}"

ASSEMBLY = r'''<?xml version="1.0" encoding="utf-8"?>
<package version="2.2" id="%s" target="Five">
  <metadata>
    <name>GTA V Hebrew UI - RESTORE ORIGINAL (English)</name>
    <version>
      <major>1</major>
      <minor>0</minor>
    </version>
    <author>
      <displayName>Game Translator</displayName>
    </author>
    <description><![CDATA[Reverts the GTA V interface back to the ORIGINAL English global.gxt2 (undoes the Hebrew UI translation). Install this in OpenIV to restore vanilla text.]]></description>
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
    if not os.path.exists(ORIG):
        raise SystemExit("original not found: " + ORIG)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    data = open(ORIG, "rb").read()
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("assembly.xml", ASSEMBLY)
        z.writestr("content/global.gxt2", data)
    print("built", OUT, os.path.getsize(OUT), "bytes | original gxt2", len(data), "bytes")


if __name__ == "__main__":
    main()
