"""
Generic per-game in-game TEXT-language switcher.

Several Hebrew mods ship under a game's *Arabic* locale slot (Hebrew routed
through the engine's tested RTL/bidi pipeline). To play in Hebrew the user
must flip the game's text language to Arabic; to play vanilla they flip it
back to English. Doing that by hand (regedit / a settings file / a .bat)
is fiddly - this module makes it a one-click control in the launcher,
uniformly for every supported game.

Three user-facing modes:
    auto     - follow the mod: translated → Hebrew(Arabic), otherwise the
               pre-mod / English language.
    hebrew   - force the Arabic locale slot (= Hebrew on screen).
    english  - force English.
Plus restore_original() - put the language back to whatever it was the
first time the launcher ever touched it (the genuine pre-mod value).

Two mechanisms, declared per game in LANG_CONFIGS:
    registry  - a Windows HKCU DWORD (Insomniac / Marvel's Spider-Man 2).
    cp2077    - Cyberpunk's UserSettings.json (delegates to
                cp2077_language, reusing its robust schema walker).

Every public function returns a structured dict and NEVER raises - a
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
import re
import sys
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Per-game language configuration
# ─────────────────────────────────────────────────────────────
# kind="registry": flip a HKCU DWORD.
#   subkey  - under HKEY_CURRENT_USER
#   value   - the DWORD value name
#   codes   - {"english": <int>, "hebrew": <int>}  (hebrew == the Arabic slot)
#   extra   - other DWORDs to pin on every write (e.g. keep English voice)
#
# kind="cp2077": delegate to cp2077_language (UserSettings.json Text+Subtitles).
#   codes   - {"english": "en-us", "hebrew": "ar-ar"}
LANG_CONFIGS: dict[str, dict[str, Any]] = {
    "spiderman2": {
        "kind":   "registry",
        "subkey": r"Software\Insomniac Games\Marvel's Spider-Man 2",
        "value":  "TextLanguage",
        "codes":  {"english": 0, "hebrew": 18},   # 18 = Arabic slot
        # Keep the voice-over English regardless of the on-screen text
        # language - matches the standalone LanguageSwitcher.ps1 behaviour.
        "extra":  {"englishVO": 1},
    },
    "cyberpunk": {
        "kind":  "cp2077",
        "codes": {"english": "en-us", "hebrew": "ar-ar"},
    },
    # VirtualDJ (software) - the active UI language is one XML element in the
    # user's settings file: <language modified="yes">Arabic</language>.
    # The Hebrew translation ships inside the ARABIC slot (Languages\Arabic.xml),
    # so "hebrew" == Arabic here, exactly like the Arabic-slot games.
    "virtualdj": {
        "kind":     "xmltag",
        "env":      "LOCALAPPDATA",
        "relpath":  ("VirtualDJ", "settings.xml"),
        "tag":      "language",
        "codes":    {"english": "English", "hebrew": "Arabic"},
    },
    # The Witcher 3 - the active TEXT language is one key in a plain INI settings
    # file: Documents\The Witcher 3\user.settings, [Localization] TextLanguage=EN.
    # The Hebrew mod ships inside the ARABIC slot (ar.w3strings) and renames the
    # in-game selector to "Hebrew", so "hebrew" == "AR" here. VoiceLanguage is
    # left untouched (English voice stays). Edit is surgical + backed up + atomic.
    "witcher3": {
        "kind":    "ini",
        "docsub":  ("The Witcher 3", "user.settings"),
        "section": "Localization",
        "key":     "TextLanguage",
        "codes":   {"english": "EN", "hebrew": "AR"},
    },
    # Borderless Gaming (software) - the active UI language is ONE flat key in
    # %APPDATA%\coreutils\borderless-gaming\settings.json: {"language": "he-IL"}.
    # Unlike every other title here this one gets a REAL Hebrew locale (the app
    # SCANS its languages folder), so "hebrew" is he-IL, not an Arabic-slot hijack.
    #
    # english is the shipped "en-US" locale, NOT the vanilla "" (= follow the
    # system): with our he-IL file installed, "" on a Hebrew Windows would pick
    # Hebrew again, so the switch would not switch. restore_original() still
    # returns the captured pre-mod value (normally ""), so reverting is exact.
    "borderless-gaming": {
        "kind":    "json",
        "relpath": ("coreutils", "borderless-gaming", "settings.json"),
        "key":     "language",
        "codes":   {"english": "en-US", "hebrew": "he-IL"},
    },
    # SignalRGB (software) - the active UI language is ONE REG_SZ value:
    # HKCU\\Software\\WhirlwindFX\\SignalRgb\\UI  Locale = "ar".  The Hebrew
    # translation ships inside the ARABIC slot of the exe, so "hebrew" == "ar";
    # "english" is the shipped "en_US" locale.  Read by the app's
    # SignalTranslation::FetchCurrentLocaleFromRegistry.
    "signalrgb": {
        "kind":   "regsz",
        "subkey": r"Software\WhirlwindFX\SignalRgb\UI",
        "value":  "Locale",
        # "ar" is accepted, but the app canonicalises it to "ar_EG" (its Arabic
        # locale id = the .qm slot), so read/report on that exact string.
        "codes":  {"english": "en_US", "hebrew": "ar_EG"},
    },
}

_MODES = ("auto", "hebrew", "english")

# Per-user state - sits next to the launcher's other runtime sidecars so it
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
        log.warning("game_language: cannot read state - %s", e)
    return {}


def _state_save(data: dict[str, Any]) -> None:
    try:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = _STATE_FILE.with_suffix(".tm-tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, _STATE_FILE)
    except OSError as e:
        log.warning("game_language: cannot write state - %s", e)


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
        log.warning("game_language: registry read failed - %s", e)
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
        log.warning("game_language: registry write failed - %s", e)
        return False, f"registry-write-failed: {e}"


def _regsz_read(cfg: dict[str, Any]) -> str | None:
    """A REG_SZ (string) HKCU value — e.g. SignalRGB's UI\\Locale."""
    if sys.platform != "win32":
        return None
    try:
        import winreg
    except ImportError:                                  # pragma: no cover
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, cfg["subkey"]) as key:
            val, _ = winreg.QueryValueEx(key, cfg["value"])
            return str(val)
    except FileNotFoundError:
        return None
    except OSError as e:                                 # pragma: no cover
        log.warning("game_language: regsz read failed - %s", e)
        return None


