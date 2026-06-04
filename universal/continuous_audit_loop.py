"""
continuous_audit_loop.py
========================
Autonomous LQA loop for the Hebrew translation corpus, hardened with
the Safety & Autonomy protocol below.

SAFETY & AUTONOMY PROTOCOL
--------------------------
1. READ-ONLY AUDIT.
   Source translation JSONs are listed in PROTECTED_FILES. Every write
   this script performs first passes through _safe_write_check();
   any attempt to write a protected source — or anywhere outside the
   project root — invokes _critical_safety_stop() which prints a
   CRITICAL_SAFETY_STOP marker on stderr and exits with code 99.
   The script's only writes are: cross_audit_batch.json (via the
   subprocess), the per-batch _tmp_flags_*.json temp file, and the
   sidecars get_next_audit_batch.py manages (flags JSONL, checkpoint,
   dashboard). No source translation file is ever opened by this
   process.

2. SELF-HEALING.
   * Connection failures to LM Studio → 30 s pause, INFINITE retry
     until the API responds. Holds true at preflight, on the per-row
     judge call, and on the subprocess fetch.
   * Empty / malformed responses or non-connection judge errors →
     30 s pause, up to MAX_BAD_RESPONSE_RETRIES attempts, then the row
     is skipped (so a single poison-pill row can't trap the loop).
   * 4xx BadRequestError → not retried (config / code bug — retrying
     can't help). Row skipped, run continues.
   * Logic error / crash inside a batch's processing → flush whatever
     flags we have, 30 s pause, restart the SAME in-memory batch from
     row 0, up to MAX_BATCH_RESTARTS times. After that, the batch is
     abandoned and the loop continues with the next one.

3. CAUTIONARY PRINCIPLE.
   Before any FS write, _safe_write_check() asks "would the user
   allow this?" — the answer is yes only for project-root paths that
   are not in PROTECTED_FILES. Anything else triggers
   CRITICAL_SAFETY_STOP. Logging (stderr/stdout) is exempt — it's
   non-destructive by construction.

4. AUTONOMY.
   No user prompts, no input() calls, no approval pauses. Every error
   class above is handled in-code. Ctrl+C is the only escape hatch
   and it triggers a clean exit after the in-flight row finishes.

5. SINGLE INSTANCE.
   On startup the script creates `audit.lock` atomically with its own
   PID inside. If the file already exists AND its PID is still alive,
   it refuses to start with `ERROR: Audit is already running!`. Stale
   locks (from a crashed previous run) are detected and reclaimed.
   The lock is removed on clean exit via atexit; a hard-kill leaves
   it behind but the next launch recognises it as stale via the PID
   check.

JUDGE
-----
Qwen 2.5 32B Instruct running locally on LM Studio at
http://10.0.0.5:1234. System prompt: Lead LQA Editor — "be concise,
default PASS, only flag real bugs / stilted phrasing".

WHAT IT DOES (per cycle)
------------------------
1. `get_next_audit_batch.py next --size N` → fetch N rows, advance the
   checkpoint atomically.
2. For each row, send (english, hebrew) to LM Studio. PASS → skip.
   FAIL → collect into the per-batch flag buffer.
3. `get_next_audit_batch.py flag --file <tmp>` → JSONL-append the
   flags and refresh `cross_audit_dashboard.md`.
4. Loop until the corpus is exhausted or Ctrl+C.

SETUP
-----
  In LM Studio (host 10.0.0.5) load model id:  qwen2.5-32b-instruct
  pip install openai
  python continuous_audit_loop.py --limit 100      # sanity test
  python continuous_audit_loop.py                  # full corpus
"""
from __future__ import annotations

import argparse
import atexit
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
import traceback

try:
    import openai as _openai_mod
    from openai import OpenAI
except ImportError:
    print("FATAL: openai SDK not installed. Run: pip install openai",
          file=sys.stderr)
    sys.exit(2)


