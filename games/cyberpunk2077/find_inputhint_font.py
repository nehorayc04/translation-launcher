"""Locate the input-hint widget and the font it references, so we know which
.fnt to override (the input-hint action labels render BLANK in Hebrew even
though they are translated+baked and every overridden font has Hebrew —
meaning the widget points at a font the mod does not replace)."""
import os, sys, subprocess, glob, json

CLI = r"C:\Users\Nehoray_Cohen\AppData\Local\Programs\WolvenKit-CLI\WolvenKit.CLI.exe"
CP  = r"C:\Game Lab\Cyberpunk 2077"
WORK = r"c:\tmp\font_fix\widget"
os.makedirs(WORK, exist_ok=True)


def run(args):
    return subprocess.run(args, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def main():
    archs = glob.glob(os.path.join(CP, r"archive\pc\content\basegame_*.archive"))
    # input-hint widgets live under .../input/ or .../inputhint/
    for a in archs:
        run([CLI, "extract", a, "-o", WORK, "-w", "*input_hint*.inkwidget"])
        run([CLI, "extract", a, "-o", WORK, "-w", "*inputhint*.inkwidget"])
        run([CLI, "extract", a, "-o", WORK, "-w", "*hint*controller*.inkwidget"])
    widgets = glob.glob(os.path.join(WORK, "**", "*.inkwidget"), recursive=True)
    print(f"extracted {len(widgets)} candidate widgets")
    for w in widgets[:20]:
        print("  ", os.path.relpath(w, WORK))
        run([CLI, "convert", "serialize", w, "-o", WORK])
    # scan the serialized JSON for font references
    fonts = set()
    for j in glob.glob(os.path.join(WORK, "**", "*.json"), recursive=True):
        try:
            txt = open(j, encoding="utf-8").read()
        except Exception:
            continue
        import re
        for m in re.finditer(r'"(DepotPath|fontFamily|fontStyle)"\s*:\s*[^\n]*?([^"\\/\n]+\.(?:inkfontfamily|inkstyle|fnt))', txt):
            fonts.add(m.group(2))
    print("\n== font/style references found in input-hint widgets ==")
    for f in sorted(fonts):
        print("  ", f)
    if not fonts:
        print("  (none — font likely set via inkstyle theme or engine code)")


if __name__ == "__main__":
    main()
