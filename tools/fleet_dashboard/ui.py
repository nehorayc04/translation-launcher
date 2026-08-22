# -*- coding: utf-8 -*-
"""The launcher's design system, ported to Qt widgets.

Every value here is lifted from the launcher's own `frontend/src/index.css` +
`tailwind.config.js` rather than re-invented, so the two apps read as one family:

    canvas            #050510            text #f0f0ff        font Heebo (bundled TTFs)
    brand             yellow #fff700 · cyan #00ffe0 · ink #0a0a14
    .glass            rgba(12,12,26,0.82) + 1px rgba(255,255,255,0.08)
    .sidebar-glass    rgba(10,10,22,0.94), edge as an INSET highlight — never a border, so the
                      72↔230 width animation shows no 1px white seam (a real bug they hit)
    rail              72 ↔ 230 px, width .46s cubic-bezier(.34,1.35,.5,1)
    nav indicator     accent-tinted pill + a 4px rounded glowing edge bar, top/height .44s, same curve
    view transition   .5s cubic-bezier(.34,1.3,.5,1): opacity 0→1, y 18→-4→0, scale .976→1.008→1
    stagger           rise .5s, 40ms per child

Two things CSS does and QSS does not — glow and blur — are painted or delegated instead:
glows are drawn with QPainter, and the frosted blur is the REAL Windows DWM backdrop
(acrylic/mica), which is better than the launcher can get inside QtWebEngine.
"""
from __future__ import annotations

import ctypes
import os
import sys

from PySide6.QtCore import (QEasingCurve, QPropertyAnimation, QRect, QSize, Qt, QTimer,
                            QVariantAnimation, Signal)
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QLinearGradient, QPainter, QPainterPath,
                           QPen, QRadialGradient)
from PySide6.QtWidgets import (QCheckBox, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel,
                               QPushButton, QSizePolicy, QSlider, QVBoxLayout, QWidget)

# ---------------------------------------------------------------- tokens

CANVAS = "#050510"
INK = "#0a0a14"
TEXT = "#f0f0ff"
MUTED = "#8b93b0"
YELLOW = "#fff700"
CYAN = "#00ffe0"
RED = "#ff5c5c"
AMBER = "#ffb020"
GREEN = "#3fe08a"
BLUE = "#5dade2"

EASE_SPRING = QEasingCurve.Type.OutBack          # ≈ cubic-bezier(.34,1.35,.5,1)
EASE_SOFT = QEasingCurve.Type.OutCubic

RAIL_NARROW, RAIL_WIDE = 72, 230


def _mix(hex_color: str, alpha: float) -> str:
    c = QColor(hex_color)
    return f"rgba({c.red()},{c.green()},{c.blue()},{alpha:.3f})"


