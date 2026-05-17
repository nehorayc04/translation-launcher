"""
User overrides for game install paths.

Persists to `<user-home>/.translation_manager/custom_paths.json`. Library
view consults this BEFORE falling back to the auto-detector, so a manual
path always wins.
"""

import json
from pathlib import Path

_STORE_DIR  = Path.home() / ".translation_manager"
_STORE_FILE = _STORE_DIR / "custom_paths.json"


def _load() -> dict[str, str]:
    if not _STORE_FILE.exists():
        return {}
    try:
        return json.loads(_STORE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save(data: dict[str, str]) -> None:
    _STORE_DIR.mkdir(parents=True, exist_ok=True)
    _STORE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                           encoding="utf-8")


def get(game_id: str) -> Path | None:
    raw = _load().get(game_id)
    if raw:
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


def all_paths() -> dict[str, Path]:
    return {gid: Path(p) for gid, p in _load().items() if Path(p).exists()}
