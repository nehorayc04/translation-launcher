"""
cp2077_orchestrator.py
======================
Drives the final stages of the Cyberpunk 2077 Hebrew pipeline, unattended:

  STAGE 0  Admin check — warn if not elevated (process suspend may fail).
  STAGE 1  Monitor cp2077_subtitle_batch.py until it finishes.
  STAGE 2  Surgical cleanup:
             • re-run audit_translations.py for a fresh contamination count
             • if 0 flagged → stop (nothing to do)
             • else: SUSPEND any other LM Studio client (auto-detected) to
               give the cleanup run dedicated LM Studio inference throughput,
               run patch_615_flagged.py, then RESUME them
  STAGE 3  If patch_615 actually fixed entries → re-pack + deploy BOTH
           subtitles and onscreens so the corrections land in the archive.

Resource-contention note: the translator scripts are thin HTTP clients —
LM Studio itself holds the Gemma-2-27B VRAM. Suspending a client does NOT
free VRAM; it frees LM Studio's *inference queue* so the cleanup run isn't
fighting another client for throughput.

Suspend/resume uses ntdll.NtSuspendProcess / NtResumeProcess via ctypes —
the same syscall psutil.suspend() wraps — so no psutil dependency is needed.

Usage:
    python cp2077_orchestrator.py            # full unattended run
    python cp2077_orchestrator.py --dry-run  # report each stage, change nothing
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import subprocess
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ── Paths ─────────────────────────────────────────────────────────────────
SCRIPTS_DIR  = os.path.dirname(os.path.abspath(__file__))
SUBTITLE_LOG = os.path.join(SCRIPTS_DIR, "subtitle_batch.log")
AUDIT_REPORT = os.path.join(SCRIPTS_DIR, "audit_translations_report.txt")
PATCH_REPORT = os.path.join(SCRIPTS_DIR, "patch_615_report.json")
ORCH_LOG     = os.path.join(SCRIPTS_DIR, "cp2077_orchestrator.log")

SUBTITLE_SCRIPT   = "cp2077_subtitle_batch.py"
AUDIT_SCRIPT      = "audit_translations.py"
PATCH_SCRIPT      = "patch_615_flagged.py"
REBUILD_SUBS      = "rebuild_subtitles_and_pack.py"
REBUILD_ONSCREENS = "rebuild_onscreens_and_pack.py"

# Other scripts that hit LM Studio — suspended during the cleanup AI run.
# (patch_615_flagged.py and cp2077_subtitle_batch.py are deliberately NOT
#  here: the patch script is the one we WANT running, and the batch has
#  already finished by Stage 2.)
LM_CLIENT_SCRIPTS = ["steam_translator.py", "translate_queue_fast.py",
                     "translate_cleanup_all.py"]

POLL_SEC             = 60
SUBTITLE_TOTAL       = 3083
COMPLETION_THRESHOLD = 0.95     # process gone + progress below this = crash

# ── ctypes — process suspend/resume (no psutil) ───────────────────────────
PROCESS_SUSPEND_RESUME = 0x0800
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_ntdll    = ctypes.WinDLL("ntdll")
_kernel32.OpenProcess.restype  = ctypes.c_void_p
_kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
_kernel32.CloseHandle.restype  = ctypes.c_int
_kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
_ntdll.NtSuspendProcess.argtypes = [ctypes.c_void_p]
_ntdll.NtResumeProcess.argtypes  = [ctypes.c_void_p]


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(ORCH_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


# ── Stage 0 helpers ───────────────────────────────────────────────────────
def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


# ── Process enumeration ───────────────────────────────────────────────────
def list_python_processes() -> list[tuple[int, str]]:
    """[(pid, cmdline)] for every running python.exe / pythonw.exe, via
    PowerShell CIM. Returns [] on any failure (never raises)."""
    ps = (
        "@(Get-CimInstance Win32_Process -Filter "
        "\"Name='python.exe' OR Name='pythonw.exe'\" "
        "| Select-Object ProcessId,CommandLine) | ConvertTo-Json -Compress"
    )
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, text=True, timeout=30,
        )
        out = (r.stdout or "").strip()
        if not out:
            return []
        data = json.loads(out)
        if isinstance(data, dict):
            data = [data]
        procs: list[tuple[int, str]] = []
        for d in data:
            pid = d.get("ProcessId")
            cmd = d.get("CommandLine") or ""
            if pid is not None:
                procs.append((int(pid), cmd))
        return procs
    except Exception as e:                                # noqa: BLE001
        log(f"  [!] process enumeration failed: {e}")
        return []


def find_processes(script_basenames: list[str]) -> list[tuple[int, str]]:
    """Running python processes whose command line mentions one of the given
    script filenames. Excludes this orchestrator's own PID."""
    me = os.getpid()
    hits: list[tuple[int, str]] = []
    for pid, cmd in list_python_processes():
        if pid == me:
            continue
        low = cmd.lower()
        if any(name.lower() in low for name in script_basenames):
            hits.append((pid, cmd))
    return hits


