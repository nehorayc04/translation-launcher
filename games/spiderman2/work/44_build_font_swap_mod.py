"""Build a font-swap test mod. Patches the @font-face CSS (idx 320895) to
remap AzbukaPro-Bold and AzbukaPro-Medium to use the URL of AzbukaPro.ttf
(Regular weight). If the squares were because Bold/Medium mapped to a
Chinese font (no Hebrew), this swap will make all 4 names point to the same
font asset and Hebrew should render.

We package the patched CSS asset as an Overstrike .stage mod."""
import os, sys, struct, json, zipfile
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
TOC  = os.path.join(GAME, "toc")
MODD = os.path.join(ROOT, "games", "spiderman2", "mod")
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib

with open(TOC, "rb") as f:
    toc = dat1lib.read(f)
toc.set_archives_dir(GAME)

# Get the @font-face asset
aid_section = toc.get_assets_section()
target_idx = 320895
e = None
for idx in range(len(aid_section.ids)):
    ee = toc.get_asset_entry_by_index(idx)
    if ee and ee.index == target_idx:
        e = ee; break
assert e is not None, "couldn't find @font-face asset"
print(f"[*] @font-face asset: idx={e.index} asset_id=0x{e.asset_id:016X} size={e.size}")

raw = bytes(toc.extract_asset(e))
prefix = raw[:36]   # AssetEntry header
content = raw[36:]  # CSS text
original_css = content.decode("utf-8", "replace")
print(f"\n=== original CSS ({len(content)} bytes) ===")
print(original_css)

# Patch — replace BOTH Bold/Medium URLs to point to AzbukaPro.ttf (Regular)
new_css = (
    '@font-face {\r\n'
    '    src: url("../fonts/AzbukaPro.ttf");\r\n'
    '    font-family: "AzbukaPro-Medium";\r\n'
    '    font-style: normal;\r\n'
    '}\r\n'
    '@font-face {\r\n'
    '    src: url("../fonts/AzbukaPro.ttf");\r\n'
    '    font-family: "AzbukaPro-Regular";\r\n'
    '    font-style: normal;\r\n'
    '}\r\n'
    '@font-face {\r\n'
    '    src: url("../fonts/AzbukaPro.ttf");\r\n'
    '    font-family: "AzbukaPro-Bold";\r\n'
    '    font-style: normal;\r\n'
    '}\r\n'
    '@font-face {\r\n'
    '    src: url("../fonts/AzbukaPro.ttf");\r\n'
    '    font-family: "AzbukaPro-Black";\r\n'
    '    font-style: normal;\r\n'
    '}\r\n'
    '@font-face {\r\n'
    '    src: url("../fonts/MagicSpellJF.otf");\r\n'
    '    font-family: "MagicSpell";\r\n'
    '    font-style: normal;\r\n'
    '}\r\n'
)
new_bytes = new_css.encode("utf-8")
print(f"\n=== patched CSS ({len(new_bytes)} bytes) ===")
print(new_css)

# Build the .stage mod — same approach as before
# Asset path inside the stage: {span_id}/{asset_id_in_hex}
# What span is asset idx 320895 in? Find via span table.
spans = toc.get_spans_section().entries
def span_for_index(asset_index):
    for s_idx, sp in enumerate(spans):
        if sp.count == 0: continue
        if sp.asset_index <= asset_index < sp.asset_index + sp.count:
            return s_idx
    return None

span = span_for_index(target_idx)
print(f"\n[*] asset {target_idx} is in span {span}")

asset_id_hex = f"{e.asset_id:016X}"
STAGE_ENTRY = f"{span}/{asset_id_hex}"

info = {
    "game": "MSM2",
    "name": "Font Swap Test (force all AzbukaPro variants -> Regular URL)",
    "author": "Nehoray",
    "format_version": 2,
}

out_stage = os.path.join(MODD, "font_swap_test.stage")
out_modular = os.path.join(MODD, "font_swap_test.modular")

with zipfile.ZipFile(out_stage, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    z.writestr(STAGE_ENTRY, new_bytes)
    z.writestr("info.json", json.dumps(info, indent=2))
print(f"\n[+] wrote {out_stage}  ({os.path.getsize(out_stage)} bytes)")

modular_info = {
    "game": "MSM2",
    "name": "Hebrew Font Swap Test",
    "author": "Nehoray",
    "format_version": 1,
    "layout": [
        ["header", "Hebrew font swap experiment"],
        ["module", "Font swap:", [
            ["", "Apply (force AzbukaPro-Bold/Medium -> AzbukaPro.ttf)", "modules/font_swap_test.stage"]
        ]],
    ],
}
with zipfile.ZipFile(out_modular, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    z.writestr("info.json", json.dumps(modular_info, indent=2))
    z.writestr("modules/font_swap_test.stage", open(out_stage, "rb").read())
print(f"[+] wrote {out_modular}  ({os.path.getsize(out_modular)} bytes)")

# Copy to Mods Library so Overstrike picks it up
import shutil
ml = os.path.join(GAME, "Mods Library")
target = os.path.join(ml, "font_swap_test.modular")
shutil.copy(out_modular, target)
print(f"[+] copied -> {target}")
