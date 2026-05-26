"""Generic monitor primitives — adapter-driven."""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import requests

log = logging.getLogger(__name__)

# Stages match api/admin/progress.ts PHASE_VALUES.
Stage = str  # 'extraction' | 'translation' | 'packaging' | 'qa' | 'deployment' | 'idle' | custom


@dataclass
class StageInfo:
    """One row in the multi-section TUI. Adapters that emit this enable
    the legacy multi-stage dashboard layout; adapters that don't get the
    simpler single-phase view."""
    key:           str                              # 'extraction' / 'translation' / ...
    title_he:      str                              # section header text, e.g. 'שלב 1 — חילוץ וסידור כתוביות'
    status:        str = 'pending'                  # 'done' | 'active' | 'pending'
    processed:     int = 0
    total:         int = 0
    unit:          str = ''
    rate_per_hour: int = 0
    detail_lines:  list[str] = field(default_factory=list)   # pre-formatted extra rows under the bar


# ── env loading ────────────────────────────────────────────────────────
# Mirrors monitor_push.py: walks up from this file looking for a project
# .env so the script works whether run via `cp2077_monitor.bat`, scheduled
# task, or `python -m progress_monitor`. Real OS env vars always win.
def _load_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    try:
        for raw in path.read_text(encoding='utf-8', errors='replace').splitlines():
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, _, v = line.partition('=')
            v = v.strip()
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                v = v[1:-1]
            out[k.strip()] = v
    except OSError:
        pass
    return out


def _env_or_file(name: str, default: str = '') -> str:
    val = os.environ.get(name)
    if val:
        return val
    here = Path(__file__).resolve().parent
    for candidate in (here, here.parent, here.parent.parent):
        kv = _load_env_file(candidate / '.env')
        if name in kv and kv[name]:
            return kv[name]
    return default


@dataclass
class Snapshot:
    game_id:        str
    phase:          Stage = 'translation'
    phase_label_he: str | None = None
    processed:      int = 0
    total:          int = 0
    rate_per_hour:  int = 0
    unit:           str = 'שורות'
    gpu_model:      str = ''
    ai_model:       str = ''
    meta:           dict[str, Any] = field(default_factory=dict)
    # Local-only multi-stage view for the TUI. NOT sent to the API.
    # Adapters that don't supply this fall back to the simple single-phase
    # dashboard.
    stages:           list[StageInfo] = field(default_factory=list)
    summary_eta_sec:  int | None = None
    activity_tail:    list[str] = field(default_factory=list)
    headline_he:      str = ''                  # legacy-style headline, e.g. 'תרגום סייברפאנק 2077 לעברית'


