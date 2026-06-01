"""Replace the two Chinese fonts (idx 298871, 396876) with the content of
Arial Unicode MS Bold (idx 15610) — keeping the Insomniac wrapper format.

If the lobby's 'AzbukaPro-Bold' / 'AzbukaPro-Medium' maps to one of the
Chinese font asset slots, this swap forces those slots to contain Arial
Unicode MS Bold data (which has Hebrew)."""
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

# Identify entries
aid_section = toc.get_assets_section()
ENTRIES = {}
for need in (15610, 298871, 396876, 422626):
    for idx in range(len(aid_section.ids)):
        ee = toc.get_asset_entry_by_index(idx)
        if ee and ee.index == need:
            ENTRIES[need] = ee; break

print("=== font asset entries ===")
for k, e in ENTRIES.items():
    print(f"  idx {k}: asset_id=0x{e.asset_id:016X}  arch={e.archive}  size={e.size}")

# Pull Arial Unicode MS Bold (idx 15610) bytes
arial_bold = bytes(toc.extract_asset(ENTRIES[15610]))[36:]   # strip AssetEntry header (kept by .stage builder)
print(f"\n[*] Arial Unicode MS Bold content: {len(arial_bold)} bytes  head={arial_bold[:8].hex(' ')}")

# Also Arial Unicode MS Regular for variety
arial_normal = bytes(toc.extract_asset(ENTRIES[422626]))[36:]
print(f"[*] Arial Unicode MS Normal content: {len(arial_normal)} bytes  head={arial_normal[:8].hex(' ')}")

# Span for each Chinese font's asset
spans = toc.get_spans_section().entries
def span_for(asset_index):
    for s_idx, sp in enumerate(spans):
        if sp.count == 0: continue
        if sp.asset_index <= asset_index < sp.asset_index + sp.count:
            return s_idx
    return None

span_298871 = span_for(298871)
span_396876 = span_for(396876)
print(f"\n[*] Chinese W2 (idx 298871) is in span {span_298871}")
print(f"[*] Chinese W4 (idx 396876) is in span {span_396876}")

# Build a stage that maps:
#   span/asset_id_298871 -> Arial Unicode MS Bold content
#   span/asset_id_396876 -> Arial Unicode MS Normal content
e_298871 = ENTRIES[298871]
e_396876 = ENTRIES[396876]

stage_entries = {
    f"{span_298871}/{e_298871.asset_id:016X}": arial_bold,
    f"{span_396876}/{e_396876.asset_id:016X}": arial_normal,
}

info = {"game":"MSM2","name":"Font Swap — Chinese slots -> Arial Unicode MS","author":"Nehoray","format_version":2}
out_stage = os.path.join(MODD, "font_swap_chinese.stage")
out_modular = os.path.join(MODD, "font_swap_chinese.modular")

with zipfile.ZipFile(out_stage, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for path, content in stage_entries.items():
        z.writestr(path, content)
    z.writestr("info.json", json.dumps(info, indent=2))
print(f"\n[+] wrote {out_stage}  ({os.path.getsize(out_stage)} bytes)")

modular_info = {
    "game":"MSM2","name":"Hebrew Font Swap v3 (Chinese slots)","author":"Nehoray","format_version":1,
    "layout":[["header","Force Chinese font slots to Arial Unicode MS"],
              ["module","Apply:",[["", "Replace M 盈黑 PRC W2+W4 with Arial Unicode MS", "modules/font_swap_chinese.stage"]]]],
}
with zipfile.ZipFile(out_modular, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    z.writestr("info.json", json.dumps(modular_info, indent=2))
    z.writestr("modules/font_swap_chinese.stage", open(out_stage, "rb").read())

ml = os.path.join(GAME, "Mods Library")
target = os.path.join(ml, "font_swap_chinese.modular")
shutil.copy(out_modular, target)

# Clean up old swap mod
for old_name in ("font_swap_local.modular", "font_swap_test.modular"):
    old = os.path.join(ml, old_name)
    if os.path.exists(old):
        os.remove(old)
        print(f"[*] removed old {old_name}")

print(f"\n[+] copied -> {target}")
print()
print("Stage entries inside:")
for path in stage_entries:
    print(f"  {path}  ({len(stage_entries[path])} bytes)")
