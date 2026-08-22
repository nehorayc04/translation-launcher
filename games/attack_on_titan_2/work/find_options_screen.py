"""Search for the Options/Settings screen strings the user just screenshotted
(Difficulty / Control Assistance / Gore Level / Slow Motion During Battle /
Vibration / Extra-wall Map Speed / Skip Journey Events / Voice Chat /
Default Network Settings / Preferred Input Method / tab names)."""
import sys, struct
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from aot2_linkdata import MAGIC, decompress_blocks, is_datatable, parse_datatable, read_cstring

GAME_ROOT = Path(r"F:\Games\Attack on Titan 2")
LD = GAME_ROOT / "LINKDATA"

CANDIDATES = [
    LD / "REGION" / "LINKDATA_REGION_EU.BIN",
    LD / "REGION" / "LINKDATA_REGION_EDEN_EU.BIN",
]

WORDS = {"Difficulty", "Control Assistance", "Gore Level",
         "Slow Motion During Battle", "Vibration", "Extra-wall Map Speed",
         "Skip Journey Events", "Voice Chat", "Default Network Settings",
         "Preferred Input Method", "Game 1", "Game 2", "Controls", "Camera",
         "Audio", "Graphics 1", "Graphics 2", "Keyboard and Mouse", "Easy"}

def iter_entries(path):
    data = path.read_bytes()
    code, files, mult, pad = struct.unpack_from("<IIII", data, 0)
    if code != MAGIC:
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

for path in CANDIDATES:
    print(f"=== {path.name} ===")
    for idx, content in iter_entries(path):
        for label, strs in all_tables(content):
            hits = [(si, s) for si, s in enumerate(strs) if s is not None and s.strip() in WORDS]
            if len(hits) >= 3:  # a real cluster, not a coincidence
                print(f"  entry {idx} [{label}]: {len(hits)} hits, {len(strs)} strings total")
                for si, s in hits[:10]:
                    print(f"      [{si}] {s!r}")
    print()
