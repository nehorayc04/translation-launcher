# A pre-window, WebEngine-free branded loading splash.
#
# Shown the instant QApplication exists (BEFORE the network fetch and the heavy
# QtWebEngine MainWindow build), so a cold boot NEVER shows an empty window, and
# reused for the post-update boot. Pure QPainter (no QtWebEngine, no CSS blur).
#
# It is a SMALL floating card (not a full-window cover) centred on the window,
# painting the same content as the in-app splash used to: logo · "PROJECT
# TRANSLATION" · the gradient "מנהל התרגומים" · a shimmer bar. There is NO in-app
# React boot splash - this native card is the ONE loading surface, and it is
# dismissed by main_qt shortly after the page loads (a fixed grace), so it never
# lingers over an already-loaded app. It MUST be a separate top-level
# (Qt.SplashScreen | WindowStaysOnTop) - a child overlay would be drawn OVER by
# the QWebEngineView.
from __future__ import annotations
import logging
import sys
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QRectF, QElapsedTimer
from PySide6.QtGui import (QColor, QPainter, QPixmap, QPen, QBrush, QFont,
                           QLinearGradient, QRadialGradient, QPainterPath,
                           QGuiApplication)
from PySide6.QtWidgets import QWidget, QApplication

log = logging.getLogger(__name__)
_BG = QColor("#050510")            # THE one tone every surface shares
_CARD_W = 440
_CARD_H = 320


def _logo_pixmap() -> Optional[QPixmap]:
    base = getattr(sys, "_MEIPASS", None)
    root = Path(__file__).resolve().parent.parent.parent
    cands: list[Path] = []
    if base:
        cands += [Path(base) / "frontend" / "dist" / "app-logo.png",
                  Path(base) / "build_assets" / "app_512.png"]
    cands += [root / "frontend" / "dist" / "app-logo.png",
              root / "frontend" / "public" / "app-logo.png",
              root / "build_assets" / "app_512.png"]
    for c in cands:
        try:
            if c.exists():
                pm = QPixmap(str(c))
                if not pm.isNull():
                    return pm
        except Exception:
            pass
    return None


