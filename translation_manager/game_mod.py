"""
game_mod.py — local lifecycle for downloadable GAME translation mods.

Sister of `steam_mod.py`, but for mods that drop net-new files into a
game's own folder (e.g. Cyberpunk 2077's `archive/pc/mod/*.archive`).
Because the mod files are NEW — the game never shipped them — there is
no `.orig` backup to keep: `disable()` simply deletes them from the game
folder, while the pristine copy lives on in the launcher's cache.

Cache layout — `~/.translation_manager/mod_cache/<game_id>/`:
    <the extracted zip tree, e.g. archive/pc/mod/*.archive>
    state.json   {"version", "cached_at", "installed", "installed_files"}

Lifecycle (one downloadable game mod):
    download_and_cache()  fetch+verify+extract via mod_source -> cache
    install()             copy cache tree -> game folder        (ACTIVE)
    disable()             delete mod files from the game folder  (CACHED)
    install() again       = reinstall from cache (no re-download)
    clear_cache()         delete from game folder + wipe cache   (GONE)

`disable()` is the user's "Reset → sent to the temp Cache folder": the
files leave the game but survive in the cache. `clear_cache()` is the
hard wipe — a later install must re-download.
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Callable

from . import mod_source

# Progress callback: cb(phase, pct, detail) — same shape as mod_source.
ProgressCB = Callable[[str, float, str], None]

_CACHE_ROOT = Path.home() / ".translation_manager" / "mod_cache"


# ── paths ─────────────────────────────────────────────────────
def cache_dir(game_id: str) -> Path:
    return _CACHE_ROOT / game_id


def _state_file(game_id: str) -> Path:
    return cache_dir(game_id) / "state.json"


# ── state ─────────────────────────────────────────────────────
def read_state(game_id: str) -> dict:
    sf = _state_file(game_id)
    if not sf.exists():
        return {}
    try:
        data = json.loads(sf.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_state(game_id: str, state: dict) -> None:
    """Atomic write (temp + replace) — mirrors steam_mod / launcher_prefs."""
    cd = cache_dir(game_id)
    cd.mkdir(parents=True, exist_ok=True)
    sf = _state_file(game_id)
    tmp = sf.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(sf)


# ── cache payload introspection ───────────────────────────────
def _payload_files(game_id: str) -> list[tuple[str, Path]]:
    """[(posix-relpath, abspath)] for every cached mod file (skips state.json)."""
    cd = cache_dir(game_id)
    if not cd.is_dir():
        return []
    out: list[tuple[str, Path]] = []
    for f in sorted(cd.rglob("*")):
        if f.is_file() and f.name != "state.json" and not f.name.endswith(".json.tmp"):
            out.append((f.relative_to(cd).as_posix(), f))
    return out


def is_cached(game_id: str) -> bool:
    """True when a populated cache (state.json + ≥1 payload file) exists."""
    return _state_file(game_id).exists() and bool(_payload_files(game_id))


def _norm(rels: list[str]) -> list[str]:
    """Normalize config-style relpaths (Windows backslashes) to posix."""
    return [Path(r).as_posix() for r in rels if r]


def status(game_id: str, game_root: Path | None,
           expected_files: list[str] | None = None) -> dict:
    """Summary for the frontend: {cached, installed, version}.

    `installed` is resolved from the actual game folder so a mod the user
    placed there manually (or a pre-existing staging install) is still
    recognized even before the launcher ever cached it."""
    st = read_state(game_id)
    cached = is_cached(game_id)

    # Which relpaths constitute "the mod" — the cache payload if we have
    # one, else the caller's expected list (GameConfig.mod_files).
    rels = [rel for rel, _ in _payload_files(game_id)]
    if not rels and expected_files:
        rels = _norm(expected_files)

    installed = False
    if game_root is not None and rels:
        installed = all((game_root / rel).is_file() for rel in rels)

    return {
        "cached":    cached,
        "installed": installed,
        "version":   st.get("version"),
    }


# ── download → cache ──────────────────────────────────────────
def download_and_cache(game_id: str, slug: str,
                        cb: ProgressCB | None = None) -> dict:
    """Fetch+verify+extract the mod via the Worker proxy, then copy the
    extracted tree into the launcher's cache. Leaves installed=False —
    call install() next to actually apply it to the game folder."""
    try:
        extracted, version = mod_source.fetch_and_extract(cb, slug=slug)
    except mod_source.IntegrityError as e:
        return {"ok": False, "error": f"כשל אימות שלמות הקובץ: {e}"}
    except mod_source.ModSourceError as e:
        return {"ok": False, "error": f"כשל הורדה מהשרת: {e}"}

    try:
        cd = cache_dir(game_id)
        if cd.exists():
            shutil.rmtree(cd, ignore_errors=True)
        # Copy the extracted tree into the cache (state.json is written after).
        shutil.copytree(extracted, cd)
    except OSError as e:
        return {"ok": False, "error": f"כשל בכתיבת המטמון: {e}"}
    finally:
        # Drop the temp dir (downloaded zip + extracted tree) either way.
        shutil.rmtree(extracted.parent, ignore_errors=True)

    payload = _payload_files(game_id)
    if not payload:
        shutil.rmtree(cache_dir(game_id), ignore_errors=True)
        return {"ok": False, "error": "החבילה שהורדה ריקה"}

    _write_state(game_id, {
        "version":         version,
        "cached_at":       int(time.time()),
        "installed":       False,
        "installed_files": [],
    })
    return {"ok": True, "count": len(payload), "version": version}


# ── install / disable (game folder) ───────────────────────────
def install(game_id: str, game_root: Path,
            cb: ProgressCB | None = None) -> dict:
    """Copy the cached mod files into the game folder. Idempotent — also
    used as 'reinstall' (cache → game, no re-download)."""
    if not is_cached(game_id):
        return {"ok": False, "error": "אין מטמון מקומי — יש להוריד קודם"}
    if not game_root or not Path(game_root).is_dir():
        return {"ok": False, "error": "תיקיית המשחק לא נמצאה — הגדר נתיב תחילה"}

    payload = _payload_files(game_id)
    installed: list[str] = []
    err: str | None = None

    for i, (rel, src) in enumerate(payload):
        target = game_root / rel
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
            installed.append(rel)
            if cb:
                cb("apply", 100.0 * (i + 1) / len(payload), rel)
        except PermissionError as e:
            err = f"אין הרשאת כתיבה ({e.filename or 'תיקיית המשחק'}). סגור את המשחק ונסה שוב."
            break
        except OSError as e:
            err = str(e)
            break

    st = read_state(game_id)
    st["installed"] = not err
    st["installed_files"] = installed
    _write_state(game_id, st)

    if err:
        return {"ok": False, "error": err, "count": len(installed)}
    return {"ok": True, "count": len(installed)}


def disable(game_id: str, game_root: Path) -> dict:
    """Delete the mod files from the game folder. The cache copy stays —
    this is the 'Reset → sent to the temp Cache folder' step."""
    if not game_root:
        return {"ok": False, "error": "תיקיית המשחק לא נמצאה"}
    st = read_state(game_id)
    rels = st.get("installed_files") or [rel for rel, _ in _payload_files(game_id)]
    removed = 0
    err: str | None = None

    for rel in rels:
        target = game_root / rel
        try:
            if target.is_file():
                target.unlink()
                removed += 1
        except PermissionError as e:
            err = f"אין הרשאת כתיבה ({e.filename or rel}). סגור את המשחק ונסה שוב."
            break
        except OSError as e:
            err = str(e)
            break

    if st:
        st["installed"] = False
        _write_state(game_id, st)

    if err:
        return {"ok": False, "error": err, "count": removed}
    return {"ok": True, "count": removed}


# ── cache teardown ────────────────────────────────────────────
def clear_cache(game_id: str, game_root: Path | None,
                expected_files: list[str] | None = None) -> dict:
    """Remove the mod from wherever it lives — the game folder AND the
    launcher's cache. After this a fresh install must re-download."""
    # 1. Remove the mod files from the game folder (if present).
    rels = [rel for rel, _ in _payload_files(game_id)]
    if not rels:
        st = read_state(game_id)
        rels = st.get("installed_files") or _norm(expected_files or [])
    removed_game = 0
    if game_root is not None:
        for rel in rels:
            target = Path(game_root) / rel
            try:
                if target.is_file():
                    target.unlink()
                    removed_game += 1
            except OSError:
                pass                                    # leftover is harmless

    # 2. Wipe the cache directory.
    existed = cache_dir(game_id).exists()
    shutil.rmtree(cache_dir(game_id), ignore_errors=True)

    if not existed and removed_game == 0:
        return {"ok": True, "removed_game": 0, "note": "no cache to clear"}
    return {"ok": True, "removed_game": removed_game}
