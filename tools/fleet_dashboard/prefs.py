# -*- coding: utf-8 -*-
"""User preferences for the dashboard — same shape and same options as the launcher's own.

Mirrors `frontend/src/lib/themePrefs.ts`: an animation LEVEL (not a boolean), a backdrop mode, a
text-size percentage on a 5% grid, a sidebar mode, and an accent. Plus this tool's own display
switches (what is shown and what is hidden) and refresh cadences.

Stored next to the rate history so the whole tool keeps its state in one place.
"""
from __future__ import annotations

import json
import os

ANIM_LEVELS = ["high", "normal", "low", "off"]          # מלאה / רגילה / מופחתת / כבויה
ANIM_LABELS = {"high": "מלאה", "normal": "רגילה", "low": "מופחתת", "off": "כבויה"}
# The multiplier every animation duration is scaled by. "off" is 0 => no animation at all.
ANIM_FACTOR = {"high": 1.0, "normal": 0.75, "low": 0.35, "off": 0.0}

BACKDROPS = ["glass", "acrylic", "mica", "none"]
BACKDROP_LABELS = {"glass": "זכוכית", "acrylic": "אקריליק", "mica": "מיקה", "none": "אטום"}

SIDEBAR_MODES = ["auto", "wide", "narrow"]
SIDEBAR_LABELS = {"auto": "נפתח במעבר עכבר", "wide": "נעוץ פתוח", "narrow": "נעוץ מכווץ"}

# The launcher's own palette + its per-nav accents, so a swatch here matches a swatch there.
ACCENTS = {
    "cyan": "#00ffe0", "yellow": "#fff700", "gold": "#d4af37",
    "blue": "#00c2ff", "green": "#22c55e", "violet": "#a78bfa",
}

DEFAULTS = {
    "anim": "high",
    "backdrop": "glass",
    "text_size": 100,                 # 75..125 in steps of 5, exactly like the launcher
    "sidebar": "auto",
    "accent": "cyan",
    "custom_titlebar": True,
    "ripple": True,
    # what is shown / hidden
    "show_games": {},                 # {game_id: bool} — missing = shown
    "hide_info": False,               # hide INFO-level findings
    "hide_finished": False,           # hide streams that finished their shard
    "columns": {"game": True, "machine": True, "provider": True, "state": True,
                "progress": True, "remaining": True, "rate": True, "out_age": True,
                "pid": False, "reason": True},
    "overview_panels": {"cards": True, "warnings": True, "samples": True, "providers": True},
    # cadences (seconds / minutes)
    "local_seconds": 15,
    "remote_seconds": 90,
    "rate_window_minutes": 20,
    "samples_keep": 120,
    "window": None,                   # [x, y, w, h] restored on start
}


def _state_root() -> str:
    r"""%LOCALAPPDATA%\FleetDash — resolved from the REAL profile, not the environment.

    🔴 When this tool is launched from the Antigravity IDE, LOCALAPPDATA (and ~) point at a
    sandbox profile, while the user's own double-click gets the real one. That split means the
    same app reads two different prefs/stream-id files depending on who started it — the stream
    numbers I quote would not be the numbers the user sees. FOLDERID_Profile reads the token, so
    both runs agree.
    """
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(1024)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 40, None, 0, buf) == 0 and buf.value:
            return os.path.join(buf.value, "AppData", "Local", "FleetDash")
    except Exception:
        pass
    return os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "FleetDash")


def _path() -> str:
    root = _state_root()
    os.makedirs(root, exist_ok=True)
    return os.path.join(root, "prefs.json")


def load() -> dict:
    p = dict(DEFAULTS)
    try:
        with open(_path(), encoding="utf-8") as fh:
            saved = json.load(fh)
        for k, v in saved.items():
            if k in p and isinstance(p[k], dict) and isinstance(v, dict):
                merged = dict(p[k])
                merged.update(v)
                p[k] = merged
            elif k in p:
                p[k] = v
    except Exception:
        pass                                    # first run / corrupt file -> defaults, never crash
    p["anim"] = p["anim"] if p["anim"] in ANIM_LEVELS else "high"
    p["backdrop"] = p["backdrop"] if p["backdrop"] in BACKDROPS else "glass"
    p["sidebar"] = p["sidebar"] if p["sidebar"] in SIDEBAR_MODES else "auto"
    p["accent"] = p["accent"] if p["accent"] in ACCENTS else "cyan"
    try:
        p["text_size"] = min(125, max(75, 5 * round(int(p["text_size"]) / 5)))
    except Exception:
        p["text_size"] = 100
    return p


def save(p: dict) -> None:
    try:
        tmp = _path() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(p, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, _path())                # atomic: a kill mid-write can't corrupt prefs
    except Exception:
        pass


def factor(p: dict) -> float:
    return ANIM_FACTOR.get(p.get("anim", "high"), 1.0)


def accent_hex(p: dict) -> str:
    return ACCENTS.get(p.get("accent", "cyan"), "#00ffe0")
