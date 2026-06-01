"""Package the patched .localization as an Overstrike-compatible .stage mod.

Layout inside the .stage zip:
   144/BE55D94F171BF8DE   <- DAT1 content (no 36-byte AssetEntry prefix)
   info.json              <- mod metadata for Overstrike

Span 144 is the Arabic-locale slot (computed in 14_find_span.py).
Asset id  BE55D94F171BF8DE  is hex(13715107173940066526) — localization_all.localization."""
import os, json, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
WORK = os.path.join(ROOT, "games", "spiderman2", "work")
MODD = os.path.join(ROOT, "games", "spiderman2", "mod")
os.makedirs(MODD, exist_ok=True)

PATCHED = os.path.join(WORK, "arabic_patched_hebrew_menu.localization")
patched_bytes = open(PATCHED, "rb").read()
print(f"[*] patched file: {len(patched_bytes)} bytes (incl. 36-byte AssetEntry prefix)")

# Strip the 36-byte AssetEntry header — the .stage stores raw DAT1 only.
dat1_bytes = patched_bytes[36:]
print(f"[*] DAT1 content: {len(dat1_bytes)} bytes  (starts: {dat1_bytes[:4].hex()} = '{dat1_bytes[:4].decode('ascii','replace')}')")

ASSET_ID_HEX = "BE55D94F171BF8DE"   # 0xBE55D94F171BF8DE = 13715107173940066526
SPAN_ARABIC  = 144
STAGE_ENTRY  = f"{SPAN_ARABIC}/{ASSET_ID_HEX}"

info = {
    "game": "MSM2",
    "name": "Hebrew Translation — Main Menu Test (slot-hijacks Arabic)",
    "author": "Nehoray",
    "format_version": 2,
}

out_stage   = os.path.join(MODD, "hebrew_main_menu_test.stage")
out_modular = os.path.join(MODD, "hebrew_main_menu_test.modular")

# Build the .stage zip
with zipfile.ZipFile(out_stage, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    z.writestr(STAGE_ENTRY, dat1_bytes)
    z.writestr("info.json", json.dumps(info, indent=2))

print(f"\n[+] wrote {out_stage}  ({os.path.getsize(out_stage)} bytes)")

# Also produce a .modular wrapper so it shows up nicely in Overstrike with
# an enable/disable toggle. .modular is just a zip of {info.json + modules/*.stage}.
modular_info = {
    "game": "MSM2",
    "name": "Hebrew Translation — Main Menu Test",
    "author": "Nehoray",
    "format_version": 1,
    "layout": [
        ["header", "Hebrew main-menu test"],
        ["module", "Main menu:", [
            ["", "Apply (slot-hijacks Arabic)", "modules/hebrew_main_menu_test.stage"]
        ]],
    ],
}

with zipfile.ZipFile(out_modular, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    z.writestr("info.json", json.dumps(modular_info, indent=2))
    z.writestr("modules/hebrew_main_menu_test.stage", open(out_stage, "rb").read())

print(f"[+] wrote {out_modular}  ({os.path.getsize(out_modular)} bytes)")

# Quick sanity: re-open the .stage and list its contents
print(f"\n=== {os.path.basename(out_stage)} contents ===")
with zipfile.ZipFile(out_stage) as z:
    for info in z.infolist():
        print(f"  {info.file_size:>10}  {info.filename}")