# ── paths + LM Studio config ────────────────────────────────────────────────
HERE         = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)        # universal/ → project root
BATCH_SCRIPT = os.path.join(HERE, "get_next_audit_batch.py")
BATCH_FILE   = os.path.join(HERE, "cross_audit_batch.json")
LOCK_FILE    = os.path.join(HERE, "audit.lock")
LOG_FILE     = os.path.join(HERE, "audit.log")


def _log(msg: str) -> None:
    """Always emit to the rolling on-disk log alongside any stdout print.
    The supervisor's stdout can be lost when the user closes their terminal
    or after a reboot; the file persists across both, so any future crash
    has a tail you can read instead of asking the user 'what did it say?'."""
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{ts}] {msg}\n")
    except OSError:
        pass

LM_URL          = "http://127.0.0.1:1234/v1"
DEFAULT_MODEL   = "qwen2.5-32b-instruct"
REQUEST_TIMEOUT = 90.0      # seconds — 32B model needs depth to think
RETRY_SLEEP     = 30.0      # seconds — uniform backoff per spec

MAX_BATCH_RESTARTS       = 5    # restart a crashed batch this many times
MAX_BAD_RESPONSE_RETRIES = 3    # retry a single row this many times for
                                # non-connection errors before skipping it


# ── SAFETY: protected source files + write gate ─────────────────────────────
def _abs(p: str) -> str:
    return os.path.abspath(p)


PROJECT_ROOT_ABS = _abs(PROJECT_ROOT)

PROTECTED_FILES = frozenset(
    _abs(os.path.join(PROJECT_ROOT, "תרגום_משחקים", "source", "resources", n))
    for n in (
        "localization_translated.json",   # base game Hebrew spine
        "localization_export.json",       # base game English source
        "dlc_ep1_translated.json",        # Phantom Liberty Hebrew spine
        "dlc_ep1_text.json",              # Phantom Liberty English source
    )
)


def _critical_safety_stop(reason: str) -> None:
    """Emit a loud CRITICAL_SAFETY_STOP marker and exit code 99.
    Called whenever a write target violates the safety policy."""
    msg = (
        "\n" + ("!" * 72) + "\n"
        "CRITICAL_SAFETY_STOP — refusing to continue.\n"
        f"REASON: {reason}\n"
        + ("!" * 72) + "\n"
    )
    sys.stderr.write(msg)
    sys.stderr.flush()
    sys.exit(99)


def _safe_write_check(path: str) -> None:
    """Refuse any write that targets a PROTECTED_FILES entry OR a path
    outside the project root. Called immediately before every write
    this script performs."""
    abs_path = _abs(path)
    if abs_path in PROTECTED_FILES:
        _critical_safety_stop(
            f"attempted write to protected source translation file: {abs_path}"
        )
    # Allow writes only inside the project root (we don't touch user
    # config dirs, system paths, etc).
    if not (abs_path == PROJECT_ROOT_ABS
            or abs_path.startswith(PROJECT_ROOT_ABS + os.sep)):
        _critical_safety_stop(
            f"attempted write outside project root: {abs_path} "
            f"(root={PROJECT_ROOT_ABS})"
        )


# ── SINGLE-INSTANCE LOCK ────────────────────────────────────────────────────
# Prevents accidentally launching a second concurrent run that would race
# the first on the shared checkpoint / flags / batch files. On startup we
# atomically create `audit.lock` with our PID inside; if the file already
# exists AND its PID is still alive, we refuse to start. Stale locks (from
# a crashed previous run) are detected and reclaimed automatically. The
# lock is removed on clean exit via atexit; release_lock checks ownership
# before deleting so an exit-10 process never wipes someone else's lock.

