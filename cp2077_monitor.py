"""
cp2077_monitor.py — Live dashboard for the master pipeline (V2)
===============================================================
V2 pipeline steps:
  Step 1: cp2077_reextract_subtitles.py   (extract + serialize en-us subtitle CR2W)
  Step 2: cp2077_fix_missing_translations.py  (LM Studio translation)
  Step 3: cp2077_subtitle_batch.py         (inject + pack + deploy)

Run this in a separate terminal while the pipeline is running.
Refreshes every 10 seconds.

Usage:
    python cp2077_monitor.py

Press Ctrl+C to exit.
"""

import json
import os
import re
import sys
import time
import subprocess
from datetime import datetime, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Enable ANSI escape (virtual terminal) processing for legacy cmd.exe on Win10/11.
# Modern Windows Terminal already has VT on; this is a no-op there.
if os.name == "nt":
    try:
        import ctypes

        _kernel32 = ctypes.windll.kernel32
        _hStdout = _kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        _mode = ctypes.c_uint()
        if _kernel32.GetConsoleMode(_hStdout, ctypes.byref(_mode)):
            _kernel32.SetConsoleMode(
                _hStdout, _mode.value | 0x0004
            )  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    except Exception:
        pass

# Detect whether the terminal applies the Unicode bidi algorithm. Windows
# Terminal and ConEmu set env vars we can sniff. Legacy cmd.exe does NOT do
# bidi — it renders Hebrew in storage (logical) order, which looks mirrored.
_LEGACY_CONSOLE = (
    os.name == "nt"
    and not os.environ.get("WT_SESSION")
    and not os.environ.get("ConEmuPID")
    and not os.environ.get("TERM_PROGRAM")
)


# ANSI color palette. \033[0m resets. These are no-ops if redirected to a file
# (e.g. piped to `tee`), since the bytes just don't render visually anywhere.
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    GRAY = "\033[90m"
    RED = "\033[91m"  # bright red for warnings
    GREEN = "\033[92m"  # bright green for done/Smart ETA
    YELLOW = "\033[93m"  # bright yellow for active
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"  # magenta for ETA highlights
    CYAN = "\033[96m"
    WHITE = "\033[97m"


PROJ = r"C:\Users\nc528\סקריפטים\תרגום משחקים"

# Throttled push to the universal /api/admin/progress endpoint. The push
# is performed by monitor_push (which reads MONITOR_TOKEN + PROGRESS_API_URL
# from the project's .env) — this module just decides when to trigger.
PUSH_INTERVAL_SEC = 900  # once every 15 minutes
_last_push_time = 0.0

# ── Unified phase config (translation -> packaging -> idle) ─────────────────
# Total subtitle CR2W files expected after packaging completes.
SUBTITLE_DIR_TOTAL = 3083
# Where the subtitle batch deposits its rebuilt CR2W files.
PROJ_AR_SUBTITLES = (
    r"C:\Users\nc528\סקריפטים\תרגום משחקים\תרגום_משחקים"
    r"\source\archive\base\localization\ar-ar\subtitles"
)
# Rolling snapshots for measuring packaging throughput (files/hour).
_pkg_snapshots = []
_PKG_RATE_WINDOW_SEC = 1800  # 30 minutes

LOG_MASTER = os.path.join(PROJ, "master_pipeline_v2.log")
LOG_TRANS = os.path.join(PROJ, "fix_missing_translations.log")
LOG_BATCH = os.path.join(PROJ, "subtitle_batch.log")
LOG_REEXTRACT = os.path.join(PROJ, "reextract_subtitles.log")

REEXTRACT_TEXT_DIR = r"C:\Users\nc528\AppData\Local\Temp\reextract_subs\text"
REEXTRACT_DONE_MARKER = os.path.join(REEXTRACT_TEXT_DIR, ".serialize_done")
REEXTRACT_TOTAL = 3085

REFRESH_SEC = 10

# Estimates for steps not yet started
STEP3_EST_FILES_PER_SEC = 1.0  # WolvenKit subtitle batch, rough
STEP3_TOTAL_FILES = 3083
STEP_DEPLOY_EST_SEC = 30  # pack + deploy

# ── Smart-ETA resource files + throughput profile ────────────────────────────
BASE_RESOURCES = os.path.join(PROJ, "תרגום_משחקים", "source", "resources")
ORIGINAL_FILE = os.path.join(BASE_RESOURCES, "localization_export.json")
TRANSLATED_FILE = os.path.join(BASE_RESOURCES, "localization_translated.json")
TM_CACHE_FILE = os.path.join(BASE_RESOURCES, "tm_cache.json")
SKIPS_FILE = os.path.join(BASE_RESOURCES, "translation_skips.json")

DYN_MAX_WORDS = 150  # dynamic-batch soft cap (mirror translation script)
DYN_MAX_LINES = 12  # dynamic-batch hard cap
PARALLEL_WORKERS = 4  # concurrent LM Studio slots used (mirrors translation script)
SECS_PER_BATCH = 180  # observed wall time per 12-item batch under 4-worker contention (Gemma-2-27B Q4 on RX 9070)

# ── regexes ───────────────────────────────────────────────────────────────────
RE_REEXTRACT_PROGRESS = re.compile(
    r"\[(\d[\d,]*)/(\d[\d,]*)\]\s+done=([\d,]+)\s+failed=([\d,]+)"
    r"\s+rate=([0-9.]+)/s\s+ETA=([0-9.]+)h"
)
# Accept both legacy "[*] N fields need (re)translation" and new global-queue
# "[*] Global queue: N pending items" formats. Allow comma-separated digits in N.
RE_NEED = re.compile(
    r"\[\*\]\s+(?:Global\s+queue:\s+)?([\d,]+)\s+(?:pending\s+items|fields?\s+need\s+\(re\)translation)"
)
RE_SAVED = re.compile(r"\[~\]\s+Saved\s+—\s+([\d,]+)\s+fixed,\s+~([\d,]+)\s+remaining")
RE_SKIP = re.compile(r"\[SKIP\]")
RE_BATCH_PROGRESS = re.compile(
    r"\[(\d+)/(\d+)\][^\|]*\|\s*processed=(\d+)\s+skipped=(\d+)\s+failed=(\d+)"
    r"\s*\|\s*rate=([0-9.]+)/s\s*\|\s*ETA\s+([0-9.]+)h"
)
# New format emitted by cp2077_subtitle_batch.py after the progress-bar refactor:
#   [####------]  53.4%  1,772 / 3,083  rate=0.08/s  ETA 4.5h  (processed=820 skipped=952 failed=0)
RE_BATCH_PROGRESS_NEW = re.compile(
    r"\[[#\-]+\]\s+([\d.]+)%\s+([\d,]+)\s*/\s*([\d,]+)\s+"
    r"rate=([\d.]+)/s\s+ETA\s+([\d.]+)h\s+"
    r"\(processed=(\d+)\s+skipped=(\d+)\s+failed=(\d+)\)"
)
RE_BATCH_STATS = re.compile(r"Phase 2 stats:")
RE_PHASE2_PROC = re.compile(r"Phase 2:\s+Processing\s+([\d,]+)\s+subtitle files")
RE_TRANS_DONE = re.compile(r"\[\*\]\s+Done\.\s+Fixed\s+([\d,]+)\s+fields?\b")
RE_TRANS_START_TIME = re.compile(
    r"\[started:\s+(?:(\d{4}-\d{2}-\d{2})\s+)?(\d{2}:\d{2}:\d{2})\]"
)
# Physical ceiling for translation throughput: 4 LM-Studio workers
# producing at most ~0.5 items/sec each. If the apparent burn rate is
# above this, the parsed run-start date is older than today and needs
# to be walked back another day.
MAX_ITEMS_PER_SEC = 2.0
# Global-queue phase markers: Phase 2 produces TM/FT counts (the instant burst),
# Phase 3 is the LM-only steady state we want to project from.
RE_PHASE2_DONE = re.compile(
    r"\[\*\]\s+Phase\s+2\s+done:\s+([\d,]+)\s+TM\s+hits,\s+([\d,]+)\s+fast-track\s+hits"
)
RE_PHASE3_START = re.compile(r"\[\*\]\s+Phase\s+3:")
RE_DEPLOY = re.compile(r"Deployed:.*archive.*?\((\d[\d,]*)\s+bytes\)")
RE_STEP_DONE = re.compile(
    r"STEP DONE:\s+(.+?)\s+\(exit=(-?\d+),\s+took\s+([\d.]+)\s*min\)"
)
RE_PIPELINE_DONE = re.compile(r"MASTER PIPELINE COMPLETE\s+—\s+total\s+([\d.]+)\s*min")
RE_LOG_TIME = re.compile(r"^\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\]")


