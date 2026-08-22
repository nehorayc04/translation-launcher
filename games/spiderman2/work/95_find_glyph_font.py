"""Find the INPUT/CONTROLLER glyph font — the one that renders button-prompt
icons ([ACTION_*], hold, mouse, slow-mo symbol). These render as tofu boxes in
the Arabic locale. all_ui_fonts.json only captured the 33 TEXT fonts; the icon
font is probably a separate asset. Scan every asset in the userinterface
archive for TTF/OTF magic and report the ones with many PUA / symbol glyphs."""
import os, sys, io, json
ROOT = r"C:\Users\Nehoray_Cohen\Projects\Game translator"
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib
from fontTools.ttLib import TTFont

toc = dat1lib.read(open(os.path.join(GAME, "toc"), "rb"))
toc.set_archives_dir(GAME)
ids = toc.get_assets_section().ids
spans = toc.get_spans_section().entries
def span_for(ai):
    for s, sp in enumerate(spans):
        if sp.count and sp.asset_index <= ai < sp.asset_index + sp.count:
            return s
    return None

archs = toc.get_archives_section()
ui_archs = set()
for i, a in enumerate(archs.archives):
    name = bytes(a.filename).split(b"\x00")[0].decode("ascii", "replace")
    if "userinterface" in name.lower():
        ui_archs.add(i)

TTF_MAGIC = (b"\x00\x01\x00\x00", b"OTTO", b"true", b"ttcf")
found = []
scanned = 0
for idx in range(len(ids)):
    e = toc.get_asset_entry_by_index(idx)
    if e is None or (ui_archs and e.archive not in ui_archs):
        continue
    try:
        raw = bytes(toc.extract_asset(e))
    except Exception:
        continue
    if not raw:
        continue
    # font magic at 0 or right after a small prefix
    for off in (0, 36):
        if raw[off:off+4] in TTF_MAGIC:
            scanned += 1
            try:
                f = TTFont(io.BytesIO(raw[off:]))
                cm = f.getBestCmap()
                pua = [c for c in cm if 0xE000 <= c <= 0xF8FF]
                sym = [c for c in cm if 0x2300 <= c <= 0x2BFF]  # symbols/arrows/dingbats
                try:
                    name = f["name"].getDebugName(1) or "?"
                except Exception:
                    name = "?"
                if pua or sym:
                    found.append((idx, span_for(idx), format(ids[idx], "X"),
                                  len(cm), len(pua), len(sym), name))
            except Exception:
                pass
            break

print(f"[*] scanned {scanned} font assets in UI archive")
print(f"[*] fonts WITH PUA or symbol glyphs (candidate icon fonts):\n")
found.sort(key=lambda x: -(x[4] + x[5]))
for idx, sp, aid, ng, npua, nsym, name in found:
    print(f"  idx={idx:<8} span={sp} aid={aid:<18} glyphs={ng:<5} PUA={npua:<4} sym={nsym:<4} | {name}")
if not found:
    print("  (none — input prompts are likely IMAGE SPRITES, not a font)")
