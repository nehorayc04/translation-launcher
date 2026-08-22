"""
plugins.game_copilot - the "Live Game Co-Pilot" plugin engine.

What it does (see the README section in CLAUDE.md "game co-pilot" for the
full design): while a game is running the user can press a configurable
hotkey (or a button in this plugin's settings) to pop a small always-on-top
panel over the game. The panel shows what game/situation is on screen and a
short, clear, step-by-step Hebrew explanation of what to do - produced by
sending a screenshot + a short prompt to an AI vision model (Google Gemini or
OpenAI, the user's OWN API key).

Split of responsibilities, same shape as save_backup.py / engine.py:
  * THIS module is the stateless "kind" engine - config shape, the capture +
    AI pipeline, and the plain dispatch table `run_action()` that
    `plugins/engine.py` delegates to for `kind == "game_copilot"`. It never
    touches Qt.
  * `qt_shell/game_copilot_runtime.py` is the Qt-specific runtime: the actual
    always-on-top overlay widget + the global hotkey (Win32 RegisterHotKey).
    It polls this module's tiny thread-safe IPC (`request_toggle` /
    `request_show` / `poll_pending`) from its own GUI-thread timer, so a
    button click on a background (QThreadPool) worker thread can still tell
    the GUI thread to show/hide the overlay without ever touching a QWidget
    off-thread.

The API key is NEVER stored in the plugin's plain-JSON config (which lives at
`~/.translation_manager/plugins/state.json`) - it goes through the OS keyring
(the same `keyring` package `auth/storage.py` already depends on), exactly
like every other credential this app holds.
"""
from __future__ import annotations

import io
import logging
import os
import sys
import time
import threading

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Config shape / option tables
# ─────────────────────────────────────────────────────────────
DEFAULT_PROVIDER = "gemini"

PROVIDER_OPTIONS = [
    {"value": "gemini", "label": "Google Gemini (מהיר, יש מפתח חינמי)"},
    {"value": "openai", "label": "OpenAI (GPT-4o)"},
    {"value": "groq", "label": "Groq (מהיר מאוד, יש מפתח חינמי)"},
    {"value": "nvidia", "label": "NVIDIA NIM (nvapi, יש מפתח חינמי)"},
    {"value": "sambanova", "label": "SambaNova (יש מפתח חינמי)"},
]

# Where to point "get a free key" for each provider (ONE generic button in the
# UI, see get_state()'s `keyUrl`, instead of one hardcoded row per provider).
_PROVIDER_KEY_URL = {
    "gemini":    "https://aistudio.google.com/app/apikey",
    "openai":    "https://platform.openai.com/api-keys",
    "groq":      "https://console.groq.com/keys",
    "nvidia":    "https://build.nvidia.com/",
    "sambanova": "https://cloud.sambanova.ai/apis",
}

# Every provider here except Gemini speaks the SAME OpenAI-compatible chat-
# completions REST shape (this project already leans on that fact for its
# translation fleet - see universal/fleet_providers.py) - only the base URL
# differs. Groq additionally needs a real browser User-Agent (Cloudflare
# 1010-blocks the default urllib UA; same fix used there).
_OPENAI_COMPAT_BASE = {
    "openai":    "https://api.openai.com/v1/chat/completions",
    "groq":      "https://api.groq.com/openai/v1/chat/completions",
    "nvidia":    "https://integrate.api.nvidia.com/v1/chat/completions",
    "sambanova": "https://api.sambanova.ai/v1/chat/completions",
}
_PROVIDER_DISPLAY = {
    "gemini": "Gemini", "openai": "OpenAI", "groq": "Groq",
    "nvidia": "NVIDIA NIM", "sambanova": "SambaNova",
}

# Each model states whether it accepts an IMAGE. A text-only model still
# works (the AI gets the game's name/window title instead of pixels), but
# sending a screenshot to a model that can't use it just wastes the call -
# analyze() skips the capture up front for those, and the UI shows a note.
MODEL_OPTIONS: dict[str, list[dict]] = {
    "gemini": [
        {"value": "gemini-2.5-flash", "label": "Gemini 2.5 Flash", "vision": True},
        {"value": "gemini-2.0-flash", "label": "Gemini 2.0 Flash", "vision": True},
        {"value": "gemini-1.5-flash", "label": "Gemini 1.5 Flash", "vision": True},
    ],
    "openai": [
        {"value": "gpt-4o-mini", "label": "GPT-4o mini (מהיר וזול)", "vision": True},
        {"value": "gpt-4o", "label": "GPT-4o (איכותי יותר)", "vision": True},
    ],
    "groq": [
        {"value": "meta-llama/llama-4-scout-17b-16e-instruct",
         "label": "Llama 4 Scout (תומך תמונות, מומלץ)", "vision": True},
        {"value": "meta-llama/llama-4-maverick-17b-128e-instruct",
         "label": "Llama 4 Maverick (תומך תמונות, מדויק ואיטי יותר)", "vision": True},
        {"value": "openai/gpt-oss-120b",
         "label": "GPT-OSS 120B (טקסט בלבד, בלי ניתוח תמונה)", "vision": False},
    ],
    "nvidia": [
        {"value": "meta/llama-3.2-90b-vision-instruct",
         "label": "Llama 3.2 90B Vision (מומלץ)", "vision": True},
        {"value": "meta/llama-3.2-11b-vision-instruct",
         "label": "Llama 3.2 11B Vision (מהיר יותר)", "vision": True},
        {"value": "meta/llama-3.1-70b-instruct",
         "label": "Llama 3.1 70B (טקסט בלבד, בלי ניתוח תמונה)", "vision": False},
    ],
    "sambanova": [
        {"value": "Llama-3.2-90B-Vision-Instruct",
         "label": "Llama 3.2 90B Vision (אם זמין לחשבון שלכם)", "vision": True},
        {"value": "Meta-Llama-3.3-70B-Instruct",
         "label": "Llama 3.3 70B (טקסט בלבד, בלי ניתוח תמונה)", "vision": False},
        {"value": "DeepSeek-V3.2",
         "label": "DeepSeek V3.2 (טקסט בלבד, בלי ניתוח תמונה)", "vision": False},
    ],
}


def _model_info(provider: str, model: str) -> dict | None:
    return next((m for m in MODEL_OPTIONS.get(provider, []) if m["value"] == model), None)


def _model_supports_vision(provider: str, model: str) -> bool:
    info = _model_info(provider, model)
    return bool(info["vision"]) if info else True

# Win32 hotkey modifiers (RegisterHotKey). Kept here as plain ints (no ctypes
# import in this module) so the Qt runtime can read one shared table.
_MOD_ALT, _MOD_CONTROL, _MOD_SHIFT, _MOD_WIN = 0x1, 0x2, 0x4, 0x8