# ── helpers ───────────────────────────────────────────────────────────────────
def clear_screen():
    subprocess.run("cls" if os.name == "nt" else "clear", shell=True, check=False)


# Bracket / quote pairs that look directional. When we reverse a Hebrew string
# for legacy cmd.exe, these characters end up on the "wrong" side and need to
# be flipped to their mirror partner so the visual pairing still reads naturally
# at an L-to-R glance.
_BRACKET_MIRROR = str.maketrans(
    {
        "(": ")",
        ")": "(",
        "[": "]",
        "]": "[",
        "{": "}",
        "}": "{",
        "<": ">",
        ">": "<",
        "«": "»",
        "»": "«",
        "‹": "›",
        "›": "‹",
        "⟨": "⟩",
        "⟩": "⟨",
        "“": "”",
        "”": "“",  # “ ”
        "‘": "’",
        "’": "‘",  # ‘ ’
    }
)


# A Hebrew "segment" is a Hebrew char optionally followed by more Hebrew /
# spaces / common punctuation and closed with another Hebrew char. This
# means multi-word Hebrew like "מה קורה" is treated as one run for reversal,
# so legacy cmd.exe (no bidi) shows the words in the correct order.
_HEB_RANGE = "֐-׿"
# Punctuation allowed *inside* a Hebrew segment (between Hebrew letters).
# Quotes are deliberately excluded - they usually delimit the segment.
_HEB_INNER_PUNCT = r"  \.,!?:;\-–—\(\)\[\]"
# Trailing sentence punctuation absorbed into the segment so it ends up
# on the correct (R-to-L) side after reversal.
_HEB_TRAIL_PUNCT = r"[\.,!?:;]*"
_HEB_SEGMENT_RE = re.compile(
    rf"[{_HEB_RANGE}](?:[{_HEB_RANGE}{_HEB_INNER_PUNCT}]*[{_HEB_RANGE}])?{_HEB_TRAIL_PUNCT}"
)


def fix_rtl(text):
    """Reverse Hebrew segments (including embedded spaces/punctuation) for
    legacy cmd.exe; pass through unchanged on bidi-aware terminals."""
    if not text or not _LEGACY_CONSOLE:
        return text
    return _HEB_SEGMENT_RE.sub(lambda m: m.group(0)[::-1], text)


def H(s):
    """Reverse pure-Hebrew labels for legacy cmd.exe, pass through otherwise.
    Also flips directional brackets so the visual pairing stays correct."""
    if not _LEGACY_CONSOLE:
        return s
    return s[::-1].translate(_BRACKET_MIRROR)


def read_lines_safe(path, max_lines=20000):
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return lines[-max_lines:]
    except Exception:
        return []


def read_current_run_lines(path, start_markers):
    """Return only lines from the LAST occurrence of any start_marker.
    Reads the entire file rather than a tail window — cumulative logs (e.g.
    the translation log, which grows to >30k lines as runs accumulate) can
    push the current-run marker outside any fixed-size sliding window, which
    used to silently blind the parser to a still-active run."""
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


def get_run_start_time(path, start_markers):
    lines = read_current_run_lines(path, start_markers)
    return parse_log_time(lines[0]) if lines else None


def get_trans_run_start():
    """Parse the '[started: ...]' marker from the current translation run.

    Two formats supported:
      * `[started: YYYY-MM-DD HH:MM:SS]`  (preferred, unambiguous)
      * `[started: HH:MM:SS]`            (legacy — needs date guessing)

    For the legacy format: build today's date + HH:MM:SS, then walk the
    date back one day at a time while either (a) start_dt is still in
    the future (midnight-crossing) or (b) the implied items/sec burn
    rate from the log's arrow-line count exceeds the physical ceiling
    (multi-day-old run)."""
    lines = read_current_run_lines(LOG_TRANS, TRANS_START)
    for line in lines:
        m = RE_TRANS_START_TIME.search(line)
        if not m:
            continue
        m_date, m_time = m.group(1), m.group(2)
        try:
            now_dt = datetime.now()
            if m_date:
                return datetime.strptime(
                    f"{m_date} {m_time}", "%Y-%m-%d %H:%M:%S"
                )
            start_dt = datetime.strptime(
                f"{now_dt.date()} {m_time}", "%Y-%m-%d %H:%M:%S"
            )
            while start_dt > now_dt:
                start_dt -= timedelta(days=1)
            # Multi-day rollback: if the run already has more arrow lines
            # than is physically possible in the implied elapsed window,
            # walk back another day. Loop converges (each step adds 24h).
            fixed_observed = sum(
                1 for l in lines if " -> '" in l or " → " in l
            )
            while fixed_observed > 0:
                elapsed = (now_dt - start_dt).total_seconds()
                if elapsed <= 0 or fixed_observed / elapsed <= MAX_ITEMS_PER_SEC:
                    break
                start_dt -= timedelta(days=1)
            return start_dt
        except Exception:
            return None
    return None


def fmt_duration(seconds):
    s = int(seconds)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h}h {m:02d}m" if h > 0 else f"{m}m {s:02d}s"


def parse_log_time(line):
    m = RE_LOG_TIME.match(line)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def count_json_files(directory):
    """Walk directory and count *.json files (real-time disk count)."""
    try:
        count = 0
        for _, _, files in os.walk(directory):
            for f in files:
                if f.endswith(".json"):
                    count += 1
        return count
    except Exception:
        return 0


def count_subtitle_cr2w():
    """Count packaged subtitle CR2W files in the project archive tree.
    These are stored with a .json extension despite being binary CR2W."""
    return count_json_files(PROJ_AR_SUBTITLES)


def packaging_rate_per_hour(current_count):
    """Maintain a rolling-window snapshot list and return files/hour rate.
    Returns 0 until at least two snapshots span enough time to be meaningful."""
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


