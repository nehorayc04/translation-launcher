"""Dump EVERY textual UI asset (HTML/CSS/JS/JSON) from the userinterface
archive(s), with a full manifest (index, span, assetID, size, markers).

Goal: find the in-game SETTINGS-menu cohtml document + its CSS, identify the
description container's text-direction, so we can patch direction:rtl at the
ROOT (the container) instead of wrapping every string.

Output:
  extracted/ui_dump/<index>.txt        — each textual asset
  extracted/ui_dump/_manifest.json     — [{index, span, assetID, archive, size, markers, head}]
"""
import os, sys, json, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
TOC  = os.path.join(GAME, "toc")
OUT  = os.path.join(ROOT, "games", "spiderman2", "extracted", "ui_dump")
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib

with open(TOC, "rb") as f:
    toc = dat1lib.read(f)
toc.set_archives_dir(GAME)

spans = toc.get_spans_section().entries
def span_for_index(ai):
    for si, sp in enumerate(spans):
        if sp.count and sp.asset_index <= ai < sp.asset_index + sp.count:
            return si, ai - sp.asset_index
    return None, None

assets = toc.get_assets_section()
ids = assets.ids

archs = toc.get_archives_section()
ui_archs = {}
for i, a in enumerate(archs.archives):
    name = bytes(a.filename).split(b"\x00")[0].decode("ascii", "replace")
    if "userinterface" in name.lower() or name.lower().endswith("ui"):
        ui_archs[i] = name
print(f"[*] UI archives: {ui_archs}")

# textual markers we care about
MARK = {
    "html":   [b"<html", b"<body", b"<div", b"<!DOCTYPE", b"cohtml", b"<span"],
    "css":    [b"{", b"font-family", b"text-align", b"direction:", b"display:", b".cls", b"@media"],
    "js":     [b"function", b"var ", b"const ", b"=>", b"prototype", b"addEventListener"],
    "bidi":   [b"direction", b"rtl", b"ltr", b"unicode-bidi", b"dir="],
    "settings":[b"setting", b"Setting", b"description", b"Description", b"desc", b"DESC",
                b"display", b"Display", b"graphics", b"Graphics", b"PCDISPLAY"],
}

def is_textual(b):
    if len(b) < 8:
        return False
    head = b[:64]
    printable = sum(1 for c in head if 0x20 <= c <= 0x7E or c in (9, 10, 13))
    return printable >= len(head) * 0.85

manifest = []
nsaved = 0
nseen = 0
for idx in range(len(ids)):
    e = toc.get_asset_entry_by_index(idx)
    if e is None:
        continue
    if ui_archs and e.archive not in ui_archs:
        continue
    nseen += 1
    try:
        raw = bytes(toc.extract_asset(e))
    except Exception:
        continue
    if not raw:
        continue
    # try both with and without a 36-byte prefix
    for body, off in ((raw, 0), (raw[36:], 36)):
        if is_textual(body):
            markers = {}
            for grp, toks in MARK.items():
                hits = [t.decode("latin-1") for t in toks if t in body]
                if hits:
                    markers[grp] = hits
            if not markers:
                break
            span, pos = span_for_index(e.index)
            aid = format(ids[e.index], "X") if e.index < len(ids) else "?"
            outp = os.path.join(OUT, f"{e.index}.txt")
            with open(outp, "wb") as fo:
                fo.write(body)
            manifest.append({
                "index": e.index, "span": span, "pos": pos, "assetID": aid,
                "archive": e.archive, "size": len(body), "prefix_off": off,
                "markers": markers,
                "head": body[:120].decode("utf-8", "replace"),
            })
            nsaved += 1
            break

manifest.sort(key=lambda m: -m["size"])
json.dump(manifest, open(os.path.join(OUT, "_manifest.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"[*] scanned {nseen} UI assets, saved {nsaved} textual")
# quick report: which have bidi + settings markers
print("\n=== assets with BOTH bidi + settings markers ===")
for m in manifest:
    if "bidi" in m["markers"] and "settings" in m["markers"]:
        print(f"  idx={m['index']:<9} span={m['span']} aid={m['assetID']:<18} size={m['size']:<8} bidi={m['markers'].get('bidi')}")
print("\n=== assets with direction: in them ===")
for m in manifest:
    if "css" in m["markers"] and any("direction" in x for x in m["markers"].get("bidi", [])):
        print(f"  idx={m['index']:<9} span={m['span']} aid={m['assetID']:<18} size={m['size']}")
