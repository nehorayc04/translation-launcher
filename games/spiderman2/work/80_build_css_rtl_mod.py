"""Build an Overstrike mod that patches cohtml CSS asset(s) for Hebrew RTL,
and bundle it together with the existing Hebrew localization .stage into one
.modular.

Reads css_rtl_patches.json:
  [{ "index": 125074, "assetID": "929531853AE6FE29",
     "edits": [ ["find_substr", "replace_substr"], ... ],   # exact, must be unique
     "append": "css text appended at end (optional)" }, ...]

For each asset:  content = extract_asset(index)  (raw, no 36-byte prefix for CSS)
Apply edits + append, collect into ONE .stage with entries  0/<assetID> -> bytes.
Then build the combined .modular:  localization module + css module.

Verifies every edit applied (find present exactly once) — never silently skips.
"""
import os, sys, json, io, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
TOC  = os.path.join(GAME, "toc")
MODD = os.path.join(ROOT, "games", "spiderman2", "mod")
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib

PATCHES = os.path.join(HERE, "css_rtl_patches.json")
patches = json.load(open(PATCHES, encoding="utf-8"))

toc = dat1lib.read(open(TOC, "rb"))
toc.set_archives_dir(GAME)
ids = toc.get_assets_section().ids
spans = toc.get_spans_section().entries

def span_for(ai):
    for si, sp in enumerate(spans):
        if sp.count and sp.asset_index <= ai < sp.asset_index + sp.count:
            return si
    return None

# ---- build the CSS .stage (may hold several assets) -------------------------
css_stage = os.path.join(MODD, "hebrew_css_rtl.stage")
entries = {}
PRISTINE_DIR = os.path.join(ROOT, "games", "spiderman2", "extracted", "ui_dump")
# ⚠️ GAME-UPDATE-AWARE: an asset's INDEX is positional and SHIFTS on every game patch
# (v1.131 -> 350558, v2.629 -> 350646), while its assetID is a stable hash of the path.
# Resolve the index FROM the assetID; `index` in the json is only a legacy hint.
_ID_TO_IDX = {}
for _i, _a in enumerate(ids):
    _ID_TO_IDX.setdefault(format(_a, "X").upper(), _i)

# Is the live toc vanilla? (If a mod is applied, extracting would return modded content.)
_TOC_IS_VANILLA = not any(
    b"tm_he_" in bytes(_e.filename) or b"mod" == bytes(_e.filename).split(b"\x00", 1)[0][:3]
    for _e in toc.get_archives_section().archives)

for p in patches:
    aid_want = (p.get("assetID") or "").upper()
    if aid_want:
        if aid_want not in _ID_TO_IDX:
            raise SystemExit(f"[!] assetID {aid_want} not in this game's toc — game updated? re-check css_rtl_patches.json")
        idx = _ID_TO_IDX[aid_want]
        if idx != p.get("index"):
            print(f"[i] assetID {aid_want}: index moved {p.get('index')} -> {idx} (game update) — using {idx}")
    else:
        idx = p["index"]
    e = toc.get_asset_entry_by_index(idx)
    # Source PRISTINE content. Prefer the LIVE toc when it is vanilla (that is the only
    # copy that matches the CURRENT game version); fall back to the ui_dump snapshot
    # (keyed by assetID, else the legacy index) when a mod is applied, because Overstrike
    # patches archives in place and extracting would return already-modded content.
    content = None
    if _TOC_IS_VANILLA:
        try:
            content = bytes(toc.extract_asset(e))
        except Exception as _ex:
            print(f"[!] live extract failed for idx {idx}: {_ex} — falling back to ui_dump")
    if content is None:
        for _cand in (f"{aid_want}.txt", f"{idx}.txt", f"{p.get('index')}.txt"):
            _pp = os.path.join(PRISTINE_DIR, _cand)
            if os.path.exists(_pp):
                content = open(_pp, "rb").read()
                break
    if content is None:
        content = bytes(toc.extract_asset(e))
    txt = content.decode("utf-8")
    for find, repl in p.get("edits", []):
        n = txt.count(find)
        if n != 1:
            raise SystemExit(f"[!] idx {idx}: edit find-string occurs {n}x (need exactly 1): {find!r:.80}")
        txt = txt.replace(find, repl)
        print(f"[+] idx {idx}: edit OK  {find[:40]!r} -> {repl[:40]!r}")
    if p.get("append"):
        txt = txt + "\n" + p["append"] + "\n"
        print(f"[+] idx {idx}: appended {len(p['append'])} chars")
    span = span_for(idx)
    aid = p.get("assetID") or format(ids[idx], "X")
    assert format(ids[idx], "X").upper() == aid.upper(), f"assetID mismatch idx {idx}"
    entry = f"{span}/{aid}"
    entries[entry] = txt.encode("utf-8")
    print(f"    -> stage entry {entry}  ({len(entries[entry])} bytes, was {len(content)})")

info = {"game": "MSM2", "name": "Hebrew RTL CSS fix", "author": "Nehoray", "format_version": 2}
with zipfile.ZipFile(css_stage, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for entry, data in entries.items():
        z.writestr(entry, data)
    z.writestr("info.json", json.dumps(info, indent=2))
print(f"\n[+] wrote {css_stage}  ({os.path.getsize(css_stage)} bytes, {len(entries)} entries)")

# ---- build combined .modular: localization + css ---------------------------
loc_stage = os.path.join(MODD, "hebrew_main_menu_test.stage")
out_modular = os.path.join(MODD, "hebrew_full.modular")
BUILD_VERSION = "30"   # bump every rebuild → Overstrike's mod list shows the new build
modular_info = {
    "game": "MSM2",
    "name": f"Hebrew Translation v{BUILD_VERSION} (menu + RTL CSS)",
    "author": "Nehoray",
    "format_version": 1,
    "layout": [
        ["header", "Hebrew translation"],
        ["module", "Translation:", [
            ["", "Menu text (Arabic slot)", "modules/hebrew_main_menu_test.stage"]
        ]],
        ["module", "RTL fix:", [
            ["", "cohtml RTL CSS", "modules/hebrew_css_rtl.stage"]
        ]],
    ],
}
with zipfile.ZipFile(out_modular, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    z.writestr("info.json", json.dumps(modular_info, indent=2))
    z.writestr("modules/hebrew_main_menu_test.stage", open(loc_stage, "rb").read())
    z.writestr("modules/hebrew_css_rtl.stage", open(css_stage, "rb").read())
print(f"[+] wrote {out_modular}  ({os.path.getsize(out_modular)} bytes)")