def is_translation_complete(trans):
    """Translation is done if any of:
      * the trans log shows a successful '[*] Done. Fixed N fields' marker,
      * the parsed trans_state has step_done_min set,
      * fixed reached the queue size that the translator scanned.
    The first check is the authoritative one — it works even when the trans
    parser early-returns an empty state because some other run is active
    (e.g. standalone_batch mode while subtitle packaging is in progress)."""
    if _trans_step_done():
        return True
    if trans.get("step_done_min") is not None:
        return True
    needed = trans.get("fields_needed")
    fixed = trans.get("fixed", 0) or 0
    return needed is not None and fixed >= needed


def detect_unified_phase(trans, reex=None):
    """Returns one of:
        'extraction'  — WolvenKit unbundle/serialize step is actively running
        'translation' — LM-Studio translation pass is in progress
        'packaging'   — subtitle CR2W rebuild is in progress
        'idle'        — all 3,083 files packaged, nothing more to do

    Auto-detection order matches the natural pipeline:
      extraction → translation → packaging → idle.
    The first phase whose "is-it-running?" predicate fires wins, so the
    UI tracks the current step without any manual switch.
    """
    if reex is None:
        try:
            reex = parse_reextract_state()
        except Exception:
            reex = None

    # Extraction is "currently running" when the reextract job has started
    # but neither phase 1 (unbundle) nor the final serialize-done marker
    # has fired. Once both are true the script's output is no longer the
    # source of progress — translation/packaging take over.
    if reex:
        started = bool(reex.get("started_at"))
        complete = bool(reex.get("complete"))
        if started and not complete:
            return "extraction"

    if not is_translation_complete(trans):
        return "translation"
    if count_subtitle_cr2w() < SUBTITLE_DIR_TOTAL:
        return "packaging"
    return "idle"


# ── Smart-ETA predicates (mirror cp2077_fix_missing_translations.py) ────────
_HEBREW_RE = re.compile(r"[֐-׿]")
_LATIN_RE = re.compile(r"[A-Za-z]")
_TAG_RE = re.compile(r"<.*?>|\{.*?\}|%[a-zA-Z]")
_FOREIGN_RE = re.compile(r"[Ѐ-ӿ؀-ۿ฀-๿ऀ-ॿ一-鿿]")
_FT_PUNCT_RE = re.compile(r"^(.+?)([\.\!\?,;:]*)$")
_ALLOWED_FOLDERS = ("onscreens", "subtitles")
_FAST_TRACK_KEYS = frozenset(
    {
        "yes",
        "yeah",
        "yep",
        "yup",
        "sure",
        "ok",
        "okay",
        "alright",
        "no",
        "nope",
        "nah",
        "hello",
        "hi",
        "hey",
        "bye",
        "goodbye",
        "thanks",
        "thank you",
        "please",
        "sorry",
        "excuse me",
        "wait",
        "stop",
        "go",
        "look",
        "listen",
        "help",
        "come on",
        "hurry",
        "damn",
        "shit",
        "fuck",
        "really",
        "maybe",
    }
)


def _is_valid_translation(orig, trans):
    if not isinstance(trans, str) or not trans:
        return False
    if not _HEBREW_RE.search(trans):
        return False
    if _FOREIGN_RE.search(trans):
        return False
    if isinstance(orig, str):
        for tag in _TAG_RE.findall(orig):
            if tag not in trans:
                return False
    return True


def _needs_translation(orig, trans):
    if not orig or not isinstance(orig, str):
        return False
    if _is_valid_translation(orig, trans):
        return False
    if not _LATIN_RE.search(orig):
        return False
    cleaned = re.sub(r"<[^>]+>", "", orig)
    if len(re.sub(r"[^a-zA-Z]", "", cleaned)) <= 1:
        return False
    return True


def _is_fast_trackable(text):
    if not isinstance(text, str) or not text:
        return False
    if "<" in text or "{" in text or "%" in text:
        return False
    s = text.strip()
    if not s:
        return False
    m = _FT_PUNCT_RE.match(s)
    if not m:
        return False
    return m.group(1).strip().lower() in _FAST_TRACK_KEYS


def _in_allowed_folder(path):
    p = path.lower()
    return any(f in p for f in _ALLOWED_FOLDERS)


# Lazy JSON loaders — reload only when mtime changes (the 122 MB original is
# constant during a run; the translated file rewrites every 100 fixes).
_smart_eta_cache = {
    "original": None,
    "original_mtime": 0,
    "translated": None,
    "translated_mtime": 0,
    "tm": None,
    "tm_mtime": 0,
    "skips": None,
    "skips_mtime": 0,
    "result": None,  # invalidated whenever any source file changes
}


def _load_if_changed(path, key_data, key_mtime):
    if not os.path.exists(path):
        return _smart_eta_cache[key_data]
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return _smart_eta_cache[key_data]
    if mtime == _smart_eta_cache[key_mtime] and _smart_eta_cache[key_data] is not None:
        return _smart_eta_cache[key_data]
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return _smart_eta_cache[key_data]
    _smart_eta_cache[key_data] = data
    _smart_eta_cache[key_mtime] = mtime
    _smart_eta_cache["result"] = None  # any change invalidates the computed ETA
    return data


def compute_smart_eta():
    """Return a dict with the precise batch-count-driven ETA, or None if data unavailable."""
    original = _load_if_changed(ORIGINAL_FILE, "original", "original_mtime")
    translated = _load_if_changed(TRANSLATED_FILE, "translated", "translated_mtime")
    tm = _load_if_changed(TM_CACHE_FILE, "tm", "tm_mtime")
    skips_raw = _load_if_changed(SKIPS_FILE, "skips", "skips_mtime")

    if not original or not translated:
        return None
    if _smart_eta_cache["result"] is not None:
        return _smart_eta_cache["result"]

    tm = tm or {}
    skips = set()
    if skips_raw:
        try:
            skips = set(
                tuple(x)
                for x in skips_raw
                if isinstance(x, (list, tuple)) and len(x) == 3
            )
        except Exception:
            skips = set()

    total_batches = 0
    lm_items = 0
    tm_skipped = 0
    ft_skipped = 0
    already_done = 0

    for filepath, orig_entries in original.items():
        if not _in_allowed_folder(filepath):
            continue
        trans_entries = translated.get(filepath, [])

        pending_texts = []  # only items that would actually hit the LM
        for i, orig in enumerate(orig_entries):
            t = trans_entries[i] if i < len(trans_entries) else {}
            for field in ("femaleVariant", "maleVariant"):
                if (filepath, str(i), field) in skips:
                    continue
                src = orig.get(field, "") or t.get(field, "")
                trg = t.get(field, "")
                if not _needs_translation(src, trg):
                    already_done += 1
                    continue
                if src in tm and _is_valid_translation(src, tm[src]):
                    tm_skipped += 1
                    continue
                if _is_fast_trackable(src):
                    ft_skipped += 1
                    continue
                pending_texts.append(src)
                lm_items += 1

        # Simulate the per-file dynamic batcher: words<=DYN_MAX_WORDS or len<=DYN_MAX_LINES.
        bs = 0
        bw = 0
        for text in pending_texts:
            w = len(text.split())
            if bs > 0 and (bw + w > DYN_MAX_WORDS or bs >= DYN_MAX_LINES):
                total_batches += 1
                bs = 0
                bw = 0
            bs += 1
            bw += w
        if bs > 0:
            total_batches += 1

    eta_sec = (total_batches * SECS_PER_BATCH) / max(PARALLEL_WORKERS, 1)
    result = {
        "batches": total_batches,
        "lm_items": lm_items,
        "tm_skipped": tm_skipped,
        "ft_skipped": ft_skipped,
        "already_done": already_done,
        "eta_sec": eta_sec,
    }
    _smart_eta_cache["result"] = result
    return result


