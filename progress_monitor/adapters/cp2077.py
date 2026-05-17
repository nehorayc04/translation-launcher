"""Cyberpunk 2077 adapter for the universal progress_monitor package.

Lifts the data-collection logic from cp2077_monitor.py and exposes it as
a build() -> Monitor factory for use with:
    python -m progress_monitor --adapter cp2077 --once --dry-run -v
"""
from __future__ import annotations

import logging
import os
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

from ..core import Monitor, Snapshot, Stage, StageInfo

log = logging.getLogger(__name__)

# ── constants (mirrors cp2077_monitor.py) ────────────────────────────────────
GAME_ID   = 'cyberpunk'
GPU       = 'AMD Radeon RX 9070 16GB'
AI_MODEL  = 'Gemma-2 27B'

PROJ = r"C:\Users\nc528\סקריפטים\תרגום משחקים"

SUBTITLE_DIR_TOTAL  = 3083
REEXTRACT_TOTAL     = 3085
MAX_ITEMS_PER_SEC   = 2.0
_PKG_RATE_WINDOW_SEC = 1800  # 30 min rolling window for packaging rate

PROJ_AR_SUBTITLES = (
    r"C:\Users\nc528\סקריפטים\תרגום משחקים\תרגום_משחקים"
    r"\source\archive\base\localization\ar-ar\subtitles"
)

LOG_MASTER    = os.path.join(PROJ, "master_pipeline_v2.log")
LOG_TRANS     = os.path.join(PROJ, "fix_missing_translations.log")
LOG_BATCH     = os.path.join(PROJ, "subtitle_batch.log")
LOG_REEXTRACT = os.path.join(PROJ, "reextract_subtitles.log")

REEXTRACT_TEXT_DIR  = r"C:\Users\nc528\AppData\Local\Temp\reextract_subs\text"
REEXTRACT_DONE_MARKER = os.path.join(REEXTRACT_TEXT_DIR, ".serialize_done")

MASTER_START    = "MASTER PIPELINE"
BATCH_START     = "cp2077_subtitle_batch starting"
REEXTRACT_START = "cp2077_reextract_subtitles starting"
TRANS_START     = "[*] Using"

# ── regexes (lifted verbatim from cp2077_monitor.py) ─────────────────────────
RE_NEED = re.compile(
    r"\[\*\]\s+(?:Global\s+queue:\s+)?([\d,]+)\s+(?:pending\s+items|fields?\s+need\s+\(re\)translation)"
)
RE_SAVED = re.compile(r"\[~\]\s+Saved\s+—\s+([\d,]+)\s+fixed,\s+~([\d,]+)\s+remaining")
RE_SKIP  = re.compile(r"\[SKIP\]")
RE_BATCH_PROGRESS_NEW = re.compile(
    r"\[[#\-]+\]\s+([\d.]+)%\s+([\d,]+)\s*/\s*([\d,]+)\s+"
    r"rate=([\d.]+)/s\s+ETA\s+([\d.]+)h\s+"
    r"\(processed=(\d+)\s+skipped=(\d+)\s+failed=(\d+)\)"
)
RE_BATCH_PROGRESS = re.compile(
    r"\[(\d+)/(\d+)\][^\|]*\|\s*processed=(\d+)\s+skipped=(\d+)\s+failed=(\d+)"
    r"\s*\|\s*rate=([0-9.]+)/s\s*\|\s*ETA\s+([0-9.]+)h"
)
RE_REEXTRACT_PROGRESS = re.compile(
    r"\[(\d[\d,]*)/(\d[\d,]*)\]\s+done=([\d,]+)\s+failed=([\d,]+)"
    r"\s+rate=([0-9.]+)/s\s+ETA=([0-9.]+)h"
)
RE_PHASE2_DONE  = re.compile(
    r"\[\*\]\s+Phase\s+2\s+done:\s+([\d,]+)\s+TM\s+hits,\s+([\d,]+)\s+fast-track\s+hits"
)
RE_PHASE3_START = re.compile(r"\[\*\]\s+Phase\s+3:")
RE_TRANS_DONE   = re.compile(r"\[\*\]\s+Done\.\s+Fixed\s+([\d,]+)\s+fields?\b")
RE_TRANS_START_TIME = re.compile(
    r"\[started:\s+(?:(\d{4}-\d{2}-\d{2})\s+)?(\d{2}:\d{2}:\d{2})\]"
)
RE_LOG_TIME = re.compile(r"^\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\]")

