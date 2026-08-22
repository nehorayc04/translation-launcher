"""
QWebEngineProfile + QWebChannel bootstrap.

A single profile is shared across the main window AND the PayPal popup
QDialog so Supabase's localStorage session survives both. The profile's
persistent storage lives next to the launcher's other per-user state in
`~/.translation_manager/qtwebengine/` so an uninstall-clean install
leaves no orphan cache.

Script injection - the QWebChannel boot is wired here:

  1. qwebchannel.js  is read from Qt's bundled resources and injected at
     DocumentCreation on every page load.
  2. _BRIDGE_BOOT    constructs the channel, exposes `window.bridge`, and
     dispatches `bridge:ready` so the eel.ts shim can resolve its queue.

The injection is set up ONCE on the profile, then automatically applies
to every page the profile serves (main window + popup).
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import QFile, QIODevice
from PySide6.QtWebEngineCore import (
    QWebEngineProfile,
    QWebEngineScript,
    QWebEngineSettings,
)

log = logging.getLogger(__name__)


def _read_qwebchannel_js() -> str:
    """Pull qwebchannel.js from Qt's compiled-in resources (PySide6 ships
    it under :/qtwebchannel/qwebchannel.js). Falls back to an empty string
    if the resource isn't reachable - caller logs and the bridge stays
    silent rather than crashing the launcher."""
    f = QFile(":/qtwebchannel/qwebchannel.js")
    if not f.open(QIODevice.ReadOnly | QIODevice.Text):
        log.warning("qt_shell: qwebchannel.js resource missing - bridge will not boot")
        return ""
    try:
        data = bytes(f.readAll()).decode("utf-8", errors="replace")
    finally:
        f.close()
    return data


# Boot script: hook the channel transport Qt injects into every page,
# pin the bridge onto window.bridge, then fire 'bridge:ready' so the
# JS shim resolves any pending RPC calls.
_BRIDGE_BOOT = """
(function () {
    if (window.__bridgeBooted) return;
    window.__bridgeBooted = true;
    function boot() {
        if (typeof QWebChannel === 'undefined' || !window.qt || !qt.webChannelTransport) {
            return setTimeout(boot, 30);
        }
        new QWebChannel(qt.webChannelTransport, function (channel) {
            window.bridge = channel.objects.bridge;
            window.dispatchEvent(new CustomEvent('bridge:ready'));
        });
    }
    boot();
})();
"""


def _resolve_storage_root() -> Path:
    """Where QtWebEngine keeps its on-disk cache + persistent storage.

    Ubisoft-style: in a FROZEN install we put it in a `data/` folder INSIDE
    the install directory (next to the exe) - the installer grants Users
    modify rights on it, and deleting that folder simply makes the launcher
    re-download every cover/banner/logo on next run (the images are no longer
    bundled). If that folder isn't writable (e.g. a locked-down Program Files
    without the granted ACL), or in a dev run, fall back to the per-user
    `~/.translation_manager/qtwebengine` location so caching never breaks."""
    if getattr(sys, "frozen", False):
        data_dir = Path(sys.executable).parent / "data" / "webengine"
        try:
            data_dir.mkdir(parents=True, exist_ok=True)
            probe = data_dir / ".write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return data_dir
        except Exception:
            log.info("qt_shell: install-dir data folder not writable - "
                     "falling back to the per-user cache location")
    return Path.home() / ".translation_manager" / "qtwebengine"


def build_profile(parent=None) -> QWebEngineProfile:
    """Create the persistent profile + register the bootstrap script.

    Returns a profile that is safe to pass to QWebEnginePage(profile,
    parent) for both the main window and the popup."""
    storage_root = _resolve_storage_root()
    try:
        storage_root.mkdir(parents=True, exist_ok=True)
        cache_root = storage_root / "cache"
        cache_root.mkdir(parents=True, exist_ok=True)
        profile = QWebEngineProfile("translation-manager-qt", parent)
        profile.setPersistentStoragePath(str(storage_root))
        profile.setCachePath(str(cache_root))
        # CAP the HTTP disk cache. Left at Qt's default (0 = "let Chromium
        # decide") this grows on its own schedule under {app}\data\webengine -
        # which matters on a small/full SSD. We only cache our own small static
        # assets + cover images, so 96 MB is generous.
        profile.setHttpCacheMaximumSize(96 * 1024 * 1024)
        profile.setPersistentCookiesPolicy(QWebEngineProfile.ForcePersistentCookies)
    except Exception:
        # If even the per-user fallback dir is unwritable (disk full /
        # locked-down roaming profile), an unguarded mkdir or profile ctor
        # would raise out of main() BEFORE the window exists → a blank boot
        # crash. Degrade to an OFF-THE-RECORD (in-memory) profile instead:
        # no cookie/cache persistence this session (a login won't survive a
        # restart), but the launcher BOOTS and stays fully usable.
        log.warning("qt_shell: persistent profile unavailable - falling back "
                    "to an in-memory profile (no cookie/cache persistence)")
        try:
            profile = QWebEngineProfile(parent)      # no name → off-the-record
        except Exception:
            profile = QWebEngineProfile()            # absolute last resort

    # DevTools (F12 in QtWebEngine when QTWEBENGINE_REMOTE_DEBUGGING is
    # set). DeveloperExtrasEnabled enables the right-click "Inspect"
    # affordance - useful while we validate the bridge end-to-end.
    settings = profile.settings()
    settings.setAttribute(QWebEngineSettings.JavascriptEnabled,              True)
    settings.setAttribute(QWebEngineSettings.LocalStorageEnabled,            True)
    settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
    settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls,  True)
    settings.setAttribute(QWebEngineSettings.PlaybackRequiresUserGesture,    False)
    settings.setAttribute(QWebEngineSettings.AllowRunningInsecureContent,    False)
    # NOTE: the Google-login "copy link" button writes via the NATIVE Qt
    # clipboard (qt_shell.bridge.copy_to_clipboard) - we intentionally do NOT
    # flip QtWebEngine's JS clipboard attributes here (they proved an
    # instability source and the native slot makes them unnecessary).

    qwebchannel_js = _read_qwebchannel_js()
    boot_script = QWebEngineScript()
    boot_script.setName("qt-bridge-boot")
    boot_script.setSourceCode(qwebchannel_js + _BRIDGE_BOOT)
    boot_script.setInjectionPoint(QWebEngineScript.DocumentCreation)
    boot_script.setWorldId(QWebEngineScript.MainWorld)
    boot_script.setRunsOnSubFrames(False)
    profile.scripts().insert(boot_script)

    return profile
