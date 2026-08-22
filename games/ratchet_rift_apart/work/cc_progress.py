# -*- coding: utf-8 -*-
"""Push Ratchet & Clank: Rift Apart COMMUNITY-COMPUTE progress to the hub dashboard.

Unlike the NIM fleet pushers, the work here is done by VOLUNTEER phones (BYOK), so
DONE / STREAMS come from the community control plane (Supabase `cc_stats` RPC), not
from local bank files:
    done    = cc_lines with status='done'
    total   = open + claimed + done   (the whole seeded queue)
    streams = workers active in the last 10 min  (= the volunteer devices)

Counted in LINES (each cc_lines row is one line). 60 s loop -> /api/admin/progress.
Run:  python cc_progress.py            (loop)
      python cc_progress.py --once     (single push, for a test)
"""
import os, sys, json, time, urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GAME_ID = "ratchet-rift-apart"        # MUST match the Supabase games row id (dashboard joins on it)
API = "https://hebrew-translation-hub.com"
INTERVAL = 60

# community control plane (same values the app ships — anon/publishable key + soft secret)
SB_URL = "https://mfudkftrluabqlrpkvtj.supabase.co"
SB_ANON = "sb_publishable_zq_z7pF4EwWH4HHzsYm6pQ_RAm7oc2x"
CC_SECRET = "cc_06950e1d42d186525b087a400bc522460ae3034fae0c75d4"

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
HIST = os.path.join(HERE, "cc_progress_hist.json")


def _load_env(path):
    env = {}
    try:
        for ln in open(path, encoding="utf-8"):
            ln = ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k, v = ln.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return env


def cc_stats():
    """{open, claimed, done, workers} for THIS game only (anon key + game filter — the queue now
    also holds other games' lines, e.g. hogwarts, so an unfiltered call would mix them in)."""
    body = json.dumps({"p_secret": CC_SECRET, "p_game": GAME_ID}).encode("utf-8")
    req = urllib.request.Request(
        SB_URL + "/rest/v1/rpc/cc_stats", body,
        {"apikey": SB_ANON, "Authorization": "Bearer " + SB_ANON, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _rate(done):
    hist = []
    try: hist = json.load(open(HIST, encoding="utf-8"))
    except Exception: hist = []
    now = time.time(); hist.append([now, done])
    hist = [p for p in hist if now - p[0] <= 3900][-80:]
    try: json.dump(hist, open(HIST, "w", encoding="utf-8"))
    except OSError: pass
    win = [p for p in hist if now - p[0] <= 1500] or hist[-2:]
    if len(win) < 2: return 0.0
    (t0, c0), (t1, c1) = win[0], win[-1]
    if t1 <= t0 or c1 < c0: return 0.0
    return (c1 - c0) / ((t1 - t0) / 3600.0)


def push(token, processed, total, rate, streams):
    body = json.dumps({
        "gameId": GAME_ID, "phase": "translation",
        "phaseLabelHe": "תרגום קהילתי · מכשירי מתנדבים",
        "processed": processed, "total": total, "ratePerHour": int(rate),
        "unit": "שורות", "meta": {"alive": True, "streams": streams, "countUnit": "lines"},
        "aiModel": f"תרגום רב לשונית - {streams} זרמים", "gpuModel": "",
    }).encode("utf-8")
    req = urllib.request.Request(API + "/api/admin/progress", body,
                                 {"Content-Type": "application/json", "Authorization": "Bearer " + token})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status


def one(token):
    s = cc_stats()
    done = int(s.get("done", 0))
    total = done + int(s.get("open", 0)) + int(s.get("claimed", 0))
    streams = int(s.get("workers", 0))
    rate = _rate(done)
    st = push(token, done, total, rate, max(streams, 0))
    pct = (100 * done / total) if total else 0
    print(f"pushed {done}/{total} ({pct:.1f}%) rate={int(rate)}/h streams={streams} -> {st}")


def main():
    once = "--once" in sys.argv
    env = _load_env(os.path.join(ROOT, ".env"))
    token = env.get("MONITOR_TOKEN", "")
    if not token:
        print("no MONITOR_TOKEN in .env — exiting"); return 1
    print(f"R&C community pusher (gameId={GAME_ID}) every {INTERVAL}s -> {API}"
          + (" [ONCE]" if once else ""))
    while True:
        try:
            one(token)
        except Exception as e:
            print(f"tick failed: {e}")
        if once:
            break
        time.sleep(INTERVAL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
