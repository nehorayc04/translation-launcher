"""Hebrew font mod v7 — swap every non-Hebrew UI face with HEEBO (a clean,
modern geometric Hebrew family that fits SM2's UI far better than plain Arial),
weight-matched (Regular/Medium/Bold/Black) to the face it replaces."""
import os, sys, json, zipfile, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
MODD = os.path.join(ROOT, "games", "spiderman2", "mod")
HEEBO = os.path.join(ROOT, "games", "spiderman2", "extracted", "_heebo")
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib

# Swap the Arabic faces too (NeueFrutigerArabic): untranslated text then shows
# as tofu boxes — a clear visual marker of what's not yet translated — instead
# of leftover Arabic. Final build is all-Hebrew anyway.
SKIP_SUBSTR = ["盈黑", "Yoon", "ShinGo", "Arial Unicode MS", "Aguda"]
manifest = json.load(open(os.path.join(HERE, "all_ui_fonts.json")))

def weight_file(family):
    f = family.lower()
    if any(b in f for b in ("black", "heavy", "w7")):   return "Heebo-Black.ttf"
    if "bold" in f:                                      return "Heebo-Bold.ttf"
    if "medium" in f:                                    return "Heebo-Medium.ttf"
    return "Heebo-Regular.ttf"

COMMON = {  # _common faces by path -> explicit weight
    "ui/loaded/authored/_common/fonts/AzbukaPro.ttf":                 "Heebo-Regular.ttf",
    "ui/loaded/authored/_common/fonts/AzbukaPro-Medium.ttf":          "Heebo-Medium.ttf",
    "ui/loaded/authored/_common/fonts/AzbukaPro-Bold.ttf":            "Heebo-Bold.ttf",
    "ui/loaded/authored/_common/fonts/AzbukaPro-Black.ttf":           "Heebo-Black.ttf",
    "ui/loaded/authored/_common/fonts/NeueFrutigerArabic-Regular.ttf":"Heebo-Regular.ttf",
    "ui/loaded/authored/_common/fonts/MagicSpellJF.otf":              "Heebo-Black.ttf",
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

cache = {}
def fb(name):
    if name not in cache:
        cache[name] = open(os.path.join(HEEBO, name), "rb").read()
    return cache[name]

stage, report = {}, []
for fnt in manifest:
    fam = fnt["family"]
    if any(s in fam for s in SKIP_SUBSTR) or fnt["heb"] >= 5:
        continue
    sp = span_for(fnt["idx"]); aid = int(fnt["aid"], 16)
    wf = weight_file(fam)
    stage[f"{sp}/{aid:016X}"] = fb(wf)
    report.append((f"idx {fnt['idx']}", fam, wf, sp))

for path, wf in COMMON.items():
    ents = toc.get_asset_entries_by_path(path, stop_on_first=True)
    if not ents:
        continue
    e = ents[0]; sp = span_for(e.index); key = f"{sp}/{e.asset_id:016X}"
    if key not in stage:
        stage[key] = fb(wf); report.append((os.path.basename(path), "(common)", wf, sp))

print(f"Swapping {len(stage)} font assets with Heebo:")
for tag, fam, wf, sp in sorted(report):
    print(f"  span{sp}  {tag:<14} {fam!r:<34} <- {wf}")

info = {"game":"MSM2","name":"Hebrew Font v7 (Heebo)","author":"Nehoray","format_version":2}
out_stage = os.path.join(MODD, "hebrew_font_v7.stage")
out_modular = os.path.join(MODD, "hebrew_font_v7.modular")
with zipfile.ZipFile(out_stage, "w", zipfile.ZIP_DEFLATED, 6) as z:
    for p, c in stage.items():
        z.writestr(p, c)
    z.writestr("info.json", json.dumps(info, indent=2))
mi = {"game":"MSM2","name":"Hebrew Font Swap v7 (Heebo)","author":"Nehoray","format_version":1,
      "layout":[["header","Swap UI fonts with Heebo (clean modern Hebrew family)"],
                ["module","Apply:",[["","UI fonts -> Heebo","modules/hebrew_font_v7.stage"]]]]}
with zipfile.ZipFile(out_modular, "w", zipfile.ZIP_DEFLATED, 6) as z:
    z.writestr("info.json", json.dumps(mi, indent=2))
    z.writestr("modules/hebrew_font_v7.stage", open(out_stage, "rb").read())

ml = os.path.join(GAME, "Mods Library")
shutil.copy(out_modular, os.path.join(ml, "hebrew_font_v7.modular"))
old = os.path.join(ml, "hebrew_font_v6.modular")
if os.path.exists(old):
    os.remove(old); print("[*] removed hebrew_font_v6.modular")
print(f"\n[+] {out_modular}  ({os.path.getsize(out_modular):,} B)")
print("[+] deployed -> Mods Library/hebrew_font_v7.modular")
