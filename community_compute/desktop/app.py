# -*- coding: utf-8 -*-
"""Community Compute — desktop volunteer worker.

Same design language as the Translation-Hub launcher (ui.py IS the launcher's
design system ported to Qt): frameless glass window, ambient background, nav
rail, segmented controls, staggered entrances. A big central ON/OFF switch
inside a live stage-ring drives a resilient pull-loop that translates community
lines with the volunteer's OWN free API keys. Keys are encrypted on the device
and NEVER transmitted; a network drop does not stop work (it buffers locally and
syncs on reconnect).

v1.0.2 brings the desktop up to the Android build's design + fixes what was
genuinely broken (see engine.py — every finished translation was being thrown
away, and the heartbeat was never sent).
"""
from __future__ import annotations

import os
import sys

from PySide6.QtCore import QEasingCurve, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QFont, QGuiApplication, QIcon
from PySide6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
                               QMessageBox, QPushButton, QStackedWidget, QSystemTrayIcon,
                               QVBoxLayout, QWidget)

import ui
ui.BRAND_SHORT = "קהילה"
ui.BRAND_WIDE = "מחשוב קהילתי"

import client
import keystore
import providers
import single
from bigtoggle import BigToggle
from config import APP_NAME, APP_VERSION, CC_BASE, PROVIDERS
from engine import Engine
from stagering import StageRing
from state import State

ACCENTS = {
    "green":  ui.GREEN,
    "cyan":   ui.CYAN,
    "yellow": ui.YELLOW,
    "purple": "#c084fc",
    "pink":   "#f472b6",
    "amber":  "#fb923c",
}
ANIM_FACTOR = {"full": 1.0, "normal": 0.75, "reduced": 0.35, "off": 0.0}

# rotated so a long quiet stretch never looks frozen
PHRASES = {
    0: ["מבקש שורות חדשות מהמאגר", "מושך את המנה הבאה", "בודק אם יש עבודה"],
    1: ["מתרגם עם המפתחות שלך", "שולח לספקים שהגדרת", "עובד על המנה"],
    2: ["בודק תקינות ומבנה", "מוודא שהקודים נשמרו", "בדיקת איכות מקומית"],
    3: ["שולח את התוצאה", "מעדכן את המאגר", "מסיים את המנה"],
}


def _set_autostart(on: bool) -> None:
    """Enforce 'run at login' via the HKCU Run key (reversible, no admin).
    Only meaningful for the frozen EXE; a no-op in a dev run."""
    exe = sys.executable if getattr(sys, "frozen", False) else None
    if not exe:
        return
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Run",
                            0, winreg.KEY_SET_VALUE) as k:
            if on:
                winreg.SetValueEx(k, "CommunityCompute", 0, winreg.REG_SZ, f'"{exe}"')
            else:
                try:
                    winreg.DeleteValue(k, "CommunityCompute")
                except FileNotFoundError:
                    pass
    except OSError:
        pass


def _brand_icon() -> QIcon:
    """The real brand mark, resolved for both a dev run and the frozen EXE."""
    here = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    for rel in ("app.ico", os.path.join("..", "..", "build_assets", "app.ico")):
        p = os.path.join(here, rel)
        if os.path.exists(p):
            return QIcon(p)
    return QIcon()


def _line(placeholder="", password=False):
    e = QLineEdit()
    e.setPlaceholderText(placeholder)
    if password:
        e.setEchoMode(QLineEdit.EchoMode.Password)
    e.setMinimumHeight(38)
    e.setStyleSheet("QLineEdit{background:rgba(255,255,255,0.05);border:1px solid "
                    "rgba(255,255,255,0.12);border-radius:10px;padding:6px 12px;color:#f0f0ff;}"
                    "QLineEdit:focus{border-color:%s;}" % ui.CYAN)
    return e


def _fmt_uptime(secs: int) -> str:
    if secs <= 0:
        return "—"
    h, m = secs // 3600, (secs % 3600) // 60
    if h:
        return f"{h} שע' {m} דק'"
    if m:
        return f"{m} דק'"
    return f"{secs} שנ'"


