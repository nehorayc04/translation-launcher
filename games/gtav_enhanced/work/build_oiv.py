#!/usr/bin/env python3
"""build_oiv.py - assemble the OpenIV install/restore packages for GTA V **Enhanced**.

OIV 2.2 format, exactly as OpenIV accepts it (copied from the proven Legacy packages in
games/gtav/release/*.oiv, after OpenIV rejected a first attempt):

  * the archive action is **`<add source="FLAT">target.ext</add>`** - `<replace>` is NOT a
    valid action and OpenIV logs `Unknown archive action at node: content>archive>archive>replace`
    then installs **nothing**, while still reporting success.
  * `<archive path=...>` uses **backslashes**.
  * `createIfNotExist="True"`.
  * `source` is a FLAT name inside the zip's `content/` folder - no sub-directories.

Both tables (`update.rpf` and `update2.rpf`) hold a byte-identical `american_rel.rpf`, so
the 610 payload files are stored **once** and referenced from both archive blocks.

    python work/build_oiv.py
"""
import argparse
import os
import sys
import uuid
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

EXTRACT = os.path.join(ROOT, "extract")
BUILD = os.path.join(ROOT, "build")
RELEASE = os.path.join(ROOT, "release")
AUTHOR = "Hebrew Translation Hub"

# Verified on this install 2026-08-02. `american_rel.rpf` is byte-identical in both outer
# archives (md5 06e01d53..., 611 entries); load order decides which wins, so both are patched.
LANG_INNER = r"x64\data\lang\american_rel.rpf"
FONT_INNERS = [
    (r"x64\data\cdimages\scaleform_platform_pc.rpf", "font_lib_efigs_pc.gfx"),
    (r"x64\data\cdimages\scaleform_generic.rpf", "font_lib_efigs.gfx"),
]
# outer archive -> does it carry the language table / the fonts
OUTER = [
    (r"update\update2.rpf", True, False),
    (r"update\update.rpf", True, True),
]


def gxt2_source_dir(hebrew):
    """The 610 gxt2 to ship. Both tables are identical, so one directory serves both."""
    base = BUILD if hebrew else os.path.join(EXTRACT, "vanilla")
    for tag in ("update2", "update"):
        d = os.path.join(base, tag, LANG_INNER.replace("\\", "__"))
        if os.path.isdir(d) and any(f.endswith(".gxt2") for f in os.listdir(d)):
            return d
    return None


def build_content(hebrew):
    """-> (content xml, {flat_arcname: src_path})"""
    gdir = gxt2_source_dir(hebrew)
    if not gdir:
        return None, None
    names = sorted(f for f in os.listdir(gdir) if f.lower().endswith(".gxt2"))
    fdir = os.path.join(BUILD, "fonts") if hebrew else os.path.join(EXTRACT, "fonts")

    files = {f"al_{n}": os.path.join(gdir, n) for n in names}
    lang_adds = "\n".join(
        f'        <add source="al_{n}">{n}</add>' for n in names)

    blocks = []
    for arch, has_lang, has_fonts in OUTER:
        inner = []
        if has_lang:
            inner.append(
                f'      <archive path="{LANG_INNER}" createIfNotExist="True" type="RPF7">\n'
                f'{lang_adds}\n'
                f'      </archive>')
        if has_fonts:
            for inner_path, fname in FONT_INNERS:
                src = os.path.join(fdir, fname)
                if not os.path.isfile(src):
                    continue
                files[f"f_{fname}"] = src
                inner.append(
                    f'      <archive path="{inner_path}" createIfNotExist="True" type="RPF7">\n'
                    f'        <add source="f_{fname}">{fname}</add>\n'
                    f'      </archive>')
        if inner:
            blocks.append(
                f'    <archive path="{arch}" createIfNotExist="True" type="RPF7">\n'
                + "\n".join(inner) + "\n    </archive>")

    return "  <content>\n" + "\n".join(blocks) + "\n  </content>\n", files


def pkg(out_path, name, desc, color, content_xml, files):
    guid = "{" + str(uuid.uuid4()).upper() + "}"
    asm = ('<?xml version="1.0" encoding="utf-8"?>\n'
           f'<package version="2.2" id="{guid}" target="Five">\n'
           '  <metadata>\n'
           f'    <name>{name}</name>\n'
           '    <version><major>1</major><minor>0</minor></version>\n'
           f'    <author><displayName>{AUTHOR}</displayName></author>\n'
           f'    <description footerLink="https://hebrew-translation-hub.com" '
           f'footerLinkTitle="Hebrew Translation Hub"><![CDATA[{desc}]]></description>\n'
           '  </metadata>\n'
           '  <colors>\n'
           f'    <headerBackground useBlackTextColor="False">{color}</headerBackground>\n'
           '    <iconBackground>$FF2E2E2E</iconBackground>\n'
           '  </colors>\n'
           + content_xml +
           '</package>\n')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("assembly.xml", asm)
        for arc, src in files.items():
            z.write(src, "content/" + arc)
    print(f"  {os.path.basename(out_path):<34} {os.path.getsize(out_path):>12,} B  "
          f"({len(files)} payload files, {asm.count('<add ')} adds)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=RELEASE)
    a = ap.parse_args()

    if not os.path.isdir(BUILD):
        print("NO build/ - run work/build_hebrew.py first.")
        return 2

    inst_xml, inst_files = build_content(hebrew=True)
    rest_xml, rest_files = build_content(hebrew=False)
    if not inst_files:
        print("nothing to package - build/ has no gxt2.")
        return 1

    pkg(os.path.join(a.out, "gtav_enhanced_hebrew.oiv"),
        "GTA V Enhanced - Hebrew",
        "Hebrew translation for Grand Theft Auto V Enhanced.\n"
        "Installs into the mods\\ folder - the original game files stay untouched.\n"
        "Requires OpenRPF.asi so the game loads from mods\\.",
        "$FF1B7F3B", inst_xml, inst_files)

    pkg(os.path.join(a.out, "gtav_enhanced_restore.oiv"),
        "GTA V Enhanced - Restore English",
        "Restores the original English text and fonts, byte-identical to vanilla.",
        "$FF7F1B1B", rest_xml, rest_files)
    return 0


if __name__ == "__main__":
    sys.exit(main())
