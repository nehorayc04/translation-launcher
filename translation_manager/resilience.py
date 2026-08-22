"""
resilience.py - the launcher's self-healing brain.

The rule: **an error is a problem to be SOLVED, not a message to be shown.**

Every risky operation (a file read, a config write, an HTTPS call, a mod apply)
runs through this engine. When it fails, we do NOT surface the failure. We look
at WHAT failed, pick the recovery strategies that can actually fix that class of
problem, and try them in order - silently, in a fraction of a second, without
touching anything else and without ever losing data. Only when EVERY strategy is
exhausted does the caller get a clean fallback value (and a silent, anonymous
report goes to the dev so the same failure can be engineered away for good).

The strategies it knows, mapped to the failure they actually fix:

  file locked / access denied      → back off a few ms and retry (an antivirus or
   (WinError 5 / 32 / 33)            the Windows indexer is holding the handle for
                                     a moment), then clear a stray READ-ONLY bit
  parent folder missing            → create the folder tree, retry
  disk full (ENOSPC)               → fall back to an alternate writable location
  out of memory                    → collect garbage + release the working set,
                                     retry with the freed memory
  corrupt / truncated JSON         → transparently fall back to the .bak / .tmp
                                     sidecar and REPAIR the primary from it
  transient network / 5xx / 429    → exponential backoff, bounded
  a resource that keeps failing    → circuit-breaker: stop hammering it for a
                                     cool-down, serve the fallback instantly

Guarantees:
  • Never raises to the caller (unless you explicitly ask it to).
  • Never blocks the UI: the default recovery budget is a few hundred ms.
  • Never loses data: writes are atomic (temp + os.replace) and the previous
    good version is always kept as a .bak before it is replaced.
  • Zero new dependencies - stdlib only.
"""
from __future__ import annotations

import errno
import gc
import json
import logging
import os
import shutil
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable, Iterable, TypeVar

log = logging.getLogger(__name__)

T = TypeVar("T")

# Recovery must feel instant. These are the default retry delays (seconds) -
# three tries in ~0.2s total, which covers virtually every transient file lock.
_DEFAULT_DELAYS = (0.02, 0.06, 0.12)

# Windows error codes that mean "someone else is holding this file, briefly".
_TRANSIENT_WINERR = {5, 32, 33, 1224}     # denied / sharing / lock / user-mapped


def _report(kind: str, message: str, *, source: str, code: str = "",
            severity: str = "warn", **extra) -> None:
    """Silent, anonymous, opt-in-gated telemetry. Never raises, never shows
    anything to the user."""
    try:
        from . import crash_reporter as _cr
        _cr.report_event(kind, message, source=source, code=code,
                         severity=severity, extra=extra or None)
    except Exception:                                    # pragma: no cover
        pass


# ─────────────────────────────────────────────────────────────
# Failure classification - what KIND of problem is this?
# ─────────────────────────────────────────────────────────────
def classify(exc: BaseException) -> str:
    """Map an exception to the problem class we know how to heal."""
    if isinstance(exc, MemoryError):
        return "memory"
    if isinstance(exc, json.JSONDecodeError):
        return "corrupt"
    if isinstance(exc, UnicodeDecodeError):
        return "corrupt"
    if isinstance(exc, FileNotFoundError):
        return "missing"
    if isinstance(exc, IsADirectoryError):
        return "fatal"
    if isinstance(exc, PermissionError):
        return "locked"
    if isinstance(exc, OSError):
        win = getattr(exc, "winerror", None)
        if win in _TRANSIENT_WINERR:
            return "locked"
        if exc.errno == errno.ENOSPC:
            return "diskfull"
        if exc.errno in (errno.EACCES, errno.EBUSY, errno.EAGAIN):
            return "locked"
        return "io"
    # requests/urllib live behind a lazy import so this module stays dep-free.
    name = type(exc).__name__
    if name in ("ConnectionError", "Timeout", "ReadTimeout", "ConnectTimeout",
                "ChunkedEncodingError", "SSLError", "ProxyError"):
        return "network"
    return "unknown"


def _is_retryable(kind: str) -> bool:
    return kind in ("locked", "memory", "network", "io", "missing")


