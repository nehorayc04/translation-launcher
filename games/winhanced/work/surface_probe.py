"""Which XBF surface does Winhanced actually render -- the loose .xbf files on
disk, or the copies embedded inside Winhanced.pri?

Both exist, so patching the wrong one changes nothing on screen (the classic
base+patch trap).  This settles it in ONE launch: the same string is replaced
with a DIFFERENT equal-length marker in each surface, so whichever marker shows
up names the winner.  Equal length => delta-0 => no offset math, no rebuild,
byte-for-byte reversible.

    python surface_probe.py --status
    python surface_probe.py --deploy
    python surface_probe.py --revert
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(r"C:\Program Files\Winhanced")
LOOSE = ROOT / "MainWindow.xbf"
PRI = ROOT / "Winhanced.pri"

# The probe string and the two equal-length markers (12 chars each).
TARGET = "Recent Games"
MARK_LOOSE = "LOOSE-XBF-OK"
MARK_PRI = "PRI-EMBED-OK"

TARGETS = [(LOOSE, MARK_LOOSE), (PRI, MARK_PRI)]


def _backup(p: Path) -> Path:
    b = p.with_suffix(p.suffix + ".he_backup")
    if not b.exists():
        shutil.copy2(p, b)
    return b


def _count(data: bytes, s: str) -> int:
    return data.count(s.encode("utf-16le"))


def status() -> None:
    for p, mark in TARGETS:
        d = p.read_bytes()
        b = p.with_suffix(p.suffix + ".he_backup")
        print(
            f"{p.name:<20} size={len(d):>9}  {TARGET!r}x{_count(d, TARGET)}"
            f"  {mark!r}x{_count(d, mark)}  backup={'yes' if b.exists() else 'NO'}"
        )


def deploy() -> int:
    assert len(MARK_LOOSE) == len(MARK_PRI) == len(TARGET), "markers must match length"
    for p, mark in TARGETS:
        d = p.read_bytes()
        n = _count(d, TARGET)
        if n != 1:
            print(f"!! {p.name}: {TARGET!r} occurs {n}x (need exactly 1) -- aborting")
            return 1

    for p, mark in TARGETS:
        _backup(p)
        d = p.read_bytes()
        out = d.replace(TARGET.encode("utf-16le"), mark.encode("utf-16le"))
        assert len(out) == len(d), "delta-0 violated"
        p.write_bytes(out)
        print(f"patched {p.name}: {TARGET!r} -> {mark!r}  (size unchanged {len(out)})")

    print("\nLaunch Winhanced and look at the home screen's 'Recent Games' header:")
    print(f"  '{MARK_LOOSE}'  -> the loose .xbf files on disk are what render")
    print(f"  '{MARK_PRI}'  -> the copies embedded in Winhanced.pri render")
    print(f"  '{TARGET}'  -> neither; the header comes from somewhere else")
    return 0


def revert() -> int:
    for p, _ in TARGETS:
        b = p.with_suffix(p.suffix + ".he_backup")
        if b.exists():
            shutil.copy2(b, p)
            b.unlink()
            print(f"reverted {p.name}")
        else:
            print(f"no backup for {p.name}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    if a.deploy:
        sys.exit(deploy())
    if a.revert:
        sys.exit(revert())
    status()
