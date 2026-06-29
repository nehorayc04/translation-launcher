"""
Watch Dogs 2 — native Hebrew-mod applier (fat-redirect, no Overstrike / mod
manager). Python reimplementation of the proven `games/watchdogs2/work/
wd2_archive.py` deploy, hardened for shipping inside the launcher.

WD2 (Ubisoft Disrupt, FAT5 v11) stores assets across load-ordered archives
`common < patch < patch2` — each a `<name>.fat` index + `<name>.dat` blob under
`<game>/data_win64/`. We install the Hebrew translation by, for each of the 3
shipped files (localization `.loc` + the Hebrew font `.ffd` + its atlas `.xbt`):

  1. APPEND the file's bytes to every archive's `.dat`, and
  2. REWRITE that asset's `.fat` entry to point at the new offset, stored
     uncompressed (v11 stored ⇒ UncompressedSize=0).

Fully reversible: each `.fat` is backed up ONCE and the `.dat`'s original size
recorded; `revert()` restores the `.fat` and truncates the `.dat`. Backups + an
apply marker live OUTSIDE the game folder (the launcher's app-data cache) so a
Program-Files install with no writable backup subfolder still reverts cleanly.

Activation is in-game (Settings → Written Language = العربية / Arabic) — the
Hebrew rides the Arabic RTL slot — so this applier does NOT touch any game
setting; only the 3 asset files. Never raises out of the public API.
"""

from __future__ import annotations

import json
import os
import shutil
import struct
from pathlib import Path
from typing import Callable

ProgressCB = Callable[[str, float, str], None]

ARCHIVES = ("common", "patch", "patch2")     # load order low → high
_M64 = 0xFFFFFFFFFFFFFFFF
_MARKER = "wd2_he_applied.json"              # under the backup dir → is_applied()

# The 3 files we ship → their in-archive paths (the asset keys we redirect).
# `local` names match the bundled files under assets/watchdogs2/.
TARGETS: tuple[tuple[str, str], ...] = (
    ("main_arabic.loc", r"languages\main_arabic.loc"),
    ("heb_font.ffd",    r"ui\fonts\helveticaneuelt_w1g_65_md_arabic.ffd"),
    ("heb_font.xbt",    r"ui\fonts\helveticaneuelt_w1g_65_md_arabic_1.xbt"),
)


# ─────────────────────────────────────────────────────────────
# FAT5 helpers (FNV-1a name hash + 20-byte entry layout)
# ─────────────────────────────────────────────────────────────
def _fnv1a(s: str) -> int:
    h = 0xCBF29CE484222325
    for c in s:
        h = (h * 0x100000001B3) & _M64
        h ^= ord(c)
    return h


def _name_hash(path: str) -> int:
    h = _fnv1a(path.lower())
    h &= 0x1FFFFFFFFFFFFFFF
    h |= 0xA000000000000000
    return h


def _find_entry(fat_bytes: bytes, want_hash: int):
    """Return (fatpos, comp, off, unc, scheme) for want_hash, or None."""
    if len(fat_bytes) < 28:
        return None
    cnt = struct.unpack_from("<I", fat_bytes, 24)[0]
    for i in range(cnt):
        p = 28 + i * 20
        if p + 20 > len(fat_bytes):
            break
        a = struct.unpack_from("<Q", fat_bytes, p)[0]
        if a == want_hash:
            b, c, d = struct.unpack_from("<III", fat_bytes, p + 8)
            comp = b & 0x3FFFFFFF
            off = (c << 2) | ((b >> 30) & 3)
            unc = (d >> 2) & 0x3FFFFFFF
            return (p, comp, off, unc, d & 3)
    return None


def _data_dir(game_root: Path) -> Path:
    return Path(game_root) / "data_win64"


def _tag(rel_path: str) -> str:
    return rel_path.replace("\\", "_").replace("/", "_")


# ─────────────────────────────────────────────────────────────
# Per-archive deploy / revert
# ─────────────────────────────────────────────────────────────
def _deploy_one(data: Path, backup: Path, rel_path: str, payload_path: Path) -> int:
    """Redirect `rel_path` to `payload_path` across all archives that hold it.
    Backs up each `.fat` once + records the `.dat` original size. Returns the
    number of archives actually redirected."""
    h = _name_hash(rel_path)
    payload = Path(payload_path).read_bytes()
    L = len(payload)
    tag = _tag(rel_path)
    redirected = 0
    for name in ARCHIVES:
        fatp = data / (name + ".fat")
        datp = data / (name + ".dat")
        if not (fatp.is_file() and datp.is_file()):
            continue
        e = _find_entry(fatp.read_bytes(), h)
        if not e:
            continue                                   # this archive lacks the asset
        fatpos = e[0]
        fbk = backup / f"{name}.fat.{tag}.bak"
        szf = backup / f"{name}.dat.{tag}.origsize"
        if not fbk.exists():                           # capture the TRUE original once
            shutil.copy2(fatp, fbk)
            szf.write_text(str(datp.stat().st_size), encoding="utf-8")
        with open(datp, "r+b") as f:
            f.seek(0, 2)
            pos = f.tell()
            pad = (16 - (pos % 16)) % 16
            if pad:
                f.write(b"\x00" * pad)
                pos += pad
            newoff = pos
            f.write(payload)
        fat = bytearray(fatp.read_bytes())
        nb = (L & 0x3FFFFFFF) | ((newoff & 3) << 30)
        nc = newoff >> 2
        nd = 0                                         # unc=0, scheme=None (v11 stored)
        struct.pack_into("<III", fat, fatpos + 8, nb, nc, nd)
        fatp.write_bytes(fat)
        redirected += 1
    return redirected