# LEGACY preset table - no longer offered in the UI (the Settings panel now
# does a real physical key/gamepad CAPTURE, see `start_capture` below and
# `qt_shell/game_copilot_runtime._CaptureDialog`). Kept ONLY so an already-
# persisted `cfg["hotkey"]` string (a preset value from before this change)
# still migrates cleanly via `_normalize_hotkey` instead of breaking.
HOTKEY_OPTIONS = [
    {"value": "ctrl+shift+g", "label": "Ctrl + Shift + G",
     "mods": _MOD_CONTROL | _MOD_SHIFT, "vk": 0x47},
    {"value": "ctrl+alt+g", "label": "Ctrl + Alt + G",
     "mods": _MOD_CONTROL | _MOD_ALT, "vk": 0x47},
    {"value": "alt+shift+g", "label": "Alt + Shift + G",
     "mods": _MOD_ALT | _MOD_SHIFT, "vk": 0x47},
    {"value": "ctrl+shift+h", "label": "Ctrl + Shift + H",
     "mods": _MOD_CONTROL | _MOD_SHIFT, "vk": 0x48},
    {"value": "ctrl+shift+j", "label": "Ctrl + Shift + J",
     "mods": _MOD_CONTROL | _MOD_SHIFT, "vk": 0x4A},
    {"value": "f9", "label": "F9 בלבד", "mods": 0, "vk": 0x78},
    {"value": "f10", "label": "F10 בלבד", "mods": 0, "vk": 0x79},
    {"value": "ctrl+f10", "label": "Ctrl + F10", "mods": _MOD_CONTROL, "vk": 0x79},
]

# The panel docks FLUSH to a screen EDGE (with an arrow-handle to collapse/
# expand it) instead of floating in a corner. PRIMARY way to position it is
# now a long-press-and-drag on the handle itself (Samsung-side-panel style -
# see the Qt runtime's _OverlayPanel drag handling), which snaps to whichever
# of the 4 edges is nearest and remembers WHERE along that edge (`edge_pos`,
# a 0..1 fraction) the panel was dropped. This dropdown is the coarse
# keyboard/no-mouse-drag fallback - picking a value here resets `edge_pos`
# back to centered (0.5), since a discrete choice carries no "where along the
# edge" information. `_normalize_edge` migrates an old 2-value/4-corner value.
EDGE_OPTIONS = [
    {"value": "right", "label": "בצד ימין של המסך"},
    {"value": "left", "label": "בצד שמאל של המסך"},
    {"value": "top", "label": "בחלק העליון של המסך"},
    {"value": "bottom", "label": "בחלק התחתון של המסך"},
]
DEFAULT_EDGE = "right"
DEFAULT_EDGE_POS = 0.5

# How the panel's surface is drawn. Two genuinely different materials, and
# which one looks right is a taste call - so it is a setting, not a guess:
#   glass - Windows' acrylic blurs the game behind the panel (frosted).
#   tint  - no blur at all: the game stays SHARP through a slightly darkened
#           see-through panel. Also the cheaper option (no acrylic surface to
#           re-sample), which matters because this is on screen while a game
#           is running.
SURFACE_OPTIONS = [
    {"value": "tint", "label": "שקוף עם הכהיה קלה (המשחק נשאר חד)"},
    {"value": "glass", "label": "זכוכית מטושטשת (הרקע מיטשטש)"},
]
DEFAULT_SURFACE = "tint"


def _normalize_surface(value) -> str:
    return value if value in {o["value"] for o in SURFACE_OPTIONS} else DEFAULT_SURFACE


def hotkey_spec(value: str) -> dict | None:
    for o in HOTKEY_OPTIONS:
        if o["value"] == value:
            return o
    return None


def _default_hotkey() -> dict:
    return {"type": "keyboard", "mods": _MOD_CONTROL | _MOD_SHIFT, "vk": 0x47,
            "label": "Ctrl + Shift + G"}


def _normalize_hotkey(value) -> dict:
    """Accepts the NEW captured shape ({type:'keyboard'|'gamepad', ...}) as-is;
    migrates an OLD preset-string value (from before real key-capture existed)
    via the legacy table; falls back to the built-in default for anything
    else (missing / corrupt / unrecognised)."""
    if isinstance(value, dict) and value.get("type") in ("keyboard", "gamepad") and value.get("label"):
        return value
    if isinstance(value, str) and value:
        spec = hotkey_spec(value)
        if spec:
            return {"type": "keyboard", "mods": spec["mods"], "vk": spec["vk"], "label": spec["label"]}
    return _default_hotkey()


def hotkey_label(cfg: dict) -> str:
    return _normalize_hotkey((cfg or {}).get("hotkey")).get("label") or ""


_EDGE_MIGRATE = {"top-right": "right", "bottom-right": "right",
                  "top-left": "left", "bottom-left": "left"}
_EDGE_VALUES = {"left", "right", "top", "bottom"}


def _normalize_edge(value) -> str:
    if value in _EDGE_VALUES:
        return value
    return _EDGE_MIGRATE.get(value, DEFAULT_EDGE)


def _normalize_edge_pos(value) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return DEFAULT_EDGE_POS
    if f != f:                                        # NaN guard
        return DEFAULT_EDGE_POS
    return max(0.0, min(1.0, f))


def _default_model(provider: str) -> str:
    opts = MODEL_OPTIONS.get(provider) or MODEL_OPTIONS[DEFAULT_PROVIDER]
    return opts[0]["value"]


def _effective_model(provider: str, cfg: dict) -> str:
    """The model id to actually use for `provider`, given a saved config.

    A provider can retire a model id we used to offer (this just happened -
    Groq pulled llama-3.3-70b-versatile). If someone's persisted `model` is
    no longer a real entry in MODEL_OPTIONS[provider], silently fall back to
    that provider's current default instead of sending a dead id to the API
    or leaving the Settings dropdown with a stale, unmatched selection.
    """
    saved = cfg.get("model") or ""
    if saved and any(o["value"] == saved for o in MODEL_OPTIONS.get(provider, [])):
        return saved
    return _default_model(provider)


def default_config() -> dict:
    return {
        "provider": DEFAULT_PROVIDER,
        "model": _default_model(DEFAULT_PROVIDER),
        "hotkey": _default_hotkey(),
        "corner": DEFAULT_EDGE,
        "edge_pos": DEFAULT_EDGE_POS,
        "surface": DEFAULT_SURFACE,
        "last_game": "",
        "last_at": 0,
        "last_text": "",
        "last_ok": True,
        "last_error": "",
    }


