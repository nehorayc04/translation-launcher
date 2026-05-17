"""
Chunk-based file downloader with live progress reporting.

Two worker flavors:
  • `_real_download_worker`   — uses requests.get(stream=True), chunk-by-chunk,
                                computes percent + MB/s in real time.
  • `_simulated_worker`       — fake bytes-per-second loop for offline testing
                                (test items don't hit the network).

The active worker emits progress via a module-level callback that main_eel
wires to `eel.update_download_progress(item_id, pct, speed_text)()`.

Threading: each download runs in a daemon thread; cancellation goes through
a per-job `threading.Event`. The progress callback is fired from the worker
thread — main_eel marshals it back to Eel's RPC layer, which is safe to
call from any thread.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable, Optional

import requests


# ─────────────────────────────────────────────────────────────
# Public progress callback (set by main_eel at boot)
# Signature: callback(item_id: str, pct: float, speed_text: str, state: str)
#   state ∈ {"running", "done", "cancelled", "error"}
# ─────────────────────────────────────────────────────────────
ProgressCB = Callable[[str, float, str, str], None]
_progress_cb: Optional[ProgressCB] = None


def set_progress_callback(cb: ProgressCB) -> None:
    global _progress_cb
    _progress_cb = cb


def _emit(item_id: str, pct: float, speed_text: str, state: str) -> None:
    if _progress_cb is not None:
        try:
            _progress_cb(item_id, pct, speed_text, state)
        except Exception:
            pass  # never let UI errors crash the worker


# Note: the catalog of available updates lives in `main_eel._load_updates()`
# (remote-first / local-fallback, same pattern as catalog + news). This module
# is now purely the execution engine — callers pass the item dict in directly.


# ─────────────────────────────────────────────────────────────
# Job book-keeping
# ─────────────────────────────────────────────────────────────
_jobs: dict[str, dict] = {}   # item_id → {"thread": Thread, "cancel": Event, "state": str}


def _new_job(item_id: str) -> tuple[threading.Event, dict]:
    cancel = threading.Event()
    rec    = {"thread": None, "cancel": cancel, "state": "running"}
    _jobs[item_id] = rec
    return cancel, rec


def is_running(item_id: str) -> bool:
    rec = _jobs.get(item_id)
    return rec is not None and rec["state"] == "running"


def cancel(item_id: str) -> dict:
    rec = _jobs.get(item_id)
    if rec is None:
        return {"ok": False, "error": "no such job"}
    rec["cancel"].set()
    rec["state"] = "cancelled"
    _emit(item_id, 0, "בוטל", "cancelled")
    return {"ok": True}


# ─────────────────────────────────────────────────────────────
# Workers
# ─────────────────────────────────────────────────────────────
def _human_speed(bps: float) -> str:
    """Pretty-print bytes-per-second."""
    mbs = bps / (1024 * 1024)
    if mbs >= 1.0:
        return f"{mbs:.1f} MB/s"
    kbs = bps / 1024
    return f"{kbs:.0f} KB/s"


def _simulated_worker(item: dict, cancel: threading.Event, rec: dict) -> None:
    """Fake bytes-per-second simulation. Variable speed for realism."""
    total_mb = float(item.get("size_mb", 25.0))
    item_id  = item["id"]

    downloaded = 0.0
    tick       = 0.12       # 120 ms per tick
    # Start slow, accelerate, then plateau — feels organic
    elapsed = 0.0
    while downloaded < total_mb and not cancel.is_set():
        # Speed curve: 0.5 → 4.5 MB/s ramp, then jitter
        progress_frac = downloaded / total_mb
        if progress_frac < 0.15:
            speed_mbs = 0.5 + progress_frac * 20    # 0.5 → 3.5
        elif progress_frac > 0.85:
            speed_mbs = 3.0 + (1 - progress_frac) * 3  # taper at end
        else:
            speed_mbs = 4.0 + (hash(int(elapsed * 10)) % 100) / 100  # 4.0–5.0 with jitter
        downloaded = min(total_mb, downloaded + speed_mbs * tick)
        pct        = (downloaded / total_mb) * 100
        speed_text = _human_speed(speed_mbs * 1024 * 1024)
        _emit(item_id, pct, speed_text, "running")
        time.sleep(tick)
        elapsed += tick

    if cancel.is_set():
        rec["state"] = "cancelled"
        return
    rec["state"] = "done"
    _emit(item_id, 100.0, "הושלם", "done")


def _real_download_worker(item: dict, cancel: threading.Event, rec: dict) -> None:
    """Real chunked download via requests.get(stream=True)."""
    item_id = item["id"]
    url     = item["url"]
    out_dir = Path.home() / ".translation_manager" / "downloads"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{item_id}.bin"

    try:
        r = requests.get(url, stream=True, timeout=10)
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))

        downloaded = 0
        last_emit  = time.monotonic()
        last_bytes = 0
        chunk      = 64 * 1024

        with out_file.open("wb") as f:
            for piece in r.iter_content(chunk_size=chunk):
                if cancel.is_set():
                    rec["state"] = "cancelled"
                    return
                if not piece:
                    continue
                f.write(piece)
                downloaded += len(piece)

                now = time.monotonic()
                if now - last_emit >= 0.15:
                    elapsed = now - last_emit
                    bps     = (downloaded - last_bytes) / elapsed
                    pct     = (downloaded / total * 100) if total else 0.0
                    _emit(item_id, pct, _human_speed(bps), "running")
                    last_emit  = now
                    last_bytes = downloaded

        rec["state"] = "done"
        _emit(item_id, 100.0, "הושלם", "done")
    except requests.RequestException as e:
        rec["state"] = "error"
        _emit(item_id, 0.0, f"שגיאה: {e}", "error")


def start(item: dict) -> dict:
    """Kick off a download in a daemon thread. Returns immediately.
    The caller (main_eel.start_download) resolves the item from the dynamic
    updates catalog before passing it in here."""
    item_id = item.get("id")
    if not item_id:
        return {"ok": False, "error": "item missing id"}
    if is_running(item_id):
        return {"ok": False, "error": "already running"}

    cancel_evt, rec = _new_job(item_id)
    target = _simulated_worker if item.get("simulated") else _real_download_worker
    t = threading.Thread(target=target, args=(item, cancel_evt, rec), daemon=True)
    rec["thread"] = t
    t.start()
    return {"ok": True}