def load_fonts() -> str:
    """Register the bundled Heebo TTFs — the launcher's exact typeface, not a lookalike."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    fam = ""
    for name in ("Heebo-Regular.ttf", "Heebo-Medium.ttf", "Heebo-Bold.ttf", "Heebo-Black.ttf"):
        p = os.path.join(base, "fonts", name)
        if os.path.exists(p):
            fid = QFontDatabase.addApplicationFont(p)
            fams = QFontDatabase.applicationFontFamilies(fid)
            if fams:
                fam = fams[0]
    return fam or "Segoe UI"


def qss(accent: str, backdrop: str, base_pt: float) -> str:
    """One stylesheet for the whole app. `backdrop` decides how transparent the surfaces are:
    with a real DWM blur behind the window they can be light; with none they must be solid."""
    glassy = backdrop != "none"
    panel = _mix("#0c0c1a", 0.55 if glassy else 0.94)
    panel_soft = _mix("#0e0e1c", 0.38 if glassy else 0.80)
    rail = _mix("#0a0a16", 0.66 if glassy else 0.97)
    line = "rgba(255,255,255,0.08)"
    return f"""
    QWidget {{ color: {TEXT}; font-size: {base_pt:.1f}pt; }}
    #root {{ background: transparent; }}
    #panel {{ background: {panel}; border: 1px solid {line}; border-radius: 18px; }}
    #panelSoft {{ background: {panel_soft}; border: 1px solid rgba(255,255,255,0.06);
                  border-radius: 16px; }}
    #rail {{ background: {rail}; border: 0; border-radius: 20px; }}
    #cap {{ color: {MUTED}; font-weight: 600; }}
    #big {{ font-size: {base_pt * 2.0:.1f}pt; font-weight: 800; }}
    #h1 {{ font-size: {base_pt * 1.35:.1f}pt; font-weight: 700; }}
    QLabel[muted="1"] {{ color: {MUTED}; }}
    QPushButton {{ background: rgba(255,255,255,0.045); border: 1px solid {line};
                   border-radius: 11px; padding: 7px 14px; color: {TEXT}; }}
    QPushButton:hover {{ background: rgba(255,255,255,0.09);
                         border-color: {_mix(accent, 0.45)}; }}
    QPushButton:pressed {{ background: {_mix(accent, 0.16)}; }}
    QPushButton[flat="1"] {{ background: transparent; border: 0; padding: 4px; }}
    QPushButton[flat="1"]:hover {{ background: rgba(255,255,255,0.07); }}
    QTableWidget {{ background: transparent; border: 0; gridline-color: rgba(255,255,255,0.05);
                    selection-background-color: {_mix(accent, 0.18)}; }}
    QHeaderView::section {{ background: transparent; color: {MUTED}; border: 0;
                            border-bottom: 1px solid {line}; padding: 7px 6px;
                            font-weight: 600; }}
    QTableWidget::item {{ padding: 5px 6px; border-bottom: 1px solid rgba(255,255,255,0.035); }}
    QTextBrowser {{ background: transparent; border: 0; }}
    QScrollBar:vertical {{ background: transparent; width: 9px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: rgba(255,255,255,0.10); border-radius: 5px;
                                   min-height: 30px; }}
    QScrollBar::handle:vertical:hover {{ background: {_mix(accent, 0.45)}; }}
    QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page
        {{ background: transparent; height: 0; width: 0; }}
    QScrollBar:horizontal {{ background: transparent; height: 9px; margin: 2px; }}
    QScrollBar::handle:horizontal {{ background: rgba(255,255,255,0.10); border-radius: 5px;
                                     min-width: 30px; }}
    QCheckBox {{ color: {TEXT}; spacing: 8px; }}
    QCheckBox::indicator {{ width: 17px; height: 17px; border-radius: 5px;
                            border: 1px solid rgba(255,255,255,0.22);
                            background: rgba(255,255,255,0.04); }}
    QCheckBox::indicator:checked {{ background: {accent}; border-color: {accent}; }}
    QSlider::groove:horizontal {{ height: 4px; background: rgba(255,255,255,0.12);
                                  border-radius: 2px; }}
    QSlider::sub-page:horizontal {{ background: {accent}; border-radius: 2px; }}
    QSlider::handle:horizontal {{ width: 15px; height: 15px; margin: -6px 0; border-radius: 8px;
                                  background: #fff; border: 2px solid {accent}; }}
    QToolTip {{ background: {INK}; color: {TEXT}; border: 1px solid {line}; padding: 6px; }}
    """


# ---------------------------------------------------------------- Windows glass

def apply_window_effects(widget: QWidget, backdrop: str) -> bool:
    """Rounded corners + the REAL system backdrop (the thing CSS could not give the launcher).

    DWMWA_USE_IMMERSIVE_DARK_MODE(20) so the frame is dark, WINDOW_CORNER_PREFERENCE(33)=ROUND,
    SYSTEMBACKDROP_TYPE(38): 2=Mica, 3=Acrylic, 4=Tabbed. Returns True when a blur was applied, so
    the caller knows whether its surfaces may be translucent.
    """
    try:
        hwnd = int(widget.winId())
        dwm = ctypes.windll.dwmapi
        val = ctypes.c_int(1)
        dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(val), 4)          # dark frame
        val = ctypes.c_int(2)
        dwm.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(val), 4)          # rounded corners
        kind = {"mica": 2, "acrylic": 3, "glass": 3, "none": 1}.get(backdrop, 3)
        val = ctypes.c_int(kind)
        rc = dwm.DwmSetWindowAttribute(hwnd, 38, ctypes.byref(val), 4)
        return rc == 0 and kind != 1
    except Exception:
        return False


# ---------------------------------------------------------------- animation helpers

def _fade(widget: QWidget, factor: float, ms: int = 420, delay: int = 0) -> None:
    """Fade a widget in through a graphics effect.

    Opacity is safe inside a layout; `pos` is NOT. Animating pos on a layout-managed widget makes
    the layout re-place it mid-flight — that is what made two cards overlap and one of them vanish.
    """
    if factor <= 0:
        return
    eff = widget.graphicsEffect()
    if not isinstance(eff, QGraphicsOpacityEffect):
        eff = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(eff)
    eff.setOpacity(0.0)
    a = QPropertyAnimation(eff, b"opacity", widget)
    a.setDuration(max(1, int(ms * factor)))
    a.setStartValue(0.0)
    a.setEndValue(1.0)
    a.setEasingCurve(EASE_SOFT)
    widget._fade_anim = a
    if delay:
        QTimer.singleShot(delay, a.start)
    else:
        a.start()


def view_in(widget: QWidget, factor: float) -> None:
    """The launcher's view transition: fade + a real RISE, done layout-safely — the rise is the
    layout's own top margin relaxing 18px -> 0, so no geometry is contested."""
    if factor <= 0:
        return
    _fade(widget, factor, 430)
    lay = widget.layout()
    if lay is None:
        return
    m = lay.contentsMargins()
    a = QVariantAnimation(widget)
    a.setDuration(int(480 * factor))
    a.setStartValue(m.top() + 18)
    a.setEndValue(m.top())
    a.setEasingCurve(EASE_SPRING)
    a.valueChanged.connect(
        lambda v: lay.setContentsMargins(m.left(), max(0, int(v)), m.right(), m.bottom()))
    widget._rise_anim = a
    a.start()


def stagger_in(widgets: list[QWidget], factor: float) -> None:
    """The launcher's `.stagger`: the same fade 40 ms apart, so a screen assembles instead of
    snapping. Touches no geometry, so it is safe in any layout."""
    if factor <= 0:
        return
    for i, w in enumerate(widgets):
        _fade(w, factor, 460, delay=int(i * 40 * factor))


# ---------------------------------------------------------------- surfaces

class Panel(QFrame):
    """A .glass panel. `glow` paints the accent bloom the launcher gets from box-shadow."""

    def __init__(self, parent=None, soft=False, glow: str | None = None):
        super().__init__(parent)
        self.setObjectName("panelSoft" if soft else "panel")
        self._glow = glow

    def set_glow(self, color: str | None):
        self._glow = color
        self.update()

    def paintEvent(self, ev):
        super().paintEvent(ev)
        if not self._glow:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QColor(self._glow)
        for corner, cx, cy in (("tr", self.width(), 0), ("bl", 0, self.height())):
            g = QRadialGradient(cx, cy, max(140, self.width() * 0.5))
            c2 = QColor(c)
            c2.setAlpha(46 if corner == "tr" else 26)
            g.setColorAt(0.0, c2)
            c3 = QColor(c)
            c3.setAlpha(0)
            g.setColorAt(1.0, c3)
            path = QPainterPath()
            path.addRoundedRect(0, 0, self.width(), self.height(), 18, 18)
            p.setClipPath(path)
            p.fillPath(path, g)


class Ambient(QWidget):
    """The launcher's per-accent ambient background: two STATIC soft radial blobs (no blur filter,
    no infinite animation — that combination is what made the launcher feel slow)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._accent = CYAN
        self._solid = False

    def configure(self, accent: str, solid: bool):
        self._accent, self._solid = accent, solid
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._solid:
            p.fillRect(self.rect(), QColor(CANVAS))
        else:
            p.fillRect(self.rect(), QColor(5, 5, 16, 205))
        w, h = self.width(), self.height()
        for (cx, cy, r, a) in ((w * 0.94, -h * 0.10, max(w, h) * 0.62, 108),
                               (w * 0.06, h * 1.10, max(w, h) * 0.55, 82)):
            g = QRadialGradient(cx, cy, r)
            c = QColor(self._accent)
            c.setAlpha(a)
            g.setColorAt(0.0, c)
            c0 = QColor(self._accent)
            c0.setAlpha(0)
            g.setColorAt(1.0, c0)
            p.fillRect(self.rect(), g)


# ---------------------------------------------------------------- title bar

class TitleBar(QWidget):
    """Frameless bar: an empty drag region + glyph-only controls that recolor and glow on hover,
    with NO square hover box — exactly the launcher's redesign."""

    def __init__(self, win: QWidget, title: str):
        super().__init__(win)
        self.win = win
        self.setFixedHeight(38)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 4, 8, 4)
        lay.setSpacing(2)
        self.caption = QLabel(title)
        self.caption.setProperty("muted", "1")
        lay.addWidget(self.caption)
        lay.addStretch(1)
        for glyph, tip, col, slot in (("—", "מזער", CYAN, self._min),
                                      ("▢", "הגדל", YELLOW, self._max),
                                      ("✕", "סגור", RED, win.close)):
            b = QPushButton(glyph)
            b.setProperty("flat", "1")
            b.setToolTip(tip)
            b.setFixedSize(34, 26)
            b.setCursor(Qt.CursorShape.ArrowCursor)
            b.setStyleSheet(f"QPushButton{{background:transparent;border:0;color:{MUTED};"
                            f"font-size:12pt;}}QPushButton:hover{{color:{col};background:transparent;}}")
            b.clicked.connect(slot)
            lay.addWidget(b)

    def _min(self):
        self.win.showMinimized()

    def _max(self):
        self.win.showNormal() if self.win.isMaximized() else self.win.showMaximized()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            h = self.win.windowHandle()
            if h:
                h.startSystemMove()

    def mouseDoubleClickEvent(self, ev):
        self._max()


# ---------------------------------------------------------------- nav rail

class NavRail(QWidget):
    """72↔230 rail with the travelling glowing indicator.

    The indicator is one child widget whose geometry is animated with the spring curve, and it
    PAINTS what CSS did with box-shadow: an accent-tinted body, a top sheen, a 4 px rounded edge bar
    on the right (RTL) and an outward bloom. The rail's edge is an inset highlight, not a border, so
    the width animation never shows a 1 px seam.
    """

    changed = Signal(str)

    def __init__(self, items: list[tuple[str, str, str, str]], parent=None):
        super().__init__(parent)
        self.setObjectName("rail")
        self.items = items
        self.current = items[0][0]
        self._factor = 1.0
        self._mode = "auto"
        self._expanded = False
        self.setFixedWidth(RAIL_NARROW)
        self.setMouseTracking(True)

        self.ind = QWidget(self)
        self.ind.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.ind.paintEvent = self._paint_indicator                      # type: ignore[assignment]

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 12, 10, 12)
        lay.setSpacing(6)

        self.brand = QLabel("צי")
        self.brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.brand.setFixedHeight(44)
        self.brand.setStyleSheet(
            f"font-size:13pt;font-weight:800;color:{INK};border-radius:14px;"
            f"background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {YELLOW},stop:1 {CYAN});")
        lay.addWidget(self.brand)
        lay.addSpacing(6)

        self.buttons: dict[str, QPushButton] = {}
        for key, label, accent, glyph in items:
            b = QPushButton(glyph)
            b.setProperty("flat", "1")
            b.setFixedHeight(46)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setToolTip(label)
            b.clicked.connect(lambda _=False, k=key: self.select(k))
            b.setObjectName("railBtn")
            b.setStyleSheet(self._btn_qss(accent, False))
            lay.addWidget(b)
            self.buttons[key] = b
        lay.addStretch(1)
        self.hint = QLabel("")
        self.hint.setProperty("muted", "1")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.hint)
        QTimer.singleShot(0, lambda: self._move_indicator(False))

    # -------- appearance
    def _btn_qss(self, accent: str, active: bool) -> str:
        col = accent if active else "#c9d1e4"
        align = "right" if self._expanded else "center"
        pad = "padding-right:16px;" if self._expanded else ""
        return (f"QPushButton{{background:transparent;border:0;text-align:{align};{pad}"
                f"color:{col};font-size:13pt;font-weight:{'700' if active else '500'};}}"
                f"QPushButton:hover{{color:{accent};background:transparent;}}")

    def set_factor(self, f: float):
        self._factor = f

    def set_mode(self, mode: str):
        self._mode = mode
        self._apply_width(mode == "wide", animate=False)

    def accent_of(self, key: str) -> str:
        for it in self.items:
            if it[0] == key:
                return it[2]
        return CYAN

    def _paint_indicator(self, _ev):
        w, h = self.ind.width(), self.ind.height()
        if w <= 0 or h <= 0:
            return
        acc = QColor(self.accent_of(self.current))
        p = QPainter(self.ind)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # outward bloom (box-shadow 0 0 26px -12px accent)
        for i, alpha in ((7, 12), (4, 20), (2, 30)):
            c = QColor(acc)
            c.setAlpha(alpha)
            p.setPen(QPen(c, 2))
            p.drawRoundedRect(QRect(i, i, w - 2 * i, h - 2 * i), 13, 13)
        body = QPainterPath()
        body.addRoundedRect(0, 0, w, h, 13, 13)
        fill = QColor(acc)
        fill.setAlpha(46)
        p.fillPath(body, fill)
        sheen = QLinearGradient(0, 0, 0, h * 0.48)
        sheen.setColorAt(0.0, QColor(255, 255, 255, 34))
        sheen.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setClipPath(body)
        p.fillRect(QRect(0, 0, w, int(h * 0.48)), sheen)
        p.setClipping(False)
        # the 4px rounded edge bar (RTL: on the right), plus its own glow
        bar = QRect(w - 5, 10, 4, max(6, h - 20))
        for grow, alpha in ((6, 26), (3, 48)):
            c = QColor(acc)
            c.setAlpha(alpha)
            p.setBrush(c)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(bar.adjusted(-grow, -grow // 2, grow, grow // 2), 6, 6)
        p.setBrush(acc)
        p.drawRoundedRect(bar, 2, 2)

    def _move_indicator(self, animate=True):
        b = self.buttons.get(self.current)
        if not b:
            return
        target = QRect(6, b.y(), self.width() - 12, b.height())
        if not animate or self._factor <= 0:
            self.ind.setGeometry(target)
        else:
            a = QPropertyAnimation(self.ind, b"geometry", self)
            a.setDuration(int(440 * self._factor))
            a.setEasingCurve(EASE_SPRING)
            a.setStartValue(self.ind.geometry())
            a.setEndValue(target)
            self._ind_anim = a
            a.start()
        self.ind.lower()
        self.ind.show()
        self.ind.update()

    def select(self, key: str):
        if key == self.current:
            return
        for it in self.items:
            self.buttons[it[0]].setStyleSheet(self._btn_qss(it[2], it[0] == key))
        self.current = key
        self._move_indicator(True)
        self.changed.emit(key)

    def set_current_silent(self, key: str):
        for it in self.items:
            self.buttons[it[0]].setStyleSheet(self._btn_qss(it[2], it[0] == key))
        self.current = key
        self._move_indicator(False)

    # -------- width behaviour (hover-expand in "auto", like the launcher)
    def _apply_width(self, expand: bool, animate=True):
        if self._expanded == expand and animate:
            return
        self._expanded = expand
        target = RAIL_WIDE if expand else RAIL_NARROW
        for key, label, _a, glyph in self.items:
            self.buttons[key].setText(f"{glyph}   {label}" if expand else glyph)
        self.brand.setText("צי התרגום" if expand else "צי")
        for it in self.items:                       # alignment follows the mode
            self.buttons[it[0]].setStyleSheet(self._btn_qss(it[2], it[0] == self.current))
        self.hint.setText("Fleet Dashboard" if expand else "")
        if not animate or self._factor <= 0:
            self.setFixedWidth(target)
            QTimer.singleShot(0, lambda: self._move_indicator(False))
            return
        a = QPropertyAnimation(self, b"minimumWidth", self)
        a2 = QPropertyAnimation(self, b"maximumWidth", self)
        for an in (a, a2):
            an.setDuration(int(460 * self._factor))
            an.setEasingCurve(EASE_SPRING)
            an.setStartValue(self.width())
            an.setEndValue(target)
        self._w_anims = (a, a2)
        a.start()
        a2.start()
        QTimer.singleShot(int(470 * self._factor), lambda: self._move_indicator(False))

    def enterEvent(self, ev):
        if self._mode == "auto":
            self._apply_width(True)

    def leaveEvent(self, ev):
        if self._mode == "auto":
            self._apply_width(False)

    def paintEvent(self, ev):
        """The .sidebar-glass edge: an INSET highlight, never a border — a border would show a 1px
        white seam while the width animates (the exact bug the launcher's CSS comment warns about)."""
        super().paintEvent(ev)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(255, 255, 255, 26), 1))
        p.drawRoundedRect(QRect(0, 0, self.width() - 1, self.height() - 1), 20, 20)
        p.setPen(QPen(QColor(255, 255, 255, 10), 1))
        p.drawRoundedRect(QRect(1, 1, self.width() - 3, self.height() - 3), 19, 19)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._move_indicator(False)


