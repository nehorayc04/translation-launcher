"""Cross-validation audit adapter for the universal progress_monitor.

Reads the live state written by `universal/continuous_audit_loop.py` and
exposes it to the website + launcher under the same "בקרת איכות" slot
that the now-dormant `cp2077_qa_watchdog.py` used to fill, so live
linguistic-cross-validation progress shows up wherever the legacy QA
status used to.

State sources (all in universal/, written by the audit itself):
    cross_audit_checkpoint.json   processed / base_done / dlc_done / flagged
    cross_audit_flags.json        appended JSONL of every flag (not parsed here)
    cross_audit_dashboard.md      human-readable rendering (not parsed here)
    audit.lock                    JSON with pid/started_at/host

The adapter polls those JSONs (already atomically written by the audit's
own atomic_write helper, with retry through transient WinError 5), so no
fancy file-watch is needed.

Usage:
    python -m progress_monitor --adapter audit               # tui + 60s pushes
    python -m progress_monitor --adapter audit --once        # one-shot push
    python -m progress_monitor --adapter audit --once --dry-run
"""
from __future__ import annotations

import ctypes
import json
import logging
import os
import time
from pathlib import Path

from ..core import Monitor, Snapshot, StageInfo

log = logging.getLogger(__name__)

GAME_ID  = 'cyberpunk'        # publishes into the cyberpunk row's `qa` slot
GPU      = 'AMD Radeon RX 9070 16GB'
AI_MODEL = 'Qwen2.5 32B'

# Resolve the universal/ folder relative to this file
# (adapters → progress_monitor → universal → repo root → universal again).
_HERE      = Path(__file__).resolve()
UNIVERSAL  = _HERE.parents[2]                     # progress_monitor/.. == universal/
CHECKPOINT = UNIVERSAL / "cross_audit_checkpoint.json"
LOCK_FILE  = UNIVERSAL / "audit.lock"

# Sliding-window rate calculation — items/hour over the last 10 minutes,
# matches the cadence of the audit's batch=10 / ~30 s rhythm.
_HISTORY: list[tuple[float, int]] = []
_HISTORY_WINDOW_SEC = 600.0


def _read_json(p: Path) -> dict:
    """Best-effort read; returns {} on missing/corrupt/stale-tmp races."""
    try:
        if p.exists():
            return json.loads(p.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def _pid_alive(pid: int) -> bool:
    """Cross-platform check that the audit's lock-recorded PID is the
    actual live process. On Windows uses OpenProcess + GetExitCodeProcess
    to dodge ERROR_ACCESS_DENIED for our own elevated handles."""
    try:
        if os.name == 'nt':
            SYNC = 0x00100000
            h = ctypes.windll.kernel32.OpenProcess(SYNC, False, int(pid))
            if not h:
                return False
            try:
                exit_code = ctypes.c_ulong()
                ok = ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(exit_code))
                STILL_ACTIVE = 259
                return bool(ok) and exit_code.value == STILL_ACTIVE
            finally:
                ctypes.windll.kernel32.CloseHandle(h)
        else:
            os.kill(int(pid), 0)
            return True
    except (OSError, ValueError):
        return False


def _audit_alive() -> bool:
    lk = _read_json(LOCK_FILE)
    pid = lk.get('pid')
    return bool(pid) and _pid_alive(int(pid))


def _rate_per_hour(processed_now: int) -> int:
    now = time.time()
    _HISTORY.append((now, processed_now))
    cutoff = now - _HISTORY_WINDOW_SEC
    while _HISTORY and _HISTORY[0][0] < cutoff:
        _HISTORY.pop(0)
    if len(_HISTORY) < 2:
        return 0
    ts_old, p_old = _HISTORY[0]
    delta_p = processed_now - p_old
    delta_t = now - ts_old
    if delta_t <= 0 or delta_p <= 0:
        return 0
    return int(delta_p * 3600 / delta_t)


def _collect() -> Snapshot | None:
    cp = _read_json(CHECKPOINT)
    if not cp:
        log.info("audit adapter: no checkpoint yet (universal/cross_audit_checkpoint.json missing)")
        return None

    processed  = int(cp.get('processed', 0))
    base_total = int(cp.get('base_total', 0))
    dlc_total  = int(cp.get('dlc_total',  0))
    total      = base_total + dlc_total
    flagged    = int(cp.get('flagged', 0))
    base_done  = int(cp.get('base_done', 0))
    dlc_done   = int(cp.get('dlc_done',  0))
    started_at = cp.get('started_at') or ''
    saved_at   = cp.get('saved_at')   or ''
    alive      = _audit_alive()
    rate       = _rate_per_hour(processed) if alive else 0

    flag_rate = (flagged / processed * 100.0) if processed else 0.0
    pct       = (processed / total    * 100.0) if total     else 0.0

    detail = [
        f"בסיס:   {base_done:>7,} / {base_total:>7,}",
        f"DLC:    {dlc_done:>7,} / {dlc_total:>7,}",
        f"flags:  {flagged:>7,}   ({flag_rate:.2f}% מהשורות שנבדקו)",
    ]
    if started_at:
        detail.append(f"החל: {started_at}")
    if saved_at:
        detail.append(f"עודכן: {saved_at}")
    detail.append("● חי, מוערך ע\"י Qwen-32B" if alive else "○ לא רץ — נתונים אחרונים")

    stage = StageInfo(
        key='qa',
        title_he='שלב 4 — ביקורת תרגום צולבת (LQA חי)',
        status='active' if alive else 'pending',
        processed=processed,
        total=total,
        unit='שורות',
        rate_per_hour=rate,
        detail_lines=detail,
    )

    return Snapshot(
        game_id        = GAME_ID,
        phase          = 'qa',
        phase_label_he = 'ביקורת תרגום צולבת',
        processed      = processed,
        total          = total,
        rate_per_hour  = rate,
        unit           = 'שורות',
        gpu_model      = GPU,
        ai_model       = AI_MODEL,
        meta           = {
            'flagged':     flagged,
            'flagRatePct': round(flag_rate, 2),
            'baseDone':    base_done,
            'baseTotal':   base_total,
            'dlcDone':     dlc_done,
            'dlcTotal':    dlc_total,
            'pctComplete': round(pct, 2),
            'startedAt':   started_at,
            'savedAt':     saved_at,
            'alive':       alive,
        },
        stages         = [stage],
        headline_he    = 'ביקורת תרגום צולבת — Cyberpunk 2077',
    )


# ── factory ───────────────────────────────────────────────────────────────────

def build() -> Monitor:
    """Polls + pushes every 60 s — the audit moves ~10 rows per ~30 s
    so a one-minute cadence keeps the live numbers fresh on the
    website and launcher without flooding the upsert endpoint."""
    return Monitor(game_id=GAME_ID, adapter=_collect, interval_s=60.0)
