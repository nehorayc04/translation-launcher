#!/usr/bin/env python3
"""build_update2_oiv.py — THE fix, found via OpenIV.log.

OpenIV.log (real run, game v1.0.3788.0) proved the actual american_rel load order:
    openArchive 'update2:/x64/data/lang/american_rel.rpf'       <- the REAL base text layer
    openArchive 'update:/x64/patch/data/lang/american_rel.rpf'  <- the patch DELTA on top
The x64b base american_rel.rpf is SHADOWED by these title-update layers (that is why editing
x64b had zero effect — mods\\x64b IS read [openBulk '{M}'], but its american_rel is overridden).
The full base table the engine actually reads lives in update\\update2.rpf (494 MB, real file,
NG-encrypted — OpenIV decrypts/re-encrypts it). Putting the full 23,136 Hebrew table there =
the table loads ONCE as the base map (no delta-merge -> no story-load hang), and it is
mods-redirectable (OpenIV.asi shows '{M}' for mods\\update\\update2.rpf) -> NO anti-tamper.

gtav_hebrew_UPDATE2.oiv (install to the MODS folder) writes:
  * update\\update2.rpf  x64\\data\\lang\\american_rel.rpf\\global.gxt2  <- full Hebrew (23,136)  [BASE layer]
  * update\\update.rpf   x64\\patch\\data\\lang\\american_rel.rpf\\global.gxt2 <- vanilla 351 (clean delta)
  * x64b.rpf             data\\lang\\american_rel.rpf\\global.gxt2        <- vanilla base (shadowed; kept clean)
  * update\\update.rpf   x64\\data\\cdimages\\scaleform_generic.rpf\\font_lib_efigs.gfx      <- Hebrew font
  * update\\update.rpf   x64\\data\\cdimages\\scaleform_platform_pc.rpf\\font_lib_efigs_pc.gfx <- Hebrew font
  * removes the failed DLC: delete dlcpacks\\hebrew\\dlc.rpf + remove its dlclist Item

gtav_restore_UPDATE2.oiv reverts update2's american_rel to vanilla (needs the vanilla base
bytes; we ship the same vanilla base table the engine had — visually identical to stock).
"""
import os, uuid, zipfile, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
GTAV = os.path.normpath(os.path.join(HERE, ".."))
ORIG = os.path.join(GTAV, "_originals")
FSRC = os.path.join(GTAV, "_fonts_src")
REL = os.path.join(GTAV, "release")
GAME = r"F:\Games\Grand Theft Auto V Legacy"

HE_GXT2 = os.path.join(HERE, "global_he_super.gxt2")                    # 69,289 superset = update2-vanilla + our Hebrew (no blank rows)
OG_UPDATE2 = os.path.join(FSRC, "american_rel.rpf", "global.gxt2")      # 3,748,484 / 69,209 keys — the REAL update2 vanilla (restore target!)
OG_BASE = os.path.join(HERE, "_rpf", "global.gxt2")                     # 1,141,267 / 23,136 — x64b vanilla base
OG_PATCH = os.path.join(ORIG, "global_PATCH_vanilla_351entries.gxt2")   # 111,375 vanilla patch
HE_EFIGS = os.path.join(ORIG, "font_lib_efigs_HEBREW.gfx")
HE_PC = os.path.join(ORIG, "font_lib_efigs_pc_HEBREW.gfx")
HE_WEB = os.path.join(ORIG, "font_lib_web_HEBREW.gfx")             # in-game browser font (eyefind)
# vanilla fonts (for byte-exact restore) — from the user's OpenIV export
VAN_EFIGS = os.path.join(FSRC, "scaleform_generic.rpf", "font_lib_efigs.gfx")
VAN_PC = os.path.join(FSRC, "scaleform_platform_pc.rpf", "font_lib_efigs_pc.gfx")
VAN_WEB = os.path.join(FSRC, "scaleform_generic.rpf", "font_lib_web.gfx")

INSTALL_ASM = '''<?xml version="1.0" encoding="utf-8"?>
<package version="2.2" id="%s" target="Five">
  <metadata>
    <name>GTA V Hebrew - update2 BASE layer (full UI, mods folder)</name>
    <version><major>1</major><minor>0</minor></version>
    <author><displayName>Game Translator</displayName></author>
    <description><![CDATA[Full Hebrew UI (23,136) written into the REAL base text layer update2.rpf (x64/data/lang/american_rel.rpf) that the engine actually reads -> no story-load hang. Clean vanilla patch slot + Hebrew fonts. Removes the failed Hebrew DLC pack. INSTALL TO THE MODS FOLDER. Set the game language to American.]]></description>
  </metadata>
  <colors>
    <headerBackground useBlackTextColor="False">$FF1565C0</headerBackground>
    <iconBackground>$FF2E2E2E</iconBackground>
  </colors>
  <content>
    <archive path="update\\update2.rpf" createIfNotExist="True" type="RPF7">
      <archive path="x64\\data\\lang\\american_rel.rpf" createIfNotExist="True" type="RPF7">
        <add source="global_he.gxt2">global.gxt2</add>
      </archive>
    </archive>
    <archive path="x64b.rpf" createIfNotExist="True" type="RPF7">
      <archive path="data\\lang\\american_rel.rpf" createIfNotExist="True" type="RPF7">
        <add source="global_base_vanilla.gxt2">global.gxt2</add>
      </archive>
    </archive>
    <archive path="update\\update.rpf" createIfNotExist="True" type="RPF7">
      <xml path="common\\data\\dlclist.xml">
        <remove xpath="/SMandatoryPacksData/Paths/Item[contains(text(),'hebrew')]"/>
      </xml>
      <archive path="x64\\patch\\data\\lang\\american_rel.rpf" createIfNotExist="True" type="RPF7">
        <add source="global_patch_vanilla.gxt2">global.gxt2</add>
      </archive>
      <archive path="x64\\data\\cdimages\\scaleform_generic.rpf" createIfNotExist="True" type="RPF7">
        <add source="font_lib_efigs.gfx">font_lib_efigs.gfx</add>
        <add source="font_lib_web.gfx">font_lib_web.gfx</add>
      </archive>
      <archive path="x64\\data\\cdimages\\scaleform_platform_pc.rpf" createIfNotExist="True" type="RPF7">
        <add source="font_lib_efigs_pc.gfx">font_lib_efigs_pc.gfx</add>
      </archive>
    </archive>
    <delete>update\\x64\\dlcpacks\\hebrew\\dlc.rpf</delete>
  </content>
</package>
'''