# ── active-run detection ──────────────────────────────────────────────────────
MASTER_START = "MASTER PIPELINE"  # catches both V1 and V2
BATCH_START = "cp2077_subtitle_batch starting"
REEXTRACT_START = "cp2077_reextract_subtitles starting"
TRANS_START = "[*] Using"  # first line cp2077_fix_missing_translations prints


def _trans_step_done():
    """True only when the CURRENT translation run finished AND fixed_count > 0.

    Scoped to the latest `[*] Using` (TRANS_START) marker so a previous run's
    'Done. Fixed N fields' line in the accumulated log doesn't falsely report
    the active run as complete — which would push the monitor into Step 3 and
    surface stale subtitle_batch.log data."""
    lines = read_current_run_lines(LOG_TRANS, TRANS_START)
    if not lines:
        return False
    for line in lines:
        m = RE_TRANS_DONE.search(line)
        if m:
            return int(m.group(1).replace(",", "")) > 0
    return False


def detect_active_run():
    """Return ('master', start_time) | ('standalone_batch', start_time) | ('idle', None)."""
    master_start = get_run_start_time(LOG_MASTER, MASTER_START)
    batch_start = get_run_start_time(LOG_BATCH, BATCH_START)
    reextract_start = get_run_start_time(LOG_REEXTRACT, REEXTRACT_START)
    trans_start = get_trans_run_start()  # parses [started: HH:MM:SS] from trans log

    # Step 1 active (reextract not yet done)
    if reextract_start and not os.path.exists(REEXTRACT_DONE_MARKER):
        if master_start is None or reextract_start >= master_start:
            return ("master", reextract_start)

    # Step 2 active (translation log exists and not done)
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


# ── parsers ───────────────────────────────────────────────────────────────────
def parse_reextract_state():
    """Step 1: extraction + serialization progress."""
    state = {
        "phase1_done": False,
        "phase2_started": False,
        "done_log": 0,  # last checkpoint from log
        "file_count": 0,  # real-time disk count
        "total": REEXTRACT_TOTAL,
        "failed": 0,
        "rate_per_sec": 0.0,
        "eta_h": 0.0,
        "complete": False,
        "started_at": None,
    }

    if os.path.exists(REEXTRACT_DONE_MARKER):
        state["complete"] = True

    # Real-time file count (always, even if log is stale)
    state["file_count"] = count_json_files(REEXTRACT_TEXT_DIR)

    lines = read_lines_safe(LOG_REEXTRACT, max_lines=5000)
    if not lines:
        return state

    # Scope to latest run
    last_start = -1
    for i, line in enumerate(lines):
        if REEXTRACT_START in line:
            last_start = i
    if last_start >= 0:
        state["started_at"] = parse_log_time(lines[last_start])
        lines = lines[last_start:]

    for line in lines:
        if "Extracted" in line and "subtitle CR2W" in line:
            state["phase1_done"] = True
        if "Phase 2: Serializing" in line:
            state["phase2_started"] = True
        m = RE_REEXTRACT_PROGRESS.search(line)
        if m:
            state["done_log"] = int(m.group(1).replace(",", ""))
            state["total"] = int(m.group(2).replace(",", ""))
            state["failed"] = int(m.group(4).replace(",", ""))
            state["rate_per_sec"] = float(m.group(5))
            state["eta_h"] = float(m.group(6))
        if "serialize_done" in line or "Phase 2: serialize already done" in line:
            state["complete"] = True

    return state


def parse_translation_state():
    """Step 2: LM Studio translation progress (scoped to current master run).

    Phase 3 detection: if `[*] Phase 3:` appears in the log, the rate calculation
    drops everything from before the marker so the Phase 2 instant burst (TM+FT
    lookups) doesn't pollute the steady-state estimate.
    """
    state = {
        "fields_needed": None,
        "fixed": 0,
        "remaining": None,
        "skipped": 0,
        "last_save_time": None,
        "first_save_time": None,
        "rate_per_min": 0,
        "step_done_min": None,
        "skipped_step": False,
        "run_start_dt": None,
        "elapsed_sec": None,
        # Phase 2/3 tracking — used to compute Phase-3-only steady-state rate
        "phase3_seen": False,
        "phase3_baseline_fixed": 0,   # items already counted by end of Phase 2
        "phase3_elapsed_sec": None,   # wall seconds since Phase 3 effectively began
    }
    mode, _ = detect_active_run()
    if mode == "standalone_batch":
        state["skipped_step"] = True
        return state

    # Scope to latest run of the standalone translation script
    lines = read_current_run_lines(LOG_TRANS, TRANS_START)

    saves = []
    arrow_lines = []  # individual "entry X -> 'hebrew'" lines between saves
    for line in lines:
        m = RE_NEED.search(line)
        if m:
            state["fields_needed"] = int(m.group(1).replace(",", ""))
        m = RE_SAVED.search(line)
        if m:
            t = parse_log_time(line)
            saves.append(
                (t, int(m.group(1).replace(",", "")), int(m.group(2).replace(",", "")))
            )
            arrow_lines = []  # reset; save checkpoint is now the floor
        if RE_SKIP.search(line):
            state["skipped"] += 1
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
                    # Midnight-crossing rollback (run started yesterday-late).
                    while start_dt > now_dt:
                        start_dt -= timedelta(days=1)
                    state["run_start_dt"] = start_dt
            except Exception:
                pass
        m = RE_TRANS_DONE.search(line)
        if m:
            # Compute elapsed minutes from run start to this line
            t_done = parse_log_time(line)
            t_start = parse_log_time(lines[0]) if lines else None
            if t_done and t_start:
                state["step_done_min"] = (t_done - t_start).total_seconds() / 60.0
            else:
                state["step_done_min"] = 0.0

    # Compute elapsed seconds from run start to now
    if state["run_start_dt"]:
        state["elapsed_sec"] = (datetime.now() - state["run_start_dt"]).total_seconds()

    # Multi-day rollback for old-format [started: HH:MM:SS] logs: when the
    # implied burn rate exceeds the physical ceiling, the parsed start date
    # is wrong by an integer number of days. Walk it back until the rate
    # becomes plausible. Skipped automatically for the new full-date format
    # because the rate will already be within bounds.
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
        state["fixed"] = base_fixed + extra
        state["remaining"] = max(0, saves[-1][2] - extra)
        state["last_save_time"] = saves[-1][0]
        state["first_save_time"] = saves[0][0]
        window = saves[-5:]
        if len(window) >= 2 and window[0][0] and window[-1][0]:
            dt = (window[-1][0] - window[0][0]).total_seconds()
            d_fixed = window[-1][1] - window[0][1]
            state["rate_per_min"] = (d_fixed / dt * 60) if dt > 0 else 0
        # Refine rate with arrow lines accrued since last save
        if not state["rate_per_min"] and state["elapsed_sec"] and state["fixed"] > 0:
            state["rate_per_min"] = state["fixed"] / state["elapsed_sec"] * 60
    elif arrow_lines and state["fields_needed"]:
        # No save checkpoint yet — estimate from arrow lines + elapsed
        state["fixed"] = len(arrow_lines)
        state["remaining"] = max(0, state["fields_needed"] - len(arrow_lines))
        if state["elapsed_sec"] and state["elapsed_sec"] > 0:
            state["rate_per_min"] = len(arrow_lines) / state["elapsed_sec"] * 60

    # Override with Phase-3-only rate when we have enough Phase 3 data. This
    # removes the Phase 2 instant-burst contribution (TM + fast-track hits) that
    # would otherwise inflate the cumulative average.
    if (
        state["phase3_seen"]
        and state["run_start_dt"]
        and state["fixed"] > state["phase3_baseline_fixed"]
    ):
        # Estimate Phase 3 start as run_start + 30s (Phase 2's instant lookups
        # for ~1k-2k items finish in well under a minute on disk-bound I/O).
        phase3_start = state["run_start_dt"] + timedelta(seconds=30)
        phase3_elapsed = (datetime.now() - phase3_start).total_seconds()
        if phase3_elapsed > 60:
            phase3_items = state["fixed"] - state["phase3_baseline_fixed"]
            state["phase3_elapsed_sec"] = phase3_elapsed
            state["rate_per_min"] = phase3_items / phase3_elapsed * 60

    return state


