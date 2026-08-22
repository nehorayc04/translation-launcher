"""Extract Proxima Nova Regular+Bold from the R&C toc and report the exact deploy
params (global size-entry index, span, header_offset, size-entry value) needed to
override each font via the SM2 native applier's (span, asset_id) .stage mechanism.
Read-only against the game."""
import os, sys, struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = r"F:\Game Lab\Ratchet & Clank - Rift Apart"
TOC  = os.path.join(GAME, "toc")
OUT  = os.path.join(HERE, "fonts")
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import dat1lib, dat1lib.types.dat1 as _d1

FONTS = {
    "proximanova_regular_normal.ttf": 0xA2197874D2B7B1AC,
    "proximanova_bold_normal.ttf":    0xB5F411285669C55D,
}
LOC_AID = 0xBE55D94F171BF8DE

with open(TOC, "rb") as f:
    t = dat1lib.read(f)
t.dat1.set_recalculation_strategy(_d1.RECALCULATE_ORIGINAL_ORDER)
t.set_archives_dir(GAME)

spans  = t.get_spans_section()
assets = t.get_assets_section()
ids    = getattr(assets, "ids", None) or getattr(assets, "values", None) or []
sizes  = t.get_sizes_section()
archs  = t.get_archives_section()

def span_for_index(gi):
    for si, sp in enumerate(spans.entries):
        if sp.asset_index <= gi < sp.asset_index + sp.count:
            return si
    return -1

def report(name, aid, extract=False):
    # find global indices where ids[i]==aid
    hits = [i for i,x in enumerate(ids) if x == aid]
    print(f"\n=== {name}  aid=0x{aid:016X}  ({len(hits)} occurrence(s)) ===")
    for gi in hits[:4]:
        se = sizes.entries[gi]
        sp = span_for_index(gi)
        arc = archs.archives[se.archive_index]
        try: arcname = bytes(arc.filename).split(b"\x00")[0].decode("ascii","ignore")
        except Exception: arcname = "?"
        print(f"  index={gi} span={sp} archive_index={se.archive_index}({arcname}) offset={se.offset} value={se.value} header_offset={se.header_offset}")
    if extract and hits:
        gi = hits[0]
        entries = t.get_asset_entries_by_path("ui/loaded/authored/_common/fonts/" + name)
        entries = [e for e in (entries or []) if e is not None]
        data = None
        if entries:
            try: data = t.extract_asset(entries[0])
            except Exception as ex: print("   extract by entry err:", ex)
        if data is None:
            try: data = t.extract_asset(gi)
            except Exception as ex: print("   extract by index err:", ex)
        if data:
            op = os.path.join(OUT, name)
            open(op, "wb").write(data)
            magic = data[:4].hex()
            print(f"   extracted {len(data)} bytes, magic={magic} ({'raw sfnt TTF' if magic=='00010000' else 'NOT bare TTF'}) -> {op}")
            print(f"   size-entry value {sizes.entries[gi].value} vs len {len(data)}  (delta {len(data)-sizes.entries[gi].value:+d})")
    return hits

# loc for reference
report("localization/localization_all.localization", LOC_AID)
# fonts
for nm, aid in FONTS.items():
    report(nm, aid, extract=True)

print("\n[deploy note] .stage entry name = '{span}/{HEXID}'. blob for a font = the raw TTF"
      " (header_offset==-1 → no separate header). blob for the loc = DAT1 with the 36-byte"
      " header STRIPPED (header_offset!=-1 → engine re-prepends it).")
