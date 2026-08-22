"""
Watch Dogs 2 - native Hebrew-mod applier (fat-redirect, no Overstrike / mod
manager). Python reimplementation of the proven `games/watchdogs2/work/
wd2_archive.py` deploy, hardened for shipping inside the launcher.

WD2 (Ubisoft Disrupt, FAT5 v11) stores assets across load-ordered archives
`common < patch < patch2` - each a `<name>.fat` index + `<name>.dat` blob under
`<game>/data_win64/`. We install the Hebrew translation by, for each of the 3
shipped files (localization `.loc` + the Hebrew font `.ffd` + its atlas `.xbt`):

  1. APPEND the file's bytes to every archive's `.dat`, and
  2. REWRITE that asset's `.fat` entry to point at the new offset, stored
     uncompressed (v11 stored ⇒ UncompressedSize=0).

Fully reversible: each `.fat` is backed up ONCE and the `.dat`'s original size
recorded; `revert()` restores the `.fat` and truncates the `.dat`. Backups + an
apply marker live OUTSIDE the game folder (the launcher's app-data cache) so a
Program-Files install with no writable backup subfolder still reverts cleanly.

Activation is in-game (Settings → Written Language = العربية / Arabic) - the
Hebrew rides the Arabic RTL slot - so this applier does NOT touch any game
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


def _atomic_write_bytes(dst: Path, data: bytes) -> None:
    """Write `data` to `dst` ATOMICALLY (temp file in the same dir + os.replace).

    `dst` here is a `.fat` - the game's OWN archive INDEX. A plain open/write/close
    that is interrupted (crash, force-close, power loss, AV real-time-scan lock
    mid-write) leaves a TORN index and the game can then fail to load the whole
    archive - not just lose the mod. os.replace on the same volume is atomic, so
    the reader only ever sees the complete old or the complete new bytes. This
    mirrors the temp+replace pattern the other appliers (SM2/GoWR/HL/PT/GTAV) use.
    """
    tmp = dst.with_name(dst.name + f".tmp{os.getpid()}")
    try:
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, dst)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


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
        _atomic_write_bytes(fatp, bytes(fat))      # torn .fat = unloadable archive
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
        # Restore FIRST; only drop the backups once BOTH the .fat restore
        # and the .dat truncate actually succeed. If either raises (e.g. the
        # game is running and locks the file) the exception propagates so
        # revert() reports failure AND the backups are KEPT - a retry with
        # the game closed can then finish. The old `finally` deleted the
        # backups even on failure, which lost the true-original .fat, left
        # is_applied() stuck true, and made a re-apply stack on top → a
        # permanently-un-revertable, ever-growing .dat.
        _atomic_write_bytes(fatp, fbk.read_bytes())   # restore index atomically
        with open(datp, "r+b") as f:
            f.truncate(int(szf.read_text(encoding="utf-8").strip()))
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
        return {"ok": False, "error": "תיקיית data_win64 לא נמצאה - ודא את נתיב ההתקנה של המשחק"}
    backup = Path(backup_dir)
    try:
        # Clean slate so a re-install can't append on top of a prior redirect.
        # If that revert FAILS (e.g. the game is open and locks a .dat), we
        # MUST abort - proceeding would append the payload a second time onto
        # an already-modded .dat and back up the modded .fat as "original",
        # producing an ever-growing, un-revertable archive.
        if is_applied(backup):
            rv = revert(game_root, backup)
            if not rv.get("ok"):
                return {"ok": False,
                        "error": rv.get("error") or "שחזור ההתקנה הקודמת נכשל - סגור את המשחק ונסה שוב"}
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
        # Record each archive's .dat size AS WE LEAVE IT (post-apply). revert()
        # compares this to the live size to detect a game update that rewrote the
        # archive - restoring a stale backup over an updated .dat would corrupt it.
        applied_sizes = {
            name: (data / (name + ".dat")).stat().st_size
            for name in ARCHIVES if (data / (name + ".dat")).is_file()
        }
        (backup / _MARKER).write_text(
            json.dumps({"targets": applied_targets, "redirected": total_redirected,
                        "applied_sizes": applied_sizes},
                       ensure_ascii=False),
            encoding="utf-8",
        )
        if cb:
            cb("apply", 100.0, "הותקן")
        return {"ok": True, "count": total_redirected, "error": ""}
    except PermissionError:
        return {"ok": False,
                "error": "אין הרשאת כתיבה / המשחק פתוח - סגור את המשחק (ו/או הרץ כמנהל) ונסה שוב"}
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
        applied_sizes: dict = {}
        if marker.is_file():
            try:
                m = json.loads(marker.read_text(encoding="utf-8"))
                targets = m.get("targets", [])
                applied_sizes = m.get("applied_sizes", {}) or {}
            except (OSError, ValueError):
                targets = []
        if not targets:
            targets = [rel for _, rel in TARGETS]          # defensive sweep

        # GAME-UPDATE GUARD (checked ONCE, before ANY restore - applied_sizes is
        # the post-apply size of the whole archive, so this is only valid before
        # we start truncating): if a live .dat no longer matches the size we left
        # it at, a game patch rewrote that archive. Restoring the stale .fat +
        # truncating to the pre-mod size would CHOP/desync the updated content, so
        # DROP all backups WITHOUT touching the live archives (they're already the
        # game's own, mod-free after the update).
        stale = any(
            (data / (name + ".dat")).is_file()
            and (data / (name + ".dat")).stat().st_size != int(sz)
            for name, sz in applied_sizes.items()
        )
        if stale:
            for b in list(backup.glob("*.fat.*.bak")) + list(backup.glob("*.dat.*.origsize")):
                try:
                    b.unlink()
                except OSError:
                    pass
            try:
                marker.unlink()
            except OSError:
                pass
            return {"ok": True, "error": "", "stale": True}

        for rel in targets:
            _revert_one(data, backup, rel)
        try:
            marker.unlink()
        except OSError:
            pass
        return {"ok": True, "error": ""}
    except PermissionError:
        return {"ok": False,
                "error": "אין הרשאת כתיבה / המשחק פתוח - סגור את המשחק ונסה שוב"}
    except Exception as e:                                  # pragma: no cover
        return {"ok": False, "error": str(e)}