RESTORE_ASM = '''<?xml version="1.0" encoding="utf-8"?>
<package version="2.2" id="%s" target="Five">
  <metadata>
    <name>GTA V - RESTORE vanilla (exact, mod-safe)</name>
    <version><major>1</major><minor>0</minor></version>
    <author><displayName>Game Translator</displayName></author>
    <description><![CDATA[Reverts ONLY the files this Hebrew mod touched (the american_rel global.gxt2 in update2/x64b/patch + the 3 Scaleform fonts) back to byte-exact vanilla. Other mods in the same archives are untouched (file-level revert, no archive deletion). INSTALL TO THE MODS FOLDER.]]></description>
  </metadata>
  <colors>
    <headerBackground useBlackTextColor="False">$FFB71C1C</headerBackground>
    <iconBackground>$FF2E2E2E</iconBackground>
  </colors>
  <content>
    <archive path="update\\update2.rpf" createIfNotExist="True" type="RPF7">
      <archive path="x64\\data\\lang\\american_rel.rpf" createIfNotExist="True" type="RPF7">
        <add source="global_update2_vanilla.gxt2">global.gxt2</add>
      </archive>
    </archive>
    <archive path="x64b.rpf" createIfNotExist="True" type="RPF7">
      <archive path="data\\lang\\american_rel.rpf" createIfNotExist="True" type="RPF7">
        <add source="global_base_vanilla.gxt2">global.gxt2</add>
      </archive>
    </archive>
    <archive path="update\\update.rpf" createIfNotExist="True" type="RPF7">
      <archive path="x64\\patch\\data\\lang\\american_rel.rpf" createIfNotExist="True" type="RPF7">
        <add source="global_patch_vanilla.gxt2">global.gxt2</add>
      </archive>
      <archive path="x64\\data\\cdimages\\scaleform_generic.rpf" createIfNotExist="True" type="RPF7">
        <add source="font_lib_efigs.gfx">font_lib_efigs.gfx</add>
        <add source="font_lib_web.gfx">font_lib_web.gfx</add>
      </archive>
      <archive path="x64\\data\\cdimages\\scaleform_platform_pc.rpf" createIfNotExist="True" type="RPF7">
        <add source="font_lib_efigs_pc.gfx">font_lib_efigs_pc.gfx</add>
      </archive>
    </archive>
  </content>
</package>
'''


def build(fname, asm_tmpl, files):
    os.makedirs(REL, exist_ok=True)
    out = os.path.join(REL, fname)
    asm = asm_tmpl % ("{" + str(uuid.uuid4()).upper() + "}")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("assembly.xml", asm)
        for arc, src in files.items():
            z.write(src, "content/" + arc)
    shutil.copy2(out, os.path.join(GAME, fname))
    print("built", fname, os.path.getsize(out), "B -> game folder")


def main():
    build("gtav_hebrew_UPDATE2.oiv", INSTALL_ASM, {
        "global_he.gxt2": HE_GXT2,
        "global_base_vanilla.gxt2": OG_BASE,
        "global_patch_vanilla.gxt2": OG_PATCH,
        "font_lib_efigs.gfx": HE_EFIGS,
        "font_lib_efigs_pc.gfx": HE_PC,
        "font_lib_web.gfx": HE_WEB,
    })
    build("gtav_restore_UPDATE2.oiv", RESTORE_ASM, {
        "global_update2_vanilla.gxt2": OG_UPDATE2,   # 69,209 — THE correct update2 vanilla (was wrongly OG_BASE)
        "global_base_vanilla.gxt2": OG_BASE,         # 23,136 — x64b vanilla
        "global_patch_vanilla.gxt2": OG_PATCH,       # 351 — patch vanilla
        "font_lib_efigs.gfx": VAN_EFIGS,
        "font_lib_efigs_pc.gfx": VAN_PC,
        "font_lib_web.gfx": VAN_WEB,
    })


if __name__ == "__main__":
    main()