def _regsz_write(cfg: dict[str, Any], code: str) -> tuple[bool, str]:
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
            winreg.SetValueEx(key, cfg["value"], 0, winreg.REG_SZ, str(code))
        finally:
            winreg.CloseKey(key)
        return True, ""
    except OSError as e:
        log.warning("game_language: regsz write failed - %s", e)
        return False, f"registry-write-failed: {e}"


# ─────────────────────────────────────────────────────────────
# CP2077 mechanism (UserSettings.json - delegate to cp2077_language)
# ─────────────────────────────────────────────────────────────
def _cp_read(cfg: dict[str, Any]) -> str | None:
    try:
        from translation_manager import cp2077_language as cp
        return cp.current_text_language()
    except Exception as e:                               # pragma: no cover
        log.warning("game_language: cp2077 read failed - %s", e)
        return None


def _cp_write(cfg: dict[str, Any], locale: str) -> tuple[bool, str]:
    try:
        from translation_manager import cp2077_language as cp
        r = cp.set_text_language(locale)
        return bool(r.get("ok")), str(r.get("error") or "")
    except Exception as e:                               # pragma: no cover
        return False, str(e)


# ─────────────────────────────────────────────────────────────
# XML-tag mechanism (one element's text in a settings file - VirtualDJ)
# ─────────────────────────────────────────────────────────────
def _xml_path(cfg: dict[str, Any]) -> Path | None:
    base = os.environ.get(cfg["env"]) if cfg.get("env") else None
    if not base:
        return None
    return Path(base).joinpath(*cfg["relpath"])


def _xml_re(cfg: dict[str, Any]) -> re.Pattern[str]:
    tag = re.escape(cfg["tag"])
    # <language modified="yes">Arabic</language>  → keep the attributes as-is.
    return re.compile(rf"(<{tag}\b[^>]*>)(.*?)(</{tag}>)", re.DOTALL)


def _xml_read(cfg: dict[str, Any]) -> str | None:
    p = _xml_path(cfg)
    if p is None or not p.is_file():
        return None                                      # app never launched yet
    try:
        m = _xml_re(cfg).search(p.read_text(encoding="utf-8-sig", errors="replace"))
    except OSError as e:                                 # pragma: no cover
        log.warning("game_language: xml read failed - %s", e)
        return None
    return m.group(2).strip() if m else None


def _xml_write(cfg: dict[str, Any], value: str) -> tuple[bool, str]:
    p = _xml_path(cfg)
    if p is None:
        return False, "settings-path-unavailable"
    if not p.is_file():
        # The app writes this file on first run/exit - nothing to flip yet.
        return False, "settings-file-missing"
    try:
        text = p.read_text(encoding="utf-8-sig", errors="replace")
        new, n = _xml_re(cfg).subn(lambda m: f"{m.group(1)}{value}{m.group(3)}", text, count=1)
        if n == 0:
            return False, "language-tag-not-found"
        tmp = p.with_suffix(p.suffix + ".tm-tmp")
        tmp.write_text(new, encoding="utf-8")
        os.replace(tmp, p)                               # atomic - never a half file
        return True, ""
    except OSError as e:
        log.warning("game_language: xml write failed - %s", e)
        return False, f"settings-write-failed: {e}"


