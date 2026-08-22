"""
Round 2 — the strict DataTable+exact-string scan (find_menu_text.py) found
ZERO hits across all 6 REGION archives. Broaden: raw ASCII byte-substring
search (both an ASCII and a UTF-16LE variant) across EVERY entry of EVERY
archive, independent of DataTable well-formedness — in case the menu labels
live in a different sub-format, or the encoding differs from the dialogue
tables. Reports which ARCHIVE + ENTRY index contains which target word, with
a small context window so a hit can be told apart from a coincidental match.
"""
from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from aot2_linkdata import MAGIC  # noqa: E402

ROOT = Path(r"F:\Games\Attack on Titan 2\LINKDATA")

# distinctive words unlikely to appear by accident
NEEDLES_ASCII = [b"Story Mode", b"Another Mode", b"Territory Recovery", b"Gallery", b"Manual"]
NEEDLES_UTF16 = [n.decode("ascii").encode("utf-16-le") for n in NEEDLES_ASCII]

ARCHIVES = [
    ROOT / "REGION" / "LINKDATA_REGION_EU.BIN.he_backup",
    ROOT / "REGION" / "LINKDATA_REGION_JP.BIN",
    ROOT / "REGION" / "LINKDATA_REGION_AS.BIN",
    ROOT / "REGION" / "LINKDATA_REGION_EDEN_EU.BIN",
    ROOT / "REGION" / "LINKDATA_REGION_EDEN_JP.BIN",
    ROOT / "REGION" / "LINKDATA_REGION_AS.BIN",
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
        for n in NEEDLES_ASCII:
            if n in content:
                pos = content.find(n)
                ctx = content[max(0, pos - 20) : pos + 40]
                print(f"  >>> ASCII hit: entry {i} word={n!r} ctx={ctx!r}")
                any_hit = True
        for n in NEEDLES_UTF16:
            if n in content:
                pos = content.find(n)
                ctx = content[max(0, pos - 20) : pos + 60]
                print(f"  >>> UTF16 hit: entry {i} word={n!r} ctx={ctx!r}")
                any_hit = True
    if not any_hit:
        print("  (no matches)")
    print()


def main() -> None:
    for arc in ARCHIVES:
        scan_archive(arc)


if __name__ == "__main__":
    main()