def _pid_exists(pid: int) -> bool:
    """Cross-platform 'is this PID currently running' check."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32
        h = kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return False
        try:
            code = ctypes.c_ulong()
            kernel32.GetExitCodeProcess(h, ctypes.byref(code))
            return code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(h)
    # POSIX
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def acquire_lock() -> None:
    """Atomically create audit.lock or exit(10) if another live instance
    already holds it. Stale locks (PID dead) are silently reclaimed."""
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r", encoding="utf-8") as f:
                info = json.load(f)
            other_pid = int(info.get("pid", 0))
        except (OSError, ValueError):
            info = {}
            other_pid = 0

        if other_pid and _pid_exists(other_pid):
            print(f"ERROR: Audit is already running!  "
                  f"(PID {other_pid}, started "
                  f"{info.get('started_at', 'unknown')})",
                  file=sys.stderr)
            print(f"       Stop that instance first. If you are SURE no "
                  f"python continuous_audit_loop is running, delete:\n"
                  f"       {LOCK_FILE}", file=sys.stderr)
            sys.exit(10)

        print(f"[*] Stale lock detected (PID {other_pid or '?'} not "
              f"alive) — reclaiming.", flush=True)
        try:
            os.unlink(LOCK_FILE)
        except OSError:
            pass

    # Atomic create: O_EXCL fails if the file appeared between our check
    # above and now (i.e. a second process raced us in this tiny window).
    try:
        fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        print("ERROR: Audit is already running! "
              "(another process grabbed the lock concurrently)",
              file=sys.stderr)
        sys.exit(10)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({
            "pid": os.getpid(),
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "host": os.environ.get("COMPUTERNAME", "unknown"),
        }, f)
    print(f"[*] Acquired audit.lock (PID {os.getpid()}).", flush=True)


def release_lock() -> None:
    """Delete audit.lock — but ONLY if it's still ours. Idempotent."""
    try:
        if not os.path.exists(LOCK_FILE):
            return
        try:
            with open(LOCK_FILE, "r", encoding="utf-8") as f:
                info = json.load(f)
            if int(info.get("pid", 0)) != os.getpid():
                return                  # someone else's lock — leave alone
        except (OSError, ValueError):
            pass                        # corrupt — fall through and delete
        os.unlink(LOCK_FILE)
    except OSError:
        pass


# ── LQA judge prompt — Lead LQA Editor, "be concise, default PASS" ─────────
JUDGE_SYSTEM = (
    "You are a Lead LQA Editor for the Hebrew localization of "
    "Cyberpunk 2077.\n\n"
    "Evaluate each Hebrew translation against its English source with "
    "deep linguistic reasoning across three axes:\n"
    "1. NATURALNESS — does it read like native, idiomatic Hebrew to an "
    "Israeli gamer? Or stiff / literal / machine-translated?\n"
    "2. CYBERPUNK REGISTER — does it match the source's tone (street-gang "
    "slang, corporate tech-speak, Silverhand punk attitude, ripperdoc "
    "clinical, fixer cool), or is it neutralised?\n"
    "3. INTEGRITY — any hidden truncation (dangling ו/ב/ל/מ/ש/כ/של/את "
    "with English content continuing past), broken punctuation, mangled "
    "tags (<Rich>, <kiroshi>, {VALUE,...}, %s), or foreign-script "
    "contamination (Cyrillic / Arabic / Thai / CJK / Hangul)?\n\n"
    "DO NOT flag:\n"
    "- Single-word translations or transliterations of proper nouns / "
    "brand names ('Grill' → 'גריל', 'Arasaka' → 'אראסאקה').\n"
    "- Brand names, acronyms, codes, or the protagonist's name 'V' kept "
    "in Latin script (V, NCPD, Mk.31, HDR10).\n"
    "- Hebrew parentheticals like 'מיכל דלק (מתפוצץ)' — parentheses are "
    "valid Hebrew syntax; do NOT claim data is missing.\n"
    "- Translations you would phrase differently but that accurately "
    "convey the English meaning.\n\n"
    "BE CONCISE. If the translation is good, just output PASS. Only if "
    "there is a real bug or stilted phrasing, output your critique and "
    "a better Hebrew alternative.\n\n"
    "STRICT LANGUAGE — non-negotiable: You MUST respond ONLY in Hebrew "
    "and English. Any output containing Arabic, Russian / Cyrillic, "
    "Chinese / Japanese / Korean, Thai, Devanagari, Greek, Armenian, or "
    "any other non-Hebrew / non-English script is a CRITICAL FAILURE — "
    "the post-processor will discard such flags entirely, so the row "
    "gets no review. Your suggested Hebrew alternative must contain "
    "ONLY Hebrew letters, Latin letters where appropriate (brand names, "
    "the protagonist's name 'V'), digits, and standard punctuation. "
    "If you cannot give a clean Hebrew suggestion, reply PASS.\n\n"
    "OUTPUT FORMAT — EXACTLY one of these, nothing else:\n"
    "  PASS\n"
    "  FAIL: <one short critique>; SUGGEST: <better Hebrew alternative>\n\n"
    "No preamble. No reasoning shown. When in doubt, reply PASS. All "
    "suggestions are advisory — the source JSONs are NEVER modified."
)


