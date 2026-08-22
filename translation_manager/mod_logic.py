"""
Pure logic for detecting state and enabling / disabling / removing mod files.
No UI imports here - easy to unit-test or reuse from a CLI.
"""

import threading
from pathlib import Path
from typing import Callable

from .config import GameConfig


# Mod state constants
STATE_ACTIVE        = "ACTIVE"
STATE_DISABLED      = "DISABLED"
STATE_NOT_INSTALLED = "NOT_INSTALLED"     # files defined but absent → ready to install
STATE_NOT_AVAILABLE = "NOT_AVAILABLE"     # no mod package exists yet for this title
STATE_UNKNOWN       = "UNKNOWN"


def detect_state(game: GameConfig, base: Path) -> str:
    """Determine current mod state by inspecting expected files.

    Strict semantics so the UI never shows a "Remove" action on a game that
    has no actual mod files on disk:
      - No mod_files declared in config  → NOT_AVAILABLE (no package authored).
      - install dir missing              → NOT_INSTALLED.
      - all target files present         → ACTIVE.
      - all target files exist as .disabled → DISABLED.
      - none of either                   → NOT_INSTALLED.
      - mix of present/missing           → ACTIVE/DISABLED based on majority.
    """
    if not game.mod_files:
        return STATE_NOT_AVAILABLE
    if not base.exists():
        return STATE_NOT_INSTALLED

    active = 0
    disabled = 0
    for rel in game.mod_files:
        p = base / rel
        p_disabled = base / (rel + game.disabled_suffix)
        if p.exists():
            active += 1
        elif p_disabled.exists():
            disabled += 1

    total = len(game.mod_files)
    if active == total:
        return STATE_ACTIVE
    if disabled == total:
        return STATE_DISABLED
    if active == 0 and disabled == 0:
        return STATE_NOT_INSTALLED
    # Mixed - pick the dominant flavor
    return STATE_ACTIVE if active >= disabled else STATE_DISABLED


def enable_mod(game: GameConfig, base: Path) -> tuple[bool, int, str]:
    """Rename *.disabled → original name. Returns (ok, count, error_message)."""
    renamed = 0
    for rel in game.mod_files:
        p = base / rel
        p_disabled = base / (rel + game.disabled_suffix)
        if p_disabled.exists() and not p.exists():
            try:
                p_disabled.rename(p)
                renamed += 1
            except OSError as e:
                return False, renamed, str(e)
    return (renamed > 0), renamed, ""


def disable_mod(game: GameConfig, base: Path) -> tuple[bool, int, str]:
    """Rename active files → *.disabled (safe online mode)."""
    renamed = 0
    for rel in game.mod_files:
        p = base / rel
        p_disabled = base / (rel + game.disabled_suffix)
        if p.exists() and not p_disabled.exists():
            try:
                p.rename(p_disabled)
                renamed += 1
            except OSError as e:
                return False, renamed, str(e)
    return (renamed > 0), renamed, ""


def uninstall_mod(game: GameConfig, base: Path) -> tuple[bool, int, str]:
    """Delete both active and disabled mod files."""
    deleted = 0
    for rel in game.mod_files:
        for candidate in (base / rel, base / (rel + game.disabled_suffix)):
            if candidate.exists():
                try:
                    candidate.unlink()
                    deleted += 1
                except OSError as e:
                    return False, deleted, str(e)
    return (deleted > 0), deleted, ""


def autodetect_path(game: GameConfig, on_found: Callable[[str | None], None]) -> None:
    """Background scan of known install paths. Calls on_found(path_or_none) when done."""
    def worker():
        for raw in game.common_paths:
            p = Path(raw)
            if p.exists() and game.is_valid_dir(p):
                on_found(str(p))
                return
        on_found(None)

    threading.Thread(target=worker, daemon=True).start()
