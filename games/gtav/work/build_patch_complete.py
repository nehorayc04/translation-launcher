#!/usr/bin/env python3
"""build_patch_complete.py — the SUPERSET-patch fix for the story-mode hang.

Root cause (new): the vanilla x64/patch slot's global.gxt2 = 351 keys, of which ~325 are
NEW DLC keys (vehicle/brand descriptions) that DO NOT exist in the base table. When we put
ONLY our 23,136 base-derived Hebrew table into that slot, those 325 DLC keys VANISH from
the patch layer — and the game reads them at world-init (owned vehicles / store) → missing
key → "Not Responding" on Story load. (The menu renders because it doesn't touch the DLC
vehicle keys.)

Fix: ship a patch global.gxt2 that is a SUPERSET — our full 23,136 Hebrew table UNION the
original 351 patch keys (the ~325 DLC-only keys kept in their vanilla English bytes; our
Hebrew wins on the ~26 that overlap the base). Nothing the engine expects is missing, and
the UI is Hebrew. Hash-sorted, no-dedup, monotonic via the proven write_gxt2.

Also emits gtav_hebrew_PATCH.oiv which:
  * deploys the superset patch -> update.rpf\\x64\\patch\\data\\lang\\american_rel.rpf
  * REMOVES the broken DLC (delete dlcpacks\\hebrew\\dlc.rpf + remove its dlclist Item)
  * keeps x64b base vanilla + the all-faces Hebrew fonts
"""
import os, sys, uuid, zipfile, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gtav_gxt2 as G

GTAV = os.path.normpath(os.path.join(HERE, ".."))
ORIG = os.path.join(GTAV, "_originals")
REL = os.path.join(GTAV, "release")
GAME = r"F:\Games\Grand Theft Auto V Legacy"
HE_GXT2 = os.path.join(HERE, "global_he.gxt2")
OG_PATCH = os.path.join(ORIG, "global_PATCH_vanilla_351entries.gxt2")
HE_EFIGS = os.path.join(ORIG, "font_lib_efigs_HEBREW.gfx")
HE_PC = os.path.join(ORIG, "font_lib_efigs_pc_HEBREW.gfx")


def build_superset():
    he = G.read_gxt2(open(HE_GXT2, "rb").read())          # 23,136 visual Hebrew
    patch = G.read_gxt2(open(OG_PATCH, "rb").read())       # 351 vanilla (325 DLC-only)
    merged = dict(patch)        # start with the 351 (so all DLC keys present)
    merged.update(he)           # our Hebrew wins on every base key (incl the 26 overlaps)
    added = sum(1 for k in patch if k not in he)
    blob = G.write_gxt2(merged)
    out = os.path.join(HERE, "global_patch_complete.gxt2")
    open(out, "wb").write(blob)
    # verify round-trip + that DLC-only keys survived
    rb = G.read_gxt2(blob)
    assert all(rb.get(k) == patch[k] for k in patch if k not in he), "DLC key lost"
    assert all(rb.get(k) == he[k] for k in he), "Hebrew key lost"
    print(f"superset patch: {len(merged)} keys ({len(he)} Hebrew + {added} vanilla DLC), {len(blob)} B -> {out}")
    return out


ASM = '''<?xml version="1.0" encoding="utf-8"?>
<package version="2.2" id="%s" target="Five">
  <metadata>
    <name>GTA V Hebrew - complete patch (superset, no DLC pack)</name>
    <version><major>1</major><minor>0</minor></version>
    <author><displayName>Game Translator</displayName></author>
    <description><![CDATA[Hebrew UI via a SUPERSET patch (23,136 Hebrew + the 325 vanilla DLC keys, so nothing is missing -> no story-load hang). Removes the broken Hebrew DLC pack. Keeps the Hebrew fonts. Set the game language to American.]]></description>
  </metadata>
  <colors>
    <headerBackground useBlackTextColor="False">$FF1565C0</headerBackground>
    <iconBackground>$FF2E2E2E</iconBackground>
  </colors>
  <content>
    <delete>update\\x64\\dlcpacks\\hebrew\\dlc.rpf</delete>
    <archive path="update\\update.rpf" createIfNotExist="True" type="RPF7">
      <xml path="common\\data\\dlclist.xml">
        <remove xpath="/SMandatoryPacksData/Paths/Item[contains(text(),'hebrew')]"/>
      </xml>
      <archive path="x64\\patch\\data\\lang\\american_rel.rpf" createIfNotExist="True" type="RPF7">
        <add source="global_patch_complete.gxt2">global.gxt2</add>
      </archive>
      <archive path="x64\\data\\cdimages\\scaleform_generic.rpf" createIfNotExist="True" type="RPF7">
        <add source="font_lib_efigs.gfx">font_lib_efigs.gfx</add>
      </archive>
      <archive path="x64\\data\\cdimages\\scaleform_platform_pc.rpf" createIfNotExist="True" type="RPF7">
        <add source="font_lib_efigs_pc.gfx">font_lib_efigs_pc.gfx</add>
      </archive>
    </archive>
  </content>
</package>
'''


def main():
    patch = build_superset()
    os.makedirs(REL, exist_ok=True)
    out = os.path.join(REL, "gtav_hebrew_PATCH.oiv")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("assembly.xml", ASM % ("{" + str(uuid.uuid4()).upper() + "}"))
        z.write(patch, "content/global_patch_complete.gxt2")
        z.write(HE_EFIGS, "content/font_lib_efigs.gfx")
        z.write(HE_PC, "content/font_lib_efigs_pc.gfx")
    shutil.copy2(out, os.path.join(GAME, "gtav_hebrew_PATCH.oiv"))
    print("built gtav_hebrew_PATCH.oiv", os.path.getsize(out), "B -> game folder")


if __name__ == "__main__":
    main()
