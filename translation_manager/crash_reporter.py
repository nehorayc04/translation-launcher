"""Crash / error reporting for the launcher.

Installs process-wide exception hooks (main thread + worker threads), captures
the exception + a tail of the log, SCRUBS PII (the user's home path → "~",
long token-like runs → "<redacted>"), and POSTs a report to the hub's
/api/crash endpoint - so the developer can see which builds crash on which
machines and fix them.

Privacy:
  • Reporting is ON by default but the user can turn it off in Settings
    (launcher_prefs "crash_reporting" = False), and a one-time notice is
    shown by the UI on first launch.
  • Only the error type/message/traceback/log-tail + build/OS metadata are
    sent. Home paths and long tokens are scrubbed before the POST.

Robustness:
  • Every hook is defensive - a reporter failure NEVER crashes the launcher.
  • A per-session counter caps reports at MAX_PER_SESSION so a crash loop
    can't flood the endpoint (the server also IP-rate-limits).
  • The POST has a short timeout and is wrapped so it can't hang shutdown.
"""
from __future__ import annotations

import logging
import os
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
# Handled (non-fatal) events are far more frequent than crashes, so they get
# their own, looser session cap + a dedup so a tight loop can't flood.
MAX_EVENTS_PER_SESSION = 60
_HOME = str(Path.home())
_count = 0
_event_count = 0
_event_seen: set[str] = set()          # dedup key = f"{kind}:{code}"
_lock = threading.Lock()
_dialog_cb = None  # set by the Qt shell: cb(error_type: str, message: str) -> None


def _device_id() -> str:
    """A stable, RANDOM per-install id (no PII). Reuses the same file the
    install-ping already writes, so no new identifier is introduced."""
    try:
        from .auth import manager as _am
        return _am.device_id()
    except Exception:
        return ""


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


_TAIL_BYTES = 64 * 1024          # plenty for 50 lines; bounded no matter the log size


def _log_tail(n: int = 50) -> str:
    """Last `n` log lines, reading only the TAIL of the file.

    This used to do `read_text().splitlines()` - i.e. pull the ENTIRE log into
    memory (and then a list of every line) just to keep 50. launcher.log is
    append-only for the life of an install, so on an old machine that is a
    hundreds-of-MB read + a multi-x RAM spike... executed WHILE the app is
    crashing, very often from memory pressure in the first place. The reporter
    could therefore amplify the crash it exists to report.

    Now: seek to the last _TAIL_BYTES and split only that. Constant memory,
    constant time, regardless of how big the log has grown."""
    try:
        with open(_LOG_PATH, "rb") as f:
            try:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                f.seek(max(0, size - _TAIL_BYTES), os.SEEK_SET)
            except OSError:
                pass                                  # unseekable → read what we can
            blob = f.read(_TAIL_BYTES)
        text = blob.decode("utf-8", errors="replace")
        lines = text.splitlines()
        if len(lines) > 1 and len(blob) >= _TAIL_BYTES:
            lines = lines[1:]                         # drop the half-cut first line
        # Trim from the FRONT, keeping the END. This was [:2000], which kept the
        # OLDEST of the 50 lines and threw away the newest - i.e. it discarded
        # the lines immediately before the crash, the only ones that explain it.
        return _scrub("\n".join(lines[-n:]))[-2000:]
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


# ── handled-event reporting (non-fatal; NEVER shows a dialog) ───────────────
def report_event(kind: str, message: str = "", *, source: str = "",
                 code: str = "", severity: str = "error",
                 extra: dict | None = None) -> None:
    """Report ONE handled, non-fatal event (install failure, game-launch
    failure, RPC/button error, JS error, network error…) - anonymously and
    SILENTLY. No dialog, fire-and-forget on a daemon thread so it can never
    block or crash the caller.

    Gated on the SAME disclosed `crash_reporting` opt-in as crashes: if the
    user turned reporting off, nothing is sent, period. Deduped per session so
    a loop reports a given (kind, code) once, and capped by MAX_EVENTS.
    """
    global _event_count
    try:
        if not is_enabled():
            return
        kind = re.sub(r"[^A-Za-z0-9_.]", "_", (kind or "Event"))[:60] or "Event"
        if not kind[0].isalpha() and kind[0] != "_":
            kind = "e_" + kind
        sev = severity if severity in ("error", "warn") else "error"
        # Dedup key: (kind, code). When no code is given (e.g. generic install
        # failures that share `install_error`), fall back to a short hash of the
        # message so DISTINCT failures still each report once - while a true loop
        # (identical message) is still collapsed. Anti-flood without under-count.
        sig = code
        if not sig and message:
            import hashlib
            sig = hashlib.md5(message[:80].encode("utf-8", "replace")).hexdigest()[:8]
        dedup = f"{kind}:{sig}"[:120]
        with _lock:
            if _event_count >= MAX_EVENTS_PER_SESSION:
                return
            if dedup in _event_seen:
                return
            _event_seen.add(dedup)
            _event_count += 1

        ex: dict = {"kind": kind, "severity": sev}
        if source:
            ex["source"] = str(source)[:60]
        if code:
            ex["code"] = _scrub(str(code))[:80]
        dev = _device_id()
        if dev:
            ex["device"] = dev          # random uuid - NOT scrubbed (would be redacted as a token)
        if extra and isinstance(extra, dict):
            # Scrub every extra value too - a future caller might put a path/token here.
            ex.update({str(k)[:40]: _scrub(str(v))[:200] for k, v in list(extra.items())[:8]})

        payload = {
            "appVersion":    _VERSION,
            "buildId":       _BUILD_ID,
            "os":            platform.platform(),
            "pythonVersion": platform.python_version(),
            "errorType":     kind,
            "message":       _scrub(message or kind)[:500] or kind,
            "severity":      sev,
            "extra":         ex,
        }

        def _post() -> None:
            try:
                requests.post(_API_BASE + "/api/crash", json=payload, timeout=5)
            except Exception:
                pass

        threading.Thread(target=_post, name="event-report", daemon=True).start()
    except Exception:
        pass


# ── install ────────────────────────────────────────────────────────────────
def set_dialog_callback(cb) -> None:
    """Register a UI callback (e.g. a Qt QMessageBox) shown after a main-thread
    crash. cb(error_type: str, message: str). Optional - reporting works
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

    # Worker-thread crashes (Python 3.8+). No dialog - not the GUI thread.
    def _thread_hook(args):
        report_exception(args.exc_type, args.exc_value, args.exc_traceback)

    try:
        threading.excepthook = _thread_hook  # type: ignore[assignment]
    except Exception:
        pass

    log.info("crash_reporter installed (version=%s build=%s)", _VERSION, _BUILD_ID)
