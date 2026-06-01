"""Extract all variant entries of localization_all.localization and byte-sniff
which one is the Arabic version (Hebrew-target slot)."""
import os, sys, struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
TOC  = os.path.join(GAME, "toc")
OUT  = os.path.join(ROOT, "games", "spiderman2", "extracted", "loc_variants")
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))

import dat1lib

with open(TOC, "rb") as f:
    toc = dat1lib.read(f)
toc.set_archives_dir(GAME)

entries = [e for e in toc.get_asset_entries_by_path("localization/localization_all.localization") if e is not None]
print(f"[+] {len(entries)} variants to extract")

# Script-bucket sniffer for the .localization payload. Skips the file header,
# then walks the data looking for UTF-8 byte runs of each script.
def sniff_scripts(buf: bytes) -> dict:
    counts = {"arabic": 0, "cyrillic": 0, "latin_extended": 0, "cjk": 0,
              "hiragana": 0, "katakana": 0, "hangul": 0, "thai": 0,
              "devanagari": 0, "ascii_only": 0}
    # walk every byte; we care about ranges of starting UTF-8 lead bytes
    i = 0
    n = len(buf)
    ascii_chars = 0
    while i < n:
        b = buf[i]
        if b < 0x80:
            ascii_chars += 1
            i += 1
        elif b < 0xC0:
            i += 1  # continuation, skip
        elif b < 0xE0 and i+1 < n:
            cp = ((b & 0x1F) << 6) | (buf[i+1] & 0x3F)
            if 0x0600 <= cp <= 0x06FF: counts["arabic"] += 1
            elif 0x0400 <= cp <= 0x04FF: counts["cyrillic"] += 1
            elif 0x0100 <= cp <= 0x024F: counts["latin_extended"] += 1
            i += 2
        elif b < 0xF0 and i+2 < n:
            cp = ((b & 0x0F) << 12) | ((buf[i+1] & 0x3F) << 6) | (buf[i+2] & 0x3F)
            if 0x3040 <= cp <= 0x309F: counts["hiragana"] += 1
            elif 0x30A0 <= cp <= 0x30FF: counts["katakana"] += 1
            elif 0xAC00 <= cp <= 0xD7AF: counts["hangul"] += 1
            elif 0x0E00 <= cp <= 0x0E7F: counts["thai"] += 1
            elif 0x0900 <= cp <= 0x097F: counts["devanagari"] += 1
            elif 0x4E00 <= cp <= 0x9FFF: counts["cjk"] += 1
            i += 3
        else:
            i += 4
    counts["ascii_only"] = ascii_chars
    return counts

# Loop: dump every variant via dat1lib.types.toc2.TOC2.extract_asset(asset_id, index)
# extract_asset(asset_id, target_path) — signature differs; let me check
import inspect
print("[*] extract_asset signature:", inspect.signature(toc.extract_asset))

# We'll bypass extract_asset and read the archive manually using known archive name + offset + size
arch_section = toc.get_archives_section()
arch170 = arch_section.archives[170]
arch_name = bytes(arch170.filename).split(b"\x00")[0].decode("ascii")
arch_path = os.path.join(GAME, arch_name)
print(f"[*] archive #170 path: {arch_path} exists={os.path.exists(arch_path)} size={os.path.getsize(arch_path)}")
print()

# Each entry points at a DSAR chunk header (offset is within the archive file).
# The archive is a DSAR container — we need dsar to decompress to get the raw .localization.
# But: ALERT exposes toc.extract_asset which already handles DSAR. Use that.
from io import BytesIO

# Build a small helper that uses dat1lib's read_asset_data if it exists; otherwise the TOC method.
results = []
for k, e in enumerate(entries):
    out_path = os.path.join(OUT, f"variant_{k:02d}_idx{e.index}.localization")
    try:
        data = toc.extract_asset(e)
    except Exception as ex:
        print(f"  [{k:02d}] extract_asset(entry) error: {ex}")
        try:
            data = toc.extract_asset(e.index)
        except Exception as ex2:
            print(f"  [{k:02d}] extract_asset(index) error: {ex2}")
            continue

    if not data:
        print(f"  [{k:02d}] empty data (asset_id={e.asset_id})")
        continue

    with open(out_path, "wb") as f:
        f.write(data)
    counts = sniff_scripts(data[:200000] if len(data) > 200000 else data)  # cheap sample
    magic = data[:4].hex()
    results.append((k, e.index, len(data), magic, counts, out_path))
    print(f"  [{k:02d}] idx={e.index:7} size={len(data):9} magic={magic}  scripts={ {k:v for k,v in counts.items() if v>50} }")

print()
print("=== ranking by Arabic-codepoint count ===")
for r in sorted(results, key=lambda r: -r[4]["arabic"]):
    print(f"  variant_{r[0]:02d} arabic_cps={r[4]['arabic']:6}  size={r[2]:8}  -> {os.path.basename(r[5])}")
