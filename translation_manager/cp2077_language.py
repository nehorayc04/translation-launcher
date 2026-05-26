"""
Cyberpunk 2077 language-slot automation.

The Hebrew translation mod ships under Cyberpunk's Arabic locale archive
(see CP2077 pipeline notes — Hebrew CR2W in en-us crashes the engine,
Arabic-slot uses CDPR's tested RTL/bidi path). This module flips the
game's Text + Subtitles settings to "ar-ar" when the mod is installed
and restores the user's prior choice when it's removed.

Voice is intentionally untouched — the user keeps their preferred
voice-over language (typically English).

Public surface:
    enable_arabic_slot()  -> dict
    restore_language()    -> dict

Both return a structured dict and never raise. The launcher's mod
install/remove flow consults `ok` for telemetry only — failures here
must not block the file-level mod operations, which are the actual
load-bearing part.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Iterable

log = logging.getLogger(__name__)

ARABIC_LOCALE       = "ar-ar"
LANG_VARS_TO_SWAP   = ("Text", "Subtitles")        # NOT Voice
LANG_GROUP_NAMES    = ("/language", "language")

# Cached backup file — sits next to custom_paths.json so it auto-cleans
# with the rest of the launcher's per-user runtime data.
_STATE_DIR  = Path.home() / ".translation_manager"
_STATE_FILE = _STATE_DIR / "cp2077_lang_backup.json"


# ─────────────────────────────────────────────────────────────
# Path + file helpers
# ─────────────────────────────────────────────────────────────
def _settings_file() -> Path:
    """Resolve %LOCALAPPDATA%\\CD Projekt Red\\Cyberpunk 2077\\UserSettings.json."""
    raw = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(raw) / "CD Projekt Red" / "Cyberpunk 2077" / "UserSettings.json"


def _read_json(path: Path) -> dict[str, Any] | None:
    """Read + parse a JSON file, tolerating an optional UTF-8 BOM."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as e:
        log.warning("cp2077_language: cannot read %s — %s", path, e)
        return None
    return data if isinstance(data, dict) else None


def _write_json_atomic(path: Path, data: dict[str, Any]) -> bool:
    """Write JSON via a sibling temp file + os.replace (atomic on Windows)."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tm-tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)
        return True
    except OSError as e:
        log.warning("cp2077_language: write failed for %s — %s", path, e)
        return False


# ─────────────────────────────────────────────────────────────
# Backup state
# ─────────────────────────────────────────────────────────────
def _read_state() -> dict[str, Any]:
    data = _read_json(_STATE_FILE)
    return data if data is not None else {}


def _write_state(state: dict[str, Any]) -> None:
    _write_json_atomic(_STATE_FILE, state)


def _clear_state() -> None:
    try:
        if _STATE_FILE.exists():
            _STATE_FILE.unlink()
    except OSError as e:
        log.debug("cp2077_language: state cleanup ignored — %s", e)


# ─────────────────────────────────────────────────────────────
# UserSettings.json structure walkers
# ─────────────────────────────────────────────────────────────
def _iter_lang_vars(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Find every var dict inside the language group.

    The expected schema is:
        { "groups": [ { "name": "/language", "vars": [ {name, value, ...}, ... ] }, ... ] }

    We tolerate the alternate `vars` → `entries` rename and case
    variations of the group name. If the standard schema yields nothing,
    we fall back to a recursive scan that picks up any object whose
    `name` matches one of the language vars we care about — that way an
    unexpected schema bump from CDPR doesn't silently no-op.
    """
    out: list[dict[str, Any]] = []
    targets = set(LANG_VARS_TO_SWAP) | {"Voice"}    # used only by fallback filter

    # Pass 1 — standard groups[].vars[] structure.
    groups = data.get("groups")
    if isinstance(groups, list):
        for g in groups:
            if not isinstance(g, dict):
                continue
            if str(g.get("name", "")).lower() not in LANG_GROUP_NAMES:
                continue
            vars_ = g.get("vars") or g.get("entries") or []
            if isinstance(vars_, list):
                out.extend(v for v in vars_ if isinstance(v, dict))
    if out:
        return out

    # Pass 2 — recursive fallback. Only collect dicts that look like a
    # language var (name ∈ {Text, Subtitles, Voice} + has a `value`),
    # which avoids accidentally rewriting unrelated nodes called "Text"
    # elsewhere in the file.
    def walk(node: Any) -> None:
        if isinstance(node, dict):
            name = node.get("name")
            if isinstance(name, str) and name in targets and "value" in node:
                out.append(node)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for it in node:
                walk(it)
    walk(data)
    return out