class NativeSplash(QWidget):
    """A small floating branded loading card (no WebEngine)."""

    def __init__(self, message: str = "") -> None:
        super().__init__(None, Qt.SplashScreen | Qt.FramelessWindowHint
                               | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)   # rounded card, no square bg
        self.resize(_CARD_W, _CARD_H)
        self._message = message
        self._logo = _logo_pixmap()
        self._t = QElapsedTimer()
        self._t.start()
        self._spin = QTimer(self)
        self._spin.setInterval(16)          # ~60fps (drives the shimmer bar)
        self._spin.timeout.connect(self.update)
        self._anim: Optional[QPropertyAnimation] = None
        self._dismissed = False

    # ── lifecycle ──────────────────────────────────────────────
    def _center_on(self, rect) -> None:
        if rect is None:
            return
        x = rect.x() + (rect.width() - _CARD_W) // 2
        y = rect.y() + (rect.height() - _CARD_H) // 2
        self.setGeometry(x, y, _CARD_W, _CARD_H)

    def show_over(self, rect=None) -> None:
        """Centre the card on `rect` (defaults to the primary screen) and FORCE
        the first frame to paint before the caller does any slow work."""
        if rect is None:
            scr = QGuiApplication.primaryScreen()
            rect = scr.geometry() if scr else None
        self._center_on(rect)
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self._spin.start()
        try:
            QApplication.processEvents()    # ← paints INSTANTLY, kills the pre-window gap
        except Exception:
            pass
        self._fade(0.0, 1.0, 180)

    def cover(self, window) -> None:
        """Re-centre the card over the MainWindow once it is shown."""
        try:
            self._center_on(window.frameGeometry())
            self.raise_()
        except Exception:
            pass

    def set_message(self, text: str) -> None:
        self._message = text or ""
        self.update()

    def dismiss(self, ms: int = 360, on_done: Optional[Callable] = None) -> None:
        if self._dismissed:
            return
        self._dismissed = True

        def _fin():
            try:
                self._spin.stop()
            except Exception:
                pass
            if on_done:
                try:
                    on_done()
                except Exception:
                    pass
            try:
                self.close()
            except Exception:
                pass
        self._fade(self.windowOpacity(), 0.0, ms, _fin)

    def _fade(self, a: float, b: float, ms: int, done=None) -> None:
        try:
            an = QPropertyAnimation(self, b"windowOpacity", self)
            an.setDuration(int(ms))
            an.setStartValue(float(a))
            an.setEndValue(float(b))
            if done:
                an.finished.connect(done)
            an.start()
            self._anim = an                 # keep a ref alive (else GC snaps the fade)
        except Exception:
            self.setWindowOpacity(b)
            if done:
                done()

    # ── painting (a small rounded card, centred content) ──
    def paintEvent(self, _e) -> None:       # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        w = float(self.width())
        h = float(self.height())
        cx = w / 2.0

        # rounded card body
        card = QRectF(1, 1, w - 2, h - 2)
        path = QPainterPath()
        path.addRoundedRect(card, 22, 22)
        p.setClipPath(path)
        p.fillRect(self.rect(), Qt.transparent)
        p.fillPath(path, QColor(5, 8, 22, 250))     # ~#050510, near-opaque

        # faint ambient glows (blue top-left, pink bottom-right)
        gt = QRadialGradient(cx - 40, 40, 220)
        gt.setColorAt(0.0, QColor(79, 139, 255, 46))
        gt.setColorAt(1.0, QColor(79, 139, 255, 0))
        p.fillPath(path, QBrush(gt))
        gb = QRadialGradient(cx + 90, h - 20, 220)
        gb.setColorAt(0.0, QColor(255, 59, 123, 40))
        gb.setColorAt(1.0, QColor(255, 59, 123, 0))
        p.fillPath(path, QBrush(gb))

        # subtle rim
        p.setPen(QPen(QColor(255, 255, 255, 26), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(card, 22, 22)

        # logo (96px), centred near the top third
        logo_cy = 96.0
        if self._logo is not None and not self._logo.isNull():
            side = 96
            pm = self._logo.scaled(side, side, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            p.drawPixmap(int(cx - pm.width() / 2), int(logo_cy - pm.height() / 2), pm)

        # eyebrow: "PROJECT TRANSLATION"
        eb = QFont()
        eb.setPixelSize(12)
        eb.setBold(True)
        eb.setLetterSpacing(QFont.AbsoluteSpacing, 4.0)
        p.setFont(eb)
        p.setPen(QColor("#9db4ff"))
        p.drawText(QRectF(0, logo_cy + 56, w, 20),
                   Qt.AlignHCenter | Qt.AlignVCenter, "PROJECT TRANSLATION")

        # title: "מנהל התרגומים" with the blue→purple→pink gradient
        title = QFont()
        title.setPixelSize(32)
        title.setBold(True)
        p.setFont(title)
        title_rect = QRectF(0, logo_cy + 80, w, 44)
        tg = QLinearGradient(cx - 110, 0, cx + 110, 0)
        tg.setColorAt(0.0, QColor("#4f8bff"))
        tg.setColorAt(0.5, QColor("#a855f7"))
        tg.setColorAt(1.0, QColor("#ff3b7b"))
        p.setPen(QPen(QBrush(tg), 1))
        p.drawText(title_rect, Qt.AlignHCenter | Qt.AlignVCenter, "מנהל התרגומים")

        # shimmer progress bar (200×6, moving gradient highlight)
        bw, bh = 200.0, 6.0
        bx = cx - bw / 2
        by = logo_cy + 140
        track = QRectF(bx, by, bw, bh)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 26))
        p.drawRoundedRect(track, bh / 2, bh / 2)
        hw = bw / 3.0
        frac = (self._t.elapsed() % 1400) / 1400.0
        hx = bx - hw + frac * (bw + hw)     # left: -1/3 → 100%
        p.save()
        clip = QPainterPath()
        clip.addRoundedRect(track, bh / 2, bh / 2)
        p.setClipPath(clip)
        hg = QLinearGradient(hx, 0, hx + hw, 0)
        hg.setColorAt(0.0, QColor("#4f8bff"))
        hg.setColorAt(0.5, QColor("#a855f7"))
        hg.setColorAt(1.0, QColor("#ff3b7b"))
        p.setBrush(QBrush(hg))
        p.drawRoundedRect(QRectF(hx, by, hw, bh), bh / 2, bh / 2)
        p.restore()

        p.end()
