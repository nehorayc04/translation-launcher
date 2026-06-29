"""Crash / error reporting for the launcher.

Installs process-wide exception hooks (main thread + worker threads), captures
the exception + a tail of the log, SCRUBS PII (the user's home path → "~",
long token-like runs → "<redacted>"), and POSTs a report to the hub's
/api/crash endpoint — so the developer can see which builds crash on which
machines and fix them.

Privacy:
  • Reporting is ON by default but the user can turn it off in Settings
    (launcher_prefs "crash_reporting" = False), and a one-time notice is
    shown by the UI on first launch.
  • Only the error type/message/traceback/log-tail + build/OS metadata are
    sent. Home paths and long tokens are scrubbed before the POST.

Robustness:
  • Every hook is defensive — a reporter failure NEVER crashes the launcher.
  • A per-session counter caps reports at MAX_PER_SESSION so a crash loop
    can't flood the endpoint (the server also IP-rate-limits).
  • The POST has a short timeout and is wrapped so it can't hang shutdown.
"""
from __future__ import annotations

import logging
import platform
import re
import sys
import threading
import traceback as _tb
from pathlib import Path

import requests

log = logging.getLogger(__name__)

# ── config (overridden by install()) ──────────────────────────────────────
_API_BASE = "https://hebrew-translation-hub.com"
_VERSION = "dev"
_BUILD_ID = "dev"
_LOG_PATH = Path.home() / ".translation_manager" / "launcher.log"

MAX_PER_SESSION = 5
_HOME = str(Path.home())
_count = 0
_lock = threading.Lock()
_dialog_cb = None  # set by the Qt shell: cb(error_type: str, message: str) -> None


# ── opt-in (default ON) ────────────────────────────────────────────────────
def is_enabled() -> bool:
    """True unless the user explicitly disabled crash reporting."""
    try:
        from . import launcher_prefs
        return launcher_prefs.load().get("crash_reporting", True) is not False
    except Exception:
        return True


def set_enabled(enabled: bool) -> bool:
    try:
        from . import launcher_prefs
        prefs = launcher_prefs.load()
        prefs["crash_reporting"] = bool(enabled)
        return launcher_prefs.save(prefs)
    except Exception as e:
        log.warning("crash_reporter.set_enabled failed: %s", e)
        return False


# ── PII scrubbing ──────────────────────────────────────────────────────────
def _scrub(text: str) -> str:
    if not text:
        return ""
    out = text.replace(_HOME, "~")
    # also catch a forward-slash spelling of the home dir
    out = out.replace(_HOME.replace("\\", "/"), "~")
    # redact long token-like runs (api keys, jwts, hashes)
    out = re.sub(r"[A-Za-z0-9_\-]{32,}", "<redacted>", out)
    return out


def _log_tail(n: int = 50) -> str:
    try:
        lines = _LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
        return _scrub("\n".join(lines[-n:]))[:2000]
    except Exception:
        return ""


# ── reporting ──────────────────────────────────────────────────────────────
def report(error_type: str, message: str, traceback_text: str = "",
           *, screen: str | None = None, extra: dict | None = None) -> None:
    """Send one crash/error report (opt-in gated, deduped by session cap)."""
    global _count
    if not is_enabled():
        return
    with _lock:
        if _count >= MAX_PER_SESSION:
            return
        _count += 1

    payload = {
        "appVersion":    _VERSION,
        "buildId":       _BUILD_ID,
        "os":            platform.platform(),
        "pythonVersion": platform.python_version(),
        "errorType":     (error_type or "Error")[:200],
        "message":       _scrub(message or "")[:500],
        "traceback":     _scrub(traceback_text or "")[:8000],
        "logTail":       _log_tail(),
    }
    ex = {}
    if screen:
        ex["screen"] = str(screen)[:80]
    if extra and isinstance(extra, dict):
        ex.update({str(k)[:40]: str(v)[:200] for k, v in list(extra.items())[:10]})
    if ex:
        payload["extra"] = ex

    try:
        requests.post(_API_BASE + "/api/crash", json=payload, timeout=5)
        log.info("crash report sent: %s", payload["errorType"])
    except Exception as e:  # never let reporting raise
        log.warning("crash report POST failed: %s", e)


def report_exception(exc_type, exc, tb, *, screen: str | None = None) -> None:
    try:
        name = getattr(exc_type, "__name__", "Error")
        text = "".join(_tb.format_exception(exc_type, exc, tb))
        report(name, str(exc), text, screen=screen)
    except Exception:
        pass


# ── install ────────────────────────────────────────────────────────────────
def set_dialog_callback(cb) -> None:
    """Register a UI callback (e.g. a Qt QMessageBox) shown after a main-thread
    crash. cb(error_type: str, message: str). Optional — reporting works
    without it."""
    global _dialog_cb
    _dialog_cb = cb


def install(*, version: str = "dev", build_id: str = "dev",
            api_base: str | None = None, log_path: str | None = None) -> None:
    """Install sys + threading exception hooks. Idempotent-safe to call once
    at startup. Existing hooks are chained, not replaced."""
    global _VERSION, _BUILD_ID, _API_BASE, _LOG_PATH
    _VERSION = version or "dev"
    _BUILD_ID = build_id or "dev"
    if api_base:
        _API_BASE = api_base.rstrip("/")
    if log_path:
        _LOG_PATH = Path(log_path)

    _prev_hook = sys.excepthook

    def _main_hook(exc_type, exc, tb):
        report_exception(exc_type, exc, tb)
        if _dialog_cb is not None:
            try:
                _dialog_cb(getattr(exc_type, "__name__", "Error"), str(exc))
            except Exception:
                pass
        try:
            _prev_hook(exc_type, exc, tb)
        except Exception:
            pass

    sys.excepthook = _main_hook

    # Worker-thread crashes (Python 3.8+). No dialog — not the GUI thread.
    def _thread_hook(args):
        report_exception(args.exc_type, args.exc_value, args.exc_traceback)

    try:
        threading.excepthook = _thread_hook  # type: ignore[assignment]
    except Exception:
        pass

    log.info("crash_reporter installed (version=%s build=%s)", _VERSION, _BUILD_ID)
