"""Dump the full 'fontmap' region in d/config — list every font file the
UI registers + the asset path prefix, so we can locate the Arabic font asset
(NeueFrutigerArabic) and plan its replacement."""
import os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
buf = open(os.path.join(GAME, "d", "config"), "rb").read()

# All readable strings mentioning fonts in the whole config archive
print("=== every .ttf / .otf / fonts/ path string in d/config ===")
seen = set()
for m in re.finditer(rb"[ -~]{4,200}", buf):
    s = m.group()
    if (b".ttf" in s or b".otf" in s or b"fonts/" in s or b"fontmap" in s
            or b"NeueFrutiger" in s or b"Avenir" in s):
        txt = s.decode("latin-1")
        if txt not in seen:
            seen.add(txt)
            print(f"  [{m.start():>9}] {txt!r}")

print("\n=== raw window around the fontmap (8746000..8760500) ===")
region = buf[8746000:8760500]
for m in re.finditer(rb"[ -~]{3,}", region):
    print(f"  [{8746000+m.start():>9}] {m.group().decode('latin-1')!r}")
