"""
cp2077_master_pipeline.py
=========================
Unattended overnight pipeline — chains everything needed for full Hebrew coverage:

  STEP 1: Translate missing subtitle dialogue via LM Studio
          (cp2077_fix_missing_translations.py — local Gemma-2-27b, batch=3)
          ETA: ~1-3 hours for ~3,669 missing subtitle strings

  STEP 2: Inject all 3,083 subtitle CR2W files via Arabic-slot pipeline,
          then pack + deploy z_hebrew_translation.archive
          (cp2077_subtitle_batch.py)
          ETA: ~1-2 hours for serialize/apply/deserialize/pack

Total expected time: 2-5 hours unattended.

Logs to master_pipeline.log + each child script logs to its own file.
"""

import os
import sys
import subprocess
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PROJ_DIR = r"C:\Users\Nehoray_Cohen\Projects\Game translator"
LOG_FILE = os.path.join(PROJ_DIR, "master_pipeline.log")


def log(msg):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def run_step(step_name, script_name, args=None, timeout=None):
    log("=" * 70)
    log(f"STEP: {step_name}")
    log("=" * 70)
    cmd = [sys.executable, os.path.join(PROJ_DIR, script_name)] + (args or [])
    log(f"Running: {' '.join(cmd)}")
    log("")

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"

    t0 = time.time()
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=PROJ_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            bufsize=1,
        )
        # Stream child output to our log
        for raw in proc.stdout:
            line = raw.rstrip()
            if line:
                log(f"  > {line}")
        rc = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        log(f"STEP TIMEOUT after {timeout}s — killing")
        proc.kill()
        rc = -1
    except Exception as e:
        log(f"STEP EXCEPTION: {e}")
        rc = -2

    elapsed = time.time() - t0
    log("")
    log(f"STEP DONE: {step_name}  (exit={rc}, took {elapsed/60:.1f} min)")
    log("")
    return rc == 0


def main():
    log("=" * 70)
    log("MASTER PIPELINE STARTING")
    log("=" * 70)
    log("Plan:")
    log("  Step 1: cp2077_fix_missing_translations.py  (LM Studio translation)")
    log("  Step 2: cp2077_subtitle_batch.py            (inject + pack + deploy)")
    log("")

    t_start = time.time()

    # Step 1: Translate via LM Studio. This script processes onscreens + subtitles
    # and uses needs_translation() to skip entries that already have Hebrew, so
    # re-running over already-done onscreens is essentially free.
    ok1 = run_step(
        "Translate missing entries via LM Studio",
        "cp2077_fix_missing_translations.py",
        args=[],
        timeout=8 * 3600,  # 8 hours hard cap
    )
    if not ok1:
        log("[!] Step 1 had issues. Continuing anyway — partial translations are still useful.")

    # Step 2: subtitle_batch.py extracts → serializes → applies → deserializes
    # → packs → deploys, all in one run. It's resumable and skips already-done files.
    ok2 = run_step(
        "Inject subtitles + pack + deploy",
        "cp2077_subtitle_batch.py",
        args=[],
        timeout=14 * 3600,  # 14 hours hard cap
    )
    if not ok2:
        log("[!] Step 2 had issues. Check subtitle_batch.log for details.")

    total_min = (time.time() - t_start) / 60
    log("=" * 70)
    log(f"MASTER PIPELINE COMPLETE — total {total_min:.1f} min ({total_min/60:.2f}h)")
    log("=" * 70)
    log("")
    log("To verify deployment:")
    log("  ls -la 'C:/Game Lab/Cyberpunk 2077/archive/pc/mod/'")
    log("  Look for z_hebrew_translation.archive (should be ~7-15 MB now with subtitles)")


if __name__ == "__main__":
    main()
