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

from PySide6.QtCore import QUrl, Qt
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
    def show_and_activate(self) -> None:
        """Tray 'Open' calls this. Restores from minimized/hidden state
        and pulls the window to the foreground."""
        if self.isMinimized():
            self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        self.show()
        self.raise_()
        self.activateWindow()

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
