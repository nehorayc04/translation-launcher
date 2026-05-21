"""
Stale-While-Revalidate disk-backed cache.

Lets `main_eel.py` return last-known-good data instantly on every call,
then refresh from the live API in the background and push the fresh
result to the React frontend via Eel.

Storage:
    ~/.translation_manager/cache.json   (sibling of custom_paths.json)

Public API:
    configure(bundled_files=..., push_cb=...)        # wire at boot
    swr(kind, fetcher, *, sub_key=None, ttl=30.0)    # SWR getter
    put(kind, data, *, sub_key=None, push=True)      # manual override
    peek(kind, *, sub_key=None)                      # read without TTL
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger(__name__)

# ── Disk location ────────────────────────────────────────────────
_STORE_DIR  = Path.home() / ".translation_manager"
_STORE_FILE = _STORE_DIR / "cache.json"
SCHEMA      = 1

# ── Module state ─────────────────────────────────────────────────
_Key = tuple[str, str | None]               # (kind, sub_key)

_mem: dict[_Key, dict[str, Any]] = {}       # {(kind, sub_key): {"ts": float, "data": Any}}
_inflight: dict[_Key, threading.Event] = {} # bg-refresh dedup
_disk_lock     = threading.Lock()
_inflight_lock = threading.Lock()
_persist_pending = threading.Event()

_push_cb: Callable[[str, Any, str | None], None] | None = None
_loaded_from_disk = False


# ─────────────────────────────────────────────────────────────────
# Public configuration
# ─────────────────────────────────────────────────────────────────
def configure(*,
              bundled_files: dict[str, Path] | None = None,
              push_cb: Callable[[str, Any, str | None], None] | None = None,
              ) -> None:
    """Wire optional pieces. Safe to call multiple times.

    bundled_files maps {kind: Path} for read-only fallbacks shipped next
    to the launcher (e.g. games.json). Only used for the very first
    cold start when no cache.json exists yet.
    """
    global _push_cb
    if push_cb is not None:
        _push_cb = push_cb
    if bundled_files:
        log.info("[swr] ignoring %d bundled files — cache is network-only now",
                 len(bundled_files))
    _ensure_loaded(bundled_files or {})


# ─────────────────────────────────────────────────────────────────
# Public getters / setters
# ─────────────────────────────────────────────────────────────────
def swr(kind: str,
        fetcher: Callable[[], Any],
        *,
        sub_key: str | None = None,
        ttl: float = 30.0) -> Any:
    """SWR getter.

    1) Hot path — cached value newer than ttl  → return immediately, no work.
    2) Stale-but-present path                   → return immediately AND
                                                  spawn a background refresh.
    3) Cold path (nothing cached anywhere)      → run fetcher synchronously.

    None responses are cached only for kind=="progress" (where None = legit 404).
    For other kinds a None response is treated as "no update; keep old".
    """
    _ensure_loaded({})  # idempotent — handles modules that don't call configure()

    key: _Key = (kind, sub_key)
    now   = time.time()
    entry = _mem.get(key)

    if entry is not None:
        if (now - entry["ts"]) >= ttl:
            _maybe_refresh_bg(key, fetcher)
        return entry["data"]

    # Cold path — first ever call for this key
    try:
        fresh = fetcher()
    except Exception as e:                                # noqa: BLE001
        log.warning("[swr] cold fetch %s failed: %s", key, e)
        return None

    if fresh is None and kind != "progress":
        # Nothing to cache; caller decides on a fallback.
        return None

    _mem[key] = {"ts": time.time(), "data": fresh}
    _persist_async()
    return fresh


def put(kind: str, data: Any, *, sub_key: str | None = None, push: bool = True) -> None:
    """Manual override — used by force-refresh paths."""
    key: _Key = (kind, sub_key)
    old = _mem.get(key, {}).get("data")
    _mem[key] = {"ts": time.time(), "data": data}
    _persist_async()
    if push and _push_cb is not None and _stable_json(data) != _stable_json(old):
        try:
            _push_cb(kind, data, sub_key)
        except Exception as e:                            # noqa: BLE001
            log.warning("[swr] push callback failed for %s: %s", key, e)


def peek(kind: str, *, sub_key: str | None = None) -> Any | None:
    """Return the cached value (ignoring TTL) or None if nothing cached."""
    entry = _mem.get((kind, sub_key))
    return entry["data"] if entry else None


def touch_all() -> None:
    """Mark every cached entry as freshly-fetched (ts → now).

    Used on a tray-restore boot: the next swr() call then treats the
    disk cache as hot and SKIPS the on-demand background refresh, so a
    restore-from-tray shows the cached UI instantly with no
    refresh-on-open. The periodic poller keeps the data live afterwards.
    A genuine cold start does NOT call this, so it still refreshes."""
    now = time.time()
    for entry in _mem.values():
        entry["ts"] = now


def progress_keys() -> list[str]:
    """Sub-keys of every cached ('progress', <id>) entry — lets the
    background poller refresh exactly the games whose progress the UI
    has already shown, without guessing ids."""
    return [sk for (kind, sk) in _mem if kind == "progress" and sk is not None]


# ─────────────────────────────────────────────────────────────────
# Internal — disk seed
# ─────────────────────────────────────────────────────────────────
def _ensure_loaded(bundled_files: dict[str, Path]) -> None:
    """Idempotently load cache.json into _mem and seed missing scalar
    kinds from bundled JSON fallbacks. Called from both configure() and
    the first swr() call so callers don't have to remember to wire it."""
    global _loaded_from_disk
    if _loaded_from_disk:
        # Still allow bundled-files to fill any gaps a later caller introduces.
        _seed_bundled(bundled_files)
        return
    _loaded_from_disk = True

    if _STORE_FILE.exists():
        try:
            raw = json.loads(_STORE_FILE.read_text(encoding="utf-8"))
            entries = raw.get("entries", {}) if isinstance(raw, dict) else {}
            for kind in ("games", "news", "updates"):
                ent = entries.get(kind)
                if isinstance(ent, dict) and "data" in ent:
                    _mem[(kind, None)] = {
                        "ts":   float(ent.get("ts", 0.0)),
                        "data": ent["data"],
                    }
            prog = entries.get("progress")
            if isinstance(prog, dict):
                by_id = prog.get("by_id", {})
                if isinstance(by_id, dict):
                    for gid, ent in by_id.items():
                        if isinstance(ent, dict) and "data" in ent:
                            _mem[("progress", gid)] = {
                                "ts":   float(ent.get("ts", 0.0)),
                                "data": ent["data"],
                            }
            log.info("[swr] loaded %d entries from %s", len(_mem), _STORE_FILE)
        except (OSError, json.JSONDecodeError, ValueError) as e:
            log.warning("[swr] %s unreadable (%s) — starting empty", _STORE_FILE, e)

    _seed_bundled(bundled_files)


