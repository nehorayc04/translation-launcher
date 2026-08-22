# -*- coding: utf-8 -*-
"""chain_progress.py — push the overnight chain's 0->100% to the website.

Reads the live state of every chain stage from its own log/output files and
maps it onto a single weighted 0-100% bar, pushed to the hub's
/api/admin/progress (gameId=cyberpunk2077) every 60s — the same QA channel
the project always uses. Pure read-only; runs as its own background loop
alongside the chain.

Stage weights (sum 100):
   5  subtitle bake (current 590)        -> reads rebuild_subtitles.log [n/590]
   3  glossary unify                     -> g4_chain.log marker
  42  gemma-4 judging                    -> gemma4_judgments.jsonl / queue
   3  merge                              -> g4_chain.log marker
  15  onscreens bake                     -> rebuild_onscreens.log
  12  touched-subtitle bake              -> rebuild_subtitles.log restart
  18  DLC bake (716)                      -> rebuild_dlc.log [n/716]
   2  done                               -> "ALL DONE" marker
"""
import os, re, sys, time, json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "universal"))
from progress_monitor.core import Monitor, Snapshot   # type: ignore

CHAIN_LOG = os.path.join(HERE, "g4_chain.log")
SUB_LOG = os.path.join(HERE, "rebuild_subtitles.log")
ONS_LOG = os.path.join(HERE, "rebuild_onscreens.log")
DLC_LOG = os.path.join(HERE, "rebuild_dlc.log")
QUEUE = os.path.join(HERE, "gemma4_queue.jsonl")
JUDG = os.path.join(HERE, "gemma4_judgments.jsonl")

# WALL-TIME weighted (not item-count) so the % reflects time-to-ready, not
# raw items. The DLC bake is only 716 items but ~6h — the long tail; the
# subtitle bake #1 (~3h) is already done. Weights ~ estimated hours.
WEIGHTS = [("subbake1", 20), ("unify", 1), ("judge", 27), ("merge", 1),
           ("onsbake", 1), ("subbake2", 12), ("dlcbake", 36), ("done", 2)]


def tail_text(p, n=4000):
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            return f.read()[-n:]
    except OSError:
        return ""


def count_lines(p):
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def last_bake_frac(log, total):
    """[n/total] from the most recent bake progress line."""
    m = re.findall(r"\[(\d+)/" + str(total) + r"\]", tail_text(log, 8000))
    return (int(m[-1]) / total) if m else 0.0


def compute():
    chain = tail_text(CHAIN_LOG, 8000)

    def reached(marker):
        return marker in chain

    frac = {k: 0.0 for k, _ in WEIGHTS}
    # subtitle bake #1 (the one we wait on)
    if reached("subtitle bake DONE"):
        frac["subbake1"] = 1.0
    else:
        frac["subbake1"] = last_bake_frac(SUB_LOG, 590)
        return frac, "subbake1", "אופה כתוביות"

    if reached("STAGE unify") or reached("STAGE queue"):
        frac["unify"] = 1.0
    if reached("STAGE judge") or reached("STAGE merge"):
        frac["unify"] = 1.0
        # judging fraction = judged / queued
        q = count_lines(QUEUE)
        j = count_lines(JUDG)
        frac["judge"] = (j / q) if q else (1.0 if reached("STAGE merge") else 0.0)
        if not reached("STAGE merge"):
            return frac, "judge", f"gemma-4 שופט {j}/{q}"
    if reached("gemma4 round COMPLETE"):
        frac["unify"] = frac["judge"] = frac["merge"] = 1.0
    if reached("baking onscreens"):
        frac["merge"] = 1.0
        frac["onsbake"] = 1.0 if reached("baking touched subtitles") else last_bake_frac(ONS_LOG, 2)
        if not reached("baking touched subtitles"):
            return frac, "onsbake", "אופה onscreens"
    if reached("baking touched subtitles"):
        frac["onsbake"] = 1.0
        frac["subbake2"] = 1.0 if reached("baking DLC") else last_bake_frac(SUB_LOG, 99999) or 0.5
        if not reached("baking DLC"):
            return frac, "subbake2", "אופה כתוביות שתוקנו"
    if reached("baking DLC"):
        frac["subbake2"] = 1.0
        frac["dlcbake"] = 1.0 if reached("ALL DONE") else last_bake_frac(DLC_LOG, 716)
        if not reached("ALL DONE"):
            return frac, "dlcbake", "אופה DLC"
    if reached("ALL DONE"):
        for k, _ in WEIGHTS:
            frac[k] = 1.0
        return frac, "done", "הושלם"
    return frac, "judge", "מעבד"


_DONE = {"v": False}
_TOTAL_W = sum(w for _, w in WEIGHTS)
_HIST = []          # (epoch, pct) for %/h rate calc
_STAGE_LBL = {"subbake1": "אופה כתוביות", "unify": "מאחד מילון",
              "judge": "gemma-4 שופט", "merge": "ממזג תיקונים",
              "onsbake": "אופה onscreens", "subbake2": "אופה כתוביות מתוקנות",
              "dlcbake": "אופה DLC", "done": "הושלם"}


def _adapter(now=None):
    now = now if now is not None else __import__("time").time()
    frac, stage, label = compute()
    pct = sum(frac[k] * w for k, w in WEIGHTS) / _TOTAL_W * 100
    if stage == "done":
        _DONE["v"] = True
        pct = 100.0
    # rate = percent-points per hour over the last ~15 min window
    _HIST.append((now, pct))
    while _HIST and now - _HIST[0][0] > 900:
        _HIST.pop(0)
    rate = 0
    if len(_HIST) >= 2:
        dt = now - _HIST[0][0]
        if dt > 0:
            rate = round((pct - _HIST[0][1]) / dt * 3600, 1)
    print(f"[{time.strftime('%H:%M:%S')}] {pct:5.1f}%  {stage:8} {label}  rate={rate}%/h",
          flush=True)
    return Snapshot(
        game_id="cyberpunk2077",
        phase="qa",
        phase_label_he=f"בקרת איכות — {_STAGE_LBL.get(stage, label)} ({round(pct)}%)",
        processed=int(round(pct)),
        total=100,
        rate_per_hour=int(rate),
        unit="%",
        ai_model="gemma-4-31b-it",
        headline_he="בקרת איכות תרגום סייברפאנק 2077",
        meta={"stage": stage, "detail": label, "ratePctPerHour": rate},
    )


def main():
    mon = Monitor(game_id="cyberpunk2077", adapter=_adapter)
    mon.interval_s = 60          # push every minute
    while not _DONE["v"]:
        mon.push(_adapter())
        if _DONE["v"]:
            break
        time.sleep(60)
    mon.push(_adapter())
    print("chain complete -> progress pusher stopped at 100%", flush=True)


if __name__ == "__main__":
    main()