# ---------------------------------------------------------------- segmented control

class Segmented(QWidget):
    """The launcher's SegmentedControl: one glass row, and the active option is a GLOWING thumb that
    slides with the same spring curve as the menu indicator."""

    changed = Signal(str)

    def __init__(self, options: list[tuple[str, str]], value: str, accent: str = CYAN, parent=None):
        super().__init__(parent)
        self.options = options
        self.value = value
        self.accent = accent
        self._factor = 1.0
        self.setFixedHeight(38)
        # compact, like the launcher's picker — a stretched 4-option bar reads as a toolbar
        self.setMaximumWidth(112 * max(2, len(options)))
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.setStyleSheet("background: rgba(255,255,255,0.05); border-radius: 19px;"
                           "border: 1px solid rgba(255,255,255,0.10);")
        self.thumb = QWidget(self)
        self.thumb.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.thumb.paintEvent = self._paint_thumb                        # type: ignore[assignment]
        lay = QHBoxLayout(self)
        lay.setContentsMargins(5, 5, 5, 5)
        lay.setSpacing(2)
        self.btns: dict[str, QPushButton] = {}
        for key, label in options:
            b = QPushButton(label)
            b.setProperty("flat", "1")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self.set_value(k, True))
            lay.addWidget(b, 1)
            self.btns[key] = b
        self._restyle()
        QTimer.singleShot(0, lambda: self._move(False))

    def set_factor(self, f: float):
        self._factor = f

    def _restyle(self):
        for k, b in self.btns.items():
            on = k == self.value
            b.setStyleSheet(f"QPushButton{{background:transparent;border:0;padding:2px 8px;"
                            f"color:{'#ffffff' if on else MUTED};font-weight:{'700' if on else '500'};}}"
                            f"QPushButton:hover{{color:#ffffff;background:transparent;}}")

    def _paint_thumb(self, _ev):
        w, h = self.thumb.width(), self.thumb.height()
        if w <= 0:
            return
        acc = QColor(self.accent)
        p = QPainter(self.thumb)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        for grow, alpha in ((6, 18), (3, 34)):
            c = QColor(acc)
            c.setAlpha(alpha)
            p.setBrush(c)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRect(-grow, -grow, w + 2 * grow, h + 2 * grow), h / 2, h / 2)
        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, h / 2, h / 2)
        f = QColor(acc)
        f.setAlpha(52)
        p.fillPath(path, f)
        g = QLinearGradient(0, 0, 0, h)
        g.setColorAt(0.0, QColor(255, 255, 255, 28))
        g.setColorAt(1.0, QColor(255, 255, 255, 5))
        p.fillPath(path, g)

    def _move(self, animate=True):
        b = self.btns.get(self.value)
        if not b:
            return
        target = QRect(b.x(), 5, b.width(), self.height() - 10)
        if not animate or self._factor <= 0:
            self.thumb.setGeometry(target)
        else:
            a = QPropertyAnimation(self.thumb, b"geometry", self)
            a.setDuration(int(440 * self._factor))
            a.setEasingCurve(EASE_SPRING)
            a.setStartValue(self.thumb.geometry())
            a.setEndValue(target)
            self._a = a
            a.start()
        self.thumb.lower()
        self.thumb.show()
        self.thumb.update()

    def set_value(self, key: str, emit=False):
        if key not in self.btns:
            return
        self.value = key
        self._restyle()
        self._move(True)
        if emit:
            self.changed.emit(key)

    def set_accent(self, accent: str):
        self.accent = accent
        self.thumb.update()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._move(False)


