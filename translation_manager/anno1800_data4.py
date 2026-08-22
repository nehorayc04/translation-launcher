# -*- coding: utf-8 -*-
"""anno1800_data4.py — the launcher's maindata `data4.rda` deploy for the Anno 1800
Hebrew (English-slot) mod.

The loose-file mod (deployed to %Documents%\\Anno 1800\\mods) supplies the Hebrew TEXT,
but the cold-boot pre-baked atlas (settings labels / warnings / profile) draws from the
maindata fonts. So the English-slot build ALSO needs the Hebrew-injected `data4.rda`
dropped into the game's `maindata`. The mod archive carries that file at its root; this
module deploys it with a backup OUTSIDE the game (so a Program-Files install still
reverts) and is game-update-aware (a game patch rewrites data4 -> refresh the backup so a
later revert restores the NEW retail file, never a stale one).

Safety contract (same as the native appliers):
  * back up the user's ORIGINAL data4.rda once, into the launcher backup dir;
  * atomic write (temp + os.replace) — never a half-written archive;
  * revert restores byte-exact and KEEPS the backup (re-install re-takes if the game changed);
  * the game must be CLOSED (it locks maindata) — a lock surfaces as a clear Hebrew error.
"""
from __future__ import annotations
import hashlib
import json
import os
import shutil
from pathlib import Path

_ORIG = "data4.rda.original"
_META = "data4_meta.json"


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _anno_running() -> bool:
    try:
        return "Anno1800.exe" in os.popen('tasklist /FI "IMAGENAME eq Anno1800.exe" /NH 2>NUL').read()
    except Exception:
        return False


def _live(game_root: Path) -> Path:
    return Path(game_root) / "maindata" / "data4.rda"


def _read_meta(backup_dir: str) -> dict:
    try:
        return json.loads((Path(backup_dir) / _META).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_meta(backup_dir: str, meta: dict) -> None:
    try:
        (Path(backup_dir) / _META).write_text(json.dumps(meta), encoding="utf-8")
    except Exception:
        pass


def is_applied(game_root: Path | None, backup_dir: str) -> bool:
    """True iff the live maindata data4.rda is the Hebrew-injected one we deployed."""
    if not game_root:
        return False
    live = _live(game_root)
    if not live.is_file():
        return False
    meta = _read_meta(backup_dir)
    dep = meta.get("deployed_sha")
    if not dep:
        return False
    try:
        return _sha(live) == dep
    except Exception:
        return False


def deploy(game_root: Path, src_data4: Path, backup_dir: str) -> dict:
    """Back up the user's data4.rda (once, or refresh it after a game update) and drop in
    the Hebrew-injected one. No-op OK if the archive carries no data4 (loose-only fallback)."""
    src = Path(src_data4)
    if not src.is_file():
        return {"ok": True, "skipped": "no data4 in payload (loose-only)"}
    live = _live(game_root)
    if not live.parent.is_dir():
        return {"ok": True, "skipped": "no maindata folder (game path?)"}
    if _anno_running():
        return {"ok": False, "error": "Anno 1800 רץ — סגור את המשחק וההתקנה תמשיך (הוא נועל את קובצי המשחק)."}

    bdir = Path(backup_dir)
    bdir.mkdir(parents=True, exist_ok=True)
    bak = bdir / _ORIG
    meta = _read_meta(backup_dir)
    src_sha = _sha(src)
    try:
        live_sha = _sha(live) if live.is_file() else None
        # Back up the ORIGINAL once. If the live file is neither our deployed build NOR the
        # recorded backup, the game updated data4 -> refresh the backup to this NEW retail file
        # so a later revert restores the current game version, not a stale one.
        if live_sha is not None:
            if not bak.is_file():
                shutil.copy2(live, bak)
                meta["original_sha"] = live_sha
            elif live_sha != meta.get("deployed_sha") and live_sha != meta.get("original_sha"):
                shutil.copy2(live, bak)         # game update rewrote data4 -> refresh baseline
                meta["original_sha"] = live_sha
        # atomic deploy
        tmp = live.with_suffix(".rda.tm_new")
        shutil.copy2(src, tmp)
        os.replace(tmp, live)
        meta["deployed_sha"] = src_sha
        _write_meta(backup_dir, meta)
        return {"ok": True}
    except PermissionError:
        return {"ok": False, "error": "אין גישה לקובצי המשחק — סגור את Anno 1800 והרץ שוב."}
    except OSError as e:
        return {"ok": False, "error": f"כשל בהתקנת גופני המשחק (data4): {e}"}


def revert(game_root: Path | None, backup_dir: str) -> dict:
    """Restore the user's original data4.rda from the backup (kept for re-install)."""
    if not game_root:
        return {"ok": True, "skipped": "no game path"}
    live = _live(game_root)
    bak = Path(backup_dir) / _ORIG
    if not bak.is_file():
        return {"ok": True, "skipped": "no data4 backup"}
    if _anno_running():
        return {"ok": False, "error": "Anno 1800 רץ — סגור אותו כדי לשחזר את קובצי המשחק."}
    try:
        tmp = live.with_suffix(".rda.tm_new")
        shutil.copy2(bak, tmp)
        os.replace(tmp, live)
        return {"ok": True}
    except PermissionError:
        return {"ok": False, "error": "אין גישה לקובצי המשחק — סגור את Anno 1800 והרץ שוב."}
    except OSError as e:
        return {"ok": False, "error": f"כשל בשחזור data4: {e}"}
