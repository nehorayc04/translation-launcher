"""
cp2077_master_pipeline_v2.py
============================
Full re-extraction + translation + injection pipeline for subtitle dialogue.

Step 1: Re-extract en-us subtitle text via WolvenKit (fixes the empty-source bug)
Step 2: Translate newly-discovered English entries via LM Studio (Gemma-2-27b)
Step 3: Apply translations + pack + deploy via subtitle batch

Designed for unattended overnight runs. Resumable. Logs to master_pipeline_v2.log.

ETA: Step 1 ~6h, Step 2 ~24h, Step 3 ~3h = ~33h total.
"""

import os
import sys
import subprocess
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PROJ_DIR = r"C:\Users\nc528\סקריפטים\תרגום משחקים"
LOG_FILE = os.path.join(PROJ_DIR, "master_pipeline_v2.log")


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
        proc = subprocess.Popen(cmd, cwd=PROJ_DIR, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True,
                                encoding="utf-8", errors="replace",
                                env=env, bufsize=1)
        for raw in proc.stdout:
            line = raw.rstrip()
            if line:
                log(f"  > {line}")
        rc = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        log(f"STEP TIMEOUT after {timeout}s")
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
    log("MASTER PIPELINE V2 STARTING")
    log("=" * 70)
    log("Plan:")
    log("  Step 1: cp2077_reextract_subtitles.py    (re-extract en-us subtitle source)")
    log("  Step 2: cp2077_fix_missing_translations.py  (LM Studio translation)")
    log("  Step 3: cp2077_subtitle_batch.py         (inject + pack + deploy)")
    log("")

    t_start = time.time()

    if not run_step(
        "Re-extract subtitle source from EN-US CR2W",
        "cp2077_reextract_subtitles.py",
        timeout=10 * 3600,
    ):
        log("[!] Step 1 had issues — aborting (translation needs the source text)")
        sys.exit(1)

    # Clear subtitle entries from skip list before translation, otherwise the
    # translator will skip the very entries we just re-extracted.
    try:
        import json
        skip_path = os.path.join(PROJ_DIR, r"תרגום_משחקים\source\resources\translation_skips.json")
        if os.path.exists(skip_path):
            import shutil
            backup = skip_path + f".bak.v2.{int(time.time())}"
            shutil.copy2(skip_path, backup)
            with open(skip_path, "r", encoding="utf-8") as f:
                skips = json.load(f)
            before = len(skips)
            filtered = [s for s in skips if not s[0].startswith("subtitles")]
            with open(skip_path, "w", encoding="utf-8") as f:
                json.dump(filtered, f, ensure_ascii=False, indent=2)
            log(f"Cleared subtitle skips: {before:,} -> {len(filtered):,} (backup: {backup})")
    except Exception as e:
        log(f"[!] Skip-list clear had issue: {e} (continuing)")

    if not run_step(
        "Translate newly-discovered subtitle text via LM Studio",
        "cp2077_fix_missing_translations.py",
        timeout=36 * 3600,
    ):
        log("[!] Step 2 had issues. Continuing — partial translations are still useful.")

    if not run_step(
        "Inject subtitles + pack + deploy",
        "cp2077_subtitle_batch.py",
        timeout=14 * 3600,
    ):
        log("[!] Step 3 had issues. Check subtitle_batch.log for details.")

    total_min = (time.time() - t_start) / 60
    log("=" * 70)
    log(f"MASTER PIPELINE V2 COMPLETE — total {total_min:.1f} min ({total_min/60:.2f}h)")
    log("=" * 70)


if __name__ == "__main__":
    main()
