"""
font_icon_fix.py — restore CP2077 input-icon glyphs that were lost when the
mod replaced raj/industry with subset-Heebo.

Root cause: subset_heebo.py kept only ASCII+Hebrew+punct, dropping the
Private-Use-Area (PUA, U+E000..U+F8FF) input-icon glyphs that vanilla raj
carried. The engine renders <Input actionName="..."> as a PUA glyph in the
UI font; with no PUA glyph it shows an empty "( )".

Fix: pull the PUA icon glyphs out of vanilla raj and merge them INTO our
deployed Heebo fonts (Heebo keeps Hebrew+ASCII, vanilla supplies the icons),
staying under the ~295-glyph engine buffer ceiling. Then import back to .fnt
and re-pack the static archive.

Stages (arg): extract | merge | deploy
"""
import os, sys, subprocess, glob, shutil

CLI  = r"C:\Users\Nehoray_Cohen\AppData\Local\Programs\WolvenKit-CLI\WolvenKit.CLI.exe"
CP   = r"C:\Game Lab\Cyberpunk 2077"
ENGINE_ARCH = os.path.join(CP, r"archive\pc\content\basegame_1_engine.archive")
PROJECT = r"C:\Users\Nehoray_Cohen\Projects\Game translator\תרגום_משחקים"
SRC_FONTS = os.path.join(PROJECT, r"source\archive\base\gameplay\gui\fonts")

WORK = r"c:\tmp\font_fix"
VAN_FNT = os.path.join(WORK, "vanilla_fnt")      # extracted vanilla .fnt (CR2W)
VAN_TTF = os.path.join(WORK, "vanilla_ttf")      # exported vanilla .ttf
CUR_TTF = os.path.join(WORK, "current_ttf")      # exported current deployed .ttf
MERGED  = os.path.join(WORK, "merged_ttf")       # Heebo + icons
for d in (VAN_FNT, VAN_TTF, CUR_TTF, MERGED):
    os.makedirs(d, exist_ok=True)

# (deployed .fnt basename, relative path under SRC_FONTS)
FONTS = [
    ("rajdhani-regular", r"raj\rajdhani-regular.fnt"),
    ("raj-medium",       r"raj\raj-medium.fnt"),
    ("raj-semibold",     r"raj\raj-semibold.fnt"),
    ("raj-bold",         r"raj\raj-bold.fnt"),
    ("industry_demi",    r"industry\industry_demi.fnt"),
]
PUA_LO, PUA_HI = 0xE000, 0xF8FF


