"""
QDialog wrapper for the PayPal popup (and any future `target="_blank"`
flow originating inside the React app).

Shares the SAME QWebEngineProfile as the main window. Two consequences
matter:

  1. Supabase's localStorage / cookies are visible across both webviews,
     so the popup boots already-signed-in - no second login round-trip.
  2. PayPal's Smart-Buttons OAuth flow finishes inside the popup; the
     captured order id then flows back to the main window via PayPal's
     own postMessage transport (works because both pages share the same
     profile and we don't sandbox cross-origin storage).

The dialog is modal-style (non-modal Qt window, but always-on-top of the
parent main window). Closed via the OS close button OR programmatically
when the inner page navigates somewhere we treat as "checkout complete".
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QUrl, Qt
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QDialog, QVBoxLayout, QWidget

log = logging.getLogger(__name__)


class WebPopup(QDialog):
    """A bare-chrome QDialog that hosts a QWebEngineView. Used for
    PayPal Smart Buttons and any other in-flow popup the React app opens
    via window.open / target="_blank"."""

    def __init__(self,
                 profile: QWebEngineProfile,
                 parent: QWidget | None = None,
                 size: tuple[int, int] = (480, 700)) -> None:
        super().__init__(parent)
        self.setWindowTitle("")  # PayPal sets its own title on first paint
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.resize(*size)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.view = QWebEngineView(self)
        self.page = QWebEnginePage(profile, self.view)
        self.view.setPage(self.page)
        layout.addWidget(self.view)

        # The popup may itself trigger another popup (rare, PayPal can do
        # this for 3DS challenges). Recurse: spawn another WebPopup.
        self.page.newWindowRequested.connect(self._on_new_window)

        # PayPal's Smart Buttons SDK calls window.close() on the popup
        # page once the user completes/cancels approval. In a real
        # browser the popup window auto-closes; in Qt the JS call fires
        # the page's windowCloseRequested signal but nothing reacts to
        # it by default - the dialog stays open showing "תודה
        # שהשתמשת ב-PayPal" forever. Wire it to self.close() so the
        # popup vanishes the moment the embedded page asks.
        self.page.windowCloseRequested.connect(self.close)

    def navigate(self, url: str) -> None:
        self.view.setUrl(QUrl(url))

    def _on_new_window(self, request) -> None:
        try:
            child = WebPopup(self.page.profile(), parent=self)
            child.show()
            request.openIn(child.page)
        except Exception:
            log.exception("popup: failed to open nested window")
