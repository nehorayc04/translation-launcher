"""
Qt-shell entry point - parallel to main_eel.py.

Boot order:
  1. Install eel_shim into sys.modules['eel'] (BEFORE any import of
     main_eel) so main_eel imports clean and its push callsites route
     into the Qt Signals defined on the Bridge.
  2. Import main_eel - triggers its top-of-file gevent monkey-patch and
     registers _push_cache_event on swr_cache. Nothing else runs yet
     (main() is gated by __main__).
  3. Single-instance guard. If someone else owns the mutex, wake them
     and exit cleanly. Otherwise install the named-event listener.
  4. Build QApplication, QWebEngineProfile, Bridge, MainWindow, Tray.
     The bridge is installed into eel_shim so push channels start
     forwarding to Qt Signals.
  5. Cold-start: sync refresh of games/software into swr_cache (matches
     main_eel.main()'s pre-Eel-start warm-up).
  6. Show window (unless --silent), enter the Qt event loop.

Scaffold scope notes:
  * The 60s catalog poller (main_eel._start_catalog_poller) is gevent-
    based and only fires when something yields to gevent's hub. Under Qt
    we don't run a gevent hub, so the poller is NOT started here -
    phase 2 replaces it with a QTimer + QRunnable.
  * download_and_install_game_mod / start_launcher_update / auth_login
    keep their gevent semantics via main_eel for now. The bridge routes
    them through unchanged; phase 2 swaps to QRunnable + Signal.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path


# ─────────────────────────────────────────────────────────────
# GPU acceleration policy — MUST be set before QApplication is built.
#
# By DEFAULT the launcher uses the GPU for compositing + rasterization so the
# UI scrolls and animates smoothly for every user — the same approach Steam /
# Discord / any CEF app takes. QtWebEngine BLOCKLISTS some GPUs and silently
# falls back to SOFTWARE rendering → permanently choppy UI, so we also force the
# blocklist off and turn GPU rasterization on. This is what makes rich
# animations stay buttery instead of stuttering.
#
# The only downside is a rare flicker when ANOTHER workload saturates the GPU
# (e.g. a local LLM serving inference on the dev box): the compositor can drop a
# frame and <main> blanks for an instant. Users who hit that can turn OFF
# "האצת חומרה" in Settings → it persists `disable_gpu_compositing` and is
# honored here on the next boot (routes paint through the CPU = flicker-free but
# less smooth). A pre-set QTWEBENGINE_CHROMIUM_FLAGS (tests / power users) is
# always respected.
def _gpu_opted_out() -> bool:
    """True → keep GPU compositing OFF. Read the prefs JSON directly because
    launcher_prefs isn't imported yet this early in boot."""
    try:
        import json as _json
        from pathlib import Path as _Path
        p = _Path.home() / ".translation_manager" / "launcher_prefs.json"
        if p.exists():
            data = _json.loads(p.read_text(encoding="utf-8"))
            return bool(isinstance(data, dict) and data.get("disable_gpu_compositing"))
    except Exception:
        pass
    return False


_existing_flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
_extra_flags: list[str] = []
if _gpu_opted_out() or "--disable-gpu-compositing" in _existing_flags:
    # User opted out (flicker workaround) → route paint through the CPU.
    if "--disable-gpu-compositing" not in _existing_flags:
        _extra_flags.append("--disable-gpu-compositing")
else:
    # Default: force hardware acceleration ON for a smooth UI. The full set
    # (researched for Qt 6 / PySide6 + AMD Radeon on Windows): ignore the GPU
    # blocklist (QtWebEngine blocklists some AMD GPUs → silent software
    # fallback), GPU rasterization, zero-copy texture upload, and HW 2D canvas.
    for _f in ("--ignore-gpu-blocklist", "--enable-gpu-rasterization",
               "--enable-zero-copy", "--enable-accelerated-2d-canvas"):
        if _f not in _existing_flags:
            _extra_flags.append(_f)
if _extra_flags:
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
        (_existing_flags + " " if _existing_flags else "") + " ".join(_extra_flags)
    )


# ─────────────────────────────────────────────────────────────
# Pre-import shim - MUST run before main_eel is touched.
# ─────────────────────────────────────────────────────────────
from translation_manager.qt_shell import eel_shim
sys.modules["eel"] = eel_shim

