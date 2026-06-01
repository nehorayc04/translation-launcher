"""Locate the span containing the Arabic asset entry (index 1276510) and
also map all 31 entries → spans, so we know exactly which span(s) the game
selects for each language."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
TOC  = os.path.join(GAME, "toc")
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib

with open(TOC, "rb") as f:
    toc = dat1lib.read(f)
spans = toc.get_spans_section().entries
print(f"[+] {len(spans)} spans total")

def span_for_index(asset_index):
    for s_idx, sp in enumerate(spans):
        if sp.count == 0: continue
        if sp.asset_index <= asset_index < sp.asset_index + sp.count:
            return s_idx, asset_index - sp.asset_index
    return None, None

entries = [e for e in toc.get_asset_entries_by_path("localization/localization_all.localization") if e is not None]
print(f"[+] {len(entries)} localization_all entries")
print()
print(f"=== span mapping for every localization_all entry ===")
print(f"{'#':>2}  {'asset_idx':>10}  {'span':>4}  {'pos_in_span':>11}  size")
for i, e in enumerate(entries):
    s, pos = span_for_index(e.index)
    print(f"  {i:>2}  {e.index:>10}  {s if s is not None else '--':>4}  {pos if pos is not None else '--':>11}  {e.size}")

print()
print("=== summary ===")
ARABIC_INDEX = 1276510
s, pos = span_for_index(ARABIC_INDEX)
print(f"Arabic entry (index={ARABIC_INDEX}) is in span={s}, offset_in_span={pos}")
if s is not None:
    print(f"Span {s}: asset_index={spans[s].asset_index}, count={spans[s].count}")