# ─────────────────────────────────────────────────────────────
# JSON mechanism (one top-level string key in a settings.json - Borderless Gaming)
# ─────────────────────────────────────────────────────────────
def _real_appdata() -> Path | None:
    """Roaming AppData under the REAL user profile.

    Deliberately NOT %APPDATA% and NOT FOLDERID_RoamingAppData: when the process
    runs under a redirected/sandboxed profile BOTH of those resolve to the
    sandbox, so the write lands in a folder the app never reads (this exact trap
    silently swallowed the first Borderless Gaming deploy). FOLDERID_Profile is
    the only one that always resolves to the true C:\\Users\\<user>.
    """
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes
            class GUID(ctypes.Structure):
                _fields_ = [("a", wintypes.DWORD), ("b", wintypes.WORD),
                            ("c", wintypes.WORD), ("d", ctypes.c_ubyte * 8)]
            # FOLDERID_Profile {5E6C858F-0E22-4760-9AFE-EA3317B67173}
            fid = GUID(0x5E6C858F, 0x0E22, 0x4760,
                       (ctypes.c_ubyte * 8)(0x9A, 0xFE, 0xEA, 0x33, 0x17, 0xB6, 0x71, 0x73))
            out = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(
                    ctypes.byref(fid), 0, None, ctypes.byref(out)) == 0:
                try:
                    profile = Path(out.value)
                finally:
                    ctypes.windll.ole32.CoTaskMemFree(out)
                cand = profile / "AppData" / "Roaming"
                if cand.is_dir():
                    return cand
        except Exception as e:                               # pragma: no cover
            log.warning("game_language: FOLDERID_Profile lookup failed - %s", e)
    base = os.environ.get("APPDATA")
    return Path(base) if base else None


def _json_path(cfg: dict[str, Any]) -> Path | None:
    base = _real_appdata()
    return None if base is None else base.joinpath(*cfg["relpath"])


def _json_read(cfg: dict[str, Any]) -> str | None:
    p = _json_path(cfg)
    if p is None or not p.is_file():
        return None                                          # app never launched yet
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig", errors="replace"))
    except (OSError, ValueError) as e:
        log.warning("game_language: json read failed - %s", e)
        return None
    if not isinstance(data, dict):
        return None
    val = data.get(cfg["key"])
    return val if isinstance(val, str) else None


def _json_write(cfg: dict[str, Any], value: str) -> tuple[bool, str]:
    p = _json_path(cfg)
    if p is None:
        return False, "settings-path-unavailable"
    if not p.is_file():
        return False, "settings-file-missing"                # written on first run
    try:
        text = p.read_text(encoding="utf-8-sig", errors="replace")
        data = json.loads(text)                              # validate before touching
        if not isinstance(data, dict) or cfg["key"] not in data:
            return False, "language-key-not-found"
        # Surgical: rewrite ONLY this key's value so every other setting keeps
        # its exact bytes/formatting. Never ADD the key - a schema we don't
        # recognise is a no-op, not a guess.
        rx = re.compile(rf'("{re.escape(cfg["key"])}"\s*:\s*)"[^"\\]*(?:\\.[^"\\]*)*"')
        new, n = rx.subn(lambda m: m.group(1) + json.dumps(value), text, count=1)
        if n == 0:
            return False, "language-key-not-found"
        json.loads(new)                                      # never write invalid JSON
        tmp = p.with_suffix(p.suffix + ".tm-tmp")
        tmp.write_text(new, encoding="utf-8")
        os.replace(tmp, p)                                   # atomic - never a half file
        return True, ""
    except (OSError, ValueError) as e:
        log.warning("game_language: json write failed - %s", e)
        return False, f"settings-write-failed: {e}"


# ─────────────────────────────────────────────────────────────
# INI mechanism (one KEY under one [SECTION] in a plain settings file - W3)
# ─────────────────────────────────────────────────────────────
def _documents_dir() -> Path:
    """Real Documents known-folder (OneDrive-redirect aware), fallback ~/Documents."""
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
            ) as k:
                val, _ = winreg.QueryValueEx(k, "Personal")
                if val:
                    return Path(os.path.expandvars(val))
        except OSError:
            pass
    return Path.home() / "Documents"