def parse_batch_state():
    """Step 3: WolvenKit subtitle batch progress (scoped to current run).
    Returns empty state if Step 2 hasn't properly completed yet, so stale
    batch log data from previous runs never leaks into the display."""
    state = {
        "started": False,
        "processing_total": None,
        "current_idx": 0,
        "processed": 0,
        "skipped": 0,
        "failed": 0,
        "rate_per_sec": 0.0,
        "eta_h": 0.0,
        "stats_seen": False,
        "step_done_min": None,
    }
    # Hard gate: don't read batch log at all until Step 2 is genuinely done
    if not _trans_step_done():
        return state

    mode, _ = detect_active_run()

    lines = read_current_run_lines(LOG_BATCH, BATCH_START)
    for line in lines:
        m = RE_PHASE2_PROC.search(line)
        if m:
            state["started"] = True
            state["processing_total"] = int(m.group(1).replace(",", ""))
        # New progress-bar format (post-refactor) takes precedence
        m_new = RE_BATCH_PROGRESS_NEW.search(line)
        if m_new:
            state["current_idx"] = int(m_new.group(2).replace(",", ""))
            state["processing_total"] = int(m_new.group(3).replace(",", ""))
            state["rate_per_sec"] = float(m_new.group(4))
            state["eta_h"] = float(m_new.group(5))
            state["processed"] = int(m_new.group(6))
            state["skipped"] = int(m_new.group(7))
            state["failed"] = int(m_new.group(8))
            state["started"] = True
            continue
        m = RE_BATCH_PROGRESS.search(line)
        if m:
            state["current_idx"] = int(m.group(1))
            if state["processing_total"] is None:
                state["processing_total"] = int(m.group(2))
            state["processed"] = int(m.group(3))
            state["skipped"] = int(m.group(4))
            state["failed"] = int(m.group(5))
            state["rate_per_sec"] = float(m.group(6))
            state["eta_h"] = float(m.group(7))
        if RE_BATCH_STATS.search(line):
            state["stats_seen"] = True

    # Authoritative override: the actual count of packaged CR2W files on disk.
    # This stays accurate even if the log parser misses lines (e.g. if the
    # batch is logging to a different file than LOG_BATCH).
    cur_disk = count_subtitle_cr2w()
    if cur_disk > 0:
        state["started"] = True
        state["current_idx"] = max(state["current_idx"], cur_disk)
        if state["processing_total"] is None:
            state["processing_total"] = SUBTITLE_DIR_TOTAL
        # If the log didn't yield a rate, fall back to the rolling snapshot rate.
        if state["rate_per_sec"] <= 0:
            rph = packaging_rate_per_hour(cur_disk)
            if rph > 0:
                state["rate_per_sec"] = rph / 3600.0
                files_left = max(0, SUBTITLE_DIR_TOTAL - cur_disk)
                state["eta_h"] = (files_left / state["rate_per_sec"]) / 3600 if state["rate_per_sec"] > 0 else 0.0

    if mode == "master":
        pipeline_lines = read_current_run_lines(LOG_MASTER, MASTER_START)
        for line in pipeline_lines:
            m = RE_STEP_DONE.search(line)
            if m and "Inject" in m.group(1):
                state["step_done_min"] = float(m.group(3))

    return state


def parse_pipeline_state():
    """Overall pipeline state."""
    state = {
        "running": False,
        "started_at": None,
        "current_step": "Unknown",
        "complete": False,
        "complete_total_min": None,
        "deployed_size": None,
        "mode": "idle",
    }
    mode, started_at = detect_active_run()
    state["mode"] = mode
    state["started_at"] = started_at
    state["running"] = mode != "idle"

    if mode == "master":
        lines = read_current_run_lines(LOG_MASTER, MASTER_START)
        for line in lines:
            m = re.search(r"^\[.*?\] STEP:\s+(.+)$", line)
            if m:
                state["current_step"] = m.group(1).strip()
            m = RE_PIPELINE_DONE.search(line)
            if m:
                state["complete"] = True
                state["complete_total_min"] = float(m.group(1))
            m = RE_DEPLOY.search(line)
            if m:
                state["deployed_size"] = int(m.group(1).replace(",", ""))
    elif mode == "standalone_batch":
        lines = read_current_run_lines(LOG_BATCH, BATCH_START)
        state["current_step"] = "Standalone subtitle batch"
        for line in lines:
            m = RE_DEPLOY.search(line)
            if m:
                state["deployed_size"] = int(m.group(1).replace(",", ""))
            if "cp2077_subtitle_batch DONE" in line:
                state["complete"] = True
                t = parse_log_time(line)
                if t and started_at:
                    state["complete_total_min"] = (
                        t - started_at
                    ).total_seconds() / 60.0

    return state


def get_recent_activity(n=6):
    mode, _ = detect_active_run()
    if mode == "master":
        # Pick the most relevant active log
        if not os.path.exists(REEXTRACT_DONE_MARKER):
            lines = read_current_run_lines(LOG_REEXTRACT, REEXTRACT_START)
        elif not _trans_step_done():
            lines = read_current_run_lines(LOG_TRANS, TRANS_START)
        else:
            lines = read_current_run_lines(LOG_MASTER, MASTER_START)
    elif mode == "standalone_batch":
        lines = read_current_run_lines(LOG_BATCH, BATCH_START)
    else:
        lines = []

    keep = []
    for line in reversed(lines):
        line = line.rstrip()
        if not line:
            continue
        if any(
            k in line
            for k in (
                "STEP",
                "Saved",
                "Phase",
                "Deployed",
                "PIPELINE",
                "FAIL",
                "fields need",
                "Global queue",
                "ok fv",
                "Extracting",
                "Serializing",
                "done=",
                "serialize_done",
                "[~]",
                "[SKIP]",
                "Done. Fixed",
                "→",
                " -> '",
            )
        ):
            keep.append(line)
        if len(keep) >= n:
            break
    return list(reversed(keep))


