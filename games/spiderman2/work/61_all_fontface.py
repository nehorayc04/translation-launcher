"""Enumerate EVERY font reference across the UI data. We replaced all 6
_common/fonts faces yet the lobby header is still tofu -> a 7th font draws it.
Find every @font-face / url(...ttf/otf) and every font filename token in
d/userinterface + d/config so nothing is missed."""
import os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")

url_re = re.compile(rb'url\("?([^")]{1,80}\.(?:ttf|otf|ttc|woff2?))"?\)', re.I)
file_re = re.compile(rb'[ -~]{0,60}?([A-Za-z0-9_\-]{2,40}\.(?:ttf|otf|ttc))', re.I)
fontface_re = re.compile(rb'@font-face')
famsrc_re = re.compile(rb'font-family:\s*"([^"]{1,40})"', re.I)

for arch in ("userinterface", "config"):
    path = os.path.join(GAME, "d", arch)
    buf = open(path, "rb").read()
    print("\n" + "#" * 70)
    print(f"# d/{arch}  ({len(buf):,} bytes)")
    print("#" * 70)

    print(f"  @font-face blocks: {len(fontface_re.findall(buf))}")

    print("\n  -- url(...) font references --")
    seen = set()
    for m in url_re.finditer(buf):
        u = m.group(1).decode("latin-1")
        if u not in seen:
            seen.add(u)
            print(f"    [{m.start():>9}] {u!r}")

    print("\n  -- every *.ttf/*.otf filename token --")
    seen = set()
    for m in re.finditer(rb'([A-Za-z0-9_\-]{2,40}\.(?:ttf|otf|ttc))', buf):
        u = m.group(1).decode("latin-1")
        if u not in seen:
            seen.add(u)
            print(f"    [{m.start():>9}] {u!r}")

    if arch == "userinterface":
        print("\n  -- every distinct font-family name --")
        fams = {}
        for m in famsrc_re.finditer(buf):
            f = m.group(1).decode("latin-1")
            fams[f] = fams.get(f, 0) + 1
        for f, c in sorted(fams.items(), key=lambda x: -x[1]):
            print(f"    {c:>4}x  {f!r}")
