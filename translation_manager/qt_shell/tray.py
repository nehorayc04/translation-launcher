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

        # Custom-title-bar toggle - a SAFETY NET: if the frameless window ever
        # breaks (can't move/close), this reverts to the native Windows frame
        # from the tray (which works regardless of the window's own state).
        self._a_tb = QAction("פס כותרת מותאם", menu)
        self._a_tb.setCheckable(True)
        try:
            from .. import launcher_prefs
            self._a_tb.setChecked(bool(launcher_prefs.get_custom_titlebar()))
        except Exception:
            self._a_tb.setChecked(False)
        self._a_tb.triggered.connect(self._on_toggle_titlebar)
        menu.addAction(self._a_tb)
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
        # window - the affordance Windows users expect from any tray app.
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

    def _on_toggle_titlebar(self, checked: bool) -> None:
        """Toggle the custom frameless title bar (takes effect next launch).
        Reachable even when the window itself is unusable → the guaranteed
        way out of a broken frameless window."""
        try:
            from .. import launcher_prefs
            launcher_prefs.set_custom_titlebar(bool(checked))
            self._tray.showMessage(
                "פס כותרת",
                ("פס הכותרת המותאם יופעל בהפעלה הבאה." if checked
                 else "פס הכותרת של Windows יחזור בהפעלה הבאה."),
                QSystemTrayIcon.MessageIcon.Information, 6000,
            )
        except Exception:
            log.exception("tray: toggle titlebar failed")
