"""Extract lobby CSS files, look for HEADER-class font-family declarations."""
import os, sys, re
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
TOC  = os.path.join(GAME, "toc")
OUT  = os.path.join(ROOT, "games", "spiderman2", "extracted", "lobby_css")
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib

with open(TOC, "rb") as f:
    toc = dat1lib.read(f)
toc.set_archives_dir(GAME)

LOBBY_HITS = [61532, 64553, 67776, 72645, 121254, 145502, 152081, 160659,
              183196, 324279, 327909, 389605, 426836]

aid_section = toc.get_assets_section()
for target_idx in LOBBY_HITS:
    e = None
    for idx in range(len(aid_section.ids)):
        ee = toc.get_asset_entry_by_index(idx)
        if ee and ee.index == target_idx:
            e = ee; break
    if not e: continue
    d = bytes(toc.extract_asset(e))[36:]
    outp = os.path.join(OUT, f"lobby_{target_idx}.txt")
    with open(outp, "wb") as f: f.write(d)
    # Grep font-family lines
    famuse = set()
    for m in re.finditer(rb'font-family:\s*"?([^";}]+)"?', d):
        famuse.add(m.group(1).decode("utf-8", "replace").strip())
    print(f"\n=== lobby_{target_idx}.txt  size={len(d)} ===")
    head_txt = d[:120].decode("utf-8", "replace")
    print(f"  head: {head_txt!r}")
    print(f"  font-families used: {sorted(famuse)}")
    # Find lines that mention Header
    headers = re.findall(rb'\.[^{}]*[Hh]eader[^{}]*\{[^}]{0,500}\}', d)
    if headers:
        print(f"  found {len(headers)} 'Header'-class definitions")
        for h in headers[:3]:
            print(f"    {h[:200].decode('utf-8', 'replace')!r}")