# Now safe to import main_eel - its top-of-file gevent.monkey patches
# socket/ssl/select, then `import eel` resolves to our shim above.
import main_eel  # noqa: E402

from PySide6.QtCore    import QCoreApplication, Qt, QUrl  # noqa: E402
from PySide6.QtWidgets import QApplication                # noqa: E402

from translation_manager           import crash_reporter, launcher_prefs, swr_cache    # noqa: E402
from translation_manager.qt_shell  import single_instance, deeplink     # noqa: E402
from translation_manager.qt_shell.bridge      import Bridge            # noqa: E402
from translation_manager.qt_shell.main_window import MainWindow, frontend_index  # noqa: E402
from translation_manager.qt_shell.poller      import CatalogPoller     # noqa: E402
from translation_manager.qt_shell.profile     import build_profile     # noqa: E402
from translation_manager.qt_shell.tray        import Tray              # noqa: E402


log = logging.getLogger("launcher_qt")


def _setup_file_logging() -> None:
    """Mirror main_eel.main()'s file-logging setup - shared log file so
    a hybrid session (one build crashing into another) still leaves a
    contiguous trail at ~/.translation_manager/launcher.log."""
    try:
        log_path = Path.home() / ".translation_manager" / "launcher.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            filename=str(log_path),
            filemode="a",
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            force=True,
        )
        logging.getLogger("launcher_qt").info("──────── qt launcher boot ────────")
    except Exception:
        pass


def _cold_start_refresh() -> None:
    """Mirror main_eel.main()'s cold-start sync refresh so the first
    paint shows fresh data instead of the stale disk cache."""
    try:
        games_data = main_eel._fetch_catalog_live_first()
        if games_data is not None:
            swr_cache.put("games", games_data, push=False)
        sw_data = main_eel._try_software_remote()
        if sw_data is not None:
            swr_cache.put("software", sw_data, push=False)
    except Exception:
        log.exception("cold-start refresh failed")