def run(args, **kw):
    return subprocess.run(args, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", **kw)


def find(root, name):
    for r, _, files in os.walk(root):
        if name in files:
            return os.path.join(r, name)
    return None


def stage_extract():
    from fontTools.ttLib import TTFont
    print("== extracting vanilla raj/industry .fnt from basegame_1_engine ==")
    for base, _ in FONTS:
        run([CLI, "extract", ENGINE_ARCH, "-o", VAN_FNT, "-w", f"*{base}.fnt"])
    print("== exporting vanilla .fnt -> .ttf ==")
    for base, _ in FONTS:
        fnt = find(VAN_FNT, base + ".fnt")
        if not fnt:
            print(f"  [!] vanilla {base}.fnt not found"); continue
        run([CLI, "export", fnt, "-o", VAN_TTF, "-gp", CP])
    print("== PUA icon check (vanilla) ==")
    total_icons = {}
    for base, _ in FONTS:
        ttf = find(VAN_TTF, base + ".ttf")
        if not ttf:
            print(f"  [!] export missing for {base}"); continue
        t = TTFont(ttf); cmap = t.getBestCmap()
        pua = sorted(c for c in cmap if PUA_LO <= c <= PUA_HI)
        total_icons[base] = pua
        rng = f" [{hex(pua[0])}..{hex(pua[-1])}]" if pua else ""
        print(f"  {base}: glyphs={t['maxp'].numGlyphs} cmap={len(cmap)} PUA={len(pua)}{rng}")
    n = len(total_icons.get("rajdhani-regular", []))
    print(f"\nVERDICT: vanilla raj PUA icons = {n} "
          f"({'CONFIRMED — fix is viable' if n else 'NONE — icons are textures, theory wrong'})")


def stage_allfonts():
    """Extract EVERY game UI font, export, scan for PUA / symbol glyphs — to
    locate the input-icon font (if it is a font at all)."""
    from fontTools.ttLib import TTFont
    ALL = os.path.join(WORK, "all_fnt"); ALL_TTF = os.path.join(WORK, "all_ttf")
    for d in (ALL, ALL_TTF):
        os.makedirs(d, exist_ok=True)
    archs = glob.glob(os.path.join(CP, r"archive\pc\content\basegame_*.archive"))
    print(f"scanning {len(archs)} base archives for *gameplay*gui*fonts*.fnt ...")
    for a in archs:
        run([CLI, "extract", a, "-o", ALL, "-w", "*gameplay*fonts*.fnt"])
    fnts = glob.glob(os.path.join(ALL, "**", "*.fnt"), recursive=True)
    print(f"extracted {len(fnts)} .fnt; exporting + scanning PUA ...")
    hits = []
    for fnt in fnts:
        run([CLI, "export", fnt, "-o", ALL_TTF, "-gp", CP])
    for ttf in glob.glob(os.path.join(ALL_TTF, "**", "*.ttf"), recursive=True):
        try:
            cmap = TTFont(ttf).getBestCmap()
        except Exception:
            continue
        pua = [c for c in cmap if PUA_LO <= c <= PUA_HI]
        sym = [c for c in cmap if 0x2190 <= c <= 0x2BFF]  # arrows/symbols/dingbats
        if pua or sym:
            hits.append((os.path.basename(ttf), len(pua), len(sym)))
    print("\n== fonts with PUA or symbol glyphs (candidate icon fonts) ==")
    for name, p, s in sorted(hits, key=lambda x: -(x[1] + x[2])):
        print(f"  {name}: PUA={p} symbols={s}")
    if not hits:
        print("  NONE — no game UI font carries icon glyphs -> input icons are TEXTURES")


def stage_hebcheck():
    """Export every DEPLOYED source-tree .fnt and report Hebrew coverage —
    a font with 0 Hebrew glyphs renders Hebrew text as BLANK (the symptom)."""
    from fontTools.ttLib import TTFont
    OUT = os.path.join(WORK, "deployed_ttf")
    os.makedirs(OUT, exist_ok=True)
    fnts = glob.glob(os.path.join(SRC_FONTS, "**", "*.fnt"), recursive=True)
    print(f"exporting {len(fnts)} deployed .fnt + checking Hebrew (U+05D0..U+05EA) ...")
    rows = []
    for fnt in fnts:
        sub = os.path.join(OUT, os.path.splitext(os.path.basename(fnt))[0])
        os.makedirs(sub, exist_ok=True)
        run([CLI, "export", fnt, "-o", sub, "-gp", CP])
    for ttf in glob.glob(os.path.join(OUT, "**", "*.ttf"), recursive=True):
        try:
            cmap = TTFont(ttf).getBestCmap()
        except Exception:
            continue
        heb = sum(1 for c in cmap if 0x05D0 <= c <= 0x05EA)
        rel = os.path.relpath(ttf, OUT)
        rows.append((rel, len(cmap), heb))
    rows.sort(key=lambda x: x[2])
    print("\n== Hebrew coverage of deployed fonts (heb=0 => renders Hebrew BLANK) ==")
    for rel, cm, heb in rows:
        flag = "  <<< NO HEBREW" if heb == 0 else ""
        print(f"  {rel}: cmap={cm} hebrew={heb}{flag}")


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "extract"
    {"extract": stage_extract, "allfonts": stage_allfonts,
     "hebcheck": stage_hebcheck}.get(stage, stage_extract)()
