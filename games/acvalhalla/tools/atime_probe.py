#!/usr/bin/env python3
"""
atime_probe.py — find out which forges a game session actually opens.

Windows last-access tracking is ENABLED on this machine (`fsutil behavior query
DisableLastAccess` = 2), so every file the game reads gets its atime stamped. That turns
"which archive serves this screen?" from guesswork into a measurement.

    python atime_probe.py snap      # BEFORE launching the game
    <launch, reach the screen, quit>
    python atime_probe.py diff      # what the session touched

⚠️ Your own tooling clobbers atime — snapshot BEFORE any scan, and do not read the
forges between `snap` and `diff`. That is exactly how the first attempt lost the
evidence: the base forges looked "not opened" only because later scans overwrote it.
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.environ.get("ACM_GAME", r"F:/Game Lab/Assassin's Creed Mirage")
SNAP = os.path.join(HERE, "..", "work", "logo", "_atime_snap.json")

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def forges():
    out = []
    for root, _d, names in os.walk(GAME):
        for n in names:
            if n.lower().endswith(".forge"):
                out.append(os.path.join(root, n))
    return sorted(out)


def snap():
    data = {p: os.stat(p).st_atime for p in forges()}
    os.makedirs(os.path.dirname(SNAP), exist_ok=True)
    json.dump({"t": time.time(), "a": data}, open(SNAP, "w"))
    print(f"snapshot: {len(data)} forges at {time.strftime('%H:%M:%S')}")
    print("now launch the game, reach the screen with the logo, then quit.")


def diff():
    s = json.load(open(SNAP))
    base, t0 = s["a"], s["t"]
    print(f"snapshot taken {time.strftime('%H:%M:%S', time.localtime(t0))}; "
          f"now {time.strftime('%H:%M:%S')}\n")
    touched = []
    for p in forges():
        old = base.get(p)
        new = os.stat(p).st_atime
        if old is None or new > old + 1:
            touched.append((new, p))
    if not touched:
        print("NO forge was opened — the session did not read any archive (or atime is stale).")
        return
    print(f"{len(touched)} forge(s) opened during the session:")
    for t, p in sorted(touched):
        print(f"  {time.strftime('%H:%M:%S', time.localtime(t))}  {os.path.relpath(p, GAME)}")
    print("\nNOT opened (safe to stop searching in these):")
    for p in forges():
        if p not in [q for _t, q in touched]:
            print(f"  {os.path.relpath(p, GAME)}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "snap"
    {"snap": snap, "diff": diff}[cmd]()