# ---------------------------------------------------------------- small helpers

def caption(text: str) -> QLabel:
    lb = QLabel(text)
    lb.setObjectName("cap")
    return lb


def row(*widgets, spacing=10, margins=(0, 0, 0, 0)) -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(*margins)
    lay.setSpacing(spacing)
    for x in widgets:
        if x is None:
            lay.addStretch(1)
        elif isinstance(x, QWidget):
            lay.addWidget(x)
        else:
            lay.addWidget(QLabel(str(x)))
    return w


def setting_row(label: str, control: QWidget, hint: str = "") -> QWidget:
    box = Panel(soft=True)
    lay = QVBoxLayout(box)
    lay.setContentsMargins(14, 11, 14, 11)
    lay.setSpacing(7)
    head = QLabel(label)
    head.setStyleSheet("font-weight:600;")
    lay.addWidget(head)
    if hint:
        h = QLabel(hint)
        h.setProperty("muted", "1")
        h.setWordWrap(True)
        lay.addWidget(h)
    lay.addWidget(control)
    return box


def slider_row(minimum: int, maximum: int, step: int, value: int) -> QSlider:
    s = QSlider(Qt.Orientation.Horizontal)
    s.setMinimum(minimum)
    s.setMaximum(maximum)
    s.setSingleStep(step)
    s.setPageStep(step)
    s.setValue(value)
    s.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return s


def checkbox(label: str, checked: bool) -> QCheckBox:
    c = QCheckBox(label)
    c.setChecked(bool(checked))
    return c


def swatch(color: str, active: bool) -> QPushButton:
    b = QPushButton()
    b.setFixedSize(QSize(30, 30))
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setStyleSheet(
        f"QPushButton{{background:{color};border-radius:15px;"
        f"border:{'3px solid #ffffff' if active else '1px solid rgba(255,255,255,0.25)'};}}")
    return b