def _vars_by_name(vars_: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for v in vars_:
        n = v.get("name")
        if isinstance(n, str):
            out[n] = v
    return out


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────
def enable_arabic_slot() -> dict[str, Any]:
    """Flip Text + Subtitles to ar-ar; back up the prior values.

    Returns:
        {
          "ok":       bool,
          "changed":  list[str],          # var names actually rewritten
          "previous": dict[str, str],     # backed-up originals (Text/Subtitles)
          "error":    str,                # empty when ok
        }
    """
    path = _settings_file()
    data = _read_json(path)
    if data is None:
        return {"ok": False, "changed": [], "previous": {}, "error": "settings-file-missing-or-unreadable"}

    by_name = _vars_by_name(_iter_lang_vars(data))
    previous: dict[str, str] = {}
    changed:  list[str]      = []

    for name in LANG_VARS_TO_SWAP:
        var = by_name.get(name)
        if var is None or "value" not in var:
            continue
        current = str(var["value"])
        previous[name] = current
        if current != ARABIC_LOCALE:
            var["value"] = ARABIC_LOCALE
            changed.append(name)

    if not previous:
        return {"ok": False, "changed": [], "previous": {}, "error": "language-vars-not-found"}

    # Only persist a fresh backup the FIRST time we flip. Re-running
    # enable on an already-flipped install must NOT overwrite the
    # backup with ar-ar (that would make the next restore a no-op).
    state = _read_state()
    if not state.get("previous"):
        _write_state({"previous": previous, "settings_path": str(path)})

    if changed and not _write_json_atomic(path, data):
        return {"ok": False, "changed": [], "previous": previous, "error": "settings-write-failed"}

    return {"ok": True, "changed": changed, "previous": previous, "error": ""}


def restore_language() -> dict[str, Any]:
    """Restore Text + Subtitles to the backed-up values, then clear the backup.

    Returns:
        {
          "ok":        bool,
          "restored":  list[str],
          "error":     str,
        }

    Always clears the backup state on exit (whether or not the write
    succeeded) so a missing/uninstalled game doesn't keep a stale
    snapshot around to silently restore later.
    """
    state    = _read_state()
    previous = state.get("previous") if isinstance(state.get("previous"), dict) else {}

    if not previous:
        _clear_state()
        return {"ok": False, "restored": [], "error": "no-backup-found"}

    path = _settings_file()
    data = _read_json(path)
    if data is None:
        _clear_state()
        return {"ok": False, "restored": [], "error": "settings-file-missing-or-unreadable"}

    by_name = _vars_by_name(_iter_lang_vars(data))
    restored: list[str] = []
    for name in LANG_VARS_TO_SWAP:
        prior = previous.get(name)
        var   = by_name.get(name)
        if not isinstance(prior, str) or var is None or "value" not in var:
            continue
        var["value"] = prior
        restored.append(name)

    if not restored:
        _clear_state()
        return {"ok": False, "restored": [], "error": "nothing-to-restore"}

    ok = _write_json_atomic(path, data)
    _clear_state()
    if not ok:
        return {"ok": False, "restored": restored, "error": "settings-write-failed"}
    return {"ok": True, "restored": restored, "error": ""}