def _entitled() -> bool:
    from . import registry
    try:
        return bool(registry.can_use_plugins())
    except Exception:                                        # pragma: no cover
        return False


def _fmt_ts(ts: int) -> str:
    if not ts:
        return ""
    try:
        import datetime
        return datetime.datetime.fromtimestamp(int(ts)).strftime("%d/%m %H:%M")
    except Exception:                                        # pragma: no cover
        return ""


# ─────────────────────────────────────────────────────────────
# API key storage - OS keyring, never the plain-JSON plugin config
# ─────────────────────────────────────────────────────────────
_KEYRING_SERVICE = "TranslationManagerGameCopilot"


def _keyring_user(provider: str) -> str:
    return f"api_key_{provider}"


def has_api_key(provider: str) -> bool:
    return bool(get_api_key(provider))


def get_api_key(provider: str) -> str:
    try:
        import keyring
        return keyring.get_password(_KEYRING_SERVICE, _keyring_user(provider)) or ""
    except Exception:                                        # pragma: no cover
        log.debug("game_copilot: keyring read failed", exc_info=True)
        return ""


def set_api_key(provider: str, key: str) -> bool:
    try:
        import keyring
        keyring.set_password(_KEYRING_SERVICE, _keyring_user(provider), (key or "").strip())
        return True
    except Exception:                                        # pragma: no cover
        log.warning("game_copilot: keyring write failed", exc_info=True)
        return False


def clear_api_key(provider: str) -> None:
    try:
        import keyring
        keyring.delete_password(_KEYRING_SERVICE, _keyring_user(provider))
    except Exception:                                        # pragma: no cover
        pass


# ─────────────────────────────────────────────────────────────
# Thread-safe IPC toward the Qt runtime (see the module docstring).
# Plain module-level state guarded by a lock - this is all ONE process, so no
# real IPC is needed, just safe cross-thread signalling without touching Qt
# from a non-GUI thread.
# ─────────────────────────────────────────────────────────────
_lock = threading.Lock()
_runtime_status = {"visible": False, "hotkey_ok": False, "hotkey_label": ""}
_pending = {"toggle_seq": 0, "show_seq": 0, "show_game": "", "show_text": ""}


def report_runtime_status(*, visible: bool | None = None, hotkey_ok: bool | None = None,
                           hotkey_label: str | None = None) -> None:
    """Called by the Qt runtime (GUI thread) to publish its live status, read
    back by `get_state()` for the settings panel."""
    with _lock:
        if visible is not None:
            _runtime_status["visible"] = bool(visible)
        if hotkey_ok is not None:
            _runtime_status["hotkey_ok"] = bool(hotkey_ok)
        if hotkey_label is not None:
            _runtime_status["hotkey_label"] = hotkey_label


def _status_snapshot() -> dict:
    with _lock:
        return dict(_runtime_status)


def _overlay_is_visible() -> bool:
    """Is OUR panel on screen right now? The capture happens while it is (it
    holds the "analysing" state), so the prompt has to tell the model to
    ignore it - see `_build_prompt(overlay_visible=...)`. Safe from the
    analysis thread; it is the same lock every other reader uses."""
    with _lock:
        return bool(_runtime_status.get("visible"))


def request_toggle() -> None:
    """Ask the Qt runtime to show/hide the overlay. Safe from ANY thread."""
    with _lock:
        _pending["toggle_seq"] += 1


def request_show(game: str, text: str) -> None:
    """Ask the Qt runtime to show the overlay with a ready result. Safe from
    ANY thread."""
    with _lock:
        _pending["show_seq"] += 1
        _pending["show_game"] = game or ""
        _pending["show_text"] = text or ""


def poll_pending(last_toggle_seq: int, last_show_seq: int) -> dict:
    """Called ONLY by the Qt runtime's GUI-thread poll timer."""
    with _lock:
        return {
            "toggle_seq": _pending["toggle_seq"],
            "toggled": _pending["toggle_seq"] != last_toggle_seq,
            "show_seq": _pending["show_seq"],
            "shown": _pending["show_seq"] != last_show_seq,
            "show_game": _pending["show_game"],
            "show_text": _pending["show_text"],
        }


def _status_text(status: dict) -> str:
    if sys.platform != "win32":
        return "מקש הקיצור והחלונית הצפה זמינים רק בגרסת Windows של התוכנה."
    if not status.get("hotkey_ok"):
        return ("התוסף פעיל, אבל מקש הקיצור עדיין לא נקלט (ייתכן שהוא תפוס "
                "ע\"י תוכנה אחרת) - תמיד אפשר להשתמש בכפתור \"הצג/הסתר\" למטה.")
    label = status.get("hotkey_label") or ""
    vis = "גלויה כרגע" if status.get("visible") else "מוסתרת כרגע"
    return f"התוסף פעיל · מקש הקיצור {label} מוכן · החלונית {vis}."


# ─────────────────────────────────────────────────────────────
# Foreground-window / capture (Win32, best-effort, in-memory only - a
# screenshot is NEVER written to disk).
# ─────────────────────────────────────────────────────────────
def _foreground_window_info() -> dict | None:
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes
        u = ctypes.windll.user32
        u.GetForegroundWindow.restype = wintypes.HWND
        u.GetForegroundWindow.argtypes = []
        u.GetWindowTextLengthW.restype = ctypes.c_int
        u.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        u.GetWindowTextW.restype = ctypes.c_int
        u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        u.GetWindowThreadProcessId.restype = wintypes.DWORD
        u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        u.GetWindowRect.restype = wintypes.BOOL
        u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]

        hwnd = u.GetForegroundWindow()
        if not hwnd:
            return None
        length = u.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        u.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value or ""

        pid = wintypes.DWORD(0)
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

        rect = wintypes.RECT()
        bbox = None
        if u.GetWindowRect(hwnd, ctypes.byref(rect)) and rect.right > rect.left and rect.bottom > rect.top:
            bbox = (rect.left, rect.top, rect.right, rect.bottom)

        return {"hwnd": int(hwnd), "title": title, "pid": int(pid.value), "bbox": bbox}
    except Exception:                                        # pragma: no cover
        log.debug("game_copilot: foreground probe failed", exc_info=True)
        return None


def _process_exe_name(pid: int) -> str:
    if not pid or sys.platform != "win32":
        return ""
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.windll.kernel32
        k32.OpenProcess.restype = wintypes.HANDLE
        k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        k32.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        k32.CloseHandle.restype = wintypes.BOOL
        k32.CloseHandle.argtypes = [wintypes.HANDLE]

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not h:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(260)
            size = wintypes.DWORD(260)
            if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                return buf.value or ""
        finally:
            k32.CloseHandle(h)
    except Exception:                                        # pragma: no cover
        log.debug("game_copilot: exe name lookup failed", exc_info=True)
    return ""


