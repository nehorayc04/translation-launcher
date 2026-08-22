"""
qt_shell.game_copilot_runtime - the LIVE part of the Game Co-Pilot plugin:
a small always-on-top glass overlay panel + a global (system-wide) hotkey
- keyboard OR game-controller - that shows/hides it, even while a game has
keyboard focus and the launcher window is hidden in the tray.

Everything ELSE about the plugin (config, the capture+AI pipeline, the
declarative settings panel) lives in `plugins/game_copilot.py`, which this
module talks to only through its tiny thread-safe IPC
(`report_runtime_status` / `poll_pending` / capture IPC) - never by
importing Qt into it.

Design, in one paragraph: `ensure_started()` is called once at boot
(main_qt.py) and is a near-no-op until the plugin is actually installed +
enabled. A QTimer on the GUI thread re-reads the plugin's install-state and
config every ~600ms; when enabled and the hotkey is a KEYBOARD combo it
(re)registers it via Win32 `RegisterHotKey(NULL, ...)`, which posts
`WM_HOTKEY` to the CALLING THREAD's message queue - Qt's own Win32 event
dispatcher pumps that queue and hands every message to installed
`QAbstractNativeEventFilter`s (the exact same `windows_generic_MSG`
native-event technique `qt_shell/main_window.py` already uses for its
custom frame). When the hotkey is a GAMEPAD combo (no Win32 equivalent to
RegisterHotKey) a second, faster timer polls XInput/legacy-joystick and
edge-triggers the same toggle. A button click in the Settings panel runs on
a QThreadPool WORKER thread (see bridge.py), so it can't touch a QWidget
directly - it goes through the same poll-and-react IPC instead. Screen
capture + the AI call always run on a plain background thread; the result
reaches the GUI thread via a queued Signal, which Qt handles automatically
when the emitter and receiver live on different threads.

Setting a NEW hotkey ("start_capture") is a special case: the Settings
button's `run_action` call BLOCKS its own worker thread (a plain sleep-poll,
never touching Qt) while THIS module pops a small native "press the new
combo" popup on the GUI thread and samples the global keyboard state
(`GetAsyncKeyState` - system-wide, independent of window focus) plus
XInput/legacy gamepad state until the user presses 1-2 keys/buttons
together and releases them, or cancels. No new frontend/React code is
needed anywhere for this - the whole capture UX is native.

The panel's VISUAL layer is an HTML/CSS page (`copilot_overlay.html`) shown
in a QWebEngineView, not hand-painted QPainter chrome: CSS gives real
border-radius, box-shadow and layered translucency for free, and the design
stays editable as a stylesheet. Python keeps only the WINDOW behaviour -
docking FLUSH to a screen EDGE (left/right/top/bottom), the Samsung-side-
panel-style LONG-PRESS-AND-DRAG reposition (the page reports intent and
screen coordinates over QWebChannel; `_OverlayPanel._on_drag_*` owns the
snap), and the show/hide motion, which uses the SAME springy overshoot-then-
settle easing curve as the launcher's own CSS (`cubic-bezier(.34,1.35,.5,1)`,
see `_spring_curve`) so this native window feels like part of the same
product.
"""
from __future__ import annotations

import ctypes
import html as _html
import logging
import re
import sys
import threading
import time
from pathlib import Path

log = logging.getLogger(__name__)

_PLUGIN_ID = "game-copilot"
_IS_WIN = sys.platform == "win32"

