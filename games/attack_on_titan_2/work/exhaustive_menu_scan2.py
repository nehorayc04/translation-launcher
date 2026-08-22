import sys, struct
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from aot2_linkdata import MAGIC, decompress_blocks, is_datatable, parse_datatable, read_cstring

GAME_ROOT = Path(r"F:\Games\Attack on Titan 2")
LD = GAME_ROOT / "LINKDATA"

CANDIDATES = [
    LD / "REGION" / "LINKDATA_REGION_EDEN_JP.BIN",
    LD / "REGION" / "LINKDATA_REGION_EDEN_AS.BIN",
    LD / "LINKDATA_D.BIN",
    LD / "LINKDATA_DLC.BIN",
    LD / "PATCH" / "LINKDATA_PATCH_000.BIN",
    LD / "EX" / "LINKDATA_EX_MASTER.BIN",
    LD / "LINKDATA_PLATFORM_DX11.BIN",
    LD / "LINKDATA_PLATFORM_EDEN_DX11.BIN",
]

MENU_WORDS = {"Story Mode", "Another Mode", "Character Episode Mode",
              "Territory Recovery Mode", "Gallery", "System", "Exit", "Manual"}

def iter_entries(path):
    data = path.read_bytes()
    code, files, mult, pad = struct.unpack_from("<IIII", data, 0)
    if code != MAGIC:
        print(f"  [not a LINKDATA archive, magic={code:#x}]")
        return
    for i in range(files):
        eo, epad, csize, dsize = struct.unpack_from("<IIII", data, 16 + i * 16)
        if csize == 0:
            continue
        start = eo * mult
        raw = data[start:start+csize]
        try:
            content = raw if dsize == 0 else decompress_blocks(raw[8:], dsize)
        except Exception:
            continue
        yield i, content

def flat_strings(content):
    if not is_datatable(content):
        return None
    blobs = parse_datatable(content)
    return [read_cstring(b) if b is not None else None for b in blobs]

def all_tables(content):
    s = flat_strings(content)
    if s is not None:
        yield ("flat", s)
        return
    if len(content) < 4:
        return
    (count,) = struct.unpack_from("<I", content, 0)
    if count == 0 or count > 100000 or 4 + count * 4 > len(content):
        return
    offsets = struct.unpack_from(f"<{count}I", content, 4)
    if any(o < 0 or o >= len(content) for o in offsets):
        return
    for gi, off in enumerate(offsets):
        sub = content[off:]
        s = flat_strings(sub)
        if s is not None:
            yield (f"group{gi}", s)

total_hits = 0
for path in CANDIDATES:
    if not path.exists():
        print(f"[skip missing] {path}")
        continue
    size_mb = path.stat().st_size / (1024*1024)
    print(f"=== {path.name} ({size_mb:.1f} MB) ===", flush=True)
    file_hits = 0
    for idx, content in iter_entries(path):
        for label, strs in all_tables(content):
            for si, s in enumerate(strs):
                if s is not None and s.strip() in MENU_WORDS:
                    file_hits += 1
                    total_hits += 1
                    lo, hi = max(0, si-2), min(len(strs), si+3)
                    ctx = strs[lo:hi]
                    print(f"  entry {idx} [{label}] str {si} = {s!r}")
                    print(f"      context[{lo}:{hi}] = {ctx}")
    print(f"  -> {file_hits} exact hits in this archive", flush=True)
    print()

print(f"TOTAL exact hits: {total_hits}")
print("DONE")
