"""
Deep-link support - the custom `hebrewhub://game/<id>` URL protocol.

The website's personal-area "פתח בתוכנה" button opens this protocol so the
launcher pops to the foreground on the specific game's card. Windows-only
(every function no-ops elsewhere). Three responsibilities:

  1. register_scheme()  - register the `hebrewhub` protocol under HKCU (no admin
     needed); re-run every launch so the exe path stays correct after an
     install/move. Self-healing.
  2. parse_and_strip()  - pull a `hebrewhub://game/<id>` arg out of argv (and
     remove it) so argparse / QApplication never trip on the extra positional;
     returns the <id>.
  3. pending-file handoff - when a SECOND instance is launched with the URI it
     writes the id to a temp file and signals the running instance (the
     named-event signal itself can't carry a payload); the owner reads it and
     navigates.
"""
from __future__ import annotations

import logging
import re
import sys
import tempfile
import time
from pathlib import Path

log = logging.getLogger(__name__)

SCHEME   = "hebrewhub"
_URI_RE  = re.compile(r"^hebrewhub://game/([A-Za-z0-9_-]{1,64})", re.IGNORECASE)
_PENDING = Path(tempfile.gettempdir()) / "translation_manager_deeplink_qt.txt"


def parse_and_strip(argv: list[str]) -> str | None:
    """Find a hebrewhub://game/<id> arg, REMOVE it from argv in place, and
    return the <id> (None if absent). Stripping keeps argparse + QApplication
    from choking on the unexpected positional."""
    found: str | None = None
    keep: list[str] = []
    for a in argv:
        m = _URI_RE.match(str(a).strip().strip('"'))
        if m and found is None:
            found = m.group(1)
            continue                       # drop this arg
        keep.append(a)
    if found is not None:
        argv[:] = keep
    return found


def register_scheme() -> None:
    """Register hebrewhub:// under HKCU\\Software\\Classes so a browser can
    launch us. Idempotent + self-healing (rewrites the current exe path each
    launch). No-op off Windows / on any failure."""
    if sys.platform != "win32":
        return
    try:
        import winreg
        # The command Windows runs. Frozen → the exe; source → python + script.
        if getattr(sys, "frozen", False):
            cmd = f'"{sys.executable}" "%1"'
        else:
            script = str(Path(sys.argv[0]).resolve())
            cmd = f'"{sys.executable}" "{script}" "%1"'
        base = rf"Software\Classes\{SCHEME}"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base) as k:
            winreg.SetValueEx(k, None, 0, winreg.REG_SZ, "URL:Hebrew Translation Hub")
            winreg.SetValueEx(k, "URL Protocol", 0, winreg.REG_SZ, "")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + r"\shell\open\command") as k:
            winreg.SetValueEx(k, None, 0, winreg.REG_SZ, cmd)
        log.info("deeplink: registered %s:// → %s", SCHEME, cmd)
    except Exception:
        log.exception("deeplink: scheme registration failed")


def write_pending(game_id: str) -> None:
    """Second-instance side - stash the target id for the running instance."""
    try:
        _PENDING.write_text(str(game_id), encoding="utf-8")
    except Exception:
        log.exception("deeplink: write_pending failed")


# A handoff is consumed within milliseconds. Anything older is debris from a
# handoff whose signal never landed (the owner was busy/dying) - consuming it
# would make a LATER, unrelated launch jump to a stale game card out of nowhere.
_PENDING_MAX_AGE_S = 60.0


def read_pending() -> str | None:
    """Owner side - consume the stashed id (read + delete). None if absent or
    STALE. Always deletes the file, so debris can never accumulate."""
    try:
        if not _PENDING.exists():
            return None
        try:
            age = time.time() - _PENDING.stat().st_mtime
        except OSError:
            age = 0.0
        gid = _PENDING.read_text(encoding="utf-8").strip()
        try:
            _PENDING.unlink()
        except Exception:
            pass
        if age > _PENDING_MAX_AGE_S:
            log.info("deeplink: ignoring stale pending id (%.0fs old)", age)
            return None
        return gid or None
    except Exception:
        return None