# ── module-level mutable state for rolling rate windows ──────────────────────
_pkg_snapshots: list[tuple[float, int]] = []

# ANSI fragments used inside detail_lines (the TUI doesn't post-process).
C_DIM   = '\033[2m'
C_RESET = '\033[0m'


# ── helpers (lifted from cp2077_monitor.py) ───────────────────────────────────

def _parse_log_time(line: str) -> datetime | None:
    m = RE_LOG_TIME.match(line)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def _read_lines_safe(path: str, max_lines: int = 20000) -> list[str]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return lines[-max_lines:]
    except Exception:
        return []


def _read_current_run_lines(path: str, start_markers) -> list[str]:
    if not os.path.exists(path):
        return []
    if isinstance(start_markers, str):
        start_markers = [start_markers]
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception:
        return []
    last_start = -1
    for i, line in enumerate(lines):
        if any(marker in line for marker in start_markers):
            last_start = i
    return [] if last_start < 0 else lines[last_start:]


def _get_run_start_time(path: str, start_markers) -> datetime | None:
    lines = _read_current_run_lines(path, start_markers)
    return _parse_log_time(lines[0]) if lines else None


def _count_json_files(directory: str) -> int:
    try:
        count = 0
        for _, _, files in os.walk(directory):
            for f in files:
                if f.endswith(".json"):
                    count += 1
        return count
    except Exception:
        return 0


def _count_subtitle_cr2w() -> int:
    return _count_json_files(PROJ_AR_SUBTITLES)


def _packaging_rate_per_hour(current_count: int) -> int:
    now = time.time()
    _pkg_snapshots.append((now, current_count))
    cutoff = now - _PKG_RATE_WINDOW_SEC
    while len(_pkg_snapshots) > 2 and _pkg_snapshots[0][0] < cutoff:
        _pkg_snapshots.pop(0)
    if len(_pkg_snapshots) < 2:
        return 0
    dt = _pkg_snapshots[-1][0] - _pkg_snapshots[0][0]
    dc = _pkg_snapshots[-1][1] - _pkg_snapshots[0][1]
    if dt < 30 or dc <= 0:
        return 0
    return int((dc / dt) * 3600)


def _trans_step_done() -> bool:
    lines = _read_current_run_lines(LOG_TRANS, TRANS_START)
    if not lines:
        return False
    for line in lines:
        m = RE_TRANS_DONE.search(line)
        if m:
            return int(m.group(1).replace(",", "")) > 0
    return False


def _get_trans_run_start() -> datetime | None:
    lines = _read_current_run_lines(LOG_TRANS, TRANS_START)
    fixed_observed = sum(1 for l in lines if " -> '" in l or " → " in l)
    for line in lines:
        m = RE_TRANS_START_TIME.search(line)
        if not m:
            continue
        m_date, m_time = m.group(1), m.group(2)
        try:
            now_dt = datetime.now()
            if m_date:
                return datetime.strptime(f"{m_date} {m_time}", "%Y-%m-%d %H:%M:%S")
            start_dt = datetime.strptime(f"{now_dt.date()} {m_time}", "%Y-%m-%d %H:%M:%S")
            while start_dt > now_dt:
                start_dt -= timedelta(days=1)
            while fixed_observed > 0:
                elapsed = (now_dt - start_dt).total_seconds()
                if elapsed <= 0 or fixed_observed / elapsed <= MAX_ITEMS_PER_SEC:
                    break
                start_dt -= timedelta(days=1)
            return start_dt
        except Exception:
            return None
    return None