# Windows that are NOT the thing the user wants explained - a browser, a
# chat app, the launcher itself. Recognising them is what lets the answer
# CHANGE SUBJECT when the user alts-tab out of the game instead of stubbornly
# explaining a quest that is no longer on screen.
_KNOWN_APPS = {
    "chrome": "דפדפן Chrome", "msedge": "דפדפן Edge", "firefox": "דפדפן Firefox",
    "brave": "דפדפן Brave", "opera": "דפדפן Opera",
    "explorer": "סייר הקבצים של Windows", "notepad": "פנקס רשימות",
    "code": "Visual Studio Code", "devenv": "Visual Studio",
    "discord": "Discord", "whatsapp": "WhatsApp", "telegram": "Telegram",
    "spotify": "Spotify", "vlc": "נגן VLC", "obs64": "OBS Studio",
    "steam": "Steam", "steamwebhelper": "Steam", "epicgameslauncher": "Epic Games",
    "upc": "Ubisoft Connect", "battle.net": "Battle.net", "galaxyclient": "GOG Galaxy",
    "translationmanager": "מנהל התרגומים (התוכנה הזו)",
}


def detect_context(win: dict | None) -> dict:
    """What is the user actually looking at?

    Returns {title, exe, catalog_id, app, is_game, display}. `is_game` is
    True only when the launcher's OWN games catalog recognises the window -
    everything else is reported honestly as an app, so the AI adapts its
    answer to the screen in front of the user rather than assuming a game.
    """
    if not win:
        return {"title": "", "exe": "", "catalog_id": "", "app": "", "is_game": False, "display": ""}
    title = (win.get("title") or "").strip()
    exe_path = _process_exe_name(win.get("pid") or 0)
    exe = os.path.splitext(os.path.basename(exe_path))[0] if exe_path else ""

    catalog_id = ""
    try:
        from .. import game_detector
        catalog_id = game_detector.match_to_catalog(title) or ""
        if not catalog_id and exe:
            # A game in exclusive fullscreen often has a useless window title
            # ("", the engine name); its EXE almost never lies.
            catalog_id = game_detector.match_to_catalog(exe) or ""
    except Exception:                                        # pragma: no cover
        pass

    app = _KNOWN_APPS.get(exe.lower(), "")
    return {"title": title, "exe": exe, "catalog_id": catalog_id, "app": app,
            "is_game": bool(catalog_id), "display": title or app or exe}


def detect_game_name(win: dict | None) -> tuple[str, str]:
    """(display_name, hint) - kept for callers/tests that predate
    `detect_context`."""
    ctx = detect_context(win)
    return ctx["display"], (ctx["catalog_id"] or ctx["exe"] or "")


def _monitor_rect(hwnd: int | None) -> tuple[int, int, int, int] | None:
    """The FULL bounds of the monitor the given window is on, in
    virtual-desktop coordinates (which is exactly what Pillow's
    `grab(bbox=..., all_screens=True)` expects - it subtracts the virtual
    screen's own offset, so a monitor to the left of the primary, with
    negative coordinates, is handled correctly)."""
    if not hwnd or sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD),
                        ("rcMonitor", wintypes.RECT),
                        ("rcWork", wintypes.RECT),
                        ("dwFlags", wintypes.DWORD)]

        u = ctypes.windll.user32
        u.MonitorFromWindow.restype = wintypes.HANDLE
        u.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        u.GetMonitorInfoW.restype = wintypes.BOOL
        u.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MONITORINFO)]

        MONITOR_DEFAULTTONEAREST = 2
        mon = u.MonitorFromWindow(wintypes.HWND(hwnd), MONITOR_DEFAULTTONEAREST)
        if not mon:
            return None
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if not u.GetMonitorInfoW(mon, ctypes.byref(info)):
            return None
        r = info.rcMonitor
        if r.right <= r.left or r.bottom <= r.top:
            return None
        return (int(r.left), int(r.top), int(r.right), int(r.bottom))
    except Exception:                                        # pragma: no cover
        log.debug("game_copilot: monitor probe failed", exc_info=True)
        return None


def _capture_screen(win: dict | None) -> tuple[bytes, tuple[int, int]] | None:
    """JPEG bytes of the WHOLE SCREEN the active window is on (plus the
    captured pixel size) - or None on any failure (incl. an
    exclusive-fullscreen black frame, which plain GDI capture cannot read;
    the user should run the game in borderless-windowed mode). Never
    written to disk.

    🔴 The FULL MONITOR, not the window rect. A window crop hides exactly
    what the answer needs - the HUD, the minimap, the quest tracker and the
    prompts all live at the screen edges, and half of them sit outside a
    windowed game's client area. It also makes the capture behave the same
    whether the game is windowed, borderless or maximised."""
    try:
        from PIL import ImageGrab
        bbox = _monitor_rect((win or {}).get("hwnd")) or (win or {}).get("bbox")
        img = ImageGrab.grab(bbox=bbox, all_screens=True) if bbox else ImageGrab.grab(all_screens=True)
        if img is None:
            return None
        shot = img.size
        # 1536 (was 1280) at q85 (was 72): the whole point of this feature is
        # now READING the screen - a quest name, an objective line, a tooltip -
        # and small UI type is the first thing a hard downscale plus JPEG
        # ringing destroys.
        img.thumbnail((1536, 1536))
        try:
            lo, hi = img.convert("L").getextrema()
            if hi == 0:
                return None
        except Exception:                                    # pragma: no cover
            pass
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=85, optimize=True)
        data = buf.getvalue()
        buf.close()
        return data, shot
    except Exception:                                        # pragma: no cover
        log.debug("game_copilot: capture failed", exc_info=True)
        return None