def _revert_one(data: Path, backup: Path, rel_path: str) -> None:
    tag = _tag(rel_path)
    for name in ARCHIVES:
        fbk = backup / f"{name}.fat.{tag}.bak"
        szf = backup / f"{name}.dat.{tag}.origsize"
        if not (fbk.is_file() and szf.is_file()):
            continue
        datp = data / (name + ".dat")
        fatp = data / (name + ".fat")
        try:
            shutil.copy2(fbk, fatp)
            with open(datp, "r+b") as f:
                f.truncate(int(szf.read_text(encoding="utf-8").strip()))
        finally:
            # Drop the backups so is_applied() flips False and a future apply
            # re-captures the (now-original) .fat.
            for b in (fbk, szf):
                try:
                    b.unlink()
                except OSError:
                    pass


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────
def is_applied(backup_dir) -> bool:
    return (Path(backup_dir) / _MARKER).is_file()


def apply(game_root, payload_map: list, backup_dir, cb: ProgressCB | None = None) -> dict:
    """Deploy the Hebrew mod. `payload_map` = [(payload_path, rel_path), …].
    Returns {ok, count, error}. Idempotent: re-applying first reverts a prior
    apply (so we never stack offsets / lose the true-original backup)."""
    data = _data_dir(game_root)
    if not data.is_dir():
        return {"ok": False, "error": "תיקיית data_win64 לא נמצאה — ודא את נתיב ההתקנה של המשחק"}
    backup = Path(backup_dir)
    try:
        # Clean slate so a re-install can't append on top of a prior redirect.
        if is_applied(backup):
            revert(game_root, backup)
        backup.mkdir(parents=True, exist_ok=True)
        n = max(1, len(payload_map))
        total_redirected = 0
        applied_targets: list[str] = []
        for i, (pp, rel) in enumerate(payload_map):
            if cb:
                cb("apply", 5.0 + 90.0 * i / n, f"מחיל קובץ {i + 1}/{len(payload_map)}…")
            r = _deploy_one(data, backup, rel, Path(pp))
            if r > 0:
                total_redirected += r
                applied_targets.append(rel)
        if total_redirected == 0:
            return {"ok": False,
                    "error": "אף קובץ לא תאם לארכיוני המשחק (ייתכן שהמשחק עודכן)"}
        (backup / _MARKER).write_text(
            json.dumps({"targets": applied_targets, "redirected": total_redirected},
                       ensure_ascii=False),
            encoding="utf-8",
        )
        if cb:
            cb("apply", 100.0, "הותקן")
        return {"ok": True, "count": total_redirected, "error": ""}
    except PermissionError:
        return {"ok": False,
                "error": "אין הרשאת כתיבה / המשחק פתוח — סגור את המשחק (ו/או הרץ כמנהל) ונסה שוב"}
    except Exception as e:                                  # pragma: no cover
        return {"ok": False, "error": str(e)}


def revert(game_root, backup_dir) -> dict:
    """Restore the original `.fat`/`.dat` for every redirected file + remove the
    apply marker. Safe to call when nothing is applied. {ok, error}."""
    data = _data_dir(game_root)
    backup = Path(backup_dir)
    try:
        marker = backup / _MARKER
        targets: list[str] = []
        if marker.is_file():
            try:
                targets = json.loads(marker.read_text(encoding="utf-8")).get("targets", [])
            except (OSError, ValueError):
                targets = []
        if not targets:
            targets = [rel for _, rel in TARGETS]          # defensive sweep
        for rel in targets:
            _revert_one(data, backup, rel)
        try:
            marker.unlink()
        except OSError:
            pass
        return {"ok": True, "error": ""}
    except PermissionError:
        return {"ok": False,
                "error": "אין הרשאת כתיבה / המשחק פתוח — סגור את המשחק ונסה שוב"}
    except Exception as e:                                  # pragma: no cover
        return {"ok": False, "error": str(e)}