# ── Ctrl+C handler ──────────────────────────────────────────────────────────
_STOP = False


def _on_sigint(_sig, _frm):
    global _STOP
    _STOP = True
    print("\n[!] Ctrl+C — finishing current row then exiting cleanly...",
          flush=True)


# ── small helpers ───────────────────────────────────────────────────────────
def _is_connection_error(e: Exception) -> bool:
    """Detect 'LM Studio unreachable' style errors — these warrant
    infinite retry per the Self-Healing rule."""
    if isinstance(e, (
        _openai_mod.APIConnectionError,
        _openai_mod.APITimeoutError,
    )):
        return True
    s = (str(e) or "").lower()
    return any(t in s for t in (
        "connection", "timeout", "timed out", "refused", "unreachable",
        "remote end closed", "name or service not known", "no route to host",
        "broken pipe",
    ))


def _sleep_interruptible(secs: float) -> None:
    """Sleep but wake every second to check _STOP so Ctrl+C exits promptly."""
    deadline = time.time() + secs
    while not _STOP:
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        time.sleep(min(1.0, remaining))


# ── language guard: reject judge outputs with forbidden scripts, emojis, ──
#    or mixed-script words (Hebrew letters welded to Latin in one token). ──
#
# Three rejection categories:
#   1. Foreign script chars (Arabic, Cyrillic, CJK, Hangul, ...) — full
#      cross-script hallucination.
#   2. Emoji / pictograph symbols — 🎯 etc. added to a Hebrew suggestion.
#   3. Mixed-script words — Hebrew + ASCII Latin glued into one token,
#      e.g. 'בworty', 'נפilling', 'אxygen'. Strong signal the judge
#      token-merged across scripts mid-word.
#
FORBIDDEN_SCRIPT_RE = re.compile(
    "["
    "؀-ۿ"    # Arabic
    "ݐ-ݿ"    # Arabic Supplement
    "ﭐ-﷿"    # Arabic Presentation Forms-A
    "ﹰ-﻿"    # Arabic Presentation Forms-B
    "Ѐ-ӿ"    # Cyrillic
    "Ԁ-ԯ"    # Cyrillic Supplement
    "一-鿿"    # CJK Unified Ideographs
    "　-〿"    # CJK Symbols & Punctuation
    "぀-ゟ"    # Hiragana
    "゠-ヿ"    # Katakana
    "฀-๿"    # Thai
    "가-힯"    # Hangul
    "ऀ-ॿ"    # Devanagari
    "Ͱ-Ͽ"    # Greek
    "԰-֏"    # Armenian
    "]"
)

# Emoji / pictograph blocks — covers 🎯 (U+1F3AF) and the rest of the
# Supplementary Multilingual Plane symbol ranges.
EMOJI_AND_SYMBOL_RE = re.compile(
    "[☀-⛿"                # Miscellaneous Symbols
    "✀-➿"                 # Dingbats
    "\U0001F300-\U0001FAFF]"        # Supplemental Symbols & Pictographs etc.
)