def compute_total_eta(reex, trans, batch, pipeline):
    """Estimate total remaining seconds across all three steps."""
    if pipeline["complete"]:
        return None

    remaining_sec = 0

    # Step 1: extraction/serialization
    if not reex["complete"]:
        done = max(reex["file_count"], reex["done_log"])
        files_left = reex["total"] - done
        rate = (
            reex["rate_per_sec"] if reex["rate_per_sec"] > 0 else 0.08
        )  # observed fallback
        remaining_sec += files_left / rate

    # Step 2: translation (only meaningful once Step 1 is done and translation isn't yet complete)
    if reex["complete"] and not is_translation_complete(trans):
        if trans.get("rate_per_min", 0) > 0 and trans.get("remaining"):
            remaining_sec += trans["remaining"] / trans["rate_per_min"] * 60
        elif trans.get("remaining"):
            remaining_sec += trans["remaining"] / 6.0 * 60

    # Step 3: subtitle CR2W packaging — drive from on-disk file count when
    # translation is complete. Use the rolling rate; fall back to a generous
    # 0.25 files/sec estimate if the rate isn't established yet (< 30s gap).
    if is_translation_complete(trans) and not batch.get("step_done_min"):
        cur = count_subtitle_cr2w()
        files_left = max(0, SUBTITLE_DIR_TOTAL - cur)
        if files_left > 0:
            rate_per_sec = batch.get("rate_per_sec", 0) or 0
            if rate_per_sec <= 0:
                rph = packaging_rate_per_hour(cur)
                rate_per_sec = (rph / 3600.0) if rph > 0 else 0.0
            remaining_sec += files_left / rate_per_sec if rate_per_sec > 0 else files_left * 4.0

    if not pipeline["deployed_size"]:
        remaining_sec += STEP_DEPLOY_EST_SEC

    return remaining_sec


# Smart ETA calibration: track snapshots so we can compute a sliding-window
# burn rate that adapts faster than the log-save-derived `rate_per_min`.
_eta_snapshots = []          # list of (epoch_seconds, items_remaining)
_ETA_WINDOW_SEC  = 900       # 15-minute window for slope estimation
_ETA_MIN_WINDOW  = 90        # need at least 90s of data before we trust the slope
_phase3_seen_prev = False    # tracks the Phase-3-marker transition between refreshes


def _calibrated_eta_sec(eta_struct, trans_state):
    """Return the most accurate wall-time ETA we can compute.

    Order of preference:
      1. Sliding-window items/sec from monitor snapshots (most reactive).
         Snapshots are reset on the Phase-2→Phase-3 transition so the Phase 2
         instant burst (TM + fast-track) doesn't poison the slope.
      2. trans_state['rate_per_min'] from log save checkpoints (most stable).
      3. Static SECS_PER_BATCH × batches / workers formula (cold-start fallback).
    """
    global _phase3_seen_prev

    if not eta_struct:
        return None, "n/a"
    items_remaining = eta_struct["lm_items"] + eta_struct["tm_skipped"] + eta_struct["ft_skipped"]
    if items_remaining <= 0:
        return 0.0, "completed"

    # Phase 3 transition: when we first observe the marker, drop all snapshots
    # so the slope is recomputed from Phase 3 onward only.
    phase3_now = bool(trans_state and trans_state.get("phase3_seen"))
    if phase3_now and not _phase3_seen_prev:
        _eta_snapshots.clear()
    _phase3_seen_prev = phase3_now

    now_ts = time.time()
    _eta_snapshots.append((now_ts, items_remaining))
    # Prune snapshots older than the window (but always keep at least 2).
    cutoff = now_ts - _ETA_WINDOW_SEC
    while len(_eta_snapshots) > 2 and _eta_snapshots[0][0] < cutoff:
        _eta_snapshots.pop(0)

    # 1) Try sliding-window slope
    if len(_eta_snapshots) >= 2:
        oldest_ts, oldest_remaining = _eta_snapshots[0]
        elapsed = now_ts - oldest_ts
        consumed = oldest_remaining - items_remaining
        if elapsed >= _ETA_MIN_WINDOW and consumed > 0:
            rate_per_sec = consumed / elapsed
            return items_remaining / rate_per_sec, f"window {int(elapsed/60)}m, {consumed/elapsed*60:.1f}/min"

    # 2) Fall back to log-derived save-checkpoint rate
    rpm = trans_state.get("rate_per_min", 0) if trans_state else 0
    if rpm and rpm > 0:
        return items_remaining / (rpm / 60.0), f"log rate {rpm:.1f}/min"

    # 3) Final fallback: static structural profile
    static = (eta_struct["batches"] * SECS_PER_BATCH) / max(PARALLEL_WORKERS, 1)
    return static, f"static {SECS_PER_BATCH}s × batch / {PARALLEL_WORKERS} workers"


# ── render ────────────────────────────────────────────────────────────────────
WIDTH = 78


def _section(title, color=""):
    """Print a section divider + colored title."""
    print(C.GRAY + ("─" * WIDTH) + C.RESET)
    print(f"  {color}{title}{C.RESET}")
    print(C.GRAY + ("─" * WIDTH) + C.RESET)


def _bar(done, total, width=50, color=""):
    pct = (done / total * 100) if total else 0.0
    filled = int(width * done / max(total or 1, 1))
    return f"{color}{'█' * filled}{C.GRAY}{'░' * (width - filled)}{C.RESET}", pct


def _status(complete, active):
    """Return (icon, color) tuple matching the section's state."""
    if complete:
        return ("✓", C.GREEN)
    if active:
        return ("⏵", C.YELLOW)
    return ("·", C.GRAY)


