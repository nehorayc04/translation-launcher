"""
The launcher's main QMainWindow - hosts a QWebEngineView that loads the
React app from frontend/dist/index.html and binds the QWebChannel bridge.

Close-to-tray plumbing lives here: closeEvent consults launcher_prefs
and either hides the window (minimize) or accepts the close (exit). The
tray module owns the QSystemTrayIcon and calls show_and_activate() on
'Open'.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import QPoint, QUrl, Qt, Slot
from PySide6.QtGui import (QBrush, QCloseEvent, QColor, QDesktopServices, QIcon,
                           QLinearGradient, QPainter, QPen)
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QVBoxLayout, QWidget

from .popup import WebPopup

log = logging.getLogger(__name__)

_WINDOW_TITLE = "מנהל התרגומים הרשמי"

# ── Win32 bits for the CUSTOM (but still fully native) window frame ──
# We deliberately do NOT use Qt.FramelessWindowHint: it strips the window's
# non-client area and with it Aero Snap (drag to an edge), the Windows 11
# snap-layouts picker, the drop shadow and the rounded corners. Instead the window
# stays a completely NORMAL Windows window and we ZERO the frame by handling
# WM_NCCALCSIZE - the same technique VS Code / Windows Terminal use. Everything
# native keeps working; we just draw our own title bar in the reclaimed space.
_WM_NCCALCSIZE = 0x0083

if sys.platform == "win32":                       # pragma: no cover - Windows only
    import ctypes as _ct

    class _RECT(_ct.Structure):
        _fields_ = [("left", _ct.c_long), ("top", _ct.c_long),
                    ("right", _ct.c_long), ("bottom", _ct.c_long)]

    class _NCCALCSIZE_PARAMS(_ct.Structure):
        _fields_ = [("rgrc", _RECT * 3), ("lppos", _ct.c_void_p)]

    class _MSG(_ct.Structure):
        _fields_ = [("hwnd", _ct.c_void_p), ("message", _ct.c_uint),
                    ("wParam", _ct.c_size_t), ("lParam", _ct.c_ssize_t),
                    ("time", _ct.c_uint), ("pt_x", _ct.c_long), ("pt_y", _ct.c_long)]


class _WinButton(QWidget):
    """A single window-control button (minimize / maximize / restore / close),
    painted natively. It lives in the Qt MAIN process, so it stays instantly
    responsive no matter what the embedded web content is doing - the whole
    point of moving the title bar out of the React/web layer."""

    def __init__(self, kind: str, on_click, parent=None) -> None:
        super().__init__(parent)
        self._kind = kind            # 'min' | 'max' | 'restore' | 'close'
        self._on_click = on_click
        self._hover = False
        self.setFixedSize(46, 34)
        self.setCursor(Qt.PointingHandCursor)

    def set_kind(self, kind: str) -> None:
        if kind != self._kind:
            self._kind = kind
            self.update()

    def enterEvent(self, e) -> None:   # noqa: N802
        self._hover = True; self.update()

    def leaveEvent(self, e) -> None:   # noqa: N802
        self._hover = False; self.update()

    def mousePressEvent(self, e) -> None:   # noqa: N802
        if e.button() == Qt.LeftButton:
            e.accept()

    def mouseReleaseEvent(self, e) -> None:   # noqa: N802
        # Fire on release-inside (standard button behaviour) so a press that
        # slides off doesn't trigger.
        if e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self._on_click()

    def paintEvent(self, e) -> None:   # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        if self._hover:
            p.fillRect(self.rect(), QColor(255, 255, 255, 18))
        colors = {"min": QColor(0, 255, 224), "max": QColor(255, 247, 0),
                  "restore": QColor(255, 247, 0), "close": QColor(255, 77, 109)}
        col = colors[self._kind] if self._hover else QColor(190, 198, 220)
        pen = QPen(col); pen.setWidthF(1.5); pen.setCapStyle(Qt.RoundCap); pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        cx, cy, s = self.width() // 2, self.height() // 2, 5
        if self._kind == "min":
            p.drawLine(cx - s, cy, cx + s, cy)
        elif self._kind == "max":
            p.drawRect(cx - s, cy - s, 2 * s, 2 * s)
        elif self._kind == "restore":
            p.drawRect(cx - s + 2, cy - s, 2 * s - 2, 2 * s - 2)     # front square
            p.drawLine(cx - s, cy - s + 2, cx - s, cy + s - 2)       # back square hint
            p.drawLine(cx - s, cy - s + 2, cx + s - 4, cy - s + 2)
        elif self._kind == "close":
            p.drawLine(cx - s, cy - s, cx + s, cy + s)
            p.drawLine(cx - s, cy + s, cx + s, cy - s)
        p.end()


class _NativeTitleBar(QWidget):
    """The frameless window's title bar as a NATIVE Qt widget (drag + double-
    click-maximize + min/max/close), sitting ABOVE the web view. Because it is
    a real widget in the main process - not a React element inside the web
    content - it never freezes while the web UI is busy loading/rendering
    (e.g. a plugin's settings). Background work is untouched; only the bar is
    decoupled. Drag starts only after the pointer actually MOVES, so a click or
    a double-click never enters Windows' modal move loop and gets swallowed."""

    def __init__(self, win: "MainWindow") -> None:
        super().__init__(win)
        self._win = win
        self._press: QPoint | None = None
        self._dragging = False
        self.setFixedHeight(34)
        self.setAttribute(Qt.WA_StyledBackground, True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addStretch(1)                                    # empty drag region
        self._btn_min = _WinButton("min", win.showMinimized, self)
        self._btn_max = _WinButton("max", self._toggle_max, self)
        self._btn_close = _WinButton("close", win.close, self)
        lay.addWidget(self._btn_min)
        lay.addWidget(self._btn_max)
        lay.addWidget(self._btn_close)

    def _toggle_max(self) -> None:
        if self._win.isMaximized():
            self._win.showNormal()
        else:
            self._win.showMaximized()
        self.sync_max_state()

    def sync_max_state(self) -> None:
        self._btn_max.set_kind("restore" if self._win.isMaximized() else "max")

    def paintEvent(self, e) -> None:   # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = self.rect()
        # Frosted-glass LOOK via pure painting: a translucent-dark vertical
        # gradient + a faint top sheen + a bottom hairline. Deliberately NOT a
        # CSS backdrop-filter blur (that's the CPU killer under the embedded web
        # engine) - this costs nothing to render.
        g = QLinearGradient(0, 0, 0, r.height())
        g.setColorAt(0.0, QColor(30, 34, 52, 232))
        g.setColorAt(1.0, QColor(9, 11, 22, 232))
        p.fillRect(r, QBrush(g))
        p.setPen(QColor(255, 255, 255, 30))                  # top sheen
        p.drawLine(0, 0, r.width(), 0)
        p.setPen(QColor(255, 255, 255, 14))                  # bottom hairline
        p.drawLine(0, r.height() - 1, r.width(), r.height() - 1)
        p.end()

    def mousePressEvent(self, e) -> None:   # noqa: N802
        if e.button() == Qt.LeftButton:
            self._press = e.globalPosition().toPoint()
            self._dragging = False
            e.accept()

    def mouseMoveEvent(self, e) -> None:   # noqa: N802
        if self._press is None or self._dragging:
            return
        gp = e.globalPosition().toPoint()
        if (abs(gp.x() - self._press.x()) > 4 or abs(gp.y() - self._press.y()) > 4):
            self._dragging = True
            self._press = None
            h = self._win.windowHandle()
            if h is not None:
                h.startSystemMove()

    def mouseReleaseEvent(self, e) -> None:   # noqa: N802
        self._press = None
        self._dragging = False

    def mouseDoubleClickEvent(self, e) -> None:   # noqa: N802
        if e.button() == Qt.LeftButton:
            self._toggle_max()


def frontend_index() -> Path:
    """Locate frontend/dist/index.html for both source and frozen builds.

    Public so main_qt.py can convert it to a QUrl + pass it to MainWindow
    (or override it with http://localhost:5173 under --dev)."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        p = Path(base) / "frontend" / "dist" / "index.html"
        if p.exists():
            return p
    return Path(__file__).resolve().parent.parent.parent / "frontend" / "dist" / "index.html"


def _report_hidden(hidden: bool) -> None:
    """Tell perf_manager whether the user can actually SEE us.

    Without this the module can only sense "not foreground" = "background"
    (3x backoff) and is_dormant() stays False, so trim_memory() NEVER fires
    while we sit in the tray - which is the single scenario the whole adaptive
    memory feature exists for (holding ~150-300 MB of Chromium behind a running
    game). Best-effort; never raises."""
    try:
        from .. import perf_manager
        perf_manager.set_hidden(hidden)
    except Exception:
        log.debug("perf_manager.set_hidden(%s) skipped", hidden, exc_info=True)


def _icon_path() -> Path | None:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        p = Path(base) / "build_assets" / "app.ico"
        if p.exists():
            return p
    p = Path(__file__).resolve().parent.parent.parent / "build_assets" / "app.ico"
    return p if p.exists() else None


class MainWindow(QMainWindow):
    """Hosts the React shell + the QWebChannel bridge."""

    def __init__(self,
                 profile,
                 bridge,
                 prefs_getter,
                 on_close_to_exit,
                 initial_url: QUrl,
                 parent=None) -> None:
        """
        :param profile:          QWebEngineProfile (shared with popups)
        :param bridge:           Bridge QObject (lives on main thread)
        :param prefs_getter:     callable returning launcher_prefs.get_close_behavior()
                                 result at the moment of the close event.
        :param on_close_to_exit: callable invoked when the user confirms a
                                 real exit (so main_qt.py can quit tray etc.)
        :param initial_url:      QUrl the QWebEngineView loads on boot.
                                 main_qt.py picks between file:// (frontend/dist)
                                 and http://localhost:5173 (--dev Vite server).
        """
        super().__init__(parent)
        self.setWindowTitle(_WINDOW_TITLE)
        self.resize(1400, 900)
        ico = _icon_path()
        if ico is not None:
            self.setWindowIcon(QIcon(str(ico)))

        # CUSTOM title bar - ON by default. The React app draws its own title bar
        # (min/max/close); drag/resize are driven from JS via the bridge's
        # startSystemMove / startSystemResize. NOTE we do NOT set
        # Qt.FramelessWindowHint - the window stays a NORMAL Windows window (so Aero
        # Snap, the Win11 snap-layouts picker, the shadow and the rounded corners all
        # keep working) and the frame is zeroed in nativeEvent() via WM_NCCALCSIZE.
        # Fully reversible (Settings + tray → restart), so a broken window is undoable.
        self._frameless = False
        try:
            from .. import launcher_prefs
            if launcher_prefs.get_custom_titlebar():
                self.setMinimumSize(900, 600)
                self._frameless = True
        except Exception:
            log.debug("custom title bar setup skipped", exc_info=True)

        self._prefs_getter    = prefs_getter
        self._on_close_to_exit = on_close_to_exit
        self._allow_exit       = False  # tray "Quit" flips this

        # ── Webview + channel ───────────────────────────────────
        self.view = QWebEngineView(self)
        self.page = QWebEnginePage(profile, self.view)
        self.view.setPage(self.page)
        # Paint any dropped/pre-first-paint frame the app's DARK base
        # (#050510) instead of pure black. Under --disable-gpu-compositing
        # a GPU-saturation frame-drop momentarily shows the page's
        # background color; with none set that default is BLACK → the
        # reported "black bars" flicker. A dark base makes a dropped frame
        # nearly invisible against the app's own dark UI.
        self.page.setBackgroundColor(QColor("#050510"))
        # Also pin the QMainWindow's OWN chrome to the same dark tone, so the brief
        # pre-web-paint window frame is #050510 (not a themed gray/black flash)
        # during a cold boot / restore.
        try:
            from PySide6.QtGui import QPalette
            _pal = self.palette()
            _pal.setColor(QPalette.Window, QColor("#050510"))
            self.setPalette(_pal)
        except Exception:
            pass

        # Frameless → a NATIVE Qt title bar ABOVE the web view (so its controls
        # never freeze while the web content is busy). Otherwise the plain view.
        self._native_titlebar: _NativeTitleBar | None = None
        if self._frameless:
            container = QWidget(self)
            v = QVBoxLayout(container)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(0)
            self._native_titlebar = _NativeTitleBar(self)
            v.addWidget(self._native_titlebar)
            v.addWidget(self.view, 1)
            self.setCentralWidget(container)
            # The QWebEngineView is a native surface that can render OVER sibling
            # widgets - keep the title bar stacked above it so its bar/buttons are
            # never covered by the web content bleeding up into the top strip.
            self._native_titlebar.raise_()
        else:
            self.setCentralWidget(self.view)

        self.channel = QWebChannel(self.page)
        self.channel.registerObject("bridge", bridge)
        self.page.setWebChannel(self.channel)

        # Forward target="_blank" / window.open into a WebPopup. Critical
        # for PayPal Smart Buttons: clicking "Pay" inside the embedded
        # PayPal iframe opens a popup the SDK then drives.
        self.page.newWindowRequested.connect(self._on_new_window)

        self.view.setUrl(initial_url)

    # ──────────────────────────────────────────────────────────────
    # Window lifecycle
    # ──────────────────────────────────────────────────────────────
    @Slot()
    def hide_for_game(self) -> None:
        """Put the window away because a GAME was just launched from the library.

        Called cross-thread (the launch runs on a bridge worker) via
        QMetaObject.invokeMethod BY NAME - so, exactly like `show_and_activate`
        below, the @Slot decorator is REQUIRED or the invoke silently no-ops.

        Hiding (not just minimising) is what actually stops QtWebEngine
        painting/compositing on the GPU the game needs, and removes any
        always-on-top surface that would knock it out of exclusive fullscreen.
        The tray icon stays, so the user gets the window back the usual way."""
        try:
            self.hide()
            _report_hidden(True)       # hidden → longest poll cadence + memory trim
        except Exception:
            log.debug("hide_for_game failed", exc_info=True)

    @Slot()
    def show_and_activate(self) -> None:
        """Restore from minimized/hidden state and pull the window to the
        foreground. Called directly by the tray 'Open' menu AND - via
        QMetaObject.invokeMethod by NAME - by the single-instance listener
        when a second launch (desktop shortcut) wakes us. The @Slot
        decorator is REQUIRED for that by-name invoke to resolve; without
        it the shortcut-relaunch silently failed to raise the window."""
        # Un-throttle perf FIRST so the page's timers/rAF resume before we show
        # (invalidates perf_manager's ~2s sense cache immediately), then WAKE the
        # QtWebEngine page + React shell so the first frame composites at once
        # instead of leaving the dark #050510 base up for a few seconds after a
        # tray/idle restore (the reported "dark-blue then it opens" delay).
        _report_hidden(False)          # visible again → full cadence, stop trimming
        if self.isMinimized():
            self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        try:
            self.view.show()
        except Exception:
            pass
        self._wake_web_page()
        self.show()
        self.raise_()
        self.activateWindow()
        self._force_foreground()

    def _wake_web_page(self) -> None:
        """Resume a throttled/hidden QtWebEngine page and nudge the React shell
        awake so the first frame composites fast after a tray/idle restore.
        Every API call is getattr-guarded so a missing Qt API never raises."""
        try:
            st = getattr(QWebEnginePage, "LifecycleState", None)
            set_life = getattr(self.page, "setLifecycleState", None)
            if callable(set_life) and st is not None:
                set_life(st.Active)
            set_vis = getattr(self.page, "setVisible", None)
            if callable(set_vis):
                set_vis(True)
        except Exception:
            log.debug("_wake_web_page: page resume nudge failed", exc_info=True)
        try:
            # Wake the React shell: resume paused rAF/animations + force a repaint.
            self.page.runJavaScript(
                "document.dispatchEvent(new Event('visibilitychange'));"
                "window.dispatchEvent(new Event('focus'));")
        except Exception:
            pass

    def _force_foreground(self) -> None:
        """Windows focus-stealing prevention can leave activateWindow() with
        the window un-hidden but stuck behind the foreground app. Nudge it
        with the Win32 APIs (best-effort, no-op off Windows / on failure).
        The relaunching process calls AllowSetForegroundWindow first (see
        single_instance.signal_show) so this is permitted to take focus."""
        if sys.platform != "win32":
            return
        try:
            import ctypes
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32
            SW_RESTORE = 9
            user32.ShowWindow(hwnd, SW_RESTORE)
            user32.SetForegroundWindow(hwnd)
        except Exception:
            log.debug("show_and_activate: _force_foreground best-effort failed", exc_info=True)

    def _is_foreground(self) -> bool:
        """True iff OUR window is the current foreground window (Win32)."""
        if sys.platform != "win32":
            return bool(self.isActiveWindow())
        try:
            import ctypes
            return int(ctypes.windll.user32.GetForegroundWindow()) == int(self.winId())
        except Exception:
            return bool(self.isActiveWindow())

    @Slot()
    def toggle_visibility(self) -> None:
        """Taskbar-button toggle: bring a hidden/minimized window forward, but
        MINIMIZE a window that is already up front. Called by the single-instance
        relaunch (clicking the pinned taskbar icon relaunches the exe → the
        running instance gets woken here) so a second click hides the window the
        way Windows users expect - instead of always re-showing it. A window that
        is visible but BEHIND another app comes forward (never a no-op)."""
        try:
            if self.isMinimized() or not self.isVisible():
                self.show_and_activate()
            elif self._is_foreground():
                self.showMinimized()
            else:
                self.show_and_activate()
        except Exception:
            log.debug("toggle_visibility failed → show", exc_info=True)
            self.show_and_activate()

    # ──────────────────────────────────────────────────────────────
    # "ביג-לאנץ" — the separate 10ft console shell
    # ──────────────────────────────────────────────────────────────
    @Slot(bool, result=bool)
    def set_big_launch(self, on: bool) -> bool:
        """Enter/leave the borderless-fullscreen console state.

        The console shell is a genuinely separate experience (its own React
        root, its own shortcut), so it gets a genuinely separate WINDOW state:
        real fullscreen, no title bar, no resize handles. We remember the
        pre-fullscreen geometry so leaving restores the exact desktop window
        the user had - `showNormal()` alone loses a maximized state.

        Returns the state actually applied (False if the window refused)."""
        try:
            if on:
                if not self.isFullScreen():
                    self._pre_big_maximized = bool(self.isMaximized())
                    self._pre_big_geometry = self.saveGeometry()
                    # The custom title bar is part of the DESKTOP chrome - hide
                    # it so the console shell owns the whole surface.
                    if self._native_titlebar is not None:
                        self._native_titlebar.setVisible(False)
                    self.showFullScreen()
                return True
            # ── back to the desktop shell ──
            if self.isFullScreen():
                self.showNormal()
                geo = getattr(self, "_pre_big_geometry", None)
                if geo is not None:
                    try: self.restoreGeometry(geo)
                    except Exception: pass
                if getattr(self, "_pre_big_maximized", False):
                    self.showMaximized()
            if self._native_titlebar is not None:
                self._native_titlebar.setVisible(True)
            return False
        except Exception:
            log.debug("set_big_launch(%s) failed", on, exc_info=True)
            return False

    def nativeEvent(self, eventType, message):   # noqa: N802 (Qt override)
        """CUSTOM FRAME: zero the non-client area instead of using
        Qt.FramelessWindowHint.

        FramelessWindowHint strips the window's non-client area, and Windows keys
        Aero Snap (drag to an edge → half/maximize), the Win11 snap-layouts picker,
        the drop shadow and the rounded corners off exactly that. So we leave the
        window a completely NORMAL Windows window and simply tell Windows the frame
        has zero size (WM_NCCALCSIZE, client rect == window rect). Result: it snaps,
        shows the layout picker, casts a shadow and rounds its corners like any other
        window - we just paint our own title bar in the space the frame used to take.
        (Same technique as VS Code / Windows Terminal.)"""
        if sys.platform != "win32" or not getattr(self, "_frameless", False):
            return super().nativeEvent(eventType, message)
        try:
            et = bytes(eventType) if not isinstance(eventType, bytes) else eventType
            if et != b"windows_generic_MSG":
                return super().nativeEvent(eventType, message)
            msg = _ct.cast(int(message), _ct.POINTER(_MSG)).contents
            if msg.message == _WM_NCCALCSIZE and msg.wParam:
                if self.isMaximized():
                    # A maximized window whose frame is zeroed overhangs the work
                    # area by the border width and its edges get clipped off-screen.
                    # Inset the client rect by that border to sit flush instead.
                    p = _ct.cast(msg.lParam, _ct.POINTER(_NCCALCSIZE_PARAMS)).contents
                    u = _ct.windll.user32
                    pad = u.GetSystemMetrics(92)                    # SM_CXPADDEDBORDER
                    bx  = u.GetSystemMetrics(32) + pad              # SM_CXSIZEFRAME
                    by  = u.GetSystemMetrics(33) + pad              # SM_CYSIZEFRAME
                    p.rgrc[0].left   += bx
                    p.rgrc[0].top    += by
                    p.rgrc[0].right  -= bx
                    p.rgrc[0].bottom -= by
                return True, 0        # handled → client area fills the whole window
        except Exception:
            log.debug("nativeEvent WM_NCCALCSIZE failed", exc_info=True)
        return super().nativeEvent(eventType, message)

    def changeEvent(self, event) -> None:   # noqa: N802 (Qt override)
        # Keep the native title bar's max/restore glyph in sync when the window
        # is maximized/restored by ANY means (Aero Snap, Win+Up, the taskbar).
        super().changeEvent(event)
        try:
            from PySide6.QtCore import QEvent
            if event.type() == QEvent.WindowStateChange:
                if self._native_titlebar is not None:
                    self._native_titlebar.sync_max_state()
                # A MINIMISED window is just as invisible as a tray-hidden one -
                # report it so the launcher backs off + releases RAM there too.
                _report_hidden(self.isMinimized())
        except Exception:
            pass

    def showEvent(self, event) -> None:   # noqa: N802 (Qt override)
        super().showEvent(event)
        # Round the frameless window's corners once it's shown (Win11 DWM). The
        # DWM compositor clips the whole surface - incl. the web content - so no
        # CSS rounding is needed. Best-effort; a no-op on Win10/off-Windows.
        if getattr(self, "_frameless", False) and not getattr(self, "_corners_rounded", False):
            self._corners_rounded = True
            self._apply_rounded_corners()

    def _apply_rounded_corners(self) -> None:
        """Win11: DWMWCP_ROUND on the frameless window (best-effort)."""
        if sys.platform != "win32":
            return
        try:
            import ctypes
            from ctypes import wintypes
            hwnd = wintypes.HWND(int(self.winId()))
            DWMWA_WINDOW_CORNER_PREFERENCE = 33
            DWMWCP_ROUND = 2
            pref = ctypes.c_int(DWMWCP_ROUND)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(pref), ctypes.sizeof(pref))
        except Exception:
            log.debug("rounded corners best-effort failed", exc_info=True)

    @Slot(str)
    def navigate_to_game(self, game_id: str) -> None:
        """Deep-link target - bring the window forward and tell the React
        shell to open this game's detail panel. Used when an ALREADY-RUNNING
        instance is re-invoked with hebrewhub://game/<id> (a cold start instead
        carries the id in the initial URL hash). Marshalled to the GUI thread
        by main_qt.py's single-instance listener via QMetaObject.invokeMethod."""
        import json as _json
        self.show_and_activate()
        try:
            self.page.runJavaScript(
                "window.dispatchEvent(new CustomEvent('deep-link-game',"
                "{detail:{id:%s}}))" % _json.dumps(str(game_id))
            )
        except Exception:
            log.exception("navigate_to_game failed")

    def request_real_exit(self) -> None:
        """Called by the tray 'Quit' menu so the next closeEvent skips
        the minimize-to-tray branch."""
        self._allow_exit = True
        self.close()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._allow_exit:
            self._on_close_to_exit()
            event.accept()
            return
        try:
            pref = self._prefs_getter()
        except Exception:
            # FAIL SAFE, NOT DESTRUCTIVE. This used to fall through to the real
            # exit branch, so a transient prefs read failure (an AV/indexer lock
            # on launcher_prefs.json) turned a click on X into "kill the app" -
            # taking any in-flight download / mod install with it. Minimising is
            # both the DEFAULT and the recoverable choice, so an unknown pref
            # must land there.
            log.warning("closeEvent: prefs unreadable → defaulting to minimize",
                        exc_info=True)
            pref = "minimize"
        if pref == "minimize":
            event.ignore()
            self.hide()
            _report_hidden(True)       # in the tray → back off hard + release RAM
            return
        # Explicit "close" → genuine exit.
        self._on_close_to_exit()
        event.accept()

    # ──────────────────────────────────────────────────────────────
    # Popup routing (PayPal etc.)
    # ──────────────────────────────────────────────────────────────
    def _on_new_window(self, request) -> None:
        """A target="_blank" / window.open originated in the React app.

        EVERY real external site ("visit website" links, the hub, openiv, the
        web profile, AND the purchase flow - payment is done on the website now,
        not via an in-app PayPal popup) opens in the user's DEFAULT system
        browser, never an in-app window. Only an about:blank / localhost blank
        (no real host) falls back to an in-app WebPopup for any internal flow.
        """
        try:
            url = request.requestedUrl()
            host = (url.host() or "").lower()
            if url.isValid() and url.scheme() in ("http", "https") and host \
                    and host not in ("localhost", "127.0.0.1"):
                QDesktopServices.openUrl(url)     # → system browser
                return
            # about:blank / localhost / non-web scheme → in-app popup fallback.
            popup = WebPopup(self.page.profile(), parent=self)
            popup.show()
            request.openIn(popup.page)
        except Exception:
            log.exception("main_window: failed to route new window")