def _detect_active_run() -> tuple[str, datetime | None]:
    master_start    = _get_run_start_time(LOG_MASTER, MASTER_START)
    batch_start     = _get_run_start_time(LOG_BATCH, BATCH_START)
    reextract_start = _get_run_start_time(LOG_REEXTRACT, REEXTRACT_START)
    trans_start     = _get_trans_run_start()

    if reextract_start and not os.path.exists(REEXTRACT_DONE_MARKER):
        if master_start is None or reextract_start >= master_start:
            return ("master", reextract_start)
    if trans_start and not _trans_step_done():
        return ("master", trans_start)
    if master_start and batch_start:
        return (
            ("standalone_batch", batch_start)
            if batch_start > master_start
            else ("master", master_start)
        )
    if master_start:
        return ("master", master_start)
    if batch_start:
        return ("standalone_batch", batch_start)
    return ("idle", None)


def _parse_reextract_state() -> dict:
    state: dict = {
        "complete": False,
        "file_count": 0,
        "done_log": 0,
        "total": REEXTRACT_TOTAL,
        "rate_per_sec": 0.0,
        "started_at": None,
        "phase2_started": False,
    }
    if os.path.exists(REEXTRACT_DONE_MARKER):
        state["complete"] = True
    state["file_count"] = _count_json_files(REEXTRACT_TEXT_DIR)
    lines = _read_lines_safe(LOG_REEXTRACT, max_lines=5000)
    if not lines:
        return state
    last_start = -1
    for i, line in enumerate(lines):
        if REEXTRACT_START in line:
            last_start = i
    if last_start >= 0:
        state["started_at"] = _parse_log_time(lines[last_start])
        lines = lines[last_start:]
    for line in lines:
        if "Phase 2: Serializing" in line:
            state["phase2_started"] = True
        m = RE_REEXTRACT_PROGRESS.search(line)
        if m:
            state["done_log"] = int(m.group(1).replace(",", ""))
            state["total"]    = int(m.group(2).replace(",", ""))
            state["rate_per_sec"] = float(m.group(5))
        if "serialize_done" in line or "Phase 2: serialize already done" in line:
            state["complete"] = True
    return state


