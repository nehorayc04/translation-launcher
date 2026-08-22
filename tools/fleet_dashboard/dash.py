# -*- coding: utf-8 -*-
"""מצב הצי — a live dashboard for the translation/QA fleet.

A SEPARATE program from the launcher (it never touches it), built on the launcher's OWN design
system and behaviour: Heebo, the glass surfaces, the 72↔230 rail with a travelling glowing
indicator, the view transition, the staggered entrance, segmented controls with a sliding glass
thumb, a custom frameless title bar, an accent-tinted ambient background, an animation LEVEL
(מלאה/רגילה/מופחתת/כבויה), a text-size slider, and a settings screen that decides what is shown and
what is hidden. Every token is sourced in ui.py.

    python dash.py            # the window
    python dash.py --once     # one collection printed as text (same data, no GUI)
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import collector as C                                                   # noqa: E402
import health as H                                                      # noqa: E402
import prefs as P                                                       # noqa: E402

CFG_NAME = "fleet_config.json"
FAMILY = "Segoe UI"


def log_dir() -> str:
    d = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "FleetDash")
    os.makedirs(d, exist_ok=True)
    return d


def load_cfg() -> dict:
    # frozen: the config rides inside the EXE (sys._MEIPASS); a copy next to the EXE wins so the
    # fleet layout can be edited without a rebuild.
    for base in (os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else None,
                 getattr(sys, "_MEIPASS", None), HERE):
        if base and os.path.exists(os.path.join(base, CFG_NAME)):
            with open(os.path.join(base, CFG_NAME), encoding="utf-8") as fh:
                return json.load(fh)
    raise SystemExit(f"{CFG_NAME} not found")


STATE_COLOR = {
    "עובד": "#3fe08a", "חנוק 429": "#ffd23f", "איטי": "#ff9f43",
    "חנוק ותקוע": "#ff9f43", "תקוע": "#ff5c5c", "מת": "#ff5c5c", "כפול": "#ff5c5c",
    "סיים": "#5dade2", "לא נבדק": "#8b93b0", "לא מדווח": "#ff9f43",
}
SEV_COLOR = {"error": "#ff5c5c", "warn": "#ffb020", "info": "#5dade2"}
SEV_TEXT = {"error": "תקלה", "warn": "אזהרה", "info": "מידע"}


def _esc(s) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fmt_rate(r) -> str:
    return "—" if r is None else (f"{r:.1f}/דק'" if r < 100 else f"{r:.0f}/דק'")


def fmt_pct(done: int, total: int, remaining: int) -> str:
    """Percent that can NEVER read 100% while work is left.

    🔴 202,611/202,702 is 99.955% and `f"{x:.1f}"` rounds it to "100.0%" — the panel announced a
    finished game with 91 lines still queued. A progress figure is a claim about STATE, so it must
    round DOWN and reserve 100% for remaining == 0; the same applies to any "done" badge.
    """
    if not total:
        return "0.0%"
    if remaining <= 0 and done >= total:
        return "100.0%"
    p = math.floor(done / total * 1000) / 10.0
    return f"{min(p, 99.9):.1f}%"


def fmt_eta(remaining: int, rate) -> str:
    if not rate or remaining <= 0:
        return "—"
    m = remaining / rate
    if m < 90:
        return f"{m:.0f} דק'"
    if m < 60 * 48:
        return f"{m / 60:.1f} שע'"
    return f"{m / 1440:.1f} ימים"


def fmt_age(sec) -> str:
    if sec is None or sec < 0:
        return "—"
    if sec < 120:
        return f"{int(sec)} ש'"
    return f"{int(sec / 60)} דק'" if sec < 5400 else f"{sec / 3600:.1f} שע'"


# --------------------------------------------------------------------------- text mode

def once_text(cfg: dict) -> str:
    hist, seen, strikes = C.load_history(), {}, {}
    t0 = time.time()
    remote = C.probe_all(cfg)
    snap = C.collect(cfg, remote, hist)
    C.latest_samples(cfg, snap, seen)
    findings = H.check(cfg, snap, strikes)
    C.save_history(hist)
    L = [f"collected in {time.time() - t0:.1f}s"]
    for g in snap["games"]:
        L.append(f"\n=== {g['id']}  {g['done']:,}/{g['total']:,} "
                 f"({fmt_pct(g['done'], g['total'], g['remaining'])})  remaining {g['remaining']:,}  "
                 f"rate {fmt_rate(g['rate'])}  eta {fmt_eta(g['remaining'], g['rate'])}  "
                 f"merge {fmt_age(g.get('merge_age'))}  dupes {g['dupes']:,}")
        for s in g["streams"]:
            st, why = H.stream_state(s, cfg["thresholds"])
            L.append(f"  #{s.get('num', 0):<3}{s['machine']:<8} {s['provider']:<10} {st:<11} "
                     f"{s['done']:>4}/{s['shard']:<5} rate {fmt_rate(s['rate']):<9} "
                     f"out {fmt_age(s['out_age']):<8} {why[:70]}")
    L.append("\n=== findings ===")
    if not findings:
        L.append("  (none) — כל הזרמים תקינים")
    for x in findings:
        L.append(f"  [{x['sev'].upper():<5}] {x['scope']}: {x['title']} — {x['reason']}")
    return "\n".join(L)


# --------------------------------------------------------------------------- GUI

def run_gui(cfg: dict) -> int:
    from PySide6.QtCore import QEvent, QObject, QRunnable, Qt, QThreadPool, QTimer, Signal
    from PySide6.QtGui import QColor, QFont, QPainter
    from PySide6.QtWidgets import (QAbstractItemView, QApplication, QHBoxLayout, QHeaderView,
                                   QLabel, QPushButton, QScrollArea, QTableWidget,
                                   QTableWidgetItem, QTextBrowser, QVBoxLayout, QWidget)
    import ui as U

    NO_EDIT = QAbstractItemView.EditTrigger.NoEditTriggers
    FIT = QHeaderView.ResizeMode.ResizeToContents
    STRETCH = QHeaderView.ResizeMode.Stretch

    # (key, label, accent, glyph). The glyph is what the COLLAPSED 72px rail shows — without one a
    # collapsed rail is literally blank (the launcher has SVG icons in that slot).
    VIEWS = [("overview", "סקירה", U.YELLOW, "◈"), ("streams", "זרמים", "#d4af37", "≡"),
             ("warnings", "אזהרות", U.RED, "⚠"), ("samples", "תרגומים", "#00c2ff", "✎"),
             ("perf", "ביצועים", U.GREEN, "⚡"), ("settings", "הגדרות", "#a78bfa", "⚙")]
    VIEW_LABEL = {k: lbl for k, lbl, _a, _g in VIEWS}

    # "progress" means two different things and the header says which: with a pre-assigned
    # shard it is done/shard-size, in POOL MODE there is no shard at all - it is what this
    # stream has translated over what it is holding right now. Rendering "93/47" under a
    # header that says "progress in the shard" reads as nonsense.
    COLS = [("num", "#"), ("game", "משחק"), ("machine", "מכונה"), ("provider", "ספק"), ("state", "מצב"),
            ("progress", "התקדמות במנה"), ("remaining", "נשאר"), ("rate", "קצב"),
            ("out_age", "עודכן"), ("pid", "PID"), ("reason", "סיבה / הערה")]
    COLS_POOL = {"progress": "תורגם / מחזיק", "remaining": "נשאר במאגר", "out_age": "דיווח אחרון"}

    class Sig(QObject):
        ready = Signal(dict)
        failed = Signal(str)

    class Job(QRunnable):
        """One collection pass off the UI thread; `remote` is reused when not due."""

        def __init__(self, app, do_remote):
            super().__init__()
            self.app, self.do_remote = app, do_remote

        def run(self):
            try:
                t0 = time.time()
                if self.do_remote:
                    self.app.remote = C.probe_all(self.app.cfg)
                    self.app.remote_t = time.time()
                snap = C.collect(self.app.cfg, self.app.remote, self.app.hist)
                samples = C.latest_samples(self.app.cfg, snap, self.app.seen)
                findings = H.check(self.app.cfg, snap, self.app.strikes)
                C.save_history(self.app.hist)
                self.app.sig.ready.emit({"snap": snap, "samples": samples, "findings": findings,
                                         "took": time.time() - t0, "remote_t": self.app.remote_t})
            except Exception:
                self.app.sig.failed.emit(traceback.format_exc())

    class Ripple(QWidget):
        """The launcher's global click ripple as a short-lived painted child."""

        def __init__(self, parent, center, factor):
            super().__init__(parent)
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            self.setGeometry(parent.rect())
            self.center = center
            self._max = max(parent.width(), parent.height()) * 1.15
            self._i, self._steps, self._r = 0, max(1, int(20 * factor)), 0.0
            self.show()
            self._t = QTimer(self)
            self._t.timeout.connect(self._tick)
            self._t.start(16)

        def _tick(self):
            self._i += 1
            self._r = self._max * (self._i / self._steps)
            self.update()
            if self._i >= self._steps:
                self._t.stop()
                self.deleteLater()

        def paintEvent(self, _):
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, int(60 * (1 - self._i / max(1, self._steps)))))
            p.drawEllipse(self.center, int(self._r), int(self._r))

    class Dash(QWidget):
        def __init__(self, cfg):
            super().__init__()
            self.cfg = cfg
            self.p = P.load()
            self.hist = C.load_history()
            self.seen: dict = {}
            self.strikes: dict = {}
            self.remote: dict = {}
            self.remote_t = 0.0
            self.busy = False
            self.feed: list[dict] = []
            self.last: dict | None = None
            want = "overview"
            if "--view" in sys.argv:                 # deep-link, used by the screenshot checks
                i = sys.argv.index("--view") + 1
                if i < len(sys.argv):
                    want = sys.argv[i]
            self.view = want if want in dict((k, 1) for k, _l, _a, _g in VIEWS) else "overview"
            self.filters = {"streams": "all", "warnings": "all", "samples": "all"}
            self.sig = Sig()
            self.sig.ready.connect(self.on_ready)
            self.sig.failed.connect(self.on_failed)
            self.pool = QThreadPool()
            self.pool.setMaxThreadCount(2)

            self.setWindowTitle("מצב הצי — Fleet Dashboard")
            self.setObjectName("root")
            self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            self.setMinimumSize(1100, 680)
            if self.p.get("custom_titlebar", True):
                self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
                self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            g = self.p.get("window")
            self.setGeometry(*(g if isinstance(g, list) and len(g) == 4 else (110, 55, 1500, 950)))

            self.amb = U.Ambient(self)

            root = QVBoxLayout(self)
            root.setContentsMargins(0, 0, 0, 0)
            root.setSpacing(0)
            if self.p.get("custom_titlebar", True):
                root.addWidget(U.TitleBar(self, "מצב הצי · Fleet Dashboard"))

            body = QHBoxLayout()
            body.setContentsMargins(12, 6, 12, 12)
            body.setSpacing(12)
            root.addLayout(body, 1)

            self.rail = U.NavRail(VIEWS, self)
            self.rail.changed.connect(self.go)
            body.addWidget(self.rail)

            right = QVBoxLayout()
            right.setSpacing(10)
            body.addLayout(right, 1)

            head = U.Panel()
            hl = QHBoxLayout(head)
            hl.setContentsMargins(14, 10, 14, 10)
            hl.setSpacing(10)
            self.pill = QLabel("בודק…")
            self.pill.setMinimumWidth(140)
            self.pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.title = QLabel("סקירה")
            self.title.setObjectName("h1")
            self.sub = QLabel("")
            self.sub.setProperty("muted", "1")
            btn_now = QPushButton("רענן")
            btn_now.setToolTip("איסוף מלא כולל בדיקת כל המכונות")
            btn_now.clicked.connect(lambda: self.tick(True))
            hl.addWidget(self.pill)
            hl.addWidget(self.title)
            hl.addStretch(1)
            hl.addWidget(self.sub)
            hl.addWidget(btn_now)
            for gm in cfg["games"]:
                b = QPushButton(f"מיזוג {gm['id']}")
                b.setToolTip("מריץ את ה-pull: מרענן בנקים, התקדמות ודוגמאות")
                b.clicked.connect(
                    lambda _=False, gg=gm: self.status.setText(C.run_pull(self.cfg, gg)))
                hl.addWidget(b)
            right.addWidget(head)

            self.host = QWidget()
            self.hostlay = QVBoxLayout(self.host)
            self.hostlay.setContentsMargins(0, 0, 0, 0)
            right.addWidget(self.host, 1)

            self.status = QLabel("")
            self.status.setProperty("muted", "1")
            right.addWidget(self.status)

            self.apply_prefs()
            self.go(self.view, animate=False)
            self.t_local = QTimer(self)
            self.t_local.timeout.connect(lambda: self.tick(False))
            self.t_local.start(max(5, int(self.p["local_seconds"])) * 1000)
            QTimer.singleShot(150, lambda: self.tick(True))
            QApplication.instance().installEventFilter(self)

        # ------------------------------------------------ prefs / chrome
        def accent(self) -> str:
            return P.accent_hex(self.p)

        def factor(self) -> float:
            return P.factor(self.p)

        def apply_prefs(self, rerender=False):
            acc, bd = self.accent(), self.p["backdrop"]
            blurred = U.apply_window_effects(self, bd)
            base_pt = 10.5 * (int(self.p["text_size"]) / 100.0)
            self.setStyleSheet(U.qss(acc, bd if blurred else "none", base_pt))
            self.amb.configure(acc, solid=(bd == "none"))
            self.amb.setGeometry(self.rect())
            self.amb.lower()
            self.rail.set_factor(self.factor())
            self.rail.set_mode(self.p["sidebar"])
            fo = QFont(FAMILY)
            fo.setPointSizeF(base_pt)
            QApplication.instance().setFont(fo)
            if rerender:
                self.go(self.view, animate=False)

        def eventFilter(self, obj, ev):
            if (ev.type() == QEvent.Type.MouseButtonPress and self.p.get("ripple", True)
                    and self.factor() > 0 and isinstance(obj, QPushButton)):
                try:
                    Ripple(obj, ev.position().toPoint(), self.factor())
                except Exception:
                    pass
            return False

        def resizeEvent(self, ev):
            super().resizeEvent(ev)
            self.amb.setGeometry(self.rect())
            self.amb.lower()

        def closeEvent(self, ev):
            r = self.geometry()
            self.p["window"] = [r.x(), r.y(), r.width(), r.height()]
            P.save(self.p)
            super().closeEvent(ev)

        # ------------------------------------------------ navigation
        def go(self, key: str, animate=True):
            self.view = key
            while self.hostlay.count():
                item = self.hostlay.takeAt(0)
                w = item.widget()
                if w:
                    w.setParent(None)
                    w.deleteLater()
            w = {"overview": self.build_overview, "streams": self.build_streams,
                 "warnings": self.build_warnings, "samples": self.build_samples,
                 "perf": self.build_perf, "settings": self.build_settings}[key]()
            self.hostlay.addWidget(w)
            self.title.setText(VIEW_LABEL[key])
            self.rail.set_current_silent(key)
            if animate:
                U.view_in(w, self.factor())

        def render_all(self):
            if self.view != "settings":                    # never yank the screen out from a click
                self.go(self.view, animate=False)

        # ------------------------------------------------ data
        def tick(self, force_remote: bool):
            if self.busy:
                return
            due = force_remote or (time.time() - self.remote_t > int(self.p["remote_seconds"]))
            self.busy = True
            self.status.setText("אוסף נתונים…" + ("  ·  בודק מכונות" if due else ""))
            self.cfg["refresh"]["rate_window_minutes"] = int(self.p["rate_window_minutes"])
            self.pool.start(Job(self, due))

        def on_failed(self, tb: str):
            self.busy = False
            with open(os.path.join(log_dir(), "dash.log"), "a", encoding="utf-8") as fh:
                fh.write(f"\n--- {time.strftime('%F %T')}\n{tb}")
            self.status.setText("שגיאה באיסוף — נרשמה ל-dash.log")

        def on_ready(self, res: dict):
            self.busy = False
            self.last = res
            for s in res["samples"]:
                self.feed.insert(0, s)
            self.feed = self.feed[:int(self.p["samples_keep"])]
            f = self.visible_findings(res)
            n_err = sum(1 for x in f if x["sev"] == "error")
            n_warn = sum(1 for x in f if x["sev"] == "warn")
            if n_err:
                txt, col = f"תקלה · {n_err}", SEV_COLOR["error"]
            elif n_warn:
                txt, col = f"אזהרה · {n_warn}", SEV_COLOR["warn"]
            else:
                txt, col = "הכל תקין", "#2ecc71"
            self.pill.setText(txt)
            self.pill.setStyleSheet(f"background:{col};color:#0a0a14;border-radius:15px;"
                                    f"padding:6px 14px;font-weight:800;")
            streams = self.visible_streams(res["snap"])
            alive = sum(1 for s in streams if s["alive"] >= 1)
            age = time.time() - res["remote_t"] if res["remote_t"] else -1
            self.sub.setText(f"{alive}/{len(streams)} זרמים חיים · מכונות נבדקו לפני {fmt_age(age)}"
                             f" · איסוף {res['took']:.1f} ש'")
            self.status.setText(f"עודכן {time.strftime('%H:%M:%S')}")
            self.render_all()

        # ------------------------------------------------ shown / hidden
        def game_shown(self, gid: str) -> bool:
            return bool(self.p["show_games"].get(gid, True))

        def visible_streams(self, snap: dict) -> list[dict]:
            out = [s for s in snap["streams"] if self.game_shown(s["game"])]
            if self.p.get("hide_finished"):
                out = [s for s in out if H.stream_state(s, self.cfg["thresholds"])[0] != "סיים"]
            return out

        def visible_findings(self, res: dict) -> list[dict]:
            f = list(res["findings"])
            if self.p.get("hide_info"):
                f = [x for x in f if x["sev"] != "info"]
            hidden = [g["id"] for g in res["snap"]["games"] if not self.game_shown(g["id"])]
            return [x for x in f if not any(h in x["scope"] for h in hidden)]

        # ------------------------------------------------ views
        @staticmethod
        def _scroll(inner: QWidget) -> QScrollArea:
            sa = QScrollArea()
            sa.setWidgetResizable(True)
            sa.setFrameShape(QScrollArea.Shape.NoFrame)
            sa.setStyleSheet("QScrollArea,QScrollArea>QWidget>QWidget{background:transparent;}")
            sa.setWidget(inner)
            return sa

        def _text(self, html: str) -> QTextBrowser:
            tb = QTextBrowser()
            tb.setOpenExternalLinks(False)
            tb.setHtml(html)
            return tb

        def build_overview(self) -> QWidget:
            wrap = QWidget()
            lay = QVBoxLayout(wrap)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(10)
            if not self.last:
                lay.addWidget(U.caption("אוסף נתונים…"))
                return wrap
            res = self.last
            panels = self.p["overview_panels"]
            appear: list[QWidget] = []
            if panels.get("cards", True):
                strip = QHBoxLayout()
                strip.setSpacing(10)
                bars = []
                for g in res["snap"]["games"]:
                    if not self.game_shown(g["id"]):
                        continue
                    card = U.Panel(glow=self.accent())
                    cl = QVBoxLayout(card)
                    cl.setContentsMargins(16, 14, 16, 14)
                    cl.setSpacing(5)
                    t = QLabel(g["title"])
                    t.setStyleSheet("font-weight:700;")
                    pct = g["done"] / g["total"] * 100 if g["total"] else 0
                    big = QLabel(fmt_pct(g["done"], g["total"], g["remaining"]))
                    big.setObjectName("big")
                    sub = QLabel(f"{g['done']:,} / {g['total']:,}")
                    sub.setProperty("muted", "1")
                    track = QWidget()
                    track.setFixedHeight(8)
                    track.setStyleSheet("background:rgba(255,255,255,0.07);border-radius:4px;")
                    fill = QWidget(track)
                    fill.setStyleSheet(
                        f"background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {U.YELLOW},"
                        f"stop:1 {self.accent()});border-radius:4px;")
                    bars.append((fill, track, pct))
                    facts = QLabel(f"נשארו <b>{g['remaining']:,}</b> · קצב "
                                   f"<b>{fmt_rate(g['rate'])}</b> · סיום "
                                   f"<b>{fmt_eta(g['remaining'], g['rate'])}</b>")
                    facts.setTextFormat(Qt.TextFormat.RichText)
                    meta = QLabel(f"מיזוג לפני {fmt_age(g.get('merge_age'))} · "
                                  f"כפולות {g['dupes']:,} · {len(g['streams'])} זרמים")
                    meta.setProperty("muted", "1")
                    for x in (t, big, sub, track, facts, meta):
                        cl.addWidget(x)
                    strip.addWidget(card, 1)
                    appear.append(card)
                lay.addLayout(strip)
                QTimer.singleShot(0, lambda bs=bars: [
                    f.setGeometry(0, 0, max(6, int(tr.width() * pc / 100)), 8) for f, tr, pc in bs])
            lower = QHBoxLayout()
            lower.setSpacing(10)
            for key, cap, html in (
                    ("warnings", "אזהרות ותקלות — הדחוף למעלה",
                     lambda: self.findings_html(self.visible_findings(res)[:8])),
                    ("samples", "תרגומים אחרונים", lambda: self.samples_html(12)),
                    ("providers", "ספקים", lambda: self.providers_html(res["snap"]))):
                if not panels.get(key, True):
                    continue
                box = U.Panel()
                bl = QVBoxLayout(box)
                bl.setContentsMargins(14, 12, 14, 12)
                bl.setSpacing(7)
                bl.addWidget(U.caption(cap))
                bl.addWidget(self._text(html()))
                lower.addWidget(box, 1)
                appear.append(box)
            lay.addLayout(lower, 1)
            U.stagger_in(appear, self.factor())
            return wrap

        def _seg_head(self, cap: str, key: str, options, on_change) -> QWidget:
            seg = U.Segmented(options, self.filters[key], self.accent())
            seg.set_factor(self.factor())
            seg.changed.connect(on_change)
            return U.row(U.caption(cap), None, seg)

        def build_streams(self) -> QWidget:
            wrap = U.Panel()
            lay = QVBoxLayout(wrap)
            lay.setContentsMargins(14, 12, 14, 12)
            lay.setSpacing(10)
            lay.addWidget(self._seg_head(
                "זרמים · לחיצה על סיבה מציגה את הכל", "streams",
                [("all", "הכל"), ("problem", "בעיות"), ("work", "עובדים"), ("done", "סיימו")],
                lambda v: (self.filters.__setitem__("streams", v), self.go("streams", False))))
            # a pool-mode game on the board renames the three columns whose meaning changed
            pool_mode = any(g.get("pool")
                            for g in (((self.last or {}).get("snap") or {}).get("games") or []))
            cols = [(k, (COLS_POOL.get(k, lbl) if pool_mode else lbl))
                    for k, lbl in COLS if self.p["columns"].get(k, True)]
            tbl = QTableWidget(0, len(cols))
            tbl.setHorizontalHeaderLabels([lbl for _, lbl in cols])
            tbl.verticalHeader().setVisible(False)
            tbl.setEditTriggers(NO_EDIT)
            tbl.setShowGrid(False)
            hh = tbl.horizontalHeader()
            for i, (k, _) in enumerate(cols):
                hh.setSectionResizeMode(i, STRETCH if k == "reason" else FIT)
            rows = self.visible_streams(self.last["snap"]) if self.last else []
            th = self.cfg["thresholds"]
            filt = self.filters["streams"]
            keep = []
            for s in rows:
                st, why = H.stream_state(s, th)
                if filt == "problem" and st in ("עובד", "סיים"):
                    continue
                if filt == "work" and st not in ("עובד", "חנוק 429"):
                    continue
                if filt == "done" and st != "סיים":
                    continue
                keep.append((s, st, why))
            tbl.setRowCount(len(keep))
            for r, (s, st, why) in enumerate(keep):
                vals = {"num": str(s.get("num", 0)), "game": s["game"], "machine": s["machine"], "provider": s["provider"],
                        "state": st, "progress": f"{s['done']}/{s['shard']}",
                        "remaining": str(s["remaining"]), "rate": fmt_rate(s["rate"]),
                        "out_age": fmt_age(s["out_age"]), "pid": str(s["pid"] or "—"),
                        "reason": why}
                for c, (k, _) in enumerate(cols):
                    it = QTableWidgetItem(vals[k])
                    if k == "state":
                        it.setForeground(QColor(STATE_COLOR.get(st, U.TEXT)))
                        fo = QFont(FAMILY)
                        fo.setBold(True)
                        it.setFont(fo)
                    if why:
                        it.setToolTip(why)
                    tbl.setItem(r, c, it)
            lay.addWidget(tbl, 1)
            return wrap

        def build_warnings(self) -> QWidget:
            wrap = U.Panel()
            lay = QVBoxLayout(wrap)
            lay.setContentsMargins(14, 12, 14, 12)
            lay.setSpacing(10)
            lay.addWidget(self._seg_head(
                "כל בעיה — עם הסיבה ומה עושים", "warnings",
                [("all", "הכל"), ("error", "תקלות"), ("warn", "אזהרות")],
                lambda v: (self.filters.__setitem__("warnings", v), self.go("warnings", False))))
            f = self.visible_findings(self.last) if self.last else []
            if self.filters["warnings"] != "all":
                f = [x for x in f if x["sev"] == self.filters["warnings"]]
            lay.addWidget(self._text(self.findings_html(f)), 1)
            return wrap

        def build_samples(self) -> QWidget:
            wrap = U.Panel()
            lay = QVBoxLayout(wrap)
            lay.setContentsMargins(14, 12, 14, 12)
            lay.setSpacing(10)
            lay.addWidget(self._seg_head(
                "שורות שנכנסו לבנק — אנגלית, ואז עברית לפני/אחרי", "samples",
                [("all", "הכל"), ("fix", "תיקונים בלבד")],
                lambda v: (self.filters.__setitem__("samples", v), self.go("samples", False))))
            lay.addWidget(self._text(self.samples_html(60)), 1)
            return wrap

        def build_perf(self) -> QWidget:
            wrap = QWidget()
            lay = QVBoxLayout(wrap)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(10)
            if not self.last:
                lay.addWidget(U.caption("אוסף נתונים…"))
                return wrap
            boxes = []
            for cap, html, weight in (("ספקים", self.providers_html(self.last["snap"]), 1),
                                      ("מכונות", self.machines_html(self.last["snap"]), 2)):
                box = U.Panel()
                bl = QVBoxLayout(box)
                bl.setContentsMargins(14, 12, 14, 12)
                bl.setSpacing(7)
                bl.addWidget(U.caption(cap))
                bl.addWidget(self._text(html))
                lay.addWidget(box, weight)
                boxes.append(box)
            U.stagger_in(boxes, self.factor())
            return wrap

        def build_settings(self) -> QWidget:
            inner = QWidget()
            lay = QVBoxLayout(inner)
            lay.setContentsMargins(2, 2, 2, 2)
            lay.setSpacing(9)

            def commit(key, val, chrome=False):
                self.p[key] = val
                P.save(self.p)
                self.apply_prefs(rerender=chrome)

            def sub(key, k2, val):
                self.p[key][k2] = val
                P.save(self.p)

            lay.addWidget(U.caption("מראה"))
            s = U.Segmented([(k, P.ANIM_LABELS[k]) for k in P.ANIM_LEVELS], self.p["anim"],
                            self.accent())
            s.set_factor(self.factor())
            s.changed.connect(lambda v: commit("anim", v, True))
            lay.addWidget(U.setting_row(
                "אנימציה", s, "מלאה = מחוון זכוכית נודד ותנועה קפיצית · מופחתת = מיד · כבויה = ללא"))
            s = U.Segmented([(k, P.BACKDROP_LABELS[k]) for k in P.BACKDROPS], self.p["backdrop"],
                            self.accent())
            s.set_factor(self.factor())
            s.changed.connect(lambda v: commit("backdrop", v, True))
            lay.addWidget(U.setting_row(
                "רקע החלון", s,
                "זכוכית/אקריליק/מיקה = טשטוש אמיתי של Windows מאחורי החלון · אטום = בלי"))
            sw = QWidget()
            swl = QHBoxLayout(sw)
            swl.setContentsMargins(0, 0, 0, 0)
            swl.setSpacing(8)
            for name, hexc in P.ACCENTS.items():
                b = U.swatch(hexc, name == self.p["accent"])
                b.setToolTip(name)
                b.clicked.connect(lambda _=False, n=name: commit("accent", n, True))
                swl.addWidget(b)
            swl.addStretch(1)
            lay.addWidget(U.setting_row("צבע מבטא", sw, "צובע את הרקע, המחוון, הבוהק והברים"))
            sl = U.slider_row(75, 125, 5, int(self.p["text_size"]))
            lb = QLabel(f"{self.p['text_size']}%")
            lb.setMinimumWidth(48)
            sl.valueChanged.connect(lambda v: lb.setText(f"{5 * round(v / 5)}%"))
            sl.sliderReleased.connect(
                lambda: commit("text_size", 5 * round(sl.value() / 5), True))
            lay.addWidget(U.setting_row("גודל טקסט", U.row(sl, lb), "75%–125%, כמו בלאנצ'ר"))
            s = U.Segmented([(k, P.SIDEBAR_LABELS[k]) for k in P.SIDEBAR_MODES], self.p["sidebar"],
                            self.accent())
            s.set_factor(self.factor())
            s.changed.connect(lambda v: commit("sidebar", v, True))
            lay.addWidget(U.setting_row("סרגל צד", s))
            c1 = U.checkbox("אפקט גל בלחיצה", self.p.get("ripple", True))
            c1.toggled.connect(lambda v: commit("ripple", v))
            c2 = U.checkbox("פס כותרת מותאם (בהפעלה הבאה)", self.p.get("custom_titlebar", True))
            c2.toggled.connect(lambda v: commit("custom_titlebar", v))
            lay.addWidget(U.setting_row("פרטים", U.row(c1, c2, None)))

            lay.addWidget(U.caption("מה מוצג ומה מוסתר"))
            gw = QWidget()
            gl = QHBoxLayout(gw)
            gl.setContentsMargins(0, 0, 0, 0)
            for gm in self.cfg["games"]:
                c = U.checkbox(gm["id"], self.game_shown(gm["id"]))
                c.toggled.connect(lambda v, i=gm["id"]: (sub("show_games", i, v),
                                                         self.render_all()))
                gl.addWidget(c)
            gl.addStretch(1)
            lay.addWidget(U.setting_row("משחקים", gw, "הסתרה מוציאה אותם מכל הפאנלים והממצאים"))
            cw = QWidget()
            cl = QHBoxLayout(cw)
            cl.setContentsMargins(0, 0, 0, 0)
            for k, label in COLS:
                c = U.checkbox(label, self.p["columns"].get(k, True))
                c.toggled.connect(lambda v, kk=k: (sub("columns", kk, v), self.render_all()))
                cl.addWidget(c)
            cl.addStretch(1)
            lay.addWidget(U.setting_row("עמודות בטבלת הזרמים", cw))
            pw = QWidget()
            pl = QHBoxLayout(pw)
            pl.setContentsMargins(0, 0, 0, 0)
            for k, label in (("cards", "כרטיסי משחק"), ("warnings", "אזהרות"),
                             ("samples", "תרגומים"), ("providers", "ספקים")):
                c = U.checkbox(label, self.p["overview_panels"].get(k, True))
                c.toggled.connect(lambda v, kk=k: (sub("overview_panels", kk, v),
                                                   self.render_all()))
                pl.addWidget(c)
            pl.addStretch(1)
            lay.addWidget(U.setting_row("פאנלים במסך הסקירה", pw))
            fw = QWidget()
            fl = QHBoxLayout(fw)
            fl.setContentsMargins(0, 0, 0, 0)
            c3 = U.checkbox("הסתר ממצאי מידע (429 וכו')", self.p.get("hide_info", False))
            c3.toggled.connect(lambda v: commit("hide_info", v))
            c4 = U.checkbox("הסתר זרמים שסיימו את המנה", self.p.get("hide_finished", False))
            c4.toggled.connect(lambda v: commit("hide_finished", v))
            fl.addWidget(c3)
            fl.addWidget(c4)
            fl.addStretch(1)
            lay.addWidget(U.setting_row("סינון", fw))

            lay.addWidget(U.caption("רענון"))
            for key, label, lo, hi, step, unit, hint in (
                    ("local_seconds", "רענון מקומי", 5, 60, 5, "שניות",
                     "קריאת הבנקים — זול, אפשר תכוף"),
                    ("remote_seconds", "בדיקת מכונות", 30, 300, 30, "שניות",
                     "ssh לשש מכונות — יקר, לכן נדיר יותר"),
                    ("rate_window_minutes", "חלון חישוב הקצב", 5, 60, 5, "דקות",
                     "חלון קצר מגיב מהר אבל רועש")):
                sl2 = U.slider_row(lo, hi, step, int(self.p[key]))
                v = QLabel(f"{self.p[key]} {unit}")
                v.setMinimumWidth(86)
                sl2.valueChanged.connect(
                    lambda x, vv=v, st=step, un=unit: vv.setText(f"{st * round(x / st)} {un}"))
                sl2.sliderReleased.connect(lambda kk=key, ss=sl2, st=step: (
                    commit(kk, st * round(ss.value() / st)),
                    self.t_local.setInterval(max(5, int(self.p["local_seconds"])) * 1000)))
                lay.addWidget(U.setting_row(label, U.row(sl2, v), hint))

            lay.addWidget(U.caption("מערכת"))
            b1 = QPushButton("פתח תיקיית הגדרות/לוגים")
            b1.clicked.connect(lambda: os.startfile(log_dir()))
            b2 = QPushButton("איפוס הגדרות")
            b2.clicked.connect(lambda: (self.p.update(json.loads(json.dumps(P.DEFAULTS))),
                                        P.save(self.p), self.apply_prefs(),
                                        self.go("settings", False)))
            lay.addWidget(U.setting_row("קבצים", U.row(b1, b2, None), log_dir()))
            lay.addStretch(1)
            return self._scroll(inner)

        # ------------------------------------------------ html blocks
        def _css(self) -> str:
            return (f"body{{color:{U.TEXT};}} .en{{color:{U.MUTED};}} .old{{color:#d29922;}}"
                    f" .new{{color:{U.GREEN};}} .id{{color:{self.accent()};}}"
                    f" td{{padding:3px 9px;}} b{{color:{U.TEXT};}}")

        def findings_html(self, findings: list[dict]) -> str:
            if not findings:
                return (f"<body><p style='color:{U.GREEN}'><b>אין בעיות.</b> כל הזרמים חיים, "
                        f"המיזוג עובד, ואין workers מיותרים.</p></body>")
            h = [f"<body><style>{self._css()}</style>"]
            for x in findings:
                c = SEV_COLOR[x["sev"]]
                h.append(
                    f"<p style='margin:0 0 11px 0'>"
                    f"<span style='background:{c};color:#0a0a14;padding:1px 8px;border-radius:7px;"
                    f"font-weight:700'>{SEV_TEXT[x['sev']]}</span> <b>{_esc(x['title'])}</b> "
                    f"<span style='color:{U.MUTED}'>· {_esc(x['scope'])}</span><br>"
                    f"{_esc(x['reason'])}"
                    + (f"<br><span style='color:{U.MUTED}'>מה עושים: {_esc(x['action'])}</span>"
                       if x.get("action") else "") + "</p>")
            return "".join(h) + "</body>"

        def samples_html(self, limit: int) -> str:
            feed = [s for s in self.feed if self.game_shown(s["game"])]
            if self.filters["samples"] == "fix":
                feed = [s for s in feed if s["iss"] != "ok"]
            feed = feed[:limit]
            if not feed:
                return (f"<body><p style='color:{U.MUTED}'>ממתין לשורות חדשות בבנק… "
                        f"(מתעדכן אחרי כל מיזוג — הכפתורים בכותרת)</p></body>")
            h = [f"<body><style>{self._css()}</style>"]
            for s in feed:
                fixed = s["iss"] != "ok" and s["he_new"] and s["he_new"] != s["he_old"]
                chip = U.GREEN if s["iss"] != "ok" else U.MUTED
                body = ((f"<span class='old'>לפני: {_esc(s['he_old'])}</span><br>"
                         f"<span class='new'>אחרי: {_esc(s['he_new'])}</span>") if fixed else
                        (f"<span class='new'>{_esc(s['he_new'] or s['he_old'])}</span>"
                         f"<span style='color:{U.MUTED}'> · אושר ללא שינוי</span>"))
                h.append(
                    f"<p style='margin:0 0 10px 0;border-bottom:1px solid rgba(255,255,255,0.06);"
                    f"padding-bottom:7px'><span class='id'>"
                    f"#{s.get('num', 0)} · {s['game']}·{s['machine']}·{s['provider']}</span> "
                    f"<span style='color:{chip}'>[{_esc(s['iss'])}]</span> "
                    f"<span style='color:{U.MUTED}'>"
                    f"{time.strftime('%H:%M', time.localtime(s['t']))} · "
                    f"{_esc(str(s['id'])[-40:])}</span><br>"
                    + (f"<span class='en' dir='ltr'>{_esc(s['en'])}</span><br>" if s["en"] else "")
                    + body + "</p>")
            return "".join(h) + "</body>"

        def providers_html(self, snap: dict) -> str:
            th = self.cfg["thresholds"]
            per: dict[str, dict] = {}
            for s in self.visible_streams(snap):
                d = per.setdefault(s["provider"],
                                   {"alive": 0, "n": 0, "rate": 0.0, "thr": 0, "rem": 0})
                d["n"] += 1
                d["alive"] += 1 if s["alive"] >= 1 else 0
                d["rate"] += s["rate"] or 0.0
                d["rem"] += s["remaining"]
                if "חנוק" in H.stream_state(s, th)[0]:
                    d["thr"] += 1
            h = [f"<body><style>{self._css()}</style><table>"]
            for p, d in per.items():
                h.append(f"<tr><td><b>{p}</b></td><td>{d['alive']}/{d['n']} חיים</td>"
                         f"<td><b>{d['rate']:.1f}</b>/דק'</td><td>נשאר {d['rem']:,}</td>"
                         f"<td style='color:#d29922'>{d['thr']} חנוקים</td></tr>")
            return "".join(h) + "</table></body>"

        def machines_html(self, snap: dict) -> str:
            h = [f"<body><style>{self._css()}</style><table>"]
            for g in snap["games"]:
                if not self.game_shown(g["id"]):
                    continue
                for m in g["machines"]:
                    pr = m.get("probe") or {}
                    if not pr.get("ok"):
                        h.append(f"<tr><td><b>{m['name']}</b></td><td colspan=5 "
                                 f"style='color:{U.RED}'>לא נענתה: "
                                 f"{_esc(str(pr.get('error', '—'))[:90])}</td></tr>")
                        continue
                    vm = m.get("vm")
                    vmtxt = "—" if not vm else ("רץ" if vm in (snap.get("vbox") or set())
                                                else "לא רץ")
                    tsk = "—" if m.get("no_task") else pr.get("task", "?")
                    h.append(f"<tr><td><b>{m['name']}</b></td><td>{g['id']}</td>"
                             f"<td>{pr.get('free_gb', '?')} GB</td><td>task {tsk}</td>"
                             f"<td>VM {vmtxt}</td><td>legacy {pr.get('legacy', 0)} · "
                             f"זומבים {len(pr.get('zombies') or [])}</td></tr>")
            return "".join(h) + "</table></body>"

    app = QApplication(sys.argv)
    global FAMILY
    FAMILY = U.load_fonts()
    app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    fo = QFont(FAMILY)
    fo.setPointSizeF(10.5)
    app.setFont(fo)
    w = Dash(cfg)
    w.show()
    return app.exec()


def main() -> int:
    # cp1255 stdout is the project's oldest banana skin: the first Hebrew character printed to a
    # redirected pipe raises UnicodeEncodeError and killed this tool's --once mode in silence.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    try:
        cfg = load_cfg()
        if "--once" in sys.argv:
            print(once_text(cfg))
            return 0
        return run_gui(cfg)
    except SystemExit:
        raise
    except Exception:
        tb = traceback.format_exc()
        with open(os.path.join(log_dir(), "dash.log"), "a", encoding="utf-8") as fh:
            fh.write(f"\n--- {time.strftime('%F %T')} FATAL\n{tb}")
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox
            a = QApplication.instance() or QApplication(sys.argv)
            QMessageBox.critical(None, "מצב הצי — שגיאה", tb[-1500:])
            del a
        except Exception:
            print(tb)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
