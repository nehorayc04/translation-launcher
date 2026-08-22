"""Build the CORRECT Hebrew font-swap mod.

Targets the actual UI fontmap assets (found via path-CRC64 in d/config's
UIFontMap), NOT the CJK fallback fonts the old v4 mod hit by mistake:

  AzbukaPro-Medium.ttf  (primary menu font)      -> Arial
  AzbukaPro-Bold.ttf    (primary bold)           -> Arial Bold
  AzbukaPro-Black.ttf   (headers)                -> Arial Bold
  NeueFrutigerArabic-Regular.ttf (RTL fallback)  -> Arial

All four replacements carry full Hebrew + Arabic + Latin + Cyrillic coverage,
so Hebrew renders whether the engine draws it through the primary face or the
Arabic-script fallback chain.
"""
import os, sys, json, zipfile, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
MODD = os.path.join(ROOT, "games", "spiderman2", "mod")
WINF = r"C:\Windows\Fonts"
os.makedirs(MODD, exist_ok=True)
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib

# target asset path -> replacement Windows font file
# NOTE the @font-face mapping: family "AzbukaPro-Regular" -> file "AzbukaPro.ttf"
# (no suffix) — that Regular face draws the lobby header, so it MUST be swapped
# too or the title renders as tofu while the body text is already Hebrew.
TARGETS = {
    "ui/loaded/authored/_common/fonts/AzbukaPro.ttf":                 "arial.ttf",
    "ui/loaded/authored/_common/fonts/AzbukaPro-Medium.ttf":          "arial.ttf",
    "ui/loaded/authored/_common/fonts/AzbukaPro-Bold.ttf":            "arialbd.ttf",
    "ui/loaded/authored/_common/fonts/AzbukaPro-Black.ttf":           "arialbd.ttf",
    "ui/loaded/authored/_common/fonts/NeueFrutigerArabic-Regular.ttf":"arial.ttf",
    # MagicSpell is the decorative display face used for the giant lobby
    # HEADER (font-size 23vh) — the only fontmap face left un-swapped, and the
    # reason "המשך משחק" stayed tofu while body text was already Hebrew. It's an
    # .otf asset but RenoirCore parses by sfnt magic, so .ttf bytes drop in fine.
    "ui/loaded/authored/_common/fonts/MagicSpellJF.otf":              "arialbd.ttf",
}

with open(os.path.join(GAME, "toc"), "rb") as f:
    toc = dat1lib.read(f)
toc.set_archives_dir(GAME)

spans = toc.get_spans_section().entries
def span_for(asset_index):
    for s_idx, sp in enumerate(spans):
        if sp.count == 0:
            continue
        if sp.asset_index <= asset_index < sp.asset_index + sp.count:
            return s_idx
    return None

stage_entries = {}
print("Resolving targets:")
for path, repl in TARGETS.items():
    entries = toc.get_asset_entries_by_path(path, stop_on_first=True)
    if not entries:
        print(f"  [!] NOT FOUND: {path}")
        continue
    e = entries[0]
    sp = span_for(e.index)
    repl_path = os.path.join(WINF, repl)
    content = open(repl_path, "rb").read()
    stage_path = f"{sp}/{e.asset_id:016X}"
    stage_entries[stage_path] = content
    print(f"  [+] {os.path.basename(path):<32} asset={e.asset_id:016X} span={sp} "
          f"<- {repl} ({len(content):,} B)")

assert stage_entries, "no targets resolved!"

info = {"game": "MSM2",
        "name": "Hebrew Font — AzbukaPro+Arabic -> Arial",
        "author": "Nehoray", "format_version": 2}
out_stage = os.path.join(MODD, "hebrew_font_v5.stage")
out_modular = os.path.join(MODD, "hebrew_font_v5.modular")

with zipfile.ZipFile(out_stage, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for p, c in stage_entries.items():
        z.writestr(p, c)
    z.writestr("info.json", json.dumps(info, indent=2))
print(f"\n[+] {out_stage}  ({os.path.getsize(out_stage):,} B)")

modular_info = {
    "game": "MSM2",
    "name": "Hebrew Font Swap v5 (UI fontmap -> Arial)",
    "author": "Nehoray", "format_version": 1,
    "layout": [
        ["header", "Replace AzbukaPro + NeueFrutigerArabic with Arial (Hebrew-capable)"],
        ["module", "Apply:", [["", "UI fonts -> Arial", "modules/hebrew_font_v5.stage"]]],
    ],
}
with zipfile.ZipFile(out_modular, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    z.writestr("info.json", json.dumps(modular_info, indent=2))
    z.writestr("modules/hebrew_font_v5.stage", open(out_stage, "rb").read())
print(f"[+] {out_modular}  ({os.path.getsize(out_modular):,} B)")

# Deploy to Mods Library + retire the misguided v4 swap
ml = os.path.join(GAME, "Mods Library")
shutil.copy(out_modular, os.path.join(ml, "hebrew_font_v5.modular"))
for old in ("font_swap_all.modular", "font_swap_chinese.modular",
            "font_swap_local.modular", "font_swap_test.modular"):
    p = os.path.join(ml, old)
    if os.path.exists(p):
        os.remove(p)
        print(f"[*] removed stale {old}")
print(f"[+] deployed -> Mods Library/hebrew_font_v5.modular")
