"""Comprehensive Hebrew font mod. The lobby header used a DUPLICATE 'Azbuka
Pro' asset (different path than the _common set we first swapped), so it stayed
tofu. d/userinterface actually holds 33 sfnt fonts; this swaps every Latin/
Cyrillic UI face that lacks Hebrew (incl. all Azbuka Pro copies) with Arial,
plus the 6 _common faces by path. CJK/Korean/Japanese fallbacks, Arial Unicode
MS, and the already-Hebrew 'Aguda for Insomniac' faces are left untouched."""
import os, sys, json, zipfile, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
MODD = os.path.join(ROOT, "games", "spiderman2", "mod")
WINF = r"C:\Windows\Fonts"
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib
from dat1lib import crc64

# Families to SKIP (script-specific fallbacks + already-Hebrew Aguda + the
# big pan-Unicode Arial Unicode MS which already covers everything).
SKIP_SUBSTR = ["盈黑", "Yoon", "ShinGo", "Arial Unicode MS", "Aguda"]
BOLD_SUBSTR = ["bold", "black", "heavy", "w7", "ultra", "extra bold"]

manifest = json.load(open(os.path.join(HERE, "all_ui_fonts.json")))

# The 6 _common faces, by path (re-included so a from-scratch install covers all)
COMMON = {
    "ui/loaded/authored/_common/fonts/AzbukaPro.ttf":                 "arial.ttf",
    "ui/loaded/authored/_common/fonts/AzbukaPro-Medium.ttf":          "arial.ttf",
    "ui/loaded/authored/_common/fonts/AzbukaPro-Bold.ttf":            "arialbd.ttf",
    "ui/loaded/authored/_common/fonts/AzbukaPro-Black.ttf":           "arialbd.ttf",
    "ui/loaded/authored/_common/fonts/NeueFrutigerArabic-Regular.ttf":"arial.ttf",
    "ui/loaded/authored/_common/fonts/MagicSpellJF.otf":              "arialbd.ttf",
}

with open(os.path.join(GAME, "toc"), "rb") as f:
    toc = dat1lib.read(f)
toc.set_archives_dir(GAME)
spans = toc.get_spans_section().entries
def span_for(ai):
    for s, sp in enumerate(spans):
        if sp.count and sp.asset_index <= ai < sp.asset_index + sp.count:
            return s
    return None

def repl_for(family):
    f = family.lower()
    return "arialbd.ttf" if any(b in f for b in BOLD_SUBSTR) else "arial.ttf"

cache = {}
def font_bytes(name):
    if name not in cache:
        cache[name] = open(os.path.join(WINF, name), "rb").read()
    return cache[name]

stage = {}
report = []

# 1) manifest fonts (by asset_id) that lack Hebrew and aren't skipped
for fnt in manifest:
    fam = fnt["family"]
    if any(s in fam for s in SKIP_SUBSTR):
        continue
    if fnt["heb"] >= 5:        # already has Hebrew
        continue
    idx = fnt["idx"]
    sp = span_for(idx)
    aid = int(fnt["aid"], 16)
    repl = repl_for(fam)
    stage[f"{sp}/{aid:016X}"] = font_bytes(repl)
    report.append((f"idx {idx}", fam, repl, sp))

# 2) the 6 _common faces by path
for path, repl in COMMON.items():
    ents = toc.get_asset_entries_by_path(path, stop_on_first=True)
    if not ents:
        continue
    e = ents[0]; sp = span_for(e.index)
    key = f"{sp}/{e.asset_id:016X}"
    if key not in stage:
        stage[key] = font_bytes(repl)
        report.append((os.path.basename(path), "(common)", repl, sp))

print(f"Swapping {len(stage)} font assets:")
for tag, fam, repl, sp in sorted(report):
    print(f"  span{sp}  {tag:<14} {fam!r:<34} <- {repl}")

info = {"game":"MSM2","name":"Hebrew Font v6 (all UI faces -> Arial)",
        "author":"Nehoray","format_version":2}
out_stage = os.path.join(MODD, "hebrew_font_v6.stage")
out_modular = os.path.join(MODD, "hebrew_font_v6.modular")
with zipfile.ZipFile(out_stage, "w", zipfile.ZIP_DEFLATED, 6) as z:
    for p, c in stage.items():
        z.writestr(p, c)
    z.writestr("info.json", json.dumps(info, indent=2))
mod_info = {"game":"MSM2","name":"Hebrew Font Swap v6 (ALL UI fonts -> Arial)",
            "author":"Nehoray","format_version":1,
            "layout":[["header","Swap every non-Hebrew UI face (incl. duplicate Azbuka Pro) with Arial"],
                      ["module","Apply:",[["","All UI fonts -> Arial","modules/hebrew_font_v6.stage"]]]]}
with zipfile.ZipFile(out_modular, "w", zipfile.ZIP_DEFLATED, 6) as z:
    z.writestr("info.json", json.dumps(mod_info, indent=2))
    z.writestr("modules/hebrew_font_v6.stage", open(out_stage, "rb").read())

ml = os.path.join(GAME, "Mods Library")
shutil.copy(out_modular, os.path.join(ml, "hebrew_font_v6.modular"))
old = os.path.join(ml, "hebrew_font_v5.modular")
if os.path.exists(old):
    os.remove(old); print("[*] removed hebrew_font_v5.modular")
print(f"\n[+] {out_modular}  ({os.path.getsize(out_modular):,} B)")
print("[+] deployed -> Mods Library/hebrew_font_v6.modular")
