"""ANSI live dashboard for the universal progress monitor.

Standalone — no external deps. Works in plain cmd.exe (enables VT100 mode
explicitly) and in any modern terminal. Designed to be repainted on a
fast cadence (~1.5s) while the actual network push runs on a much slower
schedule (15 min) inside core.Monitor._run_tui.

Bidi behaviour: legacy cmd.exe doesn't run the Unicode bidi algorithm, so
Hebrew strings render in logical (storage) order — i.e. backwards. We
detect that case and reverse Hebrew segments ourselves before printing.
Windows Terminal / ConEmu / non-Windows pass through unchanged.
"""
from __future__ import annotations

import os
import re
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


# ── bidi (lifted from legacy cp2077_monitor.py) ──────────────────────────
# Empirically, every Windows console host we've tested — legacy cmd.exe,
# standalone PowerShell, Windows Terminal (WT_SESSION), VS Code's
# integrated terminal (TERM_PROGRAM=vscode), and ConEmu (ConEmuPID) —
# renders Hebrew left-to-right in logical (storage) order instead of
# running the Unicode bidi algorithm. So on Windows we ALWAYS reverse by
# default; the user opts out only if their terminal genuinely bidi's
# (which today means almost no Windows console host).
#
#   MONITOR_BIDI_REVERSE=1/on   force reversal on   (explicit)
#   MONITOR_BIDI_REVERSE=0/off  force reversal off  (terminal does bidi
#                                                    correctly — rare)
#   unset                       default — reverse on Windows, do nothing
#                               elsewhere.
_BIDI_FORCE = os.environ.get('MONITOR_BIDI_REVERSE', '').strip().lower()
_LEGACY_CONSOLE = (
    _BIDI_FORCE in ('1', 'true', 'on', 'yes')
    or (
        _BIDI_FORCE not in ('0', 'false', 'off', 'no')
        and os.name == 'nt'
    )
)

_BRACKET_MIRROR = str.maketrans({
    '(': ')', ')': '(', '[': ']', ']': '[',
    '{': '}', '}': '{', '<': '>', '>': '<',
    '«': '»', '»': '«', '‹': '›', '›': '‹',
    '⟨': '⟩', '⟩': '⟨', '“': '”', '”': '“', '‘': '’', '’': '‘',
})

_HEB_RANGE = '֐-׿'
_HEB_INNER_PUNCT = r'  \.,!?:;\-–—\(\)\[\]"'
_HEB_TRAIL_PUNCT = r'[\.,!?:;]*'
_HEB_SEGMENT_RE = re.compile(
    rf'[{_HEB_RANGE}](?:[{_HEB_RANGE}{_HEB_INNER_PUNCT}]*[{_HEB_RANGE}])?{_HEB_TRAIL_PUNCT}'
)


def fix_rtl(text: str) -> str:
    """Reverse Hebrew segments in text so legacy cmd.exe renders them L-to-R
    in the correct visual order. ANSI escape sequences pass through unchanged
    because they contain no Hebrew characters."""
    if not text or not _LEGACY_CONSOLE:
        return text
    return _HEB_SEGMENT_RE.sub(lambda m: m.group(0)[::-1].translate(_BRACKET_MIRROR), text)


def H(s: str) -> str:
    """Reverse a pure-Hebrew label. Use for self-contained Hebrew strings
    (e.g. section titles). For mixed content use fix_rtl()."""
    if not s or not _LEGACY_CONSOLE:
        return s
    return s[::-1].translate(_BRACKET_MIRROR)


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
    """Robust clear: wipe viewport, wipe scrollback, home cursor, flush.

    `\\033[2J` alone clears the viewport but leaves scrollback intact on
    some Windows terminals, so consecutive frames stack underneath each
    other when the render is taller than the window. Adding `\\033[3J`
    discards the scrollback, and the explicit flush makes sure the clear
    lands BEFORE the next render's bytes hit the terminal buffer.
    """
    sys.stdout.write('\033[2J\033[3J\033[H')
    sys.stdout.flush()


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


def _bar(done: int, total: int, width: int = 50, color: str = C.GREEN) -> tuple[str, float]:
    """Legacy-style horizontal bar: solid blocks for done, dotted for remainder."""
    pct = (done / total * 100) if total else 0.0
    safe_total = max(total or 1, 1)
    filled = min(width, max(0, int(width * done / safe_total)))
    return f"{color}{'█' * filled}{C.GRAY}{'░' * (width - filled)}{C.RESET}", pct


def _section(title: str, color: str = '') -> None:
    """Legacy-style section divider: gray ── + colored title + gray ──."""
    print(C.GRAY + ('─' * WIDTH) + C.RESET)
    print(f"  {color}{title}{C.RESET}")
    print(C.GRAY + ('─' * WIDTH) + C.RESET)


def _status_marker(status: str) -> tuple[str, str]:
    """Legacy mapping: done=✓ green, active=⏵ yellow, pending=· gray."""
    if status == 'done':
        return ('✓', C.GREEN)
    if status == 'active':
        return ('⏵', C.YELLOW)
    return ('·', C.GRAY)


