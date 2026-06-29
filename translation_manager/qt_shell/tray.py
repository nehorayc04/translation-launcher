"""
Native QSystemTrayIcon - replaces the pystray + daemon-thread scheme
used by the Eel build.

Two menu items, matching the existing Hebrew labels:
  * "פתח את התוכנה"  → MainWindow.show_and_activate()
  * "סגור לצמיתות"   → MainWindow.request_real_exit() (closeEvent then
                       accepts the close; main_qt's quit_app fires)

Why a clean win over pystray here:
  - QSystemTrayIcon lives on the Qt main thread; no separate daemon
    thread, no win32 cross-thread headaches.
  - 'Open' just un-hides the existing window. The Eel build had to
    spawn a fresh subprocess because Chrome --app windows can't be
    revived programmatically - that whole code path is gone.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtGui  import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

log = logging.getLogger(__name__)


def _icon_path() -> Path | None:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        p = Path(base) / "build_assets" / "app.ico"
        if p.exists():
            return p
    p = Path(__file__).resolve().parent.parent.parent / "build_assets" / "app.ico"
    return p if p.exists() else None


class Tray:
    """QSystemTrayIcon wrapper bound to a MainWindow.

    Caller owns the lifetime; this class only sets up the icon, menu, and
    activation handler. Hide via `tray.hide()` from the quit-handler so the
    icon disappears before QApplication.quit() returns.
    """

    def __init__(self,
                 app,
                 window,
                 tooltip: str = "Translation Manager") -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            log.warning("tray: system tray not available on this desktop")
        self._app = app
        self._window = window

        icon_p = _icon_path()
        icon = QIcon(str(icon_p)) if icon_p else QIcon()

        self._tray = QSystemTrayIcon(icon, app)
        self._tray.setToolTip(tooltip)

        menu = QMenu()
        a_open = QAction("פתח את התוכנה", menu)
        a_quit = QAction("סגור לצמיתות", menu)
        a_open.triggered.connect(self._on_open)
        a_quit.triggered.connect(self._on_quit)
        menu.addAction(a_open)
        menu.addSeparator()
        menu.addAction(a_quit)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_activated)
        self._tray.show()

    # ── Public ────────────────────────────────────────────────────
    def hide(self) -> None:
        try:
            self._tray.hide()
        except Exception:
            pass

    # ── Handlers ──────────────────────────────────────────────────
    def _on_activated(self, reason) -> None:
        # Single LEFT-click (Trigger) AND double-click both restore the
        # window — the affordance Windows users expect from any tray app.
        # Right-click (Context) still shows the menu via the default
        # context-menu handling, so we don't intercept it here.
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self._on_open()

    def _on_open(self) -> None:
        try:
            self._window.show_and_activate()
        except Exception:
            log.exception("tray: show_and_activate failed")

    def _on_quit(self) -> None:
        try:
            self._window.request_real_exit()
        except Exception:
            log.exception("tray: request_real_exit failed")
