#!/usr/bin/env python3
"""Community-translation REPAIR guard-dog — the second safeguard for the
crowdsourced EN→Hebrew pipeline.

The web layer (api/translate.ts) NEVER bounces a contributor with a "you made
an error". Guard dog #1 (server, deterministic) strips niqqud / zero-width junk
and ACCEPTS the submission, flagging anything it couldn't fix as
`auto_qa.needs_repair = true`. This script is guard dog #2: it pulls those
flagged submissions and uses the local LM (LM Studio) to REWRITE the draft into
a valid, structured Hebrew line — same tokens/placeholders, no niqqud, no
foreign script, natural phrasing — then writes it back as `pending` for the
admin to approve. So a messy or even English draft becomes a clean Hebrew line
instead of a rejection.

Mirrors the Universal Playbook §4/§5 watchdog discipline: UTF-8 stdout,
singleton-guarded, crash-protected loop, deterministic post-validation, and a
strike/park cap so an unrepairable row stops looping.

⚠ The LM is SHARED with the SM2/WD2 translators. This guard-dog is LOW priority:
if the model is unresponsive it WAITS and retries — it does NOT force a reload
(which would disrupt a running translator) unless you pass --manage-lm.

Reads SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY from website/.env (service key
bypasses RLS — never log it). LM endpoint + model via env (defaults below).
No third-party deps (urllib only).

Usage:
    python community_qa_watchdog.py --status        # how many need repair
    python community_qa_watchdog.py --once          # one pass over flagged rows
    python community_qa_watchdog.py                 # continuous loop (guard dog)
    python community_qa_watchdog.py --once --game spiderman2 --limit 20
    python community_qa_watchdog.py --manage-lm     # also reload a dead LM (solo)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
WEBSITE = HERE.parent / "website"
LOCK = HERE / "community_qa_watchdog.lock"
LOG = Path(os.environ.get("CT_QA_LOG", r"c:\tmp\community_qa_watchdog.log"))

# LM Studio (OpenAI-compatible). gemma-4 handles short repair well; override via env.
LM_URL   = os.environ.get("CT_QA_LM_URL", "http://localhost:1234/v1/chat/completions")
LM_MODEL = os.environ.get("CT_QA_MODEL", "gemma-4-31b-it")
LM_TIMEOUT = int(os.environ.get("CT_QA_TIMEOUT", "180"))

MAX_STRIKES   = 3          # park a row after this many failed repair attempts
POLL_EMPTY    = 60         # seconds to sleep when nothing needs repair
POLL_LM_DOWN  = 60         # seconds to wait when the shared LM is unresponsive
BATCH_LIMIT   = 25         # rows pulled per pass

# ── token / language validators (MIRROR api/translate.ts autoQa) ──────────────
NIQQUD  = re.compile(r"[֑-ׇ]")
ZW      = re.compile(r"[​-‍﻿]")
FOREIGN = re.compile(r"[؀-ۿЀ-ӿ฀-๿ऀ-ॿ"
                     r"぀-ヿ一-鿿가-힯]")
HEB     = re.compile(r"[א-ת]")
TOKEN   = re.compile(r"\[[A-Z][A-Z_0-9]*\]|\{[A-Z][A-Z_0-9]*\}")
STRIP_FOR_NAME = re.compile(r"\[[^\]]*\]|\{[^}]*\}|<[^>]*>")


def clean_he(s: str) -> str:
    """Deterministic clean — same as guard dog #1 (niqqud + zero-width)."""
    return ZW.sub("", NIQQUD.sub("", s))


def is_name_or_code(source_en: str) -> bool:
    return not re.search(r"[a-z]{2,}", STRIP_FOR_NAME.sub("", source_en))


def validate(source_en: str, he: str) -> list[str]:
    """Return a list of QA error codes ([] = clean). Mirrors the server gate."""
    he = he.strip()
    if not he:
        return ["empty"]
    errs: list[str] = []
    if NIQQUD.search(he):
        errs.append("niqqud")
    if FOREIGN.search(he):
        errs.append("foreign-script")
    name = is_name_or_code(source_en)
    if not name and he == source_en.strip():
        errs.append("identical-to-source")
    if not name and not HEB.search(he):
        errs.append("no-hebrew")
    src = Counter(TOKEN.findall(source_en))
    got = Counter(TOKEN.findall(he))
    if any(got[t] < n for t, n in src.items()):
        errs.append("missing-tokens")
    return errs


# ── env / Supabase REST ───────────────────────────────────────────────────────
def load_env() -> tuple[str, str]:
    url = key = None
    for line in (WEBSITE / ".env").read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("SUPABASE_URL="):
            url = s.split("=", 1)[1].strip().strip('"').strip("'")
        elif s.startswith("SUPABASE_SERVICE_ROLE_KEY="):
            key = s.split("=", 1)[1].strip().strip('"').strip("'")
    if not url or not key:
        sys.exit("ERROR: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY missing in website/.env")
    return url.rstrip("/"), key


