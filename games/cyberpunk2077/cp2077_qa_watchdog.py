"""
cp2077_qa_watchdog.py
=====================
The "castle guard" — a persistent background QA process for the Cyberpunk 2077
Hebrew translation.

Every ~20 minutes it re-audits localization_translated.json with the SAME
detection the one-shot sweep uses (cp2077_qa_defects.scan_all), and AUTO-FIXES
whatever it finds by re-translating the bad lines in place.

It deliberately NEVER re-bakes or re-deploys — fixing the data is in scope,
re-packing the game archive is not (that needs the game closed and is the
master pipeline's job). The monitor's QA stage shows when watchdog fixes are
waiting for a deploy.

Safety:
  * skips a tick while any translator / sweep / master pipeline is running
    (the watchdog is for the quiet periods between those);
  * takes cp2077_qa_defects' qa.lock for the fix, so it never races the sweep;
  * an entry that fails GIVEUP_AFTER ticks in a row is parked in
    qa_watchdog_giveup.json and no longer retried — no infinite LM burn;
  * if LM Studio is offline it reports the issue count and defers the fix
    instead of failing every entry.

It writes ~/.translation_manager/cp2077_qa_status.json — the cp2077 monitor
adapter reads that and surfaces a live "בקרת איכות" stage in the TUI / website
/ launcher.

Usage:
    python cp2077_qa_watchdog.py                 # run forever, 20-min ticks
    python cp2077_qa_watchdog.py --interval 600  # 10-min ticks
    python cp2077_qa_watchdog.py --once          # a single tick, then exit
    python cp2077_qa_watchdog.py --once --dry-run  # audit + report, no fixes
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import cp2077_qa_defects as qa
import cp2077_qa_sweep as sweep
import cp2077_orchestrator as orch
import patch_615_flagged as p615

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# ── paths / config ──────────────────────────────────────────────────────────
TRANSLATED_FILE = qa.TRANSLATED_FILE
EXPORT_FILE     = qa.EXPORT_FILE
STATUS_DIR      = os.path.join(os.path.expanduser("~"), ".translation_manager")
STATUS_FILE     = os.path.join(STATUS_DIR, "cp2077_qa_status.json")
GIVEUP_FILE     = os.path.join(_HERE, "qa_watchdog_giveup.json")
LOG_FILE        = os.path.join(_HERE, "cp2077_qa_watchdog.log")

DEFAULT_INTERVAL = 1200          # 20 minutes
GIVEUP_AFTER     = 3             # ticks an entry may fail before being parked

# A tick is skipped while any of these run — the watchdog guards the quiet
# periods, it must never fight a translator or the master pipeline for writes.
BUSY_SCRIPTS = [
    "cp2077_markup_translate.py", "translate_cleanup_all.py",
    "translate_queue_fast.py", "cp2077_qa_sweep.py",
    "cp2077_post_pipeline.py", "patch_615_flagged.py",
]


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


# ── giveup tracking ─────────────────────────────────────────────────────────

def _key(d) -> str:
    return f"{d.section}\x00{d.pk}\x00{d.field}"


def _key_tuple(t) -> str:
    return f"{t[0]}\x00{t[1]}\x00{t[2]}"


def load_giveup() -> dict:
    if not os.path.exists(GIVEUP_FILE):
        return {}
    try:
        with open(GIVEUP_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_giveup(counts: dict) -> None:
    try:
        tmp = GIVEUP_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(counts, f, ensure_ascii=False, indent=1)
        os.replace(tmp, GIVEUP_FILE)
    except OSError:
        pass


# ── status sidecar (read by progress_monitor's cp2077 adapter) ──────────────

def write_status(*, state: str, interval: int, issues_found: int = 0,
                  fixed_last_tick: int = 0, residual: int = 0,
                  by_kind: dict | None = None, permanently_failed: int = 0,
                  note: str = "") -> None:
    os.makedirs(STATUS_DIR, exist_ok=True)
    payload = {
        "updated_at":         datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "state":              state,      # clean|issues|fixed|deferred|error
        "issues_found":       issues_found,
        "fixed_last_tick":    fixed_last_tick,
        "residual":           residual,
        "permanently_failed": permanently_failed,
        "by_kind":            by_kind or {},
        "note":               note,
        "next_check_at": (datetime.now() + timedelta(seconds=interval))
                         .strftime("%Y-%m-%d %H:%M:%S"),
    }
    try:
        tmp = STATUS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, STATUS_FILE)
    except OSError as e:
        log(f"  [!] could not write status file: {e}")


def _lm_alive(client) -> bool:
    try:
        p615._lm_call(client, p615.SYSTEM_PROMPT, "ok")
        return True
    except Exception:
        return False


# ── one patrol tick ─────────────────────────────────────────────────────────

def tick(client, export: dict, interval: int, dry_run: bool) -> None:
    busy = orch.find_processes(BUSY_SCRIPTS)
    if busy:
        names = ", ".join(c.split("\\")[-1][:40] for _pid, c in busy)
        log(f"  translator/pipeline active — deferring tick ({names})")
        write_status(state="deferred", interval=interval,
                     note="a translator or the pipeline is running")
        return

    if not qa.acquire_lock("qa_watchdog"):
        log("  qa.lock held (a sweep is running?) — deferring tick")
        write_status(state="deferred", interval=interval,
                     note="qa.lock held by another QA process")
        return

    try:
        with open(TRANSLATED_FILE, "r", encoding="utf-8") as f:
            translated = json.load(f)

        defects = qa.scan_all(translated, export)
        by_kind = dict(Counter(d.kind for d in defects))
        counts  = load_giveup()
        parked  = {k for k, c in counts.items() if c >= GIVEUP_AFTER}
        fixable = [d for d in defects if _key(d) not in parked]
        perm    = sum(1 for d in defects if _key(d) in parked)

        if not defects:
            log("  clean — no defects.")
            write_status(state="clean", interval=interval, issues_found=0)
            return

        log(f"  {len(defects):,} defects (foreign={by_kind.get('foreign',0)} "
            f"english_leak={by_kind.get('english_leak',0)} "
            f"missing={by_kind.get('missing',0)} "
            f"structural={by_kind.get('structural',0)}); "
            f"{len(fixable):,} fixable, {perm:,} parked")

        if dry_run:
            write_status(state="issues", interval=interval,
                         issues_found=len(defects), residual=len(defects),
                         by_kind=by_kind, permanently_failed=perm,
                         note="dry-run — no fixes attempted")
            return

        if not fixable:
            write_status(state="issues", interval=interval,
                         issues_found=len(defects), residual=len(defects),
                         by_kind=by_kind, permanently_failed=perm,
                         note="all remaining defects are parked (unfixable)")
            return

        if not _lm_alive(client):
            log("  LM Studio offline — reporting issues, deferring fixes.")
            write_status(state="issues", interval=interval,
                         issues_found=len(defects), residual=len(defects),
                         by_kind=by_kind, permanently_failed=perm,
                         note="LM Studio offline — fixes deferred")
            return

        res = sweep.fix_defects(fixable, translated, export, client)
        if res["fixed"]:
            qa.atomic_write_json(TRANSLATED_FILE, translated)

        # update the giveup ledger: a key that failed this tick gains a strike,
        # a key that got fixed is cleared.
        failed = {_key_tuple(t) for t in res.get("failed_keys", set())}
        attempted = {_key(d) for d in fixable}
        for ks in attempted:
            if ks in failed:
                counts[ks] = counts.get(ks, 0) + 1
            else:
                counts.pop(ks, None)
        save_giveup(counts)

        residual = max(0, len(defects) - res["fixed"])
        log(f"  fixed {res['fixed']:,}, {residual:,} still flagged")
        write_status(state=("fixed" if res["fixed"] else "issues"),
                     interval=interval, issues_found=len(defects),
                     fixed_last_tick=res["fixed"], residual=residual,
                     by_kind=by_kind,
                     permanently_failed=sum(1 for c in counts.values()
                                            if c >= GIVEUP_AFTER),
                     note=("fixes applied — re-bake/deploy to push them in-game"
                           if res["fixed"] else "no entry could be fixed"))
    except Exception as e:                                  # noqa: BLE001
        log(f"  [!] tick error: {type(e).__name__}: {e}")
        write_status(state="error", interval=interval, note=str(e)[:200])
    finally:
        qa.release_lock()


# ── main loop ───────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="CP2077 Hebrew QA watchdog.")
    ap.add_argument("--interval", type=int, default=DEFAULT_INTERVAL,
                    help="seconds between patrols (default 1200 = 20 min)")
    ap.add_argument("--once", action="store_true", help="one tick, then exit")
    ap.add_argument("--dry-run", action="store_true",
                    help="audit + report only — never re-translate")
    args = ap.parse_args()

    log("=" * 70)
    log(f"cp2077_qa_watchdog starting — interval {args.interval}s"
        f"{'  (--once)' if args.once else ''}"
        f"{'  (DRY RUN)' if args.dry_run else ''}")

    if not os.path.exists(TRANSLATED_FILE) or not os.path.exists(EXPORT_FILE):
        log("FATAL: localization_translated.json / localization_export.json "
            "missing.")
        return 1

    # The English export is large and static — load it ONCE for the session.
    log(f"[*] loading English source {EXPORT_FILE} (once) …")
    with open(EXPORT_FILE, "r", encoding="utf-8") as f:
        export = json.load(f)
    log(f"[*] export loaded — {len(export):,} sections")

    client = None
    if not args.dry_run:
        if OpenAI is None:
            log("FATAL: the 'openai' package is required (pip install openai).")
            return 1
        client = OpenAI(base_url=p615.LM_URL, api_key="lm-studio", timeout=600)

    try:
        while True:
            log("— patrol —")
            tick(client, export, args.interval, args.dry_run)
            if args.once:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        log("[!] stopped by user.")
        qa.release_lock()
    log("cp2077_qa_watchdog exiting.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
