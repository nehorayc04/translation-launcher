"""
User overrides for game install paths.

Persists to `<user-home>/.translation_manager/custom_paths.json`. Library
view consults this BEFORE falling back to the auto-detector, so a manual
path always wins.
"""

from pathlib import Path

_STORE_DIR  = Path.home() / ".translation_manager"
_STORE_FILE = _STORE_DIR / "custom_paths.json"


def _load() -> dict[str, str]:
    """Self-healing read. A corrupt/truncated custom_paths.json no longer wipes
    every path the user typed in: resilience falls back to the `.bak` sidecar
    (and repairs the primary from it) before it ever returns an empty dict."""
    from . import resilience
    data = resilience.read_json(_STORE_FILE, default={}, name="paths")
    return data if isinstance(data, dict) else {}


def _save(data: dict[str, str]) -> None:
    """Self-healing write: atomic (temp + os.replace), keeps the previous good
    version as `.bak`, retries through a transient AV/indexer file lock, and - if
    the location is genuinely unwritable - parks the payload rather than losing
    the user's manually-entered install paths."""
    from . import resilience
    resilience.write_json(_STORE_FILE, data, name="paths")


def get(game_id: str) -> Path | None:
    raw = _load().get(game_id)
    # isinstance guard: a hand-corrupted custom_paths.json with a non-string
    # value (e.g. {"cyberpunk": 5}) would make Path(raw) raise TypeError.
    if isinstance(raw, str) and raw:
        p = Path(raw)
        if p.exists():
            return p
    return None


def set_path(game_id: str, path: str | None) -> None:
    data = _load()
    if path:
        data[game_id] = str(path)
    else:
        data.pop(game_id, None)
    _save(data)


# ── the exact EXE the user picked (for DISPLAY only) ─────────────────────────
# The install path stored above is always the game ROOT folder (every applier
# writes into it). Separately, we remember the full EXE path the user picked in
# the "choose file" dialog so the Settings field can SHOW it. Kept in its own
# file so the root-path schema/functions above are untouched.
_EXE_FILE = _STORE_DIR / "custom_exes.json"


def _load_exes() -> dict[str, str]:
    from . import resilience
    data = resilience.read_json(_EXE_FILE, default={}, name="exes")
    return data if isinstance(data, dict) else {}


def get_exe(game_id: str) -> str | None:
    """The full EXE path the user picked for this game, if it still exists."""
    raw = _load_exes().get(game_id)
    if isinstance(raw, str) and raw:
        p = Path(raw)
        if p.is_file():
            return str(p)
    return None


def set_exe(game_id: str, exe: str | None) -> None:
    from . import resilience
    data = _load_exes()
    if exe:
        data[game_id] = str(exe)
    else:
        data.pop(game_id, None)
    resilience.write_json(_EXE_FILE, data, name="exes")


def all_paths() -> dict[str, Path]:
    # Skip non-string values defensively - a hand-corrupted JSON value
    # would otherwise make Path(p) raise TypeError mid-comprehension and
    # break the whole library view.
    out: dict[str, Path] = {}
    for gid, p in _load().items():
        if not isinstance(p, str):
            continue
        pp = Path(p)
        if pp.exists():
            out[gid] = pp
    return out
