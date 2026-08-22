"""
steam_mod.py - local lifecycle for the Steam Hebrew translation mod.

Owns the persistent cache and the enable/disable toggle. Sits above
`steam_apply`, which it uses only to locate the Steam install.

Cache layout - `~/.translation_manager/mod_cache/steam/`:
    steamui/localization/*_arabic-json.js
    resource/*_arabic.txt
    friends/*_arabic.txt
    state.json   {"version", "cached_at", "enabled", "installed_files"}

(Kept under `~/.translation_manager/` for consistency with `paths.py`,
`launcher_prefs.py` and the SWR cache - all launcher state lives there.)

Backup scheme - the `.orig` rule
---------------------------------
The files we install are `*_arabic*`. Steam ships its OWN files at those
paths (the real Arabic localization). To make the toggle reversible we
keep ONE pristine copy per file:

    <file>.orig - the genuine Steam file, captured the FIRST time we ever
                  overwrite <file>, and never touched again.

  enable()  : if <file>.orig is absent and <file> exists -> copy it to
              <file>.orig once; then copy the cached Hebrew file in.
  disable() : if <file>.orig exists -> restore it; else (the file was
              purely ours, e.g. a new resource/*_arabic.txt) -> delete it.

A timestamped `.bak` scheme can't do this: a second enable() would back
up our OWN Hebrew file, and a later "restore latest" would yield Hebrew.

disable() only touches files listed in `state["installed_files"]` - the
exact set the last enable() actually wrote - so a partial enable can't
make disable delete a file it never installed.
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Callable

from . import steam_apply

# Progress callback: cb(phase, pct, detail). For this module `phase` is
# always "apply" - download/verify/extract belong to mod_source.py.
ProgressCB = Callable[[str, float, str], None]

CACHE_DIR  = Path.home() / ".translation_manager" / "mod_cache" / "steam"
STATE_FILE = CACHE_DIR / "state.json"

# Managed sub-trees, mirrored between the cache and the Steam install.
_GLOBS: list[tuple[str, str]] = [
    ("steamui/localization", "*_arabic-json.js"),
    ("resource",             "*_arabic.txt"),
    ("friends",              "*_arabic.txt"),
]


# ── state ─────────────────────────────────────────────────────
def read_state() -> dict:
    """Return the cache state dict, or {} if there is no cache."""
    if not STATE_FILE.exists():
        return {}
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_state(state: dict) -> None:
    """Atomic write (temp + replace) - mirrors launcher_prefs.py."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STATE_FILE)


def _cache_files() -> list[tuple[str, Path]]:
    """[(relpath, abspath)] for every managed file currently in the cache."""
    out: list[tuple[str, Path]] = []
    for subdir, pattern in _GLOBS:
        d = CACHE_DIR / subdir
        if d.is_dir():
            for f in sorted(d.glob(pattern)):
                out.append((f"{subdir}/{f.name}", f))
    return out


def is_cached() -> bool:
    """True when a populated cache (state.json + at least one file) exists."""
    return STATE_FILE.exists() and bool(_cache_files())


def status() -> dict:
    """Summary for the frontend: {cached, enabled, version}."""
    st = read_state()
    return {
        "cached":  is_cached(),
        "enabled": bool(st.get("enabled", False)),
        "version": st.get("version"),
    }


# ── cache population ──────────────────────────────────────────
def populate_cache(src: Path, version: str) -> dict:
    """Copy a freshly-extracted `steam_hebrew_output` tree into the cache,
    replacing any existing cache. Leaves `enabled=False` - call enable()
    next to actually apply it."""
    if not src.is_dir():
        return {"ok": False, "error": f"source not found: {src}"}

    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR, ignore_errors=True)

    copied = 0
    for subdir, pattern in _GLOBS:
        sd = src / subdir
        if not sd.is_dir():
            continue
        dd = CACHE_DIR / subdir
        dd.mkdir(parents=True, exist_ok=True)
        for f in sd.glob(pattern):
            shutil.copy2(f, dd / f.name)
            copied += 1

    if copied == 0:
        shutil.rmtree(CACHE_DIR, ignore_errors=True)
        return {"ok": False, "error": "no translated files found in source"}

    _write_state({
        "version":         version,
        "cached_at":       int(time.time()),
        "enabled":         False,
        "installed_files": [],
    })
    return {"ok": True, "count": copied}


