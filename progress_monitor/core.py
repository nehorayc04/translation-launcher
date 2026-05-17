"""Generic monitor primitives — adapter-driven."""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import requests

log = logging.getLogger(__name__)

# Stages match api/admin/progress.ts PHASE_VALUES.
Stage = str  # 'extraction' | 'translation' | 'packaging' | 'qa' | 'deployment' | 'idle' | custom


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


@dataclass
class Monitor:
    """Wraps a project-specific adapter callback into a poll-and-push loop.

    adapter()  -> Snapshot | None    Called every `interval_s` seconds.
                                     Return None to skip this tick.
    """
    game_id:    str
    adapter:    Callable[[], Snapshot | None]
    api_base:   str = field(default_factory=lambda: os.environ.get(
                    'PROGRESS_API_BASE', 'https://hebrew-translation-hub.vercel.app'))
    api_token:  str = field(default_factory=lambda: os.environ.get('MONITOR_TOKEN', ''))
    interval_s: float = 900.0     # 15 min

    def push(self, snap: Snapshot) -> bool:
        if not self.api_token:
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
            log.warning("push failed: %s", e)
            return False
        if r.status_code == 409 and 'source-locked-manual' in r.text:
            log.info("row is locked to manual; skipping")
            return True               # benign — caller doesn't need to retry
        if not r.ok:
            log.warning("push HTTP %s: %s", r.status_code, r.text[:200])
            return False
        return True

    def run(self, *, once: bool = False, dry_run: bool = False) -> int:
        """Returns the number of successful pushes (useful for tests)."""
        sent = 0
        while True:
            try:
                snap = self.adapter()
            except Exception as e:                      # noqa: BLE001
                log.exception("adapter raised: %s", e)
                snap = None
            if snap is not None:
                if dry_run:
                    log.info("[dry-run] would push %s", snap)
                    sent += 1
                elif self.push(snap):
                    sent += 1
            if once:
                return sent
            time.sleep(self.interval_s)
