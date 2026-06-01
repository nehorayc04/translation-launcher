"""Inspect spans (TOC2 variant grouping) for localization_all."""
import os, sys, struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
TOC  = os.path.join(GAME, "toc")
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))

import dat1lib

with open(TOC, "rb") as f:
    toc = dat1lib.read(f)
toc.set_archives_dir(GAME)

spans = toc.get_spans_section()
print("[*] spans attrs:", [m for m in dir(spans) if not m.startswith("_")])
print("[*] spans count:", len(getattr(spans, "spans", [])) if hasattr(spans, "spans") else "?")

if hasattr(spans, "spans") and spans.spans:
    print("[*] first span attrs:", [m for m in dir(spans.spans[0]) if not m.startswith("_")])
    print()
    print("=== first 15 spans ===")
    for i, s in enumerate(spans.spans[:15]):
        print(f"  [{i:3}] {vars(s)}")

# Pull every entry tied to localization_all
entries = toc.get_asset_entries_by_path("localization/localization_all.localization")
print()
print(f"[+] {len(entries)} entries for localization_all")
print()
print("=== all 32 entries: index, archive, offset, size ===")
for e in entries:
    print(f"  index={e.index:7}  archive={e.archive:3}  offset={e.offset:10}  size={e.size:9}")

# For TOC2 the language slot is usually tied to the entry's index inside a span range.
# Print sizes() and offsets() raw counts.
sizes = toc.get_sizes_section()
offsets = toc.get_offsets_section()
print()
print("[*] sizes section count:", len(getattr(sizes, "entries", getattr(sizes, "sizes", []))))
print("[*] offsets section count:", len(getattr(offsets, "entries", getattr(offsets, "offsets", []))))