# ── multi-stage layout (faithful port of legacy cp2077_monitor.render) ───
def render_multi_stage(
    snap: Snapshot,
    *,
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
    now_dt = datetime.now()
    uptime = _fmt_duration(now - started_at)

    # Apply fix_rtl to every emitted line so Hebrew runs come out in the
    # correct visual order on legacy cmd.exe. ANSI codes are pass-through.
    def _p(s: str = '') -> None:
        print(fix_rtl(s))

    # ─── HEADER ───
    headline = snap.headline_he or f'Universal progress monitor — {snap.game_id}'
    _p(C.CYAN + ('═' * WIDTH) + C.RESET)
    _p(f"  {C.BOLD}{C.WHITE}{headline}{C.RESET}")
    _p(
        f"  {now_dt:%Y-%m-%d  %H:%M:%S}    "
        f"זמן ריצה: {C.CYAN}{uptime}{C.RESET}    "
        f"רענון כל {refresh_s:.1f} שניות"
    )
    # LTR English phase tag — unambiguous at a glance, mirrors the legacy.
    phase_up = snap.phase.upper()
    phase_color = {
        'EXTRACTION':  C.BLUE,
        'TRANSLATION': C.YELLOW,
        'PACKAGING':   C.MAGENTA,
        'QA':          C.CYAN,
        'DEPLOYMENT':  C.CYAN,
        'IDLE':        C.GREEN,
    }.get(phase_up, C.WHITE)
    phase_line = f"[PHASE: {phase_up}]  {snap.processed:,} / {snap.total:,} {snap.unit}"
    _p(f"  {C.BOLD}{phase_color}{phase_line}{C.RESET}")
    _p(C.CYAN + ('═' * WIDTH) + C.RESET)

    # ─── OVERALL SUMMARY ───
    _p(f"{C.BLUE}◆ סיכום כללי{C.RESET}")
    _p(C.GRAY + ('─' * WIDTH) + C.RESET)
    if snap.summary_eta_sec is None:
        _p(f"   זמן משוער לסיום:        {C.DIM}(לא ידוע — אין קצב){C.RESET}")
    elif snap.summary_eta_sec == 0:
        _p(f"   זמן משוער לסיום:        {C.GREEN}✓ הסתיים{C.RESET}")
    else:
        _p(
            f"   זמן משוער לסיום:        {C.MAGENTA}{_fmt_duration(snap.summary_eta_sec)}{C.RESET}"
        )
    # Current-stage label
    active_stage = next((s for s in snap.stages if s.status == 'active'), None)
    if active_stage:
        current_label = active_stage.title_he
    else:
        current_label = snap.phase_label_he or snap.phase
    _p(f"   שלב נוכחי:              {C.YELLOW}{current_label}{C.RESET}")
    if snap.gpu_model or snap.ai_model:
        meta = ' · '.join(s for s in [snap.gpu_model, snap.ai_model] if s)
        _p(f"   {C.DIM}{meta}{C.RESET}")
    _p()

    # ─── PER-STAGE SECTIONS ───
    for st in snap.stages:
        icon, color = _status_marker(st.status)
        # Inline _section to route through _p so Hebrew titles get reversed
        # on legacy cmd.exe.
        _p(C.GRAY + ('─' * WIDTH) + C.RESET)
        _p(f"  {color}{icon} {st.title_he}{C.RESET}")
        _p(C.GRAY + ('─' * WIDTH) + C.RESET)
        if st.status != 'pending' or st.processed > 0:
            bar, pct = _bar(st.processed, st.total or 1, width=50, color=color)
            _p(f"   [{bar}] {C.CYAN}{pct:5.1f}%{C.RESET}")
        for line in st.detail_lines:
            _p(f"   {line}")
        _p()

    # ─── ACTIVITY TAIL ───
    if snap.activity_tail:
        _p(C.GRAY + ('─' * WIDTH) + C.RESET)
        _p(f"  {C.CYAN}◇ פעילות אחרונה{C.RESET}")
        _p(C.GRAY + ('─' * WIDTH) + C.RESET)
        for line in snap.activity_tail:
            _p(f"   {C.DIM}{line}{C.RESET}")
        _p()

    # ─── PUSH STATUS FOOTER ───
    _p(C.CYAN + ('═' * WIDTH) + C.RESET)
    if last_push_at is None:
        last_str = f"{C.DIM}never (first push pending){C.RESET}"
    else:
        ago = int(now - last_push_at)
        tick = f"{C.GREEN}✓{C.RESET}" if last_push_ok else f"{C.RED}✗{C.RESET}"
        suffix = f" {C.DIM}({last_push_msg}){C.RESET}" if last_push_msg else ''
        last_str = f"{tick} {ago}s ago{suffix}"
    next_in = max(0, int(next_push_at - now))
    mode = f"{C.YELLOW}[DRY-RUN] {C.RESET}" if dry_run else ''
    _p(
        f"  {mode}pushes: {C.GREEN}{push_count}{C.RESET}    "
        f"last: {last_str}    "
        f"next push in: {C.CYAN}{_fmt_duration(next_in)}{C.RESET}"
    )
    _p(
        f"  {C.DIM}push interval: {int(push_interval_s)}s · Ctrl+C to stop{C.RESET}"
    )
    _p(C.CYAN + ('═' * WIDTH) + C.RESET)
    sys.stdout.flush()


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