# Word tokenizer for the mixed-script check. Python 3 `\w` is Unicode-aware
# by default — Hebrew, Latin, digits all match. So 'בworty' is ONE token,
# while 'אנשי FBI' is two (space is not \w).
_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _find_mixed_script_word(text: str) -> str | None:
    """Return the first word containing BOTH Hebrew and ASCII Latin letters
    inside a single token, or None if no such word exists."""
    for m in _WORD_RE.finditer(text or ""):
        word = m.group(0)
        has_he = any("֐" <= c <= "׿" for c in word)
        has_la = any(c.isascii() and c.isalpha() for c in word)
        if has_he and has_la:
            return word
    return None


def _contains_forbidden_script(text: str) -> str | None:
    """Return short label for the first detected issue, or None if clean.
    Checks in order: forbidden script chars → emoji/symbols → mixed-script
    word. The rejection itself is unconditional — the label is just for the
    log message."""
    text = text or ""
    # 1. Forbidden script ranges
    m = FORBIDDEN_SCRIPT_RE.search(text)
    if m:
        code = ord(m.group(0))
        if 0x0600 <= code <= 0x06FF or 0x0750 <= code <= 0x077F \
                or 0xFB50 <= code <= 0xFDFF or 0xFE70 <= code <= 0xFEFF:
            return "Arabic"
        if 0x0400 <= code <= 0x04FF or 0x0500 <= code <= 0x052F:
            return "Cyrillic"
        if 0x4E00 <= code <= 0x9FFF or 0x3000 <= code <= 0x303F:
            return "CJK"
        if 0x3040 <= code <= 0x309F:
            return "Hiragana"
        if 0x30A0 <= code <= 0x30FF:
            return "Katakana"
        if 0x0E00 <= code <= 0x0E7F:
            return "Thai"
        if 0xAC00 <= code <= 0xD7AF:
            return "Hangul"
        if 0x0900 <= code <= 0x097F:
            return "Devanagari"
        if 0x0370 <= code <= 0x03FF:
            return "Greek"
        if 0x0530 <= code <= 0x058F:
            return "Armenian"
        return f"U+{code:04X}"
    # 2. Emoji / pictograph symbols
    m = EMOJI_AND_SYMBOL_RE.search(text)
    if m:
        return f"Emoji U+{ord(m.group(0)):04X}"
    # 3. Mixed-script word — Hebrew + Latin glued in one token
    bad = _find_mixed_script_word(text)
    if bad:
        return f"MixedWord {bad!r}"
    return None


