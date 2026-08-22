"""
virtualdj_mod.py - local lifecycle for the VirtualDJ 2026 Hebrew
translation (Atomix DJ software).

The translation is a SINGLE loose file - `Languages\\Arabic.xml` under the
user's VirtualDJ data folder (`%LOCALAPPDATA%\\VirtualDJ\\Languages\\`).
Dropping it there overrides the Arabic language embedded in the exe; the
user then picks Options → Language = Arabic and gets full Hebrew (the app
RTL-renders the Arabic locale, and Hebrew inherits it).

Cloud, NOT bundled: the launcher downloads the `Arabic.xml` payload from
the Cloudflare Worker (slug `virtualdj-hebrew` → GitHub release) via
`mod_source`; only the tiny catalog metadata is bundled
(`software_catalog.py`). This module owns the local cache + the
enable/disable toggle, mirroring `steam_mod.py`.

Backup scheme - the `.orig` rule (same as steam_mod):
    Languages\\Arabic.xml.orig - the user's genuine file (if any),
    captured the FIRST time we overwrite it, restored on disable. If the
    user had no Arabic.xml (the common case - Languages\\ ships empty),
    disable() simply deletes ours.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path
from typing import Callable

# cb(phase, pct, detail) - here phase is always "apply".
ProgressCB = Callable[[str, float, str], None]

CACHE_DIR  = Path.home() / ".translation_manager" / "mod_cache" / "virtualdj"
STATE_FILE = CACHE_DIR / "state.json"
CACHE_XML  = CACHE_DIR / "Arabic.xml"

# The one file we install, relative to the VirtualDJ data root.
_REL = Path("Languages") / "Arabic.xml"


# ── VirtualDJ data folder ─────────────────────────────────────
def data_dir() -> Path:
    """`%LOCALAPPDATA%\\VirtualDJ` (fallback ~/AppData/Local/VirtualDJ)."""
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "VirtualDJ"


def _target() -> Path:
    return data_dir() / _REL


# ── state ─────────────────────────────────────────────────────
def read_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_state(state: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STATE_FILE)


def is_cached() -> bool:
    return STATE_FILE.exists() and CACHE_XML.exists()


def status() -> dict:
    """{cached, enabled, version} for the frontend card CTA."""
    st = read_state()
    enabled = bool(st.get("enabled", False))
    # Reconcile against reality: if our file is gone the toggle is off.
    if enabled and not _target().exists():
        enabled = False
    return {
        "cached":  is_cached(),
        "enabled": enabled,
        "version": st.get("version"),
    }


# ── cache population (from a cloud download) ──────────────────
def populate_cache(src: Path, version: str) -> dict:
    """Copy the freshly-extracted `Arabic.xml` into the cache. `src` is the
    extracted download folder (mod_source.fetch_and_extract output); we
    accept either `src/Arabic.xml` or the first `Arabic.xml` found under it."""
    xml = src / "Arabic.xml"
    if not xml.is_file():
        found = next(iter(src.rglob("Arabic.xml")), None)
        xml = found if found else xml
    if not xml.is_file():
        return {"ok": False, "error": "לא נמצא Arabic.xml בחבילה שהורדה"}

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(xml, CACHE_XML)
    _write_state({
        "version":   version,
        "cached_at": int(time.time()),
        "enabled":   False,
    })
    return {"ok": True, "count": 1}


# ── toggle ────────────────────────────────────────────────────
def enable(cb: ProgressCB | None = None) -> dict:
    if not is_cached():
        return {"ok": False, "error": "אין מטמון מקומי - יש להתקין קודם"}
    if cb:
        cb("apply", 10.0, "מתקין")
    target = _target()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        # Capture the user's genuine file ONCE.
        orig = target.with_suffix(".xml.orig")
        if target.exists() and not orig.exists():
            shutil.copy2(target, orig)
        shutil.copy2(CACHE_XML, target)
    except OSError as e:
        return {"ok": False, "error": f"כשל בכתיבת קובץ השפה: {e}"}

    st = read_state(); st["enabled"] = True; _write_state(st)
    if cb:
        cb("apply", 100.0, "הושלם")
    return {"ok": True, "count": 1}


def disable(cb: ProgressCB | None = None) -> dict:
    target = _target()
    orig = target.with_suffix(".xml.orig")
    try:
        if orig.exists():
            shutil.copy2(orig, target)      # restore the user's original
            orig.unlink(missing_ok=True)
        elif target.exists():
            target.unlink()                 # the file was purely ours
    except OSError as e:
        return {"ok": False, "error": f"כשל בשחזור: {e}"}

    st = read_state(); st["enabled"] = False; _write_state(st)
    return {"ok": True}


def clear_cache() -> dict:
    """Revert VirtualDJ, then wipe the local cache (leaves the machine pristine)."""
    disable()
    shutil.rmtree(CACHE_DIR, ignore_errors=True)
    return {"ok": True}
