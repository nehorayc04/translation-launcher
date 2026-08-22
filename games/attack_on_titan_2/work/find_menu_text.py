"""
Locate the main-menu / title-screen UI chrome DataTable, now that we have the
EXACT visible strings from the user's own screenshot of the live game:
  Story Mode / Another Mode / Character Episode Mode / Territory Recovery Mode
  / Gallery / System / Exit / Manual

Scans every REGION_* text archive (base EU/JP/AS + Eden EU/JP/AS) entry-by-
entry for a DataTable containing 2+ of these EXACT strings (a single hit on
a common word like "Exit"/"System" is not enough signal on its own).
"""
from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from aot2_linkdata import MAGIC, is_datatable, parse_datatable, read_cstring  # noqa: E402

ROOT = Path(r"F:\Games\Attack on Titan 2\LINKDATA")

TARGETS = [
    "Story Mode",
    "Another Mode",
    "Character Episode Mode",
    "Territory Recovery Mode",
    "Gallery",
    "System",
    "Exit",
    "Manual",
]

ARCHIVES = [
    ROOT / "REGION" / "LINKDATA_REGION_EU.BIN.he_backup",  # pristine copy, prefer this
    ROOT / "REGION" / "LINKDATA_REGION_JP.BIN",
    ROOT / "REGION" / "LINKDATA_REGION_AS.BIN",
    ROOT / "REGION" / "LINKDATA_REGION_EDEN_EU.BIN",
    ROOT / "REGION" / "LINKDATA_REGION_EDEN_JP.BIN",
    ROOT / "REGION" / "LINKDATA_REGION_EDEN_AS.BIN",
]


def scan_archive(path: Path) -> list[tuple[int, int, list[str]]]:
    if not path.exists():
        # fall back to the live (possibly patched) file if no .he_backup exists
        alt = Path(str(path).replace(".he_backup", ""))
        if not alt.exists():
            print(f"  [skip] {path.name} — not found")
            return []
        path = alt
    data = path.read_bytes()
    code, files, mult, pad = struct.unpack_from("<IIII", data, 0)
    if code != MAGIC:
        print(f"  [skip] {path.name} — bad magic")
        return []
    print(f"Scanning {path.name} ({len(data) / 1e6:.1f} MB, {files} entries) ...")
    hits: list[tuple[int, int, list[str]]] = []
    for i in range(files):
        eo, epad, csize, dsize = struct.unpack_from("<IIII", data, 16 + i * 16)
        start = eo * mult
        raw = data[start : start + csize]
        if not raw:
            continue
        try:
            content = raw if dsize == 0 else zlib.decompress(raw[8:])
        except Exception:
            continue
        if not is_datatable(content):
            continue
        blobs = parse_datatable(content)
        if not blobs:
            continue
        strings = [read_cstring(b) if b is not None else "" for b in blobs]
        sset = set(strings)
        matched = [t for t in TARGETS if t in sset]
        if len(matched) >= 2:
            hits.append((i, len(blobs), matched))
    return hits


def main() -> None:
    for arc in ARCHIVES:
        hits = scan_archive(arc)
        for idx, n, matched in hits:
            print(f"  >>> HIT: entry {idx} ({n} strings) matched {matched}")
        if not hits:
            print("  (no matches)")
        print()


if __name__ == "__main__":
    main()