def sb(method: str, path: str, body=None, prefer=None, timeout=60):
    headers = {"apikey": _KEY, "Authorization": "Bearer " + _KEY,
               "Content-Type": "application/json"}
    if prefer:
        headers["Prefer"] = prefer
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(_BASE + path, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8")
        return json.loads(raw) if raw.strip() else None


def fetch_flagged(game: str | None, limit: int) -> list[dict]:
    # pending submissions flagged for repair, with their source string embedded
    q = ("/rest/v1/translation_submissions"
         "?status=eq.pending&auto_qa->>needs_repair=eq.true"
         "&select=id,string_id,game_id,hebrew_text,auto_qa,"
         "translation_strings(source_en,string_key)"
         "&order=created_at.asc&limit=" + str(limit))
    if game:
        q += "&game_id=eq." + game
    return sb("GET", q) or []


def count_flagged(game: str | None) -> int:
    q = ("/rest/v1/translation_submissions"
         "?status=eq.pending&auto_qa->>needs_repair=eq.true&select=id")
    if game:
        q += "&game_id=eq." + game
    rows = sb("GET", q, prefer="count=exact")
    return len(rows or [])


# ── LM ────────────────────────────────────────────────────────────────────────
SYSTEM = (
    "You repair Hebrew video-game translations. You get an English source line "
    "and a contributor's rough draft. Output ONE corrected line that:\n"
    "- is natural, fluent Hebrew (fix grammar/wording; translate any leftover "
    "English to Hebrew).\n"
    "- copies EVERY tag/placeholder/format token from the SOURCE verbatim and "
    "in the right place: <...> tags, [UPPER_TOKEN], {VALUE}, %d/%s, \\n.\n"
    "- uses Hebrew + Latin letters ONLY. NO niqqud (vowel points). NO Arabic/"
    "Cyrillic/CJK or any other script.\n"
    "- keeps character & place names; keeps the source's punctuation/structure.\n"
    "Output ONLY the corrected Hebrew line — no quotes, no notes, no English."
)


def lm_chat(system: str, user: str, max_tokens: int = 512, timeout: int = LM_TIMEOUT) -> str:
    body = {"model": LM_MODEL,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "temperature": 0.2, "max_tokens": max_tokens, "stream": False}
    req = urllib.request.Request(LM_URL, data=json.dumps(body).encode(),
                                 method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read().decode("utf-8"))
    return (d["choices"][0]["message"]["content"] or "").strip()


def lm_responsive() -> bool:
    try:
        return bool(lm_chat("Reply with OK.", "OK", max_tokens=5, timeout=30))
    except Exception:
        return False


def reload_lm() -> None:
    """Only used with --manage-lm (solo runs). Never call while another
    translator holds the shared model."""
    try:
        subprocess.run(["cmd", "/c", "attrib", "-R",
                        os.path.expanduser(r"~\.lmstudio\.internal"), "/S", "/D"],
                       capture_output=True, timeout=30)
        subprocess.run(["lms", "unload", "--all"], capture_output=True, timeout=60)
        subprocess.run(["lms", "load", LM_MODEL, "-y", "--gpu", "max",
                        "--context-length", "8192", "--parallel", "1"],
                       capture_output=True, timeout=300)
    except Exception as e:
        log(f"reload_lm failed: {e}")


def strip_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\n?", "", s)
        s = re.sub(r"\n?```$", "", s)
    # drop a leading "Corrected Hebrew:" style echo
    s = re.sub(r"^(corrected hebrew|hebrew|תרגום|תיקון)\s*[:：-]\s*", "", s, flags=re.I)
    return s.strip()


# ── repair one submission ─────────────────────────────────────────────────────
def repair_one(sub: dict) -> tuple[str, list[str]] | None:
    """Return (repaired_he, []) on success, (best, errors) on failure, or
    None if the LM call itself errored (connection)."""
    st = sub.get("translation_strings") or {}
    source_en = st.get("source_en") or ""
    draft = sub.get("hebrew_text") or ""
    user = f"English: {source_en}\nDraft: {draft}\nCorrected Hebrew:"
    last_errs: list[str] = ["empty"]
    best = ""
    for attempt in range(2):  # one retry with a firmer nudge
        try:
            out = clean_he(strip_fences(lm_chat(SYSTEM, user)))
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            return None  # connection/LM problem — caller waits + retries the row
        except Exception as e:
            log(f"  lm error: {e}")
            return None
        if out:
            best = out
            errs = validate(source_en, out)
            if not errs:
                return out, []
            last_errs = errs
            # firmer second prompt naming exactly what's wrong
            user = (f"English: {source_en}\nDraft: {draft}\n"
                    f"Your previous answer had these problems: {', '.join(errs)}. "
                    f"Fix them. Output ONLY the corrected Hebrew line.\nCorrected Hebrew:")
    return best, last_errs


def patch_repaired(sub: dict, repaired: str, by: str) -> None:
    aq = dict(sub.get("auto_qa") or {})
    aq.update({"ok": True, "flags": [], "needs_repair": False,
               "repaired": True, "repaired_by": by})
    sb("PATCH", f"/rest/v1/translation_submissions?id=eq.{sub['id']}",
       body={"hebrew_text": repaired, "auto_qa": aq},
       prefer="return=minimal")


def patch_strike(sub: dict, errors: list[str]) -> bool:
    """Bump the strike counter; park (needs_repair=false) at MAX_STRIKES.
    Returns True if parked."""
    aq = dict(sub.get("auto_qa") or {})
    strikes = int(aq.get("repair_strikes", 0)) + 1
    aq["repair_strikes"] = strikes
    aq["flags"] = errors
    parked = strikes >= MAX_STRIKES
    if parked:
        aq["needs_repair"] = False
        aq["repaired"] = False
        aq.setdefault("flags", []).append("unrepairable")
    sb("PATCH", f"/rest/v1/translation_submissions?id=eq.{sub['id']}",
       body={"auto_qa": aq}, prefer="return=minimal")
    return parked


# ── infra: log + singleton ────────────────────────────────────────────────────
def log(msg: str) -> None:
    line = time.strftime("%Y-%m-%d %H:%M:%S") + "  " + msg
    print(line, flush=True)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def acquire_singleton() -> bool:
    """Crude but robust: a fresh lock (<120s old) means another instance is
    alive. A stale lock is taken over (a crashed run leaves it behind)."""
    try:
        if LOCK.exists() and (time.time() - LOCK.stat().st_mtime) < 120:
            return False
    except OSError:
        pass
    touch_lock()
    return True


def touch_lock() -> None:
    try:
        LOCK.write_text(str(os.getpid()), encoding="utf-8")
    except OSError:
        pass


# ── passes ────────────────────────────────────────────────────────────────────
def run_pass(game: str | None, limit: int, manage_lm: bool) -> int:
    """One pass over the flagged rows. Returns the number repaired."""
    rows = fetch_flagged(game, limit)
    if not rows:
        return 0
    if not lm_responsive():
        if manage_lm:
            log("LM unresponsive — reloading (solo mode)…")
            reload_lm()
            if not lm_responsive():
                log("LM still down after reload; waiting.")
                return -1
        else:
            log("LM (shared) unresponsive — waiting, will retry.")
            return -1
    repaired = parked = failed = 0
    for sub in rows:
        touch_lock()
        st = sub.get("translation_strings") or {}
        key = st.get("string_key", "?")
        res = repair_one(sub)
        if res is None:                       # connection problem mid-row
            log(f"  [{key}] LM/connection error — leaving for next pass")
            return repaired                   # bail the pass; row stays flagged
        text, errs = res
        if not errs:
            patch_repaired(sub, text, LM_MODEL)
            repaired += 1
            log(f"  [{key}] repaired ✓")
        else:
            if patch_strike(sub, errs):
                parked += 1
                log(f"  [{key}] parked after {MAX_STRIKES} tries ({','.join(errs)})")
            else:
                failed += 1
                log(f"  [{key}] still bad ({','.join(errs)}) — will retry")
    log(f"pass done: repaired={repaired} parked={parked} retry={failed}")
    return repaired


def loop(game: str | None, limit: int, manage_lm: bool) -> None:
    log(f"guard-dog up · model={LM_MODEL} · game={game or 'ALL'} · pid={os.getpid()}")
    while True:
        try:
            touch_lock()
            n = run_pass(game, limit, manage_lm)
            if n == -1:                       # LM down
                _sleep(POLL_LM_DOWN)
            elif n == 0:                      # nothing to do
                _sleep(POLL_EMPTY)
            else:
                _sleep(2)                     # more may be waiting — quick next pass
        except KeyboardInterrupt:
            log("interrupted — exiting")
            return
        except Exception as e:               # never let the guard dog die
            log(f"loop error: {e!r} — backing off")
            _sleep(30)


def _sleep(sec: int) -> None:
    # interruptible sleep so Ctrl+C is snappy
    end = time.time() + sec
    while time.time() < end:
        time.sleep(min(1, end - time.time()))


def main() -> None:
    global _BASE, _KEY
    _BASE, _KEY = load_env()
    ap = argparse.ArgumentParser(description="Community-translation repair guard-dog (LM)")
    ap.add_argument("--once", action="store_true", help="single pass then exit")
    ap.add_argument("--status", action="store_true", help="print flagged count and exit")
    ap.add_argument("--game", default=None, help="restrict to one game_id")
    ap.add_argument("--limit", type=int, default=BATCH_LIMIT)
    ap.add_argument("--manage-lm", action="store_true",
                    help="reload a dead LM (only when running solo — disrupts shared runs)")
    a = ap.parse_args()

    if a.status:
        print(f"submissions needing repair{f' [{a.game}]' if a.game else ''}: "
              f"{count_flagged(a.game)}")
        return

    if not acquire_singleton():
        log("another guard-dog instance is already running — exiting")
        return
    try:
        if a.once:
            run_pass(a.game, a.limit, a.manage_lm)
        else:
            loop(a.game, a.limit, a.manage_lm)
    finally:
        try:
            LOCK.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
