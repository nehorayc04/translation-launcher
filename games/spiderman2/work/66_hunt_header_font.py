"""Decompress every text-like userinterface asset and map font-family -> the
largest font-size that uses it. The lobby header is big and still tofu, so its
family is one we have NOT swapped and lives in a COMPRESSED document invisible
to a raw byte grep. This surfaces it."""
import os, sys, re
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib

with open(os.path.join(GAME, "toc"), "rb") as f:
    toc = dat1lib.read(f)
toc.set_archives_dir(GAME)

archs = toc.get_archives_section().archives
ui_arch = None
for i, a in enumerate(archs):
    nm = bytes(a.filename).split(b"\x00")[0].decode("ascii", "replace")
    if nm.endswith("userinterface"):
        ui_arch = i
        break
print(f"[*] userinterface = archive {ui_arch}")

ids = toc.get_assets_section().ids
ui_idxs = []
for idx in range(len(ids)):
    e = toc.get_asset_entry_by_index(idx)
    if e and e.archive == ui_arch:
        ui_idxs.append(idx)
print(f"[*] {len(ui_idxs)} userinterface assets")

fam_re = re.compile(rb'font-family:\s*"([^"]{1,48})"')
fsz_re = re.compile(rb'font-size:\s*([0-9.]+)vh')
ff_re  = re.compile(rb'@font-face')

# family -> (max_vh, asset_index)
fam_max = {}
# all @font-face src urls seen
src_urls = {}
processed = 0
for idx in ui_idxs:
    e = toc.get_asset_entry_by_index(idx)
    try:
        d = bytes(toc.extract_asset(e))
    except Exception:
        continue
    if b"font-family" not in d and b"@font-face" not in d:
        continue
    processed += 1
    # @font-face urls
    for m in re.finditer(rb'url\("?([^")]{1,90}\.(?:ttf|otf|ttc))"?\)', d, re.I):
        u = m.group(1).decode("latin-1")
        src_urls.setdefault(u, idx)
    # font-family with nearest preceding font-size in same ~200 bytes
    for m in fam_re.finditer(d):
        fam = m.group(1).decode("latin-1")
        back = d[max(0, m.start()-220):m.start()]
        sizes = fsz_re.findall(back)
        vh = 0.0
        if sizes:
            try: vh = float(sizes[-1])
            except: vh = 0.0
        cur = fam_max.get(fam)
        if cur is None or vh > cur[0]:
            fam_max[fam] = (vh, idx)

print(f"[*] processed {processed} text assets\n")
print("=== font-family -> max font-size(vh) seen, asset idx ===")
for fam, (vh, idx) in sorted(fam_max.items(), key=lambda x: -x[1][0]):
    print(f"  {vh:>7.2f}vh   {fam!r:<34} (asset {idx})")

print("\n=== ALL @font-face url() font files referenced (decompressed) ===")
for u, idx in sorted(src_urls.items()):
    print(f"  asset {idx:>8}  {u!r}")
