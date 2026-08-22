#!/usr/bin/env python3
"""apply_lqa_overrides.py — re-apply the LQA-verified line fixes after every merge.

`pull_missing.sh` REBUILDS hebrew_missing.json from the per-worker banks, so a fix written
straight into the bank is silently reverted on the next 5-minute pull — the same trap that
made the name-canon a no-op for the whole run. The verified fixes therefore live in
`lqa_overrides.json` (the durable record) and are re-applied here, every merge.

Only rewrites a key that is PRESENT in the bank and DIFFERENT, and prints how many lines it
actually changed — a transform that cannot report its own effect is indistinguishable from one
that never ran.
"""
from __future__ import annotations

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BANK = os.path.join(HERE, "hebrew_missing.json")
OV = os.path.join(HERE, "lqa_overrides.json")

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def main() -> None:
    if not os.path.exists(OV):
        return
    ov = json.load(open(OV, encoding="utf-8"))
    bank = json.load(open(BANK, encoding="utf-8"))
    hit = {k: v for k, v in ov.items() if k in bank and bank[k] != v}
    if not hit:
        print(f"lqa-overrides: 0 lines to re-apply ({len(ov)} on file)")
        return
    bank.update(hit)
    tmp = f"{BANK}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(bank, f, ensure_ascii=False)
    for wait in (0, 0.4, 1.0, 2.5, 5.0):
        if wait:
            time.sleep(wait)
        try:
            os.replace(tmp, BANK)
            print(f"lqa-overrides: re-applied {len(hit)} lines ({len(ov)} on file)")
            return
        except OSError:
            continue
    try:
        os.remove(tmp)
    except OSError:
        pass
    print(f"lqa-overrides: bank locked, {len(hit)} lines pending")


if __name__ == "__main__":
    main()
