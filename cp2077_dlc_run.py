"""
cp2077_dlc_run.py
=================
Crash-resilient supervisor for the DLC translation.

cp2077_dlc_translate.py is fully resumable — dlc_ep1_translated.json is its
state, checkpointed every 50 (markup) / 200 (plain) entries. But a ~50h
unattended run can have the process killed (a one-off exit 127 was seen
2026-05-22 06:24). This supervisor simply re-launches the translator after
any abnormal exit, so the run survives process deaths without intervention.

Stop conditions:
  * the translator exits 0  -> it finished its collected work cleanly: DONE.
  * 0 entries still need translation                                 : DONE.
  * the translator died but the untranslated count did NOT drop       : the
    remainder is unfixable (codes / failed validation) — stop, don't spin.

Logs to cp2077_dlc_run.log. Run: python cp2077_dlc_run.py
"""
from __future__ import annotations

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

HERE   = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "cp2077_dlc_translate.py")
DLC    = os.path.join(HERE, "תרגום_משחקים", "source", "resources",
                      "dlc_ep1_translated.json")
LOG    = os.path.join(HERE, "cp2077_dlc_run.log")

HEB = re.compile(r"[֐-׿]")
LAT = re.compile(r"[A-Za-z]")
MAX_RUNS = 400


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [supervisor] {msg}"
    print(line, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def untranslated() -> int:
    """Entries whose femaleVariant/maleVariant is still English (Latin, no
    Hebrew) — the translator's remaining work, plus the irreducible
    code/non-translatable tail."""
    try:
        d = json.load(open(DLC, encoding="utf-8"))
    except Exception:                                       # noqa: BLE001
        return -1
    n = 0
    for rows in d.values():
        if not isinstance(rows, list):
            continue
        for e in rows:
            if not isinstance(e, dict):
                continue
            for fld in ("femaleVariant", "maleVariant"):
                v = e.get(fld) or ""
                if v and LAT.search(v) and not HEB.search(v):
                    n += 1
    return n


def main() -> int:
    log("=" * 60)
    log("DLC translation supervisor starting")
    for attempt in range(1, MAX_RUNS + 1):
        before = untranslated()
        log(f"run {attempt}: {before:,} entries still English (untranslated)")
        if before == 0:
            log("nothing untranslated — DONE")
            return 0

        t0 = time.time()
        rc = subprocess.run([sys.executable, SCRIPT], cwd=HERE).returncode
        mins = (time.time() - t0) / 60
        after = untranslated()
        log(f"run {attempt}: translator exited rc={rc} after {mins:.0f} min; "
            f"untranslated {before:,} -> {after:,}")

        if rc == 0:
            log("translator exited cleanly — collected work finished. DONE.")
            return 0
        if after < 0:
            log("could not read dlc_ep1_translated.json — stopping.")
            return 1
        if after >= before:
            log("translator died and made NO progress — remaining entries are "
                "unfixable (codes / validation failures). Stopping.")
            return 0
        log(f"translator died (rc={rc}) but made progress — resuming in 20s …")
        time.sleep(20)

    log(f"hit MAX_RUNS ({MAX_RUNS}) — stopping.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
