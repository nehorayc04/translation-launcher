"""
Round 3 — round 1/2's scans used the OLD single-shot zlib.decompress(), which
SILENTLY TRUNCATES any entry whose decompressed size exceeds one 32768-byte
block (see aot2_linkdata.decompress_blocks + the module docstring). This is
the correct-decompression version: full per-entry decode via
decompress_blocks(), raw ASCII substring search for "System"/"Exit" — two
words that returned ZERO hits when I searched exactly within REGION_EDEN_EU's
entry-0 master table, meaning the real title-screen table is elsewhere.
"""
from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from aot2_linkdata import MAGIC, decompress_blocks  # noqa: E402

ROOT = Path(r"F:\Games\Attack on Titan 2\LINKDATA")

NEEDLES = [b"System", b"Exit", b"Story Mode", b"Gallery", b"Manual"]

ARCHIVES = [
    ROOT / "REGION" / "LINKDATA_REGION_EU.BIN.he_backup",
    ROOT / "REGION" / "LINKDATA_REGION_JP.BIN",
    ROOT / "REGION" / "LINKDATA_REGION_AS.BIN",
    ROOT / "REGION" / "LINKDATA_REGION_EDEN_EU.BIN",
    ROOT / "REGION" / "LINKDATA_REGION_EDEN_JP.BIN",
    ROOT / "REGION" / "LINKDATA_REGION_EDEN_AS.BIN",
    ROOT / "LINKDATA_D.BIN",
    ROOT / "EX" / "LINKDATA_EX_MASTER.BIN",
    ROOT / "LINKDATA_PLATFORM_DX11.BIN",
    ROOT / "LINKDATA_PLATFORM_EDEN_DX11.BIN",
]


def scan_archive(path: Path) -> None:
    if not path.exists():
        alt = Path(str(path).replace(".he_backup", ""))
        if not alt.exists():
            print(f"  [skip] {path.name} (and non-backup variant) — not found")
            return
        path = alt
    data = path.read_bytes()
    code, files, mult, pad = struct.unpack_from("<IIII", data, 0)
    if code != MAGIC:
        print(f"  [skip] {path.name} — bad magic")
        return
    print(f"Scanning {path.name} ({len(data) / 1e6:.1f} MB, {files} entries) ...")
    any_hit = False
    fail = 0
    for i in range(files):
        eo, epad, csize, dsize = struct.unpack_from("<IIII", data, 16 + i * 16)
        start = eo * mult
        raw = data[start : start + csize]
        if not raw:
            continue
        if dsize == 0:
            content = raw
        else:
            try:
                content = decompress_blocks(raw[8:], dsize)
            except Exception:
                fail += 1
                continue
        for n in NEEDLES:
            if n in content:
                pos = content.find(n)
                ctx = content[max(0, pos - 30) : pos + 40]
                print(f"  >>> entry {i} word={n!r} ctx={ctx!r}")
                any_hit = True
    if not any_hit:
        print("  (no matches)")
    if fail:
        print(f"  ({fail} entries failed to decompress — likely non-text binary, not a problem)")
    print()


def main() -> None:
    for arc in ARCHIVES:
        scan_archive(arc)


if __name__ == "__main__":
    main()