def _nt_proc(pid: int, suspend: bool) -> None:
    """Suspend or resume every thread of `pid` via ntdll. Raises OSError."""
    h = _kernel32.OpenProcess(PROCESS_SUSPEND_RESUME, False, pid)
    if not h:
        raise OSError(f"OpenProcess failed pid={pid} "
                      f"(winerr {ctypes.get_last_error()})")
    try:
        fn = _ntdll.NtSuspendProcess if suspend else _ntdll.NtResumeProcess
        status = fn(h)
        if status != 0:
            verb = "Suspend" if suspend else "Resume"
            raise OSError(f"Nt{verb}Process pid={pid} "
                          f"status=0x{status & 0xFFFFFFFF:08X}")
    finally:
        _kernel32.CloseHandle(h)


# ── Sub-script runner ─────────────────────────────────────────────────────
def run_script(script: str, *args: str) -> int:
    """Run a sibling script with the same interpreter, streaming its output
    live. Returns the child's exit code."""
    cmd = [sys.executable, os.path.join(SCRIPTS_DIR, script), *args]
    log(f"  -> running: {script} {' '.join(args)}".rstrip())
    try:
        r = subprocess.run(cmd, cwd=SCRIPTS_DIR)
        log(f"  -> {script} exited {r.returncode}")
        return r.returncode
    except Exception as e:                                # noqa: BLE001
        log(f"  [!] {script} failed to run: {e}")
        return 1


