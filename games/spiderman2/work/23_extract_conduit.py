"""1. Search dagstr for 'uiresources/' paths.
2. List all assets in archive 'conduit' via TOC, extract them, find any that
   look like font files (OTF/TTF/TTC magic at offset 0)."""
import os, sys, struct
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
TOC  = os.path.join(GAME, "toc")
OUT  = os.path.join(ROOT, "games", "spiderman2", "extracted", "conduit_assets")
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib

# 1. dagstr for 'uiresources' / 'coui://' style paths
print("=== dagstr search ===")
DAGSTR = os.path.join(GAME, "dagstr")
data = open(DAGSTR, "rb").read()
for needle in (b"uiresources", b"UIResources", b"UIResource", b"_mocked_",
               b"coui:", b"cohtml", b"_fontset", b"_fontconfig"):
    c = data.count(needle)
    if c:
        print(f"  {needle!r}: {c} hits")
        i = 0; shown = 0
        while shown < 5:
            j = data.find(needle, i)
            if j < 0: break
            start = j
            while start > 0 and data[start-1] != 0:
                start -= 1
            end = data.find(b"\x00", j)
            if end < 0: end = j+200
            s = data[start:end].decode("utf-8", "replace")
            if 0 < len(s) < 300:
                print(f"    {s!r}")
                shown += 1
            i = end + 1

# 2. Find d/conduit's archive index in TOC, then list+extract its assets
print()
print("=== extract conduit assets ===")
with open(TOC, "rb") as f:
    toc = dat1lib.read(f)
toc.set_archives_dir(GAME)

archs = toc.get_archives_section()
conduit_arch = None
for i, a in enumerate(archs.archives):
    name = bytes(a.filename).split(b"\x00")[0].decode("ascii")
    if name.endswith("conduit") or name.endswith("\\conduit"):
        conduit_arch = i
        print(f"  conduit archive index = {i}  (filename: {name})")
        break

if conduit_arch is None:
    print("[!] conduit archive not found")
    sys.exit(0)

# Walk all asset entries and pull those in conduit_arch
aid_section = toc.get_assets_section()
offsets = toc.get_offsets_section()
sizes = toc.get_sizes_section()

# size entries are u32 — get raw and parse
size_entries = sizes.entries if hasattr(sizes, 'entries') else None
offset_entries = offsets.entries if hasattr(offsets, 'entries') else None
print(f"  sizes type: {type(size_entries)} count: {len(size_entries) if size_entries else '?'}")
print(f"  offsets type: {type(offset_entries)} count: {len(offset_entries) if offset_entries else '?'}")

if offset_entries and size_entries:
    # offset entry has archive_index + offset
    conduit_assets = []
    for idx, off_ent in enumerate(offset_entries):
        if hasattr(off_ent, 'archive_index'):
            if off_ent.archive_index == conduit_arch:
                conduit_assets.append((idx, off_ent.offset))
    print(f"  found {len(conduit_assets)} entries in conduit archive (by offset section)")

# Alternative: iterate all asset entries and filter by archive
ENTRIES = []
for idx in range(len(aid_section.ids)):
    e = toc.get_asset_entry_by_index(idx)
    if e is not None and e.archive == conduit_arch:
        ENTRIES.append(e)
print(f"  via get_asset_entry_by_index: {len(ENTRIES)} entries in conduit archive")

# Extract each, look at the first 8 bytes
print()
print("=== extracting and classifying first few conduit assets ===")
FONT_MAGICS = (b"OTTO", b"\x00\x01\x00\x00", b"ttcf", b"wOFF", b"wOF2")
DAT1_MAGIC = b"\x44\x41\x54\x31"  # "DAT1"
saved = 0
font_candidates = []
for k, e in enumerate(ENTRIES[:500]):
    try:
        d = toc.extract_asset(e)
    except Exception as ex:
        continue
    if not d: continue

    # Skip the 36-byte AssetEntry.header to get the real asset content
    content = bytes(d[36:]) if len(d) >= 36 else bytes(d)
    head = content[:8]
    is_font = any(content.startswith(m) for m in FONT_MAGICS)
    is_dat1 = content.startswith(DAT1_MAGIC)
    if is_font:
        font_candidates.append((e, len(content), head))
        print(f"  [FONT?] idx={e.index} size={len(content)} head={head.hex()} -> {head}")
        # save it
        outp = os.path.join(OUT, f"conduit_asset_{e.index}_{head.decode('ascii', 'replace')[:4]}.bin")
        with open(outp, "wb") as wf:
            wf.write(content)
        saved += 1
    elif k < 5 or (k % 100 == 0):
        kind = "DAT1" if is_dat1 else "?"
        print(f"  [{k:3}] idx={e.index} size={len(content):>8} head={head.hex()}  ({kind})")

print()
print(f"[+] {len(font_candidates)} font candidates found in conduit archive")
print(f"[+] {saved} extracted to {OUT}")
