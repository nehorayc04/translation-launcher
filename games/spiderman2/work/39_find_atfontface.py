"""Find @font-face declarations and lobby-specific CSS."""
import os, sys, struct, re
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
TOC  = os.path.join(GAME, "toc")
OUT  = os.path.join(ROOT, "games", "spiderman2", "extracted", "ui_atfontface")
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib

with open(TOC, "rb") as f:
    toc = dat1lib.read(f)
toc.set_archives_dir(GAME)
archs = toc.get_archives_section()
ui_arch = None
for i, a in enumerate(archs.archives):
    name = bytes(a.filename).split(b"\x00")[0].decode("ascii")
    if name.endswith("userinterface"):
        ui_arch = i
        break

aid_section = toc.get_assets_section()
ui_entries = []
for idx in range(len(aid_section.ids)):
    e = toc.get_asset_entry_by_index(idx)
    if e is not None and e.archive == ui_arch:
        ui_entries.append(e)

# Look for @font-face SPECIFICALLY in all entries.
# Also: list font-family values found.
print(f"[*] scanning {len(ui_entries)} UI assets for @font-face / Lobby keyword")
font_face_hits = []
lobby_hits = []
all_font_families = set()
for k, e in enumerate(ui_entries):
    if e.size > 5_000_000: continue  # skip the giant fonts
    try:
        d = bytes(toc.extract_asset(e))[36:]
    except Exception:
        continue
    if not d: continue
    if d.count(b"@font-face") > 0:
        font_face_hits.append((e.index, e.size, d.count(b"@font-face")))
    if d.count(b"Lobby") > 5 or d.count(b"lobby") > 5:
        lobby_hits.append((e.index, e.size, d.count(b"Lobby") + d.count(b"lobby")))
    # extract font-family values
    for m in re.finditer(b"font-family:\\s*['\"]?([^'\";}]{0,60})", d):
        try:
            fam = m.group(1).decode("utf-8", "replace").strip()
            if fam: all_font_families.add(fam)
        except: pass

print(f"\n=== {len(font_face_hits)} assets with @font-face ===")
for idx, size, c in font_face_hits[:20]:
    print(f"  idx={idx:<8} size={size:<10} @font-face count={c}")

print(f"\n=== {len(lobby_hits)} assets with 'Lobby' references ===")
for idx, size, c in lobby_hits[:20]:
    print(f"  idx={idx:<8} size={size:<10} Lobby count={c}")

print(f"\n=== {len(all_font_families)} unique font-family values seen ===")
for fam in sorted(all_font_families):
    print(f"  {fam!r}")

# Extract one @font-face file to show context
if font_face_hits:
    target_idx = font_face_hits[0][0]
    e = next((ee for ee in ui_entries if ee.index == target_idx), None)
    if e:
        d = bytes(toc.extract_asset(e))[36:]
        # find @font-face block
        i = d.find(b"@font-face")
        if i >= 0:
            print(f"\n=== first @font-face occurrence in idx={target_idx} ===")
            print(d[max(0,i-50):i+1500].decode("utf-8", "replace"))
        outp = os.path.join(OUT, f"ui_atfontface_{target_idx}.txt")
        with open(outp, "wb") as f: f.write(d)
        print(f"  saved -> {outp}")
