# -*- coding: utf-8 -*-
"""Push the W3 Arabic->Hebrew sub-task (1,447 lines whose English was corrupted) live to the
hub dashboard, on the witcher3 tab. Reads agent_arabic/hebrew.json (the pull merges the 3
streams there). 60 s loop -> POST /api/admin/progress (MONITOR_TOKEN from repo-root .env).
"""
import os, sys, json, time, urllib.request
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
BANK = os.path.join(HERE, "agent_arabic", "hebrew.json")
TT   = os.path.join(HERE, "agent_arabic", "to_translate.json")
HIST = os.path.join(HERE, "w3ar_progress_hist.json")

GAME_ID = "witcher3"
AI_MODEL = "llama-3.1-70b (NIM cloud, 3-stream)"
INTERVAL = 60
API = "https://hebrew-translation-hub.com"


def _load_env(path):
    env = {}
    try:
        for ln in open(path, encoding="utf-8"):
            ln = ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k, v = ln.split("=", 1); env[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return env


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


def push(token, processed, total, rate):
    body = json.dumps({
        "gameId": GAME_ID, "phase": "translation", "phaseLabelHe": "תיקון שורות ערבית",
        "processed": processed, "total": total, "ratePerHour": int(rate),
        "unit": "שורות", "meta": {"alive": True, "streams": 3},
        "aiModel": AI_MODEL, "gpuModel": "",
    }).encode("utf-8")
    req = urllib.request.Request(API + "/api/admin/progress", body,
                                 {"Content-Type": "application/json", "Authorization": "Bearer " + token})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status


def main():
    env = _load_env(os.path.join(ROOT, ".env"))
    token = env.get("MONITOR_TOKEN", "")
    if not token:
        print("no MONITOR_TOKEN — exiting"); return 1
    total = len(json.load(open(TT, encoding="utf-8")))
    print(f"W3-arabic pusher: total {total} lines, every {INTERVAL}s -> {API}")
    while True:
        try: done = len(json.load(open(BANK, encoding="utf-8")))
        except Exception: done = 0
        rate = _rate(done)
        try:
            st = push(token, done, total, rate)
            print(f"pushed {done}/{total} ({100*done/total:.1f}%) rate={int(rate)}/h -> {st}")
        except Exception as e:
            print(f"push failed: {e}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    raise SystemExit(main())
