"""Extract the two documents that declare the lowercase @font-face families
(331186, 414413). Reveal: which element/header uses azbukapro_regular, the
exact @font-face family name, css <link> hrefs and image url() paths (those
expose the document's base dir so we can resolve ../fonts/<file> -> asset)."""
import os, sys, re
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib

with open(os.path.join(GAME, "toc"), "rb") as f:
    toc = dat1lib.read(f)
toc.set_archives_dir(GAME)

for idx in (331186, 414413):
    e = toc.get_asset_entry_by_index(idx)
    d = bytes(toc.extract_asset(e))
    print("=" * 72)
    print(f"asset {idx}  size={len(d)}  head={d[:4].hex()}")
    print("=" * 72)
    # path-revealing strings: href=, url(, .html, .css, authored/, coui
    for pat in (rb'href="[^"]{1,90}"', rb'url\("?[^")]{1,90}"?\)',
                rb'[A-Za-z0-9_/\-]{4,90}\.(?:html|css)',
                rb'authored/[ -~]{2,80}', rb'@font-face[ -~]{0,90}',
                rb'font-family:\s*"[^"]{1,40}"'):
        hits = []
        seen = set()
        for m in re.finditer(pat, d):
            s = m.group().decode("latin-1")
            if s not in seen:
                seen.add(s); hits.append((m.start(), s))
        if hits:
            label = pat.decode("latin-1")[:20]
            print(f"\n  -- pattern {label!r} ({len(hits)}) --")
            for off, s in hits[:25]:
                print(f"    [{off:>8}] {s!r}")
    print()