def _seed_bundled(_bundled_files: dict[str, Path]) -> None:
    """Intentionally a no-op.

    Earlier versions seeded the cache from JSON files shipped with the
    installer. That caused users without internet on first launch to see
    stale data from whenever the installer was signed. The cache is now
    network-only: first launch MUST be online; everything else is served
    from cache.json on disk.
    """
    return


# ─────────────────────────────────────────────────────────────────
# Internal — background refresh
# ─────────────────────────────────────────────────────────────────
def _maybe_refresh_bg(key: _Key, fetcher: Callable[[], Any]) -> None:
    """Refresh `key` in the background unless a refresh is already running.
    The in-flight lock prevents the thundering-herd problem when 12 game
    cards all ask for the same progress key in the same React tick.

    The refresh runs on a gevent GREENLET, not a real OS thread: on a
    successful refresh `_bg_worker` calls `_push_cb` → eel.cache_refreshed
    (...)(), and that eel bridge call is bound to the launcher's main
    gevent hub. Invoking it from a separate OS thread fails silently — so
    the live UI update never arrives and the data only appears to refresh
    on the next component re-mount. A greenlet shares the hub; the
    fetcher's `requests` call still cooperatively yields."""
    with _inflight_lock:
        if key in _inflight:
            return
        _inflight[key] = threading.Event()

    try:
        import gevent
        gevent.spawn(_bg_worker, key, fetcher)
    except Exception:                                     # pragma: no cover
        # No gevent (e.g. a non-launcher caller) — fall back to a thread.
        threading.Thread(target=_bg_worker, args=(key, fetcher), daemon=True).start()