# ─────────────────────────────────────────────────────────────
# The AI call
# ─────────────────────────────────────────────────────────────
_SYSTEM_PROMPT = (
    "אתה עוזר חי (Co-Pilot) שרואה צילום מסך מלא של המסך של המשתמש ברגע זה. "
    "המשתמש רוצה לדעת בדיוק מה קורה על המסך עכשיו ומה עליו לעשות הלאה.\n\n"

    "שלב 1 - זהה במה מדובר. התמונה היא צילום של המסך המלא, לא של חלון בודד, "
    "ולכן ייתכן שרואים בה גם שולחן עבודה, סרגל משימות או חלונות נוספים. "
    "החליטו לפי מה שתופס את המסך: משחק? דפדפן? תוכנה? תפריט של משגר? "
    "אל תניחו שמדובר במשחק רק כי כך היה קודם - אם המשתמש עבר לחלון אחר, "
    "עברו איתו לנושא החדש והתייחסו למה שבאמת מוצג עכשיו.\n\n"

    "שלב 2 - קראו את כל מה שכתוב על המסך. זה החלק החשוב ביותר: עברו על הטקסט "
    "בתמונה וקראו אותו ממש - שם המשימה או הפרק, יעד המשימה ביומן או במעקב, "
    "כתוביות ודיאלוג, שמות של דמויות ופריטים, כפתורים והנחיות ('לחץ E'), "
    "מדדים ב-HUD (חיים, תחמושת, זמן, כסף), התראות ושגיאות, וכל טקסט בתפריט. "
    "מהטקסט הזה הסיקו מה המשימה הנוכחית ובאיזו סיטואציה נמצאת הדמות או "
    "המשתמש (קרב? חקירה? שיחה? תפריט? תקוע במקום מסוים?).\n\n"

    "שלב 3 - השלימו את התמונה. אם זיהיתם משימה, פרק, בוס, חידה או שגיאה בשם "
    "מפורש - חפשו מידע עדכני עליהם ברשת (אם יש לכם כלי חיפוש) והשתמשו בו כדי "
    "לתת פתרון מדויק ומוכח, לא ניחוש. אם אין כלי חיפוש, הסתמכו על הידע שלכם "
    "וציינו זאת. תמיד שלבו את מה שנמצא ברשת עם מה שבאמת רואים בתמונה - "
    "המסך הוא מקור האמת לגבי המצב הנוכחי.\n\n"

    "ענו תמיד בעברית תקנית, ברורה וממוקדת - בלי פרוזה מיותרת ובלי לחזור על "
    "עצמכם. מבנה קבוע, בדיוק כך (השמיטו שורה שאין לה תוכן אמיתי):\n"
    "🎮 מה על המסך: <שם המשחק, או שם התוכנה/האתר אם זה לא משחק>\n"
    "📖 כתוב על המסך: <הטקסטים החשובים שקראתם, במרכאות, עד 4 פריטים>\n"
    "📍 המצב: <היכן נמצאת הדמות/המשתמש ומה קורה כרגע>\n"
    "🎯 המטרה: <מה צריך להשיג עכשיו, משפט אחד-שניים>\n"
    "📋 שלבים:\n"
    "1. <שלב ראשון, קצר וברור>\n"
    "2. <שלב שני>\n"
    "3. <עד 6 שלבים לכל היותר>\n"
    "💡 טיפ: <טיפ אחד שימושי, אם יש>\n"
    "🔎 מקור: <'חיפוש ברשת' / 'ידע כללי' / 'מהתמונה בלבד' - מילה-שתיים>\n\n"

    "אם הטקסט על המסך לא קריא או שאין מספיק מידע לזהות משימה ספציפית - אמרו "
    "זאת במפורש, תארו מה כן רואים, והציעו את הצעד ההגיוני הבא. לעולם אל "
    "תמציאו שם משימה, פריט או מנגנון שאינכם בטוחים בהם; עדיף לכתוב "
    "'לא הצלחתי לקרוא' מאשר לנחש."
)


def _build_prompt(ctx: dict, *, can_search: bool, shot: tuple[int, int] | None,
                   previous: str = "", minutes_ago: int = 0,
                   overlay_visible: bool = False) -> str:
    """The whole context the model gets besides the picture. Everything here
    is something the model CANNOT see in the image (the real exe behind a
    fullscreen window, our own catalog match, what was on screen last time)."""
    lines: list[str] = []
    if overlay_visible:
        # Our own panel is shown BEFORE the capture (it holds the "analysing"
        # state), so it is genuinely in the screenshot - and step 2 tells the
        # model to read every word on screen, which would otherwise make it
        # report our own UI as part of the game. Only stated when the panel is
        # really up, so we never send it hunting for something that isn't there.
        lines.append("בתמונה מופיעה גם חלונית קטנה שלנו (רקע כהה, טקסט בעברית, "
                     "לשונית עם חץ בצד המסך) - התעלמו ממנה לגמרי, היא לא חלק ממה "
                     "שרץ על המסך ואין לתאר או לצטט אותה.")
    if ctx.get("title"):
        lines.append(f"כותרת החלון הפעיל: {ctx['title']}")
    if ctx.get("exe"):
        lines.append(f"תהליך פעיל: {ctx['exe']}.exe")
    if ctx.get("catalog_id"):
        lines.append(f"זוהה בקטלוג המשחקים של התוכנה: {ctx['catalog_id']} "
                     f"(כלומר זה כמעט בוודאות משחק)")
    elif ctx.get("app"):
        lines.append(f"זוהה כתוכנה: {ctx['app']} - כנראה לא משחק")
    if shot:
        lines.append(f"הצילום הוא המסך המלא ({shot[0]}x{shot[1]} פיקסלים), לא חלון בודד")
    # THE window-switch cue: without it the model has no way to know the
    # subject changed, and tends to keep explaining the previous game.
    if previous and previous != ctx.get("display"):
        when = f"לפני {minutes_ago} דקות" if minutes_ago > 0 else "קודם"
        lines.append(f"בפעם הקודמת ({when}) על המסך היה: {previous}. "
                     f"אם השתנה - התייחסו למה שמוצג עכשיו בלבד.")
    lines.append("יש לך כלי חיפוש ברשת - השתמש בו לשם המשימה/הבוס/השגיאה שקראת על המסך."
                 if can_search else
                 "אין לך כלי חיפוש ברשת - הסתמך על הידע שלך וציין זאת ב'מקור'.")
    return _SYSTEM_PROMPT + "\n\n" + "\n".join(lines) + "\n\nהנה צילום המסך המלא הנוכחי:"


def _extract_error_detail(resp) -> str:
    """The PROVIDER's own error text, if the response body carries one (both
    Gemini and OpenAI use the same {"error": {"message": ...}} shape) - shown
    to the user VERBATIM so a bad key / wrong model / quota problem is
    immediately obvious instead of a generic status code."""
    try:
        data = resp.json()
        if isinstance(data, dict):
            err = data.get("error")
            if isinstance(err, dict) and err.get("message"):
                return str(err["message"])
            if isinstance(err, str) and err:
                return err
    except Exception:                                          # pragma: no cover
        pass
    try:
        return (resp.text or "").strip()[:220]
    except Exception:                                          # pragma: no cover
        return ""


