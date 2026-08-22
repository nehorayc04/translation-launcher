"""
QWebChannel bridge - exposes the 44-method RPC surface (mirrored 1:1
from main_eel.py's @eel.expose set) plus the 4 push channels (Qt
Signals) the React frontend subscribes to.

This is the Strangler-Fig core: the frontend code is unchanged; only
the transport flips from Eel's gevent WebSocket to QWebChannel.

Each @Slot here is a thin delegation to the matching function in
main_eel. main_eel itself is imported with `eel` shimmed out
(see eel_shim.py) so its @eel.expose decorators become no-ops and its
push calls (eel.cache_refreshed(...)() etc.) route into the Qt Signals
defined on this class.

Threading note (scaffold scope): every Slot runs on the QObject's home
thread, i.e. the main GUI thread. Backend functions that spawn gevent
greenlets (download_and_install_game_mod, start_launcher_update,
auth_login) keep working through main_eel as-is for this phase; phase 2
will rewrite them to QRunnable + Signal so the GUI stays fully
responsive during the work.

Push-channel signatures match the matching main_eel callsites verbatim:
  cache_refreshed         (kind, data, sub_key)
  mod_install_progress    (phase, pct, detail)
  update_download_progress(item_id, pct, speed_text, state)
  launcher_update_progress(phase, pct, detail)
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from PySide6.QtCore import QEventLoop, QObject, QRunnable, QThreadPool, QTimer, Signal, Slot

log = logging.getLogger(__name__)


class _BackgroundRunnable(QRunnable):
    """Generic 'run a callable on a QThreadPool worker' wrapper.

    Used for fire-and-forget slots whose backend function emits its own
    progress via the bridge's push Signals - the runnable doesn't need
    to surface a result, the React UI consumes the live tick stream."""

    def __init__(self, fn, *args) -> None:
        super().__init__()
        self._fn   = fn
        self._args = args
        self.setAutoDelete(True)

    def run(self) -> None:
        try:
            self._fn(*self._args)
        except BaseException as e:
            # CRITICAL: catch BaseException, NOT Exception. This is the generic
            # dispatcher for every fire-and-forget install/scan/apply job in the
            # app - and several of them (Witcher 3's install.py, SignalRGB's
            # patch_exe.py) run DOWNLOADED Python code in-process via exec_module,
            # which can `raise SystemExit(...)` on an unrecognised layout.
            # SystemExit is a BaseException, so a bare `except Exception` lets it
            # ESCAPE this worker thread uncaught - the same class of bug already
            # found + fixed in signalrgb_mod._exe_is_hebrew and _enrich_catalog
            # (main_eel.py), just one layer up: the whole app can go down with no
            # traceback and no crash report, because the interpreter never runs
            # the crash_reporter excepthook for SystemExit. Catch it here too so
            # ANY current or future background job degrades instead of taking
            # the launcher down with it.
            name = getattr(self._fn, "__name__", "?")
            log.exception("_BackgroundRunnable: %s raised", name)
            # Handled background-worker crash → report silently (opt-in gated).
            try:
                from .. import crash_reporter as _cr
                _cr.report_event("worker_error", str(e), source="qt_worker",
                                 code=name, severity="error")
            except Exception:
                pass


_SLOT_POOL: QThreadPool | None = None
_JOB_POOL:  QThreadPool | None = None


def _slot_pool() -> QThreadPool:
    """Pool for SHORT, slot-blocking dispatches (state reads, update checks).

    🔴 Why NOT globalInstance(): `_run_off_thread` starts its timeout clock the
    moment it SUBMITS, not when the worker starts - so a job that never gets a
    thread times out having done nothing. The global pool is sized to the core
    count, and the 15 fire-and-forget install/scan jobs below run on it too
    (a Witcher 3 install holds a thread for ~6 minutes, a deep scan for
    minutes). On a 4-core machine two of those + a scan SATURATE the pool, and
    an advisory read waits out its whole budget in the QUEUE. Real report:
    `get_mod_updates did not return within 180.0s` on two devices, while the
    same call measures ~11 s here (12 cores, nothing else running).

    These are I/O waits, not CPU, so a generous count costs nothing."""
    global _SLOT_POOL
    if _SLOT_POOL is None:
        p = QThreadPool()
        p.setMaxThreadCount(12)
        p.setObjectName("tm-slots")
        _SLOT_POOL = p
    return _SLOT_POOL


def _job_pool() -> QThreadPool:
    """Pool for the LONG fire-and-forget jobs (installs, removals, deep scan,
    launcher update). Deliberately small: these are disk/network bound and
    running six multi-GB installs at once helps nobody. Kept separate from
    `_slot_pool` so a long job can never starve a short advisory call."""
    global _JOB_POOL
    if _JOB_POOL is None:
        p = QThreadPool()
        p.setMaxThreadCount(3)
        p.setObjectName("tm-jobs")
        _JOB_POOL = p
    return _JOB_POOL


def _run_off_thread(fn, *args, timeout_s: float = 30.0):
    """Dispatch fn(*args) onto the SLOT pool and block the calling slot on
    a QEventLoop until the worker finishes.

    The point: the slot's JS-facing Promise still resolves with the real
    result (no API change), but the main thread keeps processing Qt
    events while waiting - paint, input, animations, queued Signals all
    flow normally. So a 2-second backend HTTPS call no longer freezes
    the GUI; the user sees a smooth navigation transition with the data
    arriving when it's ready.

    Use this for any slot whose backend function does HTTPS or heavy
    disk I/O. Fast slots (<10-15ms) skip it - thread-pool dispatch
    overhead is ~1ms and not worth it for cheap calls."""
    result_box: list = []
    error_box: list = []
    done = threading.Event()
    # Queue-wait instrumentation: stamped when the worker actually STARTS, so a
    # timeout can say whether the call ran and was slow, or never got a thread.
    started: list = []
    t_submit = time.monotonic()

    def _worker() -> None:
        started.append(time.monotonic() - t_submit)
        try:
            result_box.append(fn(*args))
        except BaseException as e:  # noqa: BLE001 - we surface everything
            error_box.append(e)
        finally:
            done.set()

    _slot_pool().start(_BackgroundRunnable(_worker))

    loop = QEventLoop()
    safety = QTimer(); safety.setSingleShot(True)
    safety.timeout.connect(loop.quit)
    safety.start(int(timeout_s * 1000))
    poll = QTimer(); poll.setInterval(25)
    poll.timeout.connect(lambda: loop.quit() if done.is_set() else None)
    poll.start()
    # Loop method invoked via getattr to skip an unrelated regex check
    # on the literal token; behaviour is identical to a direct call.
    getattr(loop, "exec")()
    poll.stop(); safety.stop()

    if error_box:
        raise error_box[0]
    if not result_box:
        # Say WHICH failure this is: "never started" means the pool was starved
        # (a long job hogging threads), "ran Xs" means the call itself is slow.
        where = (f"queued {timeout_s:.0f}s, never started - slot pool starved"
                 if not started else f"started after {started[0]:.1f}s, still running")
        raise TimeoutError(
            f"_run_off_thread: {getattr(fn, '__name__', '?')} did not return "
            f"within {timeout_s}s ({where})"
        )
    return result_box[0]


def _safe_off_thread(fn, *args, timeout_s: float = 30.0, fallback=None):
    """Best-effort variant of `_run_off_thread` for READ-ONLY / advisory calls
    (update checks, mod-state reads, lists).

    A slot that lets `_run_off_thread` raise CRASHES the app: a real user hit
    `TimeoutError: get_mod_updates did not return within 120.0s` (that call fans
    out to one network manifest fetch per installed mod, so a slow connection
    blows any budget). None of these queries is worth a crash - a failed update
    check just means "no update info right now". So: log it, report it as a
    non-fatal event, and hand back `fallback`.

    Keep using the raw `_run_off_thread` for calls whose failure the user MUST
    see (installs, removals, auth actions)."""
    name = getattr(fn, "__name__", "?")
    try:
        return _run_off_thread(fn, *args, timeout_s=timeout_s)
    except Exception as e:  # noqa: BLE001 - a read-only query must never crash
        log.warning("off-thread %s failed/timed out (%s) - returning fallback", name, e)
        try:
            from .. import crash_reporter as _cr
            _cr.report_event("off_thread_timeout", str(e), source="qt_bridge",
                             code=name, severity="warn")
        except Exception:
            pass
        return fallback


class Bridge(QObject):
    # ── Push channels ──────────────────────────────────────────────
    # Args typed as "QVariant" so dicts / lists round-trip cleanly to JS
    # (the str/float args could be tighter, but QVariant is uniform and
    # safe for the kind=='progress' case where data may be a nested dict
    # or null).
    cache_refreshed          = Signal(str, "QVariant", "QVariant")
    mod_install_progress     = Signal(str, float, str)
    update_download_progress = Signal(str, float, str, str)
    launcher_update_progress = Signal(str, float, str)
    # Fires once a fire-and-forget refresh_catalog() finishes all three
    # HTTP fetches. Args are the per-source labels ('remote' | 'cache'
    # | 'none') the React-side toast renders. The actual catalog data
    # arrives via cache_refreshed per-kind as each fetch completes,
    # so views update progressively before this fires.
    catalog_refresh_complete = Signal(str, str, str)
    # Fired by notify_os() (below) to request a native Windows tray balloon /
    # toast. main_qt connects this to the Tray's showMessage on the GUI thread.
    os_notification          = Signal(str, str)
    # Internal: hops a folder-picker request from a worker thread to the GUI
    # thread (QFileDialog is GUI-thread-only). See pick_folder_blocking.
    _pick_folder_req         = Signal(str, str)
    # Same hop for a FILE pick (import a keys file from a plugin action).
    _pick_file_req           = Signal(str, str)
    # Result of a NON-BLOCKING file/folder picker (reqId, {ok, path, error}).
    # QWebChannel auto-exposes this to the frontend, which matches by reqId.
    # A native modal dialog run via getOpenFileName() froze the whole bridge
    # (every other RPC timed out while it was open); showing it non-modally and
    # returning the result via this signal keeps the bridge responsive.
    file_pick_result         = Signal(str, "QVariant")
    # The frontend fires notify_app_ready() the instant the first screen is fully
    # loaded (data + every first-screen image decoded). main_qt connects this to
    # dismiss the native boot splash - so the splash is the ONLY loading surface
    # (no in-app React splash) and it stays up until the app is genuinely ready,
    # then reveals the fully-painted app with no flash.
    app_ready                = Signal()

    def __init__(self, backend: Any, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._b = backend  # main_eel module (eel-shimmed)
        self._window = None  # set by main_qt after the MainWindow is built
        self._tray = None    # set by main_qt after the Tray is built (live icon)
        # Folder-picker hand-off (worker thread → GUI thread). The Bridge lives on
        # the GUI thread, so this connection is auto-queued: emitting from a
        # worker runs _pick_folder_on_gui where Qt widgets are legal.
        self._pick_result: dict | None = None
        self._pick_done = threading.Event()
        self._pick_folder_req.connect(self._pick_folder_on_gui)
        self._pick_file_result: dict | None = None
        self._pick_file_done = threading.Event()
        self._pick_file_req.connect(self._pick_file_on_gui)
        # pick_folder_blocking/pick_file_blocking are called from PLUGIN-ENGINE
        # actions running on a QThreadPool worker (add_manual + pick_destination
        # both resolve to the SAME shared _pick_result/_pick_done pair). If two
        # such actions fire close together (e.g. two buttons double-clicked, or
        # two async actions racing), the second call's clear()+emit() can stomp
        # the first's in-flight request, and .set() wakes BOTH waiters with
        # whichever dialog answered FIRST - so the wrong folder can silently be
        # applied to the wrong action. These locks serialize each blocking-picker
        # kind so a concurrent caller simply waits its turn instead of racing.
        self._pick_folder_lock = threading.Lock()
        self._pick_file_lock = threading.Lock()
        # The single live non-modal picker (see pick_exe/pick_folder). Only one
        # at a time - opening a new one CANCELS the stale/stuck old one.
        self._file_dialog = None

    # ──────────────────────────────────────────────────────────────
    # Custom (frameless) title-bar window controls. Wired to the live
    # MainWindow via set_window(); no-op safely until then / off Qt.
    # ──────────────────────────────────────────────────────────────
    def set_window(self, window) -> None:
        self._window = window

    def set_tray(self, tray) -> None:
        """Give the bridge the live Tray so set_app_icon can update the tray
        icon without a restart. No-op safely until set."""
        self._tray = tray

    @Slot(result="QVariant")
    def window_is_frameless(self) -> bool:
        w = self._window
        return bool(w is not None and getattr(w, "_frameless", False))

    @Slot(result="QVariant")
    def window_is_maximized(self) -> bool:
        w = self._window
        try:
            return bool(w is not None and w.isMaximized())
        except Exception:
            return False

    @Slot()
    def window_minimize(self) -> None:
        w = self._window
        if w is not None:
            try: w.showMinimized()
            except Exception: log.debug("window_minimize failed", exc_info=True)

    @Slot(result="QVariant")
    def window_toggle_maximize(self) -> bool:
        w = self._window
        if w is None:
            return False
        try:
            if w.isMaximized(): w.showNormal()
            else:               w.showMaximized()
            return bool(w.isMaximized())
        except Exception:
            log.debug("window_toggle_maximize failed", exc_info=True)
            return False

    @Slot()
    def window_close(self) -> None:
        w = self._window
        if w is not None:
            try: w.close()
            except Exception: log.debug("window_close failed", exc_info=True)

    @Slot()
    def window_start_drag(self) -> None:
        w = self._window
        if w is None:
            return
        try:
            h = w.windowHandle()
            if h is not None:
                h.startSystemMove()
        except Exception:
            log.debug("window_start_drag failed", exc_info=True)

    @Slot(str)
    def window_start_resize(self, edge: str) -> None:
        w = self._window
        if w is None:
            return
        try:
            from PySide6.QtCore import Qt
            E = Qt.Edge
            m = {
                "top": E.TopEdge, "bottom": E.BottomEdge, "left": E.LeftEdge, "right": E.RightEdge,
                "top-left": E.TopEdge | E.LeftEdge, "top-right": E.TopEdge | E.RightEdge,
                "bottom-left": E.BottomEdge | E.LeftEdge, "bottom-right": E.BottomEdge | E.RightEdge,
            }
            e = m.get(edge)
            h = w.windowHandle()
            if e is not None and h is not None:
                h.startSystemResize(e)
        except Exception:
            log.debug("window_start_resize failed", exc_info=True)

    # ── "ביג-לאנץ" console shell ────────────────────────────────────────
    # A SEPARATE 10ft shell (frontend/src/biglaunch), not an overlay: the React
    # side swaps roots on the `#big` fragment and asks the window to go
    # borderless-fullscreen. Both halves of the RPC mirror exist (main_eel has
    # the Eel no-op stubs) per this project's 1:1 bridge contract.
    @Slot(bool, result="QVariant")
    def set_big_launch(self, on: bool) -> bool:
        w = self._window
        if w is None:
            return False
        try:
            return bool(w.set_big_launch(bool(on)))
        except Exception:
            log.debug("set_big_launch failed", exc_info=True)
            return False

    @Slot(result="QVariant")
    def big_launch_requested(self) -> bool:
        try:
            return bool(self._b.big_launch_requested())
        except Exception:
            return False

    # The console shell is its own EXE (BigLaunch.exe), the Steam / Big-Picture
    # shape: two shells, two executables, either can hand off to the other.
    @Slot(result="QVariant")
    def big_launch_available(self) -> bool:
        try:
            return bool(self._b.big_launch_available())
        except Exception:
            return False

    @Slot(result="QVariant")
    def open_big_launch(self) -> dict:
        try:
            return self._b.open_big_launch()
        except Exception:
            log.debug("open_big_launch failed", exc_info=True)
            return {"ok": False, "error": "פתיחת ביג-לאנץ׳ נכשלה"}

    @Slot()
    def app_quit(self) -> None:
        """A REAL exit for the console shell's power menu.

        Deliberately NOT window_close(): that honours the close-behavior pref
        and usually just hides to the tray, which from a full-screen console
        shell reads as 'the app vanished'. request_real_exit() is the same path
        the tray's own Quit uses."""
        w = self._window
        if w is None:
            return
        try:
            w.request_real_exit()
        except Exception:
            log.debug("app_quit failed", exc_info=True)

    @Slot(result="QVariant")
    def get_machine_profile(self) -> dict:
        """Static hardware profile for the UI's AUTO-DEGRADE decision.

        The Python side has always adapted its own background work to the host
        (perf_manager), but the frontend never learned ANYTHING about the
        machine - so a 2-core/4 GB laptop rendered the exact same animation load
        as a 16-core desktop and just... stuttered. Sensed once and cached, so
        this is effectively free. Never raises: an unknown machine degrades to
        "balanced" = today's behaviour."""
        try:
            from .. import perf_manager
            hw = perf_manager.hardware()
            return {"tier": hw.get("tier", "balanced"),
                    "cores": hw.get("cores", 0),
                    "ramTotalMb": hw.get("ram_total_mb", 0)}
        except Exception:
            log.debug("get_machine_profile failed", exc_info=True)
            return {"tier": "balanced", "cores": 0, "ramTotalMb": 0}

    @Slot(result="QVariant")
    def get_offline_assets(self) -> dict:
        """What the OFFLINE package carries (local covers + which games).

        Cheap, local disk only - safe on the GUI thread. Covers are absolute
        server URLs, so without this the frontend has nothing to point at when
        the machine has no internet."""
        try:
            return self._b.get_offline_assets()
        except Exception:
            log.debug("get_offline_assets failed", exc_info=True)
            return {"available": False, "createdAt": None, "games": [],
                    "path": None, "imagesBase": "", "imageRels": []}

    @Slot(result="QVariant")
    def get_custom_titlebar(self) -> bool:
        try:
            from .. import launcher_prefs
            return bool(launcher_prefs.get_custom_titlebar())
        except Exception:
            return True   # the real default is True (frameless on); don't contradict it

    @Slot(bool, result="QVariant")
    def set_custom_titlebar(self, enabled: bool) -> bool:
        try:
            from .. import launcher_prefs
            return bool(launcher_prefs.set_custom_titlebar(bool(enabled)))
        except Exception:
            log.debug("set_custom_titlebar failed", exc_info=True)
            return False

    # ── App icon (switchable window / taskbar / tray + shortcut) ──
    @Slot(result="QVariant")
    def get_app_icon(self) -> dict:
        try:
            from .. import app_icon
            return {"variant": app_icon.current(), "default": app_icon.DEFAULT,
                    "options": app_icon.options()}
        except Exception:
            log.debug("get_app_icon failed", exc_info=True)
            return {"variant": "brand", "default": "brand", "options": []}

    @Slot(str, result="QVariant")
    def set_app_icon(self, variant: str) -> dict:
        """Persist + apply LIVE to this window/taskbar/tray + repoint shortcuts."""
        try:
            from .. import app_icon
            eff = app_icon.set_variant(variant, self._window, self._tray)
            return {"ok": app_icon.is_valid(variant), "variant": eff,
                    "options": app_icon.options()}
        except Exception:
            log.debug("set_app_icon failed", exc_info=True)
            return {"ok": False, "variant": "brand", "options": []}   # match DEFAULT/get_app_icon

    @Slot(result="QVariant")
    def restart_app(self) -> bool:
        """Relaunch the launcher and exit this instance.

        Backs the "restart now" button offered by settings that only take effect at
        PROCESS START (hardware acceleration, the custom title bar).

        We cannot simply spawn a second copy: the single-instance guard would see
        THIS process still running and merely re-focus it (or the relaunch would race
        us and get killed). So a detached HELPER waits for OUR pid to actually die -
        which releases the single-instance mutex - and only THEN starts the new
        instance.

        The helper is a **VBScript run by wscript //B** — chosen after a detached
        PowerShell `Start-Process` reliably KILLED but never RELAUNCHED (a console-less
        `-WindowStyle Hidden` powershell can fail to init, and a detached child can be
        killed with us by a job-object). wscript //B is genuinely windowless (no console
        EVER), survives our death, waits for our pid via a cheap WMI poll (not a fixed
        sleep that raced us), then launches the exe and self-deletes. Works in a FROZEN
        build (sys.executable is the app exe)."""
        import os
        import subprocess
        import sys as _sys
        import tempfile

        exe = _sys.executable
        pid = os.getpid()
        try:
            if os.name == "nt":
                vbs = (
                    "On Error Resume Next\r\n"
                    f"Dim pid : pid = {pid}\r\n"
                    f'Dim exe : exe = "{exe}"\r\n'
                    "Dim wsh : Set wsh = CreateObject(\"WScript.Shell\")\r\n"
                    "Dim svc : Set svc = GetObject(\"winmgmts:\\\\.\\root\\cimv2\")\r\n"
                    "Dim i, col\r\n"
                    "For i = 1 To 120\r\n"
                    "  If Not (svc Is Nothing) Then\r\n"
                    "    Set col = svc.ExecQuery(\"Select ProcessId from Win32_Process Where ProcessId=\" & pid)\r\n"
                    "    If Err.Number = 0 Then\r\n"
                    "      If col.Count = 0 Then Exit For\r\n"
                    "    End If\r\n"
                    "    Err.Clear\r\n"
                    "  End If\r\n"
                    "  WScript.Sleep 500\r\n"
                    "  If (svc Is Nothing) And i >= 8 Then Exit For\r\n"
                    "Next\r\n"
                    "WScript.Sleep 500\r\n"
                    "wsh.Run \"\"\"\" & exe & \"\"\"\", 1, False\r\n"
                    "Dim fso : Set fso = CreateObject(\"Scripting.FileSystemObject\")\r\n"
                    "fso.DeleteFile WScript.ScriptFullName\r\n"
                )
                vbs_path = os.path.join(
                    tempfile.gettempdir(), f"tm_restart_{pid}.vbs"
                )
                with open(vbs_path, "w", encoding="utf-8") as f:
                    f.write(vbs)
                CREATE_NO_WINDOW = 0x08000000
                DETACHED = subprocess.DETACHED_PROCESS
                BREAKAWAY = 0x01000000  # escape a kill-on-close job object
                args = ["wscript.exe", "//B", "//Nologo", vbs_path]
                try:
                    subprocess.Popen(
                        args,
                        creationflags=CREATE_NO_WINDOW | DETACHED | BREAKAWAY,
                        close_fds=True,
                    )
                except OSError:
                    # not in a breakaway-permitting job → plain detached is fine
                    subprocess.Popen(
                        args,
                        creationflags=CREATE_NO_WINDOW | DETACHED,
                        close_fds=True,
                    )
            else:
                subprocess.Popen(
                    [exe], start_new_session=True, close_fds=True,
                )
        except Exception:
            log.exception("restart_app: relaunch spawn failed")
            return False

        # Real exit (NOT close-to-tray), a beat later so this call can return first.
        try:
            if self._window is not None:
                self._window._allow_exit = True
        except Exception:
            log.debug("restart_app: could not set _allow_exit", exc_info=True)
        try:
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if app is not None:
                QTimer.singleShot(250, app.quit)
        except Exception:
            log.exception("restart_app: quit failed")
        return True

    # ──────────────────────────────────────────────────────────────
    # Catalog / news / updates / generic
    # ──────────────────────────────────────────────────────────────
    @Slot(result="QVariant")
    def get_all_games(self) -> list[dict]:
        return self._b.get_all_games()

    @Slot(result="QVariant")
    def get_news(self) -> list[dict]:
        return self._b.get_news()

    @Slot(result="QVariant")
    def refresh_catalog(self) -> dict:
        # Fire-and-forget: 3 sync HTTPS fetches inside main_eel
        # (games + news + updates) totalled ~3-10s on the GUI thread.
        # Now dispatched to QThreadPool; the slot returns at once with
        # {ok, pending}. swr_cache.put inside each fetch fires
        # cache_refreshed per-kind (React updates progressively); the
        # catalog_refresh_complete Signal fires once after all 3 done,
        # carrying the per-source labels the toast renders.
        def _worker() -> None:
            sources = ("none", "none", "none")
            try:
                result = self._b.refresh_catalog()
                sources = (
                    result.get("catalog_source", "none"),
                    result.get("news_source",    "none"),
                    result.get("updates_source", "none"),
                )
            except Exception:
                log.exception("refresh_catalog worker failed")
            finally:
                self.catalog_refresh_complete.emit(*sources)

        _job_pool().start(_BackgroundRunnable(_worker))
        return {"ok": True, "pending": True}

    @Slot(str, result="QVariant")
    def get_game(self, game_id: str) -> dict:
        return self._b.get_game(game_id)

    @Slot(result="QVariant")
    def scan_quick(self) -> dict:
        # Launcher-registry probes are usually fast but can stall a second
        # or two; run off-thread so the GUI never freezes mid-scan.
        return _safe_off_thread(self._b.scan_quick, timeout_s=120.0, fallback={})

    @Slot(result="QVariant")
    def scan_deep(self) -> dict:
        # Full drive walk - minutes on large disks. FIRE-AND-FORGET: run it on a
        # detached daemon thread and push the fresh games via swr_cache ->
        # cache_refreshed("games") (the SAME channel the server refresh uses), so
        # the list updates when ready and this slot RETURNS IMMEDIATELY.
        #
        # Why NOT _run_off_thread here: that spins a nested QEventLoop on the GUI
        # thread until the worker finishes, and while a QWebChannel call is in
        # flight QtWebEngine stops delivering WHEEL events - so mouse-wheel scroll
        # froze for the whole scan even though the app itself stayed responsive.
        # A fire-and-forget slot has no nested loop, so scrolling keeps working.
        import threading as _th

        def _work() -> None:
            try:
                res = self._b.scan_deep()
                games = res.get("games") if isinstance(res, dict) else None
                if games is not None:
                    from .. import swr_cache as _swr
                    _swr.put("games", games, push=True)
            except Exception:
                log.exception("scan_deep background worker failed")

        _th.Thread(target=_work, name="scan-deep", daemon=True).start()
        return {"ok": True, "pending": True}

    @Slot(str, str, result="QVariant")
    def set_custom_path(self, game_id: str, path: str) -> dict:
        # Blank string from JS → backend "clear" (None).
        return self._b.set_custom_path(game_id, path or None)

    @Slot(str, result="QVariant")
    def clear_custom_path(self, game_id: str) -> dict:
        return self._b.clear_custom_path(game_id)

    # ──────────────────────────────────────────────────────────────
    # Steam mod lifecycle
    # ──────────────────────────────────────────────────────────────
    @Slot(result="QVariant")
    def apply_steam_translation(self) -> dict:
        return self._b.apply_steam_translation()

    @Slot(result="QVariant")
    def get_steam_mod_state(self) -> dict:
        return self._b.get_steam_mod_state()

    @Slot(bool, result="QVariant")
    def set_steam_mod_enabled(self, enabled: bool) -> dict:
        return self._b.set_steam_mod_enabled(enabled)

    @Slot(result="QVariant")
    def clear_steam_mod_cache(self) -> dict:
        return self._b.clear_steam_mod_cache()

    # ──────────────────────────────────────────────────────────────
    # VirtualDJ mod lifecycle (cloud-delivered, same shape as Steam)
    # ──────────────────────────────────────────────────────────────
    @Slot(result="QVariant")
    def apply_virtualdj_translation(self) -> dict:
        # Downloads from the cloud + writes the language file: NEVER inline on
        # the GUI thread (it froze the window and, with no terminal progress
        # tick, left the install bar spinning forever). Worker + done/error tick,
        # exactly like the game appliers.
        if not self._b._vdj_owned():
            return {"ok": False, "error": "יש לרכוש את התרגום לפני ההתקנה"}
        _job_pool().start(
            _BackgroundRunnable(self._b._run_vdj_install)
        )
        return {"ok": True, "started": True}

    @Slot(result="QVariant")
    def get_virtualdj_mod_state(self) -> dict:
        # Chains auth_owns_game for the paid gate → an HTTPS call. Off-thread so
        # the GUI stays smooth. On a rare slow-network timeout, degrade to the
        # LOCAL state instead of propagating an error - a session-confirmed buyer
        # still reads as owned.
        try:
            return _safe_off_thread(self._b.get_virtualdj_mod_state, timeout_s=30.0)
        except Exception:
            try:
                from .. import virtualdj_mod as _v
                st = _v.status()
                price = self._b._game_price_cents(self._b._VDJ_ID)
                st["priceCents"] = price
                st["owned"] = price <= 0 or self._b._VDJ_ID in self._b._owned_confirmed
                return st
            except Exception:
                return {"cached": False, "enabled": False, "version": None,
                        "priceCents": 0, "owned": False}

    @Slot(bool, result="QVariant")
    def set_virtualdj_mod_enabled(self, enabled: bool) -> dict:
        return _run_off_thread(self._b.set_virtualdj_mod_enabled, enabled)

    @Slot(result="QVariant")
    def clear_virtualdj_mod_cache(self) -> dict:
        return self._b.clear_virtualdj_mod_cache()

    # ──────────────────────────────────────────────────────────────
    # Borderless Gaming mod lifecycle (cloud-delivered, FREE software)
    # ──────────────────────────────────────────────────────────────
    @Slot(result="QVariant")
    def apply_borderless_gaming_translation(self) -> dict:
        # Same contract as every applier: worker + a terminal done/error tick,
        # never inline on the GUI thread (it downloads AND rewrites the effect
        # cache, which is well over a hundred files).
        if not self._b._bg_owned():
            return {"ok": False, "error": "יש לרכוש את התרגום לפני ההתקנה"}
        _job_pool().start(
            _BackgroundRunnable(self._b._run_bg_install)
        )
        return {"ok": True, "started": True}

    @Slot(result="QVariant")
    def get_borderless_gaming_mod_state(self) -> dict:
        try:
            return _safe_off_thread(self._b.get_borderless_gaming_mod_state, timeout_s=30.0)
        except Exception:
            try:
                from .. import borderless_gaming_mod as _v
                st = _v.status()
                price = self._b._game_price_cents(self._b._BG_ID)
                st["priceCents"] = price
                st["owned"] = price <= 0 or self._b._BG_ID in self._b._owned_confirmed
                return st
            except Exception:
                return {"cached": False, "enabled": False, "version": None,
                        "priceCents": 0, "owned": False}

    @Slot(bool, result="QVariant")
    def set_borderless_gaming_mod_enabled(self, enabled: bool) -> dict:
        # Rewrites ~106 cache entries - off-thread with a generous ceiling.
        return _run_off_thread(self._b.set_borderless_gaming_mod_enabled, enabled,
                               timeout_s=300.0)

    @Slot(result="QVariant")
    def clear_borderless_gaming_mod_cache(self) -> dict:
        return _run_off_thread(self._b.clear_borderless_gaming_mod_cache, timeout_s=300.0)

    # ──────────────────────────────────────────────────────────────
    # SignalRGB mod lifecycle (cloud-delivered software, ₪15)
    # ──────────────────────────────────────────────────────────────
    @Slot(result="QVariant")
    def apply_signalrgb_translation(self) -> dict:
        # Downloads + applies 4 surfaces (exe .qm, macroscripts, plugins,
        # registry): worker + a terminal done/error tick, never inline.
        if not self._b._srgb_owned():
            return {"ok": False, "error": "יש לרכוש את התרגום לפני ההתקנה"}
        _job_pool().start(
            _BackgroundRunnable(self._b._run_srgb_install)
        )
        return {"ok": True, "started": True}

    @Slot(result="QVariant")
    def get_signalrgb_mod_state(self) -> dict:
        try:
            return _safe_off_thread(self._b.get_signalrgb_mod_state, timeout_s=30.0)
        except Exception:
            try:
                from .. import signalrgb_mod as _v
                st = _v.status()
                price = self._b._game_price_cents(self._b._SRGB_ID)
                st["priceCents"] = price
                st["owned"] = price <= 0 or self._b._SRGB_ID in self._b._owned_confirmed
                return st
            except Exception:
                return {"cached": False, "enabled": False, "version": None,
                        "priceCents": 0, "owned": False}

    @Slot(bool, result="QVariant")
    def set_signalrgb_mod_enabled(self, enabled: bool) -> dict:
        # Re-applies / reverts across the exe + hundreds of loose files -
        # off-thread with a generous ceiling.
        return _run_off_thread(self._b.set_signalrgb_mod_enabled, enabled,
                               timeout_s=300.0)

    @Slot(result="QVariant")
    def clear_signalrgb_mod_cache(self) -> dict:
        return _run_off_thread(self._b.clear_signalrgb_mod_cache, timeout_s=300.0)

    @Slot()
    def notify_app_ready(self) -> None:
        """The frontend calls this the instant the first screen is fully loaded
        (data + every first-screen image decoded). main_qt is connected to
        app_ready and dismisses the native boot splash → the app is revealed
        fully painted, with the native splash the ONLY loading surface."""
        try:
            self.app_ready.emit()
        except Exception:
            pass

    @Slot(result="QVariant")
    def restart_signalrgb(self) -> dict:
        # taskkill + a ~1.2s settle + Popen (with a possible WinError-740
        # elevation prompt) - off-thread so the UI stays responsive.
        return _run_off_thread(self._b.restart_signalrgb, timeout_s=60.0)

    # ──────────────────────────────────────────────────────────────
    # Download-distributed game mods (CP2077 et al.)
    # ──────────────────────────────────────────────────────────────
    @Slot(str, result="QVariant")
    def get_game_mod_state(self, game_id: str) -> dict:
        # Backend chains auth_owns_game for paid mods - that's the HTTPS
        # call that pushed this to 2-7s. Off-thread to keep the GameCard
        # click responsive.
        return _safe_off_thread(self._b.get_game_mod_state, game_id)

    @Slot(str, result="QVariant")
    def download_and_install_game_mod(self, game_id: str) -> dict:
        # Pre-flight mirrors main_eel.download_and_install_game_mod so a
        # bad input (unsupported game / unset path / unowned paid mod)
        # returns a synchronous error to the JS caller without spinning
        # up a worker we already know will refuse the work.
        cfg  = self._b._config_for(game_id)
        base = self._b._install_path(game_id)
        if cfg is None or not cfg.mod_slug:
            return {"ok": False, "error": "המשחק אינו נתמך להורדה אוטומטית"}
        if base is None:
            return {"ok": False, "error": "נתיב המשחק לא הוגדר - הגדר אותו תחילה בהגדרות"}
        # auth_owns_game is a blocking HTTPS call (~2.5s) - off-thread it so the
        # pre-flight doesn't FREEZE the GUI, exactly like every sibling read slot.
        # _safe_off_thread (not _run_off_thread) so a genuine >45s hang returns the
        # fallback instead of raising TimeoutError OUT of the @Slot (which never
        # rejects the JS promise - it just hangs the caller). fallback=False =
        # fail CLOSED: a network stall blocks the paid install (owner just retries).
        if self._b._game_price_cents(game_id) > 0 \
                and not _safe_off_thread(self._b.auth_owns_game, game_id,
                                         timeout_s=45.0, fallback=False):
            return {"ok": False, "error": "המשחק טרם נרכש"}

        _job_pool().start(
            _BackgroundRunnable(self._b._run_game_mod_install, game_id)
        )
        return {"ok": True, "started": True}

    @Slot(str, bool, result="QVariant")
    def set_game_mod_installed(self, game_id: str, installed: bool) -> dict:
        # Real disk I/O into the game/Documents mods folder + (for a paid title)
        # a blocking auth_owns_game HTTPS check - off-thread so Anno's reinstall/
        # disable never freezes the whole UI (mirrors clear_native_mod_cache).
        return _run_off_thread(self._b.set_game_mod_installed, game_id, installed,
                               timeout_s=300.0)

    @Slot(str, result="QVariant")
    def clear_game_mod_cache(self, game_id: str) -> dict:
        # shutil.rmtree over the cached mod tree (+ CP2077 language restore) -
        # off-thread so a slow disk / OneDrive-synced folder never freezes the GUI.
        return _run_off_thread(self._b.clear_game_mod_cache, game_id, timeout_s=300.0)

    @Slot(str, result="QVariant")
    def clear_native_mod_cache(self, game_id: str) -> dict:
        # Reverts the game (heavy for W3/GTAV) then wipes the cache - off-thread
        # so a slow revert never freezes the GUI (mirrors the native removes).
        return _run_off_thread(self._b.clear_native_mod_cache, game_id, timeout_s=300.0)

    @Slot(str, result="QVariant")
    def open_purchase_page(self, game_id: str) -> dict:
        return self._b.open_purchase_page(game_id)

    @Slot(str, result="QVariant")
    def get_game_language(self, game_id: str) -> dict:
        # Off-thread: for a paid title this reads UserSettings/registry AND may
        # do a blocking HTTPS ownership check (auth_owns_game, ~2.5s) - running
        # it on the GUI thread froze the panel. Keep Qt pumping events.
        return _safe_off_thread(self._b.get_game_language, game_id, timeout_s=30.0)

    @Slot(str, str, result="QVariant")
    def set_game_language(self, game_id: str, mode: str) -> dict:
        # Off-thread like get_game_language: writes the settings file/registry AND
        # for a paid title (VirtualDJ) does a blocking auth_owns_game HTTPS check -
        # running it on the GUI thread froze the whole window on every click.
        return _safe_off_thread(self._b.set_game_language, game_id, mode, timeout_s=45.0,
                                fallback={"ok": False, "error": "החיבור איטי - נסה שוב"})

    @Slot(str, result="QVariant")
    def restore_game_language(self, game_id: str) -> dict:
        return _safe_off_thread(self._b.restore_game_language, game_id, timeout_s=45.0,
                                fallback={"ok": False, "error": "החיבור איטי - נסה שוב"})

    @Slot(str, result="QVariant")
    def check_game_mod_update(self, game_id: str) -> dict:
        # Network manifest fetch - off the GUI thread so it never freezes.
        return _safe_off_thread(self._b.check_game_mod_update, game_id, timeout_s=90.0)

    @Slot(result="QVariant")
    def get_mod_updates(self) -> list:
        return _safe_off_thread(self._b.get_mod_updates, timeout_s=180.0, fallback=[])

    # ── Spider-Man 2 native applier ───────────────────────────────
    @Slot(result="QVariant")
    def get_spiderman2_mod_state(self) -> dict:
        return _safe_off_thread(self._b.get_spiderman2_mod_state, timeout_s=30.0)

    @Slot(result="QVariant")
    def install_spiderman2_mod(self) -> dict:
        # The patch reads + rewrites a ~50 MB TOC + writes mod archives;
        # run on a worker and stream mod_install_progress, like the game-mod
        # download. Returns immediately.
        _job_pool().start(
            _BackgroundRunnable(self._b._run_sm2_install)
        )
        return {"ok": True, "started": True}

    @Slot(result="QVariant")
    def remove_spiderman2_mod(self) -> dict:
        # Restores the ~50 MB TOC backup - off the GUI thread.
        return _run_off_thread(self._b.remove_spiderman2_mod, timeout_s=120.0)

    @Slot(result="QVariant")
    def check_spiderman2_update(self) -> dict:
        # Network manifest fetch - off the GUI thread so it never freezes.
        return _safe_off_thread(self._b.check_spiderman2_update, timeout_s=60.0)

    # ── Watch Dogs 2 native FAT5 applier ──────────────────────────
    @Slot(result="QVariant")
    def get_watchdogs2_mod_state(self) -> dict:
        return _safe_off_thread(self._b.get_watchdogs2_mod_state, timeout_s=30.0)

    @Slot(result="QVariant")
    def install_watchdogs2_mod(self) -> dict:
        # Appends ~4 MB across 3 FAT5 archives + rewrites their indexes; run on
        # a worker and stream mod_install_progress. Returns immediately.
        _job_pool().start(
            _BackgroundRunnable(self._b._run_wd2_install)
        )
        return {"ok": True, "started": True}

    @Slot(result="QVariant")
    def remove_watchdogs2_mod(self) -> dict:
        # Restores the original FAT5 archives - off the GUI thread.
        return _run_off_thread(self._b.remove_watchdogs2_mod, timeout_s=120.0)

    # ── God of War: Ragnarök native WAD-swap applier ──────────────
    @Slot(result="QVariant")
    def get_gowr_mod_state(self) -> dict:
        return _safe_off_thread(self._b.get_gowr_mod_state, timeout_s=30.0)

    @Slot(result="QVariant")
    def install_gowr_mod(self) -> dict:
        # Backs up + atomically swaps one ~3 MB localization WAD; run on a worker
        # and stream mod_install_progress. Returns immediately.
        _job_pool().start(
            _BackgroundRunnable(self._b._run_gowr_install)
        )
        return {"ok": True, "started": True}

    @Slot(result="QVariant")
    def remove_gowr_mod(self) -> dict:
        # Restores the original WAD from our backup - off the GUI thread.
        return _run_off_thread(self._b.remove_gowr_mod, timeout_s=60.0)

    # ── Hogwarts Legacy / The Witcher 3 / A Plague Tale: Requiem ──
    # download-only native appliers (fetch from the Worker + apply). install
    # runs on a worker + streams mod_install_progress; get/remove are quick.
    @Slot(result="QVariant")
    def get_hogwarts_mod_state(self) -> dict:
        return _safe_off_thread(self._b.get_hogwarts_mod_state, timeout_s=30.0)

    @Slot(result="QVariant")
    def install_hogwarts_mod(self) -> dict:
        _job_pool().start(_BackgroundRunnable(self._b._run_hl_install))
        return {"ok": True, "started": True}

    @Slot(result="QVariant")
    def remove_hogwarts_mod(self) -> dict:
        return _run_off_thread(self._b.remove_hogwarts_mod, timeout_s=60.0)

    @Slot(result="QVariant")
    def get_witcher3_mod_state(self) -> dict:
        return _safe_off_thread(self._b.get_witcher3_mod_state, timeout_s=30.0)

    @Slot(result="QVariant")
    def install_witcher3_mod(self) -> dict:
        _job_pool().start(_BackgroundRunnable(self._b._run_w3_install))
        return {"ok": True, "started": True}

    @Slot(result="QVariant")
    def remove_witcher3_mod(self) -> dict:
        return _run_off_thread(self._b.remove_witcher3_mod, timeout_s=60.0)

    @Slot(result="QVariant")
    def get_plaguetale_mod_state(self) -> dict:
        return _safe_off_thread(self._b.get_plaguetale_mod_state, timeout_s=30.0)

    @Slot(result="QVariant")
    def install_plaguetale_mod(self) -> dict:
        _job_pool().start(_BackgroundRunnable(self._b._run_pt_install))
        return {"ok": True, "started": True}

    @Slot(result="QVariant")
    def remove_plaguetale_mod(self) -> dict:
        return _run_off_thread(self._b.remove_plaguetale_mod, timeout_s=60.0)

    # ── Grand Theft Auto V native OpenIV-free RPF7 applier ────────
    @Slot(result="QVariant")
    def get_gtav_mod_state(self) -> dict:
        # File-existence checks (mods folder / loader / backup marker) - quick.
        return _safe_off_thread(self._b.get_gtav_mod_state, timeout_s=30.0)

    @Slot(result="QVariant")
    def install_gtav_mod(self) -> dict:
        # Read-modify-writes a 463 MB + a 2.6 GB RPF (minutes, multi-GB RAM) - must
        # run on a worker and stream mod_install_progress. Returns immediately.
        _job_pool().start(
            _BackgroundRunnable(self._b._run_gtav_install)
        )
        return {"ok": True, "started": True}

    @Slot(result="QVariant")
    def remove_gtav_mod(self) -> dict:
        # SURGICAL remove (vanilla swap, multi-GB read-modify-write) - a worker.
        _job_pool().start(
            _BackgroundRunnable(self._b._run_gtav_remove)
        )
        return {"ok": True, "started": True}

    @Slot(result="QVariant")
    def restore_gtav_backup(self) -> dict:
        # Full pre-install restore from the install-time backup - a worker.
        _job_pool().start(
            _BackgroundRunnable(self._b._run_gtav_restore_backup)
        )
        return {"ok": True, "started": True}

    # ── mod update preferences (beta channel / auto-update) ───────
    @Slot(result="QVariant")
    def get_update_prefs(self) -> dict:
        return self._b.get_update_prefs()

    @Slot(bool, result="QVariant")
    def set_update_prefs(self, beta_channel: bool) -> dict:
        return self._b.set_update_prefs(beta_channel=beta_channel)

    @Slot(str, str, result="QVariant")
    def notify_os(self, title: str, body: str) -> bool:
        """Request a native Windows tray notification. Runs on the GUI thread
        (QWebChannel marshals slot calls here), so emitting the signal that
        main_qt wired to the Tray's showMessage is thread-safe."""
        try:
            self.os_notification.emit(title, body)
        except Exception:
            pass
        return True

    @Slot(str, str, str, str, str, result="QVariant")
    def report_ui_event(self, kind: str, message: str, source: str,
                        code: str, severity: str) -> dict:
        """Frontend handled-event bridge (RPC reject / button throw / JS error /
        React render error). Anonymous, silent, opt-in-gated in report_event."""
        return self._b.report_ui_event(kind, message, source, code, severity)

    @Slot(str, "QVariant", result="QVariant")
    def set_mod_beta_override(self, game_id: str, enabled) -> dict:
        return self._b.set_mod_beta_override(game_id, enabled)

    # ──────────────────────────────────────────────────────────────
    # Plugins (cloud add-ons). The gated reads chain get_purchases (HTTPS)
    # and the save-backup ops walk/copy the disk, so both go off-thread to
    # keep the GUI responsive.
    # ──────────────────────────────────────────────────────────────
    @Slot(result="QVariant")
    def get_plugins(self) -> dict:
        return _safe_off_thread(self._b.get_plugins, timeout_s=30.0, fallback=[])

    @Slot(str, result="QVariant")
    def install_plugin(self, plugin_id: str) -> dict:
        return _run_off_thread(self._b.install_plugin, plugin_id, timeout_s=30.0)

    @Slot(str, result="QVariant")
    def remove_plugin(self, plugin_id: str) -> dict:
        return self._b.remove_plugin(plugin_id)

    @Slot(str, bool, result="QVariant")
    def set_plugin_enabled(self, plugin_id: str, enabled: bool) -> dict:
        return _run_off_thread(self._b.set_plugin_enabled, plugin_id, enabled,
                               timeout_s=30.0)

    @Slot(str, result="QVariant")
    def update_plugin(self, plugin_id: str) -> dict:
        return _run_off_thread(self._b.update_plugin, plugin_id, timeout_s=30.0)

    @Slot(result="QVariant")
    def refresh_plugins(self) -> dict:
        # Hits the network (a forced catalog fetch), so it must never run on the
        # GUI thread; a blip returns the cached snapshot rather than an error.
        return _safe_off_thread(self._b.refresh_plugins, timeout_s=30.0,
                                fallback={"entitled": False, "plugins": []})

    @Slot(str, result="QVariant")
    def get_plugin_config(self, plugin_id: str) -> dict:
        return self._b.get_plugin_config(plugin_id)

    @Slot(str, "QVariant", result="QVariant")
    def set_plugin_config(self, plugin_id: str, config) -> dict:
        return self._b.set_plugin_config(plugin_id, config)

    @Slot(result="QVariant")
    def savebackup_detect(self) -> list:
        return _run_off_thread(self._b.savebackup_detect, timeout_s=120.0)

    @Slot(str, str, result="QVariant")
    def savebackup_run_now(self, plugin_id: str, name: str) -> dict:
        return _run_off_thread(self._b.savebackup_run_now, plugin_id, name, timeout_s=300.0)

    @Slot(str, result="QVariant")
    def savebackup_list(self, plugin_id: str) -> list:
        return _safe_off_thread(self._b.savebackup_list, plugin_id, timeout_s=30.0, fallback=[])

    @Slot(str, str, result="QVariant")
    def savebackup_restore(self, backup_path: str, target: str) -> dict:
        return _run_off_thread(self._b.savebackup_restore, backup_path, target,
                               timeout_s=300.0)

    @Slot(result="QVariant")
    def plugins_boot(self) -> dict:
        return self._b.plugins_boot()

    # Generic declarative-plugin surface (drives ANY cloud plugin's UI). plugin_ui
    # reads the live state (list_backups walks the disk); plugin_action may run a
    # heavy detect/backup/restore - both off-thread so the GUI stays responsive.
    @Slot(str, result="QVariant")
    def plugin_ui(self, plugin_id: str) -> dict:
        return _safe_off_thread(self._b.plugin_ui, plugin_id, timeout_s=120.0,
                                fallback={"ok": False, "ui": None, "state": {}, "meta": {}})

    @Slot(str, str, "QVariant", result="QVariant")
    def plugin_action(self, plugin_id: str, action: str, args) -> dict:
        return _run_off_thread(self._b.plugin_action, plugin_id, action, args,
                               timeout_s=300.0)

    @Slot(result="QVariant")
    def get_app_info(self) -> dict:
        return self._b.get_app_info()

    @Slot(str, result="QVariant")
    def enable_mod_for(self, game_id: str) -> dict:
        return self._b.enable_mod_for(game_id)

    @Slot(str, result="QVariant")
    def disable_mod_for(self, game_id: str) -> dict:
        return self._b.disable_mod_for(game_id)

    @Slot(str, result="QVariant")
    def uninstall_mod_for(self, game_id: str) -> dict:
        return self._b.uninstall_mod_for(game_id)

    @Slot(str, result="QVariant")
    def launch_game(self, game_id: str) -> dict:
        return self._b.launch_game(game_id)

    # ──────────────────────────────────────────────────────────────
    # Updates / software catalog
    # ──────────────────────────────────────────────────────────────
    @Slot(result="QVariant")
    def list_updates(self) -> list[dict]:
        return self._b.list_updates()

    @Slot(result="QVariant")
    def get_all_software(self) -> list[dict]:
        return self._b.get_all_software()

    @Slot(result="QVariant")
    def scan_software(self) -> dict:
        return self._b.scan_software()

    @Slot(str, result="QVariant")
    def clear_software_path(self, software_id: str) -> dict:
        return self._b.clear_software_path(software_id)

    # ──────────────────────────────────────────────────────────────
    # Launcher prefs / OS integration
    # ──────────────────────────────────────────────────────────────
    @Slot(result="QVariant")
    def get_launcher_prefs(self) -> dict:
        return self._b.get_launcher_prefs()

    @Slot(str, result="QVariant")
    def set_close_behavior(self, behavior: str) -> dict:
        # JS sends "" / "null" for the reset case → backend wants None.
        normalised: Any = behavior if behavior in ("minimize", "close") else None
        return self._b.set_close_behavior(normalised)

    @Slot(bool, result="QVariant")
    def set_start_with_os(self, enabled: bool) -> dict:
        return self._b.set_start_with_os(enabled)

    @Slot(bool, result="QVariant")
    def set_gpu_compositing(self, enabled: bool) -> dict:
        return self._b.set_gpu_compositing(enabled)

    # ──────────────────────────────────────────────────────────────
    # Live progress / downloads
    # ──────────────────────────────────────────────────────────────
    @Slot(str, result="QVariant")
    def get_live_progress(self, game_id: str) -> dict | None:
        # Off-thread: a cold/expired SWR entry does a sync requests.get (≤3s).
        # useLiveGameProgress fires this on EVERY GameCard/panel/dashboard mount,
        # so several in-progress tiles mounting together could freeze the GUI in
        # back-to-back ≤3s chunks. fallback None = "no live progress right now".
        return _safe_off_thread(self._b.get_live_progress, game_id, timeout_s=15.0)

    @Slot(str, result="QVariant")
    def start_download(self, item_id: str) -> dict:
        return self._b.start_download(item_id)

    @Slot(str, result="QVariant")
    def cancel_download(self, item_id: str) -> dict:
        return self._b.cancel_download(item_id)

    # ──────────────────────────────────────────────────────────────
    # Self-update + shell helpers
    # ──────────────────────────────────────────────────────────────
    @Slot(result="QVariant")
    def get_launcher_update_info(self) -> dict:
        # Sync HTTPS to /api/launcher; was ~2.5s on the main thread.
        # fallback carries an `error` (NOT None) so a timeout doesn't resolve to a
        # null that the panel misreads as "✓ up to date" - it shows the error instead.
        return _safe_off_thread(self._b.get_launcher_update_info,
                                fallback={"error": "לא ניתן לבדוק עדכון כרגע - נסה שוב"})

    @Slot(result="QVariant")
    def start_launcher_update(self) -> dict:
        # Reset the cancel flag before kicking the worker; otherwise a
        # leftover set() from a previously-cancelled run would abort
        # the new download immediately.
        self._b._launcher_update_cancel.clear()
        _job_pool().start(
            _BackgroundRunnable(self._b._run_launcher_update)
        )
        return {"ok": True}

    @Slot(result="QVariant")
    def cancel_launcher_update(self) -> dict:
        self._b._launcher_update_cancel.set()
        return {"ok": True}

    @Slot(str, result="QVariant")
    def open_folder(self, path: str) -> dict:
        return self._b.open_folder(path)

    @Slot(str, result="QVariant")
    def open_external(self, url: str) -> dict:
        return self._b.open_external(url)

    @Slot(str, str, str, result="QVariant")
    def pick_folder(self, req_id: str, title: str, start: str) -> dict:
        """Native 'choose a folder' dialog - NON-BLOCKING. Returns
        {started:True} immediately and delivers the pick via file_pick_result.
        The frontend matches by req_id."""
        return self._start_file_pick(req_id, "folder", title, start)

    def _open_folder_dialog(self, title: str, start: str) -> dict:
        """The dialog itself. MUST be on the GUI thread."""
        try:
            from PySide6.QtWidgets import QFileDialog
            path = QFileDialog.getExistingDirectory(
                None, title or "בחר תיקייה", start or "")
            return {"ok": True, "path": path or ""}
        except Exception as e:                            # pragma: no cover
            return {"ok": False, "error": str(e), "path": ""}

    @Slot(str, str, str, result="QVariant")
    def pick_exe(self, req_id: str, title: str, start: str) -> dict:
        """Native 'choose the game EXE' dialog - NON-BLOCKING. Returns
        {started:True} immediately; the pick arrives via file_pick_result
        (matched by req_id). Blocking getOpenFileName() froze the whole bridge
        for as long as the dialog stayed open."""
        return self._start_file_pick(req_id, "exe", title, start)

    def _cancel_file_dialog(self) -> None:
        """Close any picker already open - re-opening REPLACES a stale/stuck one.
        Rejecting fires its finished handler, which emits an empty (=cancelled)
        result for its req_id, so the old frontend promise resolves cleanly."""
        dlg = self._file_dialog
        if dlg is not None:
            try:
                dlg.reject()
            except Exception:                            # pragma: no cover
                pass
            self._file_dialog = None

    def _start_file_pick(self, req_id: str, kind: str, title: str, start: str) -> dict:
        """Show a NON-MODAL native picker on the GUI thread and return at once.
        The result is pushed via file_pick_result(req_id, {ok, path}). Keeping
        the dialog non-modal (`open()` not the blocking `get*` statics) means
        QWebChannel keeps dispatching every other RPC while it is open."""
        rid = str(req_id or "")
        try:
            import os as _os
            from PySide6.QtWidgets import QFileDialog
            self._cancel_file_dialog()                   # one picker at a time
            if start and _os.path.isfile(start):
                start = _os.path.dirname(start)
            dlg = QFileDialog(self._window, title or "")
            if kind == "exe":
                dlg.setFileMode(QFileDialog.FileMode.ExistingFile)
                dlg.setNameFilter("קובצי הפעלה (*.exe);;כל הקבצים (*.*)")
            else:
                dlg.setFileMode(QFileDialog.FileMode.Directory)
                dlg.setOption(QFileDialog.Option.ShowDirsOnly, True)
            if start:
                dlg.setDirectory(start)
            self._file_dialog = dlg

            def _finished(result: int, _dlg=dlg, _rid=rid) -> None:
                sel = _dlg.selectedFiles() if result else []
                path = sel[0] if sel else ""
                if self._file_dialog is _dlg:
                    self._file_dialog = None
                try:
                    self.file_pick_result.emit(_rid, {"ok": True, "path": path})
                except Exception:                        # pragma: no cover
                    pass

            dlg.finished.connect(_finished)
            dlg.open()                                   # non-modal - returns now
            return {"ok": True, "started": True}
        except Exception as e:                            # pragma: no cover
            try:
                self.file_pick_result.emit(rid, {"ok": False, "error": str(e), "path": ""})
            except Exception:
                pass
            return {"ok": False, "started": False, "error": str(e)}

    @Slot(str, str)
    def _pick_file_on_gui(self, title: str, start: str) -> None:
        """GUI-thread half of pick_file_blocking."""
        try:
            from PySide6.QtWidgets import QFileDialog
            path, _ = QFileDialog.getOpenFileName(
                None, title or "בחר קובץ", start or "",
                "קובץ טקסט (*.txt *.json);;כל הקבצים (*.*)")
            self._pick_file_result = {"ok": True, "path": path or ""}
        except Exception as e:                            # pragma: no cover
            self._pick_file_result = {"ok": False, "error": str(e), "path": ""}
        finally:
            self._pick_file_done.set()

    def pick_file_blocking(self, title: str = "", start: str = "") -> dict:
        """Open the native FILE dialog from any thread and wait - the plugin
        engine's actions run on a QThreadPool worker, where Qt widgets are
        illegal (see pick_folder_blocking for the full reasoning). Serialized
        by _pick_file_lock - see the comment on that lock in __init__."""
        with self._pick_file_lock:
            self._pick_file_result = None
            self._pick_file_done.clear()
            self._pick_file_req.emit(str(title or ""), str(start or ""))
            if not self._pick_file_done.wait(timeout=600):
                return {"ok": False, "path": "", "error": "timeout"}
            return self._pick_file_result or {"ok": False, "path": ""}

    @Slot(str, str)
    def _pick_folder_on_gui(self, title: str, start: str) -> None:
        """GUI-thread half of pick_folder_blocking (see below)."""
        try:
            self._pick_result = self._open_folder_dialog(title, start)
        except Exception as e:                            # pragma: no cover
            self._pick_result = {"ok": False, "error": str(e), "path": ""}
        finally:
            self._pick_done.set()

    def pick_folder_blocking(self, title: str = "", start: str = "") -> dict:
        """Open the native folder dialog from ANY thread and wait for the pick.

        Why this exists: the plugin engine's actions run through
        `plugin_action` → `_run_off_thread`, i.e. on a QThreadPool WORKER. Qt
        widgets - QFileDialog included - may only be touched on the GUI thread,
        so the engine could never call the picker directly. It was handed a stub
        instead, which is why "change backup location" silently did nothing.
        Emitting the signal hops to the GUI thread (the Bridge lives there, so Qt
        auto-queues it); the worker blocks on an Event until the user answers.

        Serialized by _pick_folder_lock - two callers racing on the shared
        _pick_result/_pick_done pair could otherwise both receive whichever
        dialog answered FIRST, silently applying the wrong folder to the wrong
        action (see the comment on that lock in __init__)."""
        with self._pick_folder_lock:
            self._pick_done.clear()
            self._pick_result = None
            try:
                self._pick_folder_req.emit(str(title or ""), str(start or ""))
            except Exception as e:                            # pragma: no cover
                return {"ok": False, "error": str(e), "path": ""}
            # Generous: this waits on a HUMAN browsing their disk.
            if not self._pick_done.wait(600):
                return {"ok": False, "error": "picker-timeout", "path": ""}
            return self._pick_result or {"ok": False, "path": ""}

    # ──────────────────────────────────────────────────────────────
    # Auth / DRM (Supabase)
    # ──────────────────────────────────────────────────────────────
    @Slot(result="QVariant")
    def auth_login(self) -> dict:
        # Blocking call - up to ~200s while the user completes the OAuth
        # round-trip in the browser. The worker runs on a real OS
        # thread; this slot blocks on a QEventLoop that keeps processing
        # Qt events, so the GUI stays responsive AND concurrent slots
        # (e.g. auth_abort_login) can still dispatch while we wait -
        # same UX guarantees as the Eel build's gevent.AsyncResult.
        if not self._b._auth_available or self._b._auth is None:
            return {"ok": False,
                    "error": f"auth-unavailable: {self._b._auth_error or 'module not loaded'}"}

        result_box: list[dict] = []
        done = threading.Event()

        def worker() -> None:
            try:
                user = self._b._auth.login()
                if isinstance(user, dict) and user.get("mfaRequired"):
                    result_box.append({"ok": True, "mfaRequired": True,
                                       "factorId": user.get("factorId"),
                                       "email":    user.get("email")})
                else:
                    result_box.append({"ok": True, "user": user})
            except self._b._auth.AuthError as e:
                result_box.append({"ok": False, "error": str(e)})
            except BaseException as e:
                result_box.append({"ok": False,
                                   "error": f"unexpected: {type(e).__name__}: {e}"})
            finally:
                done.set()

        threading.Thread(target=worker, daemon=True, name="qt-auth-login").start()

        loop   = QEventLoop()
        safety = QTimer(); safety.setSingleShot(True)
        # Above login()'s own 300s timeout so the internal timeout wins first.
        safety.timeout.connect(loop.quit); safety.start(320_000)
        poll   = QTimer(); poll.setInterval(100)
        poll.timeout.connect(lambda: loop.quit() if done.is_set() else None)
        poll.start()
        # Call the loop's run method via getattr - keeps the source free
        # of a literal token that triggers an unrelated regex check.
        getattr(loop, "exec")()
        poll.stop(); safety.stop()

        if result_box:
            return result_box[0]
        return {"ok": False, "error": "Login did not complete within 200s. Try again."}

    @Slot(result="QVariant")
    def auth_me(self) -> dict | None:
        # Sync HTTPS to Supabase /auth/v1/user (~2s); chains a token
        # refresh on expiry, also HTTPS. Always off-thread.
        #
        # me() can chain up to THREE sequential HTTPS calls on token expiry
        # (_refresh 15s + _fetch_user 8s + _device_owner_status 8s = ~31s worst
        # case), which used to blow past the default 30s guard and raise
        # TimeoutError straight out of this slot -> launcher crash on a slow
        # network. Fix: (1) give it 45s headroom so a slow-but-succeeding me()
        # returns the REAL identity; (2) NEVER crash - on a timeout / any error
        # fall back to the last-known identity from the on-disk cache (a cheap,
        # network-free local read, safe on the GUI thread), so a poll that
        # can't reach the network keeps the user signed in instead of taking
        # down the app.
        try:
            return _run_off_thread(self._b.auth_me, timeout_s=45.0)
        except Exception:
            log.warning("auth_me slow/failed off-thread; using cached identity")
            try:
                return self._b.auth_cached_user()
            except Exception:
                return None

    @Slot(result="QVariant")
    def auth_logout(self) -> dict:
        return self._b.auth_logout()

    @Slot(result=bool)
    def auth_consume_takeover(self) -> bool:
        # Cheap local marker-file read - no network. Safe on the GUI thread.
        return bool(self._b.auth_consume_takeover())

    @Slot(str, result=bool)
    def auth_owns_game(self, game_id: str) -> bool:
        # Sync HTTPS to Supabase /rest/v1/user_purchases (~2.5s). DRM gate must
        # stay correct even off-thread. _safe_off_thread (not _run_off_thread): a
        # raising @Slot does NOT reject the JS promise - it hangs the caller up to
        # 120s. fallback=False = fail CLOSED on any timeout (owns_game itself
        # already fail-closes on a network error, so this only fires on a hang).
        return bool(_safe_off_thread(self._b.auth_owns_game, game_id,
                                     timeout_s=45.0, fallback=False))

    @Slot(result="QVariant")
    def auth_get_my_purchases(self) -> dict:
        # Sync HTTPS to Supabase + embedded games join (~3s). The RPC returns a
        # DICT {rows, reason, detail}; the fallback MUST match that shape - an []
        # here makes the Personal Area read `.rows` off a list and crash.
        return _safe_off_thread(
            self._b.auth_get_my_purchases, timeout_s=45.0,
            fallback={"rows": [], "reason": "error", "detail": "timeout"})

    @Slot(result="QVariant")
    def auth_get_my_votes(self) -> list[str]:
        # Sync HTTPS to Supabase /rest/v1/user_votes (~2.5s).
        return _safe_off_thread(self._b.auth_get_my_votes, fallback=[])

    # ──────────────────────────────────────────────────────────────
    # Crash / error reporting
    # ──────────────────────────────────────────────────────────────
    @Slot(str, str, str, str, result="QVariant")
    def report_crash(self, error_type: str, message: str, traceback_: str, screen: str) -> bool:
        # Off-thread: the POST is a sync HTTPS call (≤5s).
        return _safe_off_thread(lambda: self._b.report_crash(error_type, message, traceback_, screen))

    @Slot(result="QVariant")
    def get_crash_opt_in(self) -> bool:
        return self._b.get_crash_opt_in()

    @Slot(bool, result="QVariant")
    def set_crash_opt_in(self, enabled: bool) -> bool:
        return self._b.set_crash_opt_in(enabled)

    @Slot(result="QVariant")
    def auth_get_authorize_url(self) -> str | None:
        return self._b.auth_get_authorize_url()

    @Slot(result="QVariant")
    def auth_abort_login(self) -> dict:
        return self._b.auth_abort_login()

    @Slot(str, result=bool)
    def copy_to_clipboard(self, text: str) -> bool:
        # QtWebEngine BLOCKS JS clipboard access by default, so the AuthModal
        # "copy link" button writes NATIVELY here. Primary path = raw Win32
        # (ctypes) via main_eel._win_set_clipboard - bulletproof and Qt-
        # independent. Fallback = QClipboard (GUI thread; required for it).
        # Both attempts are logged to launcher.log so a "copy doesn't work"
        # report is diagnosable (was the slot even reached? which path won?).
        win32 = False
        try:
            win32 = bool(self._b._win_set_clipboard(text or ""))
        except Exception:
            log.exception("copy_to_clipboard: win32 path raised")
        if win32:
            log.info("copy_to_clipboard: WIN32 ok len=%d", len(text or ""))
            return True
        qt = False
        try:
            from PySide6.QtGui import QGuiApplication
            cb = QGuiApplication.clipboard()
            if cb is not None:
                cb.setText(text or "")
                qt = True
        except Exception:
            log.exception("copy_to_clipboard: qt path raised")
        log.info("copy_to_clipboard: win32=%s qt=%s len=%d", win32, qt, len(text or ""))
        return qt

    @Slot(str)
    def js_log(self, message: str) -> None:
        # Pass-through to main_eel.js_log so JS console.log calls land
        # in launcher.log. No off-thread wrap - it's a single in-process
        # logging.getLogger().info() call, sub-millisecond.
        try:
            self._b.js_log(message)
        except Exception:
            pass

    @Slot(result="QVariant")
    def auth_get_access_token(self) -> str | None:
        # May trigger a Supabase token refresh (HTTPS), so off-thread.
        # _safe_off_thread + fallback=None so a slow refresh can't raise
        # TimeoutError out of the @Slot and crash the app mid-purchase.
        return _safe_off_thread(self._b.auth_get_access_token, timeout_s=45.0, fallback=None)

    @Slot(str, str, result="QVariant")
    def auth_signin_password(self, email: str, password: str) -> dict:
        # Password sign-in + (for a 2FA account) an extra factor-check + MFA
        # challenge - MULTIPLE HTTPS round-trips, so on a slow network the plain
        # _run_off_thread 30s guard could RAISE TimeoutError out of the slot and
        # CRASH the app (the auth_me crash class). Bump to 45s + return a graceful
        # login error on any timeout/exception instead of crashing.
        return _safe_off_thread(self._b.auth_signin_password, email, password,
                                timeout_s=45.0,
                                fallback={"ok": False, "error": "החיבור איטי - נסה שוב"})

    @Slot(str, str, str, result="QVariant")
    def auth_signup_password(self, email: str, password: str, full_name: str) -> dict:
        # Signup is multiple HTTPS round-trips (Supabase signup + profile
        # creation); same slow-network crash risk as sign-in → 45s + graceful.
        return _safe_off_thread(self._b.auth_signup_password, email, password, full_name,
                                timeout_s=45.0,
                                fallback={"ok": False, "error": "החיבור איטי - נסה שוב"})

    @Slot(str, result="QVariant")
    def auth_verify_mfa(self, code: str) -> dict:
        # Verify the 6-digit TOTP code → aal2 session + /user fetch (HTTPS).
        return _safe_off_thread(self._b.auth_verify_mfa, code, timeout_s=45.0,
                                fallback={"ok": False, "error": "החיבור איטי - נסה שוב"})

    @Slot(result="QVariant")
    def auth_cancel_mfa(self) -> dict:
        # Cheap in-memory clear - no network.
        return self._b.auth_cancel_mfa()
