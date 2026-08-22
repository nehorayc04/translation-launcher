"""
plugins.host - the runtime that actually RUNS enabled plugins in the background.

One daemon thread ticks about once a minute. Each tick it looks at the installed
plugin state and does whatever is due - for the save-backup plugin that means
running any save entry whose schedule (daily / weekly / monthly / realtime) has
come around. Explicit events (on_boot, on_launch) are driven by `on_boot()` /
`on_game_launch()`, called from the app lifecycle.

Design rules:
  • The thread NEVER dies - every tick is wrapped; a bad entry can't stop the loop.
  • It is a good neighbour: it uses `perf_manager.should_defer_heavy()` to skip a
    heavy copy while a game has the machine pegged, and retries next tick.
  • Idempotent: `sync()` / `start()` can be called any number of times.
  • Backups keep running once ENABLED - entitlement is enforced when the user
    turns a plugin on, not re-checked every tick (so a network blip never stops
    a backup that's already protecting the user's saves).
"""
from __future__ import annotations

import logging
import threading

log = logging.getLogger(__name__)

_TICK_S = 60.0

_thread: threading.Thread | None = None
_stop = threading.Event()
_wake = threading.Event()
_lock = threading.Lock()


# ─────────────────────────────────────────────────────────────
# Lifecycle
# ─────────────────────────────────────────────────────────────
def start() -> None:
    """Start the scheduler thread if any plugin is enabled. Idempotent."""
    global _thread
    with _lock:
        if _thread is not None and _thread.is_alive():
            return
        if not _any_enabled():
            return
        _stop.clear()
        _thread = threading.Thread(target=_loop, name="plugin-host", daemon=True)
        _thread.start()
        log.info("[plugins] host started")


def stop() -> None:
    _stop.set()
    _wake.set()
    # A long-lived worker holds LEASED work: without a graceful release those
    # lines sit unavailable to everyone until the lease expires. Give it a short
    # moment to push what it finished and hand the rest back.
    try:
        from . import community_compute
        community_compute.stop_all(join_seconds=3.0)
    except Exception:                                    # pragma: no cover
        pass


def sync() -> None:
    """Called when plugin install-state changes: make sure the thread is running
    if it needs to be, and wake it so a newly-enabled schedule takes effect now."""
    try:
        start()
        _wake.set()
    except Exception:                                    # pragma: no cover
        pass


def _any_enabled() -> bool:
    try:
        from . import registry
        return any(e.get("enabled") for e in registry.installed().values())
    except Exception:                                    # pragma: no cover
        return False


# ─────────────────────────────────────────────────────────────
# The loop
# ─────────────────────────────────────────────────────────────
def _loop() -> None:
    while not _stop.is_set():
        try:
            _tick()
        except Exception:                                # pragma: no cover
            log.exception("[plugins] host tick failed")
        # Sleep, but wake early on sync()/stop().
        _wake.wait(_TICK_S)
        _wake.clear()


def _tick() -> None:
    from . import registry
    # A plugin the admin REMOVED (or hid) from the catalog must stop working, not
    # keep running forever off its local install-state. It disappears from the
    # UI the moment the catalog changes, so a still-running one would be
    # invisible AND unstoppable. An empty/failed catalog read is ignored - a blip
    # must never shut a volunteer's worker or a user's backups down.
    try:
        live = {p["id"] for p in registry.available()} or None
    except Exception:                                    # pragma: no cover
        live = None
    for pid, ent in registry.installed().items():
        if live is not None and pid not in live:
            if ent.get("kind") == "community_compute":
                _sync_community_compute(pid, force_off=True)
            continue
        if ent.get("kind") == "community_compute":
            # Owns its OWN long-lived thread (a pull loop, not a scheduled job),
            # so the host only reconciles it with the install/enable state - and
            # it must be reconciled even when DISABLED, so it gets stopped.
            _sync_community_compute(pid)
            continue
        if not ent.get("enabled"):
            continue
        if ent.get("kind") == "save_backup":
            _run_save_backup(pid, only_due=True)


def _sync_community_compute(pid: str, force_off: bool = False) -> None:
    try:
        from . import community_compute
        if force_off:
            community_compute.stop(pid)                   # pulled from the catalog
        else:
            community_compute.sync(pid)
    except Exception:                                    # pragma: no cover
        log.exception("[plugins] community_compute sync failed")


def _defer() -> bool:
    try:
        from .. import perf_manager
        return perf_manager.should_defer_heavy()
    except Exception:                                    # pragma: no cover
        return False


