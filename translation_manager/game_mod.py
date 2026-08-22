"""
game_mod.py - local lifecycle for downloadable GAME translation mods.

Sister of `steam_mod.py`, but for mods that drop net-new files into a
game's own folder (e.g. Cyberpunk 2077's `archive/pc/mod/*.archive`).
Because the mod files are NEW - the game never shipped them - there is
no `.orig` backup to keep: `disable()` simply deletes them from the game
folder, while the pristine copy lives on in the launcher's cache.

Cache layout - `~/.translation_manager/mod_cache/<game_id>/`:
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
hard wipe - a later install must re-download.
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Callable

from . import mod_source

# Progress callback: cb(phase, pct, detail) - same shape as mod_source.
ProgressCB = Callable[[str, float, str], None]

_CACHE_ROOT = Path.home() / ".translation_manager" / "mod_cache"


# ── paths ─────────────────────────────────────────────────────
def cache_dir(game_id: str) -> Path:
    return _CACHE_ROOT / game_id


def orig_dir(game_id: str) -> Path:
    """Pristine copies of files the mod OVERWROTE in the game folder.

    Some packages ship files that can already exist for the user - RDR2's mod is a
    Lenny's-Mod-Loader tree whose `dinput8.dll` / `ScriptHookRDR2.dll` a player with
    ANY other ASI mod already has. Copying over them and later DELETING them on
    remove would break that other mod. So the genuine file is captured ONCE, on the
    first overwrite, and restored on remove (the proven `.orig` scheme from
    steam_mod). A SIBLING of the cache dir, never inside it, so the payload glob can
    never mistake a backup for a mod file."""
    return _CACHE_ROOT / f"{game_id}__orig"


def _restore_or_delete(target: Path, keep: Path) -> bool:
    """Undo one installed file: put the user's original back if we shadowed one,
    else just delete ours. Returns True when the game folder changed."""
    if keep.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(keep, target)
        keep.unlink(missing_ok=True)
        return True
    if target.is_file():
        target.unlink()
        return True
    return False


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
    """Atomic write (temp + replace) - mirrors steam_mod / launcher_prefs."""
    cd = cache_dir(game_id)
    cd.mkdir(parents=True, exist_ok=True)
    sf = _state_file(game_id)
    tmp = sf.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(sf)


# ── cache payload introspection ───────────────────────────────
# Names at the TOP LEVEL of a downloaded package that are package METADATA, not
# deploy payload: our mod zips ship a self-contained installer + a Hebrew readme
# beside the real files. Copying them into the user's game/mods folder is junk
# (and `install.py` there is confusing). Matched only at depth 0, so a payload
# that legitimately contains such a name deeper in its tree is never dropped.
_PKG_META = {"install.py", "manifest.json"}
_PKG_META_PREFIX = ("readme", "קרא_אותי")


def _is_pkg_meta(rel: str) -> bool:
    if "/" in rel:                       # depth > 0 → real payload, never skipped
        return False
    low = rel.lower()
    return rel in _PKG_META or low.endswith(".md") or low.startswith(_PKG_META_PREFIX)


def _payload_files(game_id: str,
                   exclude: tuple[str, ...] | None = None) -> list[tuple[str, Path]]:
    """[(posix-relpath, abspath)] for every cached mod file that should be DEPLOYED
    (skips state.json, package metadata, and the caller's per-game exclusions)."""
    cd = cache_dir(game_id)
    if not cd.is_dir():
        return []
    skip = set(exclude or ())
    out: list[tuple[str, Path]] = []
    for f in sorted(cd.rglob("*")):
        if not f.is_file() or f.name == "state.json" or f.name.endswith(".json.tmp"):
            continue
        rel = f.relative_to(cd).as_posix()
        if _is_pkg_meta(rel) or rel in skip:
            continue
        out.append((rel, f))
    return out


def is_cached(game_id: str) -> bool:
    """True when a populated cache (state.json + ≥1 payload file) exists."""
    return _state_file(game_id).exists() and bool(_payload_files(game_id))


def is_writable(game_root: Path | None) -> bool:
    """Non-destructive probe: can the launcher create files under the game
    folder? Games installed under C:\\Program Files need an elevated launcher
    to write the mod; checking up-front lets the caller fail fast with a clear
    message INSTEAD of downloading the whole archive and only then hitting a
    PermissionError on the copy."""
    if not game_root:
        return False
    try:
        p = Path(game_root)
        if not p.is_dir():
            return False
        import tempfile
        with tempfile.NamedTemporaryFile(dir=p, prefix=".tm_write_probe", delete=True):
            pass
        return True
    except OSError:
        return False


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

    # Which relpaths constitute "the mod" - the cache payload if we have
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
    extracted tree into the launcher's cache. Leaves installed=False -
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
            cb: ProgressCB | None = None,
            exclude: tuple[str, ...] | None = None) -> dict:
    """Copy the cached mod files into the game folder. Idempotent - also
    used as 'reinstall' (cache → game, no re-download)."""
    if not is_cached(game_id):
        return {"ok": False, "error": "אין מטמון מקומי - יש להוריד קודם"}
    if not game_root or not Path(game_root).is_dir():
        return {"ok": False, "error": "תיקיית המשחק לא נמצאה - הגדר נתיב תחילה"}

    payload = _payload_files(game_id, exclude)
    installed: list[str] = []
    err: str | None = None

    od = orig_dir(game_id)
    for i, (rel, src) in enumerate(payload):
        target = game_root / rel
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            # Capture the user's ORIGINAL once, before the first time we shadow it.
            # `not keep.exists()` makes a re-install/update idempotent - it can never
            # overwrite a real original with our own previously-installed copy.
            if target.is_file():
                keep = od / rel
                if not keep.exists():
                    keep.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(target, keep)
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
    if not err:
        # The version now APPLIED to the game folder. Tracked separately from
        # `version` (= what sits in the CACHE) so an offline bundle can seed a
        # NEWER payload into the cache without the app claiming it is already
        # applied - that gap is exactly what surfaces as "עדכון אופליין".
        st["installed_version"] = st.get("version")
    _write_state(game_id, st)

    if err:
        return {"ok": False, "error": err, "count": len(installed)}
    return {"ok": True, "count": len(installed)}