def _friendly_http_error(name: str, resp) -> str:
    code = getattr(resp, "status_code", 0)
    base = {
        401: f"מפתח ה-API של {name} שגוי או לא בתוקף",
        403: f"למפתח ה-API של {name} אין הרשאה לפעולה הזו (ייתכן שהמודל חסום למפתח הזה)",
        404: f"{name}: המודל שנבחר לא נמצא / לא זמין למפתח הזה",
        429: f"{name}: יותר מדי בקשות כרגע (או שהמכסה נוצלה) - נסו שוב בעוד רגע",
    }.get(code, f"{name} החזיר שגיאה (קוד {code})")
    detail = _extract_error_detail(resp)
    return f"{base} — {detail}" if detail else base


# Reading a whole screen, searching the web for the quest, and answering in
# seven sections needs more room and more time than the old 900/45s did - a
# truncated answer loses the STEPS, which are the part the user acts on.
_MAX_TOKENS = 1400
_TIMEOUT_S = 75          # the analysis runs on its own thread with no deadline
_VERIFY_TIMEOUT_S = 30   # ...but "save the key" must answer while they wait


def _extract_gemini_text(data: dict) -> str:
    try:
        cands = data.get("candidates") or []
        if not cands:
            fb = (data.get("promptFeedback") or {}).get("blockReason")
            raise RuntimeError(f"Gemini חסם את הבקשה ({fb})" if fb else "Gemini לא החזיר תשובה")
        parts = ((cands[0].get("content") or {}).get("parts")) or []
        text = "\n".join(p.get("text", "") for p in parts if isinstance(p, dict) and p.get("text"))
        return text.strip()
    except RuntimeError:
        raise
    except Exception as e:                                   # pragma: no cover
        raise RuntimeError(f"תשובת Gemini לא תקינה: {e}") from e