def render():
    pipeline = parse_pipeline_state()
    reex = parse_reextract_state()
    trans = parse_translation_state()
    batch = parse_batch_state()
    activity = get_recent_activity()
    total_eta_sec = compute_total_eta(reex, trans, batch, pipeline)

    now = datetime.now()
    uptime = ""
    if pipeline["started_at"]:
        uptime = fmt_duration((now - pipeline["started_at"]).total_seconds())

    unified = detect_unified_phase(trans)
    if pipeline["complete"] or unified == "idle":
        phase_label = H("הושלם")
    elif not reex["complete"]:
        phase_label = H("שלב 1 — חילוץ וסידור כתוביות")
    elif unified == "translation":
        phase_label = H("שלב 2 — תרגום LM Studio")
    elif unified == "packaging":
        phase_label = H("שלב 3 — אריזת CR2W ופריסה")
    else:
        phase_label = H("מאתחל...")

    # ─── HEADER ───
    print(C.CYAN + ("═" * WIDTH) + C.RESET)
    print(
        f"  {C.BOLD}{C.WHITE}{H('תרגום סייברפאנק 7702 לעברית — מסך מעקב חי')}{C.RESET}"
    )
    print(
        f"  {now:%Y-%m-%d  %H:%M:%S}    "
        f"{H('זמן ריצה')}: {C.CYAN}{uptime or '—'}{C.RESET}    "
        f"{H('שניות')} {REFRESH_SEC} {H('רענון כל')}"
    )
    # Unified phase indicator — left-aligned LTR English for unambiguous parsing
    unified_phase = detect_unified_phase(trans)
    if unified_phase == "translation":
        fixed = trans.get("fixed", 0) or 0
        total = trans.get("fields_needed") or 0
        phase_color = C.YELLOW
        phase_status = f"[PHASE: TRANSLATION]  {fixed:,} / {total:,} lines"
    elif unified_phase == "packaging":
        cur = count_subtitle_cr2w()
        phase_color = C.MAGENTA
        phase_status = f"[PHASE: PACKAGING]  {cur:,} / {SUBTITLE_DIR_TOTAL:,} files"
    else:
        phase_color = C.GREEN
        phase_status = f"[PHASE: IDLE]  {SUBTITLE_DIR_TOTAL:,} / {SUBTITLE_DIR_TOTAL:,} files (complete)"
    print(f"  {C.BOLD}{phase_color}{phase_status}{C.RESET}")
    print(C.CYAN + ("═" * WIDTH) + C.RESET)

    # ─── OVERALL SUMMARY ───
    print(f"◆ {H('סיכום כללי')}", C.BLUE)
    print(C.GRAY + ("─" * WIDTH) + C.RESET)
    if total_eta_sec is None:
        print(f"   {H('זמן משוער לסיום')}:        {C.GREEN}✓ {H('הסתיים')}{C.RESET}")
    else:
        print(
            f"   {H('זמן משוער לסיום')}:        {C.MAGENTA}{fmt_duration(total_eta_sec)}{C.RESET}"
        )
    print(f"   {H('שלב נוכחי')}:              {C.YELLOW}{phase_label}{C.RESET}")
    print()

    # ─── STEP 1 ───
    s1_icon, s1_color = _status(
        reex["complete"], not reex["complete"] and reex["phase2_started"]
    )
    _section(f"{s1_icon} {H('שלב 1 — חילוץ וסידור כתוביות')}", s1_color)
    if reex["complete"]:
        print(
            f"   {C.GREEN}✓ {H('הסתיים')}{C.RESET} — {C.BOLD}{reex['file_count']:,}/{REEXTRACT_TOTAL:,}{C.RESET} {H('קבצים')}"
        )
    elif reex["phase2_started"] or reex["file_count"] > 0:
        done = max(reex["file_count"], reex["done_log"])
        total = reex["total"]
        bar, pct = _bar(done, total, color=C.YELLOW)
        print(f"   [{bar}] {C.CYAN}{pct:5.1f}%{C.RESET}")
        print(
            f"   {H('קבצים (דיסק)')}: {C.BOLD}{reex['file_count']:>5,}{C.RESET}/{total:,}      "
            f"{H('לוג')}: {reex['done_log']:>5,}/{total:,}      "
            f"{H('נכשלו')}: {C.RED if reex['failed'] else C.GRAY}{reex['failed']}{C.RESET}"
        )
        if reex["rate_per_sec"] > 0:
            eta_sec = (total - done) / reex["rate_per_sec"]
            print(
                f"   {H('קצב')}: {reex['rate_per_sec']:.2f} {H('קבצים/שנ')}      "
                f"{H('זמן משוער לסיום שלב')}: {C.MAGENTA}{fmt_duration(eta_sec)}{C.RESET}"
            )
        elif reex["file_count"] > 0:
            print(
                f"   {H('זמן משוער לסיום שלב')} ({H('הערכה')}): {fmt_duration((total - reex['file_count']) / 0.08)}"
            )
    else:
        print(f"   ({H('ממתין להתחלה')})")

    # ─── STEP 2 ───
    log_trans_exists = os.path.exists(LOG_TRANS)
    s2_active = (
        reex["complete"]
        and (trans["fixed"] > 0 or (trans.get("fields_needed") or 0) > 0)
        and not trans["step_done_min"]
    )
    s2_icon, s2_color = _status(bool(trans["step_done_min"]), s2_active)
    _section(f"{s2_icon} {H('שלב 2 — תרגום LM Studio')}", s2_color)

    if not reex["complete"]:
        print(f"   ({H('ממתין לסיום שלב 1')})")
    elif trans.get("skipped_step"):
        print(f"   ({H('הסתיים בריצה קודמת')})")
    else:
        if trans["fields_needed"] is None and log_trans_exists:
            print(f"   ({H('טוען נתונים — ממתין לסריקה...')})")
        elif trans["fields_needed"] == 0 and log_trans_exists:
            print(
                f"   {C.RED}⚠ {H('אזהרה')}{C.RESET}: {H('ריצה קודמת מצאה 0 שדות — יש להריץ מחדש את הסקריפט')}"
            )
            print(
                f"     python cp2077_fix_missing_translations.py > fix_missing_translations.log 2>&1"
            )
        elif not log_trans_exists:
            print(f"   ({H('ממתין להתחלה')})")

        if trans["fixed"]:
            bar, pct = _bar(trans["fixed"], trans["fields_needed"] or 1, color=C.GREEN)
            print(f"   [{bar}] {C.CYAN}{pct:5.1f}%{C.RESET}")
            print()
            print(
                f"   {H('סה\"כ לתרגום')}:            {C.BOLD}{trans['fields_needed']:>9,}{C.RESET}"
            )
            print(
                f"   {H('תוקן עד כה')}:             {C.GREEN}{trans['fixed']:>9,}{C.RESET}"
            )
            print(
                f"   {H('נותר (מהקצב הנוכחי)')}:    ~{C.YELLOW}{trans['remaining']:>8,}{C.RESET}"
            )
            skip_col = C.RED if trans["skipped"] > 100 else C.GRAY
            print(
                f"   {H('דילוגים קבועים')}:         {skip_col}{trans['skipped']:>9,}{C.RESET}"
            )
            if trans.get("elapsed_sec"):
                print(
                    f"   {H('זמן בפעולה')}:             {C.CYAN}{fmt_duration(trans['elapsed_sec']):>9}{C.RESET}"
                )
            if trans.get("rate_per_min"):
                rpm = trans["rate_per_min"]
                print(
                    f"   {H('קצב נמדד')}:               {rpm:>6.1f} {H('ערכים בדקה')}"
                )
                if rpm > 0 and trans.get("remaining"):
                    eta_rate = fmt_duration(trans["remaining"] / rpm * 60)
                    print(
                        f"   {H('זמן משוער (לפי קצב)')}:    {C.GRAY}{eta_rate:>9}{C.RESET}"
                    )
            try:
                eta = compute_smart_eta()
                if eta:
                    eta_sec, eta_source = _calibrated_eta_sec(eta, trans)
                    finish_dt = datetime.now() + timedelta(seconds=eta_sec or 0)
                    print()
                    print(
                        f"   {C.MAGENTA}⏱  Smart ETA — {H('זמן משוער חכם')}: {C.BOLD}{C.GREEN}{fmt_duration(eta_sec)}{C.RESET}"
                    )
                    print(
                        f"      {H('סיום צפוי')}: {C.BOLD}{C.WHITE}{finish_dt:%Y-%m-%d %H:%M}{C.RESET}"
                    )
                    print(
                        f"      {C.DIM}({H('מקור הקצב')}: {eta_source}){C.RESET}"
                    )
                    # Also keep the static structural ETA visible for sanity check
                    static_sec = (eta["batches"] * SECS_PER_BATCH) / max(PARALLEL_WORKERS, 1)
                    print(
                        f"      {C.DIM}{H('הערכה סטטית')} ({eta['batches']:,} {H('אצוות')} × {SECS_PER_BATCH}{H('שנ׳')} / {PARALLEL_WORKERS}): {fmt_duration(static_sec)}{C.RESET}"
                    )
                    print()
                    print(f"   {H('פירוט עומס עבודה')}:")
                    print(
                        f"      {C.YELLOW}{H('דרך LM Studio')}{C.RESET}:        {C.BOLD}{eta['lm_items']:>9,}{C.RESET}"
                    )
                    print(
                        f"      {C.CYAN}{H('מטמון תרגום (TM)')}{C.RESET}:     {eta['tm_skipped']:>9,}"
                    )
                    print(
                        f"      {C.CYAN}{H('מילון מהיר (FT)')}{C.RESET}:      {eta['ft_skipped']:>9,}"
                    )
                    print(
                        f"      {C.GREEN}{H('תורגם תקין כבר')}{C.RESET}:       {eta['already_done']:>9,}"
                    )
            except Exception as e:
                print(f"   Smart ETA: ({H('שגיאה')}: {e})")
        elif trans["fields_needed"] and trans["fields_needed"] > 0:
            print(
                f"   {H('סה\"כ לתרגום')}: {C.BOLD}{trans['fields_needed']:,}{C.RESET}"
            )
            print(f"   ({H('סורק — ממתין לתרגום הראשון...')})")

        if trans["step_done_min"]:
            print(
                f"   {C.GREEN}✓ {H('הסתיים תוך')} {trans['step_done_min']:.1f} {H('דקות')}{C.RESET}"
            )
    print()

    # ─── STEP 3 ───
    s3_active = batch["started"] and not batch["step_done_min"]
    s3_icon, s3_color = _status(bool(pipeline["deployed_size"]), s3_active)
    _section(f"{s3_icon} {H('שלב 3 — עיבוד WolvenKit + פריסה')}", s3_color)
    if batch["started"]:
        if batch["processing_total"]:
            bar, pct = _bar(
                batch["current_idx"], batch["processing_total"], color=C.YELLOW
            )
            print(f"   [{bar}] {C.CYAN}{pct:5.1f}%{C.RESET}")
            print(
                f"   {H('מעבד')}: {C.BOLD}{batch['current_idx']:>5,}{C.RESET}/{batch['processing_total']:,}"
            )
        print(
            f"   {H('עובדו')}: {C.GREEN}{batch['processed']:>5,}{C.RESET}      "
            f"{H('דולגו')}: {batch['skipped']:>5,}      "
            f"{H('נכשלו')}: {C.RED if batch['failed'] else C.GRAY}{batch['failed']:>4}{C.RESET}"
        )
        if batch["rate_per_sec"] > 0:
            print(
                f"   {H('קצב')}: {batch['rate_per_sec']:5.2f} {H('קבצים/שנ')}      "
                f"{H('זמן משוער')}: {C.MAGENTA}{batch['eta_h']:5.2f} {H('שעות')}{C.RESET}"
            )
        if batch["step_done_min"]:
            print(
                f"   {C.GREEN}✓ {H('הסתיים תוך')} {batch['step_done_min']:.1f} {H('דקות')}{C.RESET}"
            )
    elif pipeline["deployed_size"]:
        mb = pipeline["deployed_size"] / 1024 / 1024
        print(
            f"   {C.GREEN}✓ {H('נפרס')}{C.RESET}: {C.BOLD}{pipeline['deployed_size']:,}{C.RESET} {H('בתים')}  ({mb:.2f} MB)"
        )
    else:
        print(f"   ({H('ממתין לסיום שלב 2')})")

    if pipeline["complete"] and pipeline["complete_total_min"]:
        print(
            f"  {C.BOLD}{C.GREEN}★  {H('התהליך הסתיים תוך')} {pipeline['complete_total_min']:.1f} {H('דקות')}  ★{C.RESET}"
        )
        print()

    # ─── RECENT ACTIVITY ───
    if activity:
        _section(f"◇ {H('פעילות אחרונה')}", C.CYAN)
        for line in activity:
            print(f"   {C.DIM}{fix_rtl(line)}{C.RESET}")

    print(C.CYAN + ("═" * WIDTH) + C.RESET)