class Counter(QLabel):
    """A number that COUNTS UP instead of jumping.

    The server credits a whole batch at once, so a plain label would jump
    0 → 50 → 100 and the contribution would feel like it happens to you rather
    than by you. Ticking it up is the same information, read as progress.
    """

    def __init__(self, value: int = 0):
        super().__init__(f"{value:,}")
        self._value = value
        self._anim: QVariantAnimation | None = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_value(self, v: int, animate: bool = True) -> None:
        v = int(v)
        if v == self._value:
            return
        if self._anim:
            self._anim.stop()
        if not animate or abs(v - self._value) > 5000:
            self._value = v
            self.setText(f"{v:,}")
            return
        a = QVariantAnimation(self)
        a.setStartValue(self._value)
        a.setEndValue(v)
        a.setDuration(min(1400, 260 + abs(v - self._value) * 22))
        a.setEasingCurve(QEasingCurve.Type.OutCubic)
        a.valueChanged.connect(lambda x: self.setText(f"{int(x):,}"))
        a.finished.connect(lambda: self.setText(f"{v:,}"))
        a.start()
        self._anim = a
        self._value = v


class Home(QWidget):
    """The stage ring + the big toggle + live status."""

    def __init__(self, engine: Engine, state: State, on_need_keys):
        super().__init__()
        self.engine = engine
        self.state = state
        self.on_need_keys = on_need_keys
        self._phase_i = 0
        self._last = {}

        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 16, 26, 20)
        lay.setSpacing(10)

        sub = QLabel("תרמו כוח-תרגום לקהילה — במחשב שלכם, עם המפתחות שלכם")
        sub.setProperty("muted", "1")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(sub)

        # the ring, with the toggle centred inside it
        holder = QWidget()
        holder.setMinimumHeight(300)
        self.ring = StageRing(holder)
        self.toggle = BigToggle(holder)
        self.toggle.toggled.connect(self._toggled)
        self._holder = holder
        holder.resizeEvent = self._layout_ring        # keep the toggle centred
        lay.addWidget(holder, 1)

        self.title = QLabel("כבוי")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet("font-size:15pt;font-weight:800;")
        self.note = QLabel("הפעילו כדי לתרום")
        self.note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.note.setProperty("muted", "1")
        self.note.setWordWrap(True)
        lay.addWidget(self.title)
        lay.addWidget(self.note)

        self.card_lines, self.n_lines = self._stat("שורות שתרמת")
        self.card_wait, self.n_wait = self._stat("ממתין לשליחה")
        self.card_up, self.n_up = self._stat("פועל כבר")
        r = QHBoxLayout(); r.setSpacing(10)
        for c in (self.card_lines, self.card_wait, self.card_up):
            r.addWidget(c, 1)
        lay.addLayout(r)

        self.gate = QLabel("")
        self.gate.setProperty("muted", "1")
        self.gate.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.gate.setWordWrap(True)
        lay.addWidget(self.gate)

        # data every 3s, wording every ~9s — numbers feel live, text never jitters
        self._tick = QTimer(self)
        self._tick.timeout.connect(self._rotate)
        self._tick.start(3000)

    def _layout_ring(self, ev):
        w, h = self._holder.width(), self._holder.height()
        self.ring.setGeometry(0, 0, w, h)
        side = min(w, h)
        tw = int(side * 0.42)
        th = max(64, int(side * 0.20))
        self.toggle.setGeometry((w - tw) // 2, (h - th) // 2, tw, th)

    def _stat(self, cap):
        p = ui.Panel(soft=True)
        v = QVBoxLayout(p); v.setContentsMargins(12, 10, 12, 10); v.setSpacing(2)
        num = Counter(0)
        num.setStyleSheet("font-size:19pt;font-weight:800;")
        c = ui.caption(cap); c.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(num); v.addWidget(c)
        return p, num

    def _toggled(self, on: bool):
        if on and not providers.available(keystore.load()):
            self.toggle.set_on(False, animate=True)
            self.on_need_keys()
            return
        self.engine.set_on(on)

    def _rotate(self):
        self._phase_i += 1
        if self._last:
            self._paint(self._last, rotate=True)

    def on_status(self, d: dict):
        self._last = d
        self.toggle.set_on(d["on"], animate=True)
        self._paint(d)

    def _paint(self, d: dict, rotate: bool = False):
        stage, running = int(d.get("stage") or 0), bool(d.get("on") and d.get("busy"))
        self.ring.set_state(stage, running)

        if d.get("blocked"):
            head, sub = "נחסם", "המכשיר אינו מקבל עבודה כרגע"
        elif not d["on"]:
            head, sub = "כבוי", "הפעילו כדי לתרום"
        elif not d["has_keys"]:
            head, sub = "חסר מפתח", "הוסיפו מפתח בעמוד «מפתחות»"
        elif running:
            opts = PHRASES.get(stage, ["עובד"])
            head, sub = ("פעיל", opts[(self._phase_i // 3) % len(opts)])
        elif not d["online"]:
            head, sub = "אין קשר לשרת", "העבודה נאגרת מקומית ותישלח כשהחיבור יחזור"
        else:
            head, sub = "ממתין", d.get("note") or "אין כרגע עבודה בתור"
        self.title.setText(head)
        self.note.setText(sub)
        self.ring.set_text(head, sub)

        if not rotate:
            self.n_lines.set_value(d["lines"])
            self.n_wait.set_value(d["outbox"])
        self.n_up.setText(_fmt_uptime(int(d.get("uptime") or 0)))

        if not d["has_keys"]:
            self.gate.setText("הוסיפו מפתח מלפחות ספק אחד בעמוד «מפתחות» כדי להפעיל.")
        elif d["outbox"] and not d["online"]:
            self.gate.setText(f"{d['outbox']} שורות מתורגמות ממתינות — יישלחו אוטומטית כשהחיבור יחזור.")
        elif d["inbox"]:
            self.gate.setText(f"{d['inbox']} שורות שמורות מקומית לעבודה — גם ללא חיבור לשרת.")
        else:
            self.gate.setText("")


class Keys(QWidget):
    def __init__(self, state: State, on_saved):
        super().__init__()
        self.state = state
        self.on_saved = on_saved
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 20, 26, 20)
        lay.setSpacing(11)
        h = QLabel("מפתחות API חינמיים"); h.setObjectName("h1")
        lay.addWidget(h)
        info = QLabel("שלושה ספקים בעלי דרגה חינמית. הוסיפו מפתח מכל ספק שתרצו (מומלץ שלושתם). "
                      "המפתחות נשמרים מוצפנים במחשב שלכם בלבד — לעולם לא נשלחים לשום שרת.")
        info.setProperty("muted", "1"); info.setWordWrap(True)
        lay.addWidget(info)

        keys = keystore.load()
        self.edits = {}
        for label, pid, url in PROVIDERS:
            box = ui.Panel(soft=True)
            v = QVBoxLayout(box); v.setContentsMargins(14, 12, 14, 12); v.setSpacing(6)
            top = QHBoxLayout()
            dot = QLabel("●")
            dot.setStyleSheet(f"color:{ui.GREEN if keys.get(pid) else 'rgba(255,255,255,0.20)'};")
            nm = QLabel(label); nm.setStyleSheet("font-weight:700;")
            link = QLabel(f'<a style="color:{ui.CYAN};text-decoration:none" href="https://{url}">קבלת מפתח ↗</a>')
            link.setOpenExternalLinks(True)
            top.addWidget(dot); top.addWidget(nm); top.addStretch(1); top.addWidget(link)
            v.addLayout(top)
            e = _line(f"מפתח {label}", password=True)
            if keys.get(pid):
                e.setText(keys[pid])
            eye = QPushButton("👁")
            eye.setFixedWidth(40)
            eye.setCursor(Qt.CursorShape.PointingHandCursor)
            eye.setCheckable(True)
            eye.toggled.connect(lambda on, ed=e: ed.setEchoMode(
                QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password))
            v.addWidget(ui.row(e, eye))
            self.edits[pid] = e
            lay.addWidget(box)

        save = QPushButton("שמירה")
        save.setObjectName("primary")
        save.setMinimumHeight(40)
        save.setCursor(Qt.CursorShape.PointingHandCursor)
        save.clicked.connect(self._save)
        imp = QPushButton("ייבוא מקובץ")
        exp = QPushButton("ייצוא לקובץ")
        for b in (imp, exp):
            b.setMinimumHeight(40)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        imp.clicked.connect(self._import)
        exp.clicked.connect(self._export)
        lay.addWidget(save)
        lay.addWidget(ui.row(imp, exp))
        lay.addStretch(1)

    def _save(self):
        vals = {pid: e.text().strip() for pid, e in self.edits.items()}
        keystore.save({k: v for k, v in vals.items() if v})
        self.on_saved()
        QMessageBox.information(self, APP_NAME, "המפתחות נשמרו מוצפנים במחשב הזה.")

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(self, "ייצוא מפתחות", "cc-keys.txt", "טקסט (*.txt)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                for pid, e in self.edits.items():
                    if e.text().strip():
                        f.write(f"{pid}={e.text().strip()}\n")
            QMessageBox.information(self, APP_NAME,
                                    "נשמר. ⚠ הקובץ מכיל את המפתחות בטקסט גלוי — שמרו אותו במקום בטוח.")
        except OSError as ex:
            QMessageBox.warning(self, APP_NAME, f"השמירה נכשלה: {ex}")

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(self, "ייבוא מפתחות", "", "טקסט (*.txt);;הכול (*)")
        if not path:
            return
        try:
            text = open(path, encoding="utf-8").read()
        except OSError as ex:
            QMessageBox.warning(self, APP_NAME, f"הקריאה נכשלה: {ex}")
            return
        found = 0
        for raw in text.splitlines():
            s = raw.strip()
            if not s or s.startswith("#"):
                continue
            pid, val = (s.split("=", 1) + [""])[:2] if "=" in s else ("", s)
            pid, val = pid.strip().lower(), val.strip()
            if pid not in self.edits:      # a bare token — route it by its own prefix
                pid = ("groq" if val.startswith("gsk_") else
                       "nim" if val.startswith("nvapi-") else
                       "sambanova" if val else "")
            if pid in self.edits and val:
                self.edits[pid].setText(val)
                found += 1
        QMessageBox.information(
            self, APP_NAME,
            f"זוהו {found} מפתחות. לחצו «שמירה» כדי לשמור אותם." if found
            else "לא זוהה אף מפתח בקובץ.")


class Settings(QWidget):
    """Personalisation + the server target — the launcher's own settings shape."""

    def __init__(self, state: State, engine: Engine, on_theme):
        super().__init__()
        self.state = state
        self.engine = engine
        self.on_theme = on_theme
        s = state.settings()

        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 20, 26, 20)
        lay.setSpacing(11)
        h = QLabel("הגדרות"); h.setObjectName("h1"); lay.addWidget(h)

        # accent
        sw = QWidget(); swl = QHBoxLayout(sw); swl.setContentsMargins(0, 0, 0, 0); swl.setSpacing(8)
        self._swatches = {}
        for key, col in ACCENTS.items():
            b = ui.swatch(col, key == s.get("accent"))
            b.clicked.connect(lambda _=False, k=key: self._accent(k))
            self._swatches[key] = b
            swl.addWidget(b)
        swl.addStretch(1)
        lay.addWidget(ui.setting_row("צבע ראשי", sw, "צובע את הטבעת, הרקע וההדגשות."))

        # animation level
        self.anim = ui.Segmented([("full", "מלאה"), ("normal", "רגילה"),
                                  ("reduced", "מופחתת"), ("off", "כבויה")],
                                 s.get("anim", "full"))
        self.anim.changed.connect(self._anim)
        lay.addWidget(ui.setting_row("אנימציות", self.anim,
                                     "הורידו במחשב חלש — הטבעת מפסיקה לצייר לגמרי במצב «כבויה»."))

        # glass
        glass = ui.checkbox("רקע זכוכית מטושטש", s.get("glass", True))
        glass.toggled.connect(lambda v: (state.set_setting("glass", v), on_theme()))
        lay.addWidget(glass)

        # text size
        self.txt = ui.slider_row(75, 125, 5, int(s.get("text_scale", 100)))
        self.txt_lbl = QLabel(f"{int(s.get('text_scale', 100))}%")
        self.txt.valueChanged.connect(self._text)
        lay.addWidget(ui.setting_row("גודל הטקסט", ui.row(self.txt, self.txt_lbl)))

        # behaviour
        auto = ui.checkbox("הפעלה אוטומטית עם עליית המחשב", s.get("autostart"))
        auto.toggled.connect(lambda v: (state.set_setting("autostart", v), _set_autostart(v)))
        tray = ui.checkbox("סגירה מזערת למגש המערכת (ממשיך לתרום ברקע)", s.get("min_to_tray"))
        tray.toggled.connect(lambda v: state.set_setting("min_to_tray", v))
        lay.addWidget(auto); lay.addWidget(tray)

        # server target
        self.base = _line(CC_BASE)
        self.base.setText(s.get("base_override", "") or "")
        self.base.setEchoMode(QLineEdit.EchoMode.Normal)
        apply_ = QPushButton("החל")
        apply_.setMinimumHeight(38)
        apply_.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_.clicked.connect(self._base)
        lay.addWidget(ui.setting_row(
            "כתובת השרת", ui.row(self.base, apply_),
            "השאירו ריק לברירת המחדל. ההגדרות האחרות (תדירות, גודל מנה) מגיעות מהשרת "
            "עצמו ומתעדכנות לבד — רק הכתובת נקבעת כאן."))

        self.live = QLabel("")
        self.live.setProperty("muted", "1")
        self.live.setWordWrap(True)
        lay.addWidget(self.live)
        lay.addStretch(1)

        self._t = QTimer(self); self._t.timeout.connect(self._show_live); self._t.start(3000)
        self._show_live()

    def _accent(self, key):
        self.state.set_setting("accent", key)
        for k, b in self._swatches.items():
            b.setStyleSheet(
                f"QPushButton{{background:{ACCENTS[k]};border-radius:15px;"
                f"border:{'3px solid #ffffff' if k == key else '1px solid rgba(255,255,255,0.25)'};}}")
        self.on_theme()

    def _anim(self, key):
        self.state.set_setting("anim", key)
        self.on_theme()

    def _text(self, v):
        v = int(round(v / 5.0) * 5)
        self.txt_lbl.setText(f"{v}%")
        self.state.set_setting("text_scale", v)
        self.on_theme()

    def _base(self):
        url = self.base.text().strip()
        if url and not url.startswith(("http://", "https://")):
            QMessageBox.warning(self, APP_NAME, "הכתובת חייבת להתחיל ב-http:// או https://")
            return
        self.state.set_setting("base_override", url)
        client.set_base(url)
        QMessageBox.information(self, APP_NAME,
                                f"השרת עודכן ל:\n{client.base()}\n\nהשינוי נכנס לתוקף בסבב הבא.")
        self._show_live()

    def _show_live(self):
        c = client.SERVER_CONFIG
        self.live.setText(
            f"שרת פעיל: {client.base()}\n"
            f"הגדרות מהשרת — פעימה כל {c['heartbeat_seconds'] // 60} דק' · "
            f"מנה {c['batch_size']} שורות · תקרה {c['max_inflight']} · "
            f"פקיעה {c['lease_ttl_seconds'] // 60} דק'")


class About(QWidget):
    def __init__(self, state: State):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 20, 26, 20)
        lay.setSpacing(12)
        h = QLabel("על התוכנה"); h.setObjectName("h1"); lay.addWidget(h)
        txt = QLabel(
            "מחשוב קהילתי מאפשר למתנדבים לתרום כוח-תרגום לפרויקט התרגום העברי.\n\n"
            "• כשהמתג פעיל, התוכנה מושכת שורות מהמאגר, מתרגמת אותן עם המפתחות שלך "
            "(Groq · SambaNova · NVIDIA NIM), ומחזירה את התוצאה.\n"
            "• המפתחות מוצפנים במחשב (מחסן המערכת + הצפנה) ולעולם לא נשלחים.\n"
            "• מודל משיכה: השרת אף פעם לא מתחבר אליך — כתובת ה-IP שלך לא נחשפת.\n"
            "• אם אין קשר לשרת — העבודה נאגרת מקומית ונשלחת אוטומטית כשהחיבור חוזר.\n"
            "• אם המחשב נסגר באמצע — השורות חוזרות לתור אוטומטית ואף אחת לא הולכת לאיבוד.\n"
            "• התרגומים עוברים בקרת-איכות ואישור לפני שהם נכנסים למשחק.\n"
            "• אין קוד שרירותי — התוכנה מבצעת אך ורק קריאות-תרגום לספקים שבחרת.")
        txt.setWordWrap(True); txt.setProperty("muted", "1")
        lay.addWidget(txt)
        lay.addStretch(1)
        wid = QLabel(f"מזהה המכשיר: {state.worker_id}")
        wid.setProperty("muted", "1")
        wid.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        ver = QLabel(f"גרסה {APP_VERSION}"); ver.setProperty("muted", "1")
        lay.addWidget(wid); lay.addWidget(ver)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setObjectName("root")
        self.setMinimumSize(620, 780)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self.state = State()
        client.set_base(self.state.settings().get("base_override", "") or "")
        self.engine = Engine(self.state)

        self.ambient = ui.Ambient(self)
        self.ambient.lower()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(ui.TitleBar(self, APP_NAME))

        body = QHBoxLayout()
        body.setContentsMargins(12, 6, 12, 12)
        body.setSpacing(12)

        self.rail = ui.NavRail([
            ("home", "הפעלה", ui.GREEN, "⏻"),
            ("keys", "מפתחות", ui.YELLOW, "🔑"),
            ("settings", "הגדרות", ui.CYAN, "⚙"),
            ("about", "מידע", "#c084fc", "ⓘ"),
        ])
        self.rail.set_mode("auto")
        self.rail.changed.connect(self._nav)

        self.stack = QStackedWidget()
        self.home = Home(self.engine, self.state, on_need_keys=lambda: self.rail.select("keys"))
        self.keys = Keys(self.state, on_saved=self._refresh)
        self.settings = Settings(self.state, self.engine, on_theme=self._theme)
        self.about = About(self.state)
        panel = ui.Panel(glow=ui.GREEN)
        pl = QVBoxLayout(panel); pl.setContentsMargins(0, 0, 0, 0)
        pl.addWidget(self.stack)
        for w in (self.home, self.keys, self.settings, self.about):
            self.stack.addWidget(w)

        body.addWidget(panel, 1)
        body.addWidget(self.rail)
        outer.addLayout(body, 1)

        self.engine.status.connect(self.home.on_status)
        self.engine.start()

        icon = _brand_icon()
        self.setWindowIcon(icon)
        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip(APP_NAME)
        self.tray.activated.connect(
            lambda r: self._show() if r == QSystemTrayIcon.ActivationReason.Trigger else None)
        self.tray.show()

        self._backdrop = None
        QTimer.singleShot(0, self._theme)

        # a second launch (shortcut / autostart) surfaces THIS window instead of
        # starting a rival worker
        self._show_ev = single.make_show_event()
        self._show_timer = QTimer(self)
        self._show_timer.timeout.connect(
            lambda: self._show() if single.consume_show(self._show_ev) else None)
        self._show_timer.start(1200)

    # ------------------------------------------------------------ theme
    def _theme(self):
        s = self.state.settings()
        accent = ACCENTS.get(s.get("accent", "green"), ui.GREEN)
        want_glass = bool(s.get("glass", True))
        factor = ANIM_FACTOR.get(s.get("anim", "full"), 1.0)
        scale = int(s.get("text_scale", 100)) / 100.0

        self._backdrop = ui.apply_window_effects(self, "acrylic" if want_glass else "none")
        self.ambient.configure(accent, solid=not self._backdrop)
        self.setStyleSheet(ui.qss(accent, "acrylic" if self._backdrop else "none", 11.0 * scale))
        self.home.ring.set_accent(accent)
        self.home.ring.set_anim(factor)
        f = QGuiApplication.font(); f.setPointSizeF(11.0 * scale)
        QApplication.setFont(f)

    def _nav(self, key):
        idx = {"home": 0, "keys": 1, "settings": 2, "about": 3}[key]
        self.stack.setCurrentIndex(idx)
        factor = ANIM_FACTOR.get(self.state.settings().get("anim", "full"), 1.0)
        if factor > 0:
            ui.view_in(self.stack.currentWidget(), factor)

    def _refresh(self):
        self.engine._emit()

    def _show(self):
        self.showNormal(); self.raise_(); self.activateWindow()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self.ambient.setGeometry(0, 0, self.width(), self.height())

    def closeEvent(self, ev):
        if self.state.settings().get("min_to_tray"):
            ev.ignore(); self.hide()
            self.tray.showMessage(APP_NAME, "ממשיך לתרום ברקע — לחצו על הסמל כדי לפתוח.",
                                  QSystemTrayIcon.MessageIcon.Information, 2500)
        else:
            self.engine.stop()
            self.engine.wait(4000)      # let it flush + release its lines
            ev.accept()


def main():
    # Two copies share one worker_id and one state.json — they would claim the same
    # lines and overwrite each other's counters. Hand the launch to the running copy.
    if not single.acquire():
        single.signal_show()
        return

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    fam = ui.load_fonts()
    app.setFont(QFont(fam, 11))
    app.setApplicationName(APP_NAME)
    app.setWindowIcon(_brand_icon())
    w = MainWindow()
    w.resize(680, 820)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