# ── batch I/O via the read-only fetcher subprocess ─────────────────────────
def fetch_next_batch(size: int) -> dict:
    """Calls `get_next_audit_batch.py next` and reads its BATCH_FILE
    output. Raises RuntimeError on subprocess failure — caller handles
    the retry policy."""
    proc = subprocess.run(
        [sys.executable, BATCH_SCRIPT, "next", "--size", str(size)],
        cwd=HERE, capture_output=True, text=True, encoding="utf-8",
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"fetch failed: {proc.stderr.strip() or proc.stdout.strip()}"
        )
    with open(BATCH_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def flush_flags(flags: list[dict]) -> None:
    """Persist a batch's flags via the read-only fetcher script.
    Goes through _safe_write_check before touching anything on disk."""
    if not flags:
        return
    fd, tmp = tempfile.mkstemp(suffix=".json", prefix="_tmp_flags_", dir=HERE)
    _safe_write_check(tmp)            # confirms tmp is inside project root
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(flags, f, ensure_ascii=False)
        proc = subprocess.run(
            [sys.executable, BATCH_SCRIPT, "flag", "--file", tmp],
            cwd=HERE, capture_output=True, text=True, encoding="utf-8",
        )
        if proc.returncode != 0:
            print(f"  [flag-err] {proc.stderr.strip() or proc.stdout.strip()}",
                  flush=True)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


# ── per-row judge call ──────────────────────────────────────────────────────
def judge_row(client: OpenAI, model: str, row: dict) -> dict | None:
    """Returns flag-record dict for FAIL, None for PASS (or skipped row).

    Self-healing policy:
      * Connection / availability error → 30 s pause, INFINITE retry.
      * 4xx BadRequestError             → log and skip (retrying doesn't help).
      * Other error or empty response   → 30 s pause, up to
                                          MAX_BAD_RESPONSE_RETRIES tries,
                                          then skip.
    """
    user = (
        f"ENGLISH:\n{row['english']}\n\n"
        f"HEBREW:\n{row['hebrew']}\n\n"
        f"Reply with PASS or FAIL: <critique>; SUGGEST: <alternative>."
    )

    bad_attempts = 0
    text = ""

    while not _STOP:
        try:
            resp = client.chat.completions.create(
                model=model,
                temperature=0.0,            # fully deterministic — kill hallucination
                max_tokens=300,
                timeout=REQUEST_TIMEOUT,
                messages=[
                    {"role": "system", "content": JUDGE_SYSTEM},
                    {"role": "user",   "content": user},
                ],
            )
            text = (resp.choices[0].message.content or "").strip()
            if text:
                break
            # Empty response — count as bad, may exhaust budget.
            bad_attempts += 1
            if bad_attempts >= MAX_BAD_RESPONSE_RETRIES:
                print(f"  [judge-warn] pk={row.get('pk')}: empty response "
                      f"after {bad_attempts} tries — skipping row",
                      flush=True)
                return None
            print(f"  [judge-warn] pk={row.get('pk')}: empty response, "
                  f"sleeping {RETRY_SLEEP:.0f}s "
                  f"(attempt {bad_attempts + 1}/"
                  f"{MAX_BAD_RESPONSE_RETRIES})", flush=True)
            _sleep_interruptible(RETRY_SLEEP)
        except _openai_mod.BadRequestError as e:
            # 4xx is a code/config bug — retrying won't help.
            print(f"  [client-err] pk={row.get('pk')}: {e} — skipping row "
                  f"(retry skipped: 4xx won't recover)", flush=True)
            return None
        except _openai_mod.APITimeoutError as e:
            # Per-request timeout: server IS up, but THIS row is slow
            # (e.g. Qwen got into a long generation on a hard prompt).
            # NOT infinite retry — that wastes minutes per stuck row.
            bad_attempts += 1
            if bad_attempts >= MAX_BAD_RESPONSE_RETRIES:
                print(f"  [timeout-skip] pk={row.get('pk')}: request timed "
                      f"out {bad_attempts} times — skipping row "
                      f"(server is up, this prompt is genuinely slow)",
                      flush=True)
                return None
            print(f"  [timeout] pk={row.get('pk')}: request timed out — "
                  f"sleeping {RETRY_SLEEP:.0f}s, retry "
                  f"{bad_attempts + 1}/{MAX_BAD_RESPONSE_RETRIES}",
                  flush=True)
            _sleep_interruptible(RETRY_SLEEP)
        except Exception as e:                                   # noqa: BLE001
            if _is_connection_error(e):
                # INFINITE retry per Self-Healing rule.
                print(f"  [conn-err] pk={row.get('pk')}: "
                      f"{type(e).__name__}: {e} — sleeping "
                      f"{RETRY_SLEEP:.0f}s, infinite retry until LM Studio "
                      f"responds...", flush=True)
                _sleep_interruptible(RETRY_SLEEP)
                continue
            bad_attempts += 1
            if bad_attempts >= MAX_BAD_RESPONSE_RETRIES:
                print(f"  [judge-err] pk={row.get('pk')}: "
                      f"{type(e).__name__}: {e} — {bad_attempts} attempts "
                      f"failed, skipping row", flush=True)
                return None
            print(f"  [judge-err] pk={row.get('pk')}: "
                  f"{type(e).__name__}: {e} — sleeping "
                  f"{RETRY_SLEEP:.0f}s "
                  f"(attempt {bad_attempts + 1}/"
                  f"{MAX_BAD_RESPONSE_RETRIES})", flush=True)
            _sleep_interruptible(RETRY_SLEEP)

    if _STOP or not text:
        return None

    first = text.splitlines()[0].strip()
    if first.upper().startswith("PASS"):
        return None

    # Language guard: drop the entire flag if the judge hallucinated a
    # forbidden script in either the critique or the SUGGEST. Treating
    # contaminated output as untrustworthy is safer than persisting it.
    bad_script = _contains_forbidden_script(text)
    if bad_script:
        print(f"  [script-reject] pk={row.get('pk')}: {bad_script} "
              f"— discarding flag", flush=True)
        return None

    return {
        "project":         row["project"],
        "section":         row["section"],
        "pk":              row["pk"],
        "field":           row["field"],
        "english":         row["english"],
        "hebrew":          row["hebrew"],
        "critic_feedback": text,
    }


# ── preflight (with infinite reconnect) ────────────────────────────────────
def preflight(client: OpenAI, model: str, lm_url: str) -> int:
    """Returns 0 on success, non-zero exit code on fatal misconfiguration.
    Network unreachability is NOT fatal — we keep retrying until LM Studio
    answers."""
    print("[*] Preflight — pinging LM Studio...", flush=True)
    while not _STOP:
        try:
            pre = client.chat.completions.create(
                model=model,
                temperature=0.0,
                max_tokens=8,
                timeout=REQUEST_TIMEOUT,
                messages=[{"role": "user",
                           "content": "Reply with the word OK."}],
            )
            snippet = (pre.choices[0].message.content or "").strip()[:40]
            print(f"[*] Preflight OK ({snippet!r})", flush=True)
            return 0
        except _openai_mod.BadRequestError as e:
            print(f"FATAL: preflight rejected by LM Studio — {e}",
                  file=sys.stderr)
            print(f"       check that model {model!r} is loaded at {lm_url}",
                  file=sys.stderr)
            return 2
        except Exception as e:                                   # noqa: BLE001
            if not _is_connection_error(e):
                print(f"FATAL: unexpected preflight error — "
                      f"{type(e).__name__}: {e}", file=sys.stderr)
                return 2
            print(f"[conn-err] preflight unreachable: "
                  f"{type(e).__name__}: {e} — sleeping {RETRY_SLEEP:.0f}s, "
                  f"infinite retry...", flush=True)
            _sleep_interruptible(RETRY_SLEEP)
    return 0


# ── main loop ───────────────────────────────────────────────────────────────
def main() -> int:
    signal.signal(signal.SIGINT, _on_sigint)
    # Register cleanup BEFORE acquire_lock so the lock is removed even on
    # any sys.exit() from the acquire path itself.
    atexit.register(release_lock)
    acquire_lock()

    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help=f"LM Studio model id (default: {DEFAULT_MODEL})")
    p.add_argument("--lm-url", default=LM_URL,
                   help=f"LM Studio base URL (default: {LM_URL})")
    p.add_argument("--batch-size", type=int, default=10,
                   help="rows per fetch (default 10)")
    p.add_argument("--limit", type=int, default=0,
                   help="stop after N rows total (0 = unlimited)")
    args = p.parse_args()

    client = OpenAI(
        base_url=args.lm_url,
        api_key="lm-studio",
        timeout=REQUEST_TIMEOUT,
    )

    rc = preflight(client, args.model, args.lm_url)
    if rc != 0 or _STOP:
        return rc

    print(f"[*] Continuous audit loop — model={args.model} "
          f"timeout={REQUEST_TIMEOUT:.0f}s batch={args.batch_size} "
          f"limit={args.limit or 'unlimited'}", flush=True)
    print(f"[*] SAFETY: {len(PROTECTED_FILES)} source JSONs protected; "
          f"writes outside project root blocked.", flush=True)
    print(f"[*] SELF-HEAL: conn-err → {RETRY_SLEEP:.0f}s+infinite | "
          f"batch crash → {RETRY_SLEEP:.0f}s+{MAX_BATCH_RESTARTS} restarts.",
          flush=True)
    print("[*] Ctrl+C to pause; relaunch to resume.", flush=True)

    started = time.time()
    n_processed = 0
    n_flagged = 0

    while not _STOP:
        # ── fetch with infinite retry on subprocess hiccups ──
        batch = None
        fetch_attempt = 0
        while not _STOP and batch is None:
            try:
                batch = fetch_next_batch(args.batch_size)
            except RuntimeError as e:
                fetch_attempt += 1
                print(f"[fetch-err] {e} — sleeping {RETRY_SLEEP:.0f}s "
                      f"(retry #{fetch_attempt})", flush=True)
                _sleep_interruptible(RETRY_SLEEP)
        if _STOP:
            break
        if batch.get("done") or not batch.get("rows"):
            print(f"[*] Corpus exhausted "
                  f"({batch.get('total_rows', 0):,} rows). Done.",
                  flush=True)
            break

        # ── process the batch with restart-on-crash ──
        committed_flags: list[dict] = []
        for attempt in range(MAX_BATCH_RESTARTS):
            if _STOP:
                break
            batch_flags: list[dict] = []
            local_processed = 0
            try:
                for row in batch["rows"]:
                    if _STOP:
                        break
                    if args.limit and (n_processed + local_processed) >= args.limit:
                        break
                    verdict = judge_row(client, args.model, row)
                    local_processed += 1
                    if verdict:
                        batch_flags.append(verdict)
                # batch processed successfully — commit and break
                committed_flags = batch_flags
                n_processed += local_processed
                n_flagged += len(batch_flags)
                break
            except KeyboardInterrupt:
                raise
            except Exception as e:                               # noqa: BLE001
                tb_short = "".join(
                    traceback.format_exception_only(type(e), e)
                ).strip()
                print(f"[batch-err] restart {attempt + 1}/"
                      f"{MAX_BATCH_RESTARTS}: {tb_short}", flush=True)
                # Persist whatever flags we managed to collect pre-crash so
                # they aren't lost across the restart. The next attempt
                # starts fresh from row 0.
                try:
                    flush_flags(batch_flags)
                except Exception as flush_exc:                   # noqa: BLE001
                    print(f"  [flush-err] {flush_exc}", flush=True)
                _sleep_interruptible(RETRY_SLEEP)
        else:
            print(f"[batch-err] {MAX_BATCH_RESTARTS} restarts exhausted — "
                  f"moving on to next batch (this batch's flags lost).",
                  flush=True)

        # ── persist committed flags + refresh dashboard ──
        flush_flags(committed_flags)

        elapsed = max(time.time() - started, 1.0)
        rate = n_processed / elapsed * 60
        fpct = (n_flagged / n_processed * 100) if n_processed else 0.0
        print(f"[ok] {batch['batch_index']:,}..{batch['next_index'] - 1:,} "
              f"| flags this batch: {len(committed_flags)} "
              f"| running: processed={n_processed} flagged={n_flagged} "
              f"({fpct:.1f}%) "
              f"| {rate:.1f} rows/min", flush=True)

        if args.limit and n_processed >= args.limit:
            print(f"[*] --limit {args.limit} reached. Exiting.", flush=True)
            break

    print(f"[*] Exit. Processed {n_processed}, flagged {n_flagged}.",
          flush=True)
    return 0


if __name__ == "__main__":
    # Crash trap. Any unhandled exception lands here, so audit.log carries
    # the full traceback — the supervisor bat reads the exit code and
    # restarts after a backoff.
    _log("[*] audit starting")
    try:
        _code = main()
    except KeyboardInterrupt:
        _log("[*] interrupted by user (Ctrl+C)")
        _code = 0
    except BaseException as _e:                 # noqa: BLE001 — catch everything
        _log(f"[!] unhandled {type(_e).__name__}: {_e}")
        try:
            _log("[!] traceback:\n" + traceback.format_exc())
        except Exception:                       # noqa: BLE001
            pass
        # Re-raise to preserve Python's normal exit-code semantics, but
        # keep the file log intact so the supervisor can inspect it.
        _code = 1
    _log(f"[*] audit exit code={_code}")
    sys.exit(_code)
