#!/usr/bin/env python3
"""build_dlc_oiv.py — package the full Hebrew global.gxt2 as a self-contained custom DLC
pack, mounted via the OpenIV mods folder and registered in dlclist.xml. This is the
research-backed fix for the story-mode hang: a DLC's global.gxt2 loads LAST (order 255),
overrides every base label hash, is a legitimate FULL-table layer (Rockstar's own
mpheist/mpbusiness do it), and never touches the integrity-sensitive x64/patch slot.

Builds two packages into the game folder:
  gtav_hebrew_DLC.oiv  — installs:
     * the DLC pack  mods\\update\\x64\\dlcpacks\\hebrew\\dlc.rpf
          ├─ setup2.xml  (deviceName dlc_hebrew, order 100, GROUP_STARTUP, COMPAT_PACK)
          ├─ content.xml (ONLY TEXTFILE_METAFILE dlctext.meta — the lang RPF is NOT
          │               registered as RPF_FILE; that double-mount was the no-mount+hang bug.
          │               It auto-loads via dlctext.meta hasGlobalTextFile=true. Verified vs BTTF.)
          ├─ common\\data\\dlctext.meta  (hasGlobalTextFile=true, isTitleUpdate=false)
          └─ x64\\data\\lang\\americandlc.rpf  ->  global.gxt2  (full Hebrew, 23,136; auto-discovered)
     * dlclist registration: <Item>dlcpacks:/hebrew/</Item> appended to
          update\\update.rpf\\common\\data\\dlclist.xml  (OpenIV decrypts/edits/re-encrypts)
     * REVERTS the hanging full table out of the wrong slots: x64b base -> vanilla,
          update x64/patch slot -> vanilla 351-string patch
     * (re)asserts the all-faces Hebrew fonts in update.rpf
  gtav_restore_DLC.oiv — removes the DLC: deletes dlc.rpf + removes the dlclist Item.
"""
import os, uuid, zipfile, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
GTAV = os.path.normpath(os.path.join(HERE, ".."))
ORIG = os.path.join(GTAV, "_originals")
FSRC = os.path.join(GTAV, "_fonts_src")
REL = os.path.join(GTAV, "release")
GAME = r"F:\Games\Grand Theft Auto V Legacy"

HE_GXT2 = os.path.join(HERE, "global_he.gxt2")                           # 1,511,573 Hebrew
OG_BASE = os.path.join(HERE, "_rpf", "global.gxt2")                      # 1,141,267 vanilla base
OG_PATCH = os.path.join(ORIG, "global_PATCH_vanilla_351entries.gxt2")    # 111,375 vanilla patch
HE_EFIGS = os.path.join(ORIG, "font_lib_efigs_HEBREW.gfx")               # all-faces generic
HE_PC = os.path.join(ORIG, "font_lib_efigs_pc_HEBREW.gfx")               # all-faces PC

# ---- DLC pack inner files ------------------------------------------------- #
DLCTEXT_META = '''<?xml version="1.0" encoding="UTF-8"?>
<CExtraTextMetaFile>
  <hasGlobalTextFile value="true"/>
  <hasAdditionalText value="false"/>
  <isTitleUpdate value="false"/>
</CExtraTextMetaFile>
'''

CONTENT_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<CDataFileMgr__ContentsOfDataFileXml>
  <disabledFiles/>
  <includedXmlFiles/>
  <includedDataFiles/>
  <dataFiles>
    <Item>
      <filename>dlc_hebrew:/common/data/dlctext.meta</filename>
      <fileType>TEXTFILE_METAFILE</fileType>
      <overlay value="false"/>
      <disabled value="true"/>
      <persistent value="false"/>
    </Item>
  </dataFiles>
  <contentChangeSets>
    <Item>
      <changeSetName>hebrew_AUTOGEN</changeSetName>
      <filesToEnable>
        <Item>dlc_hebrew:/common/data/dlctext.meta</Item>
      </filesToEnable>
      <txdToLoad/>
      <txdToUnload/>
      <residentResources/>
      <unregisterResources/>
    </Item>
  </contentChangeSets>
  <patchFiles/>
</CDataFileMgr__ContentsOfDataFileXml>
'''

SETUP2_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<SSetupData>
  <deviceName>dlc_hebrew</deviceName>
  <datFile>content.xml</datFile>
  <nameHash>hebrew</nameHash>
  <contentChangeSets/>
  <contentChangeSetGroups>
    <Item>
      <NameHash>GROUP_STARTUP</NameHash>
      <ContentChangeSets>
        <Item>hebrew_AUTOGEN</Item>
      </ContentChangeSets>
    </Item>
  </contentChangeSetGroups>
  <startupScript/>
  <scriptCallstackSize value="0"/>
  <type>EXTRACONTENT_COMPAT_PACK</type>
  <order value="100"/>
  <minorOrder value="0"/>
  <isLevelPack value="false"/>
  <dependencyPackHash/>
  <subPackCount value="0"/>
</SSetupData>
'''