def _bg_worker(key: _Key, fetcher: Callable[[], Any]) -> None:
    try:
        try:
            fresh = fetcher()
        except Exception as e:                            # noqa: BLE001
            log.warning("[swr] bg refresh %s failed: %s", key, e)
            return

        if fresh is None and key[0] != "progress":
            # Treat as "no update" — keep the cached value intact.
            return

        old = _mem.get(key, {}).get("data")
        try:
            changed = _stable_json(fresh) != _stable_json(old)
        except (TypeError, ValueError):
            changed = True

        _mem[key] = {"ts": time.time(), "data": fresh}
        _persist_async()

        if changed and _push_cb is not None:
            try:
                _push_cb(key[0], fresh, key[1])
            except Exception as e:                        # noqa: BLE001
                log.warning("[swr] push callback failed for %s: %s", key, e)
    finally:
        with _inflight_lock:
            evt = _inflight.pop(key, None)
        if evt is not None:
            evt.set()


# ─────────────────────────────────────────────────────────────────
# Internal — persistence
# ─────────────────────────────────────────────────────────────────
def _persist_async() -> None:
    """Schedule a debounced disk write. Coalesces multiple updates that
    land within ~200ms into a single fsync."""
    if _persist_pending.is_set():
        return
    _persist_pending.set()
    threading.Thread(target=_persist_worker, daemon=True).start()


def _persist_worker() -> None:
    try:
        time.sleep(0.2)                 # debounce window
        _persist_pending.clear()        # any write landing now schedules a new worker
        _persist_now()
    except Exception as e:                                # noqa: BLE001
        log.warning("[swr] persist worker failed: %s", e)


def _persist_now() -> None:
    snapshot = _build_snapshot()
    with _disk_lock:
        try:
            _STORE_DIR.mkdir(parents=True, exist_ok=True)
            tmp = _STORE_FILE.with_suffix(".json.tmp")
            try:
                payload = json.dumps(snapshot, ensure_ascii=False, indent=2)
            except UnicodeEncodeError:
                # A remote field contains lone UTF-16 surrogates (caused by an
                # earlier mojibake admin save). ensure_ascii=False would emit
                # those as raw bytes; flip to ascii-safe so we write valid
                # JSON instead of crashing the SWR loop and breaking the Eel
                # bridge (which black-screens the launcher).
                payload = json.dumps(snapshot, ensure_ascii=True, indent=2)
            tmp.write_text(payload, encoding="utf-8")
            os.replace(tmp, _STORE_FILE)
        except OSError as e:
            log.warning("[swr] disk write to %s failed: %s", _STORE_FILE, e)


def _build_snapshot() -> dict[str, Any]:
    entries: dict[str, Any] = {}
    progress_by_id: dict[str, Any] = {}
    for (kind, sub_key), entry in _mem.items():
        if kind == "progress":
            if sub_key is not None:
                progress_by_id[sub_key] = {"ts": entry["ts"], "data": entry["data"]}
        else:
            entries[kind] = {"ts": entry["ts"], "data": entry["data"]}
    if progress_by_id:
        entries["progress"] = {"by_id": progress_by_id}
    return {"schema": SCHEMA, "entries": entries}


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────
def _stable_json(obj: Any) -> str:
    # ensure_ascii=True so a lone surrogate in any field (e.g. corrupted
    # progress.unit from a mojibake admin save) doesn't raise UnicodeEncodeError
    # and abort the change-detection diff inside the SWR poll loop.
    return json.dumps(obj, sort_keys=True, ensure_ascii=True, default=str)
