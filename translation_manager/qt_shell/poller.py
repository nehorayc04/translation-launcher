"""
Catalog poller - QTimer + QThreadPool replacement for the Eel build's
gevent-based `main_eel._start_catalog_poller`.

How it ticks:
  * QTimer fires every _POLL_INTERVAL_MS on the GUI thread.
  * The slot dispatches a single _PollRunnable to QThreadPool.
  * The runnable hits the same _fetch_catalog_live_first /
    _try_software_remote / _try_remote helpers main_eel already owns.
  * swr_cache.put detects a change vs the cached value and fires the
    push callback registered in main_eel - which, under the Qt shell,
    routes through eel_shim into bridge.cache_refreshed.emit so the
    React frontend live-updates without a poll on its side.

Thread safety: the runnable runs on a thread-pool worker; it calls
swr_cache.put which is internally locked. swr_cache's push callback
also runs on the worker thread, but the bridge Signal it ends up
emit-ing is auto-queued to the bridge's home thread (main) by Qt.

Lifetime: caller (main_qt.py) holds the CatalogPoller reference so the
inner QTimer survives. .start() is idempotent.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer

log = logging.getLogger(__name__)

_POLL_INTERVAL_MS = 60_000


class _PollRunnable(QRunnable):
    """One refresh tick. Cheap to construct; runs once and is
    auto-deleted by QThreadPool."""

    def __init__(self, backend: Any) -> None:
        super().__init__()
        self._b = backend
        self.setAutoDelete(True)

    def run(self) -> None:
        from translation_manager import swr_cache
        try:
            games = self._b._fetch_catalog_live_first()
            if games is not None:
                swr_cache.put("games", games)

            software = self._b._try_software_remote()
            if software is not None:
                swr_cache.put("software", software)

            news = self._b._try_remote(self._b.REMOTE_NEWS_URL)
            if news is not None:
                swr_cache.put("news", news)

            updates = self._b._try_remote(self._b.REMOTE_UPDATES_URL)
            if updates is not None:
                swr_cache.put("updates", updates)

            # Refresh per-game progress, but only for games whose progress
            # the UI has already shown - same scoping rule as the Eel
            # version, no guessing of ids.
            for gid in swr_cache.progress_keys():
                try:
                    swr_cache.put("progress",
                                  self._b._fetch_progress(gid),
                                  sub_key=gid)
                except Exception:
                    pass
        except Exception:
            log.exception("catalog poller tick failed")


class CatalogPoller(QObject):
    """Holds the QTimer + the backend reference used by each tick.

    Construct in main_qt.py with the (eel-shimmed) main_eel module, then
    call .start() once after the bridge is wired into eel_shim."""

    def __init__(self, backend: Any, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._b = backend
        self._timer = QTimer(self)
        self._timer.setInterval(_POLL_INTERVAL_MS)
        self._timer.timeout.connect(self._on_tick)

    def start(self) -> None:
        if not self._timer.isActive():
            self._timer.start()
            log.info("catalog poller started (every %sms)", _POLL_INTERVAL_MS)

    def stop(self) -> None:
        self._timer.stop()

    def force_tick_now(self) -> None:
        """Useful from tests / smoke checks - forces a tick without
        waiting the full interval. Same dispatch path as the timer."""
        self._on_tick()

    def _on_tick(self) -> None:
        QThreadPool.globalInstance().start(_PollRunnable(self._b))