def _call_gemini(api_key: str, model: str, prompt: str, image_bytes: bytes | None,
                  timeout: int = _TIMEOUT_S) -> str:
    import base64
    import requests

    parts: list[dict] = [{"text": prompt}]
    if image_bytes:
        parts.append({"inline_data": {"mime_type": "image/jpeg",
                                       "data": base64.b64encode(image_bytes).decode("ascii")}})
    body = {
        "contents": [{"role": "user", "parts": parts}],
        # Reading text off a screen is a FACTUAL task - a lower temperature
        # transcribes what is there instead of paraphrasing it.
        "generationConfig": {"temperature": 0.25, "maxOutputTokens": _MAX_TOKENS},
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    last_err: str | None = None
    # Google-Search grounding, which is what lets the answer be about the
    # ACTUAL quest rather than a plausible-sounding guess. The tool's field
    # name changed between model generations (`google_search` on 2.x,
    # `google_search_retrieval` on 1.5), so try both before giving up on it -
    # a single attempt silently dropped grounding for a whole model family.
    # Falling through to no tool at all keeps an optional feature from
    # turning into a hard error.
    for tool in ({"google_search": {}}, {"google_search_retrieval": {}}, None):
        payload = dict(body)
        if tool is not None:
            payload["tools"] = [tool]
        try:
            r = requests.post(url, params={"key": api_key}, json=payload, timeout=timeout)
        except requests.RequestException as e:
            raise RuntimeError(f"תקלת רשת מול Gemini: {e}") from e
        if r.status_code == 200:
            return _extract_gemini_text(r.json())
        last_err = _friendly_http_error("Gemini", r)
        # Only a rejected TOOL is worth retrying - a bad key or a spent quota
        # will fail identically three times over and just slow the error down.
        if r.status_code not in (400, 403, 404):
            break
    raise RuntimeError(last_err or "Gemini לא החזיר תשובה")


# Cloudflare 403s ("error code 1010") the default python-requests/urllib
# User-Agent on Groq specifically - a real browser UA sails through. Same
# fix already used by universal/fleet_providers.py for the translation fleet.
_BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def _call_openai_compatible(name: str, base_url: str, api_key: str, model: str,
                             prompt: str, image_bytes: bytes | None,
                             timeout: int = _TIMEOUT_S) -> str:
    """The shared request/response shape behind OpenAI itself AND every
    OpenAI-compatible inference host this plugin offers (Groq / NVIDIA NIM /
    SambaNova) - identical `messages`/`content` request schema, identical
    `choices[0].message.content` reply. Only the base URL (and, for Groq,
    the User-Agent) differ per host."""
    import base64
    import requests

    content: list[dict] = [{"type": "text", "text": prompt}]
    if image_bytes:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
    body = {"model": model, "messages": [{"role": "user", "content": content}],
            "max_tokens": _MAX_TOKENS, "temperature": 0.25}
    headers = {"Authorization": f"Bearer {api_key}"}
    if name == "Groq":
        headers["User-Agent"] = _BROWSER_UA
    try:
        r = requests.post(base_url, headers=headers, json=body, timeout=timeout)
    except requests.RequestException as e:
        raise RuntimeError(f"תקלת רשת מול {name}: {e}") from e
    if r.status_code != 200:
        raise RuntimeError(_friendly_http_error(name, r))
    try:
        data = r.json()
        return (data["choices"][0]["message"]["content"] or "").strip()
    except Exception as e:                                   # pragma: no cover
        raise RuntimeError(f"תשובת {name} לא תקינה: {e}") from e


def _call_provider(provider: str, api_key: str, model: str, prompt: str,
                    image_bytes: bytes | None, timeout: int = _TIMEOUT_S) -> str:
    """Single dispatch point every caller goes through (analyze() AND
    verify_api_key()) - add a provider ONCE here and everything else
    (verification, the live analysis call) picks it up automatically.

    SECURITY: this is also the single choke point every error message
    passes through before reaching the UI or a persisted cfg["last_error"].
    Gemini sends its key as a URL query param, and a requests/urllib3
    network exception's str() commonly echoes the full request URL
    (including the query string) - so a plain connection error/timeout
    could otherwise leak the key straight into a visible status toast or
    an on-disk config file. Scrub it here so no per-provider call site has
    to remember to, and no future provider is missed.

    Catches `Exception`, not just the `RuntimeError` every call site above
    normally raises: the docstring's "no future provider is missed"
    guarantee only holds if this ALSO catches whatever unexpected exception
    type an unanticipated failure inside `requests`/`base64`/`json` might
    raise - a narrower catch would let that one slip through unscrubbed."""
    try:
        if provider == "gemini":
            return _call_gemini(api_key, model, prompt, image_bytes, timeout)
        name = _PROVIDER_DISPLAY.get(provider, provider)
        base_url = _OPENAI_COMPAT_BASE.get(provider, _OPENAI_COMPAT_BASE["openai"])
        return _call_openai_compatible(name, base_url, api_key, model, prompt,
                                       image_bytes, timeout)
    except Exception as e:
        msg = str(e)
        if api_key and api_key in msg:
            msg = msg.replace(api_key, "***")
        raise RuntimeError(msg) from e


def analyze(cfg: dict) -> dict:
    """The whole pipeline: detect the foreground window -> capture it ->
    build the prompt -> call the chosen AI -> return
    {ok, game, text, error}. Runs entirely off the GUI thread (safe to call
    from a QThreadPool worker or a plain background thread) - it never
    touches Qt."""
    provider = cfg.get("provider") or DEFAULT_PROVIDER
    if provider not in MODEL_OPTIONS:
        provider = DEFAULT_PROVIDER
    model = _effective_model(provider, cfg)
    api_key = get_api_key(provider)
    if not api_key:
        return {"ok": False, "error": f"לא הוגדר מפתח API עבור {provider}", "game": "", "text": ""}

    win = _foreground_window_info()
    ctx = detect_context(win)
    display_name = ctx["display"]
    supports_vision = _model_supports_vision(provider, model)
    capture_failed = False
    image = shot = None
    if supports_vision:
        grabbed = _capture_screen(win)
        capture_failed = grabbed is None
        if grabbed is not None:
            image, shot = grabbed

    # What was on screen the LAST time we ran. cfg is persisted by both call
    # sites (the hotkey path and the settings button), so this needs no state
    # of its own - and it is the only way the model can tell "the user moved
    # to another window" from "same game, new scene".
    # The cue's whole value is RECENCY, so it needs a timestamp: an entry with
    # no `last_at` (a config written before this field existed, or a partial
    # write) could be days old, and telling the model "previously you saw B"
    # about a week-old session is worse than saying nothing.
    last_at = int(cfg.get("last_at") or 0)
    mins = int((time.time() - last_at) // 60) if last_at else 0
    recent = bool(last_at) and 0 <= mins <= 120
    prompt = _build_prompt(
        ctx,
        # Web grounding is Gemini-only today; saying so keeps the model from
        # claiming it searched when it structurally cannot.
        can_search=(provider == "gemini"),
        shot=shot,
        previous=str(cfg.get("last_game") or "") if recent else "",
        minutes_ago=mins,
        overlay_visible=_overlay_is_visible(),
    )
    if not supports_vision:
        prompt += ("\n\n(שימו לב: המודל שנבחר לא תומך בניתוח תמונות - ההסבר הבא מבוסס רק "
                   "על שם/סוג המשחק שזוהה, לא על מה שבאמת מוצג על המסך כרגע.)")

    try:
        text = _call_provider(provider, api_key, model, prompt, image)
    except RuntimeError as e:
        return {"ok": False, "error": str(e), "game": display_name, "text": ""}
    except Exception as e:                                   # pragma: no cover
        return {"ok": False, "error": f"שגיאה לא צפויה: {e}", "game": display_name, "text": ""}

    if not text:
        return {"ok": False, "error": "לא התקבלה תשובה מהשירות", "game": display_name, "text": ""}
    if capture_failed:
        text = ("⚠️ לא הצלחתי לצלם את המסך (ייתכן שהמשחק רץ במסך-מלא בלעדי - נסו "
                 "מצב \"חלון ללא מסגרת\"). ההסבר הבא מבוסס רק על שם החלון:\n\n" + text)
    return {"ok": True, "error": "",
            "game": display_name or ctx.get("exe") or "לא מזוהה", "text": text}


def verify_api_key(provider: str, model: str, api_key: str) -> tuple[bool, str]:
    """A minimal, cheap, text-only call (no screenshot) that PROVES the key
    actually works for this model BEFORE we tell the user it was saved
    successfully - this is what turns a silent/later failure ("put in the
    key, nothing happens when I try it") into an immediate, specific verdict
    at the moment they click save."""
    try:
        _call_provider(provider, api_key, model, "Reply with exactly one word: OK", None,
                       _VERIFY_TIMEOUT_S)
        return True, "המפתח נשמר ואומת בהצלחה ✓"
    except RuntimeError as e:
        return False, str(e)
    except Exception as e:                                       # pragma: no cover
        return False, f"שגיאה לא צפויה באימות המפתח: {e}"


# ─────────────────────────────────────────────────────────────
# Thread-safe IPC toward the Qt runtime - hotkey/gamepad CAPTURE.
# Same shape as the toggle/show IPC above: `start_capture` (below, called on
# the WORKER thread that runs plugin_action) asks the runtime to pop a native
# capture window and then BLOCKS this worker thread (a plain sleep-poll -
# never touches Qt) until the runtime reports back a locked-in spec, a
# cancel, or nothing (timeout). The runtime's own capture window keeps
# pumping the Win32 message loop the whole time, so a global low-level
# keyboard hook / gamepad poll can run and the GUI stays fully responsive.
# ─────────────────────────────────────────────────────────────
_capture = {"seq": 0, "result": None}


def request_capture() -> int:
    with _lock:
        _capture["seq"] += 1
        _capture["result"] = None
        return _capture["seq"]


def poll_capture_request(last_seq: int) -> dict:
    with _lock:
        return {"seq": _capture["seq"], "requested": _capture["seq"] != last_seq}


def report_capture_result(seq: int, result) -> None:
    with _lock:
        if seq == _capture["seq"]:
            _capture["result"] = result


def await_capture_result(seq: int, timeout: float = 30.0):
    """dict (a locked spec) | "cancelled" | "stale" | "timeout"."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        with _lock:
            if _capture["seq"] != seq:
                return "stale"
            r = _capture["result"]
        if r is not None:
            return r
        time.sleep(0.08)
    return "timeout"


# ─────────────────────────────────────────────────────────────
# get_state() / run_action() - what plugins/engine.py delegates to for
# kind == "game_copilot" (see the branch added there).
# ─────────────────────────────────────────────────────────────
def get_state(pid: str) -> dict:
    from . import registry
    installed = registry.is_installed(pid)
    cfg = registry.get_config(pid) if installed else {}
    if not isinstance(cfg, dict):
        cfg = {}
    provider = cfg.get("provider") or DEFAULT_PROVIDER
    if provider not in MODEL_OPTIONS:
        provider = DEFAULT_PROVIDER
    status = _status_snapshot()
    last_text = cfg.get("last_text") or ""
    last_error = cfg.get("last_error") or ""
    model = _effective_model(provider, cfg)
    return {
        "entitled":           _entitled(),
        "installed":          installed,
        "enabled":            registry.is_enabled(pid) if installed else False,
        "provider":           provider,
        "providerOptions":    PROVIDER_OPTIONS,
        "keyUrl":             _PROVIDER_KEY_URL.get(provider, ""),
        "model":              model,
        "modelOptions":       MODEL_OPTIONS.get(provider, MODEL_OPTIONS[DEFAULT_PROVIDER]),
        "modelSupportsVision": _model_supports_vision(provider, model),
        "hotkeyLabel":      hotkey_label(cfg),
        "edge":             _normalize_edge(cfg.get("corner")),
        "edgePos":          _normalize_edge_pos(cfg.get("edge_pos")),
        "edgeOptions":      EDGE_OPTIONS,
        "surface":          _normalize_surface(cfg.get("surface")),
        "surfaceOptions":   SURFACE_OPTIONS,
        "hasApiKey":        has_api_key(provider),
        "lastGame":         cfg.get("last_game") or "",
        "lastAtDisplay":    _fmt_ts(cfg.get("last_at") or 0),
        "lastText":         last_text,
        "lastOk":           bool(cfg.get("last_ok", True)),
        "lastError":        last_error,
        "hasLastResult":    bool(last_text or last_error),
        "overlayVisible":   status["visible"],
        "hotkeyActive":     status["hotkey_ok"],
        "statusText":       _status_text(status),
    }


def run_action(pid: str, action: str, args: dict | None = None) -> dict:
    """Never raises - mirrors plugins/engine.py's own contract."""
    args = args if isinstance(args, dict) else {}
    a = (action or "").strip()

    if a in ("state", "refresh"):
        return {"ok": True, "state": get_state(pid)}

    if a == "open_url":
        url = str(args.get("url") or "")
        if url.startswith(("http://", "https://")):
            try:
                import webbrowser
                webbrowser.open(url)
            except Exception:                                # pragma: no cover
                log.debug("game_copilot: open_url failed", exc_info=True)
        return {"ok": True}

    from . import registry
    if not registry.is_installed(pid):
        return {"ok": False, "error": "not-installed"}
    cfg = registry.get_config(pid)
    if not isinstance(cfg, dict) or not cfg:
        cfg = default_config()

    if a == "set_provider":
        val = str(args.get("value") or "").strip()
        if val in MODEL_OPTIONS:
            registry.patch_config(pid, {"provider": val, "model": _default_model(val)})
        return {"ok": True, "state": get_state(pid)}

    if a == "set_model":
        val = str(args.get("value") or "").strip()
        provider = cfg.get("provider") or DEFAULT_PROVIDER
        if val in {o["value"] for o in MODEL_OPTIONS.get(provider, [])}:
            registry.patch_config(pid, {"model": val})
        return {"ok": True, "state": get_state(pid)}

    if a == "start_capture":
        # Ask the Qt runtime to pop its native capture window and BLOCK this
        # worker thread (never the GUI thread - see the IPC section above)
        # until the user physically presses a key/gamepad combo, cancels, or
        # nothing happens for 30s. `busyLabel` on the Settings button already
        # gives the "waiting for a keypress" feedback while this is pending.
        seq = request_capture()
        result = await_capture_result(seq, timeout=30.0)
        if isinstance(result, dict) and result.get("label"):
            registry.patch_config(pid, {"hotkey": result})
            return {"ok": True, "state": get_state(pid), "status": f"קיצור עודכן: {result['label']}"}
        if result == "cancelled":
            return {"ok": False, "state": get_state(pid), "status": "העריכה בוטלה"}
        return {"ok": False, "state": get_state(pid),
                "status": "לא זוהתה לחיצה בזמן - נסו שוב ולחצו על מקש/ים או כפתור/י שלט"}

    if a == "reset_hotkey":
        registry.patch_config(pid, {"hotkey": _default_hotkey()})
        return {"ok": True, "state": get_state(pid), "status": "מקש הקיצור אופס לברירת המחדל"}

    if a == "set_corner":
        val = str(args.get("value") or "").strip()
        if val in {o["value"] for o in EDGE_OPTIONS}:
            # a discrete pick has no along-edge info - center it
            registry.patch_config(pid, {"corner": val, "edge_pos": DEFAULT_EDGE_POS})
        return {"ok": True, "state": get_state(pid)}

    if a == "set_surface":
        val = _normalize_surface(args.get("value"))
        registry.patch_config(pid, {"surface": val})
        try:
            from ..qt_shell import game_copilot_runtime as _rt
            _rt.refresh_surface()                        # apply live, no restart
        except Exception:                                # pragma: no cover
            pass
        return {"ok": True, "state": get_state(pid)}

    if a == "set_api_key":
        key = str(args.get("key") or "").strip()
        provider = cfg.get("provider") or DEFAULT_PROVIDER
        model = _effective_model(provider, cfg)
        if not key:
            return {"ok": False, "error": "bad-args", "state": get_state(pid)}
        if not set_api_key(provider, key):
            return {"ok": False, "state": get_state(pid),
                     "status": "שמירת המפתח נכשלה (בעיה בגישה לאחסון המוצפן של Windows)"}
        # A keyring backend can report success without actually persisting
        # (a locked/misconfigured credential vault) - read it straight back
        # before telling the user it worked.
        if get_api_key(provider) != key:
            return {"ok": False, "state": get_state(pid),
                     "status": "שמירת המפתח נכשלה - האחסון המוצפן לא אישר את השמירה, נסו שוב"}
        verified, msg = verify_api_key(provider, model, key)
        return {"ok": verified, "state": get_state(pid),
                "status": (msg if verified else f"המפתח נשמר, אבל הבדיקה נכשלה: {msg}")}

    if a == "clear_api_key":
        provider = cfg.get("provider") or DEFAULT_PROVIDER
        clear_api_key(provider)
        return {"ok": True, "state": get_state(pid), "status": "המפתח נמחק"}

    if a == "toggle_overlay":
        request_toggle()
        return {"ok": True, "state": get_state(pid)}

    if a == "test_now":
        provider = cfg.get("provider") or DEFAULT_PROVIDER
        if not has_api_key(provider):
            return {"ok": False, "state": get_state(pid), "status": "קודם הגדירו מפתח API"}
        res = analyze(cfg)
        # analyze() can take many seconds - re-read+merge onto the LATEST config at
        # write time (patch_config), never blind-replace with this now-stale `cfg`,
        # or a Settings change made mid-analysis gets silently reverted.
        registry.patch_config(pid, {
            "last_game": res.get("game") or "",
            "last_at": int(time.time()),
            "last_text": res.get("text") or "",
            "last_ok": bool(res.get("ok")),
            "last_error": res.get("error") or "",
        })
        if res.get("ok"):
            request_show(res.get("game") or "", res.get("text") or "")
        return {"ok": bool(res.get("ok")), "state": get_state(pid),
                "status": ("הניתוח הוצג בחלונית" if res.get("ok")
                           else (res.get("error") or "הניתוח נכשל"))}

    return {"ok": False, "error": "unknown-action"}
