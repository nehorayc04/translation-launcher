"""
Generic per-game in-game TEXT-language switcher.

Several Hebrew mods ship under a game's *Arabic* locale slot (Hebrew routed
through the engine's tested RTL/bidi pipeline). To play in Hebrew the user
must flip the game's text language to Arabic; to play vanilla they flip it
back to English. Doing that by hand (regedit / a settings file / a .bat)
is fiddly — this module makes it a one-click control in the launcher,
uniformly for every supported game.

Three user-facing modes:
    auto     — follow the mod: translated → Hebrew(Arabic), otherwise the
               pre-mod / English language.
    hebrew   — force the Arabic locale slot (= Hebrew on screen).
    english  — force English.
Plus restore_original() — put the language back to whatever it was the
first time the launcher ever touched it (the genuine pre-mod value).

Two mechanisms, declared per game in LANG_CONFIGS:
    registry  — a Windows HKCU DWORD (Insomniac / Marvel's Spider-Man 2).
    cp2077    — Cyberpunk's UserSettings.json (delegates to
                cp2077_language, reusing its robust schema walker).

Every public function returns a structured dict and NEVER raises — a
language flip is a convenience, it must not crash the launcher. The user's
original language is captured on the first write and persisted to
~/.translation_manager/game_langs.json so restore always works, even after
the game or mod is removed.

Adding a game: drop one entry in LANG_CONFIGS. Registry games need only the
subkey/value/codes; a new file-based mechanism would get its own _read/_write
branch alongside the registry + cp2077 ones.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Per-game language configuration
# ─────────────────────────────────────────────────────────────
# kind="registry": flip a HKCU DWORD.
#   subkey  — under HKEY_CURRENT_USER
#   value   — the DWORD value name
#   codes   — {"english": <int>, "hebrew": <int>}  (hebrew == the Arabic slot)
#   extra   — other DWORDs to pin on every write (e.g. keep English voice)
#
# kind="cp2077": delegate to cp2077_language (UserSettings.json Text+Subtitles).
#   codes   — {"english": "en-us", "hebrew": "ar-ar"}
LANG_CONFIGS: dict[str, dict[str, Any]] = {
    "spiderman2": {
        "kind":   "registry",
        "subkey": r"Software\Insomniac Games\Marvel's Spider-Man 2",
        "value":  "TextLanguage",
        "codes":  {"english": 0, "hebrew": 18},   # 18 = Arabic slot
        # Keep the voice-over English regardless of the on-screen text
        # language — matches the standalone LanguageSwitcher.ps1 behaviour.
        "extra":  {"englishVO": 1},
    },
    "cyberpunk": {
        "kind":  "cp2077",
        "codes": {"english": "en-us", "hebrew": "ar-ar"},
    },
}

_MODES = ("auto", "hebrew", "english")

# Per-user state — sits next to the launcher's other runtime sidecars so it
# auto-cleans with them. Shape: {game_id: {"mode": str, "original": <code>}}.
_STATE_DIR  = Path.home() / ".translation_manager"
_STATE_FILE = _STATE_DIR / "game_langs.json"


# ─────────────────────────────────────────────────────────────
# State persistence
# ─────────────────────────────────────────────────────────────
def _state_load() -> dict[str, Any]:
    try:
        if _STATE_FILE.exists():
            data = json.loads(_STATE_FILE.read_text(encoding="utf-8-sig"))
            if isinstance(data, dict):
                return data
    except (OSError, json.JSONDecodeError) as e:
        log.warning("game_language: cannot read state — %s", e)
    return {}


def _state_save(data: dict[str, Any]) -> None:
    try:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = _STATE_FILE.with_suffix(".tm-tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, _STATE_FILE)
    except OSError as e:
        log.warning("game_language: cannot write state — %s", e)


def _state_for(game_id: str) -> dict[str, Any]:
    entry = _state_load().get(game_id)
    return entry if isinstance(entry, dict) else {}


def _state_update(game_id: str, **fields: Any) -> None:
    data = _state_load()
    entry = data.get(game_id)
    if not isinstance(entry, dict):
        entry = {}
    entry.update(fields)
    data[game_id] = entry
    _state_save(data)


# ─────────────────────────────────────────────────────────────
# Registry mechanism (Windows HKCU DWORD)
# ─────────────────────────────────────────────────────────────
def _reg_read(cfg: dict[str, Any]) -> int | None:
    if sys.platform != "win32":
        return None
    try:
        import winreg
    except ImportError:                                  # pragma: no cover
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, cfg["subkey"]) as key:
            val, _ = winreg.QueryValueEx(key, cfg["value"])
            return int(val)
    except FileNotFoundError:
        return None                                      # game never launched yet
    except OSError as e:                                 # pragma: no cover
        log.warning("game_language: registry read failed — %s", e)
        return None


def _reg_write(cfg: dict[str, Any], code: int) -> tuple[bool, str]:
    if sys.platform != "win32":
        return False, "registry-not-supported-on-this-os"
    try:
        import winreg
    except ImportError:                                  # pragma: no cover
        return False, "winreg-unavailable"
    try:
        key = winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER, cfg["subkey"], 0,
            winreg.KEY_READ | winreg.KEY_WRITE,
        )
        try:
            winreg.SetValueEx(key, cfg["value"], 0, winreg.REG_DWORD, int(code))
            for name, dword in (cfg.get("extra") or {}).items():
                winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, int(dword))
        finally:
            winreg.CloseKey(key)
        return True, ""
    except OSError as e:
        log.warning("game_language: registry write failed — %s", e)
        return False, f"registry-write-failed: {e}"


# ─────────────────────────────────────────────────────────────
# CP2077 mechanism (UserSettings.json — delegate to cp2077_language)
# ─────────────────────────────────────────────────────────────
def _cp_read(cfg: dict[str, Any]) -> str | None:
    try:
        from translation_manager import cp2077_language as cp
        return cp.current_text_language()
    except Exception as e:                               # pragma: no cover
        log.warning("game_language: cp2077 read failed — %s", e)
        return None


def _cp_write(cfg: dict[str, Any], locale: str) -> tuple[bool, str]:
    try:
        from translation_manager import cp2077_language as cp
        r = cp.set_text_language(locale)
        return bool(r.get("ok")), str(r.get("error") or "")
    except Exception as e:                               # pragma: no cover
        return False, str(e)


# ─────────────────────────────────────────────────────────────
# Mechanism dispatch
# ─────────────────────────────────────────────────────────────
def _read_raw(cfg: dict[str, Any]) -> Any:
    if cfg["kind"] == "registry":
        return _reg_read(cfg)
    if cfg["kind"] == "cp2077":
        return _cp_read(cfg)
    return None


def _write_raw(cfg: dict[str, Any], code: Any) -> tuple[bool, str]:
    if cfg["kind"] == "registry":
        return _reg_write(cfg, code)
    if cfg["kind"] == "cp2077":
        return _cp_write(cfg, code)
    return False, "unknown-mechanism"


def _name_of(cfg: dict[str, Any], code: Any) -> str:
    """Map a raw code back to a language name. 'other' = a third language the
    user had set (e.g. a non-English vanilla locale)."""
    if code is None:
        return "unknown"
    codes = cfg["codes"]
    if code == codes["hebrew"]:
        return "hebrew"
    if code == codes["english"]:
        return "english"
    return "other"


def _resolve_code(cfg: dict[str, Any], mode: str, installed: bool | None, original: Any) -> Any:
    codes = cfg["codes"]
    if mode == "hebrew":
        return codes["hebrew"]
    if mode == "english":
        return codes["english"]
    # auto — follow the mod. installed is None for games the launcher doesn't
    # track (e.g. Spider-Man 2 via Overstrike); there the translated state is
    # the launcher's whole purpose, so auto means Hebrew.
    if installed is None:
        installed = True
    if installed:
        return codes["hebrew"]
    return original if original is not None else codes["english"]


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────
def is_supported(game_id: str) -> bool:
    return game_id in LANG_CONFIGS


def get_state(game_id: str, installed: bool | None = None) -> dict[str, Any]:
    """Snapshot for the UI:
        {supported, kind, mode, current, currentCode,
         original, originalName, error}
    `current` is the language live in the game right now; `mode` is the
    user's chosen switch position (drives which segment is highlighted)."""
    cfg = LANG_CONFIGS.get(game_id)
    if cfg is None:
        return {"supported": False}
    cur = _read_raw(cfg)
    st  = _state_for(game_id)
    orig = st.get("original")
    return {
        "supported":   True,
        "kind":        cfg["kind"],
        "mode":        st.get("mode") if st.get("mode") in _MODES else "auto",
        "current":     _name_of(cfg, cur),
        "currentCode": cur,
        "original":    orig,
        "originalName": _name_of(cfg, orig) if orig is not None else None,
        "error":       "",
    }


