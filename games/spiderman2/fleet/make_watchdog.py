# -*- coding: utf-8 -*-
r"""Derive the SM2 New-Era-2 watchdog from the Skyrim one — every replacement asserted.

The watchdog is what makes "runs smoothly to the end" true rather than aspirational: a hung
guest, a dead worker, a task someone disabled, a duplicated pusher. Deriving it instead of
hand-writing a second copy means a fix to the Skyrim watchdog can be re-applied here in one
command, and the asserted replacements make a silent no-op impossible.

🔴 The `$ZOMBIE` kill-list stays a NEVER-MATCHING PLACEHOLDER, on purpose. A hardcoded list of
other games' worker names in a RECURRING task outlives the project it belonged to: this exact
file (as skyrim_watchdog.ps1) spent a night executing the then-live RDR2 fleet on all seven
machines, leaving no traceback and a throughput ceiling indistinguishable from provider
throttling. A janitor may only ever kill ITS OWN workers.

Run:  python make_watchdog.py   ->  sm2ne2_watchdog.ps1
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "..", "skyrim", "fleet", "skyrim_watchdog.ps1")
DST = os.path.join(HERE, "sm2ne2_watchdog.ps1")

# (old, new) — order matters: the longest/most specific first, so a later broad rule can never
# eat a path a specific rule was meant to own.
SUBS = [
    ("# Skyrim fleet watchdog", "# Spider-Man 2 (New-Era-2 REVIEW) fleet watchdog"),
    (r"games\skyrim\fleet", r"games\spiderman2\fleet"),
    (r"C:\tmp\skyrim_watchdog.log", r"C:\tmp\sm2ne2_watchdog.log"),
    (r"dir='C:\skyrimw'", r"dir='C:\sm2w'"),
    ("dir='C:/Users/Nehoray_Cohen/Projects/skyrim_worker'",
     "dir='C:/Users/Nehoray_Cohen/Projects/sm2_worker'"),
    ("dir='C:/skyrimw'", "dir='C:/sm2w'"),
    ("skyrim_nim_ZOMBIE_PLACEHOLDER_never_matches", "sm2ne2_nim_ZOMBIE_PLACEHOLDER_never_matches"),
    ("skyrim_nim", "sm2ne2_nim"),
    ("'^Skyrim'", "'^Sm2'"),
    ("SkyrimFleetPull", "Sm2FleetPull"),
    ("SkyrimMP", "Sm2MP"),
    ("skyrim_progress", "sm2qa_progress"),
]


def main():
    s = open(SRC, encoding="utf-8").read()
    for a, b in SUBS:
        assert a in s, f"MISSING anchor: {a!r}"
        s = s.replace(a, b)
    # nothing of the outgoing game may survive except inside the incident comment that explains
    # WHY the kill-list is a placeholder — that history is the whole point of keeping it
    leftover = [l.strip() for l in s.splitlines()
                if ("skyrim" in l.lower()) and "2026-08-07" not in l and not l.strip().startswith("#")]
    assert not leftover, f"leftover skyrim references: {leftover[:3]}"
    open(DST, "w", encoding="utf-8").write(s)
    print(f"wrote {DST}  ({len(SUBS)} replacements, all anchors matched)")


if __name__ == "__main__":
    main()