def _parse_translation_state() -> dict:
    state: dict = {
        "fields_needed": None,
        "fixed": 0,
        "remaining": None,
        "rate_per_min": 0,
        "step_done_min": None,
        "skipped_step": False,
        "run_start_dt": None,
        "elapsed_sec": None,
        "phase3_seen": False,
        "phase3_baseline_fixed": 0,
    }
    mode, _ = _detect_active_run()
    if mode == "standalone_batch":
        state["skipped_step"] = True
        return state
    lines = _read_current_run_lines(LOG_TRANS, TRANS_START)
    saves = []
    arrow_lines = []
    for line in lines:
        m = RE_NEED.search(line)
        if m:
            state["fields_needed"] = int(m.group(1).replace(",", ""))
        m = RE_SAVED.search(line)
        if m:
            t = _parse_log_time(line)
            saves.append((t, int(m.group(1).replace(",", "")), int(m.group(2).replace(",", ""))))
            arrow_lines = []
        if " -> '" in line or " → " in line:
            arrow_lines.append(line)
        m = RE_PHASE2_DONE.search(line)
        if m:
            state["phase3_baseline_fixed"] = (
                int(m.group(1).replace(",", "")) + int(m.group(2).replace(",", ""))
            )
        if RE_PHASE3_START.search(line):
            state["phase3_seen"] = True
        m = RE_TRANS_START_TIME.search(line)
        if m:
            try:
                m_date, m_time = m.group(1), m.group(2)
                now_dt = datetime.now()
                if m_date:
                    state["run_start_dt"] = datetime.strptime(
                        f"{m_date} {m_time}", "%Y-%m-%d %H:%M:%S"
                    )
                else:
                    start_dt = datetime.strptime(
                        f"{now_dt.date()} {m_time}", "%Y-%m-%d %H:%M:%S"
                    )
                    while start_dt > now_dt:
                        start_dt -= timedelta(days=1)
                    state["run_start_dt"] = start_dt
            except Exception:
                pass
        m = RE_TRANS_DONE.search(line)
        if m:
            t_done  = _parse_log_time(line)
            t_start = _parse_log_time(lines[0]) if lines else None
            if t_done and t_start:
                state["step_done_min"] = (t_done - t_start).total_seconds() / 60.0
            else:
                state["step_done_min"] = 0.0

    if state["run_start_dt"]:
        state["elapsed_sec"] = (datetime.now() - state["run_start_dt"]).total_seconds()

    fixed_so_far = (saves[-1][1] + len(arrow_lines)) if saves else len(arrow_lines)
    if state["run_start_dt"] and state["elapsed_sec"] and fixed_so_far > 0:
        while state["elapsed_sec"] > 0 and (
            fixed_so_far / state["elapsed_sec"] > MAX_ITEMS_PER_SEC
        ):
            state["run_start_dt"] -= timedelta(days=1)
            state["elapsed_sec"] = (datetime.now() - state["run_start_dt"]).total_seconds()

    if saves:
        base_fixed = saves[-1][1]
        extra = len(arrow_lines)
        state["fixed"]     = base_fixed + extra
        state["remaining"] = max(0, saves[-1][2] - extra)
        window = saves[-5:]
        if len(window) >= 2 and window[0][0] and window[-1][0]:
            dt      = (window[-1][0] - window[0][0]).total_seconds()
            d_fixed = window[-1][1] - window[0][1]
            state["rate_per_min"] = (d_fixed / dt * 60) if dt > 0 else 0
        if not state["rate_per_min"] and state["elapsed_sec"] and state["fixed"] > 0:
            state["rate_per_min"] = state["fixed"] / state["elapsed_sec"] * 60
    elif arrow_lines and state["fields_needed"]:
        state["fixed"]     = len(arrow_lines)
        state["remaining"] = max(0, state["fields_needed"] - len(arrow_lines))
        if state["elapsed_sec"] and state["elapsed_sec"] > 0:
            state["rate_per_min"] = len(arrow_lines) / state["elapsed_sec"] * 60

    if (
        state["phase3_seen"]
        and state["run_start_dt"]
        and state["fixed"] > state["phase3_baseline_fixed"]
    ):
        phase3_start   = state["run_start_dt"] + timedelta(seconds=30)
        phase3_elapsed = (datetime.now() - phase3_start).total_seconds()
        if phase3_elapsed > 60:
            phase3_items = state["fixed"] - state["phase3_baseline_fixed"]
            state["rate_per_min"] = phase3_items / phase3_elapsed * 60

    return state


def _detect_phase(trans: dict, reex: dict) -> Stage:
    """Map pipeline state to a Stage string matching the monitor API."""
    started  = bool(reex.get("started_at"))
    complete = bool(reex.get("complete"))
    if started and not complete:
        return "extraction"
    if not _is_translation_complete(trans):
        return "translation"
    if _count_subtitle_cr2w() < SUBTITLE_DIR_TOTAL:
        return "packaging"
    return "idle"


def _is_translation_complete(trans: dict) -> bool:
    if trans.get("step_done_min") is not None:
        return True
    needed = trans.get("fields_needed")
    fixed  = trans.get("fixed", 0) or 0
    return needed is not None and fixed >= needed


# ── stage file override ───────────────────────────────────────────────────────

def _detect_stage() -> Stage:
    """Read ~/.translation_manager/cp2077_stage if present; else auto-detect."""
    stage_file = Path.home() / ".translation_manager" / "cp2077_stage"
    if stage_file.exists():
        content = stage_file.read_text(encoding="utf-8").strip()
        if content:
            return content
    # Fall back to live auto-detection from log files
    reex  = _parse_reextract_state()
    trans = _parse_translation_state()
    return _detect_phase(trans, reex)


# ── multi-stage TUI helpers ──────────────────────────────────────────────────

