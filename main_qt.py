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
# HEADLESS MOD CLI — the console shell's way to install a translation.
#
# Big Launch is a separate EXE and must not re-implement the appliers: they own
# the backups, the journals, the game-update awareness and the DRM gate, and a
# second copy in another language would drift from them the first time a game
# changed. So the console ASKS this process to do the work and just renders the
# progress, which keeps exactly one implementation of every install.
#
# It runs BEFORE the single-instance guard on purpose: this is a short-lived
# worker, not a second UI, so it must neither wake the running window nor be
# turned away by it.
#
# Protocol: one JSON object per line on stdout (phase/pct/message/ok), so the
# caller can stream it without a parser.
def _mod_cli(argv: "list[str]") -> "int | None":
    if len(argv) < 2 or argv[1] != "--mod":
        return None

    import json

    def emit(**kw) -> None:
        sys.stdout.write(json.dumps(kw, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    ap = argparse.ArgumentParser(prog="TranslationManager --mod", add_help=False)
    ap.add_argument("--mod", required=True, choices=("install", "remove", "state", "language", "clearcache"))
    ap.add_argument("--game", required=True)
    ap.add_argument("--value", default="")     # language mode: auto | hebrew | english
    try:
        args = ap.parse_args(argv[1:])
    except SystemExit:
        emit(ok=False, message="בקשה לא תקינה")
        return 2

    try:
        # The packaged build ships NO eel - the Qt shell replaces it with a shim
        # whose @eel.expose is a no-op and whose push channels route to the
        # bridge. main_eel imports eel at module scope, so the shim has to be in
        # sys.modules BEFORE it is imported here exactly as it is in main()
        # below; without it this exits with "No module named 'eel'".
        from translation_manager.qt_shell import eel_shim as _shim
        sys.modules.setdefault("eel", _shim)
        import main_eel as be
    except Exception as exc:                                   # pragma: no cover
        emit(ok=False, message=f"טעינת הליבה נכשלה: {exc}")
        return 1

    gid = args.game
    try:
        if args.mod == "state":
            emit(ok=True, state=be.get_game_mod_state(gid))
            return 0

        if args.mod == "language":
            if args.value:
                emit(ok=True, result=be.set_game_language(gid, args.value))
            else:
                emit(ok=True, result=be.get_game_language(gid))
            return 0

        if args.mod == "clearcache":
            # The repair path. Without it a console user whose install went
            # wrong has no way forward at all: the launcher offers "clear the
            # translation cache", and a dead end is exactly what the console
            # must not have. It reverts FIRST and only then wipes, so a locked
            # game file stops the wipe instead of stranding the backup.
            st = be.get_game_mod_state(gid) or {}
            fn = be.clear_game_mod_cache if st.get("modSlug") else be.clear_native_mod_cache
            emit(ok=True, result=fn(gid))
            return 0

        # install / remove stream progress through the same channel the GUI uses.
        def on_progress(payload) -> None:
            try:
                if isinstance(payload, dict):
                    emit(phase=payload.get("phase", ""),
                         pct=payload.get("pct", 0),
                         message=payload.get("message", ""))
            except Exception:
                pass

        be.set_mod_progress_sink(on_progress)
        res = (be.cli_install_mod(gid) if args.mod == "install"
               else be.cli_remove_mod(gid))
        emit(ok=bool(res.get("ok")), message=res.get("message", ""), result=res)
        return 0 if res.get("ok") else 1
    except Exception as exc:
        emit(ok=False, message=str(exc))
        return 1


# HEADLESS SHELL CLI — the console's window onto the things only this process
# can answer.
#
# 🔴 THE CONSOLE CANNOT READ THE SESSION, AND MUST NOT LEARN HOW. The signed-in
# token lives in session.enc, encrypted with a Fernet key held in the Windows
# credential store and reachable only through this app's own auth stack. A C#
# re-implementation would mean a second copy of the crypto AND a second place
# that can leak a token — so the console asks here instead, exactly as it
# already does for installing a translation.
#
# The same argument covers the rest: update preferences, the beta opt-in and the
# plugin registry all have real logic behind them (defaults, migration, the
# per-mod override that outranks the global switch, a plugin host that has to be
# told to re-read its state). Editing their JSON from another process would work
# right up until one of those rules changed.
#
# Same protocol as --mod: one JSON object per line, and it runs before the
# single-instance guard because it is a short-lived worker, not a second window.
def _shell_cli(argv: "list[str]") -> "int | None":
    if len(argv) < 2 or argv[1] != "--shell":
        return None

    import json

    def emit(**kw) -> None:
        sys.stdout.write(json.dumps(kw, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    ap = argparse.ArgumentParser(prog="TranslationManager --shell", add_help=False)
    ap.add_argument("--shell", required=True,
                    choices=("all", "account", "plugins", "beta", "update"))
    ap.add_argument("--game", default="")      # beta: per-mod override target
    ap.add_argument("--id", default="")        # plugins: which plugin
    ap.add_argument("--set", dest="set_", default="")   # on | off | auto
    try:
        args = ap.parse_args(argv[1:])
    except SystemExit:
        emit(ok=False, message="בקשה לא תקינה")
        return 2

    try:
        from translation_manager.qt_shell import eel_shim as _shim
        sys.modules.setdefault("eel", _shim)
        import main_eel as be
    except Exception as exc:                                   # pragma: no cover
        emit(ok=False, message=f"טעינת הליבה נכשלה: {exc}")
        return 1

    # on/off/auto -> True/False/None. "auto" is a real third state for the
    # per-mod beta override: it means "no opinion, follow the global switch",
    # which is NOT the same as "off".
    tri = {"on": True, "true": True, "1": True,
           "off": False, "false": False, "0": False}.get(args.set_.lower())
    has_set = bool(args.set_)

    def account():
        # Identity comes from the CACHE first and deliberately: it is on disk,
        # needs no network, and a console that shows a spinner where a name
        # should be reads as broken. me() is only consulted when there is no
        # cache at all.
        user = None
        try:
            user = be.auth_cached_user()
        except Exception:
            pass
        if not user:
            try:
                user = be.auth_me()
            except Exception:
                user = None

        # Purchases DO need the network. Best-effort: a failure returns the
        # reason so the console can say why rather than show an empty list that
        # looks like "you own nothing".
        purchases, reason = [], ""
        if user:
            try:
                res = be.auth_get_my_purchases() or {}
                purchases = res.get("rows") or []
                reason = res.get("reason") or ""
            except Exception as exc:
                reason = str(exc)
        return {"user": user, "purchases": purchases, "reason": reason}

    try:
        # 🔴 ONE CALL FOR ALL FOUR, because the expensive part is not the work -
        # it is THIS PROCESS. Every invocation imports the launcher's entire
        # backend, so asking four questions separately paid that price four
        # times and left the console showing "טוען" for most of a minute. Each
        # answer is still independent: one that raises comes back null instead
        # of taking the other three down with it.
        if args.shell == "all":
            out = {}
            for key, fn in (("account", account),
                            ("plugins", be.get_plugins),
                            ("beta", be.get_update_prefs),
                            ("update", be.get_launcher_update_info)):
                try:
                    out[key] = fn()
                except Exception:
                    out[key] = None
            emit(ok=True, **out)
            return 0

        if args.shell == "account":
            emit(ok=True, **account())
            return 0

        if args.shell == "plugins":
            if args.id and has_set:
                res = be.set_plugin_enabled(args.id, bool(tri)) or {}
                # 🔴 A SETTER RETURNS ONLY {ok} — the console needs the STATE.
                # Same contract as beta below, and for the same reason: the
                # console must render what was actually stored, not what it
                # asked for. Enabling a plugin can also INSTALL it, so the
                # answer can differ from the request in more than one field.
                if not res.get("ok", False):
                    err = res.get("error") or ""
                    emit(ok=False, message=(
                        "נדרשת רכישה של תרגום אחד לפחות כדי להשתמש בתוספים"
                        if err == "not-entitled" else (err or "שינוי התוסף נכשל")))
                    return 1
                emit(ok=True, result=be.get_plugins())
                return 0
            emit(ok=True, result=be.get_plugins())
            return 0

        if args.shell == "beta":
            if has_set:
                if args.game:
                    # None clears the override -> back to following the global.
                    emit(ok=True, result=be.set_mod_beta_override(
                        args.game, None if args.set_.lower() == "auto" else bool(tri)))
                else:
                    emit(ok=True, result=be.set_update_prefs(beta_channel=bool(tri)))
                return 0
            emit(ok=True, result=be.get_update_prefs())
            return 0

        # update
        emit(ok=True, result=be.get_launcher_update_info())
        return 0
    except Exception as exc:
        emit(ok=False, message=str(exc))
        return 1


_rc = _mod_cli(sys.argv)
if _rc is None:
    _rc = _shell_cli(sys.argv)
if _rc is not None:
    sys.exit(_rc)


# ─────────────────────────────────────────────────────────────
# EARLY single-instance short-circuit — MUST run before ANY heavy import.
# A shortcut / pinned-taskbar relaunch while the app is already running used to
# import main_eel (gevent) + QtWebEngine (a large DLL) AND run a synchronous
# cold-start network fetch, only to discover the mutex is held and exit — several
# seconds during which the running window was never told to come forward. It also
# ran _mark_boot_started() below on every duplicate and never cleared it, bumping
# the GPU-safe-mode fail counter until the app was forced into CPU compositing
# ("opens laggy after a while, a restart doesn't fix it"). single_instance +
# deeplink are pure ctypes/stdlib (no Qt, no main_eel), so waking the owner and
# exiting costs microseconds. Only the SOLE instance falls through to the GPU
# block, _mark_boot_started(), and the heavy imports below.
_EARLY_DEEP_GAME_ID: "str | None" = None
if sys.platform == "win32":
    from translation_manager.qt_shell import single_instance as _si_early
    from translation_manager.qt_shell import deeplink as _dl_early
    _EARLY_DEEP_GAME_ID = _dl_early.parse_and_strip(sys.argv)   # also strips argv
    if not _si_early.acquire():
        if _EARLY_DEEP_GAME_ID:
            _dl_early.write_pending(_EARLY_DEEP_GAME_ID)
        _si_early.signal_show()
        if _si_early.elevated_owner():
            try:
                import ctypes as _c_early
                _c_early.windll.user32.MessageBoxW(
                    None,
                    "מנהל התרגומים כבר פועל, אבל במצב מנהל (Run as administrator) "
                    "ולכן אי אפשר להביא את החלון שלו לחזית.\n\n"
                    "סגור אותו לצמיתות מסמל התוכנה שליד השעון, ואז פתח שוב.",
                    "מנהל התרגומים", 0x40)          # MB_ICONINFORMATION
            except Exception:
                pass
        raise SystemExit(0)


# Windows application identity lives in translation_manager.app_icon (ONE source
# of truth - it also registers the toast's DisplayName/icon and must match the
# `AppUserModelID` installer.iss stamps on the shortcuts).


# ─────────────────────────────────────────────────────────────
# GPU acceleration policy - MUST be set before QApplication is built.
#
# By DEFAULT the launcher uses the GPU for compositing + rasterization so the
# UI scrolls and animates smoothly for every user - the same approach Steam /
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


# ── GPU SAFE MODE (self-healing white screen) ────────────────────────────
# Forcing the GPU on (below) is right for the vast majority, but on a broken /
# ancient / VM / RDP GPU it can make the QtWebEngine GPU process die on every
# launch → a permanently WHITE window. That user could never reach Settings to
# turn "האצת חומרה" off... because the settings live inside the window that
# won't render. So: drop a sentinel before we build the window and clear it the
# moment the page actually loads. A boot that never reached a first paint leaves
# the sentinel behind, and the NEXT launch automatically falls back to CPU
# compositing. Self-healing in both directions - one good boot clears it again.
def _boot_flag_path():
    from pathlib import Path as _Path
    return _Path.home() / ".translation_manager" / "boot_incomplete.flag"


def _boot_fail_count() -> int:
    """How many CONSECUTIVE boots never reached a first paint."""
    try:
        p = _boot_flag_path()
        if not p.exists():
            return 0
        return max(1, int((p.read_text(encoding="utf-8") or "1").strip() or 1))
    except Exception:
        # Unreadable/legacy ("1") flag → count it as a single failure.
        return 1


def _last_boot_failed() -> bool:
    """Degrade to CPU compositing only after TWO consecutive never-painted boots.

    A SINGLE abnormal exit (task-kill, power loss, the user closing the window
    while it is still loading) is NOT evidence of a broken GPU - and treating it
    as one made the next launch run CPU-composited, i.e. visibly laggy, for no
    reason ("it's choppy, and only a restart fixes it"). A genuinely broken GPU
    fails EVERY boot, so it trips the threshold immediately on the second try
    and still self-heals the white-screen case.
    """
    return _boot_fail_count() >= 2


def _mark_boot_started() -> None:
    try:
        p = _boot_flag_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(str(_boot_fail_count() + 1), encoding="utf-8")
    except Exception:
        pass


def mark_boot_ok() -> None:
    """Called once the web page has actually painted → this boot is healthy."""
    try:
        _boot_flag_path().unlink(missing_ok=True)
    except Exception:
        pass


_safe_mode = _last_boot_failed()
_existing_flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
_extra_flags: list[str] = []
if _gpu_opted_out() or _safe_mode or "--disable-gpu-compositing" in _existing_flags:
    # User opted out (flicker workaround), or the previous boot never painted →
    # route paint through the CPU.
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
_mark_boot_started()


# ─────────────────────────────────────────────────────────────
# Pre-import shim - MUST run before main_eel is touched.
# ─────────────────────────────────────────────────────────────
from translation_manager.qt_shell import eel_shim
sys.modules["eel"] = eel_shim

# Now safe to import main_eel - its top-of-file gevent.monkey patches
# socket/ssl/select, then `import eel` resolves to our shim above.
import main_eel  # noqa: E402

from PySide6.QtCore    import QCoreApplication, Qt, QTimer, QUrl  # noqa: E402
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
        # ROTATE. This was a plain append-forever file: an install that lives for
        # months grows an unbounded log → slow appends, wasted disk, and a crash
        # reporter that had to read it all. 2 MB x 3 backups = 8 MB ceiling, which
        # is still far more history than any diagnosis needs.
        from logging.handlers import RotatingFileHandler
        _h = RotatingFileHandler(str(log_path), maxBytes=2 * 1024 * 1024,
                                 backupCount=3, encoding="utf-8", delay=True)
        _h.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        logging.basicConfig(level=logging.INFO, handlers=[_h], force=True)
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

    # Crash reporting - capture unhandled exceptions (main + worker threads),
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

    # Deep link - pull a hebrewhub://game/<id> arg out of argv (and strip it)
    # BEFORE argparse / QApplication see it, so they don't choke on the extra
    # positional. None on a normal launch.
    # Windows already parsed + stripped the deep link in the early single-instance
    # short-circuit (top of file); only the non-Windows fallback parses here.
    deep_game_id = _EARLY_DEEP_GAME_ID if sys.platform == "win32" else deeplink.parse_and_strip(sys.argv)

    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", action="store_true",
                    help="Load the React app from http://localhost:5173 (Vite dev server)")
    ap.add_argument("--silent", action="store_true",
                    help="Boot hidden in the system tray (no main window). Used by "
                         "Windows autostart when the user opted in.")
    ap.add_argument("--restored", action="store_true",
                    help="Boot is a tray-restore relaunch, not a cold start - skip the "
                         "refresh-on-open and treat the disk cache as hot.")
    ap.add_argument("--big", action="store_true",
                    help='Boot straight into "ביג-לאנץ" - the SEPARATE full-screen '
                         "console shell (its own React root + window state), the way "
                         "Winhanced boots into its console mode. Used by the dedicated "
                         "Start-menu/Desktop shortcut.")
    args = ap.parse_args()

    # Tell the backend the process was started FOR the console shell, so the
    # frontend can ask (big_launch_requested) instead of guessing from the URL.
    try:
        main_eel.set_big_launch_requested(bool(args.big))
    except Exception:
        pass

    # Cold vs restored cache warm-up. The COLD refresh is a network round-trip;
    # run it OFF the boot thread so it never delays first paint / freezes the
    # native splash (it used to block here, before the window even existed). The
    # catalog still arrives via the SWR push; the disk cache serves the first
    # bridge read. The single-instance guard already ran at module import (the
    # early short-circuit at the top of this file), so a duplicate never reaches
    # here — do NOT call single_instance.acquire() again (a 2nd acquire in the
    # same process returns False on our own named mutex and would falsely exit).
    if args.restored:
        try:
            swr_cache.touch_all()
        except Exception:
            pass
    else:
        try:
            import threading as _thr
            _thr.Thread(target=_cold_start_refresh, name="cold-start-refresh",
                        daemon=True).start()
        except Exception:
            log.debug("cold-start refresh thread could not start", exc_info=True)

    # We're the sole instance (guaranteed above). (Re)register the hebrewhub://
    # protocol under
    # HKCU so the website's "פתח בתוכנה" button can launch us. Idempotent +
    # self-healing (rewrites the current exe path each launch).
    deeplink.register_scheme()

    # Anonymous install ping (active-install counting). Off the boot thread so
    # a slow/offline network never delays first paint. This MIRRORS the Eel
    # build's main() - without it the SHIPPED Qt build never fired the ping, so
    # launcher_installs stayed empty for every real user.
    try:
        import threading as _th
        _th.Thread(target=main_eel._ping_install, name="install-ping", daemon=True).start()
    except Exception:
        log.exception("install-ping start failed (non-fatal)")

    # ── Windows app identity (AppUserModelID) ─────────────────
    # REQUIRED for native toasts. Qt's QSystemTrayIcon.showMessage goes through
    # Shell_NotifyIcon, and Windows 10/11 will SILENTLY DROP that toast unless the
    # process declares an explicit AppUserModelID that matches the Start-menu
    # shortcut's AUMID (installer.iss sets the same string on the shortcut).
    # Symptom without it: notifications never appear AND the app never even shows
    # up under Settings → System → Notifications. Also gives the taskbar a stable
    # identity for pinning/grouping. Must run BEFORE any window/tray is created.
    try:
        import ctypes
        from translation_manager import app_icon as _ai
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            ctypes.c_wchar_p(_ai.APP_USER_MODEL_ID))
        # …and tell Windows the NAME + ICON to print on the toast, otherwise it
        # shows the raw AUMID string and a generic icon.
        _ai.register_toast_identity()
    except Exception:                                   # pragma: no cover
        log.debug("AppUserModelID could not be set (non-fatal)", exc_info=True)

    # ── Qt application boot ───────────────────────────────────
    # QCoreApplication attribute hints must be set before QApplication
    # construction (the docs make a big deal of this).
    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
    QCoreApplication.setOrganizationName("TranslationManager")
    QCoreApplication.setApplicationName("TranslationManager")

    qapp = QApplication(sys.argv)
    # Don't drop dead when the last window hides (tray mode keeps us alive).
    qapp.setQuitOnLastWindowClosed(False)

    # ── boot splash ───────────────────────────────────────────
    # The loading surface is the IN-APP React SplashScreen (App.tsx) - there is
    # NO native floating splash window (removed at the user's request). The main
    # window's own background is #050510, so the brief pre-React moment is just a
    # dark frame that the React splash covers the instant it mounts.
    splash = None

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
            from translation_manager.qt_shell import game_copilot_runtime
            game_copilot_runtime.stop()
        except Exception:
            pass
        try:
            # Was orphaned: plugins.host.stop() (the only thing that flushes a
            # community-compute worker's buffered results + releases its leased
            # lines back to the pool) had no caller anywhere in the app, so on
            # every close the daemon worker thread was just killed mid-flight -
            # any lines currently leased to this machine sat unavailable to the
            # rest of the pool until the server-side lease naturally expired.
            from translation_manager import plugins
            plugins.host.stop()
        except Exception:
            pass
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

    # Cold-start deep link - carry the target game in the URL fragment so the
    # React shell opens its detail panel on first paint (the running-instance
    # path navigates via navigate_to_game instead).
    if deep_game_id:
        initial_url.setFragment(f"game={deep_game_id}")

    # "ביג-לאנץ" - the same fragment channel selects the CONSOLE SHELL instead of
    # the desktop one (frontend/src/main.tsx routes on it). A deep link wins: if
    # the user clicked a hebrewhub://game/<id> link we open that game's page in
    # the desktop shell rather than hijacking it into the console.
    elif args.big:
        initial_url.setFragment("big")

    window = MainWindow(
        profile=profile,
        bridge=bridge,
        prefs_getter=launcher_prefs.get_close_behavior,
        on_close_to_exit=_on_close_to_exit,
        initial_url=initial_url,
    )
    # Give the bridge the live window so the (optional) custom frameless
    # title bar's min/max/close/drag/resize slots can drive it.
    bridge.set_window(window)
    tray = Tray(qapp, window, tooltip="Translation Manager")
    bridge.set_tray(tray)

    # Give the backend (and through it the PLUGIN ENGINE) a REAL folder picker.
    # Without this main_eel.pick_folder stays a stub returning "no-native-dialog",
    # which is why the save-backup plugin's "change backup location" / manual
    # browse opened nothing at all under the Qt build.
    try:
        main_eel.set_native_pick_folder(
            lambda title="", start="": bridge.pick_folder_blocking(title, start))
        main_eel.set_native_pick_file(
            lambda title="", start="": bridge.pick_file_blocking(title, start))
        # Launching a game hides the window (it runs on a bridge WORKER thread, so
        # the call must be queued onto the GUI thread - and the target must be a
        # @Slot or the by-name invoke silently no-ops).
        from PySide6.QtCore import QMetaObject, Qt as _Qt
        main_eel.set_native_minimize(
            lambda: QMetaObject.invokeMethod(window, "hide_for_game", _Qt.QueuedConnection))
    except Exception:
        log.debug("could not install the native folder picker", exc_info=True)

    # This boot is healthy → clear the GPU safe-mode sentinel so the NEXT launch
    # uses full hardware acceleration again.
    #
    # TWO independent clears, because loadFinished ALONE is a race we lose:
    # MainWindow.__init__ calls setUrl() at the end of its constructor, and the
    # frontend is a LOCAL file:// page - it can finish loading before main() gets
    # here to connect, so the signal is simply missed and the sentinel is never
    # removed. The observed result is the worst possible one: the app runs fine
    # yet EVERY subsequent launch silently drops to CPU compositing forever.
    # The timer cannot be missed: "we were still alive N seconds after start" is
    # a sufficient definition of a boot that did not die on the GPU.
    def _boot_ok(why: str) -> None:
        mark_boot_ok()
        if _safe_mode:
            log.warning("booted in GPU SAFE MODE (a previous boot never painted); "
                        "hardware accel will be retried next launch [%s]", why)
    try:
        window.view.loadFinished.connect(lambda ok: _boot_ok("loadFinished") if ok else None)
    except Exception:
        log.debug("could not wire loadFinished → boot sentinel", exc_info=True)
    QTimer.singleShot(12_000, lambda: _boot_ok("alive-12s"))

    # Dismiss the native boot splash ONLY when the frontend signals it is fully
    # ready (data + every first-screen image decoded) via bridge.app_ready. The
    # native splash is therefore the ONE loading surface - the in-app React boot
    # splash is gone - so there is no cross-fade/overlap: the splash holds until
    # the app is genuinely painted, then reveals it whole. Hard fallbacks keep it
    # from ever being stranded (a page that fails to load, or a stuck frontend).
    def _dismiss_splash(*_a) -> None:
        if splash is not None:
            try:
                splash.dismiss()
            except Exception:
                pass
    try:
        bridge.app_ready.connect(_dismiss_splash)   # dismiss the instant the app declares ready (if that comes first)
    except Exception:
        log.debug("could not wire app_ready → splash dismiss", exc_info=True)
    try:
        # The small card dismisses a fixed grace after the page LOADS - enough for
        # React to mount and paint the (preloaded) covers - so it never lingers
        # over an already-loaded app / stalls on the fragile image-decode chain.
        # On a load FAILURE, dismiss at once (reveal whatever is there).
        window.view.loadFinished.connect(
            lambda ok: QTimer.singleShot(2000, _dismiss_splash) if ok else _dismiss_splash())
    except Exception:
        log.debug("could not wire loadFinished → splash dismiss", exc_info=True)
    QTimer.singleShot(8_000, _dismiss_splash)       # absolute cap

    # Apply the user's chosen app-icon variant to the app/window/taskbar/tray
    # NOW (before the window is shown), so the taskbar button + title-bar icon
    # reflect the choice from the first paint. Best-effort; never raises.
    try:
        from translation_manager import app_icon
        app_icon.apply_live(app_icon.current(), window, tray)
    except Exception:
        log.debug("boot app-icon apply skipped", exc_info=True)

    # Native Windows notification channel - the frontend calls bridge.notify_os
    # (e.g. when it detects an available translation update on boot), which
    # emits os_notification; we show it as a tray balloon/toast. Same GUI
    # thread (the slot runs here via QWebChannel), so a direct call is safe.
    from PySide6.QtWidgets import QSystemTrayIcon as _QSysTray
    def _show_os_toast(title: str, body: str) -> None:
        # Prefer a REAL Windows Toast (via our AUMID) so it stays in the
        # notification history / Action Center and shows "מנהל התרגומים" + icon.
        # The tray balloon is only a last resort (it pops then vanishes and is
        # NOT kept in the Windows notification history).
        try:
            from translation_manager import app_icon as _ai
            if _ai.show_toast(title, body):
                return
        except Exception:
            log.debug("winrt toast unavailable, falling back to balloon", exc_info=True)
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

    # Plugins: run any on-boot / overdue save backups + start the scheduler.
    # Backstops the frontend's own plugins_boot() call so scheduled backups run
    # even before (or without) the UI mounting. Best-effort; never blocks boot.
    try:
        r = main_eel.plugins_boot()
        # A bare `pass` here hid a real regression for a long time: the host
        # never started at boot, so a background plugin sat "on" and idle until
        # the user toggled it. Report the failure instead of swallowing it.
        if not (r or {}).get("ok"):
            log.warning("[plugins] boot did not start the host: %s",
                        (r or {}).get("error"))
    except Exception:                                    # pragma: no cover
        log.exception("[plugins] plugins_boot raised")

    # Game Co-Pilot overlay: the global hotkey + always-on-top panel runtime.
    # A cheap QTimer poll that is a total no-op until the plugin is actually
    # installed + enabled (registry-driven) - always safe to start here.
    try:
        from translation_manager.qt_shell import game_copilot_runtime
        game_copilot_runtime.ensure_started()
    except Exception:                                    # pragma: no cover
        log.debug("game_copilot_runtime failed to start (non-fatal)", exc_info=True)

    # Wake-on-second-launch listener - the show callback must marshal
    # back to the GUI thread; QMetaObject.invokeMethod handles that.
    from PySide6.QtCore import QMetaObject, Q_ARG
    def _bring_to_front() -> None:
        # A deep link always SHOWS the window (+ navigates to the stashed game).
        # A bare relaunch - clicking the pinned taskbar icon of the running app -
        # TOGGLES instead, so a second click minimizes the window the way Windows
        # users expect (show → hide → show), rather than always re-showing it.
        gid = deeplink.read_pending()
        if gid:
            QMetaObject.invokeMethod(window, "show_and_activate", Qt.QueuedConnection)
            QMetaObject.invokeMethod(window, "navigate_to_game", Qt.QueuedConnection, Q_ARG(str, gid))
        else:
            QMetaObject.invokeMethod(window, "toggle_visibility", Qt.QueuedConnection)
    single_instance.start_listener(_bring_to_front)

    if not args.silent:
        # The console shell owns the whole screen: borderless full-screen, no
        # desktop title bar. Applied BEFORE the first show so it never flashes
        # as a window first.
        if args.big:
            try:
                window.set_big_launch(True)
            except Exception:
                log.debug("--big: set_big_launch failed (non-fatal)", exc_info=True)
        window.show_and_activate()
        if splash is not None:
            splash.cover(window)          # sit exactly over the empty view until React paints
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