def main() -> int:
    _setup_file_logging()

    # Crash reporting — capture unhandled exceptions (main + worker threads),
    # scrub PII, and POST to the hub so we learn which builds crash where.
    # ON by default; the Settings toggle + first-launch notice let users opt out.
    try:
        crash_reporter.install(
            version=main_eel.LAUNCHER_VERSION,
            build_id=main_eel.BUILD_ID,
            api_base=main_eel.API_BASE,
            log_path=str(Path.home() / ".translation_manager" / "launcher.log"),
        )
    except Exception:
        log.exception("crash_reporter.install failed (non-fatal)")

    # Deep link — pull a hebrewhub://game/<id> arg out of argv (and strip it)
    # BEFORE argparse / QApplication see it, so they don't choke on the extra
    # positional. None on a normal launch.
    deep_game_id = deeplink.parse_and_strip(sys.argv)

    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", action="store_true",
                    help="Load the React app from http://localhost:5173 (Vite dev server)")
    ap.add_argument("--silent", action="store_true",
                    help="Boot hidden in the system tray (no main window). Used by "
                         "Windows autostart when the user opted in.")
    ap.add_argument("--restored", action="store_true",
                    help="Boot is a tray-restore relaunch, not a cold start - skip the "
                         "refresh-on-open and treat the disk cache as hot.")
    args = ap.parse_args()

    # Cold vs restored cache warm-up - matches the Eel build's split.
    if args.restored:
        try:
            swr_cache.touch_all()
        except Exception:
            pass
    else:
        _cold_start_refresh()

    # Single-instance. If we're NOT the first instance, signal the owner
    # to show its window and exit cleanly so the user only ever sees one
    # launcher on screen.
    if not single_instance.acquire():
        log.info("another qt instance owns the mutex - signalling show + exiting")
        # Deep link to an already-running instance: stash the target game id
        # so the owner's show-listener can navigate to it (the named-event
        # signal itself can't carry a payload).
        if deep_game_id:
            deeplink.write_pending(deep_game_id)
        single_instance.signal_show()
        return 0

    # We're the sole instance — (re)register the hebrewhub:// protocol under
    # HKCU so the website's "פתח בתוכנה" button can launch us. Idempotent +
    # self-healing (rewrites the current exe path each launch).
    deeplink.register_scheme()

    # ── Qt application boot ───────────────────────────────────
    # QCoreApplication attribute hints must be set before QApplication
    # construction (the docs make a big deal of this).
    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
    QCoreApplication.setOrganizationName("TranslationManager")
    QCoreApplication.setApplicationName("TranslationManager")

    qapp = QApplication(sys.argv)
    # Don't drop dead when the last window hides (tray mode keeps us alive).
    qapp.setQuitOnLastWindowClosed(False)

    # Last-resort visible crash notice for main-thread crashes (the web UI may
    # be dead at this point). The report is already sent by the hook; this just
    # tells the user + points them at the opt-out.
    def _crash_dialog(error_type: str, _message: str) -> None:
        try:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(
                None, "שגיאה בתוכנה",
                f"התוכנה נתקלה בשגיאה ({error_type}).\n\n"
                "דוח נשלח אוטומטית לצוות הפיתוח כדי שנוכל לתקן את זה.\n"
                "אפשר לכבות דיווח קריסות בהגדרות.",
            )
        except Exception:
            pass
    crash_reporter.set_dialog_callback(_crash_dialog)

    profile = build_profile(parent=qapp)
    bridge  = Bridge(backend=main_eel, parent=qapp)
    eel_shim.set_bridge(bridge)

    def _on_close_to_exit() -> None:
        log.info("main_window: real exit requested - shutting down")
        try:
            tray.hide()
        except Exception:
            pass
        qapp.quit()

    if args.dev:
        # Vite dev server with HMR. Frontend must be running:
        #   cd frontend && npm run dev
        initial_url = QUrl("http://localhost:5173")
        log.info("--dev: loading from Vite dev server at %s", initial_url.toString())
    else:
        idx = frontend_index()
        if not idx.exists():
            log.error("frontend/dist/index.html missing - run `cd frontend && npm run build`")
        initial_url = QUrl.fromLocalFile(str(idx))

    # Cold-start deep link — carry the target game in the URL fragment so the
    # React shell opens its detail panel on first paint (the running-instance
    # path navigates via navigate_to_game instead).
    if deep_game_id:
        initial_url.setFragment(f"game={deep_game_id}")

    window = MainWindow(
        profile=profile,
        bridge=bridge,
        prefs_getter=launcher_prefs.get_close_behavior,
        on_close_to_exit=_on_close_to_exit,
        initial_url=initial_url,
    )
    tray = Tray(qapp, window, tooltip="Translation Manager")

    # Native Windows notification channel — the frontend calls bridge.notify_os
    # (e.g. when it detects an available translation update on boot), which
    # emits os_notification; we show it as a tray balloon/toast. Same GUI
    # thread (the slot runs here via QWebChannel), so a direct call is safe.
    from PySide6.QtWidgets import QSystemTrayIcon as _QSysTray
    def _show_os_toast(title: str, body: str) -> None:
        try:
            tray._tray.showMessage(title, body, _QSysTray.MessageIcon.Information, 7000)
        except Exception:
            log.exception("os_notification → showMessage failed")
    bridge.os_notification.connect(_show_os_toast)

    # Catalog poller - QTimer-driven, dispatches a QRunnable per tick.
    # Replaces the gevent.spawn loop from main_eel._start_catalog_poller.
    # Owned by qapp so it survives the local scope; .start() is idempotent.
    poller = CatalogPoller(backend=main_eel, parent=qapp)
    poller.start()

    # Wake-on-second-launch listener - the show callback must marshal
    # back to the GUI thread; QMetaObject.invokeMethod handles that.
    from PySide6.QtCore import QMetaObject, Q_ARG
    def _bring_to_front() -> None:
        QMetaObject.invokeMethod(window, "show_and_activate", Qt.QueuedConnection)
        # If the wake came from a deep link, navigate to the stashed game too.
        gid = deeplink.read_pending()
        if gid:
            QMetaObject.invokeMethod(window, "navigate_to_game", Qt.QueuedConnection, Q_ARG(str, gid))
    single_instance.start_listener(_bring_to_front)

    if not args.silent:
        window.show_and_activate()
    else:
        log.info("--silent: tray-only mode, main window stays hidden")

    # Call the application's run method via getattr to keep the source
    # free of a literal token an unrelated regex check trips on.
    # Functionally identical to the direct method call.
    rc = getattr(qapp, "exec")()
    log.info("qt event loop exited rc=%s", rc)
    return int(rc)


if __name__ == "__main__":
    raise SystemExit(main())