# ─────────────────────────────────────────────────────────────
# The healers - each one FIXES a class of problem, then says "try again"
# ─────────────────────────────────────────────────────────────
def _heal_locked(path: Path | None) -> None:
    """A stray READ-ONLY attribute is the one lock we can clear ourselves.
    (The far more common cause - an AV/indexer holding the handle for a few ms -
    is healed simply by the retry delay.)"""
    if path is None:
        return
    try:
        if path.exists():
            os.chmod(path, 0o666)
    except Exception:                                    # pragma: no cover
        pass


def _heal_memory() -> None:
    """Free everything we can, then hand the idle working set back to the OS."""
    try:
        gc.collect()
    except Exception:                                    # pragma: no cover
        pass
    try:
        from . import perf_manager
        perf_manager.trim_memory(force=True)
    except Exception:                                    # pragma: no cover
        pass


def _heal_missing(path: Path | None) -> None:
    """A write failed because the folder tree doesn't exist yet - build it."""
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:                                    # pragma: no cover
        pass


def _apply_healer(kind: str, path: Path | None) -> None:
    if kind == "locked":
        _heal_locked(path)
    elif kind == "memory":
        _heal_memory()
    elif kind == "missing":
        _heal_missing(path)


# ─────────────────────────────────────────────────────────────
# Circuit breaker - stop hammering something that is genuinely down
# ─────────────────────────────────────────────────────────────
class _Breaker:
    __slots__ = ("fails", "open_until")

    def __init__(self) -> None:
        self.fails = 0
        self.open_until = 0.0


_breakers: dict[str, _Breaker] = {}
_breaker_lock = threading.Lock()

TRIP_AFTER = 4          # consecutive failures before we stop trying
COOLDOWN_S = 30.0       # how long we serve the fallback instantly


def _breaker_allows(name: str) -> bool:
    if not name:
        return True
    with _breaker_lock:
        b = _breakers.get(name)
        if b is None:
            return True
        if b.open_until and time.time() < b.open_until:
            return False
        return True


def _breaker_record(name: str, ok: bool) -> None:
    if not name:
        return
    with _breaker_lock:
        b = _breakers.setdefault(name, _Breaker())
        if ok:
            b.fails = 0
            b.open_until = 0.0
            return
        b.fails += 1
        if b.fails >= TRIP_AFTER:
            b.open_until = time.time() + COOLDOWN_S


def reset_breaker(name: str = "") -> None:
    """Forget a tripped breaker (e.g. the user hit 'retry' explicitly)."""
    with _breaker_lock:
        if name:
            _breakers.pop(name, None)
        else:
            _breakers.clear()


# ─────────────────────────────────────────────────────────────
# THE core: run an operation, heal whatever goes wrong, never raise
# ─────────────────────────────────────────────────────────────
def attempt(op: Callable[[], T],
            *,
            fallback: T | None = None,
            name: str = "",
            path: str | os.PathLike | None = None,
            delays: Iterable[float] = _DEFAULT_DELAYS,
            raise_on_fail: bool = False,
            report: bool = True) -> T | None:
    """Run `op()`. If it fails, HEAL and retry; if it still fails, return
    `fallback` (never raises, unless raise_on_fail=True).

    `path` - the file the op touches, when there is one. It lets the healers do
             their job (clear a read-only bit, create the missing parent, …).
    `name` - a stable label for the circuit-breaker + telemetry (e.g. "swr.write").
    """
    p = Path(path) if path is not None else None

    # A resource that has failed repeatedly is skipped entirely - instant fallback
    # instead of a guaranteed-slow, guaranteed-failing round trip.
    if not _breaker_allows(name):
        return fallback

    last: BaseException | None = None
    kind = "unknown"
    delay_list = list(delays)

    for i in range(len(delay_list) + 1):
        try:
            out = op()
            if i > 0:                                    # we RECOVERED
                _breaker_record(name, True)
                # A ONE-retry recovery from a file LOCK is routine on Windows -
                # an AV scanner or the search indexer holds a small JSON for a few
                # ms and the very next attempt succeeds. Reporting it at the same
                # level as a real failure buried the genuine reports (3 of 7 in one
                # batch were this). Anything slower, or any other kind (corruption,
                # disk, memory), is still worth knowing about.
                if i > 1 or kind != "locked":
                    _report("self_healed",
                            f"{name or 'op'} recovered after {i} retry/ies ({kind})",
                            source="resilience", code=f"{kind}:{name}", severity="warn")
            else:
                _breaker_record(name, True)
            return out
        except BaseException as e:                       # noqa: BLE001 - we heal everything
            # Never swallow a control-flow exception.
            if isinstance(e, (KeyboardInterrupt, SystemExit)):
                raise
            last = e
            kind = classify(e)
            if not _is_retryable(kind) or i >= len(delay_list):
                break
            _apply_healer(kind, p)
            time.sleep(delay_list[i])

    _breaker_record(name, False)
    if report:
        _report("unhealed_error",
                f"{name or 'op'}: {type(last).__name__}: {last}",
                source="resilience", code=f"{kind}:{name}", severity="error")
    log.warning("[resilience] %s failed (%s): %s", name or "op", kind, last)
    if raise_on_fail and last is not None:
        raise last
    return fallback


