# -*- coding: utf-8 -*-
"""The stage ring — the app's signature visual, ported from the Android build.

A full circle split into FOUR stages (pull → translate → check → send). A band
of light travels around it counter-clockwise (so the top reads right-to-left,
matching the rest of the UI), passing UNDER each stage node and re-emerging.
The active node pulses; finished ones show a check.

Why a ring rather than a progress bar: the work is a LOOP, not a line with an
end — a bar would keep filling and resetting, which reads as "restarting" every
cycle. A ring shows a cycle honestly, and the light stops moving the instant
the worker idles, so "is it actually doing anything" is answerable at a glance.

The whole thing is one QWidget.paintEvent, and the animation timer STOPS when
the worker is idle or when animations are turned down — an always-on repaint is
exactly the kind of background cost this app must not have on a volunteer's PC.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

STAGES = [
    ("משיכה",  "מקבל שורות מהמאגר"),
    ("תרגום",  "מתרגם עם המפתחות שלך"),
    ("בדיקה",  "בודק תקינות ומבנה"),
    ("שליחה",  "מחזיר את התוצאה"),
]
# one hue per stage, cyan → accent → purple, so the wave reads as a gradient run
STAGE_COLORS = ["#38bdf8", "#4ade80", "#fbbf24", "#c084fc"]

_SPAN = 360.0 / len(STAGES)


class StageRing(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(300, 300)
        self._t = 0.0
        self._stage = 0
        self._running = False
        self._anim = 1.0            # animation factor (0 = off)
        self._accent = "#4ade80"
        self._title = "כבוי"
        self._sub = "הפעילו כדי לתרום"
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    # ------------------------------------------------------------ control
    def set_accent(self, hexcolor: str) -> None:
        self._accent = hexcolor
        STAGE_COLORS[1] = hexcolor
        self.update()

    def set_anim(self, factor: float) -> None:
        self._anim = factor
        self._sync_timer()

    def set_text(self, title: str, sub: str) -> None:
        if (title, sub) != (self._title, self._sub):
            self._title, self._sub = title, sub
            self.update()

    def set_state(self, stage: int, running: bool) -> None:
        self._stage = max(0, min(len(STAGES) - 1, int(stage)))
        if running != self._running:
            self._running = running
            self._sync_timer()
        self.update()

    def _sync_timer(self) -> None:
        # never burn frames when there is nothing to show
        if self._running and self._anim > 0:
            if not self._timer.isActive():
                self._timer.start(33 if self._anim >= 1 else 66)
        else:
            self._timer.stop()
            self.update()

    def _tick(self) -> None:
        self._t = (self._t + 0.010 * max(0.35, self._anim)) % 1.0
        self.update()

    # ------------------------------------------------------------ paint
    def paintEvent(self, _ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        side = min(self.width(), self.height())
        cx, cy = self.width() / 2.0, self.height() / 2.0
        r = side / 2.0 - 26
        if r <= 10:
            return
        rect = QRectF(cx - r, cy - r, r * 2, r * 2)

        # 1. the track
        p.setPen(QPen(QColor(255, 255, 255, 26), 10, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawEllipse(rect)

        # 2. the stage arcs (dim), active one lit
        for i, col in enumerate(STAGE_COLORS):
            c = QColor(col)
            active = self._running and i == self._stage
            c.setAlpha(190 if active else 60)
            p.setPen(QPen(c, 10 if active else 7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            start = 90 - i * _SPAN - 4          # 90 = 12 o'clock; negative = clockwise
            p.drawArc(rect, int(start * 16), int(-(_SPAN - 8) * 16))

        # 3. the travelling light — drawn as many short overlapping arcs whose
        #    alpha follows a gaussian, which reads as ONE continuous ribbon.
        if self._running and self._anim > 0:
            base = QColor(STAGE_COLORS[self._stage])
            seg_start = 90 - self._stage * _SPAN
            head = (self._t * 1.6) % 1.0        # sweeps the active segment, wraps
            n = 26
            for k in range(n):
                f = k / (n - 1)
                d = abs(f - head)
                d = min(d, 1 - d)               # wrap-around distance
                a = math.exp(-(d * d) / 0.0055)
                if a < 0.03:
                    continue
                c = QColor(base)
                c.setAlpha(int(225 * a))
                p.setPen(QPen(c, 11, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                s = seg_start - f * (_SPAN - 8) - 4
                p.drawArc(rect, int(s * 16), int(-(_SPAN / n) * 16 * 1.6))

        # 4. the stage nodes — a dark disc MASKS the ring so the light passes
        #    underneath, then a coloured ring marks the continuation.
        for i, col in enumerate(STAGE_COLORS):
            ang = math.radians(90 - i * _SPAN)
            nx, ny = cx + r * math.cos(ang), cy - r * math.sin(ang)
            done = self._running and i < self._stage
            active = self._running and i == self._stage
            rad = 17 if active else 14

            p.setBrush(QColor(9, 12, 24))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(nx, ny), rad + 3, rad + 3)

            c = QColor(col)
            c.setAlpha(255 if (active or done) else 110)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(c, 3))
            p.drawEllipse(QPointF(nx, ny), rad, rad)

            p.setPen(QPen(c, 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            if done:
                path = QPainterPath()
                path.moveTo(nx - 5, ny)
                path.lineTo(nx - 1.5, ny + 4)
                path.lineTo(nx + 5.5, ny - 4)
                p.drawPath(path)
            else:
                p.setBrush(c if active else Qt.BrushStyle.NoBrush)
                p.drawEllipse(QPointF(nx, ny), 3.4, 3.4)

        # 5. the label of the active stage, just inside its node
        if self._running:
            ang = math.radians(90 - self._stage * _SPAN)
            lx, ly = cx + (r - 34) * math.cos(ang), cy - (r - 34) * math.sin(ang)
            f = QFont(self.font()); f.setPointSizeF(max(7.5, self.font().pointSizeF() - 1.5)); f.setBold(True)
            p.setFont(f)
            c = QColor(STAGE_COLORS[self._stage]); c.setAlpha(220)
            p.setPen(c)
            name = STAGES[self._stage][0]
            w = p.fontMetrics().horizontalAdvance(name)
            p.drawText(QPointF(lx - w / 2, ly), name)

        p.end()