def _stage1(reex: dict) -> StageInfo:
    """Step 1 — extraction (chilutz/sidur subtitles)."""
    complete = bool(reex.get('complete'))
    started  = bool(reex.get('started_at') or reex.get('file_count'))
    file_count = int(reex.get('file_count') or 0)
    done_log   = int(reex.get('done_log')   or 0)
    total      = int(reex.get('total')      or REEXTRACT_TOTAL)
    rate_s     = float(reex.get('rate_per_sec') or 0)
    failed     = int(reex.get('failed') or 0)
    detail: list[str] = []
    if complete:
        status = 'done'
        detail.append(f"✓ הסתיים — {file_count:,}/{total:,} קבצים")
    elif started:
        status = 'active'
        detail.append(
            f"קבצים (דיסק): {file_count:>5,}/{total:,}      "
            f"לוג: {done_log:>5,}/{total:,}      נכשלו: {failed}"
        )
        if rate_s > 0:
            eta = (total - max(file_count, done_log)) / rate_s
            detail.append(
                f"קצב: {rate_s:.2f} קבצים/שנ׳      זמן משוער לסיום שלב: {_fmt_dur(eta)}"
            )
    else:
        status = 'pending'
        detail.append("(ממתין להתחלה)")
    return StageInfo(
        key='extraction',
        title_he='שלב 1 — חילוץ וסידור כתוביות',
        status=status,
        processed=max(file_count, done_log),
        total=total,
        unit='קבצים',
        rate_per_hour=int(rate_s * 3600),
        detail_lines=detail,
    )


def _stage2(reex: dict, trans: dict) -> StageInfo:
    """Step 2 — translation (LM Studio loop)."""
    reex_done = bool(reex.get('complete'))
    fixed     = int(trans.get('fixed') or 0)
    needed    = trans.get('fields_needed')
    needed_i  = int(needed) if needed else 0
    remaining = int(trans.get('remaining') or max(0, needed_i - fixed))
    skipped   = int(trans.get('skipped') or 0)
    rpm       = float(trans.get('rate_per_min') or 0)
    elapsed   = trans.get('elapsed_sec')
    step_done = trans.get('step_done_min')
    skipped_step = bool(trans.get('skipped_step'))

    detail: list[str] = []
    if not reex_done:
        status = 'pending'
        detail.append("(ממתין לסיום שלב 1)")
    elif skipped_step:
        status = 'pending'
        detail.append("(הסתיים בריצה קודמת)")
    elif step_done is not None and step_done > 0:
        status = 'done'
        detail.append(f"✓ הסתיים תוך {step_done:.1f} דקות")
    elif fixed > 0 or needed_i > 0:
        status = 'active'
        if needed_i:
            detail.append(f"סה\"כ לתרגום: {needed_i:>9,}")
        detail.append(f"תוקן עד כה:  {fixed:>9,}")
        if remaining:
            detail.append(f"נותר:        ~{remaining:>8,}")
        if skipped:
            detail.append(f"דילוגים קבועים: {skipped:>9,}")
        if elapsed:
            detail.append(f"זמן בפעולה: {_fmt_dur(elapsed)}")
        if rpm > 0:
            detail.append(f"קצב: {rpm:.1f} ערכים/דקה")
            if remaining:
                detail.append(f"זמן משוער (לפי קצב): {_fmt_dur(remaining / rpm * 60)}")
    else:
        status = 'pending'
        detail.append("(ממתין להתחלה)")
    return StageInfo(
        key='translation',
        title_he='שלב 2 — תרגום LM Studio',
        status=status,
        processed=fixed,
        total=needed_i,
        unit='שורות',
        rate_per_hour=int(rpm * 60),
        detail_lines=detail,
    )