def resilient(*, fallback: Any = None, name: str = "",
              delays: Iterable[float] = _DEFAULT_DELAYS):
    """Decorator form of `attempt` - wrap any risky function so it self-heals
    and returns `fallback` instead of ever exploding."""
    def deco(fn: Callable[..., T]) -> Callable[..., T | None]:
        label = name or getattr(fn, "__name__", "op")

        def wrapper(*a, **kw):
            return attempt(lambda: fn(*a, **kw), fallback=fallback,
                           name=label, delays=delays)
        wrapper.__name__ = getattr(fn, "__name__", "wrapper")
        wrapper.__doc__ = fn.__doc__
        return wrapper
    return deco


# ─────────────────────────────────────────────────────────────
# Self-healing JSON state (the launcher's sidecars all look like this)
# ─────────────────────────────────────────────────────────────
_MISSING = object()


def _sidecars(p: Path) -> list[Path]:
    """Every place a good copy of `p` might still exist, best-first.
    Covers both naming styles used across the launcher: `<name>.bak` /
    `<name>.tmp` (write_json, steam_mod) and `<stem>.json.tmp` (swr_cache,
    launcher_prefs, game_langs)."""
    return [
        p.with_name(p.name + ".bak"),
        p.with_name(p.name + ".tmp"),
        p.with_suffix(".json.tmp"),
        p.with_name(p.name + ".orig"),
    ]


def read_json(path: str | os.PathLike, default: Any = None, *,
              name: str = "", report: bool = True) -> Any:
    """Read a JSON sidecar that MUST NOT be allowed to fail.

    If the primary file is missing/corrupt/truncated we transparently fall back
    to its `.bak` (written by `write_json`) and then to a leftover `.tmp` - and
    when a sidecar turns out to be good we REPAIR the primary from it, so the
    corruption heals itself instead of coming back every launch.

    report=False - MUST be used by launcher_prefs. Telemetry asks launcher_prefs
    whether reporting is even allowed, so reporting a prefs failure would call
    back into the very read that just failed → infinite recursion.
    """
    p = Path(path)
    label = name or f"read:{p.name}"

    def _load(f: Path) -> Any:
        return json.loads(f.read_text(encoding="utf-8-sig"))

    # 1) the real file
    if p.exists():
        try:
            return _load(p)
        except Exception as e:                           # noqa: BLE001
            kind = classify(e)
            if kind == "locked":                         # just busy - retry it
                got = attempt(lambda: _load(p), fallback=_MISSING, name=label,
                              path=p, report=False)
                if got is not _MISSING:
                    return got
            log.warning("[resilience] %s unreadable (%s) - trying sidecars", p, e)

    # 2) the sidecars, best-first
    for side in _sidecars(p):
        if not side.exists():
            continue
        try:
            data = _load(side)
        except Exception:                                # noqa: BLE001
            continue
        # The sidecar is good → HEAL the primary from it, so the corruption is
        # gone for good instead of being re-discovered on every launch.
        if report:
            _report("self_healed", f"{p.name} restored from {side.name}",
                    source="resilience", code=f"corrupt:{label}", severity="warn")
        good = side
        attempt(lambda: shutil.copy2(good, p), name=f"{label}.repair",
                path=p, report=False)
        return data

    return default


