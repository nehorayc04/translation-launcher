# -*- coding: utf-8 -*-
"""The big central ON/OFF switch — a glass pill with a glowing neon thumb,
animated with the same spring curve as the launcher's controls."""
from __future__ import annotations

from PySide6.QtCore import (QEasingCurve, QRectF, Qt, QVariantAnimation, Signal)
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

import ui


class BigToggle(QWidget):
    toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._on = False
        self._pos = 0.0                       # 0=off .. 1=on (animated)
        self.setFixedSize(300, 132)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_on(self, on: bool, animate: bool = True) -> None:
        if on == self._on and animate:
            return
        self._on = on
        target = 1.0 if on else 0.0
        if not animate:
            self._pos = target
            self.update()
            return
        a = QVariantAnimation(self)
        a.setDuration(420)
        a.setEasingCurve(QEasingCurve.Type.OutBack)
        a.setStartValue(self._pos)
        a.setEndValue(target)
        a.valueChanged.connect(self._set_pos)
        self._anim = a
        a.start()

    def is_on(self) -> bool:
        return self._on

    def _set_pos(self, v):
        self._pos = float(v)
        self.update()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.set_on(not self._on)
            self.toggled.emit(self._on)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        track = QRectF(6, 30, w - 12, h - 60)      # the pill
        r = track.height() / 2
        acc = QColor(ui.GREEN if self._on else "#5b6480")

        # outward glow when on
        if self._pos > 0.02:
            for grow, alpha in ((22, 10), (13, 18), (6, 30)):
                c = QColor(ui.GREEN); c.setAlpha(int(alpha * self._pos))
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(c)
                p.drawRoundedRect(track.adjusted(-grow, -grow, grow, grow), r + grow, r + grow)

        # glass track
        path = QPainterPath(); path.addRoundedRect(track, r, r)
        base = QColor(12, 12, 26, 220)
        p.fillPath(path, base)
        fill = QColor(ui.GREEN); fill.setAlpha(int(60 * self._pos))
        p.fillPath(path, fill)
        p.setPen(QColor(255, 255, 255, 26)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(track, r, r)

        # sliding thumb (RTL: OFF on the right, slides LEFT to ON)
        d = track.height() - 12
        x_off = track.right() - d - 6
        x_on = track.left() + 6
        x = x_off + (x_on - x_off) * self._pos
        thumb = QRectF(x, track.top() + 6, d, d)
        for grow, alpha in ((10, int(70 * self._pos + 10)), (5, int(90 * self._pos + 20))):
            c = QColor(acc); c.setAlpha(alpha)
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(c)
            p.drawEllipse(thumb.adjusted(-grow, -grow, grow, grow))
        g = QLinearGradient(thumb.topLeft(), thumb.bottomLeft())
        g.setColorAt(0.0, QColor(255, 255, 255, 250))
        g.setColorAt(1.0, acc.lighter(150))
        p.setBrush(g); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(thumb)
        # power glyph on the thumb
        p.setPen(Qt.PenStyle.NoPen)
        cx, cy = thumb.center().x(), thumb.center().y()
        rr = d * 0.24
        p.setPen(QPen(QColor(acc if self._on else "#3a3f57"), 3, cap=Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(QRectF(cx - rr, cy - rr + 1, 2 * rr, 2 * rr), 60 * 16, 240 * 16)
        p.drawLine(int(cx), int(cy - rr - 2), int(cx), int(cy + 1))

        # state text
        p.setPen(QColor(ui.TEXT if self._on else ui.MUTED))
        f = self.font(); f.setPointSizeF(15); f.setBold(True); p.setFont(f)
        p.drawText(QRectF(0, h - 26, w, 24), Qt.AlignmentFlag.AlignCenter,
                   "פעיל" if self._on else "כבוי")
