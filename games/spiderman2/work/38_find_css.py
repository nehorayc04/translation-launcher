"""Scan d/userinterface assets that look like text (CSS/JS/HTML) for any
mention of 'font-family' / '@font-face' / our font names — so we can identify
which CSS asset to patch."""
import os, sys, struct
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
TOC  = os.path.join(GAME, "toc")
OUT  = os.path.join(ROOT, "games", "spiderman2", "extracted", "ui_text_assets")
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
ui_entries.sort(key=lambda e: -e.size)

# Keywords to grep for in each asset
KEYS = [b"@font-face", b"font-family", b"font:", b"src:", b"url(",
        b"Arial Unicode", b"NotoSans", b"M\xe7\x9b\x88", b"Proxima",
        b"Hebrew", b"hebrew", b"Arabic", b"arabic",
        b"locale", b"Locale"]

hits = []
print(f"[*] scanning top {min(200, len(ui_entries))} UI assets for CSS-like text")
for k, e in enumerate(ui_entries[:200]):
    try:
        d = bytes(toc.extract_asset(e))[36:]
    except Exception:
        continue
    if not d: continue
    # Look at first bytes — only continue if it looks textual
    head = d[:16]
    printable = sum(1 for b in head if 0x20 <= b <= 0x7E or b in (0x09, 0x0A, 0x0D))
    if printable < 12:    # not textual
        continue
    found = []
    for key in KEYS:
        c = d.count(key)
        if c:
            found.append((key, c))
    if found:
        hits.append((e.index, e.size, found, d[:200]))

print(f"\n=== {len(hits)} text assets with font/locale keywords ===")
for idx, size, found, head in hits[:30]:
    head_txt = head[:80].decode("utf-8", "replace")
    keys_str = ", ".join(f"{k.decode('utf-8','replace')}={c}" for k, c in found[:6])
    print(f"  idx={idx:<8} size={size:<10} hits: {keys_str}")
    print(f"      head: {head_txt!r}")

# Save the top hits for manual reading
print()
print("=== saving top 5 CSS-candidates to disk ===")
for idx, size, found, _ in hits[:5]:
    e = next((ee for ee in ui_entries if ee.index == idx), None)
    if e is None: continue
    d = bytes(toc.extract_asset(e))[36:]
    outp = os.path.join(OUT, f"ui_text_{idx}.txt")
    with open(outp, "wb") as f: f.write(d)
    print(f"  saved -> {outp}")
