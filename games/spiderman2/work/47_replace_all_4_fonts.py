"""Replace ALL 4 font assets in d/userinterface with the SAME content
(Arial Unicode MS Bold, idx 15610). If ANY of the 4 is what cohtml uses for
Hebrew chars, my Hebrew will render.

If even this doesn't work — cohtml is using a font NOT inside d/userinterface
(likely embedded in cohtml.WindowsDesktop.dll or pulled via DirectWrite)."""
import os, sys, json, zipfile, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
MODD = os.path.join(ROOT, "games", "spiderman2", "mod")
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib

with open(os.path.join(GAME, "toc"), "rb") as f:
    toc = dat1lib.read(f)
toc.set_archives_dir(GAME)

# All 4 font asset indices + the Bold-content source
FONT_IDXS = [15610, 298871, 396876, 422626]
SOURCE_IDX = 15610   # Arial Unicode MS Bold (proven to contain Hebrew)

aid_section = toc.get_assets_section()
ENTRIES = {}
for need in FONT_IDXS:
    for idx in range(len(aid_section.ids)):
        ee = toc.get_asset_entry_by_index(idx)
        if ee and ee.index == need:
            ENTRIES[need] = ee; break

# Pull source font content
src_e = ENTRIES[SOURCE_IDX]
src_content = bytes(toc.extract_asset(src_e))[36:]   # strip AssetEntry header
print(f"[*] source: Arial Unicode MS Bold = {len(src_content)} bytes")
print(f"    head: {src_content[:8].hex(' ')}")

# Build stage entries — each target asset replaced with the SAME source bytes
spans = toc.get_spans_section().entries
def span_for(asset_index):
    for s_idx, sp in enumerate(spans):
        if sp.count == 0: continue
        if sp.asset_index <= asset_index < sp.asset_index + sp.count:
            return s_idx
    return None

stage_entries = {}
for need in FONT_IDXS:
    e = ENTRIES[need]
    sp = span_for(need)
    path = f"{sp}/{e.asset_id:016X}"
    stage_entries[path] = src_content
    print(f"   replacing idx {need} (asset {e.asset_id:016X}) in span {sp} -> Arial Unicode MS Bold")

info = {"game":"MSM2","name":"Font Swap — ALL slots -> Arial Unicode MS Bold","author":"Nehoray","format_version":2}
out_stage = os.path.join(MODD, "font_swap_all.stage")
out_modular = os.path.join(MODD, "font_swap_all.modular")

with zipfile.ZipFile(out_stage, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for path, content in stage_entries.items():
        z.writestr(path, content)
    z.writestr("info.json", json.dumps(info, indent=2))
print(f"\n[+] wrote {out_stage}  ({os.path.getsize(out_stage)} bytes)")

modular_info = {
    "game":"MSM2","name":"Hebrew Font Swap v4 (ALL slots)","author":"Nehoray","format_version":1,
    "layout":[["header","Replace ALL 4 font slots with Arial Unicode MS Bold"],
              ["module","Apply:",[["", "All -> Arial Unicode MS Bold", "modules/font_swap_all.stage"]]]],
}
with zipfile.ZipFile(out_modular, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    z.writestr("info.json", json.dumps(modular_info, indent=2))
    z.writestr("modules/font_swap_all.stage", open(out_stage, "rb").read())

ml = os.path.join(GAME, "Mods Library")
target = os.path.join(ml, "font_swap_all.modular")
shutil.copy(out_modular, target)

# Clean up old swap mods
for old_name in ("font_swap_chinese.modular", "font_swap_local.modular", "font_swap_test.modular"):
    old = os.path.join(ml, old_name)
    if os.path.exists(old):
        os.remove(old)
        print(f"[*] removed old {old_name}")
print(f"\n[+] copied -> {target}")
