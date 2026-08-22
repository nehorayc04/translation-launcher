#!/usr/bin/env python3
"""build_diag.py — a single, information-dense diagnostic OpenIV package that answers
BOTH open questions in ONE in-game screenshot, plus a TRUE byte-perfect restore.

gtav_DIAG.oiv installs:
  * a DIAG global.gxt2 into the BASE slot (x64b.rpf\\data\\lang\\american_rel.rpf) where
    6 pause-menu TAB labels are overwritten:
      - 3 with Latin ASCII markers  (ZZBRIEF / ZZSTATS / ZZGAME)  -> font-independent;
        if these appear, the BASE gxt2 slot reaches the UI (the gxt2 pipeline works).
      - 3 with VISUAL Hebrew         (Map=מפה / Settings=הגדרות / Friends=חברים)        ->
        if these render as Hebrew (not boxes) the Hebrew PC font ($Font2) works.
  * the Hebrew Scaleform fonts (generic + the transplanted PC font) into update.rpf.

Reading the one screenshot:
  ZZ markers visible            -> BASE gxt2 slot OK
  Hebrew tabs readable          -> PC Hebrew font OK  -> ship the full mod
  Hebrew tabs = boxes (tofu)    -> font still broken  -> debug the font only
  ALL English (no ZZ, no Hebrew)-> BASE slot is NOT the runtime source -> fix the slot

gtav_restore_FULL.oiv restores the TRUE vanilla files now that the real vanilla PC font
(232,883 B) is available — base+patch gxt2 AND both original fonts, byte-perfect.
"""
import os, sys, uuid, zipfile, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gtav_gxt2 as G

GTAV = os.path.normpath(os.path.join(HERE, ".."))
ORIG = os.path.join(GTAV, "_originals")
FSRC = os.path.join(GTAV, "_fonts_src")
REL = os.path.join(GTAV, "release")
GAME = r"F:\Games\Grand Theft Auto V Legacy"

# --- vanilla sources -------------------------------------------------------- #
OG_BASE = os.path.join(HERE, "_rpf", "global.gxt2")                       # 1,141,267
OG_PATCH = os.path.join(ORIG, "global_PATCH_vanilla_351entries.gxt2")     # 111,375
VAN_EFIGS = os.path.join(FSRC, "scaleform_generic.rpf", "font_lib_efigs.gfx")        # 96,789
VAN_PC = os.path.join(FSRC, "scaleform_platform_pc.rpf", "font_lib_efigs_pc.gfx")    # 232,883 (REAL vanilla PC)
# --- hebrew sources --------------------------------------------------------- #
HE_EFIGS = os.path.join(ORIG, "font_lib_efigs_HEBREW.gfx")               # 711,440
HE_PC = os.path.join(ORIG, "font_lib_efigs_pc_HEBREW.gfx")               # 824,331

# pause-menu tab keys (joaat of label) -> diagnostic replacement
LATIN = {0x02870b64: "ZZBRIEF", 0x45e667e0: "ZZSTATS", 0x37831771: "ZZGAME"}
HEBREW = {0x159c888e: "מפה", 0x324241d9: "הגדרות", 0x036fffa1: "חברים"}


def build_diag_gxt2():
    d = G.read_gxt2(open(OG_BASE, "rb").read())
    assert len(d) == 23136, len(d)
    for k, v in LATIN.items():
        d[k] = v
    for k, v in HEBREW.items():
        d[k] = G.visual_line(v)            # store VISUAL (non-bidi engine)
    blob = G.write_gxt2(d)
    # self-check: round-trips + markers present
    rb = G.read_gxt2(blob)
    for k, v in LATIN.items():
        assert rb[k] == v, (hex(k), rb[k])
    for k, v in HEBREW.items():
        assert rb[k] == G.visual_line(v)
    out = os.path.join(HERE, "global_diag.gxt2")
    open(out, "wb").write(blob)
    print("diag gxt2:", out, len(blob), "B  (markers:",
          ", ".join(LATIN.values()), "| hebrew:", ", ".join(HEBREW.values()), ")")
    return out


def asm(name, desc, color, content):
    guid = "{" + str(uuid.uuid4()).upper() + "}"
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            '<package version="2.2" id="' + guid + '" target="Five">\n'
            '  <metadata>\n    <name>' + name + '</name>\n'
            '    <version><major>1</major><minor>0</minor></version>\n'
            '    <author><displayName>Game Translator</displayName></author>\n'
            '    <description><![CDATA[' + desc + ']]></description>\n  </metadata>\n'
            '  <colors>\n    <headerBackground useBlackTextColor="False">' + color + '</headerBackground>\n'
            '    <iconBackground>$FF2E2E2E</iconBackground>\n  </colors>\n' + content + '</package>\n')


def pkg(fname, assembly, files):
    os.makedirs(REL, exist_ok=True)
    out = os.path.join(REL, fname)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("assembly.xml", assembly)
        for arc, src in files.items():
            z.writestr("content/" + arc, open(src, "rb").read())
    shutil.copy2(out, os.path.join(GAME, fname))
    print("built", fname, os.path.getsize(out), "B -> game folder")


DIAG_CONTENT = r'''  <content>
    <archive path="x64b.rpf" createIfNotExist="True" type="RPF7">
      <archive path="data\lang\american_rel.rpf" createIfNotExist="True" type="RPF7">
        <add source="global.gxt2">global.gxt2</add>
      </archive>
    </archive>
    <archive path="update\update.rpf" createIfNotExist="True" type="RPF7">
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
    diag = build_diag_gxt2()
    pkg("gtav_DIAG.oiv",
        asm("GTA V - DIAGNOSTIC (tab markers + Hebrew font)",
            "Overwrites 6 pause-menu tab labels: 3 Latin markers (ZZBRIEF/ZZSTATS/ZZGAME) "
            "and 3 visual-Hebrew (Map/Settings/Friends), plus the Hebrew fonts. One screenshot "
            "tells if the base gxt2 slot works and if the Hebrew PC font renders.",
            "$FF6A1B9A", DIAG_CONTENT),
        {"global.gxt2": diag, "font_lib_efigs.gfx": HE_EFIGS, "font_lib_efigs_pc.gfx": HE_PC})
    pkg("gtav_restore_FULL.oiv",
        asm("GTA V - RESTORE ORIGINAL (true vanilla: UI + both fonts)",
            "Restores byte-perfect vanilla: base + patch global.gxt2 AND the ORIGINAL "
            "font_lib_efigs.gfx (96,789 B) + font_lib_efigs_pc.gfx (232,883 B). Full undo.",
            "$FFB71C1C", RESTORE_CONTENT),
        {"global.gxt2": OG_BASE, "global_patch.gxt2": OG_PATCH,
         "font_lib_efigs.gfx": VAN_EFIGS, "font_lib_efigs_pc.gfx": VAN_PC})


if __name__ == "__main__":
    main()
