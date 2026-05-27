"""
cp2077_post_pipeline.py
=======================
The master automation driver for the Cyberpunk 2077 Hebrew project — one
unattended command for everything AFTER the markup translation run.

Stages:
  0  Preconditions     — LM Studio reachable, Cyberpunk 2077 not running.
  1  Finish translation— translate_cleanup_all.py --no-rebuild  (the ~clean
                          lines still in cleanup_queue.json; resumable).
  2  QA sweep          — suspend rival LM clients (incl. the watchdog), run
                          cp2077_qa_sweep.py (audit -> fix -> re-audit), resume.
  3  Bake subtitles    — rebuild_subtitles_and_pack.py over only the touched
                          subtitle sections (markup + phase-1 + QA-patched).
  4  Bake onscreens    — rebuild_onscreens_and_pack.py — packs the whole tree
                          and deploys the final archive (backup happens inside).
  5  Reports           — cp2077_status_report.py refreshes the status report.
  6  Watchdog          — launch cp2077_qa_watchdog.bat so the QA guard keeps
                          patrolling after this run exits.

Backups: stages 3 & 4 each back up z_hebrew_translation.archive into
archive\\pc\\mod_backups\\<timestamp>\\ before overwriting it (built into the
rebuild scripts).

Usage:
    python cp2077_post_pipeline.py              # full unattended run
    python cp2077_post_pipeline.py --dry-run    # report every stage, do nothing
    python cp2077_post_pipeline.py --skip-qa    # skip stage 2 (QA sweep)
    python cp2077_post_pipeline.py --full-subs  # stage 3 re-bakes ALL subtitles
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import cp2077_orchestrator as orch          # is_admin, find_processes, _nt_proc

# ── paths / config ──────────────────────────────────────────────────────────
SCRIPTS_DIR  = _HERE
LOG_FILE     = os.path.join(SCRIPTS_DIR, "cp2077_post_pipeline.log")
MASTER_LOG   = os.path.join(SCRIPTS_DIR, "master_pipeline_v2.log")
QA_REPORT    = os.path.join(SCRIPTS_DIR, "qa_sweep_report.json")
WATCHDOG_BAT = os.path.join(SCRIPTS_DIR, "cp2077_qa_watchdog.bat")
COMBINED_SECTIONS = os.path.join(SCRIPTS_DIR, "post_pipeline_subtitle_sections.txt")

SECTION_SOURCES = ["markup_touched_sections.txt", "phase1_subtitle_sections.txt"]

CLEANUP_SCRIPT   = "translate_cleanup_all.py"
QA_SWEEP_SCRIPT  = "cp2077_qa_sweep.py"
REBUILD_SUBS     = "rebuild_subtitles_and_pack.py"
REBUILD_ONSCR    = "rebuild_onscreens_and_pack.py"
STATUS_SCRIPT    = "cp2077_status_report.py"

# LM Studio clients suspended during the QA sweep so it gets the inference
# queue to itself (cp2077_qa_sweep.py is NOT here — it is the one we run).
LM_CLIENTS = ["steam_translator.py", "translate_queue_fast.py",
              "translate_cleanup_all.py", "cp2077_markup_translate.py",
              "cp2077_qa_watchdog.py"]

LM_MODELS_URL = "http://127.0.0.1:1234/v1/models"


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def run_script(script: str, *args: str) -> int:
    """Run a sibling script with the same interpreter, streaming its output."""
    cmd = [sys.executable, os.path.join(SCRIPTS_DIR, script), *args]
    log(f"  -> running {script} {' '.join(args)}".rstrip())
    try:
        r = subprocess.run(cmd, cwd=SCRIPTS_DIR)
        log(f"  -> {script} exited {r.returncode}")
        return r.returncode
    except Exception as e:                                  # noqa: BLE001
        log(f"  [!] {script} failed to launch: {e}")
        return 1


# ── Stage 0 — preconditions ─────────────────────────────────────────────────

def _lm_reachable() -> bool:
    try:
        with urllib.request.urlopen(LM_MODELS_URL, timeout=10) as r:
            return r.status == 200
    except Exception:
        return False


def _game_running() -> bool:
    try:
        r = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq Cyberpunk2077.exe", "/NH"],
            capture_output=True, text=True, timeout=20)
        return "Cyberpunk2077.exe" in (r.stdout or "")
    except Exception:
        return False                                # can't tell -> assume closed


def stage0_preconditions(dry: bool) -> bool:
    log("STAGE 0 — preconditions")
    ok = True
    if _game_running():
        log("  [!] Cyberpunk2077.exe is RUNNING — close the game before a "
            "deploy (the bake overwrites the live mod archive).")
        ok = False
    else:
        log("  game not running — deploy target is writable")
    if _lm_reachable():
        log("  LM Studio reachable at 127.0.0.1:1234")
    else:
        log("  [!] LM Studio is NOT reachable — stages 1-2 need it. "
            "Open LM Studio, load Gemma-2-27B, start the local server.")
        ok = False
    if dry and not ok:
        log("  [dry-run] preconditions failed — a real run would abort here.")
        return True
    return ok


# ── Stage 1 — finish translation ────────────────────────────────────────────

def stage1_finish_translation(dry: bool) -> None:
    log("STAGE 1 — finishing translation (clean lines)")
    if dry:
        log(f"  [dry-run] would run {CLEANUP_SCRIPT} --no-rebuild")
        return
    rc = run_script(CLEANUP_SCRIPT, "--no-rebuild")
    if rc != 0:
        log(f"  [!] {CLEANUP_SCRIPT} exited {rc} — QA will catch anything "
            "left untranslated; continuing.")


# ── Stage 2 — QA sweep (suspend rival LM clients) ───────────────────────────

def stage2_qa_sweep(dry: bool) -> None:
    log("STAGE 2 — QA sweep (audit -> fix -> re-audit)")
    lm_procs = orch.find_processes(LM_CLIENTS)
    for pid, cmd in lm_procs:
        log(f"  LM client detected: pid {pid} — {cmd[:80]}")
    if dry:
        log("  [dry-run] would suspend the above, run cp2077_qa_sweep.py, resume")
        return

    suspended: list[int] = []
    try:
        for pid, _cmd in lm_procs:
            try:
                orch._nt_proc(pid, suspend=True)
                suspended.append(pid)
                log(f"  suspended pid {pid}")
            except OSError as e:
                log(f"  [!] could not suspend pid {pid}: {e}")
        rc = run_script(QA_SWEEP_SCRIPT)
        if rc != 0:
            log(f"  [!] {QA_SWEEP_SCRIPT} exited {rc} — continuing to bake.")
    finally:
        for pid in suspended:
            try:
                orch._nt_proc(pid, suspend=False)
                log(f"  resumed pid {pid}")
            except OSError as e:
                log(f"  [!] could not resume pid {pid}: {e}")


# ── Stage 3 — bake subtitles ────────────────────────────────────────────────

def _read_section_file(path: str) -> set[str]:
    if not os.path.exists(path):
        return set()
    try:
        txt = open(path, "r", encoding="utf-8").read()
    except OSError:
        return set()
    return {s.strip() for s in txt.replace("\n", ",").split(",") if s.strip()}


def _collect_subtitle_sections() -> list[str]:
    sections: set[str] = set()
    for name in SECTION_SOURCES:
        sections |= _read_section_file(os.path.join(SCRIPTS_DIR, name))
    if os.path.exists(QA_REPORT):
        try:
            with open(QA_REPORT, "r", encoding="utf-8") as f:
                rep = json.load(f)
            sections |= set(rep.get("patched_sections", {}).get("subtitles", []))
        except (OSError, json.JSONDecodeError):
            pass
    return sorted(s for s in sections if s.startswith("subtitles/"))


def stage3_bake_subtitles(dry: bool, full_subs: bool) -> None:
    log("STAGE 3 — bake subtitles")
    if full_subs:
        log("  --full-subs — re-baking ALL subtitle sections")
        if dry:
            log(f"  [dry-run] would run {REBUILD_SUBS} --all")
            return
        run_script(REBUILD_SUBS, "--all")
        return

    sections = _collect_subtitle_sections()
    if not sections:
        log("  no touched subtitle sections found — skipping subtitle bake.")
        return
    with open(COMBINED_SECTIONS, "w", encoding="utf-8") as f:
        f.write(",".join(sections))
    log(f"  {len(sections):,} subtitle sections -> "
        f"{os.path.basename(COMBINED_SECTIONS)}")
    if dry:
        log(f"  [dry-run] would run {REBUILD_SUBS} --sections-file "
            f"{os.path.basename(COMBINED_SECTIONS)}")
        return
    run_script(REBUILD_SUBS, "--sections-file", COMBINED_SECTIONS)


# ── Stage 4 — bake onscreens + deploy ───────────────────────────────────────

def stage4_bake_onscreens(dry: bool) -> None:
    log("STAGE 4 — bake onscreens + deploy (backup runs inside the rebuild)")
    if dry:
        log(f"  [dry-run] would run {REBUILD_ONSCR}")
        return
    rc = run_script(REBUILD_ONSCR)
    if rc != 0:
        log(f"  [!] {REBUILD_ONSCR} exited {rc} — the deploy may not have "
            "completed; inspect rebuild_onscreens.log.")


# ── Stage 5 — reports ───────────────────────────────────────────────────────

def stage5_reports(dry: bool) -> None:
    log("STAGE 5 — refreshing status report")
    if dry:
        log(f"  [dry-run] would run {STATUS_SCRIPT}")
        return
    run_script(STATUS_SCRIPT)


# ── Stage 6 — launch the QA watchdog ────────────────────────────────────────

def stage6_launch_watchdog(dry: bool) -> None:
    log("STAGE 6 — launching the QA watchdog (castle guard)")
    if orch.find_processes(["cp2077_qa_watchdog.py"]):
        log("  watchdog already running — leaving it be.")
        return
    if dry:
        log(f"  [dry-run] would launch {os.path.basename(WATCHDOG_BAT)} "
            "in a new console")
        return
    if not os.path.exists(WATCHDOG_BAT):
        log(f"  [!] {WATCHDOG_BAT} missing — cannot launch the watchdog.")
        return
    try:
        subprocess.Popen(["cmd", "/c", WATCHDOG_BAT], cwd=SCRIPTS_DIR,
                         creationflags=subprocess.CREATE_NEW_CONSOLE)
        log("  watchdog launched — it will patrol every 20 min.")
    except Exception as e:                                  # noqa: BLE001
        log(f"  [!] could not launch the watchdog: {e}")


# ── main ────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="CP2077 Hebrew post-translation "
                                             "master pipeline.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Report every stage; run / suspend / deploy nothing.")
    ap.add_argument("--skip-qa", action="store_true",
                    help="Skip stage 2 (the QA sweep).")
    ap.add_argument("--full-subs", action="store_true",
                    help="Stage 3 re-bakes ALL subtitles, not just the touched "
                         "sections.")
    args = ap.parse_args()

    log("=" * 70)
    log(f"cp2077_post_pipeline starting{'  (DRY RUN)' if args.dry_run else ''}")
    log("=" * 70)
    # marker so progress_monitor recognises this as a master run
    try:
        with open(MASTER_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
                    f"MASTER PIPELINE — cp2077_post_pipeline\n")
    except OSError:
        pass

    if orch.is_admin():
        log("  elevated (admin) — process suspend/resume fully supported")
    else:
        log("  NOTE: not elevated — same-user suspend usually still works")

    try:
        if not stage0_preconditions(args.dry_run):
            log("ABORT — preconditions not met. Fix the above and re-run.")
            return 1

        stage1_finish_translation(args.dry_run)
        if args.skip_qa:
            log("STAGE 2 — skipped (--skip-qa)")
        else:
            stage2_qa_sweep(args.dry_run)
        stage3_bake_subtitles(args.dry_run, args.full_subs)
        stage4_bake_onscreens(args.dry_run)
        stage5_reports(args.dry_run)
        stage6_launch_watchdog(args.dry_run)

        log("=" * 70)
        log("DONE — post-translation pipeline complete." if not args.dry_run
            else "DONE — dry run complete (nothing was changed).")
        log("=" * 70)
        return 0
    except KeyboardInterrupt:
        log("[!] interrupted — any suspended processes were resumed by "
            "stage 2's finally block.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