if _IS_WIN:                                        # pragma: no cover - Windows only
    from PySide6.QtCore import (QAbstractNativeEventFilter, QEasingCurve, QObject,
                                QPoint, QPointF,
                                QPropertyAnimation, QRectF, Qt, QTimer, QUrl,
                                Signal, Slot)
    from PySide6.QtGui import (QBrush, QColor, QCursor, QLinearGradient,
                               QPainter, QPainterPath, QPen)
    from PySide6.QtWidgets import (QApplication, QDialog, QFrame, QLabel,
                                   QLayout, QPushButton, QVBoxLayout, QWidget)
    # The overlay's whole visual layer is an HTML/CSS page rendered by
    # QtWebEngine (see `copilot_overlay.html`) rather than hand-painted
    # QPainter chrome. Eight rounds of hand-painting a "glassmorphism"
    # panel were rejected; CSS gives real border-radius + box-shadow +
    # layered translucency for free, and the design is then editable as
    # a stylesheet instead of as paint code.
    from PySide6.QtWebChannel import QWebChannel
    from PySide6.QtWebEngineCore import QWebEnginePage
    from PySide6.QtWebEngineWidgets import QWebEngineView

    class _MSG(ctypes.Structure):
        _fields_ = [("hwnd", ctypes.c_void_p), ("message", ctypes.c_uint),
                    ("wParam", ctypes.c_size_t), ("lParam", ctypes.c_ssize_t),
                    ("time", ctypes.c_uint), ("pt_x", ctypes.c_long), ("pt_y", ctypes.c_long)]

    _WM_HOTKEY = 0x0312
    _MOD_NOREPEAT = 0x4000
    _HOTKEY_ID = 0xC0C1          # arbitrary, process-unique, non-zero
    _EDGE_MARGIN = 10
    _SLIDE_OFFSET_PX = 30        # how far the show/hide slide travels
    # Every section marker the prompt can emit. A marker missing from here
    # renders as ordinary body text, so this MUST be kept in sync with
    # `game_copilot._SYSTEM_PROMPT`'s output format.
    _HEADER_MARKS = ("🎮", "📖", "📍", "🎯", "📋", "💡", "🔎")

    # The page fills the window edge-to-edge: DWM rounds the window and
    # draws its own shadow, so there is no CSS padding to leave room for.
    # COLLAPSED shrinks the whole window to the drag pill alone - no
    # frame, no veil, no ✕/↻ - which is only possible because the window
    # itself resizes, not just the page.
    _PANEL_W, _PANEL_H = 470, 156
    _PILL_W, _PILL_H = 40, 64
    # Must MATCH the CSS radii in copilot_overlay.html, or the window's clip
    # and the page's own rounding disagree and you see a sliver of one at the
    # corners of the other.
    _CARD_RADIUS = 22
    _PILL_RADIUS = 18

    # Win32 hotkey modifier bits - duplicated verbatim from game_copilot.py
    # (both are tiny stable Win32 constants; kept local so the hot ~45ms
    # capture-poll path never pays a cross-module import).
    _MOD_ALT, _MOD_CONTROL, _MOD_SHIFT, _MOD_WIN = 0x1, 0x2, 0x4, 0x8

    def _register_hotkey(mods: int, vk: int) -> bool:
        try:
            u = ctypes.windll.user32
            u.UnregisterHotKey(None, _HOTKEY_ID)      # clear any stale registration first
            ok = bool(u.RegisterHotKey(None, _HOTKEY_ID, mods | _MOD_NOREPEAT, vk))
            if not ok:
                ok = bool(u.RegisterHotKey(None, _HOTKEY_ID, mods, vk))
            return ok
        except Exception:                            # pragma: no cover
            log.warning("game_copilot: RegisterHotKey failed", exc_info=True)
            return False

    def _unregister_hotkey() -> None:
        try:
            ctypes.windll.user32.UnregisterHotKey(None, _HOTKEY_ID)
        except Exception:                            # pragma: no cover
            pass

    def _js_str(s: str) -> str:
        """A JS string literal. `json.dumps` escapes quotes, backslashes,
        newlines AND non-ASCII, so Hebrew crosses the runJavaScript boundary
        without depending on the transport's encoding."""
        import json as _json
        return _json.dumps(s or "", ensure_ascii=True)

    def _answer_html(text: str) -> str:
        """The AI answer as page HTML - CLASSES ONLY, never inline colour.
        The panel is deliberately colourless (blur + text), so a section
        head is marked by WEIGHT (`.head`), not by a cyan/amber accent."""
        out: list[str] = []
        for raw_line in (text or "").splitlines():
            raw = raw_line.strip()
            if not raw:
                out.append("<div style='height:5px'></div>")
                continue
            esc = _html.escape(raw)
            if any(raw.startswith(m) for m in _HEADER_MARKS):
                out.append(f"<div class='step head'>{esc}</div>")
            elif re.match(r"^\d+[.)]\s+", raw):
                out.append(f"<div class='step' style='margin-right:12px'>{esc}</div>")
            else:
                out.append(f"<div class='step'>{esc}</div>")
        return "".join(out)

    def _error_html(msg: str) -> str:
        """Same two-part split as `_format_error`: our Hebrew summary as RTL
        prose, the provider's own raw text as its own LTR block."""
        text = (msg or "").strip()
        if not text:
            return "<div class='step err'>⚠️ שגיאה לא ידועה</div>"
        summary, sep, detail = text.partition(" — ")
        head = f"<div class='step err'>⚠️ {_html.escape(summary.strip())}</div>"
        if not sep or not detail.strip():
            return head
        return head + (f"<div class='detail'>"
                       f"{_html.escape(detail.strip()).replace(chr(10), '<br>')}</div>")

    def _brand_icon_path() -> "Path | None":
        """Same resolution as qt_shell/tray.py's `_icon_path` (dev-tree vs
        frozen `_MEIPASS`) - duplicated locally on purpose, same reasoning as
        the Win32 constants above: a tiny, stable helper that shouldn't pay a
        cross-module import on this path."""
        base = getattr(sys, "_MEIPASS", None)
        if base:
            p = Path(base) / "build_assets" / "app.ico"
            if p.exists():
                return p
        p = Path(__file__).resolve().parent.parent.parent / "build_assets" / "app.ico"
        return p if p.exists() else None

    def _overlay_html_path() -> "Path | None":
        """The overlay page. Frozen, it rides the spec's
        `('translation_manager','translation_manager')` datas entry (and
        `_keep()` does not filter .html), so it sits next to this module's
        source path inside `_MEIPASS` - but check `_MEIPASS` explicitly
        first, exactly like `_brand_icon_path`, rather than trusting
        `__file__` to be a real on-disk path in a frozen build."""
        base = getattr(sys, "_MEIPASS", None)
        if base:
            p = Path(base) / "translation_manager" / "qt_shell" / "copilot_overlay.html"
            if p.exists():
                return p
        p = Path(__file__).resolve().with_name("copilot_overlay.html")
        return p if p.exists() else None

    def _spring_curve() -> "QEasingCurve":
        """The SAME springy overshoot-then-settle motion used throughout the
        launcher's own CSS (`cubic-bezier(.34, 1.35, .5, 1)` - see
        `.nav-slide`/`.view-transition` in frontend/src/index.css), so this
        native panel's open/close/resize motion reads as part of the same
        product instead of a generic Qt default ease."""
        curve = QEasingCurve()
        curve.setType(QEasingCurve.BezierSpline)
        curve.addCubicBezierSegment(QPointF(0.34, 1.35), QPointF(0.5, 1.0), QPointF(1.0, 1.0))
        return curve

    # ─────────────────────────────────────────────────────────────
    # 🔴 WINDOWS HAS TWO BLUR RECIPES AND EACH HAS TWO HALVES. Mixing halves
    # is what made this panel render as a BLACK RECTANGLE while every call
    # below reported success:
    #
    #   A. Mica/Acrylic BACKDROP     -> window must NOT be layered
    #      `DwmSetWindowAttribute` + `DWMWA_SYSTEMBACKDROP_TYPE`
    #   B. Acrylic BLUR-BEHIND       -> window MUST be layered (per-pixel alpha)
    #      `SetWindowCompositionAttribute` + ACCENT_ENABLE_ACRYLICBLURBEHIND
    #
    # This overlay hosts a QWebEngineView, which paints SOLID BLACK wherever
    # the page is transparent unless the window itself has real alpha - so
    # recipe (B) is the only viable one here, and `WA_TranslucentBackground`
    # is mandatory (see _OverlayPanel.__init__). Recipe (A) is therefore
    # NOT used; the constants stay only because DWMWA_WINDOW_CORNER_
    # PREFERENCE lives in the same API and DOES apply to a layered window.
    # ─────────────────────────────────────────────────────────────
    _DWMWA_SYSTEMBACKDROP_TYPE = 38   # (unused - recipe A, see above)
    _DWMSBT_TRANSIENTWINDOW = 3       # (unused - recipe A, see above)
    _DWMWA_WINDOW_CORNER_PREFERENCE = 33
    _DWMWCP_ROUND = 2                 # rounds the WINDOW'S OWN rectangle at the compositor
    # 🔴 Windows 11 draws a 1px BORDER around every window - including a
    # frameless, layered one. Measured on the real panel: the interior sat at
    # luminance 181, the desktop outside at 110, and exactly ONE pixel at the
    # window boundary read 246. That bright hairline is the "thin frame" that
    # survived removing every CSS rim, and DWMWA_COLOR_NONE is the only way
    # to turn it off.
    _DWMWA_BORDER_COLOR = 34
    _DWMWA_COLOR_NONE = 0xFFFFFFFE
                                       # level - which also rounds the acrylic surface, since
                                       # that fills the window rect. Same call this project's
                                       # own main_window.py already uses successfully.

    class _ACCENTPOLICY(ctypes.Structure):
        _fields_ = [("nAccentState", ctypes.c_int), ("nFlags", ctypes.c_int),
                    ("nColor", ctypes.c_uint), ("nAnimationId", ctypes.c_int)]

    class _WINCOMPATTRDATA(ctypes.Structure):
        _fields_ = [("nAttribute", ctypes.c_int), ("pData", ctypes.c_void_p),
                    ("ulDataSize", ctypes.c_size_t)]

    _WCA_ACCENT_POLICY = 19
    _ACCENT_DISABLED = 0                   # no blur surface at all
    _ACCENT_ENABLE_BLURBEHIND = 3          # cheap Aero-style blur
    _ACCENT_ENABLE_ACRYLICBLURBEHIND = 4   # the real frosted look
    # AABBGGRR. A NEUTRAL tint (no hue) - the panel must read as blurred
    # glass, never as a coloured card.
    # 🔑 This alpha is the ONLY frostiness lever we have: Windows does not
    # expose the acrylic's blur RADIUS, so "make it blurrier" is expressed
    # as a heavier tint over the blurred backdrop. 0x2A -> 0x3E reads
    # noticeably frostier while staying far from an opaque card. The page's
    # own veil is correspondingly light (see copilot_overlay.html) so the
    # two do not stack into darkness.
    _ACCENT_TINT = 0x3E1A1A1A

    def _set_accent(hwnd: int, state: int) -> bool:
        """The blur that works on a LAYERED (per-pixel-alpha) window.

        🔴 The pairing is what matters, and getting it wrong is why this
        looked BLACK for a whole round:
          * `DWMWA_SYSTEMBACKDROP_TYPE` (Mica/Acrylic) needs a NON-layered
            window - but a Qt window that is not `WA_TranslucentBackground`
            has an OPAQUE client area, and a QWebEngineView paints solid
            black wherever the page is transparent. Nothing to see through.
          * `SetWindowCompositionAttribute` + ACRYLICBLURBEHIND is designed
            for exactly the opposite case: a window that already has real
            per-pixel alpha. That is the combination this overlay needs.
        An earlier round called the acrylic API on the NON-transparent
        window - the wrong half of each recipe - and concluded the API
        "does nothing"."""
        try:
            policy = _ACCENTPOLICY(state, 2, _ACCENT_TINT, 0)
            data = _WINCOMPATTRDATA(_WCA_ACCENT_POLICY,
                                    ctypes.cast(ctypes.byref(policy), ctypes.c_void_p),
                                    ctypes.sizeof(policy))
            fn = ctypes.windll.user32.SetWindowCompositionAttribute
            fn.argtypes = [ctypes.c_void_p, ctypes.POINTER(_WINCOMPATTRDATA)]
            fn.restype = ctypes.c_int
            return bool(fn(ctypes.c_void_p(hwnd), ctypes.byref(data)))
        except Exception:                          # pragma: no cover
            log.debug("game_copilot: SetWindowCompositionAttribute unavailable", exc_info=True)
            return False

    _VK_LBUTTON, _VK_RBUTTON, _SM_SWAPBUTTON = 0x01, 0x02, 23

    def _primary_mouse_down() -> bool:
        """Is the PRIMARY mouse button physically held, right now?

        Deliberately NOT `QApplication.mouseButtons()`: that only reflects
        events Qt itself received, and this overlay is
        `WA_ShowWithoutActivating` while a game may hold the pointer - so Qt
        can report NoButton mid-drag and a guard built on it would cut a
        legitimate drag short. `GetAsyncKeyState` is system-wide and
        focus-independent (the same call this module already relies on for
        hotkey capture). Honours a swapped-button mouse."""
        try:
            vk = _VK_RBUTTON if ctypes.windll.user32.GetSystemMetrics(_SM_SWAPBUTTON) else _VK_LBUTTON
            return bool(_user32.GetAsyncKeyState(vk) & 0x8000)
        except Exception:                              # pragma: no cover
            try:
                return bool(QApplication.mouseButtons() & Qt.LeftButton)
            except Exception:
                return True                            # never strand a drag on a probe failure

    def _round_window(hwnd: int, w: int, h: int, radius: int) -> bool:
        """Clips the WINDOW itself to a rounded rect.

        Needed because Windows applies the acrylic to the whole window
        RECTANGLE - a CSS `border-radius` only rounds what WE paint, leaving
        the blurred surface square behind it (the "weird square edges").
        `DWMWA_WINDOW_CORNER_PREFERENCE` is prettier (antialiased) but is not
        honoured for every window style, so this is the deterministic
        fallback. Must be re-applied on every resize."""
        try:
            gdi = ctypes.windll.gdi32
            gdi.CreateRoundRectRgn.restype = ctypes.c_void_p
            rgn = gdi.CreateRoundRectRgn(0, 0, int(w) + 1, int(h) + 1,
                                         int(radius) * 2, int(radius) * 2)
            if not rgn:
                return False
            # SetWindowRgn takes OWNERSHIP of the region - never delete it here.
            fn = ctypes.windll.user32.SetWindowRgn
            fn.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int]
            return bool(fn(ctypes.c_void_p(hwnd), ctypes.c_void_p(rgn), True))
        except Exception:                              # pragma: no cover
            log.debug("game_copilot: SetWindowRgn unavailable", exc_info=True)
            return False

    def _apply_glass(hwnd: int) -> bool:
        """Probe whether this build accepts the acrylic accent, and set up the
        rounded corners. Deliberately leaves the window on ACCENT_DISABLED -
        the caller's `_apply_accent()` owns the real state, because forcing
        acrylic on here flashes a blurred panel before the surface setting is
        known. Returns whether the accent API works at all."""
        ok = _set_accent(hwnd, _ACCENT_ENABLE_ACRYLICBLURBEHIND)
        if not ok:                                 # older builds: plain blur still beats black
            ok = _set_accent(hwnd, _ACCENT_ENABLE_BLURBEHIND)
        _set_accent(hwnd, _ACCENT_DISABLED)        # neutral until the surface is applied
        try:
            # Rounded corners are independent of the backdrop mechanism and
            # work on a layered window too.
            corner = ctypes.c_int(_DWMWCP_ROUND)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                ctypes.c_void_p(hwnd), ctypes.c_int(_DWMWA_WINDOW_CORNER_PREFERENCE),
                ctypes.byref(corner), ctypes.sizeof(corner))
        except Exception:                          # pragma: no cover
            log.debug("game_copilot: DWM corner rounding unavailable", exc_info=True)
        try:
            # Kill Windows' own 1px window border - see _DWMWA_BORDER_COLOR.
            none = ctypes.c_uint(_DWMWA_COLOR_NONE)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                ctypes.c_void_p(hwnd), ctypes.c_int(_DWMWA_BORDER_COLOR),
                ctypes.byref(none), ctypes.sizeof(none))
        except Exception:                          # pragma: no cover
            log.debug("game_copilot: DWM border removal unavailable", exc_info=True)
        return ok

    # ─────────────────────────────────────────────────────────────
    # Global keyboard/gamepad SAMPLING used only during hotkey capture.
    # GetAsyncKeyState / XInputGetState both query GLOBAL system state (not
    # limited to whichever window has focus) - exactly what a "press the new
    # shortcut anywhere" capture needs, with none of the lifetime/threading
    # fuss of a low-level keyboard hook.
    # ─────────────────────────────────────────────────────────────
    _user32 = ctypes.windll.user32
    _user32.GetAsyncKeyState.restype = ctypes.c_short
    _user32.GetAsyncKeyState.argtypes = [ctypes.c_int]

    _MODIFIER_VKS = {0x10, 0x11, 0x12, 0x5B, 0x5C, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5}
    _VK_ESCAPE = 0x1B

    def _keys_down() -> set[int]:
        held: set[int] = set()
        for vk in range(0x08, 0xFF):
            if _user32.GetAsyncKeyState(vk) & 0x8000:
                held.add(vk)
        return held

    def _mods_from_held(held: set[int]) -> int:
        m = 0
        if held & {0x11, 0xA2, 0xA3}:
            m |= _MOD_CONTROL
        if held & {0x10, 0xA0, 0xA1}:
            m |= _MOD_SHIFT
        if held & {0x12, 0xA4, 0xA5}:
            m |= _MOD_ALT
        if held & {0x5B, 0x5C}:
            m |= _MOD_WIN
        return m

    _VK_NAMES = {
        0x20: "Space", 0x0D: "Enter", 0x09: "Tab", 0x08: "Backspace",
        0x2E: "Delete", 0x2D: "Insert", 0x24: "Home", 0x23: "End",
        0x21: "Page Up", 0x22: "Page Down",
        0x25: "◀", 0x26: "▲", 0x27: "▶", 0x28: "▼",
        0xBC: ",", 0xBE: ".", 0xBA: ";", 0xDE: "'", 0xC0: "`",
        0xBD: "-", 0xBB: "=", 0xDB: "[", 0xDD: "]", 0xDC: "\\", 0xBF: "/",
    }

    def _vk_label(vk: int) -> str:
        if 0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A:
            return chr(vk)
        if 0x70 <= vk <= 0x87:
            return f"F{vk - 0x6F}"
        return _VK_NAMES.get(vk, f"מקש {vk:#x}")

    def _kb_live_label(mods: int, vk: int | None) -> str:
        parts: list[str] = []
        if mods & _MOD_CONTROL:
            parts.append("Ctrl")
        if mods & _MOD_SHIFT:
            parts.append("Shift")
        if mods & _MOD_ALT:
            parts.append("Alt")
        if mods & _MOD_WIN:
            parts.append("Win")
        if vk:
            parts.append(_vk_label(vk))
        return " + ".join(parts)

    class _XINPUT_GAMEPAD(ctypes.Structure):
        _fields_ = [("wButtons", ctypes.c_ushort), ("bLeftTrigger", ctypes.c_ubyte),
                    ("bRightTrigger", ctypes.c_ubyte), ("sThumbLX", ctypes.c_short),
                    ("sThumbLY", ctypes.c_short), ("sThumbRX", ctypes.c_short),
                    ("sThumbRY", ctypes.c_short)]

    class _XINPUT_STATE(ctypes.Structure):
        _fields_ = [("dwPacketNumber", ctypes.c_ulong), ("Gamepad", _XINPUT_GAMEPAD)]

    def _load_xinput():
        for name in ("xinput1_4.dll", "xinput1_3.dll", "xinput9_1_0.dll"):
            try:
                dll = ctypes.windll.LoadLibrary(name)
                dll.XInputGetState.restype = ctypes.c_uint
                dll.XInputGetState.argtypes = [ctypes.c_uint, ctypes.POINTER(_XINPUT_STATE)]
                return dll
            except Exception:                      # pragma: no cover
                continue
        return None

    _XINPUT = _load_xinput()

    def _xinput_buttons() -> int:
        """OR of the button bitmask across every CONNECTED controller (so it
        doesn't matter which USB/BT port it's on) - 0 if none connected."""
        if _XINPUT is None:
            return 0
        st = _XINPUT_STATE()
        mask = 0
        for i in range(4):
            try:
                if _XINPUT.XInputGetState(i, ctypes.byref(st)) == 0:      # ERROR_SUCCESS
                    mask |= st.Gamepad.wButtons
            except Exception:                      # pragma: no cover
                pass
        return mask

    # Xbox / PlayStation dual naming - XInput abstracts the physical pad away,
    # so we can't detect brand natively; showing both reads correctly either way.
    _GP_BUTTON_NAMES = {
        0x0001: "D-Pad ↑", 0x0002: "D-Pad ↓", 0x0004: "D-Pad ◀", 0x0008: "D-Pad ▶",
        0x0010: "Start/Options", 0x0020: "Back/Share",
        0x0040: "L3", 0x0080: "R3", 0x0100: "LB/L1", 0x0200: "RB/R1",
        0x1000: "A/✕", 0x2000: "B/○", 0x4000: "X/□", 0x8000: "Y/△",
    }

    def _gp_label(mask: int) -> str:
        names = [lbl for bit, lbl in _GP_BUTTON_NAMES.items() if mask & bit]
        return ("שלט: " + " + ".join(names)) if names else ""

    # ─────────────────────────────────────────────────────────────
    # Legacy joystick (winmm) - the fallback for a controller XInput can't
    # see at all. XInput is Xbox-pad-only (or anything explicitly emulating
    # it); a PlayStation DualSense/DualShock connected in its NATIVE mode
    # never shows up there, full stop. Windows still exposes it through the
    # classic joystick API (the same one behind the old "Game Controllers"
    # / joy.cpl panel) - a plain flat winmm.dll API, no COM, always present.
    # Button NUMBERING is not standardized across brands/drivers here, so it
    # is reported generically ("Button N") instead of guessing a layout.
    # ─────────────────────────────────────────────────────────────
    class _JOYINFOEX(ctypes.Structure):
        _fields_ = [("dwSize", ctypes.c_uint), ("dwFlags", ctypes.c_uint),
                    ("dwXpos", ctypes.c_uint), ("dwYpos", ctypes.c_uint),
                    ("dwZpos", ctypes.c_uint), ("dwRpos", ctypes.c_uint),
                    ("dwUpos", ctypes.c_uint), ("dwVpos", ctypes.c_uint),
                    ("dwButtons", ctypes.c_uint), ("dwButtonNumber", ctypes.c_uint),
                    ("dwPOV", ctypes.c_uint), ("dwReserved1", ctypes.c_uint),
                    ("dwReserved2", ctypes.c_uint)]

    _JOY_RETURNBUTTONS = 0x80
    _JOYERR_NOERROR = 0

    def _load_winmm():
        try:
            dll = ctypes.windll.winmm
            dll.joyGetPosEx.restype = ctypes.c_uint
            dll.joyGetPosEx.argtypes = [ctypes.c_uint, ctypes.POINTER(_JOYINFOEX)]
            return dll
        except Exception:                      # pragma: no cover
            return None

    _WINMM = _load_winmm()

    def _joy_legacy_buttons() -> int:
        if _WINMM is None:
            return 0
        mask = 0
        info = _JOYINFOEX()
        info.dwSize = ctypes.sizeof(_JOYINFOEX)
        info.dwFlags = _JOY_RETURNBUTTONS
        for i in range(16):                    # winmm supports up to 16 legacy joystick slots
            try:
                if _WINMM.joyGetPosEx(i, ctypes.byref(info)) == _JOYERR_NOERROR:
                    mask |= int(info.dwButtons)
            except Exception:                  # pragma: no cover
                pass
        return mask

    def _joy_legacy_label(mask: int) -> str:
        nums = [str(i + 1) for i in range(32) if mask & (1 << i)]
        return ("שלט (זיהוי כללי): כפתור " + " + ".join(nums)) if nums else ""

    class _HotkeyEventFilter(QAbstractNativeEventFilter):
        """Catches the process-wide WM_HOTKEY message. Runs on the GUI thread
        (it's invoked from inside Qt's own Win32 event dispatcher), so the
        callback may touch widgets directly."""

        def __init__(self, on_hotkey):
            super().__init__()
            self._on_hotkey = on_hotkey

        def nativeEventFilter(self, eventType, message):     # noqa: N802 (Qt override)
            try:
                et = bytes(eventType) if not isinstance(eventType, bytes) else eventType
                if et == b"windows_generic_MSG":
                    msg = ctypes.cast(int(message), ctypes.POINTER(_MSG)).contents
                    if msg.message == _WM_HOTKEY and msg.wParam == _HOTKEY_ID:
                        self._on_hotkey()
            except Exception:                        # pragma: no cover
                log.debug("game_copilot: hotkey filter error", exc_info=True)
            return False, 0

    # ─────────────────────────────────────────────────────────────
    # TRUE glass, painted by hand instead of via a QSS `background:` string.
    # A QSS rounded-rect fill on a QFrame is only reliably clipped to the
    # antialiased radius by Qt's STYLE ENGINE, and can leave a square corner
    # of the fill (or a mismatched double edge against DWM's own Acrylic
    # sheet-highlight) peeking past the visible border - which is very
    # likely the "white frame / weird edges" the panel was reported to show,
    # worst on the small handle where any such sliver reads as a distinct
    # box rather than a rounded chip. Painting the fill ourselves with
    # `QPainter` + `QPainterPath.addRoundedRect` (a single, well-tested
    # Qt primitive) and filling ONLY that path removes the ambiguity
    # entirely: whatever isn't inside the rounded path is left exactly as
    # the translucent window's backing store already had it - i.e.
    # genuinely transparent, showing the blurred DWM Acrylic (or the raw
    # desktop/game if Acrylic isn't available) straight through, with a
    # perfectly smooth antialiased edge and no possible stray corner.
    #
    # The fill itself is kept LOW and mostly NEUTRAL (a cool near-navy base
    # with a bright top-left sheen, like light catching real glass) rather
    # than a loud multi-hue gradient - a wash of decorative colour across
    # the one surface that's supposed to be see-through is exactly what
    # reads as "painted", not "glass". Colour instead lives on solid
    # elements (title text, section headers, button hover glow, the handle
    # chip) per Apple's own material guidance: put colour on a solid layer,
    # never on the translucent foreground.
    # ─────────────────────────────────────────────────────────────
    def _rounded_path(rect: "QRectF", radius: float) -> "QPainterPath":
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        return path

    # Anisotropic hairlines for BRUSHED metal. A gradient alone can only
    # ever read as smooth plastic - what identifies real machined metal to
    # the eye is fine directional grain catching the light unevenly. The
    # offsets are precomputed ONCE (not random per paint) so the grain is
    # stable across repaints instead of shimmering, and cheap to draw.
    _GRAIN = []
    _s = 0x2F6E2B1
    for _i in range(150):
        _s = (_s * 1103515245 + 12345) & 0x7FFFFFFF
        _pos = (_s >> 8) % 10000 / 10000.0
        _s = (_s * 1103515245 + 12345) & 0x7FFFFFFF
        _a = 5 + (_s >> 8) % 22
        _GRAIN.append((_pos, _a, (_s >> 4) % 2 == 0))
    del _s, _i, _pos, _a

    def _brush(p: "QPainter", rect: "QRectF", clip: "QPainterPath",
               vertical: bool = True, strength: float = 1.0) -> None:
        """Draw the brushed grain inside `clip`. `vertical` = the direction
        the metal was milled in (a vertical rail is brushed along its long
        axis, exactly like a real machined faceplate)."""
        p.save()
        p.setClipPath(clip)
        for pos, a, light in _GRAIN:
            alpha = max(1, int(a * strength))
            p.setPen(QPen(QColor(255, 255, 255, alpha) if light
                          else QColor(0, 0, 0, alpha), 1.0))
            if vertical:
                x = rect.x() + pos * rect.width()
                p.drawLine(QPointF(x, rect.y()), QPointF(x, rect.y() + rect.height()))
            else:
                y = rect.y() + pos * rect.height()
                p.drawLine(QPointF(rect.x(), y), QPointF(rect.x() + rect.width(), y))
        p.restore()

    _BEZEL_W = 14.0          # thickness of the machined metal ring

    class _GlassCard(QFrame):
        """The reference look: a brushed-gunmetal shell with generously
        ROUNDED corners and a thin polished rim, holding a dark frosted
        purple/blue glass panel that the desktop shows through.

        Painted in this order:
          1. the metal shell - a vertical gradient (overhead light: bright
             top edge, dark body, one specular sweep, rim catch at the
             bottom) with real BRUSHED GRAIN drawn over it. The grain is
             what separates milled metal from a plastic gradient;
          2. the glass panel, inset over wherever the content column
             actually is, at low alpha ON PURPOSE so the blurred desktop
             behind the window stays the dominant content and the tint only
             colours it. When the card is collapsed there is no content
             column, so the shell is simply a slim milled strip;
          3. the polished rim - a bright 1px line on the outer contour and
             the classic dark-then-bright pair around the glass, which is
             what reads as a real machined step down into the pane.
        """

        def __init__(self, parent=None, radius: float = 22.0) -> None:
            super().__init__(parent)
            self._radius = radius
            self._glass_widget = None
            # Without this a child QWidget/QFrame is grabbed/rendered as an
            # OPAQUE Format_RGB32 surface (no alpha channel at all) - so the
            # region OUTSIDE the hand-painted path (the cut corners) shows
            # Qt's default palette background instead of being truly
            # see-through, no matter what paintEvent draws. Confirmed via a
            # pixel probe: without this the corners read (239,239,239,255)
            # (opaque light grey); with it they read near-zero alpha. This
            # is the "weird square edges around the glass" bug.
            self.setAttribute(Qt.WA_TranslucentBackground, True)
            self.setAttribute(Qt.WA_NoSystemBackground, True)
            self.setAutoFillBackground(False)

        def set_glass_widget(self, w) -> None:
            """Tell the card WHERE the frosted pane goes - it is drawn over
            the content column's own geometry, so the metal shell and the
            glass stay in register at any size and the pane disappears by
            itself when the column is hidden (collapsed)."""
            self._glass_widget = w

        def paintEvent(self, e) -> None:               # noqa: N802 (Qt override)
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing, True)
            r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
            rad = self._radius
            shell = _rounded_path(r, rad)

            # 1. work out WHERE the glass goes first, because the metal must
            # be CUT AWAY there. Painting an opaque shell and then laying a
            # low-alpha tint on top of it does not produce glass - it
            # produces tinted metal (measured: the pane's centre came back
            # at alpha 255, fully opaque). The pane has to be a genuine HOLE
            # in the faceplate for the blurred desktop to come through.
            # With no column registered (the capture dialog) the pane simply
            # fills the shell's inner area, so that window still gets a
            # readable glass field instead of a slab of solid metal.
            pane = None
            gw = self._glass_widget
            if gw is None or gw.isVisible():
                if gw is None:
                    gr = r.adjusted(_BEZEL_W, _BEZEL_W, -_BEZEL_W, -_BEZEL_W)
                else:
                    gr = QRectF(gw.geometry()).adjusted(-4.0, -4.0, 4.0, 4.0)
                    gr = gr.intersected(r.adjusted(2.0, 2.0, -2.0, -2.0))
                if gr.width() > 8 and gr.height() > 8:
                    grad = max(8.0, rad - 6.0)
                    pane = _rounded_path(gr, grad)

            # 2. the metal faceplate, with the pane cut out of it.
            # VERTICAL, not diagonal: a diagonal gradient's value at a point
            # is its projection onto the topLeft->bottomRight axis, so on a
            # panel much wider than it is tall the top edge and the bottom
            # edge project into nearly the SAME band and the metal renders
            # flat (measured: 4/255 lightness apart at 428x194). Lighting it
            # from straight overhead is aspect-ratio independent and is what
            # a real machined faceplate looks like anyway.
            metal = shell if pane is None else shell.subtracted(pane)
            gm = QLinearGradient(r.topLeft(), r.bottomLeft())
            # Gunmetal, and the body stays UNIFORMLY dark. Bright edges are
            # drawn later as 1px pens, NOT as gradient stops: the gradient
            # runs over the whole card height (~196px) while the metal is
            # only visible in a ~15px band at the top and bottom, so even a
            # "thin" 3% stop is ~6px = nearly half the visible frame there,
            # and reads as a wide chrome band. A hairline pen is the only
            # way to get an edge highlight that stays an EDGE.
            gm.setColorAt(0.00, QColor(74, 80, 96, 255))
            gm.setColorAt(0.30, QColor(44, 48, 60, 255))       # dark body
            gm.setColorAt(0.55, QColor(53, 58, 71, 255))       # a restrained sweep
            gm.setColorAt(0.80, QColor(37, 40, 51, 255))
            gm.setColorAt(1.00, QColor(62, 67, 82, 255))       # faint bounce off the desk
            p.fillPath(metal, QBrush(gm))
            _brush(p, r, metal, vertical=True, strength=1.0)

            # 3. the frosted tint inside the hole - deep purple at the top
            # easing into dark blue. It only COLOURS the blurred desktop
            # showing through, so the alphas stay deliberately low.
            if pane is not None:
                gg = QLinearGradient(gr.topLeft(), gr.bottomLeft())
                # A LIGHT violet wash reads as a purple slab sitting on top
                # of the wallpaper; a DARK one reads as smoked glass with the
                # bokeh coming through it, which is the reference. Same hue,
                # much lower value.
                gg.setColorAt(0.00, QColor(74, 54, 120, 74))
                gg.setColorAt(0.45, QColor(44, 36, 92, 84))
                gg.setColorAt(1.00, QColor(12, 12, 38, 104))
                p.fillPath(pane, QBrush(gg))
                # the machined step down into the pane: a dark shadowed
                # edge, then a bright lip just outside it
                p.setPen(QPen(QColor(6, 5, 20, 190), 1.0))
                p.drawPath(pane)
                p.setPen(QPen(QColor(214, 226, 250, 105), 1.0))
                p.drawPath(_rounded_path(gr.adjusted(-1.4, -1.4, 1.4, 1.4), grad + 1.2))

            # 3. the polished outer rim
            p.setPen(QPen(QColor(238, 244, 255, 190), 1.0))
            p.drawPath(shell)
            p.setPen(QPen(QColor(8, 9, 18, 120), 1.0))
            p.drawPath(_rounded_path(r.adjusted(1.4, 1.4, -1.4, -1.4), rad - 1.2))
            # deliberately NOT calling super().paintEvent(e) - this fully
            # replaces the frame's own background/border painting; child
            # widgets placed in this frame's layout still paint themselves
            # independently via Qt's normal compositing, unaffected.

    class _OverlayBridge(QObject):
        """The object the page talks to over QWebChannel (registered as
        `overlay`). Every slot just forwards to the panel - all the dock /
        snap / persist logic stays in Python, exactly where it already
        works; the page only reports intent and screen coordinates."""

        def __init__(self, panel: "_OverlayPanel") -> None:
            super().__init__(panel)
            self._panel = panel

        @Slot()
        def close(self) -> None:
            self._panel.request_close()

        @Slot()
        def refresh(self) -> None:
            self._panel.request_refresh()

        @Slot()
        def toggleCollapse(self) -> None:                 # noqa: N802 - JS-side name
            self._panel._toggle_collapsed()

        @Slot()
        def dragStart(self) -> None:                      # noqa: N802
            self._panel._on_drag_start()

        @Slot(int, int)
        def dragMove(self, x: int, y: int) -> None:       # noqa: N802
            self._panel._on_drag_move(QPoint(int(x), int(y)))

        @Slot()
        def dragEnd(self) -> None:                        # noqa: N802
            self._panel._on_drag_finish()

        @Slot(int)
        def contentHeight(self, h: int) -> None:          # noqa: N802
            """The page reports the height at which its text would STOP
            scrolling. Only the page can know it (it owns the wrapping),
            and it is what lets the window grow to fit a long answer
            instead of making the user scroll a tiny box."""
            self._panel._on_content_height(int(h))

    class _OverlayPanel(QWidget):
        """The floating, always-on-top glass card - a frameless window whose
        entire content is `copilot_overlay.html` in a QWebEngineView. Docks
        FLUSH to a screen EDGE (left/right/top/bottom), centered by default
        on a fractional position along that edge which the user can change
        by long-press-dragging the page's sapphire pill. Anchored by its
        CENTRE at that fraction, so a size change grows/shrinks it in place
        rather than letting it drift. Never steals focus from the game
        (WA_ShowWithoutActivating)."""

        _EDGES = ("left", "right", "top", "bottom")

        def __init__(self, on_close, on_refresh, parent=None) -> None:
            super().__init__(parent, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
            # WA_TranslucentBackground IS required now, and that is a
            # deliberate reversal of the earlier rounds' reasoning.
            #
            # The old note said to avoid it because it makes Qt create a
            # LAYERED window (WS_EX_LAYERED), which cannot compose with
            # DWM's `DWMWA_SYSTEMBACKDROP_TYPE`. True - but the conclusion
            # drawn from it was wrong: WITHOUT it, the window's client area
            # is OPAQUE, and a QWebEngineView paints solid BLACK wherever
            # the page is transparent. That is exactly what the user saw -
            # a black rectangle instead of glass, with every DWM call
            # reporting success.
            #
            # So the whole recipe flips to the layered path: real per-pixel
            # alpha here, and the blur from `SetWindowCompositionAttribute`
            # + ACRYLICBLURBEHIND (see `_set_accent`), which is the API
            # designed for exactly this case. `windowOpacity` still must
            # never be touched - but that is already true by construction,
            # since every fade runs in CSS inside the page.
            self.setAttribute(Qt.WA_TranslucentBackground, True)
            self.setAttribute(Qt.WA_NoSystemBackground, True)
            self.setAttribute(Qt.WA_ShowWithoutActivating, True)
            self._edge = "right"
            self._edge_pos = 0.5
            self._collapsed = False
            self._glass_applied = False
            self._show_anim: "QPropertyAnimation | None" = None
            self._hide_anim: "QPropertyAnimation | None" = None
            self._drag_mouse0: "QPoint | None" = None
            self._drag_win0: "QPoint | None" = None
            self._drag_timer: "QTimer | None" = None
            self._snap_anim: "QPropertyAnimation | None" = None
            self._dragging = False
            self._region_size = None                     # last size we clipped the window to
            self._surface = "tint"
            # THE size the window is meant to be. Kept explicitly because
            # `self.width()`/`height()` LAG a layout change by an event-loop
            # turn, and every dock calculation depends on the size - see
            # `_apply_geometry`.
            self._size = (_PANEL_W, _PANEL_H)
            # Height the page says its text needs (0 = not measured yet), so a
            # long answer grows the window instead of scrolling in a 156px box.
            self._content_h = 0

            # A game going fullscreen CHANGES THE SCREEN GEOMETRY, and the
            # overlay is shown precisely then - so without this it keeps the
            # coordinates of the old resolution and can sit half off-screen
            # (or entirely off it, on a resolution drop). Re-dock on any
            # screen change, debounced so a burst of events costs one move.
            self._geo_timer = QTimer(self)
            self._geo_timer.setSingleShot(True)
            self._geo_timer.setInterval(350)
            self._geo_timer.timeout.connect(lambda: self.reposition(animated=False))
            app = QApplication.instance()
            if app is not None:
                try:
                    app.screenAdded.connect(lambda *_: self._geo_timer.start())
                    app.screenRemoved.connect(lambda *_: self._geo_timer.start())
                    app.primaryScreenChanged.connect(lambda *_: self._geo_timer.start())
                    for sc in QApplication.screens():
                        sc.geometryChanged.connect(lambda *_: self._geo_timer.start())
                        sc.availableGeometryChanged.connect(lambda *_: self._geo_timer.start())
                except Exception:                        # pragma: no cover
                    log.debug("game_copilot: screen-change hookup failed", exc_info=True)

            # QWidget.setWindowOpacity()/QPropertyAnimation on b"windowOpacity"
            # has the SAME WS_EX_LAYERED problem as WA_TranslucentBackground did
            # above - Qt enables layered-window mode the instant windowOpacity
            # is touched, regardless of any other attribute, and that silently
            # defeats the DWM Acrylic backdrop the moment a fade/dim fires (a
            # drag, a show, a hide - i.e. constantly). Fades therefore run in
            # CSS inside the page (`setShown`/`setDimmed`) - not via
            # windowOpacity, and not via a QGraphicsOpacityEffect either: an
            # effect renders its whole subtree into an offscreen pixmap, and
            # a QWebEngineView draws through a separate compositor, so the
            # panel can come out blank.
            root = QVBoxLayout(self)
            root.setContentsMargins(0, 0, 0, 0)
            # The window must track its content EXACTLY. `adjustSize()` alone
            # does not shrink an already-shown top-level window back down
            # (measured: after collapsing, every sizeHint in the chain read 82
            # while the window stayed at 430), and with the rail now INSIDE
            # the bezel a too-wide window is visible as a wide empty frame
            # rather than as transparent space - the old design got away with
            # it only because collapsing hid the whole card. SetFixedSize
            # makes Qt resize the window to the layout on every change, which
            # is exactly right for a content-sized overlay and also keeps the
            # body-height animation's growth in step with the window.
            root.setSizeConstraint(QLayout.SetFixedSize)
            self._content = QWidget(self)
            self._content.setAttribute(Qt.WA_TranslucentBackground, True)
            self._content.setAttribute(Qt.WA_NoSystemBackground, True)
            self._content.setAutoFillBackground(False)
            root.addWidget(self._content)

            outer = QVBoxLayout(self._content)
            outer.setContentsMargins(0, 0, 0, 0)
            outer.setSpacing(0)

            self._game = ""
            self._on_close = on_close
            self._on_refresh = on_refresh
            self._page_ready = False
            self._pending_js: list[str] = []

            # The panel IS a web page. Everything visual - the rounded
            # frosted card, the rail, the sapphire drag pill, the type -
            # is CSS in `copilot_overlay.html`; Python keeps only the
            # window behaviour (docking, dragging, animation, hotkey).
            self._view = QWebEngineView(self._content)
            self._view.setAttribute(Qt.WA_TranslucentBackground, True)
            self._view.setFixedSize(_PANEL_W, _PANEL_H)
            page = QWebEnginePage(self._view)
            # Qt::transparent, so the page's own transparent html/body let
            # the window (and therefore DWM's backdrop) through. Without
            # this the page paints an opaque white ground and every bit of
            # the CSS translucency is invisible.
            page.setBackgroundColor(Qt.transparent)
            self._view.setPage(page)
            self._view.setContextMenuPolicy(Qt.NoContextMenu)

            self._bridge = _OverlayBridge(self)
            self._channel = QWebChannel(page)
            self._channel.registerObject("overlay", self._bridge)
            page.setWebChannel(self._channel)
            page.loadFinished.connect(self._flush_js)

            html_path = _overlay_html_path()
            if html_path is not None:
                self._view.load(QUrl.fromLocalFile(str(html_path)))
            else:                                        # pragma: no cover
                log.error("game_copilot: copilot_overlay.html not found - overlay will be blank")
            outer.addWidget(self._view)

            self._reflow()

        # ── edge dock + collapse/expand ─────────────────────
        def _reflow(self, animate: bool = False) -> None:
            """Tells the page which way it is docked (so the rail sits on
            the side FACING the screen edge, like a Samsung edge-panel
            handle) and whether it is collapsed, then re-docks the window to
            match. Collapsing hides only the CONTENT column - the rail with
            its grabbable pill stays, which is both the way back in and the
            drag handle.

            `animate` is a REQUEST, not a command: a glide is allowed only
            when the size is unchanged. THIS is the one place that decides
            snap-vs-glide, so no caller can accidentally animate a resize."""
            was = (self.width(), self.height())
            self._js("window.setSurface(%s)" % _js_str(self._surface))
            self._js("window.setEdge(%s)" % _js_str(self._edge))
            self._js("window.setCollapsed(%s)" % ("true" if self._collapsed else "false"))
            if not self._collapsed:
                w, h = _PANEL_W, self._expanded_height()
            elif self._edge in ("top", "bottom"):
                # The rail runs ALONG the docked edge, so a top/bottom dock
                # collapses to a WIDE, SHORT tab - not the tall one a
                # left/right dock leaves behind.
                w, h = _PILL_H, _PILL_W
            else:
                w, h = _PILL_W, _PILL_H
            self._size = (w, h)
            self._view.setFixedSize(w, h)
            # 🔴🔴 ACTIVATE THE LAYOUT CHAIN NOW - this was THE bug behind
            # "it opens off-screen to the right" and "the tab runs away".
            # `setFixedSize` on the view only reaches the WINDOW on the next
            # layout pass, so `reposition()` ran a moment later still read the
            # PREVIOUS size: expanding a right-docked panel computed x for a
            # 40px tab (x = right-50), then the window grew to 470 from there
            # = 430px off the right edge; collapsing computed x for the 470px
            # panel, then shrank around the top-left = the tab 430px inland.
            # Measured, not guessed: reposition() saw 470 while collapsing and
            # 64 while expanding, every single time.
            for lay in (self._content.layout(), self.layout()):
                if lay is not None:
                    try:
                        lay.activate()
                    except Exception:                    # pragma: no cover
                        pass
            # A pure MOVE may glide; a SIZE change must move AND resize in ONE
            # call, so there is never a frame where the new size sits at the
            # old position.
            if animate and was == (w, h):
                self.reposition(animated=True)
            else:
                self._apply_geometry()
            # Windows blurs the whole window RECT, not just the pixels we
            # paint - so leaving acrylic on while collapsed would wrap the
            # lone pill in a blurred rectangle, which is precisely the
            # "big frame" the collapsed state exists to get rid of. With
            # the accent off, the layered window's transparent areas are
            # genuinely see-through and only the pill remains.
            self._apply_accent()
            self._apply_round_region()

        def _expanded_height(self) -> int:
            """How tall the open panel should be: enough for its text, so a
            long answer is READ rather than scrolled through a 156px slot -
            capped so it can never outgrow the screen it docks to."""
            h = max(_PANEL_H, int(self._content_h or 0))
            try:
                screen = self._screen_for_point(self.geometry().center())
                room = screen.availableGeometry().height() - 2 * _EDGE_MARGIN
                h = min(h, max(_PANEL_H, int(room * 0.86)))
            except Exception:                            # pragma: no cover
                h = min(h, 900)
            return h

        def _on_content_height(self, h: int) -> None:
            """The page measured the height at which its text stops
            scrolling. Grow (or shrink back) to it.

            Converges in ONE step and cannot loop: once the window fits the
            text, the page re-measures the SAME number and the guard below
            stops there. If the text is taller than the cap the number simply
            stays high, the window stays capped, and the body scrolls - which
            is the only honest answer at that point."""
            if self._collapsed or h <= 0:
                return
            h = max(_PANEL_H, min(int(h), 4000))
            if abs(h - int(self._content_h or 0)) < 3:
                return
            self._content_h = h
            if self._expanded_height() != self._size[1]:
                self._reflow()

        def _apply_accent(self, dragging: bool | None = None) -> None:
            """THE single place that decides the window's blur state.

            Blur is OFF when collapsed (Windows blurs the whole window RECT,
            so a lone pill would otherwise sit in a blurred rectangle) and OFF
            in 'tint' mode, where the whole point is that the game stays SHARP
            behind a slightly darkened, genuinely see-through panel. While
            DRAGGING, glass drops from acrylic to plain blur - acrylic
            re-samples the backdrop on every move and that is what makes a
            drag feel heavy.

            Every caller routes through here. Hardcoding a state at a call
            site is what made a drag in tint mode flicker clear->blurred."""
            if not self._glass_applied:
                return
            if dragging is None:
                dragging = self._dragging
            if self._collapsed or self._surface != "glass":
                state = _ACCENT_DISABLED
            elif dragging:
                state = _ACCENT_ENABLE_BLURBEHIND
            else:
                state = _ACCENT_ENABLE_ACRYLICBLURBEHIND
            _set_accent(int(self.winId()), state)

        def set_surface(self, surface: str) -> None:
            surface = surface if surface in ("glass", "tint") else "tint"
            if surface == self._surface:
                return
            self._surface = surface
            self._js("window.setSurface(%s)" % _js_str(surface))
            self._apply_accent()

        def _apply_round_region(self) -> None:
            """Re-clips the window after any size change - a stale region from
            the previous size would crop the new content (or leave the old
            square blur showing)."""
            if not self._glass_applied:
                return
            size = (self.width(), self.height())
            if size == self._region_size or size[0] < 2 or size[1] < 2:
                return
            radius = _PILL_RADIUS if self._collapsed else _CARD_RADIUS
            if _round_window(int(self.winId()), size[0], size[1], radius):
                self._region_size = size

        def resizeEvent(self, e) -> None:                # noqa: N802 (Qt override)
            super().resizeEvent(e)
            self._apply_round_region()

        def set_edge(self, edge: str, pos: float = 0.5) -> None:
            edge = edge if edge in self._EDGES else "right"
            pos = max(0.0, min(1.0, pos))
            if edge == self._edge and abs(pos - self._edge_pos) < 0.002:
                return
            self._edge = edge
            self._edge_pos = pos
            # Changing the edge MUST also move the window there - without it
            # the rail flipped sides while the panel stayed put. `_reflow`
            # does the move now, and it glides only if the size did not
            # change (a collapsed tab crossing between a vertical and a
            # horizontal edge TRANSPOSES, and that has to snap).
            self._reflow(animate=True)

        def expand(self) -> None:
            if self._collapsed:
                self._collapsed = False
                self._reflow()                           # size change -> atomic snap

        # ── what the page's rail buttons call ────────────────
        def request_close(self) -> None:
            try:
                self._on_close()
            except Exception:                            # pragma: no cover
                log.debug("game_copilot: overlay close handler failed", exc_info=True)

        def request_refresh(self) -> None:
            try:
                self._on_refresh()
            except Exception:                            # pragma: no cover
                log.debug("game_copilot: overlay refresh handler failed", exc_info=True)

        def _toggle_collapsed(self) -> None:
            self._collapsed = not self._collapsed
            # 🔴 A SIZE change must re-dock in the SAME call, never with a
            # glide and never as resize-then-move. Qt resizes around the
            # window's TOP-LEFT, so a panel docked on the RIGHT otherwise
            # grows RIGHTWARD off the screen ("it opens to the right instead
            # of the other way") and a collapsing one shrinks 430px inland
            # ("the tab runs away"). `_reflow` sets the geometry atomically.
            self._reflow()

        # ── long-press-drag reposition ───────────────────────
        # The PAGE only reports start/end. Python tracks the cursor itself,
        # because the page's `mousemove` stops firing the moment the pointer
        # outruns the moving window (the drag then freezes until the cursor
        # catches up = the stutter), and its screenX/screenY are CSS pixels
        # that disagree with Qt's coordinates on a scaled display, so the
        # window drifts away from the cursor as you drag.
        def _on_drag_start(self) -> None:
            self._stop_pos_anims()                       # grabbing mid-glide must not fight it
            self._dragging = True
            self._drag_mouse0 = QCursor.pos()
            self._drag_win0 = self.pos()
            self._js("window.setDimmed(true)")
            # 🔴 Acrylic re-samples what is behind the window on every move (a
            # documented source of laggy dragging on Windows 11), so the GLASS
            # mode drops to plain blur for the fraction of a second a drag
            # lasts. In TINT mode there is no blur to drop - forcing one on
            # here is what made the panel flicker clear->blurred->dark while
            # being dragged. The policy is surface-aware in ONE place.
            self._apply_accent(dragging=True)
            if self._drag_timer is None:
                self._drag_timer = QTimer(self)
                self._drag_timer.setInterval(16)         # ~60 Hz, same as the compositor
                self._drag_timer.timeout.connect(self._drag_tick)
            self._drag_timer.start()

        def _drag_tick(self) -> None:
            if self._drag_mouse0 is None or self._drag_win0 is None:
                return
            # 🔴 SAFETY: end a drag whose `mouseup` never arrived. The page
            # reports dragEnd from its own `mouseup`, and that event is lost
            # if the page reloads mid-drag, the window is hidden by the
            # hotkey, or the game grabs the pointer. Without this the timer
            # keeps running and the window CHASES THE CURSOR FOREVER with no
            # way to stop it - the worst stability bug this window can have.
            if not _primary_mouse_down():
                self._on_drag_finish()
                return
            self.move(self._clamp_on_screen(
                self._drag_win0 + (QCursor.pos() - self._drag_mouse0)))

        def _clamp_on_screen(self, p: "QPoint") -> "QPoint":
            """Keeps the window reachable. Dragging was unbounded, so it could
            be pushed completely off every monitor and effectively lost (the
            hotkey would 'work' while nothing appeared). Clamped against the
            union of ALL screens, leaving a visible margin."""
            union = None
            for sc in QApplication.screens():
                try:
                    g = sc.availableGeometry()
                except Exception:                        # pragma: no cover
                    continue
                union = g if union is None else union.united(g)
            if union is None:
                return p
            keep = 24                                    # px that must stay on-screen
            x = max(union.left() - self.width() + keep, min(p.x(), union.right() - keep))
            y = max(union.top(), min(p.y(), union.bottom() - keep))
            return QPoint(int(x), int(y))

        def _screen_for_point(self, p: "QPoint"):
            """The screen the panel actually sits on - NOT always the primary.
            Docking used `primaryScreen()` unconditionally, so on a
            multi-monitor setup the overlay was yanked back to monitor 1 the
            moment it was released, docked, or re-shown."""
            sc = QApplication.screenAt(p)
            return sc or QApplication.primaryScreen()

        def _stop_pos_anims(self) -> None:
            """Only ONE animation may own `pos`. The show-slide (280 ms) and
            the snap-glide (220 ms) could both be running - e.g. a dock
            change right after a show - and they then fight for the same
            property, which reads as the window stuttering or landing in the
            wrong place."""
            for name in ("_snap_anim", "_show_anim"):
                anim = getattr(self, name, None)
                if anim is not None:
                    try:
                        anim.stop()
                    except Exception:                    # pragma: no cover
                        pass
                    setattr(self, name, None)

        def _on_drag_move(self, gp: "QPoint") -> None:
            """Deliberately a no-op - kept only so a stale cached page that
            still calls `dragMove` cannot error. `_drag_tick` owns the move."""

        def _on_drag_finish(self) -> None:
            if not self._dragging:
                return                                   # already finished (double dragEnd)
            self._dragging = False
            if self._drag_timer is not None:
                self._drag_timer.stop()
            self._apply_accent()                         # surface-aware, never hardcoded
            self._js("window.setDimmed(false)")
            self._drag_mouse0 = None
            self._drag_win0 = None
            self._snap_to_nearest_edge()
            self._persist_position()

        def _snap_to_nearest_edge(self) -> None:
            self.adjustSize()
            center = self.geometry().center()
            screen = self._screen_for_point(center)      # the monitor it was dropped on
            if screen is None:
                return
            try:
                geo = screen.availableGeometry()
            except Exception:                            # pragma: no cover
                return
            # 🔴 NORMALISE by each axis's half-span. Comparing raw pixels lets
            # the screen's ASPECT RATIO decide the dock: on 1920x1030 the
            # vertical half is 515px and the horizontal half is 960px, so a
            # panel anywhere in the middle band is "nearer" to top/bottom than
            # to left/right no matter where the user dropped it - which is why
            # dragging near the top locked it to TOP and threw away the
            # horizontal position they had chosen. As a fraction of how far it
            # COULD be, the centre of the screen is equidistant from all four
            # and the nearest edge is the one the user actually aimed at.
            half_w = max(1.0, geo.width() / 2.0)
            half_h = max(1.0, geo.height() / 2.0)
            distances = {
                "left":   (center.x() - geo.left())   / half_w,
                "right":  (geo.right() - center.x())  / half_w,
                "top":    (center.y() - geo.top())    / half_h,
                "bottom": (geo.bottom() - center.y()) / half_h,
            }
            nearest = min(distances, key=distances.get)
            if nearest in ("left", "right"):
                frac = (center.y() - geo.top()) / max(1, geo.height())
            else:
                frac = (center.x() - geo.left()) / max(1, geo.width())
            self._edge = nearest
            self._edge_pos = max(0.04, min(0.96, frac))
            # GLIDE to the edge instead of teleporting - a release that
            # instantly warps the window across the screen is the single
            # biggest source of "it jumps". (`_reflow` downgrades the glide
            # to a snap by itself if the size changed.)
            self._reflow(animate=True)

        def _persist_position(self) -> None:
            try:
                from translation_manager.plugins import registry
                # patch_config (not set_config): a drag-release write must not clobber
                # a config change an in-flight analysis write-back is about to apply -
                # only touch the two fields this drag actually changed.
                registry.patch_config(_PLUGIN_ID, {"corner": self._edge, "edge_pos": self._edge_pos})
            except Exception:                            # pragma: no cover
                log.debug("game_copilot: failed to persist dragged position", exc_info=True)

        # ── content (auto-height to fit, animated once visible) ─
        def _js(self, code: str) -> None:
            """Run a snippet in the page, queueing it until the page has
            actually finished loading - `set_loading()` is often called
            within milliseconds of construction, long before `loadFinished`,
            and a runJavaScript against a half-loaded page is silently
            dropped (which reads exactly like 'the overlay shows nothing')."""
            if self._page_ready:
                self._view.page().runJavaScript(code)
            else:
                self._pending_js.append(code)

        def _flush_js(self, ok: bool = True) -> None:
            self._page_ready = True
            pending, self._pending_js = self._pending_js, []
            for code in pending:
                try:
                    self._view.page().runJavaScript(code)
                except Exception:                        # pragma: no cover
                    log.debug("game_copilot: overlay js failed", exc_info=True)

        def set_hotkey_label(self, label: str) -> None:
            self._js("window.setHint(%s)" % _js_str(
                f"{label} כדי להסתיר/להציג · ↻ לרענון הניתוח · לחיצה ארוכה על החץ = הזזה" if label
                else "לחיצה ארוכה על החץ ואז גרירה = הזזת החלונית"))

        def set_loading(self, game: str) -> None:
            self._game = game or ""
            self._js("window.setTitle(%s)" % _js_str("מנתח את המסך…"))
            self._js("window.setBody(%s)" % _js_str(
                f"<div class='step'>{_html.escape(self._game)}</div>" if self._game else ""))
            self.expand()

        def set_content(self, game: str, text: str) -> None:
            self._game = game or ""
            self._js("window.setTitle(%s)" % _js_str(self._game or "עוזר משחק"))
            self._js("window.setBody(%s)" % _js_str(_answer_html(text)))

        def set_error(self, msg: str) -> None:
            self._js("window.setTitle(%s)" % _js_str("שגיאה"))
            self._js("window.setBody(%s)" % _js_str(_error_html(msg)))

        # ── geometry / glass ─────────────────────────────────
        def _target_pos(self, w: int, h: int) -> "QPoint | None":
            """Where a w x h window belongs on its docked edge: flush to that
            edge, and CENTERED on `_edge_pos` along it - so a size change
            grows the panel symmetrically around that fixed anchor (up AND
            down / left AND right) and the rail stays put."""
            # Dock on the monitor the panel is ON, not always the primary -
            # otherwise every re-dock teleports it back to monitor 1.
            screen = self._screen_for_point(self.geometry().center())
            if screen is None:
                return None
            try:
                geo = screen.availableGeometry()
            except Exception:                            # pragma: no cover
                return None
            w = max(int(w), 1)
            h = max(int(h), 1)
            frac = max(0.04, min(0.96, self._edge_pos))
            # QRect.right()/bottom() are INCLUSIVE (x + w - 1), so the far
            # edge needs the +1 - without it the right/bottom margin came out
            # 11px against the left/top's 10 and the dock looked lopsided.
            right, bottom = geo.right() + 1, geo.bottom() + 1
            if self._edge in ("left", "right"):
                y = int(geo.top() + frac * geo.height() - h / 2)
                y = max(geo.top(), min(y, bottom - h))
                x = geo.left() + _EDGE_MARGIN if self._edge == "left" else right - w - _EDGE_MARGIN
            else:
                x = int(geo.left() + frac * geo.width() - w / 2)
                x = max(geo.left(), min(x, right - w))
                y = geo.top() + _EDGE_MARGIN if self._edge == "top" else bottom - h - _EDGE_MARGIN
            return QPoint(int(x), int(y))

        def _apply_geometry(self) -> None:
            """Moves AND resizes in ONE call, from the size we INTEND rather
            than the one Qt currently reports (which lags a layout change).
            One call = one paint, so the window can never be seen at the new
            size in the old place - which is what threw an expanding
            right-docked panel off the screen."""
            if self._dragging:
                return                                   # the drag owns the position right now
            w, h = self._size
            target = self._target_pos(w, h)
            self._stop_pos_anims()                       # a pending glide would undo this
            if target is None:                           # pragma: no cover
                self.resize(w, h)
                return
            self.setGeometry(target.x(), target.y(), w, h)

        def reposition(self, animated: bool = False) -> None:
            """Re-docks the window. `animated` GLIDES - but only for a pure
            move; a size change always snaps, because Qt resizes around the
            top-left and a glide would show the panel grow the wrong way
            first."""
            if self._dragging:
                return                                   # the drag owns the position right now
            w, h = self._size
            target = self._target_pos(w, h)
            if target is None:                           # pragma: no cover
                return
            resizing = (self.width(), self.height()) != (w, h)
            if not animated or resizing or not self.isVisible() or target == self.pos():
                self._apply_geometry()
                return
            self._stop_pos_anims()
            anim = QPropertyAnimation(self, b"pos", self)
            anim.setStartValue(self.pos())
            anim.setEndValue(target)
            anim.setDuration(220)
            anim.setEasingCurve(_spring_curve())
            self._snap_anim = anim
            anim.start()

        def show_animated(self) -> None:
            """Slides in from the direction of the docked edge (native, on
            the WINDOW) while the page fades itself in (CSS); a no-op
            position-wise (just raises) if it's already showing, so e.g.
            loading->result content swaps never re-trigger the entrance."""
            if self.isVisible():
                self.raise_()
                self._js("window.setShown(true)")
                return
            target_pos = self.pos()
            dx, dy = {"left": (-_SLIDE_OFFSET_PX, 0), "right": (_SLIDE_OFFSET_PX, 0),
                      "top": (0, -_SLIDE_OFFSET_PX), "bottom": (0, _SLIDE_OFFSET_PX)}.get(self._edge, (_SLIDE_OFFSET_PX, 0))
            start_pos = QPoint(target_pos.x() + dx, target_pos.y() + dy)
            self.move(start_pos)
            self.show()
            self.raise_()
            self._js("window.setShown(true)")
            mv = QPropertyAnimation(self, b"pos", self)
            mv.setStartValue(start_pos)
            mv.setEndValue(target_pos)
            mv.setDuration(280)
            mv.setEasingCurve(_spring_curve())
            self._show_anim = mv
            mv.start()

        def hide_animated(self) -> None:
            if not self.isVisible():
                return
            # Let the page's own CSS opacity transition (.2s) play out, THEN
            # take the window down - hiding immediately would cut the fade.
            self._js("window.setShown(false)")
            QTimer.singleShot(210, self._finish_hide)

        def _finish_hide(self) -> None:
            self.hide()

        def showEvent(self, e) -> None:                # noqa: N802 (Qt override)
            super().showEvent(e)
            # The page starts in its `gone` (opacity 0) state so the first
            # show_animated() FADES in rather than popping - which means a
            # plain .show() from any other path would leave a visible,
            # correctly-sized window rendering nothing at all. Un-hiding
            # here makes that impossible regardless of how it was shown.
            self._js("window.setShown(true)")
            if not self._glass_applied:
                self._glass_applied = True
                try:
                    _apply_glass(int(self.winId()))
                    self._apply_accent()             # THEN the real, surface-aware state
                    self._apply_round_region()
                except Exception:                    # pragma: no cover
                    pass

    class _CaptureDialog(QDialog):
        """Native 'press the new hotkey' popup. Samples the GLOBAL keyboard
        state (`GetAsyncKeyState`) every ~30ms plus gamepad state (XInput,
        falling back to the legacy winmm joystick API for pads XInput can't
        see - e.g. a PlayStation pad in its native mode), shows the combo
        forming live, and locks in the moment everything is released -
        "press 1-2 physical keys/buttons together, then let go". Once a
        gamepad press is seen it LOCKS onto that one backend for the rest of
        the attempt (the two backends are independent bitmask spaces; letting
        them race caused a real bug where releasing a 2-button combo either
        picked only part of it or asked to try again), and DEBOUNCES the
        "released" edge (several consecutive empty polls, not just one) so a
        single dropped sample from a wireless/BT pad can't finalize early."""

        def __init__(self, parent=None) -> None:
            super().__init__(parent, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
            # See the identical comment on _OverlayPanel.__init__ - WA_TranslucentBackground
            # goes layered (WS_EX_LAYERED) on Windows, which DWM Acrylic can't compose with.
            self.setAttribute(Qt.WA_NoSystemBackground, True)
            self.result_spec: dict | None = None
            self._kb_prev_empty = True
            self._kb_primary: int | None = None
            self._kb_combo: tuple[int, int] | None = None
            self._gp_backend_lock: str | None = None
            self._gp_combo = 0
            self._gp_release_streak = 0
            self._gp_armed_at: float | None = None
            self._gp_overflow = False
            self._esc_prev = False

            # Same intermediate-wrapper structure that fixed _OverlayPanel's
            # identical blank-window symptom: a top-level QDialog with
            # WA_NoSystemBackground and a card added DIRECTLY as its child
            # rendered as a flat, empty DWM-Acrylic-tinted rect - the card's
            # own paintEvent (and its labels) simply never made it into the
            # composited frame. Routing everything through one extra plain
            # QWidget (itself WA_TranslucentBackground/WA_NoSystemBackground)
            # between the native top-level surface and the real content is
            # what made _OverlayPanel paint correctly again; applying the
            # identical structure here rather than re-deriving a new theory.
            root = QVBoxLayout(self)
            root.setContentsMargins(0, 0, 0, 0)
            content = QWidget(self)
            content.setAttribute(Qt.WA_TranslucentBackground, True)
            content.setAttribute(Qt.WA_NoSystemBackground, True)
            content.setAutoFillBackground(False)
            root.addWidget(content)

            outer = QVBoxLayout(content)
            outer.setContentsMargins(0, 0, 0, 0)
            card = _GlassCard(content, radius=22.0)
            card.setFixedWidth(360)
            card.setLayoutDirection(Qt.RightToLeft)
            # No drop shadow, for the same reason as the overlay's card: the
            # glass pane is a hole in the faceplate, so the surrounding
            # metal's shadow spills inward and veils it (+45 alpha,
            # measured). The bright rim pen provides the separation.
            outer.addWidget(card)
            lay = QVBoxLayout(card)
            cpad = int(_BEZEL_W) + 8            # keep the content clear of the machined ring
            lay.setContentsMargins(cpad, cpad, cpad, cpad)
            lay.setSpacing(10)

            title = QLabel("קובעים קיצור דרך חדש")
            title.setAlignment(Qt.AlignCenter)
            title.setStyleSheet("color:#fff700;font-weight:700;font-size:14px;")
            sub = QLabel("לחצו על מקש, שילוב מקשים, או כפתור/י שלט - ואז שחררו")
            sub.setWordWrap(True)
            sub.setAlignment(Qt.AlignCenter)
            sub.setStyleSheet("color:#c3c9e6;font-size:11.5px;")

            self._live = QLabel("…")
            self._live.setWordWrap(True)
            self._live.setAlignment(Qt.AlignCenter)
            self._live.setMinimumHeight(52)
            self._live.setStyleSheet(
                "color:#38bdf8;font-size:19px;font-weight:800;padding:14px 8px;"
                "background:rgba(56,189,248,22);border-radius:12px;"
            )

            cancel = QPushButton("ביטול (Esc)")
            cancel.setCursor(Qt.PointingHandCursor)
            cancel.setStyleSheet(
                "QPushButton{background:rgba(255,255,255,16);border:none;border-radius:8px;"
                "color:#e8ecff;font-size:12px;padding:7px 14px;}"
                "QPushButton:hover{background:rgba(255,255,255,32);}"
            )
            cancel.clicked.connect(self.reject)

            lay.addWidget(title)
            lay.addWidget(sub)
            lay.addWidget(self._live)
            lay.addWidget(cancel, 0, Qt.AlignCenter)

            self._timer = QTimer(self)
            self._timer.timeout.connect(self._tick)
            self._deadline = QTimer(self)
            self._deadline.setSingleShot(True)
            self._deadline.timeout.connect(self.reject)

        def showEvent(self, e) -> None:                 # noqa: N802 (Qt override)
            super().showEvent(e)
            try:
                _apply_glass(int(self.winId()))
            except Exception:                          # pragma: no cover
                pass
            screen = QApplication.primaryScreen()
            if screen is not None:
                geo = screen.availableGeometry()
                self.adjustSize()
                self.move(geo.center().x() - self.width() // 2,
                          geo.center().y() - self.height() // 2)
            self._timer.start(30)
            self._deadline.start(25000)      # well under the caller's 30s wait budget

        def closeEvent(self, e) -> None:                 # noqa: N802 (Qt override)
            self._timer.stop()
            self._deadline.stop()
            super().closeEvent(e)

        _RELEASE_DEBOUNCE = 3      # consecutive empty polls (at 30ms => ~90ms) before "released" fires
        _ARM_MS = 320               # single-button hold before "locked, add another or release" hint

        def _tick(self) -> None:
            held = _keys_down()
            esc_now = _VK_ESCAPE in held
            if esc_now and not self._esc_prev:
                self.reject()
                return
            self._esc_prev = esc_now
            primaries = held - _MODIFIER_VKS - {_VK_ESCAPE}

            if held:
                if self._kb_prev_empty:
                    self._kb_primary = next(iter(primaries), None)
                elif self._kb_primary is None and primaries:
                    self._kb_primary = next(iter(primaries))
                self._kb_prev_empty = False
                if self._kb_primary is not None and self._kb_primary in held:
                    self._kb_combo = (_mods_from_held(held), self._kb_primary)
            else:
                if not self._kb_prev_empty and self._kb_combo and self._kb_combo[1]:
                    mods, vk = self._kb_combo
                    self.result_spec = {"type": "keyboard", "mods": mods, "vk": vk,
                                         "label": _kb_live_label(mods, vk)}
                    self.accept()
                    return
                self._kb_prev_empty = True
                self._kb_primary = None
                self._kb_combo = None

            # ── gamepad: lock onto whichever backend first reports a press
            # (see the class docstring) and debounce the release edge.
            if not held:
                if self._gp_backend_lock is None:
                    raw = _xinput_buttons()
                    if raw:
                        self._gp_backend_lock = "xinput"
                    else:
                        raw = _joy_legacy_buttons()
                        if raw:
                            self._gp_backend_lock = "legacy"
                elif self._gp_backend_lock == "xinput":
                    raw = _xinput_buttons()
                else:
                    raw = _joy_legacy_buttons()

                if raw:
                    self._gp_release_streak = 0
                    new_combo = raw if not self._gp_combo else (self._gp_combo | raw)
                    if new_combo != self._gp_combo and bin(new_combo).count("1") == 1:
                        self._gp_armed_at = time.monotonic()
                    self._gp_combo = new_combo
                    self._gp_overflow = bin(self._gp_combo).count("1") > 2
                elif self._gp_backend_lock is not None:
                    self._gp_release_streak += 1
                    if self._gp_release_streak >= self._RELEASE_DEBOUNCE:
                        if self._gp_combo and not self._gp_overflow:
                            label = (_gp_label(self._gp_combo) if self._gp_backend_lock == "xinput"
                                     else _joy_legacy_label(self._gp_combo))
                            self.result_spec = {"type": "gamepad", "backend": self._gp_backend_lock,
                                                 "buttons": self._gp_combo, "label": label}
                            self.accept()
                            return
                        self._gp_backend_lock = None
                        self._gp_combo = 0
                        self._gp_armed_at = None
                        self._gp_overflow = False
                        self._gp_release_streak = 0

            if held:
                self._live.setText(_kb_live_label(_mods_from_held(held), self._kb_primary) or "…")
            elif self._gp_combo:
                lbl = (_gp_label(self._gp_combo) if self._gp_backend_lock == "xinput"
                       else _joy_legacy_label(self._gp_combo))
                if self._gp_overflow:
                    self._live.setText((lbl or "…") + "\n⚠ עד 2 כפתורים בלבד")
                elif (self._gp_armed_at is not None and bin(self._gp_combo).count("1") == 1
                      and (time.monotonic() - self._gp_armed_at) * 1000 >= self._ARM_MS):
                    self._live.setText((lbl or "…") + "\n🔒 הוסיפו כפתור נוסף או שחררו לבחירה")
                else:
                    self._live.setText(lbl or "…")
            else:
                self._live.setText("…")

    class GameCopilotController(QObject):
        """Owns the overlay + the hotkey (keyboard or gamepad) + the poll
        loop that picks up requests coming from a non-GUI thread."""

        _showRequested = Signal(str, str)
        _errorRequested = Signal(str)

        def __init__(self) -> None:
            super().__init__()
            self._overlay: "_OverlayPanel | None" = None
            self._filter: "_HotkeyEventFilter | None" = None
            self._hotkey_spec: dict | None = None
            self._hotkey_registered = False
            self._edge = "right"
            self._edge_pos = 0.5
            self._surface = "tint"
            self._analyzing = False
            self._capturing = False
            self._last_toggle_seq = 0
            self._last_show_seq = 0
            self._last_capture_seq = 0
            self._gp_target = 0
            self._gp_backend = "xinput"
            self._gp_edge = False

            self._poll_timer = QTimer(self)
            self._poll_timer.timeout.connect(self._tick)
            self._gp_timer = QTimer(self)
            self._gp_timer.timeout.connect(self._gp_tick)
            self._showRequested.connect(self._on_show, Qt.QueuedConnection)
            self._errorRequested.connect(self._on_error, Qt.QueuedConnection)

        # ── lifecycle ───────────────────────────────────────
        def start(self) -> None:
            if not self._poll_timer.isActive():
                self._poll_timer.start(600)

        def stop(self) -> None:
            self._poll_timer.stop()
            self._teardown_hotkey()
            if self._overlay is not None:
                try:
                    self._overlay.hide()
                except Exception:                     # pragma: no cover
                    pass

        # ── the poll tick (GUI thread) ──────────────────────
        def _tick(self) -> None:
            try:
                from translation_manager.plugins import registry, game_copilot as gc
            except Exception:                          # pragma: no cover
                return
            try:
                enabled = registry.is_installed(_PLUGIN_ID) and registry.is_enabled(_PLUGIN_ID)
            except Exception:                          # pragma: no cover
                enabled = False
            if not enabled:
                if self._hotkey_registered or self._filter is not None or self._gp_timer.isActive():
                    self._teardown_hotkey()
                if self._overlay is not None and self._overlay.isVisible():
                    self._overlay.hide()
                    gc.report_runtime_status(visible=False)
                return

            self._sync_from_config()

            try:
                cap = gc.poll_capture_request(self._last_capture_seq)
            except Exception:                          # pragma: no cover
                cap = {"seq": self._last_capture_seq, "requested": False}
            if cap["requested"]:
                self._last_capture_seq = cap["seq"]
                self._run_capture(cap["seq"])
                return          # capture is synchronous (nested exec()); resume next tick

            try:
                pend = gc.poll_pending(self._last_toggle_seq, self._last_show_seq)
            except Exception:                          # pragma: no cover
                return
            self._last_toggle_seq = pend["toggle_seq"]
            self._last_show_seq = pend["show_seq"]
            if pend["toggled"]:
                self._toggle()
            if pend["shown"]:
                self._on_show(pend["show_game"], pend["show_text"])

        def _sync_from_config(self) -> None:
            from translation_manager.plugins import registry, game_copilot as gc
            try:
                cfg = registry.get_config(_PLUGIN_ID) or {}
            except Exception:                          # pragma: no cover
                cfg = {}
            hk = gc._normalize_hotkey(cfg.get("hotkey"))
            if hk != self._hotkey_spec:
                self._apply_hotkey(hk)
            self._edge = gc._normalize_edge(cfg.get("corner"))
            self._edge_pos = gc._normalize_edge_pos(cfg.get("edge_pos"))
            self._surface = gc._normalize_surface(cfg.get("surface"))
            if self._overlay is not None:
                self._overlay.set_edge(self._edge, self._edge_pos)
                self._overlay.set_surface(self._surface)

        # ── hotkey (GUI thread only) - keyboard OR gamepad ──
        def _apply_hotkey(self, hk: dict) -> None:
            from translation_manager.plugins import game_copilot as gc
            self._teardown_hotkey()
            self._hotkey_spec = hk
            label = hk.get("label", "")

            if hk.get("type") == "gamepad":
                self._gp_target = int(hk.get("buttons") or 0)
                self._gp_backend = hk.get("backend") or "xinput"
                driver_present = _WINMM is not None if self._gp_backend == "legacy" else _XINPUT is not None
                ok = driver_present and self._gp_target > 0
                if ok:
                    self._gp_timer.start(70)
                gc.report_runtime_status(hotkey_ok=ok, hotkey_label=label)
                if self._overlay is not None:
                    self._overlay.set_hotkey_label(label if ok else "")
                if not ok and not driver_present:
                    log.warning("game_copilot: no %s controller driver found on this machine",
                                self._gp_backend)
                return

            app = QApplication.instance()
            if app is None:
                return
            if self._filter is None:
                self._filter = _HotkeyEventFilter(self._on_hotkey)
                app.installNativeEventFilter(self._filter)
            ok = _register_hotkey(int(hk.get("mods") or 0), int(hk.get("vk") or 0))
            self._hotkey_registered = ok
            gc.report_runtime_status(hotkey_ok=ok, hotkey_label=label)
            if not ok:
                log.warning("game_copilot: could not register hotkey %r "
                            "(probably already in use by another program)", hk)
            if self._overlay is not None:
                self._overlay.set_hotkey_label(label if ok else "")

        def _teardown_hotkey(self) -> None:
            if self._hotkey_registered:
                _unregister_hotkey()
                self._hotkey_registered = False
            app = QApplication.instance()
            if self._filter is not None and app is not None:
                try:
                    app.removeNativeEventFilter(self._filter)
                except Exception:                      # pragma: no cover
                    pass
            self._filter = None
            self._gp_timer.stop()
            self._gp_target = 0
            self._gp_backend = "xinput"
            self._gp_edge = False
            self._hotkey_spec = None
            try:
                from translation_manager.plugins import game_copilot as gc
                gc.report_runtime_status(hotkey_ok=False, hotkey_label="")
            except Exception:                          # pragma: no cover
                pass

        def _on_hotkey(self) -> None:
            self._toggle()

        def _gp_tick(self) -> None:
            if self._capturing or not self._gp_target:
                return
            mask = _joy_legacy_buttons() if self._gp_backend == "legacy" else _xinput_buttons()
            pressed = (mask & self._gp_target) == self._gp_target
            if pressed and not self._gp_edge:
                self._toggle()
            self._gp_edge = pressed

        # ── hotkey CAPTURE (new-shortcut popup) ─────────────
        def _run_capture(self, seq: int) -> None:
            from translation_manager.plugins import game_copilot as gc
            self._capturing = True
            self._poll_timer.stop()
            prev_spec = self._hotkey_spec
            self._teardown_hotkey()
            try:
                dlg = _CaptureDialog()
                outcome = dlg.exec()
                result = dlg.result_spec if (outcome == QDialog.Accepted and dlg.result_spec) else "cancelled"
            except Exception:                          # pragma: no cover
                log.exception("game_copilot: capture dialog failed")
                result = "cancelled"
            try:
                gc.report_capture_result(seq, result)
            except Exception:                          # pragma: no cover
                pass
            self._capturing = False
            if prev_spec is not None:
                self._apply_hotkey(prev_spec)
            self._poll_timer.start(600)

        # ── overlay show/hide/analyze ────────────────────────
        def _ensure_overlay(self) -> "_OverlayPanel":
            if self._overlay is None:
                self._overlay = _OverlayPanel(on_close=self._hide_overlay,
                                              on_refresh=self._start_analysis)
                self._overlay.set_edge(self._edge, self._edge_pos)
                self._overlay.set_surface(self._surface)
            return self._overlay

        def _toggle(self) -> None:
            if self._overlay is not None and self._overlay.isVisible():
                self._hide_overlay()
            else:
                ov = self._ensure_overlay()
                ov.set_edge(self._edge, self._edge_pos)
                ov.expand()
                ov.set_loading("")
                ov.set_hotkey_label("")
                ov.reposition()
                ov.show_animated()
                try:
                    from translation_manager.plugins import game_copilot as gc
                    gc.report_runtime_status(visible=True)
                except Exception:                      # pragma: no cover
                    pass
                self._start_analysis()

        def _hide_overlay(self) -> None:
            if self._overlay is not None:
                self._overlay.hide_animated()
            try:
                from translation_manager.plugins import game_copilot as gc
                gc.report_runtime_status(visible=False)
            except Exception:                          # pragma: no cover
                pass

        def _start_analysis(self) -> None:
            if self._analyzing:
                return
            self._analyzing = True
            ov = self._ensure_overlay()
            was_visible = ov.isVisible()
            # `ov._game` is the detected game name ("" when none). This used
            # to read a `_title` QLabel that the header row carried - that
            # row was removed when the panel was redesigned, so this line
            # raised AttributeError on EVERY hotkey press and the overlay
            # never appeared at all.
            ov.set_loading(ov._game)
            if not was_visible:
                ov.reposition()
                ov.show_animated()
                try:
                    from translation_manager.plugins import game_copilot as gc
                    gc.report_runtime_status(visible=True)
                except Exception:                      # pragma: no cover
                    pass

            def _work() -> None:
                try:
                    from translation_manager.plugins import registry, game_copilot as gc
                    cfg = registry.get_config(_PLUGIN_ID) or {}
                    res = gc.analyze(cfg)
                    try:
                        # analyze() runs for seconds on this background thread while the
                        # user may open Settings and change a field on the GUI thread -
                        # patch_config merges onto the LATEST config at write time instead
                        # of blind-replacing with this now-stale `cfg` snapshot, so a
                        # concurrent Settings edit can never be silently reverted.
                        registry.patch_config(_PLUGIN_ID, {
                            "last_game": res.get("game") or "",
                            "last_at": int(time.time()),
                            "last_text": res.get("text") or "",
                            "last_ok": bool(res.get("ok")),
                            "last_error": res.get("error") or "",
                        })
                    except Exception:                  # pragma: no cover
                        pass
                    if res.get("ok"):
                        self._showRequested.emit(res.get("game") or "", res.get("text") or "")
                    else:
                        self._errorRequested.emit(res.get("error") or "שגיאה לא ידועה")
                except Exception as e:                  # pragma: no cover
                    self._errorRequested.emit(f"שגיאה לא צפויה: {e}")
                finally:
                    self._analyzing = False

            threading.Thread(target=_work, name="game-copilot-analyze", daemon=True).start()

        # ── queued-connection handlers (GUI thread) ─────────
        def _on_show(self, game: str, text: str) -> None:
            ov = self._ensure_overlay()
            ov.expand()
            ov.set_content(game, text)
            ov.reposition()
            ov.set_hotkey_label(self._hotkey_spec.get("label", "") if self._hotkey_spec else "")
            ov.show_animated()
            try:
                from translation_manager.plugins import game_copilot as gc
                gc.report_runtime_status(visible=True)
            except Exception:                          # pragma: no cover
                pass

        def _on_error(self, msg: str) -> None:
            if self._overlay is not None and self._overlay.isVisible():
                self._overlay.set_error(msg)


_controller: "GameCopilotController | None" = None


def ensure_started() -> None:
    """Called once at boot (main_qt.py). Idempotent and cheap - a QTimer tick
    every 600ms that is a no-op until the plugin is installed+enabled. Safe to
    call unconditionally; a no-op off Windows."""
    global _controller
    if not _IS_WIN:
        return
    try:
        if _controller is None:
            _controller = GameCopilotController()
        _controller.start()
    except Exception:                                  # pragma: no cover
        log.exception("game_copilot_runtime: failed to start")


def refresh_surface() -> None:
    """Hook for the Settings panel's `set_surface` action.

    Deliberately does NO work: it runs on a QThreadPool WORKER, and touching a
    QWidget off the GUI thread is exactly the class of bug this runtime already
    routes around everywhere else. The controller's own 600ms GUI-thread poll
    re-reads the config every tick and calls `_OverlayPanel.set_surface`, so the
    new look lands within ~0.6s with no cross-thread plumbing to get wrong.
    Kept as a named no-op so the intent is obvious at the call site."""
    return


def stop() -> None:
    """Called on real app exit so the global hotkey is released cleanly."""
    if _controller is not None:
        try:
            _controller.stop()
        except Exception:                              # pragma: no cover
            pass