INSTALL_ASM = '''<?xml version="1.0" encoding="utf-8"?>
<package version="2.2" id="%s" target="Five">
  <metadata>
    <name>GTA V Hebrew - DLC pack (full UI, mods folder)</name>
    <version><major>1</major><minor>0</minor></version>
    <author><displayName>Game Translator</displayName></author>
    <description><![CDATA[Installs the full Hebrew UI (23,136 strings) as a custom DLC pack (dlcpacks:/hebrew/, order 255), reverts the x64b base + update patch slots to vanilla, and asserts the Hebrew Scaleform fonts. Set the game language to American.]]></description>
  </metadata>
  <colors>
    <headerBackground useBlackTextColor="False">$FF1565C0</headerBackground>
    <iconBackground>$FF2E2E2E</iconBackground>
  </colors>
  <content>
    <archive path="update\\x64\\dlcpacks\\hebrew\\dlc.rpf" createIfNotExist="True" type="RPF7">
      <add source="setup2.xml">setup2.xml</add>
      <add source="content.xml">content.xml</add>
      <add source="dlctext.meta">common\\data\\dlctext.meta</add>
      <archive path="x64\\data\\lang\\americandlc.rpf" createIfNotExist="True" type="RPF7">
        <add source="global.gxt2">global.gxt2</add>
      </archive>
    </archive>
    <archive path="x64b.rpf" createIfNotExist="True" type="RPF7">
      <archive path="data\\lang\\american_rel.rpf" createIfNotExist="True" type="RPF7">
        <add source="global_vanilla.gxt2">global.gxt2</add>
      </archive>
    </archive>
    <archive path="update\\update.rpf" createIfNotExist="True" type="RPF7">
      <xml path="common\\data\\dlclist.xml">
        <add append="Last" xpath="/SMandatoryPacksData/Paths">
          <Item>dlcpacks:/hebrew/</Item>
        </add>
      </xml>
      <archive path="x64\\patch\\data\\lang\\american_rel.rpf" createIfNotExist="True" type="RPF7">
        <add source="global_patch_vanilla.gxt2">global.gxt2</add>
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

RESTORE_ASM = '''<?xml version="1.0" encoding="utf-8"?>
<package version="2.2" id="%s" target="Five">
  <metadata>
    <name>GTA V - REMOVE Hebrew DLC pack</name>
    <version><major>1</major><minor>0</minor></version>
    <author><displayName>Game Translator</displayName></author>
    <description><![CDATA[Removes the Hebrew DLC pack: deletes dlcpacks/hebrew/dlc.rpf and removes its dlclist entry. (Run gtav_restore_FULL.oiv too to put fonts back to vanilla.)]]></description>
  </metadata>
  <colors>
    <headerBackground useBlackTextColor="False">$FFB71C1C</headerBackground>
    <iconBackground>$FF2E2E2E</iconBackground>
  </colors>
  <content>
    <archive path="update\\update.rpf" createIfNotExist="True" type="RPF7">
      <xml path="common\\data\\dlclist.xml">
        <remove xpath="/SMandatoryPacksData/Paths/Item[contains(text(),'hebrew')]"/>
      </xml>
    </archive>
    <delete>update\\x64\\dlcpacks\\hebrew\\dlc.rpf</delete>
  </content>
</package>
'''


def build(fname, asm_tmpl, files):
    os.makedirs(REL, exist_ok=True)
    out = os.path.join(REL, fname)
    asm = asm_tmpl % ("{" + str(uuid.uuid4()).upper() + "}")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("assembly.xml", asm)
        for arc, data in files.items():
            if isinstance(data, str) and os.path.isfile(data):
                z.write(data, "content/" + arc)
            else:
                z.writestr("content/" + arc, data)
    shutil.copy2(out, os.path.join(GAME, fname))
    print("built", fname, os.path.getsize(out), "B -> game folder")


def main():
    build("gtav_hebrew_DLC.oiv", INSTALL_ASM, {
        "global.gxt2": HE_GXT2,
        "global_vanilla.gxt2": OG_BASE,
        "global_patch_vanilla.gxt2": OG_PATCH,
        "font_lib_efigs.gfx": HE_EFIGS,
        "font_lib_efigs_pc.gfx": HE_PC,
        "setup2.xml": SETUP2_XML,
        "content.xml": CONTENT_XML,
        "dlctext.meta": DLCTEXT_META,
    })
    build("gtav_restore_DLC.oiv", RESTORE_ASM, {})


if __name__ == "__main__":
    main()