@dataclass
class Monitor:
    """Wraps a project-specific adapter callback into a poll-and-push loop.

    adapter()  -> Snapshot | None    Called every `interval_s` seconds.
                                     Return None to skip this tick.
    """
    game_id:    str
    adapter:    Callable[[], Snapshot | None]
    api_base:   str = field(default_factory=lambda: _env_or_file(
                    'PROGRESS_API_URL',
                    'https://hebrew-translation-hub.com'))
    api_token:  str = field(default_factory=lambda: _env_or_file('MONITOR_TOKEN', ''))
    interval_s: float = 900.0     # 15 min — network push cadence
    refresh_s:  float = 1.5       # local TUI repaint cadence

    # Pop-out push status — surfaced in the TUI footer. Not used by the
    # plain-logs path.
    _last_push_ok:  bool | None = field(default=None, init=False, repr=False)
    _last_push_msg: str         = field(default='',  init=False, repr=False)

    def push(self, snap: Snapshot) -> bool:
        if not self.api_token:
            self._last_push_ok = False
            self._last_push_msg = 'MONITOR_TOKEN missing'
            log.error("MONITOR_TOKEN missing; cannot push")
            return False
        body = {
            'gameId':       snap.game_id,
            'phase':        snap.phase,
            'phaseLabelHe': snap.phase_label_he,
            'processed':    snap.processed,
            'total':        snap.total,
            'ratePerHour':  snap.rate_per_hour,
            'unit':         snap.unit,
            'gpuModel':     snap.gpu_model,
            'aiModel':      snap.ai_model,
            'meta':         snap.meta or None,
        }
        try:
            r = requests.post(
                f"{self.api_base}/api/admin/progress",
                json=body,
                headers={'Authorization': f'Bearer {self.api_token}'},
                timeout=20,
            )
        except requests.RequestException as e:
            self._last_push_ok = False
            self._last_push_msg = f'network error: {e}'
            log.warning("push failed: %s", e)
            return False
        if r.status_code == 409 and 'source-locked-manual' in r.text:
            self._last_push_ok = True
            self._last_push_msg = 'row locked to manual'
            log.info("row is locked to manual; skipping")
            return True               # benign — caller doesn't need to retry
        if not r.ok:
            self._last_push_ok = False
            self._last_push_msg = f'HTTP {r.status_code}'
            log.warning("push HTTP %s: %s", r.status_code, r.text[:200])
            return False
        self._last_push_ok = True
        self._last_push_msg = ''
        return True

    def run(self, *, once: bool = False, dry_run: bool = False, tui: bool = False) -> int:
        """Returns the number of successful pushes (useful for tests).

        tui=True activates the live ANSI dashboard (fast repaint, network
        push still throttled to interval_s). tui implies non-once: a single
        render frame on exit isn't useful, so once=True falls through to the
        plain-logs path even when tui=True.
        """
        if tui and not once:
            return self._run_tui(dry_run=dry_run)

        if not once:
            log.info("monitor started for game_id=%s · pushing every %.0fs to %s",
                     self.game_id, self.interval_s, self.api_base)
        sent = 0
        while True:
            try:
                snap = self.adapter()
            except Exception as e:                      # noqa: BLE001
                log.exception("adapter raised: %s", e)
                snap = None
            if snap is None:
                log.info("no data this tick — adapter returned None")
            else:
                summary = (f"phase={snap.phase} processed={snap.processed} "
                           f"total={snap.total} rate={snap.rate_per_hour}/h")
                if dry_run:
                    log.info("[dry-run] would push: %s", summary)
                    sent += 1
                elif self.push(snap):
                    log.info("pushed snapshot: %s", summary)
                    sent += 1
            if once:
                return sent
            log.info("sleeping %.0fs until next push (Ctrl+C to stop)", self.interval_s)
            time.sleep(self.interval_s)

    def _run_tui(self, *, dry_run: bool = False) -> int:
        """Live ANSI dashboard. Repaints every refresh_s, pushes every
        interval_s. Silences package logging so warnings don't scribble
        over the screen — push errors surface via _last_push_msg in the
        TUI footer instead."""
        from . import tui as _tui

        _tui.enable_windows_ansi()
        logging.getLogger('progress_monitor').setLevel(logging.CRITICAL)

        started = time.time()
        last_push: float | None = None
        sent = 0
        try:
            while True:
                snap = None
                try:
                    snap = self.adapter()
                except Exception as e:                  # noqa: BLE001
                    self._last_push_ok = False
                    self._last_push_msg = f'adapter raised: {e}'
                now = time.time()
                push_due = last_push is None or (now - last_push) >= self.interval_s
                if push_due and snap is not None:
                    if dry_run:
                        self._last_push_ok = True
                        self._last_push_msg = 'dry-run'
                        sent += 1
                        last_push = now
                    elif self.push(snap):
                        sent += 1
                        last_push = now
                _tui.clear_screen()
                next_at = (last_push + self.interval_s) if last_push else (now + self.interval_s)
                if snap is not None and snap.stages:
                    # Adapter emitted a per-stage breakdown → legacy multi-section layout.
                    _tui.render_multi_stage(
                        snap,
                        started_at=started,
                        last_push_at=last_push,
                        last_push_ok=self._last_push_ok,
                        last_push_msg=self._last_push_msg,
                        next_push_at=next_at,
                        push_count=sent,
                        push_interval_s=self.interval_s,
                        refresh_s=self.refresh_s,
                        dry_run=dry_run,
                    )
                else:
                    # Single-phase fallback for adapters that don't emit stages.
                    _tui.render(
                        snap,
                        game_id=self.game_id,
                        started_at=started,
                        last_push_at=last_push,
                        last_push_ok=self._last_push_ok,
                        last_push_msg=self._last_push_msg,
                        next_push_at=next_at,
                        push_count=sent,
                        push_interval_s=self.interval_s,
                        refresh_s=self.refresh_s,
                        dry_run=dry_run,
                    )
                time.sleep(self.refresh_s)
        except KeyboardInterrupt:
            print(f"\nMonitor stopped (sent {sent} push{'es' if sent != 1 else ''}).")
            return sent
