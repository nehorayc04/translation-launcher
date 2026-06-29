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

from PySide6.QtCore import QUrl, Qt, Slot
from PySide6.QtGui import QCloseEvent, QIcon
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QMainWindow

from .popup import WebPopup

log = logging.getLogger(__name__)

_WINDOW_TITLE = "מנהל התרגומים הרשמי"


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

        self._prefs_getter    = prefs_getter
        self._on_close_to_exit = on_close_to_exit
        self._allow_exit       = False  # tray "Quit" flips this

        # ── Webview + channel ───────────────────────────────────
        self.view = QWebEngineView(self)
        self.page = QWebEnginePage(profile, self.view)
        self.view.setPage(self.page)
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
    def show_and_activate(self) -> None:
        """Restore from minimized/hidden state and pull the window to the
        foreground. Called directly by the tray 'Open' menu AND — via
        QMetaObject.invokeMethod by NAME — by the single-instance listener
        when a second launch (desktop shortcut) wakes us. The @Slot
        decorator is REQUIRED for that by-name invoke to resolve; without
        it the shortcut-relaunch silently failed to raise the window."""
        if self.isMinimized():
            self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        self.show()
        self.raise_()
        self.activateWindow()
        self._force_foreground()

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

    @Slot(str)
    def navigate_to_game(self, game_id: str) -> None:
        """Deep-link target — bring the window forward and tell the React
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
            pref = None
        if pref == "minimize":
            event.ignore()
            self.hide()
            return
        # "close" or unset (first-launch will have rendered the modal in
        # React before the close attempt) → genuine exit.
        self._on_close_to_exit()
        event.accept()

    # ──────────────────────────────────────────────────────────────
    # Popup routing (PayPal etc.)
    # ──────────────────────────────────────────────────────────────
    def _on_new_window(self, request) -> None:
        try:
            popup = WebPopup(self.page.profile(), parent=self)
            popup.show()
            request.openIn(popup.page)
        except Exception:
            log.exception("main_window: failed to spawn popup")