def _stage3(trans_done: bool) -> StageInfo:
    """Step 3 — packaging + deployment.

    Only "active" once Step 2 (translation) is done — stale CR2W files
    from a prior deploy don't count as in-progress.
    """
    cur = _count_subtitle_cr2w()
    rate_h = _packaging_rate_per_hour(cur)
    complete = cur >= SUBTITLE_DIR_TOTAL

    detail: list[str] = []
    if complete:
        status = 'done'
        detail.append(f"✓ פריסה הסתיימה — {cur:,}/{SUBTITLE_DIR_TOTAL:,} קבצים")
    elif not trans_done:
        status = 'pending'
        detail.append("(ממתין לסיום שלב 2)")
        if cur > 0:
            detail.append(f"{C_DIM}(שאריות מריצה קודמת: {cur:,} קבצים){C_RESET}")
    else:
        status = 'active'
        detail.append(f"קבצים ארוזים: {cur:>5,}/{SUBTITLE_DIR_TOTAL:,}")
        if rate_h > 0:
            remaining = SUBTITLE_DIR_TOTAL - cur
            detail.append(
                f"קצב: {rate_h:,}/שעה      זמן משוער: {_fmt_dur(remaining * 3600 / rate_h)}"
            )
    return StageInfo(
        key='packaging',
        title_he='שלב 3 — אריזת CR2W ופריסה',
        status=status,
        processed=cur,
        total=SUBTITLE_DIR_TOTAL,
        unit='קבצים',
        rate_per_hour=rate_h,
        detail_lines=detail,
    )


def _fmt_dur(seconds: float) -> str:
    s = int(max(0, seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m"
    return f"{m}m {sec:02d}s"


def _summary_eta(stages: list[StageInfo]) -> int | None:
    total = 0
    any_remaining = False
    for st in stages:
        if st.status == 'done':
            continue
        remaining = max(0, st.total - st.processed)
        if remaining and st.rate_per_hour > 0:
            total += int(remaining * 3600 / st.rate_per_hour)
            any_remaining = True
        elif remaining:
            any_remaining = True   # unknown rate; can't include but mark unfinished
    return total if any_remaining and total > 0 else (None if any_remaining else 0)


# ── main adapter callback ─────────────────────────────────────────────────────

def _collect() -> Snapshot | None:
    try:
        reex  = _parse_reextract_state()
        trans = _parse_translation_state()
    except Exception as exc:
        log.warning("cp2077 adapter: parse failed: %s", exc)
        return None

    phase = _detect_phase(trans, reex)

    if phase == "extraction":
        cur   = int(reex.get("file_count") or 0)
        total = int(reex.get("total") or REEXTRACT_TOTAL)
        rate  = int(float(reex.get("rate_per_sec") or 0) * 3600)
        unit  = "קבצים"
    elif phase == "translation":
        fixed     = int(trans.get("fixed") or 0)
        remaining = int(trans.get("remaining") or 0)
        total     = (fixed + remaining) if (fixed or remaining) else int(trans.get("fields_needed") or 0)
        cur       = fixed
        rate      = int((trans.get("rate_per_min") or 0) * 60)
        unit      = "שורות"
    elif phase == "packaging":
        cur   = _count_subtitle_cr2w()
        total = SUBTITLE_DIR_TOTAL
        rate  = _packaging_rate_per_hour(cur)
        unit  = "קבצים"
    else:  # idle
        cur   = SUBTITLE_DIR_TOTAL
        total = SUBTITLE_DIR_TOTAL
        rate  = 0
        unit  = "קבצים"

    # If no live data at all (pipeline hasn't started) return None
    if cur == 0 and total == 0:
        log.info("cp2077 adapter: no live data (pipeline not running)")
        return None

    # Build the multi-stage view for the TUI. Order matters: legacy
    # showed Step 1 → 2 → 3.
    trans_done = bool(trans.get('step_done_min') is not None or _is_translation_complete(trans))
    stages = [_stage1(reex), _stage2(reex, trans), _stage3(trans_done)]

    return Snapshot(
        game_id         = GAME_ID,
        phase           = phase,
        gpu_model       = GPU,
        ai_model        = AI_MODEL,
        processed       = cur,
        total           = total,
        rate_per_hour   = rate,
        unit            = unit,
        stages          = stages,
        summary_eta_sec = _summary_eta(stages),
        headline_he     = 'תרגום סייברפאנק 2077 לעברית — מסך מעקב חי',
    )


# ── factory ───────────────────────────────────────────────────────────────────

def build() -> Monitor:
    return Monitor(game_id=GAME_ID, adapter=_collect)