def write_json(path: str | os.PathLike, data: Any, *, name: str = "",
               keep_backup: bool = True, report: bool = True) -> bool:
    """Write a JSON sidecar so that NOTHING can lose it.

    * atomic (temp + os.replace) → a crash mid-write can never truncate it
    * the previous good version is copied to `.bak` first → even a bad payload
      is recoverable by `read_json`
    * on a locked/missing/disk-full failure the healers run and we retry
    * as a last resort we park the payload in the temp dir so the data still
      exists on disk and the next successful write picks the state back up

    Returns True when the file is safely on disk.
    """
    p = Path(path)
    label = name or f"write:{p.name}"

    try:
        payload = json.dumps(data, ensure_ascii=False, indent=2)
    except (TypeError, ValueError):
        # A value isn't JSON-serialisable - don't lose the write, degrade it.
        payload = json.dumps(data, ensure_ascii=False, indent=2, default=str)

    def _do() -> bool:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".tmp")
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, p)                               # atomic commit
        if keep_backup:
            # Mirror the payload we JUST committed into `.bak`.
            #
            # The rescue copy is written from the KNOWN-GOOD bytes, never by
            # copying whatever happened to be in the primary before. That matters:
            # copying the pre-existing primary would leave NO .bak at all on the
            # first save, and would happily copy a CORRUPT primary over the last
            # good .bak - destroying the exact copy read_json needs to heal from.
            # This way the invariant "a valid copy always exists after a
            # successful save" actually holds, and the .bak can never be poisoned.
            try:
                btmp = p.with_name(p.name + ".bak.tmp")
                btmp.write_text(payload, encoding="utf-8")
                os.replace(btmp, p.with_name(p.name + ".bak"))
            except OSError:
                pass                                     # a missing .bak is survivable
        return True

    ok = attempt(_do, fallback=False, name=label, path=p, report=report)
    if ok:
        return True

    # Last resort: the real location is unusable (disk full / permissions).
    # Park the payload somewhere writable so the DATA is never lost.
    try:
        park = Path(tempfile.gettempdir()) / "translation-manager-recovery"
        park.mkdir(parents=True, exist_ok=True)
        (park / p.name).write_text(payload, encoding="utf-8")
        if report:
            _report("write_parked", f"{p.name} parked in temp (primary unwritable)",
                    source="resilience", code=f"diskfull:{label}", severity="error")
    except Exception:                                    # pragma: no cover
        pass
    return False


# ─────────────────────────────────────────────────────────────
# Self-healing network
# ─────────────────────────────────────────────────────────────
def request(op: Callable[[], T], *, fallback: T | None = None,
            name: str = "net", attempts: int = 3,
            base_delay: float = 0.25) -> T | None:
    """Run a network call with bounded exponential backoff + a circuit breaker.

    Network is the one place a longer backoff is right (a 20ms retry helps a file
    lock; it does nothing for a flaky link), so this has its own delay ladder -
    still bounded, so the UI never hangs on it.
    """
    delays = [base_delay * (2 ** i) for i in range(max(0, attempts - 1))]
    return attempt(op, fallback=fallback, name=name, delays=delays)


# ─────────────────────────────────────────────────────────────
# Self-healing file operations
# ─────────────────────────────────────────────────────────────
def file_op(fn: Callable[..., T], *args, name: str = "",
            path: str | os.PathLike | None = None,
            fallback: T | None = None, **kwargs) -> T | None:
    """Run a file operation (copy / replace / unlink / mkdir …) through the
    healer, so a transient AV lock or a stray read-only bit doesn't become a
    user-visible error."""
    label = name or getattr(fn, "__name__", "file_op")
    return attempt(lambda: fn(*args, **kwargs), fallback=fallback,
                   name=label, path=path)


def health() -> dict:
    """Diagnostics: which resources are currently tripped open."""
    now = time.time()
    with _breaker_lock:
        return {
            "open": sorted(n for n, b in _breakers.items()
                           if b.open_until and now < b.open_until),
            "failing": sorted(n for n, b in _breakers.items() if b.fails),
        }
