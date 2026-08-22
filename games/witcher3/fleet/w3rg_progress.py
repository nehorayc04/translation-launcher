# -*- coding: utf-8 -*-
"""Push the W3 QA-cleanup (re-translating the ~1,126 lines that had an English fragment glued
into the Hebrew) live to the hub, on the witcher3 tab. The main TRANSLATION is 100% done; this
is a quality pass, so the label says QA/ניקוי (not תרגום) and the count is the cleanup set.
Reads reglue_hebrew.json (the pull merges vm3+vm5 there). 60 s loop -> /api/admin/progress.
"""
import os, sys, json, time, urllib.request
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
BANK = os.path.join(HERE, "reglue_hebrew.json")
CORPUS = os.path.join(HERE, "reglue_corpus.json")
HIST = os.path.join(HERE, "w3rg_progress_hist.json")

GAME_ID = "witcher3"
AI_MODEL = "llama-3.1-70b (NIM cloud, 2-stream) — QA cleanup"
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
        "gameId": GAME_ID, "phase": "qa", "phaseLabelHe": "ניקוי תרגום (QA)",
        "processed": processed, "total": total, "ratePerHour": int(rate),
        "unit": "שורות", "meta": {"alive": True, "streams": 2},
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
    total = len(json.load(open(CORPUS, encoding="utf-8")))
    print(f"W3 QA-cleanup pusher: total {total} lines, every {INTERVAL}s -> {API}")
    while True:
        try: done = min(len(json.load(open(BANK, encoding="utf-8"))), total)
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