# ── Report parsing ────────────────────────────────────────────────────────
def read_subtitle_progress() -> tuple[float | None, int | None, int | None]:
    """(fraction, processed, total) from the newest progress line in
    subtitle_batch.log, or (None, None, None)."""
    if not os.path.exists(SUBTITLE_LOG):
        return None, None, None
    try:
        with open(SUBTITLE_LOG, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()[-120:]
    except OSError:
        return None, None, None
    rx = re.compile(r"(\d+(?:\.\d+)?)%\s+([\d,]+)\s*/\s*([\d,]+)")
    for line in reversed(lines):
        m = rx.search(line)
        if m:
            processed = int(m.group(2).replace(",", ""))
            total     = int(m.group(3).replace(",", "")) or SUBTITLE_TOTAL
            return processed / total, processed, total
    return None, None, None


def read_audit_flagged_count() -> int | None:
    """The `# Flagged entries: N` count from audit_translations_report.txt."""
    if not os.path.exists(AUDIT_REPORT):
        return None
    try:
        with open(AUDIT_REPORT, "r", encoding="utf-8", errors="replace") as f:
            head = f.read(2000)
    except OSError:
        return None
    m = re.search(r"#\s*Flagged entries:\s*([\d,]+)", head)
    return int(m.group(1).replace(",", "")) if m else None


def read_patch_fixed_count() -> int | None:
    """The `fixed` count from patch_615_report.json."""
    if not os.path.exists(PATCH_REPORT):
        return None
    try:
        with open(PATCH_REPORT, "r", encoding="utf-8") as f:
            return int(json.load(f).get("fixed", 0))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


# ── Stages ────────────────────────────────────────────────────────────────
def stage1_monitor(dry_run: bool) -> bool:
    """Wait for cp2077_subtitle_batch.py to finish. Returns True on a clean
    completion, False if the batch process vanished while still < 95 %."""
    log("STAGE 1 — monitoring cp2077_subtitle_batch.py")
    while True:
        procs = find_processes([SUBTITLE_SCRIPT])
        frac, processed, total = read_subtitle_progress()
        pct = f"{frac * 100:.1f}% ({processed:,}/{total:,})" if frac is not None \
              else "progress unknown"

        if procs:
            log(f"  batch running — {len(procs)} process(es) — {pct}")
            if dry_run:
                log("  [dry-run] not waiting — treating batch as complete")
                return True
            time.sleep(POLL_SEC)
            continue

        log(f"  cp2077_subtitle_batch.py no longer running — last seen {pct}")
        if frac is None:
            log("  [!] no progress line in subtitle_batch.log — cannot confirm "
                "completion. Proceeding with caution.")
            return True
        if frac >= COMPLETION_THRESHOLD:
            log(f"  batch completed cleanly ({pct})")
            return True
        log(f"  [!] WARNING — batch gone but only at {pct} (< 95%). "
            f"Possible crash; NOT proceeding.")
        return False


def stage2_cleanup(dry_run: bool) -> str:
    """Returns: 'skip' (nothing flagged), 'repack' (fixes applied),
    'nofix' (flagged but nothing could be fixed)."""
    log("STAGE 2 — surgical cleanup")

    # 2a — fresh audit
    if dry_run:
        log("  [dry-run] would run audit_translations.py")
    else:
        run_script(AUDIT_SCRIPT)
    flagged = read_audit_flagged_count()
    log(f"  audit flagged entries: "
        f"{flagged if flagged is not None else 'unknown'}")

    if flagged == 0:
        log("  translations are clean — skipping patch + re-pack")
        return "skip"

    # 2b — detect LM Studio clients to suspend
    lm_procs = find_processes(LM_CLIENT_SCRIPTS)
    if lm_procs:
        for pid, cmd in lm_procs:
            log(f"  LM client detected: pid {pid} — {cmd[:90]}")
    else:
        log("  no other LM Studio clients running — nothing to suspend")

    if dry_run:
        log("  [dry-run] would suspend the above, run patch_615_flagged.py, resume")
        log("  [dry-run] assuming fixes would be applied → would re-pack")
        return "repack"

    # 2c — suspend, patch, resume (resume guaranteed by finally)
    suspended: list[int] = []
    try:
        for pid, _cmd in lm_procs:
            try:
                _nt_proc(pid, suspend=True)
                suspended.append(pid)
                log(f"  suspended pid {pid} (freed LM Studio throughput)")
            except OSError as e:
                log(f"  [!] could not suspend pid {pid}: {e}")
        run_script(PATCH_SCRIPT)
    finally:
        for pid in suspended:
            try:
                _nt_proc(pid, suspend=False)
                log(f"  resumed pid {pid}")
            except OSError as e:
                log(f"  [!] could not resume pid {pid}: {e} "
                    f"(process may have already exited)")

    # 2d — did anything actually change?
    fixed = read_patch_fixed_count()
    log(f"  patch_615 fixed entries: "
        f"{fixed if fixed is not None else 'unknown'}")
    return "repack" if (fixed and fixed > 0) else "nofix"


def stage3_deploy(dry_run: bool) -> None:
    log("STAGE 3 — final re-pack + deploy (subtitles + onscreens)")
    if dry_run:
        log(f"  [dry-run] would run {REBUILD_SUBS} then {REBUILD_ONSCREENS}")
        return
    # Subtitles first: re-bakes the patched subtitle CR2Ws into the project
    # tree. Onscreens second: its pack of the whole source/archive tree then
    # captures both domains' corrections in the final deployed archive.
    run_script(REBUILD_SUBS)
    run_script(REBUILD_ONSCREENS)


# ── Main ──────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description="CP2077 final-pipeline orchestrator.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Report each stage without suspending, calling the "
                         "LM, or deploying anything.")
    args = ap.parse_args()

    log("=" * 70)
    log(f"cp2077_orchestrator starting{'  (DRY RUN)' if args.dry_run else ''}")
    log("=" * 70)

    # Stage 0 — admin check
    if is_admin():
        log("STAGE 0 — elevated (admin): process suspend/resume fully supported")
    else:
        log("STAGE 0 — WARNING: NOT running as Administrator.")
        log("          Suspending same-user processes usually still works, but")
        log("          if NtSuspendProcess fails in Stage 2, re-launch this")
        log("          script from an elevated terminal (Run as administrator).")

    try:
        if not stage1_monitor(args.dry_run):
            log("ABORT — subtitle batch did not complete cleanly. "
                "Inspect subtitle_batch.log.")
            return 1

        decision = stage2_cleanup(args.dry_run)
        if decision == "skip":
            log("DONE — translations already clean; no re-pack needed.")
            return 0
        if decision == "nofix":
            log("DONE — flagged entries could not be auto-fixed; "
                "localization_translated.json unchanged, so no re-pack.")
            log("       Inspect patch_615.log for the failures.")
            return 0

        stage3_deploy(args.dry_run)
        log("=" * 70)
        log("DONE — orchestration complete. Hebrew corrections deployed.")
        log("=" * 70)
        return 0
    except KeyboardInterrupt:
        log("[!] interrupted by user — any suspended processes were resumed "
            "by Stage 2's finally block.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