def applied_version(game_id: str) -> str | None:
    """The version actually applied to the game folder.

    Falls back to the cached `version` for installs made BEFORE
    installed_version existed, so an upgraded launcher never shows a phantom
    update for a mod the user already has."""
    st = read_state(game_id)
    v = st.get("installed_version")
    if isinstance(v, str) and v:
        return v
    return st.get("version") if st.get("installed") else None


def cache_from_dir(game_id: str, extracted: Path, version: str) -> dict:
    """Populate the cache from an ALREADY-extracted tree (the offline path).

    Same end state as download_and_cache, minus the network - so an offline
    bundle makes the download step unnecessary while `install()` still does the
    actual apply into the game folder."""
    try:
        cd = cache_dir(game_id)
        if cd.exists():
            shutil.rmtree(cd, ignore_errors=True)
        shutil.copytree(extracted, cd)
    except OSError as e:
        return {"ok": False, "error": f"כשל בכתיבת המטמון: {e}"}

    payload = _payload_files(game_id)
    if not payload:
        shutil.rmtree(cache_dir(game_id), ignore_errors=True)
        return {"ok": False, "error": "החבילה ריקה"}

    _write_state(game_id, {
        "version":         version,
        "cached_at":       int(time.time()),
        "installed":       False,
        "installed_files": [],
        "source":          "offline",
    })
    return {"ok": True, "count": len(payload), "version": version}


def disable(game_id: str, game_root: Path,
            expected_files: list[str] | None = None) -> dict:
    """Delete the mod files from the game folder. The cache copy stays -
    this is the 'Reset → sent to the temp Cache folder' step."""
    if not game_root:
        return {"ok": False, "error": "תיקיית המשחק לא נמצאה"}
    st = read_state(game_id)
    # Fall back through: recorded files → the cache payload → the caller's known
    # relpaths (cfg.mod_files). Without the last fallback, a mod installed by an
    # OLDER build (no installed_files recorded) whose cache was cleared would
    # leave rels EMPTY → nothing removed → falsely report "disabled" (same
    # fallback its sibling clear_cache already has).
    rels = (st.get("installed_files")
            or [rel for rel, _ in _payload_files(game_id)]
            or _norm(expected_files or []))
    removed = 0
    err: str | None = None

    od = orig_dir(game_id)
    for rel in rels:
        target = game_root / rel
        try:
            if _restore_or_delete(target, od / rel):
                removed += 1
        except PermissionError as e:
            err = f"אין הרשאת כתיבה ({e.filename or rel}). סגור את המשחק ונסה שוב."
            break
        except OSError as e:
            err = str(e)
            break

    # Only record the mod as removed when every file actually went away. If a
    # deletion failed (e.g. the game is running and locks the archive), the
    # files are still on disk - keep installed=True so the UI keeps showing
    # "active" and a retry re-attempts, instead of lying that it's disabled.
    if st and not err:
        st["installed"] = False
        _write_state(game_id, st)

    if err:
        return {"ok": False, "error": err, "count": removed}
    return {"ok": True, "count": removed}


# ── cache teardown ────────────────────────────────────────────
def clear_cache(game_id: str, game_root: Path | None,
                expected_files: list[str] | None = None) -> dict:
    """Remove the mod from wherever it lives - the game folder AND the
    launcher's cache. After this a fresh install must re-download."""
    # 1. Remove the mod files from the game folder (if present).
    rels = [rel for rel, _ in _payload_files(game_id)]
    if not rels:
        st = read_state(game_id)
        rels = st.get("installed_files") or _norm(expected_files or [])
    removed_game = 0
    stuck: str | None = None
    if game_root is not None:
        od = orig_dir(game_id)
        for rel in rels:
            target = Path(game_root) / rel
            try:
                if _restore_or_delete(target, od / rel):
                    removed_game += 1
            except OSError as e:
                # A locked mod file (game running) means the mod is STILL active
                # in the game folder - don't report "cache cleared" as success.
                stuck = f"{e.filename or rel}"

    # 2. REVERT-FIRST: if a game-folder file was locked (game running), the mod is
    #    STILL active there - do NOT wipe the cache/state.json. Wiping it would
    #    strand the mod (the payload/backup is the only way to finish the removal
    #    or re-deploy) and force a full re-download. Bail; the user closes the game
    #    and retries. (Previously the rmtree ran unconditionally BEFORE this check.)
    if stuck:
        return {"ok": False, "removed_game": removed_game,
                "error": "לא ניתן להסיר את קובץ המוד מהמשחק (ייתכן שהמשחק פתוח). סגור את המשחק ונסה שוב."}

    # 3. Game folder is clean → wipe the cache directory.
    existed = cache_dir(game_id).exists()
    shutil.rmtree(cache_dir(game_id), ignore_errors=True)
    # The originals were already restored file-by-file above; drop the empty tree.
    shutil.rmtree(orig_dir(game_id), ignore_errors=True)

    if not existed and removed_game == 0:
        return {"ok": True, "removed_game": 0, "note": "no cache to clear"}
    return {"ok": True, "removed_game": removed_game}
