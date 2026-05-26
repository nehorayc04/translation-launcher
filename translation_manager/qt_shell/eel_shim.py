"""
Drop-in stand-in for the `eel` module so main_eel.py imports clean under
the Qt shell. Lets us reuse every @eel.expose function 1:1 instead of
re-implementing the 45-method bridge surface twice.

Install BEFORE importing main_eel:

    import sys
    from translation_manager.qt_shell import eel_shim
    sys.modules['eel'] = eel_shim

After Bridge is built, wire push-channel forwarding:

    eel_shim.set_bridge(bridge)

What the shim covers:
  * `@eel.expose`        - no-op decorator (returns the function untouched)
  * `eel.init` / `eel.start` - no-ops (Qt owns the window + transport)
  * `eel.cache_refreshed(...)()`, `eel.mod_install_progress(...)()`,
    `eel.update_download_progress(...)()`, `eel.launcher_update_progress(...)()`
        - routed to the matching Qt Signal on the Bridge object so the
          existing main_eel push callsites need ZERO changes.

The double-call shape (e.g. eel.cache_refreshed(a, b) followed by an
empty trailing call) is Eel's idiom: the first call captures args, the
trailing one dispatches over the websocket. We mirror it so the existing
swr_cache._push_cb / _push_download_progress / _emit_* callsites keep
working verbatim - the inner thunk just calls signal.emit(*args).
"""

from __future__ import annotations

from typing import Any, Callable, Optional

_BRIDGE: Any = None


def set_bridge(bridge: Any) -> None:
    """Install the Qt Bridge instance the push channels will forward to."""
    global _BRIDGE
    _BRIDGE = bridge


def _emit(signal_name: str, *args: Any) -> None:
    if _BRIDGE is None:
        return
    sig = getattr(_BRIDGE, signal_name, None)
    if sig is None:
        return
    try:
        sig.emit(*args)
    except Exception:
        # A swallow here is mandatory - backend code calls these on every
        # SWR tick + every progress callback, and a misfire must never
        # break the actual install / refresh path.
        pass


class _PushChannel:
    """Mimics the Eel push-channel idiom (call once with args, then call
    the returned thunk to dispatch). Here the thunk forwards to a Qt
    Signal on the live Bridge instance."""

    def __init__(self, name: str) -> None:
        self._name = name

    def __call__(self, *args: Any) -> Callable[[], None]:
        captured = args

        def _thunk() -> None:
            _emit(self._name, *captured)

        return _thunk


cache_refreshed          = _PushChannel("cache_refreshed")
mod_install_progress     = _PushChannel("mod_install_progress")
update_download_progress = _PushChannel("update_download_progress")
launcher_update_progress = _PushChannel("launcher_update_progress")


def expose(fn: Callable) -> Callable:
    """No-op replacement for @eel.expose. The Bridge re-exposes each
    function as a @Slot, so this decorator just needs to leave the
    function intact."""
    return fn


def init(_path: Optional[str] = None, *_args: Any, **_kwargs: Any) -> None:
    """Eel init is irrelevant under the Qt shell - the QWebEngineProfile
    owns the HTML root, not the eel.init directory."""
    return None


def start(*_args: Any, **_kwargs: Any) -> None:
    """Eel start is irrelevant under the Qt shell - QApplication owns the
    event loop, not eel.start."""
    return None
