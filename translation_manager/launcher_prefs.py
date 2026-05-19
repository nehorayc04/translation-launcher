"""
Persisted user preferences for the launcher window/lifecycle.

Stores a small JSON file alongside the launcher's other per-user state
(`~/.translation_manager/launcher_prefs.json`). Used to remember:

- close_behavior  : "minimize" | "close" | None (None == ask the user)
- start_with_os   : whether the launcher should boot at Windows startup
                    (the actual registry write is in `autostart.py`; this
                    is the source-of-truth flag the UI toggle binds to)

API is intentionally tiny — every read returns a fresh dict so callers
don't have to worry about cache invalidation, and every write is atomic
(temp file + os.replace) so a crashed process can't leave the file half-
written.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Literal, TypedDict

log = logging.getLogger(__name__)

CloseBehavior = Literal["minimize", "close"]


class LauncherPrefs(TypedDict, total=False):
    close_behavior: CloseBehavior        # None = unset → first-launch modal
    start_with_os:  bool                 # mirrors the registry state


_STATE_DIR  = Path.home() / ".translation_manager"
_STATE_FILE = _STATE_DIR / "launcher_prefs.json"


# ─────────────────────────────────────────────────────────────
def load() -> LauncherPrefs:
    """Return the prefs dict. Missing/corrupted file → empty dict."""
    if not _STATE_FILE.exists():
        return {}
    try:
        data = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        log.warning("launcher_prefs: cannot read %s — %s", _STATE_FILE, e)
        return {}
    return data if isinstance(data, dict) else {}


def save(prefs: LauncherPrefs) -> bool:
    """Atomic write. Returns True on success."""
    try:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = _STATE_FILE.with_suffix(_STATE_FILE.suffix + ".tm-tmp")
        tmp.write_text(json.dumps(prefs, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        os.replace(tmp, _STATE_FILE)
        return True
    except OSError as e:
        log.warning("launcher_prefs: write failed — %s", e)
        return False


# ── convenience getters / setters ────────────────────────────
def get_close_behavior() -> CloseBehavior | None:
    val = load().get("close_behavior")
    if val in ("minimize", "close"):
        return val  # type: ignore[return-value]
    return None


def set_close_behavior(behavior: CloseBehavior) -> bool:
    prefs = load()
    prefs["close_behavior"] = behavior
    return save(prefs)


def clear_close_behavior() -> bool:
    prefs = load()
    prefs.pop("close_behavior", None)
    return save(prefs)


def get_start_with_os() -> bool:
    return bool(load().get("start_with_os", False))


def set_start_with_os(enabled: bool) -> bool:
    prefs = load()
    prefs["start_with_os"] = bool(enabled)
    return save(prefs)