def _run_save_backup(pid: str, *, only_due: bool, game_id: str | None = None,
                     schedules: tuple[str, ...] | None = None) -> int:
    """Run this plugin's due (or event-triggered) save entries. Returns the
    number of entries actually backed up. Persists updated last-run times."""
    from . import registry, save_backup
    cfg = registry.get_config(pid)
    entries = cfg.get("entries") or []
    if not entries:
        return 0

    ran = 0
    touched: dict = {}                                    # entry-id -> new "last" record
    for entry in entries:
        if not entry.get("enabled", True):
            continue
        if game_id is not None and entry.get("game_id") != game_id:
            continue
        # Which schedules this call is allowed to fire (None = "the due ones").
        if schedules is not None:
            if cfg.get("schedule") not in schedules:
                continue
        elif only_due and not save_backup.is_due(entry, cfg):
            continue
        if _defer():
            continue                                     # a game owns the machine - next tick
        res = save_backup.backup_entry(entry, cfg)
        if res.get("ok") and not res.get("skipped"):
            ran += 1
            eid = entry.get("id", "")
            touched[eid] = (cfg.get("last") or {}).get(eid)
        elif res.get("skipped"):
            # backup_entry only updates last-run on a real copy; a skip still
            # advances nothing, which is correct.
            pass

    if touched:
        # A run can take minutes (real disk copies); patch_nested merges only
        # the entry ids THIS run actually touched onto the CURRENT "last" map,
        # so a concurrent run for other entries - or a user editing `entries`
        # in Settings meanwhile - is never clobbered by this stale `cfg`.
        registry.patch_nested(pid, "last", touched)
    return ran


# ─────────────────────────────────────────────────────────────
# Lifecycle events (called from the app)
# ─────────────────────────────────────────────────────────────
def on_boot() -> None:
    """App just started: run any 'on_boot' backups + catch up anything overdue,
    then make sure the scheduler is alive. Runs off the caller's thread."""
    def _work() -> None:
        try:
            from . import registry
            for pid, ent in registry.installed().items():
                if not (ent.get("enabled") and ent.get("kind") == "save_backup"):
                    continue
                _run_save_backup(pid, only_due=False, schedules=("on_boot",))
                _run_save_backup(pid, only_due=True)     # catch up daily/weekly/…
        except Exception:                                # pragma: no cover
            log.exception("[plugins] on_boot failed")
        finally:
            start()
    threading.Thread(target=_work, name="plugin-onboot", daemon=True).start()


def on_game_launch(game_id: str) -> None:
    """A game was just launched: fire its 'on_launch' + 'realtime' save backups."""
    if not game_id:
        return

    def _work() -> None:
        try:
            from . import registry
            for pid, ent in registry.installed().items():
                if not (ent.get("enabled") and ent.get("kind") == "save_backup"):
                    continue
                # The schedule + the entries list are BOTH global (one schedule
                # for all entries), so an "on_launch" run must fire EVERY on_launch
                # entry, not only the launched game's - manual/generic/Ubisoft
                # entries carry game_id "manual"/"generic"/"ubi_*", never a catalog
                # id, so a game_id filter here would silently never back them up.
                # (No dup work: backup_entry skips an unchanged folder by fingerprint.)
                _run_save_backup(pid, only_due=False,
                                 schedules=("on_launch", "realtime"))
        except Exception:                                # pragma: no cover
            log.exception("[plugins] on_game_launch failed")
    threading.Thread(target=_work, name="plugin-launch", daemon=True).start()


def run_now(pid: str, name: str = "") -> dict:
    """User pressed 'back up now' - force every entry regardless of schedule.
    An optional `name` labels the snapshot folder for all entries in this run."""
    from . import registry, save_backup
    cfg = registry.get_config(pid)
    entries = cfg.get("entries") or []
    ran, errors = 0, []
    touched: dict = {}                                    # entry-id -> new "last" record
    for entry in entries:
        if not entry.get("enabled", True):
            continue
        res = save_backup.backup_entry(entry, cfg, force=True, name=name)
        if res.get("ok") and not res.get("skipped"):
            ran += 1
            eid = entry.get("id", "")
            touched[eid] = (cfg.get("last") or {}).get(eid)
        elif not res.get("ok"):
            errors.append({"label": entry.get("label"), "error": res.get("error")})
    if touched:
        # Same lost-update guard as `_run_save_backup` above: only merge the
        # ids this manual run actually backed up onto the CURRENT "last" map.
        registry.patch_nested(pid, "last", touched)
    # ok reflects REALITY: a forced run that copied nothing because every entry
    # ERRORED (source gone / drive offline / permission denied) must NOT report
    # success - the whole point of this feature is protecting saves, so a silent
    # "no changes" on total failure is a data-loss illusion. (A forced run can
    # never legitimately return 0 with no errors: force=True skips the
    # unchanged-fingerprint short-circuit, so 0-copied means every entry failed.)
    return {"ok": not errors, "backed_up": ran, "errors": errors}
