"""ANSI live dashboard for the universal progress monitor.

Standalone — no external deps. Works in plain cmd.exe (enables VT100 mode
explicitly) and in any modern terminal. Designed to be repainted on a
fast cadence (~1.5s) while the actual network push runs on a much slower
schedule (15 min) inside core.Monitor._run_tui.
"""
from __future__ import annotations

import sys
import time
from datetime import datetime

from .core import Snapshot


# ── ANSI ─────────────────────────────────────────────────────────────────
class C:
    RESET   = '\033[0m'
    BOLD    = '\033[1m'
    DIM     = '\033[2m'
    GRAY    = '\033[90m'
    RED     = '\033[91m'
    GREEN   = '\033[92m'
    YELLOW  = '\033[93m'
    BLUE    = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN    = '\033[96m'
    WHITE   = '\033[97m'


WIDTH = 78

PHASE_LABELS_HE: dict[str, str] = {
    'extraction':  'שליפת נתונים',
    'translation': 'תרגום נתונים',
    'packaging':   'אריזת נתונים',
    'qa':          'בקרת איכות',
    'deployment':  'פריסה',
    'idle':        'הושלם',
}

PHASE_COLORS: dict[str, str] = {
    'extraction':  C.BLUE,
    'translation': C.YELLOW,
    'packaging':   C.MAGENTA,
    'qa':          C.CYAN,
    'deployment':  C.CYAN,
    'idle':        C.GREEN,
}


def enable_windows_ansi() -> None:
    """Activate VT100 escape handling AND force stdout to UTF-8 on Windows.

    cmd.exe defaults to a Hebrew (cp1255) / OEM code page that can't encode
    the box-drawing characters our TUI uses, and to VT100-disabled mode that
    treats ANSI escapes as literal junk. Both need flipping.
    """
    if sys.platform != 'win32':
        return
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        # GetStdHandle(-11) = STD_OUTPUT_HANDLE; mode 7 enables processing of
        # ANSI escape sequences (the cmd.exe default is OFF for VT100).
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass


def clear_screen() -> None:
    # ANSI clear + home cursor — avoids spawning a subshell for `cls`.
    sys.stdout.write('\033[2J\033[H')


def _fmt_duration(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return '—'
    s = int(seconds)
    if s == 0:
        return '0s'
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m {sec:02d}s"
    if m:
        return f"{m}m {sec:02d}s"
    return f"{sec}s"


def _bar(done: int, total: int, width: int = 60, color: str = C.GREEN) -> tuple[str, float]:
    pct = (done / total * 100) if total else 0.0
    safe_total = max(total or 1, 1)
    filled = min(width, max(0, int(width * done / safe_total)))
    return f"{color}{'█' * filled}{C.GRAY}{'░' * (width - filled)}{C.RESET}", pct


def render(
    snap: Snapshot | None,
    *,
    game_id: str,
    started_at: float,
    last_push_at: float | None,
    last_push_ok: bool | None,
    last_push_msg: str,
    next_push_at: float,
    push_count: int,
    push_interval_s: float,
    refresh_s: float,
    dry_run: bool = False,
) -> None:
    now = time.time()

    phase    = snap.phase if snap else '—'
    label_he = (snap.phase_label_he if (snap and snap.phase_label_he) else PHASE_LABELS_HE.get(phase, ''))
    color    = PHASE_COLORS.get(phase, C.WHITE)

    processed = snap.processed if snap else 0
    total     = snap.total     if snap else 0
    remaining = max(0, total - processed)
    rate      = snap.rate_per_hour if snap else 0
    unit      = snap.unit if snap else ''

    eta_sec: float | None
    if snap and not remaining and total:
        eta_sec = 0
    elif rate and remaining:
        eta_sec = remaining * 3600 / rate
    else:
        eta_sec = None
    bar, pct = _bar(processed, total, width=60, color=color)

    # ── header ──
    print(f"{C.CYAN}{'═' * WIDTH}{C.RESET}")
    print(f"  {C.BOLD}{C.WHITE}Universal progress monitor — {game_id}{C.RESET}")
    print(
        f"  {datetime.now():%Y-%m-%d %H:%M:%S}    "
        f"uptime: {C.CYAN}{_fmt_duration(now - started_at)}{C.RESET}    "
        f"refresh: {C.GRAY}~{refresh_s:.1f}s{C.RESET}"
    )
    print(f"{C.CYAN}{'═' * WIDTH}{C.RESET}")

    # ── phase ──
    phase_str = f"[PHASE: {phase.upper()}]"
    if label_he:
        phase_str += f"  ·  {label_he}"
    print(f"  {C.BOLD}{color}{phase_str}{C.RESET}")
    if snap and (snap.gpu_model or snap.ai_model):
        meta = ' · '.join(s for s in [snap.gpu_model, snap.ai_model] if s)
        print(f"  {C.DIM}{meta}{C.RESET}")
    print()

    # ── progress bar ──
    print(f"  Progress  {bar}  {C.BOLD}{C.WHITE}{pct:5.1f}%{C.RESET}")
    print()

    # ── numbers ──
    if snap is None:
        print(f"  {C.DIM}waiting for first adapter read...{C.RESET}")
    else:
        print(f"  {C.WHITE}{processed:>12,}{C.RESET} / {total:>12,}  {C.DIM}{unit}{C.RESET}")
        print(
            f"  {C.GRAY}remaining:{C.RESET} {remaining:>10,}     "
            f"{C.GRAY}rate:{C.RESET} {rate:>6,}/h     "
            f"{C.GRAY}ETA:{C.RESET} {_fmt_duration(eta_sec)}"
        )
    print()

    # ── push status ──
    print(f"{C.GRAY}{'─' * WIDTH}{C.RESET}")
    if last_push_at is None:
        last_str = f"{C.DIM}never (first push pending){C.RESET}"
    else:
        ago = int(now - last_push_at)
        tick = f"{C.GREEN}✓{C.RESET}" if last_push_ok else f"{C.RED}✗{C.RESET}"
        suffix = f" {C.DIM}({last_push_msg}){C.RESET}" if last_push_msg else ''
        last_str = f"{tick} {ago}s ago{suffix}"
    next_in = max(0, int(next_push_at - now))
    mode = f"{C.YELLOW}[DRY-RUN] {C.RESET}" if dry_run else ''
    print(
        f"  {mode}pushes: {C.GREEN}{push_count}{C.RESET}    "
        f"last: {last_str}    "
        f"next in: {C.CYAN}{_fmt_duration(next_in)}{C.RESET}"
    )
    print(f"  {C.DIM}Ctrl+C to stop · interval: {int(push_interval_s)}s{C.RESET}")
    print(f"{C.GRAY}{'─' * WIDTH}{C.RESET}")
    sys.stdout.flush()
