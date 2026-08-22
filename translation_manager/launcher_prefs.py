"""
Persisted user preferences for the launcher window/lifecycle.

Stores a small JSON file alongside the launcher's other per-user state
(`~/.translation_manager/launcher_prefs.json`). Used to remember:

- close_behavior  : "minimize" | "close" | None (None == ask the user)
- start_with_os   : whether the launcher should boot at Windows startup
                    (the actual registry write is in `autostart.py`; this
                    is the source-of-truth flag the UI toggle binds to)

API is intentionally tiny - every read returns a fresh dict so callers
don't have to worry about cache invalidation, and every write is atomic
(temp file + os.replace) so a crashed process can't leave the file half-
written.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal, TypedDict

log = logging.getLogger(__name__)

CloseBehavior = Literal["minimize", "close"]


class LauncherPrefs(TypedDict, total=False):
    close_behavior:   CloseBehavior      # None = unset → first-launch modal
    start_with_os:    bool               # mirrors the registry state
    cleared_software: list[str]          # software ids whose path the user
                                         # "forgot" - treated as not-installed
                                         # until the next full scan re-detects
    crash_reporting:  bool               # send crash/error reports to the dev
                                         # (default True; Settings toggle opts out)
    crash_notice_seen: bool              # one-time "we report crashes" notice ack
    mod_beta_channel: bool               # opt in to pre-release (alpha/beta/rc)
                                         # mod updates globally (default False)
    mod_beta_overrides: dict             # per-mod beta opt-in override:
                                         # {game_id: bool} wins over the global
    app_icon:         str                # chosen app-icon variant id (see
                                         # app_icon.VARIANTS); default brand icon
    disable_gpu_compositing: bool        # opt OUT of GPU compositing (default
                                         # False = GPU on, smooth UI). Set True
                                         # only as a flicker workaround when
                                         # another workload saturates the GPU;
                                         # applied by main_qt at next boot.
    # NOTE: silent auto-update was removed by request - updates are ALWAYS
    # surfaced as an in-app message + a Windows notification; nothing installs
    # without the user clicking "update". No `mod_auto_update` pref remains.


_STATE_DIR  = Path.home() / ".translation_manager"
_STATE_FILE = _STATE_DIR / "launcher_prefs.json"


# ─────────────────────────────────────────────────────────────
# ⚠ report=False on BOTH calls is load-bearing, not a style choice.
# Telemetry (crash_reporter) asks launcher_prefs whether reporting is even
# allowed. If a prefs read/write failure reported itself, the reporter would call
# back into the very load() that just failed → infinite recursion. This file is
# the one place that must heal SILENTLY.
def load() -> LauncherPrefs:
    """Self-healing read. A corrupt prefs file no longer silently resets every
    setting the user chose (reporting opt-out, close behaviour, beta channel):
    resilience serves the `.bak` sidecar and repairs the primary from it."""
    from . import resilience
    data = resilience.read_json(_STATE_FILE, default={}, name="launcher_prefs",
                                report=False)
    return data if isinstance(data, dict) else {}


def save(prefs: LauncherPrefs) -> bool:
    """Self-healing, atomic write (temp + os.replace, previous version kept as
    `.bak`, retried through a transient file lock). True on success."""
    from . import resilience
    return bool(resilience.write_json(_STATE_FILE, prefs, name="launcher_prefs",
                                      report=False))


# ── convenience getters / setters ────────────────────────────
def get_close_behavior() -> CloseBehavior:
    # DEFAULT = "minimize": clicking X keeps the launcher running in the tray
    # (no first-run prompt). The user can flip it to "close" from Settings.
    val = load().get("close_behavior")
    if val in ("minimize", "close"):
        return val  # type: ignore[return-value]
    return "minimize"


def set_close_behavior(behavior: CloseBehavior) -> bool:
    prefs = load()
    prefs["close_behavior"] = behavior
    return save(prefs)


def clear_close_behavior() -> bool:
    prefs = load()
    prefs.pop("close_behavior", None)
    return save(prefs)


def get_start_with_os() -> bool:
    return bool(load().get("start_with_os", False))


def set_start_with_os(enabled: bool) -> bool:
    prefs = load()
    prefs["start_with_os"] = bool(enabled)
    return save(prefs)


# ── GPU acceleration (compositing) ────────────────────────────
# Default OFF (i.e. GPU compositing stays ON → smooth UI). Flip True only when
# the user reports flicker; main_qt reads this at boot to add
# --disable-gpu-compositing.
def get_disable_gpu_compositing() -> bool:
    return bool(load().get("disable_gpu_compositing", False))


def set_disable_gpu_compositing(disabled: bool) -> bool:
    prefs = load()
    prefs["disable_gpu_compositing"] = bool(disabled)
    return save(prefs)


# ── Custom frameless title bar ────────────────────────────────
# Default ON (in-app frosted title bar) per user request - the OS title bar is
# replaced with an in-app one (min/max/close drawn by React, drag via
# startSystemMove, resize via startSystemResize). Applied at window creation, so
# a change needs a restart. STILL reversible from Settings AND the tray (so a
# broken frameless window can always be undone). main_window reads this at boot.
def get_custom_titlebar() -> bool:
    return bool(load().get("custom_titlebar", True))


def set_custom_titlebar(enabled: bool) -> bool:
    prefs = load()
    prefs["custom_titlebar"] = bool(enabled)
    return save(prefs)


# ── App icon variant (window/taskbar/tray + launch shortcut) ──
# One of the ids in app_icon.VARIANTS (e.g. "5g-circle-round"). The chosen
# variant is applied LIVE to the window/taskbar/tray and its .ico is pointed at
# by the Start-menu/Desktop/pinned shortcuts. Default = the brand icon (matches
# the website + the splash/sidebar logo). Stored as a plain string; app_icon
# validates it (an unknown value falls back to the default).
_APP_ICON_DEFAULT = "brand"


def get_app_icon() -> str:
    val = load().get("app_icon")
    return val if isinstance(val, str) and val else _APP_ICON_DEFAULT


def set_app_icon(variant: str) -> bool:
    prefs = load()
    prefs["app_icon"] = str(variant)
    return save(prefs)


# ── "forgotten" software paths ────────────────────────────────
# Software install paths are auto-detected (registry/path fingerprints).
# The user can "forget" one from Settings; it then reports as not-installed
# until a full scan (which clears the whole forgotten set) re-detects it.
def get_cleared_software() -> list[str]:
    val = load().get("cleared_software")
    return [str(x) for x in val] if isinstance(val, list) else []


def add_cleared_software(software_id: str) -> bool:
    prefs = load()
    cur = prefs.get("cleared_software")
    cleared = list(cur) if isinstance(cur, list) else []
    if software_id and software_id not in cleared:
        cleared.append(software_id)
    prefs["cleared_software"] = cleared
    return save(prefs)


def clear_all_cleared_software() -> bool:
    """Drop the whole forgotten-set - called by a full software scan."""
    prefs = load()
    if "cleared_software" in prefs:
        prefs.pop("cleared_software", None)
        return save(prefs)
    return True


# ── mod update channel / behaviour ────────────────────────────
# DEFAULT = True. Every translation we ship is currently a pre-release (beta),
# so an opt-OUT default stranded users on their first version and hid real
# updates. Users who dislike betas turn it off in Settings (or per-mod).
_BETA_DEFAULT = True


def get_beta_channel() -> bool:
    """Global opt-in to pre-release (alpha/beta/rc) mod updates."""
    return bool(load().get("mod_beta_channel", _BETA_DEFAULT))


def set_beta_channel(enabled: bool) -> bool:
    prefs = load()
    prefs["mod_beta_channel"] = bool(enabled)
    return save(prefs)


def wants_prerelease(game_id: str) -> bool:
    """Whether to OFFER pre-release updates for this mod: the per-mod override
    (if set) wins over the global beta-channel flag."""
    prefs = load()
    ov = prefs.get("mod_beta_overrides")
    if isinstance(ov, dict) and game_id in ov:
        return bool(ov[game_id])
    return bool(prefs.get("mod_beta_channel", _BETA_DEFAULT))


def set_mod_beta_override(game_id: str, enabled: bool | None) -> bool:
    """Set (or, with None, clear → fall back to the global flag) the per-mod
    beta opt-in override."""
    prefs = load()
    ov = prefs.get("mod_beta_overrides")
    ov = dict(ov) if isinstance(ov, dict) else {}
    if enabled is None:
        ov.pop(game_id, None)
    else:
        ov[game_id] = bool(enabled)
    prefs["mod_beta_overrides"] = ov
    return save(prefs)


