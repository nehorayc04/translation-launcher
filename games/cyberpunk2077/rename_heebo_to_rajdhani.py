"""
Replace Heebo's name table with vanilla raj/industry's name table so the engine
identifies our font under the expected family name.
"""
import os
import shutil
import subprocess
from fontTools.ttLib import TTFont

CLI = r"C:\Users\Nehoray_Cohen\AppData\Local\Programs\WolvenKit-CLI\WolvenKit.CLI.exe"
CP = r"C:\Users\Nehoray_Cohen\Projects\Game translator\Game Lab\Cyberpunk 2077"
ARCHIVE = os.path.join(CP, r"archive\pc\content\basegame_1_engine.archive")

WORK = r"C:\Users\Nehoray_Cohen\AppData\Local\Temp\font_v2"
EXTRACT = os.path.join(WORK, "extract_vanilla_ttfs")
STRIPPED = os.path.join(WORK, "stripped_ttf")
RENAMED = os.path.join(WORK, "renamed_ttf")
os.makedirs(EXTRACT, exist_ok=True)
os.makedirs(RENAMED, exist_ok=True)

# Map: heebo_weight -> vanilla_fnt_basename (in archive path)
MAP = [
    ("Regular",  "rajdhani-regular"),
    ("Medium",   "raj-medium"),
    ("SemiBold", "raj-semibold"),
    ("Bold",     "raj-bold"),
    ("Medium",   "industry_demi"),  # industry_demi uses Medium weight Heebo
]

# Step 1: extract vanilla .fnt files we want to mimic
patterns_done = set()
for _, fnt_base in MAP:
    pat = f"*{fnt_base}.fnt"
    if pat in patterns_done:
        continue
    subprocess.run([CLI, "extract", ARCHIVE, "-o", EXTRACT, "-w", pat], check=False, capture_output=True)
    patterns_done.add(pat)

# Step 2: export each .fnt to .ttf so we can read its name table
EXPORT_OUT = os.path.join(WORK, "vanilla_exports")
os.makedirs(EXPORT_OUT, exist_ok=True)
for _, fnt_base in MAP:
    fnt_paths = []
    for root, _, files in os.walk(EXTRACT):
        for fn in files:
            if fn == fnt_base + ".fnt":
                fnt_paths.append(os.path.join(root, fn))
    if fnt_paths:
        subprocess.run([CLI, "export", fnt_paths[0], "-o", EXPORT_OUT, "-gp", CP], check=False, capture_output=True)

# Step 3: For each heebo→fnt mapping, copy vanilla's name+OS/2 tables into our Heebo
for heebo_weight, fnt_base in MAP:
    src_heebo = os.path.join(STRIPPED, f"Heebo-{heebo_weight}.ttf")
    vanilla_ttf = os.path.join(EXPORT_OUT, f"{fnt_base}.ttf")
    out_ttf = os.path.join(RENAMED, f"{fnt_base}.ttf")

    if not os.path.exists(src_heebo) or not os.path.exists(vanilla_ttf):
        print(f"  SKIP {fnt_base}: src={os.path.exists(src_heebo)} vanilla={os.path.exists(vanilla_ttf)}")
        continue

    h = TTFont(src_heebo)
    v = TTFont(vanilla_ttf)

    # Replace name table entirely with vanilla's
    h["name"] = v["name"]

    # Also align OS/2 / head identifiers if vanilla has values our engine cares about
    # (We keep Heebo's metrics — tampering with those could break layout.)

    h.save(out_ttf)
    print(f"  {fnt_base}.ttf: copied vanilla name table → {os.path.getsize(out_ttf):,} bytes")

print("\nFinal renamed TTFs:")
for f in sorted(os.listdir(RENAMED)):
    print(f"  {f}: {os.path.getsize(os.path.join(RENAMED, f)):,} bytes")