# ── toggle ────────────────────────────────────────────────────
def enable(cb: ProgressCB | None = None) -> dict:
    """Copy the cached Hebrew files into the live Steam install, capturing
    each genuine original as `<file>.orig` the first time. Idempotent -
    safe to re-run after a partial failure."""
    if not is_cached():
        return {"ok": False, "error": "אין מטמון מקומי - יש להתקין קודם"}
    steam = steam_apply.find_steam_install()
    if steam is None:
        return {"ok": False, "error": "לא נמצאה תיקיית Steam - האם Steam מותקן?"}

    files = _cache_files()
    installed: list[str] = []
    err: str | None = None

    for i, (rel, src) in enumerate(files):
        target = steam / rel
        if not target.parent.is_dir():
            continue                                  # Steam lacks this sub-tree
        try:
            orig = target.with_name(target.name + ".orig")
            if target.exists() and not orig.exists():
                shutil.copy2(target, orig)            # capture pristine, once
            shutil.copy2(src, target)
            installed.append(rel)
            if cb:
                cb("apply", 100.0 * (i + 1) / len(files), rel)
        except PermissionError as e:
            err = f"אין הרשאת כתיבה ({e.filename or 'Steam'}). סגור את Steam ונסה שוב."
            break
        except OSError as e:
            err = str(e)
            break

    st = read_state()
    # "enabled" == the apply finished with no error AND at least one file landed.
    # We must NOT require len(installed)==len(files): a cache file whose Steam
    # sub-tree is absent is legitimately SKIPPED (line ~161) yet still counted in
    # `files`, so `== len(files)` would report enabled=False on a fully-successful
    # apply - which then makes clear_cache() skip its restore while still deleting
    # the .orig backups (data loss). `err is None` already means every applicable
    # file was written (the loop only breaks on a real error).
    st["enabled"] = err is None and len(installed) > 0
    st["installed_files"] = installed
    _write_state(st)

    if err:
        return {"ok": False, "error": err, "count": len(installed)}
    return {"ok": True, "count": len(installed), "steam_dir": str(steam)}


def disable(cb: ProgressCB | None = None) -> dict:
    """Restore the genuine Steam files (`<file>.orig`) over our Hebrew ones.
    Files that had no original (purely ours) are deleted. Only touches the
    set the last enable() actually installed."""
    st = read_state()
    if not st:
        return {"ok": False, "error": "אין מטמון מקומי"}
    steam = steam_apply.find_steam_install()
    if steam is None:
        return {"ok": False, "error": "לא נמצאה תיקיית Steam"}

    # Prefer the recorded install set; fall back to the full cache list
    # for any legacy state.json written before the field existed.
    installed = st.get("installed_files") or [rel for rel, _ in _cache_files()]
    reverted = 0
    err: str | None = None

    for i, rel in enumerate(installed):
        target = steam / rel
        orig = target.with_name(target.name + ".orig")
        try:
            if orig.exists():
                shutil.copy2(orig, target)            # genuine Steam file back
            elif target.exists():
                target.unlink()                       # file was purely ours
            reverted += 1
            if cb:
                cb("apply", 100.0 * (i + 1) / max(1, len(installed)), rel)
        except PermissionError as e:
            err = f"אין הרשאת כתיבה ({e.filename or 'Steam'}). סגור את Steam ונסה שוב."
            break
        except OSError as e:
            err = str(e)
            break

    st["enabled"] = False
    _write_state(st)

    if err:
        return {"ok": False, "error": err, "count": reverted}
    return {"ok": True, "count": reverted}


# ── cache teardown ────────────────────────────────────────────
def clear_cache() -> dict:
    """Revert Steam to its original files, drop the `.orig` backups, then
    delete the local cache - leaving the machine as if the mod never ran."""
    st = read_state()
    if not st and not CACHE_DIR.exists():
        return {"ok": True, "count": 0, "note": "no cache to clear"}

    # 1. Restore the genuine Steam files first whenever ANYTHING was installed -
    #    gated on installed_files, NOT the `enabled` flag. Deleting the .orig
    #    backups (step 2) without restoring would leave Steam permanently on our
    #    Hebrew files with no recovery; disable() is idempotent so restoring an
    #    already-reverted set is harmless.
    if st.get("installed_files"):
        r = disable()
        if not r.get("ok"):
            return {"ok": False, "error": f"כשל בשחזור קבצי Steam לפני הניקוי: {r.get('error')}"}

    # 2. Remove the now-redundant `.orig` backups from the Steam install.
    steam = steam_apply.find_steam_install()
    removed_orig = 0
    if steam is not None:
        installed = read_state().get("installed_files") or [rel for rel, _ in _cache_files()]
        for rel in installed:
            target = steam / rel
            orig = target.with_name(target.name + ".orig")
            if orig.exists():
                try:
                    orig.unlink()
                    removed_orig += 1
                except OSError:
                    pass                              # leftover is harmless

    # 3. Delete the cache directory.
    shutil.rmtree(CACHE_DIR, ignore_errors=True)
    return {"ok": True, "removed_orig": removed_orig}