def set_mode(game_id: str, mode: str, installed: bool | None = None) -> dict[str, Any]:
    """Apply a language mode now and persist it.

    Captures the user's CURRENT (pre-change) language as `original` the very
    first time we ever write — so a later restore_original() truly reverts to
    the pre-mod state, never to a value we ourselves wrote."""
    cfg = LANG_CONFIGS.get(game_id)
    if cfg is None:
        return {"ok": False, "supported": False, "error": "unsupported-game"}
    if mode not in _MODES:
        return {"ok": False, "supported": True, "error": f"bad-mode: {mode}"}

    st   = _state_for(game_id)
    orig = st.get("original")
    if orig is None:
        cur = _read_raw(cfg)
        if cur is not None:
            orig = cur                                    # capture the pre-mod value once

    target = _resolve_code(cfg, mode, installed, orig)
    ok, err = _write_raw(cfg, target)
    if ok:
        _state_update(game_id, mode=mode, **({"original": orig} if orig is not None else {}))
    return {
        "ok":        ok,
        "supported": True,
        "mode":      mode,
        "applied":   _name_of(cfg, target),
        "error":     err,
    }


def restore_original(game_id: str) -> dict[str, Any]:
    """Write the captured pre-mod language back. Falls back to English when no
    original was ever captured. Leaves `original` intact so it stays
    repeatable."""
    cfg = LANG_CONFIGS.get(game_id)
    if cfg is None:
        return {"ok": False, "supported": False, "error": "unsupported-game"}
    st   = _state_for(game_id)
    orig = st.get("original")
    if orig is None:
        orig = cfg["codes"]["english"]
    ok, err = _write_raw(cfg, orig)
    if ok:
        name = _name_of(cfg, orig)
        _state_update(game_id, mode=name if name in _MODES else "auto")
    return {"ok": ok, "supported": True, "restored": _name_of(cfg, orig),
            "restoredCode": orig, "error": err}


def apply_for_mod_state(game_id: str, installed: bool) -> dict[str, Any]:
    """Lifecycle hook: re-apply the language when a mod is installed/removed.

    Only acts in 'auto' mode — if the user explicitly forced Hebrew or English
    via the switch, their choice is respected and this is a no-op. Returns a
    PASS-through dict (supported=False for games with no language config) so
    callers can ignore it freely."""
    if game_id not in LANG_CONFIGS:
        return {"supported": False}
    mode = _state_for(game_id).get("mode") or "auto"
    if mode != "auto":
        return {"ok": True, "supported": True, "mode": mode, "skipped": "manual-override"}
    return set_mode(game_id, "auto", installed=installed)