def _ini_path(cfg: dict[str, Any]) -> Path | None:
    if cfg.get("env"):
        base = os.environ.get(cfg["env"])
        if not base:
            return None
        return Path(base).joinpath(*cfg["docsub"])
    return _documents_dir().joinpath(*cfg["docsub"])


def _ini_read(cfg: dict[str, Any]) -> str | None:
    p = _ini_path(cfg)
    if p is None or not p.is_file():
        return None                                      # game never launched yet
    try:
        lines = p.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    except OSError as e:                                 # pragma: no cover
        log.warning("game_language: ini read failed - %s", e)
        return None
    target, key = cfg["section"].strip().lower(), cfg["key"].strip().lower()
    in_section = False
    for ln in lines:
        s = ln.strip()
        if s.startswith("[") and s.endswith("]"):
            in_section = s[1:-1].strip().lower() == target
            continue
        if in_section and "=" in ln:
            k, _, v = ln.partition("=")
            if k.strip().lower() == key:
                return v.strip()
    return None


def _ini_write(cfg: dict[str, Any], value: str) -> tuple[bool, str]:
    p = _ini_path(cfg)
    if p is None:
        return False, "settings-path-unavailable"
    if not p.is_file():
        # The game writes this file on first run/exit - nothing to flip yet.
        return False, "settings-file-missing"
    try:
        raw = p.read_text(encoding="utf-8-sig", errors="replace")
        newline = "\r\n" if "\r\n" in raw else "\n"
        lines = raw.split(newline)
        target, key = cfg["section"].strip().lower(), cfg["key"].strip().lower()
        in_section = done = False
        for i, ln in enumerate(lines):
            s = ln.strip()
            if s.startswith("[") and s.endswith("]"):
                in_section = s[1:-1].strip().lower() == target
                continue
            if in_section and not done and "=" in ln:
                k, sep, _ = ln.partition("=")
                if k.strip().lower() == key:
                    lines[i] = f"{k}{sep}{value}"         # preserve the key's exact spelling/spacing
                    done = True
        if not done:
            # Never ADD lines - a missing key means an unexpected file; no-op.
            return False, "language-key-not-found"
        # One-time recovery backup before the very first edit.
        bak = p.with_suffix(p.suffix + ".tm-lang-backup")
        if not bak.exists():
            try:
                bak.write_bytes(p.read_bytes())
            except OSError:                              # pragma: no cover
                pass
        tmp = p.with_suffix(p.suffix + ".tm-tmp")
        tmp.write_text(newline.join(lines), encoding="utf-8")
        os.replace(tmp, p)                               # atomic - never a half file
        return True, ""
    except OSError as e:
        log.warning("game_language: ini write failed - %s", e)
        return False, f"settings-write-failed: {e}"


# ─────────────────────────────────────────────────────────────
# Mechanism dispatch
# ─────────────────────────────────────────────────────────────
def _read_raw(cfg: dict[str, Any]) -> Any:
    if cfg["kind"] == "registry":
        return _reg_read(cfg)
    if cfg["kind"] == "regsz":
        return _regsz_read(cfg)
    if cfg["kind"] == "cp2077":
        return _cp_read(cfg)
    if cfg["kind"] == "xmltag":
        return _xml_read(cfg)
    if cfg["kind"] == "ini":
        return _ini_read(cfg)
    if cfg["kind"] == "json":
        return _json_read(cfg)
    return None


def _write_raw(cfg: dict[str, Any], code: Any) -> tuple[bool, str]:
    if cfg["kind"] == "registry":
        return _reg_write(cfg, code)
    if cfg["kind"] == "regsz":
        return _regsz_write(cfg, str(code))
    if cfg["kind"] == "cp2077":
        return _cp_write(cfg, code)
    if cfg["kind"] == "xmltag":
        return _xml_write(cfg, str(code))
    if cfg["kind"] == "ini":
        return _ini_write(cfg, str(code))
    if cfg["kind"] == "json":
        return _json_write(cfg, str(code))
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
    # auto - follow the mod. installed is None for games the launcher doesn't
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
    first time we ever write - so a later restore_original() truly reverts to
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

    Only acts in 'auto' mode - if the user explicitly forced Hebrew or English
    via the switch, their choice is respected and this is a no-op. Returns a
    PASS-through dict (supported=False for games with no language config) so
    callers can ignore it freely."""
    if game_id not in LANG_CONFIGS:
        return {"supported": False}
    mode = _state_for(game_id).get("mode") or "auto"
    if mode != "auto":
        return {"ok": True, "supported": True, "mode": mode, "skipped": "manual-override"}
    return set_mode(game_id, "auto", installed=installed)