def push_stats_to_vercel(phase, processed, total, rate_per_hour):
    """Push the current snapshot to /api/admin/progress via monitor_push.

    Replaces the legacy Upstash 'translation_stats' single-key write. The
    new endpoint stores per-game rows in Supabase, so multiple games can
    have live progress simultaneously and admins can edit each from the
    /admin UI.

    Phase-aware unit selection so the dashboard reads sensibly:
       extraction / packaging → "קבצים"
       translation             → "שורות"
       idle                    → "קבצים" (terminal subtitle count)
    """
    try:
        import monitor_push                       # local helper
    except ImportError:
        print("[!] monitor_push module unavailable — live sync skipped")
        return
    unit = monitor_push.DEFAULT_UNITS_HE.get(phase, "פריטים")
    monitor_push.push_progress(
        game_id="cyberpunk",
        phase=phase,
        processed=int(processed or 0),
        total=int(total or 0),
        rate_per_hour=float(rate_per_hour or 0),
        unit=unit,
        gpu_model="AMD Radeon RX 9070 16GB",
        ai_model="Gemma-2 27B",
        # phase_label_he=None ⇒ frontend picks the default Hebrew label
        # ("שליפת נתונים" / "תרגום נתונים" / "אריזת נתונים") from the
        # shared mapping. Admins can override per game via the panel.
    )


def main():
    global _last_push_time
    try:
        while True:
            clear_screen()
            try:
                render()
            except Exception as e:
                print(f"render error: {e}")
            # Throttled live sync to /api/admin/progress (every PUSH_INTERVAL_SEC).
            if time.time() - _last_push_time >= PUSH_INTERVAL_SEC:
                trans = parse_translation_state()
                reex  = parse_reextract_state()
                phase = detect_unified_phase(trans, reex)
                if phase == "extraction":
                    # WolvenKit unbundle/serialize counts in files. `file_count`
                    # is the real-time disk tally; `total` is REEXTRACT_TOTAL
                    # (3,085 subtitle CR2Ws). Convert files/sec → files/hour.
                    cur   = int(reex.get("file_count") or 0)
                    total = int(reex.get("total") or REEXTRACT_TOTAL)
                    rate  = float(reex.get("rate_per_sec") or 0) * 3600
                    push_stats_to_vercel(phase, cur, total, rate)
                elif phase == "translation":
                    fixed = trans.get("fixed", 0) or 0
                    remaining = trans.get("remaining", 0) or 0
                    total = (fixed + remaining) if (fixed or remaining) else (trans.get("fields_needed") or 0)
                    rate_per_hour = (trans.get("rate_per_min", 0) or 0) * 60
                    push_stats_to_vercel(phase, fixed, total, rate_per_hour)
                elif phase == "packaging":
                    cur = count_subtitle_cr2w()
                    rate = packaging_rate_per_hour(cur)
                    push_stats_to_vercel(phase, cur, SUBTITLE_DIR_TOTAL, rate)
                else:  # idle / fully done
                    push_stats_to_vercel(phase, SUBTITLE_DIR_TOTAL, SUBTITLE_DIR_TOTAL, 0)
                _last_push_time = time.time()
            time.sleep(REFRESH_SEC)
    except KeyboardInterrupt:
        print("\nMonitor stopped.")


if __name__ == "__main__":
    main()
