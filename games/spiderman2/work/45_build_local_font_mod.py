"""Try cohtml's @font-face local() syntax — point AzbukaPro-Bold/Medium to
the user's installed Segoe UI (which always has Hebrew + Arabic on Windows).

We OVERRIDE the original @font-face declarations by adding new ones AFTER —
in CSS, last @font-face wins."""
import os, sys, json, zipfile, shutil
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

# Replace the @font-face CSS with one that uses local() fonts.
# local("Segoe UI") - default Windows UI font, has Hebrew + Arabic + Latin.
# Multiple @font-face per name: cohtml will try each in order until one resolves.
new_css = (
    '@font-face {\r\n'
    '    src: local("Arial Unicode MS"), local("Segoe UI"), local("Tahoma"), url("../fonts/AzbukaPro.ttf");\r\n'
    '    font-family: "AzbukaPro-Regular";\r\n'
    '    font-style: normal;\r\n'
    '}\r\n'
    '@font-face {\r\n'
    '    src: local("Arial Unicode MS"), local("Segoe UI Bold"), local("Segoe UI"), local("Tahoma"), url("../fonts/AzbukaPro-Bold.ttf");\r\n'
    '    font-family: "AzbukaPro-Bold";\r\n'
    '    font-style: normal;\r\n'
    '}\r\n'
    '@font-face {\r\n'
    '    src: local("Arial Unicode MS"), local("Segoe UI"), local("Tahoma"), url("../fonts/AzbukaPro-Medium.ttf");\r\n'
    '    font-family: "AzbukaPro-Medium";\r\n'
    '    font-style: normal;\r\n'
    '}\r\n'
    '@font-face {\r\n'
    '    src: local("Arial Unicode MS"), local("Segoe UI Black"), local("Segoe UI"), url("../fonts/AzbukaPro-Black.ttf");\r\n'
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
print(f"=== patched CSS ({len(new_bytes)} bytes) ===")
print(new_css)

# Build the stage mod
spans = toc.get_spans_section().entries
def span_for_index(asset_index):
    for s_idx, sp in enumerate(spans):
        if sp.count == 0: continue
        if sp.asset_index <= asset_index < sp.asset_index + sp.count:
            return s_idx
    return None

span = span_for_index(target_idx)
asset_id_hex = f"{e.asset_id:016X}"
STAGE_ENTRY = f"{span}/{asset_id_hex}"
print(f"\n[*] stage entry path: {STAGE_ENTRY}")

info = {"game":"MSM2","name":"Font Swap — local() Windows fallback","author":"Nehoray","format_version":2}
out_stage = os.path.join(MODD, "font_swap_local.stage")
out_modular = os.path.join(MODD, "font_swap_local.modular")

with zipfile.ZipFile(out_stage, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    z.writestr(STAGE_ENTRY, new_bytes)
    z.writestr("info.json", json.dumps(info, indent=2))
print(f"[+] wrote {out_stage}  ({os.path.getsize(out_stage)} bytes)")

modular_info = {
    "game":"MSM2","name":"Hebrew Font Swap v2 (local Windows)","author":"Nehoray","format_version":1,
    "layout":[["header","Force local Windows fonts"],
              ["module","Apply:",[["", "Use Segoe UI / Arial Unicode MS for AzbukaPro-*", "modules/font_swap_local.stage"]]]],
}
with zipfile.ZipFile(out_modular, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    z.writestr("info.json", json.dumps(modular_info, indent=2))
    z.writestr("modules/font_swap_local.stage", open(out_stage, "rb").read())

ml = os.path.join(GAME, "Mods Library")
target = os.path.join(ml, "font_swap_local.modular")
shutil.copy(out_modular, target)

# Also: remove the OLD font_swap_test.modular so they don't conflict
old = os.path.join(ml, "font_swap_test.modular")
if os.path.exists(old):
    os.remove(old)
    print(f"[*] removed old font_swap_test.modular")

print(f"\n[+] copied -> {target}")
print()
print("Now in Overstrike:")
print("  ☑ Hebrew Translation — Main Menu Test")
print("  ☑ Hebrew Font Swap v2 (local Windows)")
print("  -> Install mods")
